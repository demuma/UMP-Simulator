#pragma once

#include <SFML/System/Vector2.hpp>
#include <chrono>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <variant>
#include <vector>

using SensorTime = std::chrono::system_clock::time_point;

struct AgentObservation {
    std::string sensorId;
    std::string agentId;
    SensorTime timestamp;
    std::string type;
    sf::Vector2f position;
    sf::Vector2f estimatedVelocity;
};

struct CellCounts {
    std::unordered_map<std::string, int> agentTypeCount;
    int totalAgents = 0;
};

struct AgentSensorSample {
    // The existing ABS contract emits only observations with a velocity estimate.
    // detectedAgents also includes first sightings, which are retained internally.
    std::vector<AgentObservation> agents;
    std::size_t detectedAgents = 0;
};

struct GridCellSample {
    sf::Vector2i index;
    CellCounts counts;
};
struct GridSensorSample { std::vector<GridCellSample> cells; };
struct AdaptiveGridSensorSample { std::unordered_map<int, CellCounts> cells; };

using SensorSample = std::variant<AgentSensorSample, GridSensorSample, AdaptiveGridSensorSample>;
// Absence of an ID means no observation was due. A present, empty payload means measured empty.
using sensorFrame = std::unordered_map<std::string, SensorSample>;
using sensorFrameType = std::pair<SensorTime, sensorFrame>;
using sensorBufferFrameType = std::shared_ptr<const sensorFrameType>;

// One builder per simulation step. Finish after all due sensors have contributed.
// A step without observations returns no frame; a measured-empty payload retains its ID.
class SensorFrameBuilder {
public:
    explicit SensorFrameBuilder(SensorTime timestamp) : timestamp(timestamp) {}
    void add(const std::string& id, SensorTime observationTime, SensorSample sample) {
        if (id.empty() || observationTime != timestamp)
            throw std::invalid_argument("Sensor contribution has an invalid ID or timestamp");
        if (!samples.emplace(id, std::move(sample)).second)
            throw std::invalid_argument("Duplicate sensor contribution for one step");
    }
    sensorBufferFrameType finish() && {
        if (samples.empty()) return {};
        return std::make_shared<const sensorFrameType>(timestamp, std::move(samples));
    }
private:
    SensorTime timestamp;
    sensorFrame samples;
};

template<class Payload>
const Payload* findSensorSample(const sensorFrame& frame, const std::string& id) {
    const auto it = frame.find(id);
    return it == frame.end() ? nullptr : std::get_if<Payload>(&it->second);
}
