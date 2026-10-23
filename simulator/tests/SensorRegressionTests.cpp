#include "MappedScene.hpp"
#include "AgentBasedSensor.hpp"
#include "GridBasedSensor.hpp"
#include "AdaptiveGridBasedSensor.hpp"
#include "AdaptiveGridDisplayState.hpp"
#include <bsoncxx/builder/stream/document.hpp>
#include <mongocxx/instance.hpp>
#include <mongocxx/uri.hpp>
#include <cmath>
#include <map>
#include <set>
#include <stdexcept>

namespace {
void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

// This fixture owns only a new UUID-named test database, never Simulation.
struct TestDatabase {
    mongocxx::database db;
    ~TestDatabase() {
        try { db.drop(); }
        catch (const std::exception& e) { std::cerr << "Test database cleanup failed: " << e.what() << '\n'; }
    }
};

using TimePoint = std::chrono::system_clock::time_point;
using Counts = std::map<int64_t, int>;

int64_t sampleTime(bsoncxx::document::view row, TimePoint origin) {
    return row["timestamp"].get_date().value.count()
        - std::chrono::duration_cast<std::chrono::milliseconds>(origin.time_since_epoch()).count();
}

void verifyGrid(mongocxx::collection collection, TimePoint origin, const Counts& expected) {
    Counts observed;
    std::set<std::pair<int64_t, std::string>> keys;
    for (auto row : collection.find({})) {
        const auto time = sampleTime(row, origin);
        std::string cell;
        if (row["cell_id"]) {
            cell = std::to_string(row["cell_id"].get_int32().value);
        } else {
            const auto index = row["cell_index"].get_document().view();
            cell = std::to_string(index["x"].get_int32().value) + ","
                 + std::to_string(index["y"].get_int32().value);
        }
        require(keys.emplace(time, cell).second, "Duplicate grid cell/timestamp");
        observed[time] += row["total_agents"].get_int32().value;
    }
    require(observed == expected, "Grid cadence or occupancy differs from expected observations");
}
// Exercise real sensors with visible-episode tracks and a private one-person
// oracle. Reuse only this fixture's UUID-owned database and separate collections.
void verifyMappedSensorLifecycle(const std::shared_ptr<mongocxx::client>& client,
    const std::string& databaseName, TestDatabase& fixture, TimePoint origin) {
    // This deliberately short hidden gap is a support counterexample, not the
    // integrated first scene's stricter one-episode-per-retained-history mode.
    const ump::MappedScene scene({20, 20,
        {{"mapped-fixture-in", {{0, 1}, {2, 1}}, "", "mapped-fixture-door"},
            {"mapped-fixture-out", {{2, 1}, {0, 1}}, "mapped-fixture-door", ""}},
        {{"private-oracle-person-not-observable", "Adult Pedestrian", 10,
            {{"opaque-first-track", "mapped-fixture-in", 0},
                {"opaque-second-track", "mapped-fixture-out", 1200}}}}});
    require(scene.episodeEndMs("opaque-first-track") == 200
        && scene.episodeEndMs("opaque-second-track") == 1400
        && scene.minimumHiddenGapMs() == 1000, "Mapped sensor fixture schedule is wrong");

    const sf::FloatRect area({0.f, 0.f}, {20.f, 20.f});
    AgentBasedSensor abs(10.f, area, databaseName, "mapped_abs", client, "mapped-abs");
    GridBasedSensor gbs(10.f, area, 5.f, databaseName, "mapped_gbs", client, "mapped-gbs");
    AdaptiveGridBasedSensor agbs(10.f, area, 10.f, 2, databaseName, "mapped_agbs", client, "mapped-agbs");
    std::vector<ump::AggregationCandidate> candidates;
    agbs.enableAggregation({"mapped-regression", agbs.sensorId, "track-support-counterexample",
        {0, 0, 20, 20, 2}, 100, 2000}, .05f, origin,
        [&](const auto& candidate) { candidates.push_back(candidate); });

    Agent::AgentTypeAttributes attributes{};
    std::set<std::string> observedTracks, privatePeople;
    std::size_t measuredFrames = 0, hiddenMeasurements = 0;
    for (int ms = 0; ms < 2000; ms += 50) {
        const auto visible = scene.frameAt(ms);
        std::vector<Agent> agents;
        for (const auto& track : visible) {
            agents.emplace_back(attributes);
            auto& agent = agents.back();
            // This is the entire observation identity bridge. Stable private
            // person identity is never assigned to Agent or supplied to sensors.
            agent.agentId = track.trackId;
            agent.type = track.type;
            agent.position = {static_cast<float>(track.position.x), static_cast<float>(track.position.y)};
            agent.velocity = {static_cast<float>(track.velocity.x), static_cast<float>(track.velocity.y)};
            agent.bodyRadius = .25f;
        }
        const auto timestamp = origin + std::chrono::milliseconds{ms};
        SensorFrameBuilder builder(timestamp);
        for (Sensor* sensor : {static_cast<Sensor*>(&abs), static_cast<Sensor*>(&gbs), static_cast<Sensor*>(&agbs)}) {
            sensor->update(agents, .05f, timestamp);
            if (auto sample = sensor->takeSample())
                builder.add(sensor->sensorId, sensor->timestamp, std::move(*sample));
            sensor->postData();
        }
        const bool due = ms > 0 && ms % 100 == 0;
        const auto frame = std::move(builder).finish();
        require(static_cast<bool>(frame) == due, "Mapped source changed fixed sensor cadence");
        if (!due) continue;
        ++measuredFrames;
        require(frame->first == timestamp && frame->second.size() == 3,
            "Mapped sensors lost their common timestamp or a measured-empty contribution");
        const auto* absSample = findSensorSample<AgentSensorSample>(frame->second, abs.sensorId);
        const auto* gbsSample = findSensorSample<GridSensorSample>(frame->second, gbs.sensorId);
        const auto* agbsSample = findSensorSample<AdaptiveGridSensorSample>(frame->second, agbs.sensorId);
        require(absSample && gbsSample && agbsSample, "Mapped sensor payload type/identity missing");
        require(absSample->detectedAgents == visible.size(), "ABS detected a hidden person or missed a visible track");
        int gridTotal = 0, adaptiveTotal = 0;
        for (const auto& cell : gbsSample->cells) gridTotal += cell.counts.totalAgents;
        for (const auto& cell : agbsSample->cells) adaptiveTotal += cell.second.totalAgents;
        require(gridTotal == static_cast<int>(visible.size())
            && adaptiveTotal == static_cast<int>(visible.size()),
            "Grid sensors observed private hidden dwell state");
        if (visible.empty()) {
            ++hiddenMeasurements;
            require(absSample->agents.empty() && gbsSample->cells.empty() && agbsSample->cells.empty(),
                "A hidden interval reused old ABS, GBS or AGBS data");
        }
        if (ms == 1200)
            require(absSample->detectedAgents == 1 && absSample->agents.empty(),
                "Fresh return track bypassed ABS velocity warm-up");
        if (ms == 1300)
            require(absSample->agents.size() == 1
                && absSample->agents.front().agentId == "opaque-second-track"
                && std::abs(absSample->agents.front().estimatedVelocity.x + 10.f) < 1e-5,
                "ABS failed to estimate return velocity from two observations of the new track");
        // Oracle use is confined to this independent test audit, after sensors
        // have processed operational Agent objects. It never changes their input.
        for (const auto& track : visible) {
            observedTracks.insert(track.trackId);
            privatePeople.insert(scene.privatePersonForTrack(track.trackId));
        }
    }
    agbs.finishAggregation(origin + std::chrono::milliseconds{2000});
    require(measuredFrames == 19 && hiddenMeasurements == 16,
        "Mapped source did not preserve scheduled empty observations");
    require(candidates.size() == 1 && candidates.front().startMs == 0
        && candidates.front().endMs == 2000 && !candidates.front().truncated
        && candidates.front().coverage == ump::WindowCoverage::Complete
        && candidates.front().measuredSamples == 19
        && candidates.front().counts.observationContributions == 3,
        "Mapped AGBS source interval/capture accounting is wrong");
    require(candidates.front().counts.distinctContributors == 2 && observedTracks.size() == 2
        && privatePeople.size() == 1,
        "AGBS must expose two-track/one-person inflation rather than silently receive GT reconnection");

    const Counts gridCounts{{100, 1}, {1200, 1}, {1300, 1}};
    verifyGrid(fixture.db["mapped_gbs"], origin, gridCounts);
    verifyGrid(fixture.db["mapped_agbs"], origin, gridCounts);
    Counts absCounts;
    std::set<std::pair<int64_t, std::string>> absKeys;
    for (auto row : fixture.db["mapped_abs"].find({})) {
        const auto ms = sampleTime(row, origin);
        const std::string track{row["agent_id"].get_string().value};
        require(track == "opaque-first-track" || track == "opaque-second-track",
            "Private person identifier crossed the ABS database boundary");
        require(!row["private_person_id"] && !row["person_id"], "ABS row exposed a private person field");
        require(absKeys.emplace(ms, track).second, "Mapped ABS duplicated a track/timestamp");
        ++absCounts[ms];
        const auto velocity = row["estimated_velocity"].get_document().view();
        require(std::abs(velocity["x"].get_double().value - (ms == 100 ? 10. : -10.)) < 1e-5
            && std::abs(velocity["y"].get_double().value) < 1e-5,
            "Mapped ABS emitted a wrong initial/return interval velocity");
    }
    require(absCounts == Counts{{100, 1}, {1300, 1}}
        && absKeys.count({1200, "opaque-second-track"}) == 0,
        "Mapped ABS first sightings or hidden frames leaked into stored observations");
    for (const auto* collectionName : {"mapped_gbs", "mapped_agbs"})
        for (auto row : fixture.db[collectionName].find({}))
            require(!row["agent_id"] && !row["private_person_id"] && !row["person_id"],
                "Grid capture exposed an individual/private identifier");
}

}

