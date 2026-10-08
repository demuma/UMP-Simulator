// #include "../include/Visualizer.hpp"
// #include "../include/Logging.hpp"
// #include "../include/Utilities.hpp"

// using bsoncxx::builder::basic::kvp;
// using bsoncxx::builder::basic::make_array;
// using bsoncxx::builder::basic::make_document;

// Visualizer::Visualizer() 
// :   gridLinesVertexArray(sf::PrimitiveType::Lines)
// {
//     loadConfiguration();
//     loadSensorAttributes();
//     loadAgentsAttributes();
//     initializeDatabase();
//     initializeWindow();
//     getMetadata();
//     getData();
// }

// Visualizer::~Visualizer() {

// }

// void Visualizer::loadConfiguration() {

//     // Load the configuration file
//     config = YAML::LoadFile("config.yaml");

//     // Load window parameters
//     windowSize.x = config["display"]["width"].as<int>(); // Pixels
//     windowSize.y = config["display"]["height"].as<int>(); // Pixels
//     scale = config["display"]["pixels_per_meter"].as<float>();

//     // Load simulation parameters
//     simulationSize.x = windowSize.x / scale;
//     simulationSize.y = windowSize.y / scale;

//     // Scale
//     simulationSize.x *= scale;
//     simulationSize.y *= scale;

//     // Calculate the offset
//     offset = sf::Vector2f((windowSize.x - simulationSize.x) / 2, (windowSize.y - simulationSize.y) / 2); // Pixels
    
//     // Load database parameters
//     std::string dbHost = config["database"]["host"].as<std::string>();
//     int dbPort = config["database"]["port"].as<int>();
//     databaseName = config["database"]["db_name"].as<std::string>();
//     dbUri = "mongodb://" + dbHost + ":" + std::to_string(dbPort);
//     collectionName = config["database"]["collection_name"].as<std::string>();

//     // Visualization parameters
//     showGrids = config["renderer"]["show_grids"].as<bool>();

//     // Video parameters
//     makeVideo = config["renderer"]["make_video"].as<bool>();
// }

// void Visualizer::loadAgentsAttributes() {

//     // Extract agent attributes
//     if (config["agents"] && config["agents"]["road_user_taxonomy"]) {
//         for (const auto& agent : config["agents"]["road_user_taxonomy"]) {
//             std::string type = agent["type"].as<std::string>();
//             Agent::AgentTypeAttributes attributes;

//             attributes.color = agent["color"].as<std::string>();
//             attributes.priority = agent["priority"].as<int>();

//             // Store in map
//             agentTypeAttributes[type] = attributes;

//             // Add to allAgentTypes
//             allAgentTypes.push_back(type);
//         }
//     }

//     // Initialize ghostCellAgentCounts with zero counts for all agent types
//     for (const auto& agentType : allAgentTypes) {
//         ghostCellAgentCounts[agentType] = 0;
//     }
// }

// void Visualizer::initializeDatabase() {

//     mongocxx::uri uri(dbUri);
//     client = std::make_shared<mongocxx::client>(uri);
//     db = (*client)[databaseName];
//     collection = db[collectionName];
// }

// // Initialize the window
// void Visualizer::initializeWindow() {

//     // Turn on antialiasing
//     sf::ContextSettings settings;
//     settings.antiAliasingLevel = 16;

//     // Create window
//     window.create(sf::VideoMode({static_cast<unsigned int>(windowSize.x), static_cast<unsigned int>(windowSize.y)}), "Urban Data Visualizer", sf::Style::Default, sf::State::Windowed, settings);
//     window.setVerticalSyncEnabled(true);
    
//     // Initialize the render texture
//     settings.antiAliasingLevel = 4;
//     if (!renderTexture.resize({static_cast<unsigned int>(windowSize.x), static_cast<unsigned int>(windowSize.y)}, settings)) {
//         std::cerr << "Error: Could not create render texture." << std::endl;
//         exit(EXIT_FAILURE);
//     }
// }

// void Visualizer::loadSensorAttributes() {

//     // Extract sensor attributes
//     if (config["sensors"]) {
//         for (const auto& sensorConfig : config["sensors"]) {
//             std::string type = sensorConfig["type"].as<std::string>();
//             Sensor sensor;
//             sensor.frameRate = sensorConfig["frame_rate"].as<float>();
//             sensor.color = stringToColor(sensorConfig["color"].as<std::string>());
//             sensor.alpha = sensorConfig["alpha"].as<float>() * 256;
//             sensor.databaseName = sensorConfig["database"]["db_name"].as<std::string>();
//             sensor.collectionName = sensorConfig["database"]["collection_name"].as<std::string>();

//             if(sensorConfig["adaptive-grid-based"] || sensorConfig["grid-based"]) {
//                 sensor.showGrid = sensorConfig["grid"]["show_grid"].as<bool>();
//             }

