#include "../include/AggregationManager.hpp"
#include "../include/Utilities.hpp"

AggregationManager::AggregationManager(
    mongocxx::collection& collection,
    const std::string& sensorId,
    std::chrono::system_clock::time_point& timestamp
) : 
    collection(collection), 
    sensorId(sensorId), 
    timestamp(timestamp) {
    // Constructor implementation
}
// 
AggregationManager::~AggregationManager() {
    // Destructor implementation
}

void AggregationManager::postDataTest() {
        
    bsoncxx::builder::stream::document document{};
    document << "timestamp" << bsoncxx::types::b_date{timestamp};

    try {
        collection.insert_one(document << bsoncxx::builder::stream::finalize);
    } catch (const mongocxx::exception& e) {
        // Handle errors
        std::cerr << "Error inserting metadata: " << e.what() << std::endl;
    }
}