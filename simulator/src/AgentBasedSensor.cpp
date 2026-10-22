#include <bsoncxx/builder/stream/document.hpp>
#include <mongocxx/exception/exception.hpp>
#include <mongocxx/instance.hpp>
#include <mongocxx/uri.hpp>
#include <bsoncxx/json.hpp>
#include <iostream>

#include "../include/AgentBasedSensor.hpp"

// Constructor
AgentBasedSensor::AgentBasedSensor(
    float frameRate,
    sf::FloatRect detectionArea,
    const std::string &databaseName,
    const std::string &collectionName,
    std::shared_ptr<mongocxx::client> client,
    std::string id
) : Sensor(frameRate, detectionArea, client, std::move(id)),
    db(client->database(databaseName)), // Initialize db in initializer list
    collection(db[collectionName])
{
    this->detectionArea = detectionArea;
}

// Alternative constructor for rendering
AgentBasedSensor::AgentBasedSensor(
    sf::FloatRect detectionArea,
    sf::Color detectionAreaColor
) : Sensor(detectionArea, detectionAreaColor) {
    this->detectionArea = detectionArea;
    this->detectionAreaColor = detectionAreaColor;
}

// Destructor
AgentBasedSensor::~AgentBasedSensor() {}

// Observe the initial state internally, then capture at the configured sampling rate.
void AgentBasedSensor::update(std::vector<Agent>& agents, float timeStep, std::chrono::system_clock::time_point timestamp) {
    this->timestamp = timestamp;
    pendingSample.reset();

    if (!samplingInitialized) {
        previousPositions.clear();
        for (const auto& agent : agents) {
            if (detectionArea.contains(agent.position)) {
                previousPositions[agent.agentId] = agent.position;
            }
        }
    }

    if (!isSamplingDue(timeStep)) {
        return;
    }

    captureAgentData(agents);
    pendingSample = AgentSensorSample{dataStorage.second, currentPositions.size()};
    previousPositions = std::move(currentPositions);
    currentPositions.clear();
}

// Assemble one output batch from consecutive observations of the same agents.
void AgentBasedSensor::captureAgentData(std::vector<Agent>& agents) {

    std::vector<AgentData> observations;
    currentPositions.clear();

    for (const auto& agent : agents) {
        if (!detectionArea.contains(agent.position)) {
            continue;
        }

        currentPositions[agent.agentId] = agent.position;
        const auto previous = previousPositions.find(agent.agentId);
        if (previous == previousPositions.end()) {
            // Keep the first position internally; publish after a second observation.
            continue;
        }

        AgentData observation;
        observation.sensorId = sensorId;
        observation.agentId = agent.agentId;
        observation.timestamp = timestamp;
        observation.type = agent.type;
        observation.position = agent.position;
        // Valid for the fixed, aligned sampling intervals used by the current setup.
        observation.estimatedVelocity = (agent.position - previous->second) * frameRate;
        observations.emplace_back(std::move(observation));
    }

    dataStorage = {timestamp, std::move(observations)};
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
    const auto& timestamp = dataStorage.first;
    const auto& pendingObservations = dataStorage.second;

    // Check if there is data to post
    if (!pendingObservations.empty()) {

        // Prepare a vector of BSON documents to insert in bulk
        std::vector<bsoncxx::document::value> documents;
        documents.reserve(pendingObservations.size());

        // Iterate through the stored data
        for (const auto& agentDataPoint : pendingObservations) {

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
            // Consume only after success; another postData() call must not resend this batch.
            dataStorage.second.clear();
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