//             sensorTypeAttributes[type] = sensor;
//         }
//     }
// }

// // Get metadata from database
// void Visualizer::getMetadata() {

//     // auto collection = (*client)[databaseName]["AB_Sensor_Data"]; 

//     // Get sensor data
//     auto metadataCursor = collection.find_one(make_document(kvp("data_type", "metadata")));
//     if (!metadataCursor) {
//         std::cerr << "Error: Metadata not found." << std::endl;
//         return; 
//     }

//     DEBUG_MSG("Metadata: " << bsoncxx::to_json(*metadataCursor));

//     // Extract metadata (adjust based on your actual metadata structure)
//     bsoncxx::document::view document = metadataCursor->view();
//     // float detectionWidth = document["detection_area"]["width"].get_double().value * scale;
//     // float detectionHeight = document["detection_area"]["height"].get_double().value * scale;
//     frameRate = document["frame_rate"].get_double().value;
//     sf::Vector2f detectionArea = {
//         static_cast<float>(document["detection_area"]["width"].get_double().value * scale), 
//         static_cast<float>(document["detection_area"]["height"].get_double().value * scale)
//     };
//     sf::Vector2f position = {
//         static_cast<float>(document["position"]["x"].get_double().value * scale), 
//         static_cast<float>(document["position"]["y"].get_double().value * scale)
//     };

//     if(std::string(document["sensor_type"].get_string().value.data()) == "agent-based") {

//         Sensor sensor;
//         sensor.sensorID = std::string(document["sensor_id"].get_string().value.data());
//         sensor.type = std::string(document["sensor_type"].get_string().value.data());
//         sensor.frameRate = document["frame_rate"].get_double().value;
//         sensor.color = stringToColor("Magenta");
//         sensor.detectionArea = sf::FloatRect(position, detectionArea);
//         sensor.alpha = 80;

//         sensors.push_back(sensor);
//     }
//     else if(std::string(document["sensor_type"].get_string().value.data()) == "grid-based") {

//         Sensor sensor;
//         sensor.sensorID = std::string(document["sensor_id"].get_string().value.data());
//         sensor.type = std::string(document["sensor_type"].get_string().value.data());
//         sensor.frameRate = document["frame_rate"].get_double().value;
//         sensor.color = sensorTypeAttributes[sensor.type].color;
//         sensor.detectionArea = sf::FloatRect(position, detectionArea);
//         sensor.alpha = sensorTypeAttributes[sensor.type].alpha;
//         sensor.cellSize = document["cell_size"].get_double().value * scale;;

//         sensors.push_back(sensor);
//     }
//     else if(std::string(document["sensor_type"].get_string().value.data()) == "adaptive-grid-based") {

//         Sensor sensor;
//         sensor.sensorID = std::string(document["sensor_id"].get_string().value.data());
//         sensor.type = std::string(document["sensor_type"].get_string().value.data());
//         sensor.frameRate = document["frame_rate"].get_double().value;
//         sensor.color = sensorTypeAttributes[sensor.type].color;
//         sensor.detectionArea = sf::FloatRect(position, detectionArea);
//         sensor.alpha = sensorTypeAttributes[sensor.type].alpha;
//         sensor.cellSize = document["cell_size"].get_double().value * scale;;

//         sensors.push_back(sensor);
//     }
//     else {
//         std::cerr << "Error: Invalid sensor type." << std::endl;
//     }
// }

// void Visualizer::getData() {

//     mongocxx::pipeline pipeline;

//     // Filter out metadata entries
//     pipeline.match(make_document(kvp("data_type", "adaptive grid data")));

//     // Group by timestamp and collect grid cells in an array
//     pipeline.group(make_document(
//         kvp("_id", "$timestamp"),
//         kvp("grid_cells", make_document(kvp("$push", "$$ROOT")))
//     ));

//     // Sort the results in ascending order of timestamp
//     pipeline.sort(make_document(kvp("_id", 1)));

//     // Execute the aggregation and catch any exceptions
//     mongocxx::cursor cursor = collection.find({}, {});
//     try {
//         cursor = collection.aggregate(pipeline);
//     } catch (const mongocxx::exception& e) {
//         std::cerr << "Error: " << e.what() << std::endl;
//         return;
//     }

//     // Iterate over the documents
//     for (auto&& doc : cursor) {
//         // Access the timestamp field (referenced by "_id")
//         bsoncxx::types::b_date timestamp = doc["_id"].get_date();

//         // Access the 'grid_cells' array
//         bsoncxx::array::view gridCellsArray = doc["grid_cells"].get_array().value;

//         // Clear the current grid data
//         currentGridData.clear();

//         // Iterate over the grid cells array
//         for (auto&& gridCellDoc : gridCellsArray) {
//             // Get the grid cell document
//             auto gridCellView = gridCellDoc.get_document().value;

