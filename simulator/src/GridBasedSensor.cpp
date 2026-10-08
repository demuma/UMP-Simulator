#include <bsoncxx/builder/stream/document.hpp>
#include <mongocxx/exception/exception.hpp>
#include <mongocxx/instance.hpp>
#include <mongocxx/uri.hpp>
#include <bsoncxx/json.hpp>
#include <iostream>

#include "../include/GridBasedSensor.hpp"

// Constructor
GridBasedSensor::GridBasedSensor(
    float frameRate,
    sf::FloatRect detectionArea,
    float cellSize,
    const std::string& databaseName,
    const std::string& collectionName,
    std::shared_ptr<mongocxx::client> client,
    SharedBuffer<sensorBufferFrameType>& sensorBuffer
) : Sensor(frameRate, detectionArea, client, sensorBuffer),
    cellSize(cellSize),
    db(client->database(databaseName)),
    collection(db[collectionName]),
    sensorBuffer(sensorBuffer),
    currentGrid(cellSize, detectionArea),
    previousGrid(cellSize, detectionArea)
{
    this->detectionArea = detectionArea;
}

// Alternative constructor for rendering
GridBasedSensor::GridBasedSensor(
    sf::FloatRect detectionArea, 
    sf::Color detectionAreaColor, 
    float cellSize, 
    bool showGrid,
    SharedBuffer<sensorBufferFrameType>& sensorBuffer
) : Sensor(detectionArea, detectionAreaColor, sensorBuffer), 
    cellSize(cellSize), currentGrid(cellSize, detectionArea), 
    sensorBuffer(sensorBuffer),
    previousGrid(cellSize, detectionArea) {
        this->detectionArea = detectionArea;
        this->detectionAreaColor = detectionAreaColor;
        this->showGrid = showGrid;
    }

// Destructor
GridBasedSensor::~GridBasedSensor() {
    
    // Empty
    gridData.clear();
    dataStorage.clear();
    currentGrid.clear();
    previousGrid.clear();
}

// Update grid-based agent detection and output one gridData entry per frame
void GridBasedSensor::update(std::vector<Agent>& agents, float timeStep, std::chrono::system_clock::time_point timestamp) {

    // Update current timestamp
    this->timestamp = timestamp;

    // Clear data storage
    dataStorage.clear();

    // Update the time since the last update
    timeSinceLastUpdate += timeStep;

    // Update the estimated velocities at the specified frame rate
    if (timeSinceLastUpdate >= 1.0f / frameRate) {

        // Clear the grid data
        gridData.clear();

        // Store the previous grid data
        previousGrid = currentGrid;
        currentGrid.clear();

        // Reset boolean flag
        bool hasAgents = false;

        // Declare a variable to store the cell index
        sf::Vector2i cellIndex;

        // Iterate through the agents
        for (Agent& agent : agents) {

            // Check if the agent is within the detection area
            if (detectionArea.contains(agent.position)) {
                
                // Set the flag to true
                hasAgents = true;

                // Add the agent to the current grid and get the cell index
                cellIndex = currentGrid.addAgent(&agent);
                // std::cout << "Agent of type " << agent.type << " at position (" << agent.position.x << ", " << agent.position.y << ") added to cell (" << cellIndex.x << ", " << cellIndex.y << ")\n";

                // Increment the count of the agent type in the cell
                gridData[cellIndex].agentTypeCount[agent.type]++;
                gridData[cellIndex].totalAgents++;
            }
        }

        // Clear the previous positions and reset the time since the last update
        if(hasAgents) {

            timeSinceLastUpdate = 0.0f;
            dataStorage.push_back({timestamp, gridData}); // Pushing exactly one entry to dataStorage
        }
    }
}

// Post metadata to the database
void GridBasedSensor::postMetadata() {

    // Prepare a BSON document for the metadata
    bsoncxx::builder::stream::document document{};
    bsoncxx::builder::stream::document positionDocument{}, detectionAreaDocument{};

    positionDocument << "x" << detectionArea.position.x
                      << "y" << detectionArea.position.y;
    detectionAreaDocument << "width" << detectionArea.size.x
                          << "height" << detectionArea.size.y;

    document << "timestamp" << bsoncxx::types::b_date{timestamp}
             << "sensor_id" << sensorId
             << "sensor_type" << "grid-based"
             << "data_type" << "metadata"
             << "position" << positionDocument
             << "detection_area" << detectionAreaDocument
             << "frame_rate" << frameRate
             << "cell_size" << cellSize;

    // Insert the metadata document into the collection
    try {
        collection.insert_one(document << bsoncxx::builder::stream::finalize);
    } catch (const mongocxx::exception& e) {
        // Handle errors
        std::cerr << "Error inserting metadata: " << e.what() << std::endl;
    }
}

