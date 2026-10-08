#include <bsoncxx/builder/stream/document.hpp>
#include <mongocxx/exception/exception.hpp>
#include <mongocxx/instance.hpp>
#include <mongocxx/uri.hpp>
#include <bsoncxx/json.hpp>
#include <iostream>

#include "../include/AdaptiveGridBasedSensor.hpp"

// Base constructor for simulation
AdaptiveGridBasedSensor::AdaptiveGridBasedSensor(
    float frameRate,
    sf::FloatRect detectionArea,
    float cellSize,
    int maxDepth,
    const std::string &databaseName,
    const std::string &collectionName,
    std::shared_ptr<mongocxx::client> client,
    SharedBuffer<sensorBufferFrameType>& sensorBuffer
) : Sensor(frameRate, detectionArea, client, sensorBuffer),
    cellSize(cellSize), // Half the longest side of the detection area
    maxDepth(maxDepth),
    db(client->database(databaseName)),
    collection(db[collectionName]),
    adaptiveGrid(detectionArea.position.x, detectionArea.position.y, cellSize, maxDepth),
    aggregationManager(collection, sensorId, timestamp),
    sensorBuffer(sensorBuffer)
{
    this->detectionArea = detectionArea;
}

// Alternative constructor for rendering
AdaptiveGridBasedSensor::AdaptiveGridBasedSensor(
    sf::FloatRect detectionArea, 
    sf::Color detectionAreaColor, 
    float cellSize, 
    int maxDepth,
    bool showGrid,
    SharedBuffer<sensorBufferFrameType>& sensorBuffer
)
    : Sensor(detectionArea, detectionAreaColor, sensorBuffer), 
    cellSize(cellSize), 
    adaptiveGrid(detectionArea.position.x, detectionArea.position.y, cellSize, maxDepth), maxDepth(maxDepth), 
    aggregationManager(collection, sensorId, timestamp), sensorBuffer(sensorBuffer) 
    {
        this->detectionArea = detectionArea;
        this->detectionAreaColor = detectionAreaColor;
        this->showGrid = showGrid;
    }

// Destructor
AdaptiveGridBasedSensor::~AdaptiveGridBasedSensor() {
    
    // Empty
    adaptiveGridData.clear();
    dataStorage.clear();
    adaptiveGrid.reset(); // Reset instead of clear
}

// Update grid-based agent detection and output one gridData entry per frame
void AdaptiveGridBasedSensor::update(std::vector<Agent>& agents, float timeStep, std::chrono::system_clock::time_point timestamp) {
    
    // Update current timestamp
    this->timestamp = timestamp;
    
    // Clear data storage
    dataStorage.clear();
    currentCellIds.clear();

    // // Get the current timestamp as a string
    // auto currentTime = timestamp;

    // Update the time since the last update
    timeSinceLastUpdate += timeStep;

    // Update the estimated velocities at the specified frame rate
    if (timeSinceLastUpdate >= 1.0f / frameRate) {

        // Clear the grid data
        // adaptiveGridData.clear();
        adaptiveGridData.clear();
        adaptiveGrid.agents.clear();
        adaptiveGrid.positions.clear();

        // Reset boolean flag
        bool hasAgents = false;

        // Iterate through the agents
        for (Agent& agent : agents) {
            if (detectionArea.contains(agent.position)) {
                adaptiveGrid.agents.push_back(&agent);
                adaptiveGrid.positions.push_back(agent.position);
                hasAgents = true;
            }
        }

        if(hasAgents) {

            // Generate split sequence
            adaptiveGrid.splitFromPositions();
            
            for (Agent* agentPtr : adaptiveGrid.agents) {
                Agent& agent = *agentPtr;
                
                // Add the agent to the adaptive grid
                int cellId = adaptiveGrid.addAgent(&agent);
                
                // Add cell id to sensor buffer for snapshotting
                currentCellIds[sensorId].insert(cellId); // unordered set
                
                // Increment the count of the agent type and total agents in the cell
                adaptiveGridData[cellId].agentTypeCount[agent.type]++;
                adaptiveGridData[cellId].totalAgents++;
            }
            
            // Create a shared pointer to the timestamped current cell ids
            auto currentCellIdsPtr = std::make_shared<sensorFrameType>(this->timestamp, std::move(currentCellIds));
            
            // Write the current cell ids to the sensor buffer
            sensorBuffer.write(currentCellIdsPtr);

            // Reset the time since the last update
            timeSinceLastUpdate = 0.0f;

            // Push timestamped adaptive grid data to the data storage
            dataStorage.push_back({this->timestamp, adaptiveGridData});
        }
        else {
            // If no agents detected, write empty data to the sensor buffer
            auto emptyCellIdsPtr = std::make_shared<sensorFrameType>(this->timestamp, std::move(sensorFrame{}));
            sensorBuffer.write(emptyCellIdsPtr);
        }
    }
}