//             // Extract the cell_index as document
//             auto cellIndexView = gridCellView["cell_index"].get_document().value;
//             int x = cellIndexView["x"].get_int32();
//             int y = cellIndexView["y"].get_int32();
//             sf::Vector2i cellIndex(x, y);

//             // Extract the agent_type_count
//             auto agentTypeCountArray = gridCellView["agent_type_count"].get_array().value;
//             std::unordered_map<std::string, int> agentCounts;

//             for (auto&& agentTypeCountDoc : agentTypeCountArray) {
//                 auto agentTypeCountView = agentTypeCountDoc.get_document().value;
//                 // std::string type = agentTypeCountView["type"].get_string().value.to_string();
//                 std::string type = std::string(agentTypeCountView["type"].get_string().value.data());
//                 int count = agentTypeCountView["count"].get_int32();
//                 agentCounts[type] = count;
//             }

//             // Store in currentGridData
//             currentGridData[cellIndex] = agentCounts;
//         }

//         // Store currentGridData in frameStorage
//         frameStorage.push(currentGridData);
//     }

//     // Save the number of frames
//     numFrames = frameStorage.size();
// }

// void Visualizer::update() {
//     // Get the current grid data
//     if (!frameStorage.empty()) {
//         currentGridData = frameStorage.front();
//         frameStorage.pop();

//     } else {
//         std::cerr << "No more frames to process." << std::endl;
//     }
// }

// // Main rendering function (using rendering texture instead of window)
// void Visualizer::render() {
//     // Clear the window
//     renderTexture.clear(sf::Color::White);

//     // Clear vertex arrays if any
//     gridLinesVertexArray.clear();

//     // Iterate over all sensors
//     for (const auto& sensor : sensors) {
//         if (sensor.type != "adaptive-grid-based") continue;

//         // Draw sensor detection area first
//         sf::RectangleShape detectionArea(sf::Vector2f(sensor.detectionArea.size.x, sensor.detectionArea.size.y));
//         detectionArea.setPosition({sensor.detectionArea.position.x + offset.x, sensor.detectionArea.position.y + offset.y});
//         detectionArea.setFillColor(sf::Color(sensor.color.r, sensor.color.g, sensor.color.b, sensor.alpha));
//         detectionArea.setOutlineColor(sf::Color(220, 220, 220));
//         detectionArea.setOutlineThickness(1);
//         renderTexture.draw(detectionArea);

//         // Use sensor.cellSize for calculations
//         float cellSize = sensor.cellSize;

//         // Calculate grid dimensions
//         int gridWidth = static_cast<int>(std::ceil(sensor.detectionArea.size.x / cellSize));
//         int gridHeight = static_cast<int>(std::ceil(sensor.detectionArea.size.y / cellSize));

//         // Draw grid lines within detection area (optional)
//         if (showGrids) {
//             for (int x = 0; x <= gridWidth; ++x) {
//                 float posX = sensor.detectionArea.position.x + x * cellSize + offset.x;
//                 sf::Vertex line[] = {
//                     sf::Vertex({sf::Vector2f(posX, sensor.detectionArea.position.y + offset.y), sf::Color(220, 220, 220)}),
//                     sf::Vertex({sf::Vector2f(posX, sensor.detectionArea.position.y + sensor.detectionArea.size.y + offset.y), sf::Color(220, 220, 220)})
//                 };
//                 gridLinesVertexArray.append(line[0]);
//                 gridLinesVertexArray.append(line[1]);
//             }

//             for (int y = 0; y <= gridHeight; ++y) {
//                 float posY = sensor.detectionArea.position.y + y * cellSize + offset.y;
//                 sf::Vertex line[] = {
//                     sf::Vertex({sf::Vector2f(sensor.detectionArea.position.x + offset.x, posY), sf::Color(220, 220, 220)}),
//                     sf::Vertex({sf::Vector2f(sensor.detectionArea.position.x + sensor.detectionArea.size.x + offset.x, posY), sf::Color(220, 220, 220)})
//                 };
//                 gridLinesVertexArray.append(line[0]);
//                 gridLinesVertexArray.append(line[1]);
//             }

//             renderTexture.draw(gridLinesVertexArray);
//         }

//         // Iterate over cells within detection area
//         for (int x = 0; x < gridWidth; ++x) {
//             for (int y = 0; y < gridHeight; ++y) {
//                 sf::Vector2i cellIndex(x, y);

//                 // Get agent counts for this cell
//                 auto cellIt = currentGridData.find(cellIndex);
//                 std::unordered_map<std::string, int> agentCounts;
//                 if (cellIt != currentGridData.end()) {
//                     agentCounts = cellIt->second;
//                 } else {
//                     agentCounts = ghostCellAgentCounts; // Use ghost cell
//                 }

//                 // Calculate total agents in this cell
//                 int totalAgents = 0;
//                 for (const auto& agentType : allAgentTypes) {
//                     totalAgents += agentCounts[agentType];
//                 }

