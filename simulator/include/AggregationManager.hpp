#pragma once

#include <vector>
#include <unordered_map>
#include <yaml-cpp/yaml.h>
#include <chrono>
#include <string>
#include <set>
#include <iostream>
#include <mongocxx/client.hpp>
#include <mongocxx/database.hpp>
#include <mongocxx/collection.hpp>
#include <mongocxx/exception/exception.hpp>
#include <mongocxx/instance.hpp>
#include <mongocxx/uri.hpp>
#include <bsoncxx/builder/stream/document.hpp>
#include <bsoncxx/json.hpp>

#include "Agent.hpp"
#include "Utilities.hpp"
#include "Quadtree.hpp"

class AggregationManager {
public:
    AggregationManager(
        mongocxx::collection& collection, 
        const std::string& sensorId, 
        std::chrono::system_clock::time_point& timestamp
    );

    ~AggregationManager();

    struct AggregatedGridData {
        std::string sensorId;
        std::string dataType; // Aggregated adaptive grid data
        int cellId;
        std::string regionType;
        std::vector<int> cellPosition;
        std::unordered_map<std::string, int> agentTypeCount;
        int totalAgents;
        float privacyLevel;
        std::unordered_map<std::string, float> privacyMetrics; // Make privacy metrics struct
    };

    struct AggregatedGridDataBucket {
        int cellId;
        std::unordered_map<int, AggregatedGridData> aggregatedData;
        std::chrono::system_clock::time_point timestamp;  // For when data is sent
        std::chrono::system_clock::duration aggregationDuration; 
        std::chrono::system_clock::time_point aggregationStartTime;
        std::chrono::system_clock::time_point aggregationEndTime;

        AggregatedGridDataBucket(int cellId)
            : aggregationStartTime() {}

        void reset() {
            aggregatedData.clear();
        }

        void flush() {
            
        }
    };

    void postDataTest();

private:
    // sf::Time& simulationTime;
    // std::string datetime;
    std::chrono::system_clock::time_point& timestamp;
    mongocxx::collection& collection;
    std::string sensorId;
    std::unordered_map<int, AggregationManager::AggregatedGridDataBucket> aggregatedGridDataBuckets; // Grid Data: map(cell id, map(agent type, count)
};