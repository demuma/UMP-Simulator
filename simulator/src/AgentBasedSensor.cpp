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
    agentData.clear();

    // Update the time since the last update
    timeSinceLastUpdate += timeStep;

    // Update the estimated velocities at the specified frame rate
    // if (timeSinceLastUpdate >= 1.0f / frameRate || frameCount != 0) {
    if (timeSinceLastUpdate >= 1.0f / frameRate) {

        // Capture agent data
        captureAgentData(agents);

        // Estimate the velocities of the agents
        estimateVelocities(estimatedVelocities);

        // Reset for next update
        previousPositions = currentPositions;
        currentPositions.clear();
        timeSinceLastUpdate = 0.0f;
    }
}

// Make a snapshot of the agents in the detection area
void AgentBasedSensor::captureAgentData(std::vector<Agent>& agents) {

    // Capture the current positions of the agents
    for (Agent& agent : agents) {

        // Check if the agent is within the detection area
        if (detectionArea.contains(agent.position)) {

            // Prepare SensorData object for the agent
            AgentData agentDataPoint;
            agentDataPoint.sensorId = sensorId;
            agentDataPoint.agentId = agent.agentId;
            agentDataPoint.timestamp = timestamp;
            agentDataPoint.type = agent.type;
            agentDataPoint.position = agent.position;

            // Estimate and store the velocity of the agent TODO: Only save with velocity
            if (previousPositions.find(agent.agentId) != previousPositions.end()) {
                sf::Vector2f prevPos = previousPositions[agent.agentId];
                agentDataPoint.estimatedVelocity = (agent.position - previousPositions[agent.agentId]) * frameRate;
            }

            // Store the agent data
            agentData.emplace_back(agentDataPoint);
            
            // Store the current position of a specific agent using its UUID 
            currentPositions[agent.agentId] = agent.position;
        }
    }
    // Store the timestamped data in the data storage
    dataStorage = {timestamp, std::move(agentData)};
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
    const auto& agentData = dataStorage.second;

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
    for (const AgentData& agentDataPoint : agentData) {

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