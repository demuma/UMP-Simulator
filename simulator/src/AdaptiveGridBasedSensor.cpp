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
    std::string id
) : Sensor(frameRate, detectionArea, client, std::move(id)),
    cellSize(cellSize), // Half the longest side of the detection area
    maxDepth(maxDepth),
    db(client->database(databaseName)),
    collection(db[collectionName]),
    adaptiveGrid(detectionArea.position.x, detectionArea.position.y, cellSize, maxDepth)
{
    this->detectionArea = detectionArea;
}

// Alternative constructor for rendering
AdaptiveGridBasedSensor::AdaptiveGridBasedSensor(
    sf::FloatRect detectionArea, 
    sf::Color detectionAreaColor, 
    float cellSize, 
    int maxDepth,
    bool showGrid
)
    : Sensor(detectionArea, detectionAreaColor),
    cellSize(cellSize), 
    adaptiveGrid(detectionArea.position.x, detectionArea.position.y, cellSize, maxDepth), maxDepth(maxDepth)
    {
        this->detectionArea = detectionArea;
        this->detectionAreaColor = detectionAreaColor;
        this->showGrid = showGrid;
    }

void AdaptiveGridBasedSensor::enableAggregation(ump::AggregationConfig config, float simulationStep,
    std::chrono::system_clock::time_point origin, AggregationManager::Sink sink) {
    if (samplingInitialized || aggregationManager)
        throw std::logic_error("Enable AGBS aggregation once, before the first update");
    const double stepMs = simulationStep * 1000.0;
    const double periodMs = 1000.0 / frameRate;
    if (!std::isfinite(stepMs) || !std::isfinite(periodMs) || stepMs < 1 || periodMs < 1
        || std::abs(stepMs - std::round(stepMs)) > 1e-4
        || std::abs(periodMs - std::round(periodMs)) > 1e-4
        || std::llround(periodMs) % std::llround(stepMs) != 0
        || config.samplingPeriodMs != std::llround(periodMs))
        throw std::invalid_argument("AGBS aggregation requires whole-millisecond periods aligned to simulation ticks");
    if (detectionArea.size.x != 2 * cellSize || detectionArea.size.y != 2 * cellSize
        || maxDepth < 1 || maxDepth > 14)
        throw std::invalid_argument("AGBS aggregation requires a square full-quadtree extent and depth 1..14");
    const auto& grid = config.coverage;
    if (config.sensorId != sensorId || grid.x != detectionArea.position.x || grid.y != detectionArea.position.y
        || grid.width != detectionArea.size.x || grid.height != detectionArea.size.y || grid.leafDepth != maxDepth)
        throw std::invalid_argument("AGBS aggregation configuration must match this sensor's identity and coverage");
    auto manager = std::make_unique<AggregationManager>(config, std::move(sink));
    aggregationRunId = config.runId;
    aggregationOrigin = origin;
    aggregationManager = std::move(manager);
}

void AdaptiveGridBasedSensor::finishAggregation(std::chrono::system_clock::time_point end) {
    if (aggregationManager)
        aggregationManager->finish(std::chrono::duration_cast<std::chrono::milliseconds>(end - aggregationOrigin).count());
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
    pendingSample.reset();

    // // Get the current timestamp as a string
    // auto currentTime = timestamp;

    const auto observedAtMs = aggregationManager
        ? std::chrono::duration_cast<std::chrono::milliseconds>(timestamp - aggregationOrigin).count() : 0;
    // No-sample ticks still close elapsed fixed windows.
    if (aggregationManager) aggregationManager->advance(observedAtMs);

    // The shared gate handles initialization and resets the timer even for empty areas.
    if (isSamplingDue(timeStep)) {
        std::optional<ump::ObservationBatch> batch;
        if (aggregationManager) {
            batch.emplace(ump::ObservationBatch{aggregationRunId, sensorId, ++aggregationSequence,
                observedAtMs, ump::ObservationStatus::Measured, {}});
        }

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

            if (batch) batch->observations.reserve(adaptiveGrid.agents.size());
            // Generate split sequence
            adaptiveGrid.splitFromPositions();
            
            for (Agent* agentPtr : adaptiveGrid.agents) {
                Agent& agent = *agentPtr;
                
                // Add the agent to the adaptive grid
                int cellId = adaptiveGrid.addAgent(&agent);
                
                // Cell IDs and counts are exported together after capture.
                
                // Increment the count of the agent type and total agents in the cell
                adaptiveGridData[cellId].agentTypeCount[agent.type]++;
                adaptiveGridData[cellId].totalAgents++;
                if (batch) {
                    const auto* node = adaptiveGrid.getNodeById(cellId);
                    if (!node) throw std::logic_error("AGBS observation has no quadtree cell");
                    const auto& bounds = node->bounds;
                    batch->observations.push_back({agent.agentId, agent.type,
                        {cellId, node->depth, bounds.position.x, bounds.position.y, bounds.size.x, bounds.size.y}});
                }
            }
            
            // Push timestamped adaptive grid data to the data storage
            dataStorage.push_back({this->timestamp, adaptiveGridData});
        }
        if (batch) aggregationManager->ingest(*batch); // Also ingest a measured-empty area.
        pendingSample = AdaptiveGridSensorSample{adaptiveGridData};
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