// Post timestamped grid data to the database
void GridBasedSensor::postData() {

    // Check if there is data to post
    if(!dataStorage.empty()) {

        // Create a vector of documents for bulk insert
        std::vector<bsoncxx::document::value> documents;

        // Iterate through the data storage (currently only one entry in dataStorage)
        for (const auto& [timestamp, gridData] : dataStorage) {

            // Iterate through the grid data
            for (const auto& [cellIndex, cellData] : gridData) {
                
                // Document for the grid cell
                bsoncxx::builder::stream::document document{}, 
                                                   cellPositionDocument{},
                                                   cellIndexDocument{};

                cellPositionDocument << "x" << getCellPosition(cellIndex).x
                                     << "y" << getCellPosition(cellIndex).y;

                cellIndexDocument << "x" << cellIndex.x
                                  << "y" << cellIndex.y;

                document << "timestamp" << bsoncxx::types::b_date{timestamp}
                         << "sensor_id" << sensorId
                         << "data_type" << "grid data"
                         << "cell_index" << cellIndexDocument
                         << "cell_position" << cellPositionDocument;

                // Open an array for the agent type count
                auto agentTypeBuilder = document << "agent_type_count" << bsoncxx::builder::stream::open_array;

                // Loop through the vector and add each element to the array
                for (const auto& [agentType, count] : cellData.agentTypeCount) {

                    // Open a document for each agent type and count
                    agentTypeBuilder << bsoncxx::builder::stream::open_document
                                << "type" << agentType
                                << "count" << count
                                << bsoncxx::builder::stream::close_document;  // Close the document
                }

                // Close the array
                agentTypeBuilder << bsoncxx::builder::stream::close_array;

                // Add total agent count for the cell
                document << "total_agents" << cellData.totalAgents;
                
                // Add the document to the vector for bulk insert
                documents.push_back(document << bsoncxx::builder::stream::finalize);
            }
        }

        // Bulk insert the documents into the collection
        try {
            collection.insert_many(documents);
        } catch (const mongocxx::exception& e) {
            // Handle errors
            std::cerr << "Error inserting agent data: " << e.what() << std::endl;
        }
    }
}

// Print grid data
void GridBasedSensor::printData() {

    // auto currentTime = std::chrono::system_clock::now();

    std::time_t now = std::chrono::system_clock::to_time_t(timestamp);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&now), "%FT%TZ");
    
    // Print grid data
    for (const auto& kvp : gridData) { // key-value pair

        const sf::Vector2i& cellIndex = kvp.first;
        const GridDataPoint& cellData = kvp.second;

        std::cout << "Timestamp: " << ss.str() << " Cell (" << cellIndex.x << ", " << cellIndex.y << "): ";

        // Going through key-value pairs in the cell data
        for (const auto& kvp : cellData.agentTypeCount) {
            
            // Print agent type and count
            const std::string& agentType = kvp.first;
            int count = kvp.second;
            std::cout << agentType << ": " << count << ", ";
        }
        std::cout << std::endl;
    }
    gridData.clear();
}

// Clear the database
void GridBasedSensor::clearDatabase() {

    // Clear the collection
    collection.delete_many({});
}

// Helper function to get cell index based on position
sf::Vector2i GridBasedSensor::getCellIndex(const sf::Vector2f& position) const {

    int x = static_cast<int>((position.x - detectionArea.position.x) / cellSize);
    int y = static_cast<int>((position.y - detectionArea.position.y)/ cellSize);

    return sf::Vector2i(x, y);
}

// sf::Vector2f GridBasedSensor::getCellPosition(const sf::Vector2i& cellIndex) const {

//     float x = (cellIndex.x * cellSize + detectionArea.position.x + cellSize / 2);
//     float y = (cellIndex.y * cellSize + detectionArea.position.y + cellSize / 2);

//     return sf::Vector2f(x, y);
// }

sf::Vector2f GridBasedSensor::getCellPosition(const sf::Vector2i& cellIndex) const {

    float x = cellIndex.x * cellSize + detectionArea.position.x;
    float y = cellIndex.y * cellSize + detectionArea.position.y;

    return sf::Vector2f(x, y);
}