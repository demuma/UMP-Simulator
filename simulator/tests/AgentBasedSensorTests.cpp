#include "AgentBasedSensor.hpp"
#include <mongocxx/instance.hpp>
#include <cmath>
#include <cstdlib>
#include <stdexcept>

namespace {
using Time = std::chrono::system_clock::time_point;

Time at(int milliseconds) {
    return Time{std::chrono::milliseconds{milliseconds}};
}

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

void checkVelocity(const AgentBasedSensor::AgentData& record, float x, float y) {
    require(std::abs(record.estimatedVelocity.x - x) < 0.00001f, "Wrong x velocity");
    require(std::abs(record.estimatedVelocity.y - y) < 0.00001f, "Wrong y velocity");
}

struct Fixture {
    SharedBuffer<sensorBufferFrameType> buffer{"test"};
    // Rendering constructor creates no database connection or graphics window.
    AgentBasedSensor sensor{sf::FloatRect{{0.f, 0.f}, {100.f, 100.f}}, sf::Color::White, buffer};
    std::vector<Agent> agents;

    Fixture() {
        sensor.frameRate = 10.f;
        sensor.sensorId = "test-sensor";
        agents.emplace_back(Agent::AgentTypeAttributes{});
        agents[0].agentId = "test-agent";
        agents[0].type = "Pedestrian";
        agents[0].position = {10.f, 10.f};
    }
};

void initialIntervalAndSingleConsumption() {
    Fixture f;
    f.sensor.initializeObservations(f.agents, at(0));
    f.sensor.update(f.agents, 0.05f, at(0));
    require(f.sensor.takeMeasurements().empty(), "Published before a second observation");
    f.agents[0].position = {10.25f, 10.125f};
    f.sensor.update(f.agents, 0.05f, at(50));
    auto batch = f.sensor.takeMeasurements();
    require(batch.size() == 1, "Missing initial velocity measurement");
    require(batch[0].timestamp == at(50), "Changed observation timestamp");
    require(batch[0].agentId == "test-agent", "Changed GT agent identity");
    require(batch[0].position == f.agents[0].position, "Changed GT position");
    checkVelocity(batch[0], 5.f, 2.5f);
    require(f.sensor.takeMeasurements().empty(), "Returned the same batch twice");
    f.sensor.update(f.agents, 0.05f, at(100));
    require(f.sensor.takeMeasurements().empty(), "Republished during a non-measurement tick");
    f.agents[0].position = {10.75f, 10.375f};
    f.sensor.update(f.agents, 0.05f, at(150));
    batch = f.sensor.takeMeasurements();
    require(batch.size() == 1, "Missing subsequent measurement");
    checkVelocity(batch[0], 5.f, 2.5f);
}

void staleBatchNotRepublished() {
    Fixture f;
    f.sensor.initializeObservations(f.agents, at(0));
    f.sensor.update(f.agents, 0.05f, at(0));
    f.agents[0].position.x += 0.25f;
    f.sensor.update(f.agents, 0.05f, at(50));
    // Deliberately leave the batch undrained, as the former repeated postData path did.
    f.sensor.update(f.agents, 0.05f, at(100));
    require(f.sensor.takeMeasurements().empty(), "Stale batch survived a non-measurement tick");
}

void actualIntervalInsteadOfConfiguredFrequency() {
    Fixture f;
    f.sensor.initializeObservations(f.agents, at(0));
    f.sensor.update(f.agents, 0.075f, at(0));
    f.agents[0].position.x += 0.75f;
    f.sensor.update(f.agents, 0.075f, at(75));
    auto batch = f.sensor.takeMeasurements();
    require(batch.size() == 1, "Missing non-aligned initial sample");
    checkVelocity(batch[0], 10.f, 0.f);
    f.sensor.update(f.agents, 0.075f, at(150));
    f.agents[0].position.x += 1.5f;
    f.sensor.update(f.agents, 0.075f, at(225));
    batch = f.sensor.takeMeasurements();
    require(batch.size() == 1, "Missing non-aligned later sample");
    checkVelocity(batch[0], 10.f, 0.f);
}

void newAndReenteringAgentNeedsTwoObservations() {
    Fixture f;
    f.sensor.update(f.agents, 0.1f, at(0));
    require(f.sensor.takeMeasurements().empty(), "Published a new agent with placeholder velocity");
    f.agents[0].position.x += 1.f;
    f.sensor.update(f.agents, 0.1f, at(100));
    auto batch = f.sensor.takeMeasurements();
    require(batch.size() == 1, "Missing second observation");
    checkVelocity(batch[0], 10.f, 0.f);
    f.agents[0].position.x = 101.f;
    f.sensor.update(f.agents, 0.1f, at(200));
    require(f.sensor.takeMeasurements().empty(), "Published an agent outside the detection area");
    f.agents[0].position.x = 20.f;
    f.sensor.update(f.agents, 0.1f, at(300));
    require(f.sensor.takeMeasurements().empty(), "Estimated velocity across an observation gap");
    f.agents[0].position.x = 21.f;
    f.sensor.update(f.agents, 0.1f, at(400));
    batch = f.sensor.takeMeasurements();
    require(batch.size() == 1, "Missing second observation after reentry");
    checkVelocity(batch[0], 10.f, 0.f);
}

void zeroDurationNotPublished() {
    Fixture f;
    f.sensor.initializeObservations(f.agents, at(0));
    f.sensor.update(f.agents, 0.1f, at(0));
    require(f.sensor.takeMeasurements().empty(), "Published a zero-duration estimate");
}
}

int main() {
    mongocxx::instance instance{};
    try {
        initialIntervalAndSingleConsumption();
        staleBatchNotRepublished();
        actualIntervalInsteadOfConfiguredFrequency();
        newAndReenteringAgentNeedsTwoObservations();
        zeroDurationNotPublished();
        std::cout << "PASS: five ABS regression scenarios (no database access)\n";
    } catch (const std::exception& e) {
        std::cerr << "FAIL: " << e.what() << '\n';
        return EXIT_FAILURE;
    }
}