int main() {
    try {
        mongocxx::instance instance;
        auto client = std::make_shared<mongocxx::client>(mongocxx::uri{
            "mongodb://localhost:27017/?serverSelectionTimeoutMS=3000"});
        const std::string name = "UMP_sensor_regression_" + generateUUID();
        TestDatabase fixture{client->database(name)};
        const sf::FloatRect area({0.f, 0.f}, {20.f, 20.f});
        AgentBasedSensor abs(10.f, area, name, "abs", client);
        GridBasedSensor gbs(10.f, area, 5.f, name, "gbs", client);
        AdaptiveGridBasedSensor agbs(10.f, area, 10.f, 2, name, "agbs", client, "agbs-fast");
        AdaptiveGridBasedSensor slow(5.f, area, 10.f, 2, name, "agbs_slow", client, "agbs-slow");
        require(agbs.sensorId == "agbs-fast" && slow.sensorId == "agbs-slow", "Explicit sensor IDs lost");
        AdaptiveGridBasedSensor renderOnly(area, sf::Color::Blue, 10.f, 2, true);
        require(!renderOnly.getAggregationManager() && !agbs.getAggregationManager(),
            "Disabled/render-only AGBS unexpectedly instantiated a manager");
        const auto origin = TimePoint{std::chrono::milliseconds{1744191000000LL}};
        verifyMappedSensorLifecycle(client, name, fixture, origin);
        std::vector<ump::AggregationCandidate> fastCandidates, slowCandidates;
        ump::AggregationConfig fastConfig{"fixture", agbs.sensorId, "baseline", {0, 0, 20, 20, 2}, 100, 400};
        fastConfig.history = ump::HistoryLimits{1000, 16, 1000, 64000, 16};
        agbs.enableAggregation(fastConfig, 0.05f, origin,
            [&](const auto& result) { fastCandidates.push_back(result); });
        slow.enableAggregation({"fixture", slow.sensorId, "baseline", {0, 0, 20, 20, 2}, 200, 400},
            0.05f, origin, [&](const auto& result) { slowCandidates.push_back(result); });
        std::vector<Agent> agents;
        Agent::AgentTypeAttributes attributes{};

        std::size_t frameCount = 0;
        AdaptiveGridDisplayState display;
        std::size_t previousDisplayNodes = renderOnly.adaptiveGrid.nodeMap.size();
        require(previousDisplayNodes == 4, "Startup grid should contain the four base cells");
        // Known interval velocity (2, 1) m/s; enter, leave, then reenter the area.
        for (int ms = 0; ms <= 900; ms += 50) {
            agents.clear();
            if (ms <= 500 || ms >= 750) {
                agents.emplace_back(attributes);
                agents.back().agentId = "resident";
                agents.back().type = "pedestrian";
                agents.back().position = {1.f + 2.f * ms / 1000.f, 1.f + ms / 1000.f};
            }
            if (ms >= 350 && ms <= 500) {
                agents.emplace_back(attributes);
                agents.back().agentId = "entrant";
                agents.back().type = "pedestrian";
                agents.back().position = {6.f + 2.f * ms / 1000.f, 3.f + ms / 1000.f};
            }
            const auto timestamp = origin + std::chrono::milliseconds{ms};
            SensorFrameBuilder frame(timestamp);
            for (Sensor* sensor : {static_cast<Sensor*>(&abs), static_cast<Sensor*>(&gbs), static_cast<Sensor*>(&agbs), static_cast<Sensor*>(&slow)}) {
                sensor->update(agents, 0.05f, timestamp);
                if (auto sample = sensor->takeSample())
                    frame.add(sensor->sensorId, sensor->timestamp, std::move(*sample));
                require(!sensor->takeSample(), "Sensor sample was consumed twice");
                sensor->postData();
            }
            // Repeated writes, including non-capture ticks, must never resend ABS output.
            abs.postData();
            abs.postData();
            const bool due = ms > 0 && ms % 100 == 0;
            auto snapshot = std::move(frame).finish();
            require(static_cast<bool>(snapshot) == due, "Frame emitted without a measurement or due frame missing");
            if (display.update(snapshot, agbs.sensorId)) {
                renderOnly.adaptiveGrid.clear();
                renderOnly.adaptiveGrid.splitFromCellIds(display.cellIds());
            }
            if (!due) require(renderOnly.adaptiveGrid.nodeMap.size() == previousDisplayNodes,
                "Non-sampling tick erased visible subdivisions");
            for (int cellId : display.cellIds()) {
                const auto* rendered = renderOnly.adaptiveGrid.getNodeById(cellId);
                const auto* captured = agbs.adaptiveGrid.getNodeById(cellId);
                require(rendered && captured && rendered->bounds == captured->bounds,
                    "Grid display failed to reconstruct a measured cell at its real location");
            }
            if (ms == 100) require(renderOnly.adaptiveGrid.nodeMap.size() > 4,
                "First scheduled measurement did not subdivide the grid");
            if (ms == 600 || ms == 650 || ms == 700)
                require(renderOnly.adaptiveGrid.nodeMap.size() == 4, "Measured-empty interval kept old subdivisions");
            previousDisplayNodes = renderOnly.adaptiveGrid.nodeMap.size();
            if (snapshot) {
                ++frameCount;
                require(snapshot->first == timestamp, "Frame timestamp mismatch");
                require(snapshot->second.size() == (ms % 200 == 0 ? 4u : 3u), "Common frame cadence/IDs mismatch");
                const auto* sample = findSensorSample<AdaptiveGridSensorSample>(snapshot->second, agbs.sensorId);
                require(sample && sample->cells.empty() == (ms == 600 || ms == 700),
                        "Measured-empty AGBS payload lost its identity");
                const auto* slowSample = findSensorSample<AdaptiveGridSensorSample>(snapshot->second, slow.sensorId);
                require((slowSample != nullptr) == (ms % 200 == 0), "Slow sensor delayed or contaminated the common frame");
                const auto* agentSample = findSensorSample<AgentSensorSample>(snapshot->second, abs.sensorId);
                require(agentSample && agentSample->detectedAgents == agents.size(), "ABS observation count lost");
                const auto* gridSample = findSensorSample<GridSensorSample>(snapshot->second, gbs.sensorId);
                require(gridSample != nullptr, "GBS payload missing");
                int total = 0;
                for (const auto& cell : gridSample->cells) total += cell.counts.totalAgents;
                require(total == static_cast<int>(agents.size()), "GBS frame counts differ from capture");
            }
        }

        agbs.finishAggregation(origin + std::chrono::milliseconds{950});
        slow.finishAggregation(origin + std::chrono::milliseconds{950});
        require(fastCandidates.size() == 3 && slowCandidates.size() == 3,
            "Live AGBS adapter did not close fixed/partial windows");
        const std::vector<std::uint64_t> fastContributions{3, 4, 2}, slowContributions{1, 2, 1};
        const std::vector<std::uint64_t> expectedDistinct{1, 2, 1};
        for (std::size_t index = 0; index < 3; ++index) {
            require(fastCandidates[index].counts.observationContributions == fastContributions[index]
                && slowCandidates[index].counts.observationContributions == slowContributions[index],
                "AGBS internal contributions differ from raw capture");
            require(fastCandidates[index].counts.distinctContributors == expectedDistinct[index]
                && slowCandidates[index].counts.distinctContributors == expectedDistinct[index],
                "AGBS entry/reentry identities lost across observations");
            require(fastCandidates[index].coverage == ump::WindowCoverage::Complete
                && slowCandidates[index].coverage == ump::WindowCoverage::Complete,
                "AGBS adapter omitted a measured-empty sample");
        }
        require(fastCandidates[1].measuredSamples == 4 && slowCandidates[1].measuredSamples == 2,
            "Independent sensor schedules became coupled");
        require(fastCandidates.back().truncated && fastCandidates.back().endMs == 950,
            "Final AGBS partial interval not marked");
        require(agbs.getAggregationManager()->debugState().retainedIdentityMemberships == 0,
            "AGBS fixed accumulator retained identities after closure");

        const auto* history = agbs.getAggregationManager()->history();
        require(history && history->debugState().bins == 9 && history->debugState().observations == 9,
            "Live AGBS did not retain measured-empty samples and private observations");
        const auto historicalParent = history->query(ump::historyCell(fastConfig.coverage, 12, 1), 0, 950);
        require(historicalParent.status == ump::HistoryQueryStatus::Complete
            && historicalParent.candidate->counts.distinctContributors == 2
            && historicalParent.candidate->counts.observationContributions == 9
            && historicalParent.candidate->counts.meanSampleOccupancy == 1,
            "Live AGBS history could not reconstruct across closed windows");
        const auto emptyParent = history->query(ump::historyCell(fastConfig.coverage, 13, 1), 0, 950);
        require(emptyParent.status == ump::HistoryQueryStatus::Complete
            && emptyParent.candidate->counts.observationContributions == 0,
            "Unpopulated sibling lost known-empty coverage");
        require(!slow.getAggregationManager()->history(), "History leaked into an opt-out stream");

        require(frameCount == 9, "Expected 9 measured frames for 19 simulation steps");
        const Counts gridCounts{{100,1}, {200,1}, {300,1}, {400,2}, {500,2}, {800,1}, {900,1}};
        verifyGrid(fixture.db["gbs"], origin, gridCounts);
        verifyGrid(fixture.db["agbs"], origin, gridCounts);
        verifyGrid(fixture.db["agbs_slow"], origin, Counts{{200,1}, {400,2}, {800,1}});
        Counts absCounts;
        std::set<std::pair<int64_t, std::string>> absKeys;
        for (auto row : fixture.db["abs"].find({})) {
            const auto ms = sampleTime(row, origin);
            const std::string id{row["agent_id"].get_string().value};
            require(absKeys.emplace(ms, id).second, "Duplicate ABS identity/timestamp");
            ++absCounts[ms];
            const auto velocity = row["estimated_velocity"].get_document().view();
            require(std::abs(velocity["x"].get_double().value - 2.) < 1e-4
                 && std::abs(velocity["y"].get_double().value - 1.) < 1e-4,
                    "ABS interval velocity incorrect (including first/reentry estimate)");
            const auto position = row["position"].get_document().view();
            const float baseX = id == "resident" ? 1.f : 6.f;
            const float baseY = id == "resident" ? 1.f : 3.f;
            require(std::abs(position["x"].get_double().value - (baseX + 2.f * ms / 1000.f)) < 1e-5
                 && std::abs(position["y"].get_double().value - (baseY + ms / 1000.f)) < 1e-5,
                    "ABS identity/position/timestamp mismatch");
        }
        require(absCounts == Counts{{100,1}, {200,1}, {300,1}, {400,1}, {500,2}, {900,1}},
                "ABS startup, unknown-agent or reentry publication differs from expected");
        require(absKeys.count({500, "entrant"}) == 1 && absKeys.count({400, "entrant"}) == 0,
                "New entrant published without two observations");
        std::cout << "PASS: startup, interval velocities, batch consumption, entry/reentry, "
                     "grid counts, empty-area cadence, renderer timestamps and identity-bearing aggregation.\n";
        std::cout << "Isolated test database: " << name << " (removed on exit).\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL: " << e.what() << '\n';
        return 1;
    }
}