//                 // Skip empty cells
//                 if (totalAgents == 0) {
//                     continue;
//                 }

//                 // Collect agent types with non-zero counts
//                 std::vector<std::pair<std::string, int>> classCounts;
//                 for (const auto& [agentType, count] : agentCounts) {
//                     if (count > 0) {
//                         classCounts.emplace_back(agentType, count);
//                     }
//                 }

//                 // Sort classes by count in descending order, then by priority
//                 std::sort(classCounts.begin(), classCounts.end(), [this](const auto& a, const auto& b) {
//                     if (a.second != b.second) {
//                         // Sort by count in descending order
//                         return a.second > b.second;
//                     } else {
//                         // Counts are equal, sort by priority in descending order
//                         int priorityA = agentTypeAttributes[a.first].priority;
//                         int priorityB = agentTypeAttributes[b.first].priority;
//                         return priorityA > priorityB;
//                     }
//                 });

//                 // Determine subgrid division
//                 int numClasses = static_cast<int>(classCounts.size());
//                 int subgridRows = 2;
//                 int subgridCols = 2;

//                 if (numClasses > 4) {
//                     subgridRows = 3;
//                     subgridCols = 3;
//                 }

//                 // Function to get subgrid positions
//                 auto getSubgridPosition = [&](int index) -> sf::Vector2f {
//                     int col = index % subgridCols;
//                     int row = index / subgridCols;
//                     float subgridWidth = cellSize / subgridCols;
//                     float subgridHeight = cellSize / subgridRows;
//                     float posX = sensor.detectionArea.position.x + x * cellSize + col * subgridWidth + offset.x;
//                     float posY = sensor.detectionArea.position.y + y * cellSize + row * subgridHeight + offset.y;
//                     return sf::Vector2f(posX, posY);
//                 };

//                 // Get the largest class count for scaling
//                 int maxClassCount = classCounts[0].second;

//                 // Loop over classes and draw circles
//                 for (size_t i = 0; i < classCounts.size(); ++i) {
//                     if (i >= static_cast<size_t>(subgridRows * subgridCols)) {
//                         // Limit to available subgrids
//                         break;
//                     }

//                     const auto& [agentType, count] = classCounts[i];

//                     // Get the subgrid position
//                     sf::Vector2f subgridPos = getSubgridPosition(static_cast<int>(i));

//                     // Calculate subgrid dimensions
//                     float subgridWidth = cellSize / subgridCols;
//                     float subgridHeight = cellSize / subgridRows;

//                     // Calculate circle radius
//                     float margin = 5.0f; // Adjust margin as needed
//                     float maxCircleRadius = (std::min(subgridWidth, subgridHeight) - 2 * margin) / 2.0f;

//                     // Scaling factor relative to the largest class
//                     float scalingFactor = static_cast<float>(count) / maxClassCount;

//                     // Circle radius
//                     float circleRadius = maxCircleRadius * scalingFactor;

//                     // Center of the circle within the subgrid
//                     sf::Vector2f circleCenter = subgridPos + sf::Vector2f(subgridWidth / 2.0f, subgridHeight / 2.0f);

//                     // Draw the circle
//                     sf::CircleShape circle(circleRadius);
//                     circle.setFillColor(stringToColor(agentTypeAttributes[agentType].color));
//                     circle.setPosition(circleCenter - sf::Vector2f(circleRadius, circleRadius));
//                     circle.setOutlineThickness(1);
//                     circle.setOutlineColor(sf::Color::Black);

//                     renderTexture.draw(circle);
//                 }
//             }
//         }
//     }

//     // Draw the simulation boundary
//     sf::RectangleShape canvas(sf::Vector2f(simulationSize.x, simulationSize.y));
//     canvas.setOutlineThickness(3);
//     canvas.setOutlineColor(sf::Color::Black);
//     canvas.setFillColor(sf::Color::Transparent);
//     canvas.setPosition(offset);
//     renderTexture.draw(canvas);

//     // Display the window
//     renderTexture.display();
//     sf::Sprite sprite(renderTexture.getTexture());
//     window.clear();
//     window.draw(sprite);
//     window.display();
// }

// void Visualizer::handleEvents(){

//     // Lambda to handle window close events.
//     const auto onClose = [this](const sf::Event::Closed&) {
//         window.close();
//     };

//     // Lambda to handle key pressed events.
//     const auto onKeyPressed = [this](const sf::Event::KeyPressed& keyPressed) {
//         // Toggle pause with Space.
//         if (keyPressed.scancode == sf::Keyboard::Scancode::Space) {
//             paused = !paused;
//         }
//         else if (keyPressed.scancode == sf::Keyboard::Scancode::Q)
//         window.close();

//         else if (keyPressed.scancode == sf::Keyboard::Scancode::Escape) 
//         window.close();
//     };

