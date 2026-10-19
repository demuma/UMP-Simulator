#include "CellLocalAggregation.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <utility>
#include <set>

namespace ump {
namespace {
bool containsCell(const CellGeometry& outer, const CellGeometry& inner) {
    return outer.depth <= inner.depth
        && (inner.id >> (2 * (inner.depth - outer.depth))) == outer.id;
}
bool passed(const AggregationCandidate& candidate, const WindowMetricAssessment& assessment) {
    return candidate.coverage == WindowCoverage::Complete
        && (assessment.status == AssessmentStatus::Pass || assessment.status == AssessmentStatus::NoCandidates);
}
}

CellLocalAggregation::CellLocalAggregation(AggregationConfig settings,
    TemporalAdaptationConfig timeSettings, SpatialSelectionConfig spaceSettings,
    MetricEvaluator metrics, Sink output, std::size_t maximum)
    : config(std::move(settings)), temporal(timeSettings), spatial(spaceSettings),
      evaluator(std::move(metrics)), sink(std::move(output)), maxActiveCells(maximum) {
    historyCell(config.coverage, 12, 1);
    adaptationStrategyName(temporal.strategy);
    if (!sink || config.samplingPeriodMs <= 0 || config.windowMs <= 0
        || config.windowMs % config.samplingPeriodMs || temporal.extensionStepMs <= 0
        || temporal.extensionStepMs % config.samplingPeriodMs
        || temporal.maxWindowMs < config.windowMs
        || temporal.maxWindowMs % config.samplingPeriodMs || !temporal.maxEvaluations
        || temporal.maxWindowMs > 9007199254740991LL || !config.history
        || config.history->retentionMs < temporal.maxWindowMs
        || spatial.minDepth < 1 || spatial.minDepth > config.coverage.leafDepth
        || !spatial.maxEvaluations || maxActiveCells < 4)
        throw std::invalid_argument("Cell-local aggregation requires aligned bounded windows, history, valid spatial limits and at least four owners");
    for (int id = 12; id <= 15; ++id) {
        const auto cell = historyCell(config.coverage, id, 1);
        frontier.emplace(id, makeWindow(cell, 0));
    }
}

CellLocalAggregation::Window CellLocalAggregation::makeWindow(const CellGeometry& cell,
    AggregationTime start, std::optional<CellGeometry> previous) const {
    AggregationTime cap = temporal.maxWindowMs;
    AggregationTime minimum = config.windowMs;
    AggregationCandidate footprint{config.runId, config.sensorId, config.applicationId,
        config.coverage, start, start + 1, start + 1, false, 0, 0, 0, 0,
        WindowCoverage::NoScheduledSamples, {}, {{cell, {}}}};
    const auto assessed = evaluator.evaluate(footprint, start + 1);
    for (const auto& check : assessed.cells.at(0).checks) {
        if ((check.requirement.id == MetricId::WindowDurationMs
                || check.requirement.id == MetricId::AgeAtEvaluationMs) && check.requirement.max
            && *check.requirement.max < static_cast<double>(cap))
            cap = static_cast<AggregationTime>(*check.requirement.max);
        if (check.requirement.id == MetricId::WindowDurationMs && check.requirement.min
            && *check.requirement.min < static_cast<double>(temporal.maxWindowMs))
            minimum = std::max(minimum, static_cast<AggregationTime>(*check.requirement.min));
    }
    cap -= cap % config.samplingPeriodMs;
    if (cap <= 0)
        throw std::invalid_argument("A cell-local time maximum allows no positive sampling-aligned interval");
    if (minimum % config.samplingPeriodMs)
        minimum += config.samplingPeriodMs - minimum % config.samplingPeriodMs;
    Window result{{cell, start, start + std::min(minimum, cap), start + cap, 0, 0}, {}, {}, previous};
    return result;
}

void CellLocalAggregation::validateDomain(const CellGeometry& cell) const {
    const auto canonical = historyCell(config.coverage, cell.id, cell.depth);
    const auto close = [&](double a, double b) {
        const auto tolerance = std::min(std::ldexp(config.coverage.width, -config.coverage.leafDepth) * 1e-4,
            1e-6 * std::max({1.0, std::abs(a), std::abs(b)}));
        return std::isfinite(a) && std::abs(a - b) <= tolerance;
    };
    if (!close(cell.x, canonical.x) || !close(cell.y, canonical.y)
        || !close(cell.width, canonical.width) || !close(cell.height, canonical.height))
        throw std::invalid_argument("Cell-local domain geometry differs from its cell ID");
}

void CellLocalAggregation::validateTime(AggregationTime now, const AggregationHistory& history) const {
    if (finished || emitting)
        throw std::logic_error("Cell-local stream is finished or its sink is reentrant");
    if (now < lastNowMs || now < 0 || history.debugState().watermarkMs != now)
        throw std::invalid_argument("Cell-local evaluation requires monotonic, already advanced history");
    if (now > 9007199254740991LL - temporal.maxWindowMs)
        throw std::overflow_error("Cell-local clock exceeds the exact numeric range");
}

AggregationCandidate CellLocalAggregation::query(const CellGeometry& cell, AggregationTime start,
    AggregationTime end, const AggregationHistory& history, bool final) const {
    const auto found = history.query(cell, start, end);
    if (!found.candidate)
        throw std::runtime_error("Cell-local interval is unavailable from bounded source history");
    auto candidate = *found.candidate;
    const auto& grid = candidate.grid;
    if (candidate.runId != config.runId || candidate.sensorId != config.sensorId
        || candidate.applicationId != config.applicationId || grid.x != config.coverage.x
        || grid.y != config.coverage.y || grid.width != config.coverage.width
        || grid.height != config.coverage.height || grid.leafDepth != config.coverage.leafDepth)
        throw std::invalid_argument("Cell-local source history belongs to another stream or grid");
    candidate.truncated = final;
    return candidate;
}

void CellLocalAggregation::retryPending(AggregationTime now) {
    if (!pending) return;
    const auto checked = evaluator.evaluate(pending->selection.candidate, now);
    for (std::size_t i = 0; i < pending->selection.decisions.size(); ++i)
        if (pending->selection.decisions[i].selected
            && (checked.coverageStatus != AssessmentStatus::Pass
                || checked.cells.at(i).status != AssessmentStatus::Pass))
            throw std::runtime_error("Cell-local publication deadline expired; immutable reservation remains held");
    emitting = true;
    try { sink(pending->selection); }
    catch (...) { emitting = false; throw; }
    emitting = false;
    // All allocations, policy checks and successor construction precede disclosure.
    for (int id : pending->retiredIds) frontier.erase(id);
    frontier.merge(pending->replacements); // Transfers preallocated map nodes.
    pending.reset();
    ++completedWindows;
}

void CellLocalAggregation::emit(SpatialSelection selection, Frontier replacements, std::vector<int> retiredIds) {
    if (pending) throw std::logic_error("A cell-local immutable output is already reserved");
    std::set<int> retired(retiredIds.begin(), retiredIds.end());
    if (retired.size() != retiredIds.size() || retiredIds.size() > frontier.size()
        || replacements.size() > maxActiveCells - (frontier.size() - retiredIds.size()))
        throw std::length_error("Cell-local replacement ownership budget exceeded");
    for (int id : retiredIds)
        if (!frontier.count(id)) throw std::logic_error("Cell-local replacement does not own its retired footprint");
    for (const auto& [id, window] : replacements)
        if (frontier.count(id) && !retired.count(id))
            throw std::logic_error("Cell-local replacement collides with an unaffected owner");
    pending.emplace(Pending{std::move(selection), std::move(replacements), std::move(retiredIds)});
    retryPending(pending->selection.candidate.closedAtMs);
}

void CellLocalAggregation::refineToDomain(Frontier& cut, const CellGeometry& domain) const {
    for (;;) {
        auto enclosing = cut.end();
        for (auto it = cut.begin(); it != cut.end(); ++it)
            if (it->second.publicState.cell.depth < domain.depth
                && containsCell(it->second.publicState.cell, domain)) { enclosing = it; break; }
        if (enclosing == cut.end()) return;
        if (cut.size() > maxActiveCells - 3)
            throw std::length_error("Cell-local active ownership budget exceeded");
        const auto old = enclosing->second;
        cut.erase(enclosing);
        for (int q = 0; q < 4; ++q) {
            const auto child = historyCell(config.coverage, (old.publicState.cell.id << 2) | q,
                old.publicState.cell.depth + 1);
            auto next = makeWindow(child, old.publicState.startMs, old.previousSelected);
            next.publicState.extensions = old.publicState.extensions;
            next.publicState.evaluations = old.publicState.evaluations;
            next.decisions = old.decisions;
            // Keep already scheduled temporal progress, capped by this child's own
            // absolute deadline. The contribution's original start never changes.
            if (old.publicState.extensions)
                next.publicState.nextEndMs = std::min(old.publicState.nextEndMs, next.publicState.hardDeadlineMs);
            cut.emplace(child.id, std::move(next));
        }
    }
}

void CellLocalAggregation::refineDue(AggregationTime endpoint, const AggregationHistory& history) {
    // Query fine support once per distinct start, then split only occupied paths.
    // Empty sibling areas stay represented by compressed owners. This refinement
    // happens before output, so an occupied region never waits for a coarse policy.
    std::map<AggregationTime, std::vector<CellGeometry>> observed;
    for (const auto& [id, window] : frontier) {
        if (window.publicState.cell.depth == config.coverage.leafDepth
            || window.publicState.startMs >= endpoint || observed.count(window.publicState.startMs)) continue;
        const auto found = history.queryFinest(window.publicState.startMs, endpoint);
        if (!found.candidate) throw std::runtime_error("Cell-local refinement history is unavailable");
        std::vector<CellGeometry> occupied;
        for (const auto& item : found.candidate->cells) occupied.push_back(item.cell);
        observed.emplace(window.publicState.startMs, std::move(occupied));
    }
    if (observed.empty()) return;
    auto after = frontier;
    for (const auto& [start, cells] : observed)
        for (const auto& cell : cells) {
            auto owner = after.end();
            for (auto it = after.begin(); it != after.end(); ++it)
                if (it->second.publicState.startMs == start
                    && containsCell(it->second.publicState.cell, cell)) { owner = it; break; }
            if (owner != after.end()) refineToDomain(after, cell);
        }
    frontier.swap(after);
}

bool CellLocalAggregation::canMerge(const Frontier& cut, const CellGeometry& domain,
    AggregationTime end, AggregationTime& start) const {
    bool found = false;
    std::uint64_t covered = 0;
    const auto units = std::uint64_t{1} << (2 * (config.coverage.leafDepth - domain.depth));
    for (const auto& [id, window] : cut) {
        const auto& cell = window.publicState.cell;
        if (containsCell(cell, domain) && cell.depth < domain.depth) return false;
        if (!containsCell(domain, cell)) continue;
        if (!found) { start = window.publicState.startMs; found = true; }
        if (window.publicState.startMs != start || end <= start) return false;
        covered += std::uint64_t{1} << (2 * (config.coverage.leafDepth - cell.depth));
    }
    return found && covered == units;
}

SpatialSelection CellLocalAggregation::selectionFor(const Window& source,
    AggregationCandidate candidate, WindowMetricAssessment assessment,
    const AggregationHistory& history, bool selected, const std::string& reason, bool final) const {
    const auto scope = candidate.cells.at(0).cell;
    auto finest = candidate;
    finest.cells.clear();
    const auto raw = history.queryFinest(candidate.startMs, candidate.endMs, scope);
    if (!raw.candidate) throw std::runtime_error("Cell-local diagnostic fine history is unavailable");
    for (const auto& item : raw.candidate->cells)
        if (containsCell(scope, item.cell)) finest.cells.push_back(item);
    finest.truncated = final;
    if (finest.cells.size() > spatial.maxEvaluations)
        throw std::length_error("Cell-local diagnostic spatial evaluation budget exceeded");
    const auto fineAssessment = evaluator.evaluate(finest, candidate.closedAtMs);
    SpatialSelection result{candidate, assessment, finest, fineAssessment, {}, {}, spatial.minDepth};
    result.coordinationCell = scope;
    result.strategy = adaptationStrategyName(temporal.strategy);
    result.temporalExtensions = source.publicState.extensions;
    result.completionReason = reason;
    result.temporalDecisions = source.decisions;
    result.temporalDecisions.push_back({TemporalAction::Finalize, candidate.startMs, candidate.endMs,
        candidate.closedAtMs, assessment.status});
    // An empty private retirement is explicit in its scope, without a public zero
    // cell or a misleading suppressed-support counter.
    if (!candidate.counts.observationContributions) {
        result.candidate.cells.clear();
        result.assessment = evaluator.evaluate(result.candidate, candidate.closedAtMs);
        return result;
    }
    std::string transition = selected ? "initial" : "suppressed";
    if (selected && source.previousSelected) {
        const auto& previous = *source.previousSelected;
        transition = previous.id == scope.id ? "unchanged"
            : containsCell(previous, scope) ? "refined"
            : containsCell(scope, previous) ? "coarsened" : "new_support";
    }
    result.decisions.push_back({scope.id, selected, reason, {}, transition});
    result.attempts.push_back({candidate.cells.front(), assessment.cells.front()});
    result.selectedCells = selected ? 1 : 0;
    result.suppressedCells = selected ? 0 : 1;
    result.coarsenedCells = transition == "coarsened";
    result.refinedCells = transition == "refined";
    return result;
}

bool CellLocalAggregation::tryMerge(const CellGeometry& domain, AggregationTime end,
    const AggregationHistory& history, bool final) {
    if (domain.depth < spatial.minDepth) return false;
    // A future handoff reserves its complete domain. No old-prefix promotion
    // inside, across or above it may bypass the agreed boundary.
    for (const auto& [id, request] : handoffs)
        if (containsCell(domain, request.first) || containsCell(request.first, domain)) return false;
    Frontier refined;
    const Frontier* cut = &frontier;
    std::optional<CellGeometry> enclosing;
    for (const auto& [id, window] : frontier)
        if (window.publicState.cell.depth < domain.depth && containsCell(window.publicState.cell, domain)) {
            enclosing = window.publicState.cell;
            break;
        }
    if (enclosing) {
        refined = frontier;
        refineToDomain(refined, domain);
        cut = &refined;
    }
    AggregationTime start = 0;
    if (!canMerge(*cut, domain, end, start) || end - start > temporal.maxWindowMs) return false;
    auto candidate = query(domain, start, end, history, final);
    auto checked = evaluator.evaluate(candidate, candidate.closedAtMs);
    if (!candidate.counts.observationContributions || !passed(candidate, checked)) return false;
    Window source = makeWindow(domain, start);
    for (const auto& [id, window] : *cut)
        if (containsCell(domain, window.publicState.cell)) {
            source.publicState.extensions = std::max(source.publicState.extensions, window.publicState.extensions);
            source.publicState.evaluations = std::max(source.publicState.evaluations, window.publicState.evaluations);
            if (!source.previousSelected && window.previousSelected) source.previousSelected = window.previousSelected;
            if (window.decisions.size() > source.decisions.size()) source.decisions = window.decisions;
        }
    source.decisions.push_back({TemporalAction::CoarsenSpatially, start, end,
        candidate.closedAtMs, checked.status});
    auto selected = selectionFor(source, candidate, checked, history, true,
        final ? "end_of_stream" : "sibling_failure_parent_passed", final);
    Frontier replacements;
    std::vector<int> retired;
    if (enclosing) {
        retired.push_back(enclosing->id);
        for (const auto& [id, window] : *cut)
            if (containsCell(*enclosing, window.publicState.cell)
                && !containsCell(domain, window.publicState.cell)) replacements.emplace(id, window);
    } else {
        for (const auto& [id, window] : frontier)
            if (containsCell(domain, window.publicState.cell)) retired.push_back(id);
    }
    replacements.emplace(domain.id, makeWindow(domain, end, domain));
    emit(std::move(selected), std::move(replacements), std::move(retired));
    return true;
}

bool CellLocalAggregation::requestMerge(const CellGeometry& domain, AggregationTime end,
    const AggregationHistory& history) {
    const auto now = history.debugState().watermarkMs;
    validateTime(now, history);
    validateDomain(domain);
    if (end <= 0 || end > now || end % config.samplingPeriodMs)
        throw std::invalid_argument("Explicit parent takeover needs a closed sampling-aligned interval");
    if (pending) {
        const bool matching = pending->selection.coordinationCell
            && pending->selection.coordinationCell->id == domain.id
            && pending->selection.candidate.endMs == end;
        if (!matching)
            throw std::logic_error("A different immutable cell-local output is already reserved");
        retryPending(now);
        lastNowMs = now;
        return true;
    }
    const bool accepted = tryMerge(domain, end, history, false);
    if (accepted) lastNowMs = now;
    return accepted;
}

bool CellLocalAggregation::scheduleMerge(const CellGeometry& domain) {
    if (finished || emitting || pending)
        throw std::logic_error("Cannot schedule a handoff while finished, delivering, or reserved");
    validateDomain(domain);
    if (domain.depth < spatial.minDepth) return false;
    for (const auto& [id, request] : handoffs)
        if (containsCell(domain, request.first) || containsCell(request.first, domain)) return false;
    auto after = frontier;
    refineToDomain(after, domain);
    AggregationTime boundary = lastNowMs;
    for (const auto& [id, window] : after)
        if (containsCell(domain, window.publicState.cell))
            boundary = std::max(boundary, window.publicState.nextEndMs);
    if (boundary <= lastNowMs) return false;
    for (auto& [id, window] : after)
        if (containsCell(domain, window.publicState.cell))
            window.decisions.push_back({TemporalAction::RequestHandoff, window.publicState.startMs,
                boundary, lastNowMs, AssessmentStatus::NotConfigured});
    auto nextRequests = handoffs;
    nextRequests.emplace(domain.id, std::make_pair(domain, boundary));
    frontier.swap(after);
    handoffs.swap(nextRequests);
    return true;
}

std::optional<AggregationTime> CellLocalAggregation::handoffBoundary(const CellGeometry& cell) const {
    for (const auto& [id, request] : handoffs)
        if (containsCell(request.first, cell)) return request.second;
    return std::nullopt;
}

void CellLocalAggregation::applyHandoffs() {
    for (auto request = handoffs.begin(); request != handoffs.end();) {
        const auto domain = request->second.first;
        const auto time = request->second.second;
        AggregationTime start = 0;
        const bool allReady = canMerge(frontier, domain, time + 1, start) && start == time;
        if (!allReady) { ++request; continue; }
        auto after = frontier;
        for (auto it = after.begin(); it != after.end();)
            if (containsCell(domain, it->second.publicState.cell)) it = after.erase(it); else ++it;
        after.emplace(domain.id, makeWindow(domain, time));
        frontier.swap(after);
        request = handoffs.erase(request);
    }
}

void CellLocalAggregation::compactFreshOwners(AggregationTime boundary, const AggregationHistory& history) {
    // Ownership geometry is private state, independent of the last released cut.
    // Untouched successors with equal clocks can coalesce directly. Out-of-phase
    // idle successors first retire their proven-empty prefixes explicitly, then
    // acquire one common clock. No selected contribution is moved or discarded.
    const auto evaluatedAt = history.debugState().watermarkMs;
    for (;;) {
        std::map<int, std::vector<int>> siblings;
        for (const auto& [id, window] : frontier) {
            const auto& w = window.publicState;
            if (w.cell.depth > 1 && !w.extensions && !w.evaluations && !window.lastCheck)
                siblings[id >> 2].push_back(id);
        }
        bool changed = false;
        for (const auto& [parentId, children] : siblings) {
            if (children.size() != 4) continue;
            const auto first = frontier.find(children.front());
            if (first == frontier.end()) continue;
            const auto reference = first->second.publicState;
            const auto parent = historyCell(config.coverage, parentId, reference.cell.depth - 1);
            bool eligible = true, sameClock = true;
            for (const auto& [id, request] : handoffs)
                if (containsCell(parent, request.first) || containsCell(request.first, parent)) {
                    eligible = false;
                    break;
                }
            if (!eligible) continue;
            for (int id : children) {
                const auto child = frontier.find(id);
                if (child == frontier.end()) { eligible = false; break; }
                const auto& w = child->second.publicState;
                if (w.extensions || w.evaluations || child->second.lastCheck) { eligible = false; break; }
                sameClock = sameClock && w.startMs == reference.startMs
                    && w.nextEndMs == reference.nextEndMs && w.hardDeadlineMs == reference.hardDeadlineMs;
            }
            if (!eligible) continue;
            auto successor = makeWindow(parent, sameClock ? reference.startMs : boundary);
            if (sameClock) {
                if (successor.publicState.nextEndMs != reference.nextEndMs
                    || successor.publicState.hardDeadlineMs != reference.hardDeadlineMs) continue;
                if (reference.startMs < boundary) {
                    const auto evidence = query(parent, reference.startMs, boundary, history);
                    if (evidence.coverage != WindowCoverage::Complete
                        || evidence.counts.observationContributions) continue;
                } else if (reference.startMs != boundary) continue;
            } else {
                // Keep every private alignment record cadence-aligned, including
                // when finalization is draining an off-cadence final endpoint.
                if (boundary % config.samplingPeriodMs) continue;
                for (int id : children) {
                    const auto& w = frontier.at(id).publicState;
                    if (w.startMs > boundary || evaluatedAt > w.hardDeadlineMs
                        || boundary - w.startMs > temporal.maxWindowMs) { eligible = false; break; }
                    const auto aligned = makeWindow(w.cell, boundary);
                    if (aligned.publicState.nextEndMs != successor.publicState.nextEndMs
                        || aligned.publicState.hardDeadlineMs != successor.publicState.hardDeadlineMs) {
                        eligible = false;
                        break;
                    }
                    if (w.startMs < boundary) {
                        const auto evidence = query(w.cell, w.startMs, boundary, history);
                        if (evidence.coverage != WindowCoverage::Complete
                            || evidence.counts.observationContributions) { eligible = false; break; }
                    }
                }
                if (!eligible) continue;
                // Individual immutable ACKs make partial alignment resumable.
                // An interrupted attempt leaves already retired prefixes intact;
                // the next call rechecks all remaining private support from source.
                for (int id : children) {
                    const auto owner = frontier.at(id);
                    const auto& w = owner.publicState;
                    if (w.startMs == boundary) continue;
                    auto candidate = query(w.cell, w.startMs, boundary, history);
                    const auto checked = evaluator.evaluate(candidate, evaluatedAt);
                    auto selected = selectionFor(owner, candidate, checked, history, false, "idle_alignment", false);
                    Frontier replacement;
                    replacement.emplace(id, makeWindow(w.cell, boundary));
                    emit(std::move(selected), std::move(replacement), {id});
                }
            }
            // Preallocate before changing ownership. New fine observations expand
            // this private owner before metric checks; old display lineage is not
            // interpreted as an active output after idle coalescing.
            Frontier replacement;
            replacement.emplace(parentId, std::move(successor));
            for (int id : children) frontier.erase(id);
            frontier.merge(replacement);
            changed = true;
        }
        if (!changed) return;
    }
}

void CellLocalAggregation::process(AggregationTime now, const AggregationHistory& history, bool final) {
    retryPending(now);
    // A retry may have completed the last empty alignment in a prior endpoint.
    // Resume coalescing at the latest closed sampling boundary before new work.
    compactFreshOwners(now - now % config.samplingPeriodMs, history);
    // Refinement also runs after a successful coarse takeover while catching up.
    // It never changes a retired start or consumes an observation.
    refineDue(now, history);
    for (;;) {
        applyHandoffs();
        AggregationTime endpoint = std::numeric_limits<AggregationTime>::max();
        for (const auto& [id, window] : frontier)
            if (window.publicState.startMs < now)
                endpoint = std::min(endpoint, window.publicState.nextEndMs);
        if (final) endpoint = std::min(endpoint, now);
        if (endpoint > now) break;
        refineDue(endpoint, history);
        // New child-specific maxima can bring the next endpoint forward. Finish
        // that earlier interval before evaluating the former coarse endpoint.
        AggregationTime earlier = endpoint;
        for (const auto& [id, window] : frontier)
            if (window.publicState.startMs < endpoint)
                earlier = std::min(earlier, window.publicState.nextEndMs);
        if (earlier < endpoint) continue;
        const bool terminalEnd = final && endpoint == now;
        struct Check { AggregationCandidate candidate; WindowMetricAssessment assessment; bool failed; };
        std::map<int, Check> checks;
        std::vector<int> due;
        // Freeze this endpoint's private evidence before considering any output.
        // A passing small merge must not disclose support needed by a different
        // failed branch whose nearest passing rescue is a broader ancestor.
        for (const auto& [id, window] : frontier) {
            const auto& w = window.publicState;
            if (w.startMs >= endpoint) continue;
            auto candidate = query(w.cell, w.startMs, endpoint, history, terminalEnd);
            auto assessed = evaluator.evaluate(candidate, now);
            const bool failed = candidate.counts.observationContributions && !passed(candidate, assessed);
            checks.emplace(id, Check{std::move(candidate), std::move(assessed), failed});
            if (w.nextEndMs <= endpoint || terminalEnd) due.push_back(id);
        }
        if (due.empty()) break;
        // Planning must not bypass a due owner's temporal evaluation cap merely
        // because its support could be absorbed before the per-owner loop below.
        for (int id : due)
            if (frontier.at(id).publicState.evaluations >= temporal.maxEvaluations)
                throw std::length_error("Cell-local temporal evaluation budget exceeded");
        struct Parent {
            Check check;
            bool deadlinePressure;
            bool futurePossible;
        };
        // The budget counts unique reconstructable ancestor assessments per
        // endpoint, including future-hold tests. It is checked before any sink
        // call; shared paths do not repeatedly consume this planning budget.
        std::map<int, std::optional<Parent>> parents;
        std::size_t ancestorEvaluations = 0;
        const auto assessParent = [&](const CellGeometry& domain) -> const std::optional<Parent>& {
            const auto known = parents.find(domain.id);
            if (known != parents.end()) return known->second;
            for (const auto& [requestId, request] : handoffs)
                if (containsCell(domain, request.first) || containsCell(request.first, domain))
                    return parents.emplace(domain.id, std::nullopt).first->second;
            AggregationTime start = 0;
            if (!canMerge(frontier, domain, endpoint, start)
                || endpoint - start > temporal.maxWindowMs)
                return parents.emplace(domain.id, std::nullopt).first->second;
            if (++ancestorEvaluations > spatial.maxEvaluations)
                throw std::length_error("Cell-local endpoint ancestor evaluation budget exceeded");
            auto candidate = query(domain, start, endpoint, history, terminalEnd);
            auto assessed = evaluator.evaluate(candidate, now);
            bool deadlinePressure = terminalEnd;
            AggregationTime maximum = start + temporal.maxWindowMs;
            for (const auto& [ownerId, owner] : frontier)
                if (containsCell(domain, owner.publicState.cell)) {
                    maximum = std::min(maximum, owner.publicState.hardDeadlineMs);
                    deadlinePressure = deadlinePressure || endpoint >= owner.publicState.hardDeadlineMs
                        || now >= owner.publicState.hardDeadlineMs;
                }
            AggregationTime minimum = endpoint + config.samplingPeriodMs;
            bool futurePossible = candidate.coverage == WindowCoverage::Complete
                && assessed.cells.at(0).policyFeasible
                && assessed.cells.at(0).status != AssessmentStatus::NotConfigured;
            for (const auto& check : assessed.cells.at(0).checks) {
                const auto& requirement = check.requirement;
                if (check.status == AssessmentStatus::Unavailable) futurePossible = false;
                switch (requirement.id) {
                    case MetricId::CellSideM:
                    case MetricId::CellAreaM2:
                        if (check.status != AssessmentStatus::Pass) futurePossible = false;
                        break;
                    case MetricId::DistinctContributors:
                    case MetricId::ObservationContributions:
                        // These totals cannot shrink when extending this same
                        // interval; a violated upper bound cannot be repaired.
                        if (requirement.max && check.observed && *check.observed > *requirement.max)
                            futurePossible = false;
                        break;
                    case MetricId::WindowDurationMs:
                    case MetricId::AgeAtEvaluationMs:
                        if (requirement.min && *requirement.min <= temporal.maxWindowMs)
                            minimum = std::max(minimum, start + static_cast<AggregationTime>(*requirement.min));
                        else if (requirement.min && *requirement.min > temporal.maxWindowMs)
                            futurePossible = false;
                        if (requirement.max && *requirement.max < static_cast<double>(maximum - start))
                            maximum = start + static_cast<AggregationTime>(*requirement.max);
                        break;
                    case MetricId::PostWindowDelayMs:
                        // A timely next endpoint has zero post-window delay.
                        // A positive minimum needs a different delayed-release
                        // model and cannot justify this window-extension hold.
                        if (requirement.min && *requirement.min > 0) futurePossible = false;
                        break;
                    case MetricId::MeanSampleOccupancy:
                    case MetricId::MeasuredSampleFraction:
                        // These ratios are not monotone. They may change, but
                        // no future passing assessment is assumed or fabricated.
                        break;
                    case MetricId::OccupancyMae:
                    case MetricId::Count:
                        futurePossible = false;
                        break;
                }
            }
            if (minimum % config.samplingPeriodMs)
                minimum += config.samplingPeriodMs - minimum % config.samplingPeriodMs;
            maximum -= maximum % config.samplingPeriodMs;
            futurePossible = futurePossible && minimum <= maximum && now < maximum;
            const bool failed = !passed(candidate, assessed);
            return parents.emplace(domain.id, Parent{Check{std::move(candidate), std::move(assessed), failed},
                deadlinePressure, futurePossible}).first->second;
        };
        std::set<int> proposals;
        std::set<int> holdDomains;
        for (const auto& [id, check] : checks) {
            if (!check.failed) continue;
            const auto& w = frontier.at(id).publicState;
            bool foundNearest = false;
            for (int depth = w.cell.depth - 1; depth >= spatial.minDepth; --depth) {
                const auto domain = historyAncestor(config.coverage, w.cell, w.cell.depth - depth);
                const auto& parent = assessParent(domain);
                if (!parent) continue;
                if (parent->futurePossible) holdDomains.insert(domain.id);
                const bool mayCoarsen = temporal.strategy == AdaptationStrategy::TemporalFirst
                    || parent->deadlinePressure;
                if (!foundNearest && mayCoarsen && !parent->check.failed) {
                    proposals.insert(domain.id);
                    foundNearest = true;
                }
            }
        }
        // Every proposed domain is the finest passing rescue for at least one
        // failed owner. When those proposals nest, retain the broader one before
        // disclosure. Disjoint fine rescues remain fine; a coarser passing cell
        // alone is never a reason to replace them.
        std::vector<CellGeometry> planned;
        for (int id : proposals) {
            const auto& domain = parents.at(id)->check.candidate.cells.at(0).cell;
            bool enclosed = false;
            for (int otherId : proposals)
                if (id != otherId && containsCell(parents.at(otherId)->check.candidate.cells.at(0).cell, domain)) {
                    enclosed = true;
                    break;
                }
            if (!enclosed) planned.push_back(domain);
        }
        for (const auto& domain : planned)
            if (!tryMerge(domain, endpoint, history, terminalEnd))
                throw std::logic_error("A prevalidated cell-local endpoint merge lost its private ownership");
        std::stable_sort(due.begin(), due.end(), [&](int left, int right) {
            return checks.at(left).failed > checks.at(right).failed;
        });
        for (int id : due) {
            const auto live = frontier.find(id);
            if (live == frontier.end() || live->second.publicState.startMs != checks.at(id).candidate.startMs)
                continue; // A parent already consumed this exact private footprint.
            auto current = live->second;
            auto& state = current.publicState;
            if (++state.evaluations > temporal.maxEvaluations)
                throw std::length_error("Cell-local temporal evaluation budget exceeded");
            auto candidate = checks.at(id).candidate;
            auto checked = checks.at(id).assessment;
            current.decisions.push_back({TemporalAction::EvaluateFinest, state.startMs, endpoint, now, checked.status});
            const bool complete = candidate.coverage == WindowCoverage::Complete;
            const bool empty = candidate.counts.observationContributions == 0;
            const bool eligible = !empty && passed(candidate, checked);
            auto boundary = handoffBoundary(state.cell);
            const bool atHandoff = boundary && endpoint >= *boundary;
            const bool atLimit = endpoint >= state.hardDeadlineMs || now >= state.hardDeadlineMs;
            const bool terminal = terminalEnd || atLimit || atHandoff || (!complete && candidate.expectedSamples);
            std::size_t proposals = 0;
            // A published sibling can close an old parent option. Resolve the old
            // failed prefix, then explicitly align future windows rather than
            // waiting indefinitely or reusing the previously public support.
            if (!empty && !eligible && terminal && !terminalEnd && !boundary) {
                for (int depth = state.cell.depth - 1; depth >= spatial.minDepth; --depth) {
                    if (++proposals > spatial.maxEvaluations)
                        throw std::length_error("Cell-local spatial proposal budget exceeded");
                    const auto parent = historyAncestor(config.coverage, state.cell, state.cell.depth - depth);
                    AggregationTime commonStart = 0;
                    if (canMerge(frontier, parent, endpoint, commonStart)) continue;
                    const auto hypothetical = query(parent, state.startMs, endpoint, history);
                    const auto assessed = evaluator.evaluate(hypothetical, now);
                    bool feasible = assessed.cells.at(0).policyFeasible;
                    AggregationTime minimum = config.samplingPeriodMs, maximum = temporal.maxWindowMs;
                    for (const auto& check : assessed.cells.at(0).checks) {
                        if ((check.requirement.id == MetricId::CellSideM
                                || check.requirement.id == MetricId::CellAreaM2)
                            && check.status != AssessmentStatus::Pass) feasible = false;
                        if (check.requirement.id == MetricId::WindowDurationMs && check.requirement.min)
                            minimum = std::max(minimum, static_cast<AggregationTime>(*check.requirement.min));
                        if ((check.requirement.id == MetricId::WindowDurationMs
                                || check.requirement.id == MetricId::AgeAtEvaluationMs) && check.requirement.max)
                            maximum = std::min(maximum, static_cast<AggregationTime>(*check.requirement.max));
                    }
                    if (minimum % config.samplingPeriodMs)
                        minimum += config.samplingPeriodMs - minimum % config.samplingPeriodMs;
                    maximum -= maximum % config.samplingPeriodMs;
                    if (feasible && minimum <= maximum && scheduleMerge(parent)) {
                        boundary = handoffBoundary(state.cell);
                        current.decisions.push_back({TemporalAction::RequestHandoff, state.startMs,
                            *boundary, now, assessed.status});
                        break;
                    }
                }
            }
            bool hold = false;
            if (!terminal && (eligible || empty))
                for (int parentId : holdDomains) {
                    const auto& parent = *parents.at(parentId);
                    const auto& domain = parent.check.candidate.cells.at(0).cell;
                    if (parent.check.candidate.startMs != state.startMs || !containsCell(domain, state.cell)) continue;
                    AggregationTime commonStart = 0;
                    // A disjoint accepted merge elsewhere may have retired part
                    // of this prospective domain. Never hold for a closed option.
                    if (canMerge(frontier, domain, endpoint, commonStart) && commonStart == state.startMs) {
                        hold = true;
                        break;
                    }
                }
            if (!terminal && ((!eligible && !empty) || hold)) {
                state.nextEndMs = std::min(endpoint + temporal.extensionStepMs, state.hardDeadlineMs);
                if (boundary) state.nextEndMs = std::min(state.nextEndMs, *boundary);
                if (state.nextEndMs <= endpoint) throw std::logic_error("Cell-local temporal extension cannot progress");
                ++state.extensions;
                current.decisions.push_back({hold ? TemporalAction::CoordinationHold : TemporalAction::ExtendWindow,
                    state.startMs, state.nextEndMs, now, checked.status});
                current.lastCheck = std::make_shared<const AggregationProgressCheck>(
                    AggregationProgressCheck{candidate, checked});
                frontier.at(id) = std::move(current);
                continue;
            }
            const std::string reason = terminalEnd ? "end_of_stream"
                : atHandoff ? "coordination_handoff"
                : empty ? complete ? "measured_empty" : candidate.expectedSamples ? "coverage_unavailable" : "no_scheduled_samples"
                : eligible ? "requirements_met"
                : !complete ? "coverage_unavailable" : atLimit ? "policy_or_window_deadline" : "requirements_failed";
            auto selected = selectionFor(current, candidate, checked, history, eligible, reason, terminalEnd);
            Frontier replacements;
            auto next = makeWindow(state.cell, endpoint, eligible ? std::optional<CellGeometry>{state.cell} : current.previousSelected);
            if (boundary && endpoint < *boundary)
                next.publicState.nextEndMs = std::min(next.publicState.nextEndMs, *boundary);
            replacements.emplace(id, std::move(next));
            emit(std::move(selected), std::move(replacements), {id});
        }
        // Resolve the complete endpoint batch before coalescing: no due sibling
        // can disappear behind a newly compressed owner while awaiting its ACK.
        compactFreshOwners(endpoint, history);
    }
}

void CellLocalAggregation::advance(AggregationTime now, const AggregationHistory& history) {
    validateTime(now, history);
    process(now, history, false);
    lastNowMs = now;
}

void CellLocalAggregation::finish(AggregationTime end, const AggregationHistory& history) {
    validateTime(end, history);
    process(end, history, true);
    for (const auto& [id, window] : frontier)
        if (window.publicState.startMs != end)
            throw std::logic_error("Cell-local finalization left an unresolved spatial prefix");
    handoffs.clear();
    lastNowMs = end;
    finished = true;
}

std::vector<CellLocalWindow> CellLocalAggregation::windows() const {
    std::vector<CellLocalWindow> result;
    result.reserve(frontier.size());
    for (const auto& [id, window] : frontier) result.push_back(window.publicState);
    return result;
}

AdaptiveAggregationDebugState CellLocalAggregation::debugState() const {
    AggregationTime start = std::numeric_limits<AggregationTime>::max();
    AggregationTime next = std::numeric_limits<AggregationTime>::max();
    AggregationTime deadline = std::numeric_limits<AggregationTime>::max();
    std::size_t extensions = 0, evaluations = 0, decisions = 0;
    for (const auto& [id, window] : frontier) {
        start = std::min(start, window.publicState.startMs);
        next = std::min(next, window.publicState.nextEndMs);
        deadline = std::min(deadline, window.publicState.hardDeadlineMs);
        extensions += window.publicState.extensions;
        evaluations += window.publicState.evaluations;
        decisions += window.decisions.size();
    }
    return {start, next, deadline, extensions, evaluations, decisions, completedWindows, finished};
}

AggregationProgress CellLocalAggregation::progressSnapshot() const {
    const auto state = debugState();
    AggregationProgress result{adaptationStrategyName(temporal.strategy), state.windowStartMs,
        state.nextEndMs, state.hardDeadlineMs, lastNowMs, state.temporalExtensions,
        state.temporalEvaluations, finished ? AggregationProgressPhase::Finished
            : state.temporalExtensions ? AggregationProgressPhase::Extending : AggregationProgressPhase::Collecting, {}, true, {}};
    result.cells.reserve(frontier.size());
    for (const auto& [id, window] : frontier) {
        const auto& w = window.publicState;
        result.cells.push_back({w.cell, w.startMs, w.nextEndMs, w.hardDeadlineMs,
            w.extensions, w.evaluations, finished ? nullptr : window.lastCheck});
    }
    return result;
}

} // namespace ump
