#include "PublicationCoordinator.hpp"
#include <algorithm>
#include <cmath>
#include <set>
#include <stdexcept>

namespace ump {
namespace {
std::string keyPart(const std::string& value) {
    return std::to_string(value.size()) + ":" + value;
}
}
PublicationCoordinator::PublicationCoordinator(AggregationConfig settings, MetricEvaluator metrics,
    PublicationLimits bounds, std::optional<AggregationTime> maximum, bool scoped)
    : config(std::move(settings)), evaluator(std::move(metrics)), limits(bounds), maximumWindowMs(maximum), cellLocal(scoped) {
    historyCell(config.coverage, 12, 1);
    if (config.runId.empty() || config.sensorId.empty() || config.applicationId.empty()
        || config.windowMs <= 0 || !limits.maxCells || !limits.maxTypeEntries || !limits.maxTypeBytes)
        throw std::invalid_argument("Publication requires a stream, window and positive limits");
    if (cellLocal) retiredLedger.emplace(config.coverage, limits.maxCoordinationNodes);
    if (maximumWindowMs && (config.samplingPeriodMs <= 0 || *maximumWindowMs < config.windowMs
            || *maximumWindowMs % config.samplingPeriodMs))
        throw std::invalid_argument("Variable publication intervals need an aligned maximum at least the base window");
}

std::shared_ptr<const ReleaseSnapshot> PublicationCoordinator::seal(
    const SpatialSelection& selection, AggregationTime nowMs) {
    if (finished) throw std::logic_error("Publication stream ended with a truncated final window");
    if (pending || delivering) throw std::logic_error("Publication support is already reserved");
    if (nowMs < lastDeliveryMs) throw std::invalid_argument("Publication time must be monotonic");
    const auto& candidate = selection.candidate;
    const auto& g = candidate.grid;
    const auto& expected = config.coverage;
    if (candidate.runId != config.runId || candidate.sensorId != config.sensorId
        || candidate.applicationId != config.applicationId || g.x != expected.x || g.y != expected.y
        || g.width != expected.width || g.height != expected.height || g.leafDepth != expected.leafDepth
        || candidate.startMs < 0 || candidate.endMs <= candidate.startMs
        || candidate.endMs - candidate.startMs > maximumWindowMs.value_or(config.windowMs))
        throw std::invalid_argument("Publication requires the next disjoint bounded interval of one stream");
    if (cellLocal != selection.coordinationCell.has_value())
        throw std::invalid_argument("Publication coordination scope does not match stream mode");
    std::optional<CellWindowLedger> ledgerAfterAck;
    if (cellLocal) {
        // Preflight the final retirement before any possible disclosure. ACK only swaps
        // this prepared ledger, so a memory/budget failure cannot follow publication.
        ledgerAfterAck = *retiredLedger;
        ledgerAfterAck->retire(*selection.coordinationCell, candidate.startMs, candidate.endMs);
    } else if (candidate.startMs != retiredThroughMs) {
        throw std::invalid_argument("Publication requires the next whole-grid interval");
    }
    if ((!candidate.truncated && (maximumWindowMs
            ? (candidate.endMs - candidate.startMs) % config.samplingPeriodMs != 0
            : candidate.endMs - candidate.startMs != config.windowMs))
        || candidate.cells.size() != selection.decisions.size())
        throw std::invalid_argument("Publication window/decision shape is inconsistent");
    if (candidate.cells.size() > limits.maxCells)
        throw std::length_error("Publication cell limit exceeded");

    std::set<int> ids;
    std::size_t entries = 0, bytes = 0;
    const auto account = [&](const AggregateCounts& counts) {
        if (counts.typeObservationContributions.size() > limits.maxTypeEntries - entries)
            throw std::length_error("Publication type-entry limit exceeded");
        entries += counts.typeObservationContributions.size();
        for (const auto& type : counts.typeObservationContributions) {
            if (type.first.size() > limits.maxTypeBytes - bytes)
                throw std::length_error("Publication type-byte limit exceeded");
            bytes += type.first.size();
        }
    };
    account(candidate.counts);
    for (std::size_t i = 0; i < candidate.cells.size(); ++i) {
        const auto& item = candidate.cells[i];
        const auto& cell = item.cell;
        const auto canonical = historyCell(g, cell.id, cell.depth);
        if (selection.coordinationCell) {
            const auto& scope = *selection.coordinationCell;
            if (cell.depth < scope.depth || (cell.id >> (2 * (cell.depth - scope.depth))) != scope.id)
                throw std::invalid_argument("Publication cell lies outside its coordination footprint");
        }
        const auto close = [&](double a, double b) {
            const auto tolerance = std::min(std::ldexp(g.width, -g.leafDepth) * 1e-4,
                1e-6 * std::max({1.0, std::abs(a), std::abs(b)}));
            return std::isfinite(a) && std::abs(a - b) <= tolerance;
        };
        if (selection.decisions[i].cellId != cell.id || !ids.insert(cell.id).second
            || !close(cell.x, canonical.x) || !close(cell.y, canonical.y)
            || !close(cell.width, canonical.width) || !close(cell.height, canonical.height))
            throw std::invalid_argument("Publication cell ID, geometry or decision mismatch");
        account(item.counts);
    }
    for (const auto& item : candidate.cells) {
        int ancestor = item.cell.id;
        for (int d = item.cell.depth; d > 1; --d) {
            ancestor >>= 2;
            if (ids.count(ancestor)) throw std::invalid_argument("Publication cut overlaps parent and child");
        }
    }
    // Do not trust diagnostic pass flags or selection counters supplied by a caller.
    const auto checked = evaluator.evaluate(candidate, nowMs);
    auto output = std::make_shared<ReleaseSnapshot>();
    output->runId = candidate.runId;
    output->sensorId = candidate.sensorId;
    output->applicationId = candidate.applicationId;
    output->startMs = candidate.startMs;
    output->endMs = candidate.endMs;
    output->sealedAtMs = nowMs;
    output->policyId = checked.policyId.value_or("");
    output->policyVersion = checked.policyVersion.value_or("");
    output->coordinationCell = selection.coordinationCell;
    output->releaseId = std::string(cellLocal ? "ump-release-v2/" : "ump-release-v1/")
        + keyPart(candidate.runId) + keyPart(candidate.sensorId)
        + keyPart(candidate.applicationId) + "/" + std::to_string(candidate.startMs)
        + "/" + std::to_string(candidate.endMs);
    if (output->coordinationCell)
        output->releaseId += "/" + std::to_string(output->coordinationCell->id)
            + "/" + std::to_string(output->coordinationCell->depth);
    std::vector<std::size_t> indices;
    for (std::size_t i = 0; i < candidate.cells.size(); ++i) {
        if (!selection.decisions[i].selected) continue;
        const auto& check = checked.cells.at(i);
        if (checked.coverageStatus != AssessmentStatus::Pass || check.status != AssessmentStatus::Pass
            || !check.effectivePolicyId)
            throw std::invalid_argument("Selected cell does not meet current publication requirements");
        indices.push_back(i);
        auto publicCell = candidate.cells[i];
        // Type-level support has no separate disclosure policy in this first output model.
        publicCell.counts.typeObservationContributions.clear();
        output->cells.push_back({std::move(publicCell), *check.effectivePolicyId});
    }
    // Reserve before exposing any payload. Exceptions above leave the interval available.
    pending.emplace(Pending{candidate, std::move(indices), output,
        candidate.cells.size() - output->cells.size(), std::move(ledgerAfterAck)});
    lastDeliveryMs = nowMs;
    return output;
}

bool PublicationCoordinator::deliver(AggregationTime nowMs, const Sink& sink) {
    if (!pending || delivering) throw std::logic_error("No deliverable reservation, or reentrant delivery");
    if (!sink || nowMs < lastDeliveryMs)
        throw std::invalid_argument("Delivery requires a sink and monotonic simulation time");
    lastDeliveryMs = nowMs; // Even a rejected late attempt must not permit time travel.
    const auto checked = evaluator.evaluate(pending->candidate, nowMs);
    for (auto index : pending->selectedIndices)
        if (checked.coverageStatus != AssessmentStatus::Pass || checked.cells.at(index).status != AssessmentStatus::Pass)
            throw std::runtime_error("Publication deadline/requirements expired; reservation remains held");
    if (!pending->release->cells.empty()) {
        delivering = true;
        SinkResult result;
        try { result = sink(*pending->release); }
        catch (...) { delivering = false; throw; }
        delivering = false;
        if (result != SinkResult::Acknowledged) return false;
    }
    // Empty/suppressed windows retire privately without emitting a revealing empty record.
    if (cellLocal) {
        retiredLedger.swap(pending->retiredLedgerAfterAck);
        retiredThroughMs = retiredLedger->minimumRetiredThrough();
    } else {
        retiredThroughMs = pending->candidate.endMs;
        finished = pending->candidate.truncated;
    }
    pending.reset();
    return true;
}

std::shared_ptr<const ReleaseSnapshot> PublicationCoordinator::pendingRelease() const {
    return pending ? pending->release : nullptr;
}
PublicationState PublicationCoordinator::state() const {
    if (!pending) return {retiredThroughMs, {}, {}, 0, 0};
    return {retiredThroughMs, pending->candidate.startMs, pending->candidate.endMs,
        pending->release->cells.size(), pending->suppressedCells};
}
} // namespace ump
