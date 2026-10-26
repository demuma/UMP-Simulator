#include "MappedSceneConfiguration.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>

namespace {
using Clock = std::chrono::steady_clock;
using Time = ump::AggregationTime;

struct Options {
    std::string path;
    Time endMs = 0, reportEveryMs = 10000;
    std::uint64_t wallBudgetSeconds = 0;
};

std::uint64_t positiveInteger(const std::string& value, const std::string& name) {
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument(name + " requires a positive decimal integer");
    std::size_t consumed = 0;
    const auto result = std::stoull(value, &consumed);
    if (!result || consumed != value.size())
        throw std::invalid_argument(name + " requires a positive decimal integer");
    return result;
}

Options options(int argc, char** argv) {
    if (argc < 2 || std::string(argv[1]).empty() || std::string(argv[1]).front() == '-')
        throw std::invalid_argument("Usage: MappedMotionProbe <config.yaml> --end-ms N --wall-budget-s S [--report-every-ms N]");
    Options result;
    result.path = argv[1];
    std::set<std::string> seen;
    for (int i = 2; i < argc; i += 2) {
        const std::string key = argv[i];
        if ((key != "--end-ms" && key != "--wall-budget-s" && key != "--report-every-ms")
            || !seen.insert(key).second || i + 1 >= argc)
            throw std::invalid_argument("Unknown, duplicate or incomplete probe option: " + key);
        const auto value = positiveInteger(argv[i + 1], key);
        if (key == "--wall-budget-s") result.wallBudgetSeconds = value;
        else {
            if (value > static_cast<std::uint64_t>(std::numeric_limits<Time>::max()))
                throw std::invalid_argument(key + " exceeds the simulation time range");
            if (key == "--end-ms") result.endMs = static_cast<Time>(value);
            else result.reportEveryMs = static_cast<Time>(value);
        }
    }
    if (!result.endMs || !result.wallBudgetSeconds)
        throw std::invalid_argument("Both --end-ms and --wall-budget-s are required");
    return result;
}

double milliseconds(Clock::duration value) {
    return std::chrono::duration<double, std::milli>(value).count();
}

struct Timing {
    std::vector<double> samples;
    double sumMs = 0, maxMs = 0;
    std::size_t over50Ms = 0;
    void add(double sample) {
        samples.push_back(sample);
        sumMs += sample;
        maxMs = std::max(maxMs, sample);
        if (sample > 50.0) ++over50Ms;
    }
};

// Nearest-rank quantiles of cumulative fixed-step advance timings. Empty
// samples occur when setup alone exhausts the wall budget and report as zero.
double quantile(const std::vector<double>& sorted, double fraction) {
    if (sorted.empty()) return 0;
    const auto rank = static_cast<std::size_t>(std::ceil(fraction * sorted.size()));
    return sorted[std::max<std::size_t>(rank, 1) - 1];
}

void report(const char* state, bool final, Time atMs, std::size_t expected,
    const ump::MappedMotionDiagnostics& d, std::size_t peakActive, Time lastEndMs,
    const Timing& timing, double setupMs, double constructorMs, Clock::time_point start) {
    auto sorted = timing.samples;
    std::sort(sorted.begin(), sorted.end());
    const double totalMs = milliseconds(Clock::now() - start);
    std::cout << std::setprecision(12)
        << "{\"kind\":\"" << (final ? "final" : "progress") << "\",\"state\":\"" << state
        << "\",\"simulated_ms\":" << atMs << ",\"expected_episodes\":" << expected
        << ",\"starts\":" << d.realizedStarts << ",\"ends\":" << d.realizedEnds
        << ",\"active\":" << d.activeTracks << ",\"pending\":" << d.pendingTracks
        << ",\"stalled\":" << d.activeStalledTracks << ",\"overlaps\":" << d.overlapViolations
        << ",\"replans\":" << d.navigationReplans << ",\"replan_failures\":" << d.navigationReplanFailures
        << ",\"candidate_checks\":" << d.navigationCandidateChecks
        << ",\"start_connector_checks\":" << d.navigationStartConnectorChecks
        << ",\"expanded_start_searches\":" << d.navigationExpandedStartSearches
        << ",\"max_start_connector_checks\":" << d.navigationMaxStartConnectorChecks
        << ",\"passage_wait_steps\":" << d.passageWaitSteps << ",\"passage_batches\":" << d.passageBatches
        << ",\"passage_cleared_tracks\":" << d.passageClearedTracks
        << ",\"max_passage_wait_ms\":" << d.maxPassageWaitMs << ",\"max_stop_ms\":" << d.maxConsecutiveStopMs
        << ",\"crossing_pedestrian_wait_steps\":" << d.crossingPedestrianWaitSteps
        << ",\"crossing_rider_wait_steps\":" << d.crossingRiderWaitSteps
        << ",\"crossing_batches\":" << d.crossingBatches
        << ",\"crossing_fairness_closures\":" << d.crossingFairnessClosures
        << ",\"max_crossing_pedestrian_wait_ms\":" << d.maxCrossingPedestrianWaitMs
        << ",\"peak_active\":" << peakActive << ",\"last_end_ms\":" << lastEndMs
        << ",\"steps\":" << timing.samples.size() << ",\"steps_over_50_ms\":" << timing.over50Ms
        << ",\"step_wall_ms_mean\":" << (timing.samples.empty() ? 0 : timing.sumMs / timing.samples.size())
        << ",\"step_wall_ms_p50\":" << quantile(sorted, .50) << ",\"step_wall_ms_p95\":" << quantile(sorted, .95)
        << ",\"step_wall_ms_p99\":" << quantile(sorted, .99) << ",\"step_wall_ms_max\":" << timing.maxMs
        << ",\"advance_wall_ms\":" << timing.sumMs << ",\"setup_wall_ms\":" << setupMs
        << ",\"constructor_wall_ms\":" << constructorMs << ",\"total_wall_ms\":" << totalMs << "}\n";
    std::cout.flush();
}
} // namespace

