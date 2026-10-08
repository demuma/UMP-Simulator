#include <bsoncxx/builder/stream/document.hpp>
#include <mongocxx/exception/exception.hpp>
#include <mongocxx/instance.hpp>
#include <mongocxx/uri.hpp>
#include <bsoncxx/json.hpp>
#include <iostream>
#include <utility>

#include "../include/AgentBasedSensor.hpp"

// Constructor
AgentBasedSensor::AgentBasedSensor(
    float frameRate,
    sf::FloatRect detectionArea,
    const std::string &databaseName,
    const std::string &collectionName,
    std::shared_ptr<mongocxx::client> client,
    SharedBuffer<sensorBufferFrameType>& sensorBuffer
) : Sensor(frameRate, detectionArea, client, sensorBuffer),
    db(client->database(databaseName)), // Initialize db in initializer list
    collection(db[collectionName]),
    sensorBuffer(sensorBuffer)
{
    this->detectionArea = detectionArea;
}

// Alternative constructor for rendering
AgentBasedSensor::AgentBasedSensor(
    sf::FloatRect detectionArea,
    sf::Color detectionAreaColor,
    SharedBuffer<sensorBufferFrameType>& sensorBuffer
) : Sensor(detectionArea, detectionAreaColor, sensorBuffer), 
    sensorBuffer(sensorBuffer) {
    this->detectionArea = detectionArea;
    this->detectionAreaColor = detectionAreaColor;
}

// Destructor
AgentBasedSensor::~AgentBasedSensor() {}

// Update method for agent-based sensor, taking snapshot of agents in detection area
// void AgentBasedSensor::update(std::vector<Agent>& agents, float timeStep, sf::Time simulationTime, std::string datetime) {
void AgentBasedSensor::update(std::vector<Agent>& agents, float timeStep, std::chrono::system_clock::time_point timestamp) {

    // Update current timestamp
    this->timestamp = timestamp;

    // Clear the data storage
    dataStorage.second.clear();

    // Update the time since the last update
    timeSinceLastUpdate += timeStep;

    // Update the estimated velocities at the specified frame rate
    // if (timeSinceLastUpdate >= 1.0f / frameRate || frameCount != 0) {
    if (timeSinceLastUpdate >= 1.0f / frameRate) {

        // Capture agent data
        captureAgentData(agents);

        timeSinceLastUpdate = 0.0f;
    }
}

void AgentBasedSensor::initializeObservations(
    const std::vector<Agent>& agents,
    std::chrono::system_clock::time_point timestamp
) {
    this->timestamp = timestamp;
    timeSinceLastUpdate = 0.0f;
    previousObservations.clear();
    dataStorage = {timestamp, {}};
    for (const auto& agent : agents) {
        if (detectionArea.contains(agent.position)) {
            previousObservations.emplace(agent.agentId, Observation{agent.position, timestamp});
        }
    }
}

// Make a snapshot of the agents in the detection area
void AgentBasedSensor::captureAgentData(std::vector<Agent>& agents) {

    dataStorage = {timestamp, {}};
    std::unordered_map<std::string, Observation> observations;

    // Capture the current positions of the agents
    for (Agent& agent : agents) {

        // Check if the agent is within the detection area
        if (detectionArea.contains(agent.position)) {

            observations.emplace(agent.agentId, Observation{agent.position, timestamp});
            const auto previous = previousObservations.find(agent.agentId);
            // A new or re-entering agent needs two observations before publication.
            if (previous == previousObservations.end()) {
                continue;
            }
            const double elapsedSeconds = std::chrono::duration<double>(
                timestamp - previous->second.timestamp
            ).count();
            if (elapsedSeconds <= 0.0) {
                continue;
            }

            // Prepare SensorData object for the agent
            AgentData agentDataPoint;
            agentDataPoint.sensorId = sensorId;
            agentDataPoint.agentId = agent.agentId;
            agentDataPoint.timestamp = timestamp;
            agentDataPoint.type = agent.type;
            agentDataPoint.position = agent.position;

            const auto displacement = agent.position - previous->second.position;
            agentDataPoint.estimatedVelocity = {
                static_cast<float>(displacement.x / elapsedSeconds),
                static_cast<float>(displacement.y / elapsedSeconds)
            };

            // Store the agent data
            dataStorage.second.emplace_back(std::move(agentDataPoint));
        }
    }
    previousObservations = std::move(observations);
}