//     window.handleEvents(onClose,
//                         onKeyPressed);
// }

// void Visualizer::captureFrame(int frameNumber) {
//     // Capture the rendered texture to an image
//     sf::Image screenshot = renderTexture.getTexture().copyToImage();

//     // Generate a filename with leading zeros for proper sorting
//     const std::string framesDir = "frames";
//     std::ostringstream filename;
//     filename << framesDir << "/frame_" << std::setw(8) << std::setfill('0') << frameNumber << ".png";

//     // Save the screenshot to a file
//     if (!screenshot.saveToFile(filename.str())) {
//         std::cerr << "Failed to save screenshot " << filename.str() << std::endl;
//     }
// }

// void Visualizer::createVideoFromFrames(int totalFrames) {

//     // Build the FFmpeg command
//     std::string command = "ffmpeg -y -framerate " + std::to_string(frameRate) + " -i frames/frame_%08d.png -c:v libx264 -pix_fmt yuv420p gbs_data_video.mp4";
//     // std::string command = "ffmpeg -y -framerate " + std::to_string(frameRate) + 
//     //                   " -i frames/frame_%08d.png -c:v libx264 -pix_fmt yuv420p "
//     //                   "-preset veryslow -crf 18 -b:v 5M gt_data_video.mp4";

//     // Call the command
//     int result = std::system(command.c_str());

//     if (result != 0) {
//         std::cerr << "FFmpeg command failed with code " << result << std::endl;
//     } else {
//         std::cout << "Video created successfully." << std::endl;
//     }
// }

// void Visualizer::cleanupFrames(int totalFrames) {
//     for (int i = 0; i < totalFrames; ++i) {
//         std::ostringstream filename;
//         std::string framesDir = "frames/";
//         filename << framesDir << "frame_" << std::setw(8) << std::setfill('0') << i << ".png";

//         if (std::remove(filename.str().c_str()) != 0) {
//             std::cerr << "Error deleting file " << filename.str() << std::endl;
//         }
//     }
// }

// void Visualizer::run() {

//     // Create chrono high quality timer
//     std::chrono::high_resolution_clock timer;
//     std::chrono::time_point start = timer.now();
//     // std::chrono::duration<float> timeStep(1.0f / sensors[0].frameRate);
//     std::chrono::duration<float> timeStep(1.0f / frameRate);
//     std::chrono::duration<float> totalFrameTime(0.0f);
//     int frameNumber = 0;
    
//     while (window.isOpen() && !frameStorage.empty()) {

//         // Start timer
//         auto startTime = timer.now();

//         // Event handling
//         handleEvents();

//         if(!paused) {

//             // Update the window
//             update();

//             // Render the window
//             render();

//             // Capture frame
//             if(makeVideo) {
//                 captureFrame(frameNumber);
//             }
//             auto preFrameTime = timer.now() - startTime;

//             // Increment frame number
//             frameNumber++;

//             // Calculate remaining sleep time to meet the target frame rate
//             auto remainingTime = std::max(std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::duration<float>(0)), std::chrono::duration_cast<std::chrono::milliseconds>(timeStep) - std::chrono::duration_cast<std::chrono::milliseconds>(preFrameTime));
//             std::this_thread::sleep_for(remainingTime);
//             auto frameTime = timer.now() - startTime;
//             totalFrameTime += std::chrono::duration<float>(frameTime);
//         }
//     }
    
//     if(makeVideo) {
//         // After capturing all frames, call FFmpeg
//         createVideoFromFrames(frameNumber);
        
//         // Clean up frame images
//         cleanupFrames(frameNumber);
//     }
    
//     // Calculate the average frame time
//     STATS_MSG("Average frame time: " << totalFrameTime.count() / numFrames << " seconds for " << numFrames << " frames");
// }

#include "../include/Visualizer.hpp"
#include "../include/Logging.hpp"
#include "../include/Utilities.hpp"

#include <iomanip> // For std::setw, std::setfill

using bsoncxx::builder::basic::kvp;
using bsoncxx::builder::basic::make_array;
using bsoncxx::builder::basic::make_document;

Visualizer::Visualizer()
{
    // Note: Quadtree is initialized in getMetadata after we have sensor info
    loadConfiguration();
    loadSensorAttributes();
    loadAgentsAttributes();
    initializeDatabase();
    initializeWindow();
    getMetadata(); // This will now create the Quadtree object
    getData();

    // Load a font for the quadtree to use (even if text is disabled)
    if (!font.openFromFile("/Library/Fonts/Arial Unicode.ttf")) { // Make sure 'arial.ttf' is in your project directory
        std::cerr << "Error: Could not load font 'arial.ttf'." << std::endl;
        exit(EXIT_FAILURE);
    }
}

Visualizer::~Visualizer() {
}

