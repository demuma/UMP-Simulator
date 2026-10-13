#include "AgentBasedSensor.hpp"
#include "GridBasedSensor.hpp"
#include "AdaptiveGridBasedSensor.hpp"
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
        AdaptiveGridBasedSensor agbs(10.f, area, 20.f, 2, name, "agbs", client, "agbs-fast");
        AdaptiveGridBasedSensor slow(5.f, area, 20.f, 2, name, "agbs_slow", client, "agbs-slow");
        require(agbs.sensorId == "agbs-fast" && slow.sensorId == "agbs-slow", "Explicit sensor IDs lost");
        const auto origin = TimePoint{std::chrono::milliseconds{1744191000000LL}};
        std::vector<Agent> agents;
        Agent::AgentTypeAttributes attributes{};

        std::size_t frameCount = 0;
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
                     "grid counts, empty-area cadence and renderer timestamps.\n";
        std::cout << "Isolated test database: " << name << " (removed on exit).\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL: " << e.what() << '\n';
        return 1;
    }
}