// Post metadata to the database
void AdaptiveGridBasedSensor::postMetadata() {

    // Prepare a BSON document for the metadata
    bsoncxx::builder::stream::document document{}, 
                                       positionDocument{}, 
                                       detectionAreaDocument{};
    
    positionDocument << "x" << detectionArea.position.x
                      << "y" << detectionArea.position.y;
    detectionAreaDocument << "width" << detectionArea.size.x
                          << "height" << detectionArea.size.y;

    // document << "timestamp" << timestamp
    document << "timestamp" << bsoncxx::types::b_date{timestamp}
             << "sensor_id" << sensorId
             << "sensor_type" << "adaptive-grid-based"
             << "data_type" << "metadata"
             << "position" << positionDocument
             << "detection_area" << detectionAreaDocument
             << "frame_rate" << frameRate
             << "cell_size" << cellSize
             << "max_depth" << maxDepth;

    // Insert the metadata document into the collection
    try {
        collection.insert_one(document << bsoncxx::builder::stream::finalize);
    } catch (const mongocxx::exception& e) {
        // Handle errors
        std::cerr << "Error inserting metadata: " << e.what() << std::endl;
    }
}

// Post timestamped grid data to the database
void AdaptiveGridBasedSensor::postData() {

    // Check if there is data to post
    if(!dataStorage.empty()) {

        // Create a vector of documents for bulk insert
        std::vector<bsoncxx::document::value> documents;

        // Iterate through the data storage (currently only one entry in dataStorage)
        for (const auto& [timestamp, adaptiveGridData] : dataStorage) {

            // Iterate through the grid data
            for (const auto& [cellId, cellData] : adaptiveGridData) {
                
                // Document for the grid cell
                // TODO: Remove cell position and cell size from the document
                bsoncxx::builder::stream::document document{},
                                                   cellPositionDocument{};

                cellPositionDocument << "x" << adaptiveGrid.getCellPosition(cellId).x
                                     << "y" << adaptiveGrid.getCellPosition(cellId).y;

                document << "timestamp" << bsoncxx::types::b_date{timestamp}
                         << "sensor_id" << sensorId
                         << "data_type" << "adaptive grid data"
                         << "cell_id" << cellId
                         << "cell_position" << cellPositionDocument
                         << "cell_size" << adaptiveGrid.getCellDimensions(cellId).x;

                // Open an array for the agent type count
                auto agentTypeBuilder = document << "agent_type_count" << bsoncxx::builder::stream::open_array;

                for (const auto& [agentType, count] : cellData.agentTypeCount) {

                    // Open a document for each agent type and count
                    agentTypeBuilder 
                        << bsoncxx::builder::stream::open_document
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
void AdaptiveGridBasedSensor::printData() {

    // auto currentTime = std::chrono::system_clock::now();

    std::time_t now = std::chrono::system_clock::to_time_t(timestamp);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&now), "%FT%TZ");
    
    // Print grid data
    for (const auto& kvp : adaptiveGridData) { // key-value pair

        const int& cellId = kvp.first;
        const AdaptiveGridDataPoint& cellData = kvp.second;

        std::cout << "Timestamp: " << ss.str() << " Cell ID(" << cellId << "): ";

        // Going through key-value pairs in the cell data
        for (const auto& kvp : cellData.agentTypeCount) {
            
            // Print agent type and count
            const std::string& agentType = kvp.first;
            int count = kvp.second;
            std::cout << agentType << ": " << count << ", ";
        }
        std::cout << std::endl;
        std::cout << "Total agents: " << cellData.totalAgents << std::endl;
        std::cout << "------------------------" << std::endl;
    }
    adaptiveGridData.clear();
}

// Clear the database
void AdaptiveGridBasedSensor::clearDatabase() {

    // Clear the collection
    collection.delete_many({});
}