void Visualizer::loadConfiguration() {
    config = YAML::LoadFile("config.yaml");
    windowSize.x = config["display"]["width"].as<int>();
    windowSize.y = config["display"]["height"].as<int>();
    scale = config["display"]["pixels_per_meter"].as<float>();
    title = config["display"]["title"].as<std::string>();

    simulationSize.x = windowSize.x / scale;
    simulationSize.y = windowSize.y / scale;
    simulationSize.x *= scale;
    simulationSize.y *= scale;
    offset = sf::Vector2f((windowSize.x - simulationSize.x) / 2, (windowSize.y - simulationSize.y) / 2);
    std::string dbHost = config["database"]["host"].as<std::string>();
    int dbPort = config["database"]["port"].as<int>();
    databaseName = config["database"]["db_name"].as<std::string>();
    dbUri = "mongodb://" + dbHost + ":" + std::to_string(dbPort);
    collectionName = config["database"]["collection_name"].as<std::string>();
    showGrids = config["renderer"]["show_grids"].as<bool>();
    makeVideo = config["renderer"]["make_video"].as<bool>();
    showText = config["renderer"]["show_text"].as<bool>();
}

void Visualizer::loadAgentsAttributes() {
    if (config["agents"] && config["agents"]["road_user_taxonomy"]) {
        for (const auto& agent : config["agents"]["road_user_taxonomy"]) {
            std::string type = agent["type"].as<std::string>();
            Agent::AgentTypeAttributes attributes;
            attributes.color = agent["color"].as<std::string>();
            attributes.priority = agent["priority"].as<int>();
            agentTypeAttributes[type] = attributes;
            allAgentTypes.push_back(type);
        }
    }
}

void Visualizer::initializeDatabase() {
    mongocxx::uri uri(dbUri);
    client = std::make_shared<mongocxx::client>(uri);
    db = (*client)[databaseName];
    collection = db[collectionName];
}

void Visualizer::initializeWindow() {
    sf::ContextSettings settings;
    settings.antiAliasingLevel = 16;
    window.create(sf::VideoMode({static_cast<unsigned int>(windowSize.x), static_cast<unsigned int>(windowSize.y)}), title, sf::Style::Default, sf::State::Windowed, settings);
    window.setVerticalSyncEnabled(true);
    
    settings.antiAliasingLevel = 4;
    if (!renderTexture.resize({static_cast<unsigned int>(windowSize.x), static_cast<unsigned int>(windowSize.y)}, settings)) {
        std::cerr << "Error: Could not create render texture." << std::endl;
        exit(EXIT_FAILURE);
    }
}

void Visualizer::loadSensorAttributes() {
    // This function can remain as-is from your original file
    if (config["sensors"]) {
        for (const auto& sensorConfig : config["sensors"]) {
            std::string type = sensorConfig["type"].as<std::string>();
            Sensor sensor;
            sensor.frameRate = sensorConfig["frame_rate"].as<float>();
            sensor.color = stringToColor(sensorConfig["color"].as<std::string>());
            sensor.alpha = sensorConfig["alpha"].as<float>() * 255;
            sensorTypeAttributes[type] = sensor;
        }
    }
}

void Visualizer::getMetadata() {
    auto metadataCursor = collection.find_one(make_document(kvp("data_type", "metadata")));
    if (!metadataCursor) {
        std::cerr << "Error: Metadata not found." << std::endl;
        return; 
    }

    bsoncxx::document::view document = metadataCursor->view();
    frameRate = document["frame_rate"].get_double().value;
    sf::Vector2f detectionArea = {
        static_cast<float>(document["detection_area"]["width"].get_double().value), 
        static_cast<float>(document["detection_area"]["height"].get_double().value)
    };
    sf::Vector2f position = {
        static_cast<float>(document["position"]["x"].get_double().value), 
        static_cast<float>(document["position"]["y"].get_double().value)
    };

    std::string sensorType = std::string(document["sensor_type"].get_string().value.data());
    if (sensorType != "adaptive-grid-based") {
        std::cerr << "Error: This visualizer is configured for 'adaptive-grid-based' sensors only." << std::endl;
        exit(EXIT_FAILURE);
    }
    
    Sensor sensor;
    sensor.sensorID = std::string(document["sensor_id"].get_string().value.data());
    sensor.type = sensorType;
    sensor.frameRate = frameRate;
    sensor.detectionArea = sf::FloatRect(position * scale, detectionArea * scale);
    sensor.color = sensorTypeAttributes[sensor.type].color;
    sensor.alpha = sensorTypeAttributes[sensor.type].alpha;
    sensor.cellSize = document["cell_size"].get_double().value; // Base cell size in meters

    sensors.push_back(sensor);

    // IMPORTANT: Initialize the Quadtree object using metadata
    // The quadtree operates in simulation coordinates (meters), not pixels.
    maxDepth = document["max_depth"].get_int32();
    quadtree = std::make_unique<Quadtree>(position.x, position.y, sensor.cellSize, maxDepth);
}