std::vector<AgentBasedSensor::AgentData> AgentBasedSensor::takeMeasurements() {
    return std::exchange(dataStorage.second, std::vector<AgentData>{});
}

// Post metadata method for agent-based sensor (position, detection area, frame rate)
void AgentBasedSensor::postMetadata() {

    // Prepare a BSON document for the metadata
    bsoncxx::builder::stream::document document{};

    bsoncxx::builder::stream::document positionDocument{}, detectionAreaDocument{};
    positionDocument << "x" << detectionArea.position.x
                      << "y" << detectionArea.position.y;
    detectionAreaDocument << "width" << detectionArea.size.x
                          << "height" << detectionArea.size.y;

    // Append the metadata fields to the document
    // document << "timestamp" << generateBsonDate(timestamp)
    document << "timestamp" << bsoncxx::types::b_date{timestamp}
             << "sensor_id" << sensorId
             << "sensor_type" << "agent-based"
             << "data_type" << "metadata"             
             << "position" << positionDocument
             << "detection_area" << detectionAreaDocument
             << "frame_rate" << frameRate;

    // Insert the metadata document into the collection
    try {
        collection.insert_one(document << bsoncxx::builder::stream::finalize);
    } catch (const mongocxx::exception& e) {
        // Handle errors
        std::cerr << "Error inserting metadata: " << e.what() << std::endl;
    }
}

// Post data method for agent-based sensor
void AgentBasedSensor::postData() {

    // Get the agent data from the data storage
    const auto timestamp = dataStorage.first;
    const auto agentData = takeMeasurements();

    // Check if there is data to post
    if (!agentData.empty()) {

        // Prepare a vector of BSON documents to insert in bulk
        std::vector<bsoncxx::document::value> documents;
        documents.reserve(agentData.size());

        // Iterate through the stored data
        for (const auto& agentDataPoint : agentData) {

            // Construct a BSON document for each agent data object
            bsoncxx::builder::stream::document document{}, 
                                               positionDocument{}, 
                                               estimatedVelocityDocument{};

            // Prepare the position and estimated velocity documents
            positionDocument << "x" << agentDataPoint.position.x
                             << "y" << agentDataPoint.position.y;
                             
            estimatedVelocityDocument << "x" << agentDataPoint.estimatedVelocity.x
                                      << "y" << agentDataPoint.estimatedVelocity.y;

            // Append the fields to the document
            document << "timestamp" << bsoncxx::types::b_date{timestamp}
                     << "sensor_id" << agentDataPoint.sensorId
                     << "data_type" << "agent data"
                     << "agent_id" << agentDataPoint.agentId
                     << "type" << agentDataPoint.type
                     << "position" << positionDocument
                     << "estimated_velocity" << estimatedVelocityDocument;

            documents.push_back(document << bsoncxx::builder::stream::finalize);
        }

        try {
            // Bulk insert the documents into the collection
            collection.insert_many(documents);
        } catch (const mongocxx::exception& e) {
            // Handle errors
            std::cerr << "Error inserting agent data: " << e.what() << std::endl;
        }
    }
}

// Print the stored data
void AgentBasedSensor::printData() {

    // Print the stored data
    for (const AgentData& agentDataPoint : dataStorage.second) {

        std::cout << "  Timestamp: " << generateISOTimestampString(agentDataPoint.timestamp) << std::endl;
        std::cout << "  Sensor ID: " << agentDataPoint.sensorId << std::endl;
        std::cout << "  Agent ID: " << agentDataPoint.agentId << std::endl;
        std::cout << "  Agent Type: " << agentDataPoint.type << std::endl;
        std::cout << "  Position: (" << agentDataPoint.position.x << ", " << agentDataPoint.position.y << ")" << std::endl;
        std::cout << "  Estimated Velocity: (" << agentDataPoint.estimatedVelocity.x << ", " << agentDataPoint.estimatedVelocity.y << ")" << std::endl;
        std::cout << std::endl;
    }
}

// Clear the database
void AgentBasedSensor::clearDatabase() {

    // Clear the collection
    collection.delete_many({});
}