int main(int argc, char** argv) {
    bool running = false;
    try {
        const auto args = options(argc, argv);
        const auto start = Clock::now();
        const auto yaml = YAML::LoadFile(args.path);
        const auto taxonomy = yaml["agents"]["road_user_taxonomy"];
        if (!taxonomy || !taxonomy.IsSequence())
            throw std::invalid_argument("Probe configuration requires agents.road_user_taxonomy");
        std::unordered_set<std::string> profiles;
        for (const auto& row : taxonomy) profiles.insert(row["type"].as<std::string>());
        const auto config = readMappedSceneConfiguration(yaml["mapped_scene"],
            yaml["simulation"]["width"].as<double>(), yaml["simulation"]["height"].as<double>(), profiles);
        if (config.motionMode == ump::MappedMotionMode::Integration)
            throw std::invalid_argument("Probe requires fixed-step corridor_following or local_navigation motion");
        if (args.endMs % config.motionStepMs || args.reportEveryMs % config.motionStepMs)
            throw std::invalid_argument("Horizon and report interval must be multiples of the native motion step");
        const auto constructorStart = Clock::now();
        ump::MappedScene scene(config);
        const auto constructorMs = milliseconds(Clock::now() - constructorStart);
        const auto setupMs = milliseconds(Clock::now() - start);
        std::size_t expected = 0;
        for (const auto& person : config.people) expected += person.episodes.size();
        Time atMs = 0, lastEndMs = 0;
        auto diagnostics = scene.motionDiagnostics();
        std::size_t peakActive = diagnostics.activeTracks, consumedEvents = 0;
        Timing timing;
        running = true;
        const auto complete = [&] {
            return diagnostics.realizedStarts == expected && diagnostics.realizedEnds == expected
                && diagnostics.activeTracks == 0 && diagnostics.pendingTracks == 0;
        };
        while (atMs < args.endMs && !complete()) {
            // The budget includes YAML validation, both constructor calls and
            // reporting overhead; only advanceTo is included in step timings.
            if (milliseconds(Clock::now() - start) >= 1000.0 * args.wallBudgetSeconds) {
                report("wall_budget", true, atMs, expected, diagnostics, peakActive, lastEndMs,
                    timing, setupMs, constructorMs, start);
                return 2;
            }
            atMs += config.motionStepMs;
            const auto stepStart = Clock::now();
            scene.advanceTo(atMs);
            timing.add(milliseconds(Clock::now() - stepStart));
            diagnostics = scene.motionDiagnostics();
            peakActive = std::max(peakActive, diagnostics.activeTracks);
            const auto& events = scene.events();
            for (; consumedEvents < events.size(); ++consumedEvents)
                if (events[consumedEvents].kind == ump::MappedEventKind::EpisodeEnd)
                    lastEndMs = std::max(lastEndMs, events[consumedEvents].atMs);
            if (atMs % args.reportEveryMs == 0 && atMs < args.endMs && !complete())
                report("progress", false, atMs, expected, diagnostics, peakActive, lastEndMs,
                    timing, setupMs, constructorMs, start);
        }
        // A final advance may finish the cohort or reach the horizon while
        // crossing the budget. Keep the wall-time gate authoritative even
        // though an individual deterministic motion update is not interruptible.
        if (milliseconds(Clock::now() - start) >= 1000.0 * args.wallBudgetSeconds) {
            report("wall_budget", true, atMs, expected, diagnostics, peakActive, lastEndMs,
                timing, setupMs, constructorMs, start);
            return 2;
        }
        const bool finished = complete();
        report(finished ? "complete" : "horizon_incomplete", true, atMs, expected, diagnostics,
            peakActive, lastEndMs, timing, setupMs, constructorMs, start);
        return finished ? 0 : 3;
    } catch (const std::exception& error) {
        std::cerr << "MappedMotionProbe: " << error.what() << '\n';
        return running ? 1 : 64;
    }
}