void Visualizer::getData() {
    mongocxx::pipeline pipeline;
    pipeline.match(make_document(kvp("data_type", "adaptive grid data")));
    pipeline.group(make_document(
        kvp("_id", "$timestamp"),
        kvp("grid_cells", make_document(kvp("$push", "$$ROOT")))
    ));
    pipeline.sort(make_document(kvp("_id", 1)));

    // mongocxx::cursor cursor = collection.aggregate(pipeline);
    // Execute the aggregation and catch any exceptions
    mongocxx::cursor cursor = collection.find({}, {});
    try {
        cursor = collection.aggregate(pipeline);
    } catch (const mongocxx::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return;
    }

    for (auto&& doc : cursor) {
        std::unordered_map<int, AdaptiveCellData> frameData;
        bsoncxx::array::view gridCellsArray = doc["grid_cells"].get_array().value;

        for (auto&& gridCellDoc : gridCellsArray) {
            auto gridCellView = gridCellDoc.get_document().value;
            int cellId = gridCellView["cell_id"].get_int32();
            
            AdaptiveCellData cell;
            cell.size = gridCellView["cell_size"].get_double().value * scale;
            auto posView = gridCellView["cell_position"].get_document().value;
            cell.position = sf::Vector2f(
                posView["x"].get_double().value * scale,
                posView["y"].get_double().value * scale
            );

            auto agentTypeCountArray = gridCellView["agent_type_count"].get_array().value;
            std::unordered_map<std::string, int> agentCounts;
            for (auto&& agentTypeCountDoc : agentTypeCountArray) {
                auto agentTypeCountView = agentTypeCountDoc.get_document().value;
                std::string type = std::string(agentTypeCountView["type"].get_string().value.data());
                int count = agentTypeCountView["count"].get_int32();
                agentCounts[type] = count;
            }
            cell.agentCounts = agentCounts;
            frameData[cellId] = cell;
        }
        frameStorage.push(frameData);
    }
    numFrames = frameStorage.size();
}

void Visualizer::update() {
    if (!frameStorage.empty()) {
        currentFrameData = frameStorage.front();
        frameStorage.pop();
    } else {
        std::cout << "No more frames to process." << std::endl;
        // Optionally close window here or let the run loop handle it
        // window.close(); 
    }
}

void Visualizer::render() {
    renderTexture.clear(sf::Color::White);
    sf::Color gridColor = sf::Color::White;

    if (sensors.empty() || !quadtree) {
        return; // Nothing to render yet
    }

    const auto& sensor = sensors[0];

    // 1. Draw sensor detection area background
    sf::RectangleShape detectionArea(sf::Vector2f(sensor.detectionArea.size.x, sensor.detectionArea.size.y));
    detectionArea.setPosition({sensor.detectionArea.position.x + offset.x, sensor.detectionArea.position.y + offset.y});
    detectionArea.setFillColor(sf::Color(sensor.color.r, sensor.color.g, sensor.color.b, sensor.alpha));
    detectionArea.setOutlineColor(sf::Color::Black);
    detectionArea.setOutlineThickness(1);
    renderTexture.draw(detectionArea);

    // 2. Reconstruct and draw the full quadtree grid structure
    if (showGrids) {
        quadtree->reset(); // Clear previous frame's structure
        std::unordered_set<int> cellIds;
        for(const auto& pair : currentFrameData) {
            cellIds.insert(pair.first);
        }

        // Use the Quadtree class to build the grid structure from leaf IDs
        quadtree->splitFromCellIds(cellIds);
        quadtree->showCellId = showText;
        quadtree->draw(renderTexture, font, scale, offset);
        
        // The Quadtree's own draw function renders all parent/child lines
        // quadtree->draw(renderTexture, font, scale, offset);
    }

    // 3. Draw the agents (circles) inside the leaf cells
    for (const auto& [cellId, cellData] : currentFrameData) {
        // Calculate total agents in this cell
        int totalAgents = 0;
        for (const auto& pair : cellData.agentCounts) {
            totalAgents += pair.second;
        }
        if (totalAgents == 0) continue;

        // --- Agent drawing logic (adapted from your original code) ---
        std::vector<std::pair<std::string, int>> classCounts;
        for (const auto& [agentType, count] : cellData.agentCounts) {
            if (count > 0) classCounts.emplace_back(agentType, count);
        }

        std::sort(classCounts.begin(), classCounts.end(), [this](const auto& a, const auto& b) {
            if (a.second != b.second) return a.second > b.second;
            return agentTypeAttributes[a.first].priority > agentTypeAttributes[b.first].priority;
        });
        
        // int numClasses = static_cast<int>(classCounts.size());
        // int subgridRows = (numClasses > 4) ? 3 : 2;
        // int subgridCols = (numClasses > 4) ? 3 : 2;
        // if(numClasses == 1) { subgridRows=1; subgridCols=1; }
        // else if (numClasses == 2) { subgridRows=1; subgridCols=2; }

        // Determine subgrid division
        int numClasses = static_cast<int>(classCounts.size());
        int subgridRows = 2;
        int subgridCols = 2;

        if (numClasses > 4) {
            subgridRows = 3;
            subgridCols = 3;
        }

        int maxClassCount = classCounts[0].second;

        for (size_t i = 0; i < classCounts.size(); ++i) {
            if (i >= static_cast<size_t>(subgridRows * subgridCols)) break;

            const auto& [agentType, count] = classCounts[i];
            
            int col = i % subgridCols;
            int row = i / subgridCols;
            float subgridWidth = cellData.size / subgridCols;
            float subgridHeight = cellData.size / subgridRows;

            float margin = 2.0f; 
            float maxCircleRadius = (std::min(subgridWidth, subgridHeight) - 2 * margin) / 2.0f;
            float scalingFactor = static_cast<float>(count) / maxClassCount;
            float circleRadius = std::max(1.0f, maxCircleRadius * scalingFactor);

            sf::Vector2f subgridPos = {
                cellData.position.x + col * subgridWidth + offset.x,
                cellData.position.y + row * subgridHeight + offset.y
            };
            sf::Vector2f circleCenter = subgridPos + sf::Vector2f(subgridWidth / 2.0f, subgridHeight / 2.0f);

            sf::CircleShape circle(circleRadius);
            circle.setFillColor(stringToColor(agentTypeAttributes[agentType].color));
            circle.setPosition(circleCenter - sf::Vector2f(circleRadius, circleRadius));
            circle.setOutlineThickness(1);
            circle.setOutlineColor(sf::Color::Black);

            renderTexture.draw(circle);
        }
    }

    renderTexture.display();
    sf::Sprite sprite(renderTexture.getTexture());
    window.clear();
    window.draw(sprite);
    window.display();
}


// --- UNCHANGED HELPER FUNCTIONS ---
// The following functions can remain exactly as they were in your original file.

void Visualizer::handleEvents(){

    // Lambda to handle window close events.
    const auto onClose = [this](const sf::Event::Closed&) {
        window.close();
    };

    // Lambda to handle key pressed events.
    const auto onKeyPressed = [this](const sf::Event::KeyPressed& keyPressed) {
        // Toggle pause with Space.
        if (keyPressed.scancode == sf::Keyboard::Scancode::Space) {
            paused = !paused;
        }
        else if (keyPressed.scancode == sf::Keyboard::Scancode::Q)
        window.close();

        else if (keyPressed.scancode == sf::Keyboard::Scancode::Escape) 
        window.close();
    };

    window.handleEvents(onClose,
                        onKeyPressed);
}

void Visualizer::captureFrame(int frameNumber) {
    sf::Image screenshot = renderTexture.getTexture().copyToImage();
    const std::string framesDir = "frames";
    std::ostringstream filename;
    filename << framesDir << "/frame_" << std::setw(8) << std::setfill('0') << frameNumber << ".png";
    if (!screenshot.saveToFile(filename.str())) {
        std::cerr << "Failed to save screenshot " << filename.str() << std::endl;
    }
}

void Visualizer::createVideoFromFrames(int totalFrames) {
    std::string command = "ffmpeg -y -framerate " + std::to_string(static_cast<int>(frameRate)) + " -i frames/frame_%08d.png -c:v libx264 -pix_fmt yuv420p adaptive_data_video.mp4";
    int result = std::system(command.c_str());
    if (result != 0) {
        std::cerr << "FFmpeg command failed with code " << result << std::endl;
    } else {
        std::cout << "Video created successfully." << std::endl;
    }
}

void Visualizer::cleanupFrames(int totalFrames) {
    for (int i = 0; i < totalFrames; ++i) {
        std::ostringstream filename;
        std::string framesDir = "frames/";
        filename << framesDir << "frame_" << std::setw(8) << std::setfill('0') << i << ".png";
        if (std::remove(filename.str().c_str()) != 0) {
            // It's okay to fail if file doesn't exist, so we don't need to print an error
        }
    }
}

void Visualizer::run() {
    std::chrono::high_resolution_clock timer;
    std::chrono::duration<float> timeStep(1.0f / frameRate);
    int frameNumber = 0;
    
    while (window.isOpen() && !frameStorage.empty()) {
        auto startTime = timer.now();
        handleEvents();

        if(!paused) {
            update();
            render();

            if(makeVideo) {
                captureFrame(frameNumber);
            }
            frameNumber++;
        }

        auto frameTime = timer.now() - startTime;
        if(frameTime < timeStep) {
            std::this_thread::sleep_for(timeStep - frameTime);
        }
    }
    
    if(makeVideo && frameNumber > 0) {
        createVideoFromFrames(frameNumber);
        cleanupFrames(frameNumber);
    }
}