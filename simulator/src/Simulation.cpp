#include "../include/Simulation.hpp"
#include "../include/CollisionGrid.hpp"
#include "../include/AgentBasedSensor.hpp"
#include "../include/GridBasedSensor.hpp"
#include "../include/AdaptiveGridBasedSensor.hpp"
#include "../include/Region.hpp"
#include "../include/AggregationDiagnostics.hpp"
#include "../include/PolicyConfiguration.hpp"
#include "../include/AggregationConfiguration.hpp"
#include <limits>
#include <algorithm>
#include <cctype>
#include "PublicationCoordinator.hpp"
#include "PublicationStore.hpp"
#include "AdaptiveAggregation.hpp"
#include "CellLocalAggregation.hpp"
#include <mongocxx/exception/exception.hpp>

// Simulation constructor
Simulation::Simulation(
    SharedBuffer<agentBufferFrameType>& agentBuffer,
    SharedBuffer<sensorBufferFrameType>& sensorBuffer,
    const YAML::Node& config)
: agentBuffer(agentBuffer), sensorBuffer(sensorBuffer), config(config), collisionGrid(0, sf::FloatRect({0.0f, 0.0f}, {0.0f, 0.0f})), instance {} {
    
    // Set the initial write agentBuffer (second queue agentBuffer) -> TODO: Make SharedBuffer class and move this logic there
    DEBUG_MSG("Simulation: " << agentBuffer.name << " write buffer " << agentBuffer.writeBufferIndex);
    DEBUG_MSG("Simulation: " << sensorBuffer.name << " write buffer " << sensorBuffer.writeBufferIndex);
    loadConfiguration();
    loadAgentsAttributes();
    loadRegionsAttributes();
    initializeRegions();
    initializeMetricPolicies(); // Validate/compile before initializing any database sink.
    loadObstacles();
    initializeDatabase();
    initializeGrid();
    initializeAgents();
    initializeSensors();
}

Simulation::~Simulation() {
    
    // Clean up resources
    sensors.clear();
    obstacles.clear();
    regions.clear();
    agents.clear();
    collisionGrid.clear();
    documentBuffer.clear();
    agentTypeAttributes.clear();
    regionTypeAttributes.clear();
}

void Simulation::loadConfiguration() {

    // Load simulation parameters
    timeStep = config["simulation"]["time_step"].as<float>();
    if (!std::isfinite(timeStep) || timeStep <= 0)
        throw std::invalid_argument("simulation.time_step must be positive and finite");

    // Set the maximum number of frames if the duration is specified
    if(config["simulation"]["duration_seconds"]) {
        maxFrames = config["simulation"]["duration_seconds"].as<int>() / timeStep;
        targetSimulationTime = config["simulation"]["duration_seconds"].as<int>();
    } else {
        maxFrames = config["simulation"]["maximum_frames"].as<int>();
        targetSimulationTime = maxFrames * timeStep;
    }

    // Window scaling parameters
    scale = config["display"]["pixels_per_meter"].as<float>();
    simulationWidth = config["simulation"]["width"].as<int>(); // Pixels
    simulationHeight = config["simulation"]["height"].as<int>(); // Pixels

    // Agent parameters
    waypointDistance = config["agents"]["waypoint_distance"].as<float>();
    numAgents = config["agents"]["num_agents"].as<int>();

    // Load number of threads -> TODO: Use this to initialize the thread pool (path finding)
    // if(config["simulation"]["num_threads"].as<int>()) {
    //     numThreads = config["simulation"]["num_threads"].as<int>();
    // } else {
    //     numThreads = std::thread::hardware_concurrency();
    // }

    // If datetime is provided in the configuration, use it, otherwise use the current time
    if(config["simulation"]["datetime"]) {

        // Set time from configuration
        datetime = config["simulation"]["datetime"].as<std::string>();
    } else {

        // Set current time
        datetime = generateISOTimestamp();
    }

    // Set simulation timestamp
    timestamp = generateISOTimestamp(simulationTime, datetime);

    // Collision
    collisionGridCellSize = config["collision"]["grid"]["cell_size"].as<float>();

    // Scenario
    if(config["simulation"]["scenario"]) {
        scenario = config["simulation"]["scenario"].as<std::string>();
    } 
    else {
        scenario = "default";
    }
}

void Simulation::loadAgentsAttributes() {

    // Extract agent attributes per type
    if (config["agents"] && config["agents"]["road_user_taxonomy"]) {
        for (const auto& agentType : config["agents"]["road_user_taxonomy"]) {
            std::string type = agentType["type"].as<std::string>();
            Agent::AgentTypeAttributes attributes;

            attributes.probability = agentType["probability"].as<double>();
            attributes.priority = agentType["priority"].as<int>();
            attributes.bodyRadius = agentType["radius"].as<double>();
            attributes.color = agentType["color"].as<std::string>();

            attributes.velocity.min = agentType["velocity"]["min"].as<double>();
            attributes.velocity.max = agentType["velocity"]["max"].as<double>();
            attributes.velocity.mu = agentType["velocity"]["mu"].as<double>();
            attributes.velocity.sigma = agentType["velocity"]["sigma"].as<double>();
            attributes.velocity.noiseScale = agentType["velocity"]["noise_scale"].as<double>();
            attributes.velocity.noiseFactor = agentType["velocity"]["noise_factor"].as<double>();

            attributes.acceleration.min = agentType["acceleration"]["min"].as<double>();
            attributes.acceleration.max = agentType["acceleration"]["max"].as<double>();

            attributes.lookAheadTime = agentType["look_ahead_time"].as<double>();

            // Store in map
            agentTypeAttributes[type] = attributes;
        }

        // Set the number of agent types
        numAgentTypes = agentTypeAttributes.size();
    }
}

void Simulation::loadRegionsAttributes() {

    // Extract region atributes per type
    if (config["region_taxonomy"]) {
        for (const auto& regionType : config["region_taxonomy"]) {
            if (regionType["execution"]) throw std::invalid_argument("Regional execution strategies are not supported");
            Region::RegionTypeAttributes attributes;
            std::string type = regionType["type"].as<std::string>();
            if (type.empty() || regionTypeAttributes.count(type))
                throw std::invalid_argument("Region types must be nonempty and unique: " + type);
            attributes.metricRequirements = readMetricRequirements(regionType["metric_requirements"], true);

            // General attributes
            attributes.color = regionType["color"].as<std::string>();
            attributes.alpha = regionType["alpha"].as<float>();
            // Granularities
            attributes.granularities.spatial.min = regionType["granularities"]["spatial"]["min"].as<float>();
            attributes.granularities.spatial.max = regionType["granularities"]["spatial"]["max"].as<float>();
            attributes.granularities.temporal.min = regionType["granularities"]["temporal"]["min"].as<float>();
            attributes.granularities.temporal.max = regionType["granularities"]["temporal"]["max"].as<float>();
            // Privacy
            attributes.privacy.k_anonymity.min = regionType["privacy"]["k_anonymity"]["min"].as<int>();
            attributes.privacy.l_diversity.min = regionType["privacy"]["l_diversity"]["min"].as<int>();

            // Store in map
            regionTypeAttributes[type] = attributes;
        }

        // Set the number of agent types
        numRegionTypes = regionTypeAttributes.size();
    }
}

// Function to initialize the grid based on the YAML configuration
void Simulation::initializeGrid() {

    // Initialize the grid
    // collisionGrid = Grid(collisionGridCellSize, simulationWidth / collisionGridCellSize, simulationHeight / collisionGridCellSize);
    collisionGrid = Grid(collisionGridCellSize, sf::FloatRect({0.0f, 0.0f}, {simulationWidth, simulationHeight}));
}

// Function to load obstacles from the YAML configuration file
void Simulation::loadObstacles() {

    // Check if the 'obstacles' key exists and is a sequence
    if (config["obstacles"] && config["obstacles"].IsSequence()) {
        for (const auto& obstacleNode : config["obstacles"]) {
            std::string type = obstacleNode["type"] && obstacleNode["type"].IsScalar()
                ? obstacleNode["type"].as<std::string>()
                : "unknown";

            if (type == "rectangle") { // Only handle rectangles
                std::vector<float> position = obstacleNode["position"].as<std::vector<float>>();
                std::vector<float> size = obstacleNode["size"].as<std::vector<float>>();
                obstacles.push_back(Obstacle(
                    sf::FloatRect({position[0], position[1]}, {size[0], size[1]}), 
                    stringToColor(obstacleNode["color"].as<std::string>())
                ));
            } else {
                ERROR_MSG("Error: Unknown obstacle type '" << type << "' in config file.");
            }
        }
    } else {
        ERROR_MSG("Error: Could not find 'obstacles' key in config file or it is not a sequence.");
    }
}

void Simulation::initializeAgents() {

    // Initialize agents based on the scenario
    if (scenario == "random") {

        for (int i = 0; i < numAgents; ++i) {

            std::random_device rd;
            std::mt19937 gen(rd());

            std::uniform_real_distribution<> disPosX(0, simulationWidth);
            std::uniform_real_distribution<> disPosY(0, simulationHeight);

            Agent agent(agentTypeAttributes["Adult Cyclist"]);

            agent.agentId = generateUUID();
            agent.sensorId = "0";
            agent.type = "Adult Cyclist";
            agent.color = stringToColor(agent.attributes.color);
            agent.priority = agent.attributes.priority;
            agent.bodyRadius = agent.attributes.bodyRadius;
            agent.lookAheadTime = agent.attributes.lookAheadTime;

            agent.setBufferZoneSize();
            agent.initialPosition = sf::Vector2f(disPosX(gen), disPosY(gen));
            agent.targetPosition = sf::Vector2f(disPosX(gen), disPosY(gen));
            agent.position = agent.initialPosition;
            agent.waypointDistance = waypointDistance; // -> TODO: Use taxonomy for waypoint distance
            // agent.waypointColor = sf::Color::Red;
            agent.calculateTrajectory(agent.waypointDistance);
            agent.timestamp = timestamp; // Use simulation timestamp from initialization

            agent.velocityMagnitude = generateRandomNumberFromTND(
                agent.attributes.velocity.mu, agent.attributes.velocity.sigma, 
                agent.attributes.velocity.min, agent.attributes.velocity.max
            );
            agent.calculateVelocity(agent.trajectory[1]);
            agent.initialVelocity = agent.velocity;

            agents.push_back(agent);
        }
    }
    else if(scenario == "crossing") {

    }
    else if(scenario == "continuous") {

    }
    // Default scenario
    else {
        // Check if sum of probabilities is 1
        double sum = 0;
        for (const auto& agentType : agentTypeAttributes) {
            sum += agentType.second.probability;
        }
        if (std::abs(sum - 1) > tolerance) {
            ERROR_MSG("Error: Sum of agent probabilities is not equal to 1, but " << (float)sum);
            exit(EXIT_FAILURE);
        }

        // Generate agents based on the probabilities from agent taxonomy
        for (const auto& agentType : agentTypeAttributes) {

            // Calculate the number of agents of each type
            int numAgentsPerType = numAgents * agentType.second.probability;
            int currentNumAgents = 0;
            
            for (int i = 0; i < numAgentsPerType; ++i) {
                
                // Generate random positions
                std::random_device rd;
                std::mt19937 gen(rd());
                std::uniform_real_distribution<> disPosX(0, simulationWidth);
                std::uniform_real_distribution<> disPosY(0, simulationHeight);
                
                Agent agent(agentType.second); // Initialize agent with attributes: map(type as string, AgentTypeAttributes)
                
                agent.agentId = generateUUID();
                agent.sensorId = "0";
                agent.type = agentType.first;
                agent.color = stringToColor(agentType.second.color);
                agent.priority = agentType.second.priority;
                agent.bodyRadius = agentType.second.bodyRadius;
                agent.lookAheadTime = agentType.second.lookAheadTime;

                agent.setBufferZoneSize();
                agent.initialPosition = sf::Vector2f(disPosX(gen), disPosY(gen));
                agent.targetPosition = sf::Vector2f(disPosX(gen), disPosY(gen));
                agent.position = agent.initialPosition;
                agent.waypointDistance = waypointDistance; // -> TODO: Use taxonomy for waypoint distance
                // agent.waypointColor = sf::Color::Red;
                agent.calculateTrajectory(agent.waypointDistance);
                agent.timestamp = timestamp; // Use simulation timestamp from initialization

                agent.velocityMagnitude = generateRandomNumberFromTND(
                    agentType.second.velocity.mu, agentType.second.velocity.sigma, 
                    agentType.second.velocity.min, agentType.second.velocity.max
                );

                agent.calculateVelocity(agent.trajectory[1]);
                agent.initialVelocity = agent.velocity;
                agents.push_back(agent);

                // Increment the number of agents
                currentNumAgents++;
            }

            DEBUG_MSG("Number of agents per type " << agentType.first << ": " << currentNumAgents << " in " << agentType.second.color);
        }
        DEBUG_MSG("Total number of agents: " << agents.size());
    }    
}

void Simulation::initializeRegions() {

    // Load regions from the configuration file
    if(config["regions"]) {
        if (!config["regions"].IsSequence()) throw std::invalid_argument("regions must be a sequence");
        std::unordered_set<std::string> ids;
        for (const auto& regionType: config["regions"]) {
            if (regionType["execution"]) throw std::invalid_argument("Regional execution strategies are not supported");
            const auto type = regionType["type"].as<std::string>();
            const auto attributes = regionTypeAttributes.find(type);
            if (attributes == regionTypeAttributes.end()) throw std::invalid_argument("Unknown region type: " + type);
            Region region(attributes->second);
            region.type = type;
            region.id = regionType["id"].as<std::string>("region-" + std::to_string(regions.size()));
            if (region.id.empty() || !ids.insert(region.id).second)
                throw std::invalid_argument("Region IDs must be nonempty and unique: " + region.id);
            region.metricRequirements = readMetricRequirements(regionType["metric_requirements"], true);
            sf::FloatRect area(
                {regionType["area"]["x"].as<float>(), regionType["area"]["y"].as<float>()},
                {regionType["area"]["width"].as<float>(), regionType["area"]["height"].as<float>()}
            );
            if (!std::isfinite(area.position.x) || !std::isfinite(area.position.y)
                || !std::isfinite(area.size.x) || !std::isfinite(area.size.y)
                || area.size.x <= 0 || area.size.y <= 0
                || !std::isfinite(area.position.x + area.size.x) || !std::isfinite(area.position.y + area.size.y))
                throw std::invalid_argument("Region geometry must be finite with positive dimensions: " + region.id);
            region.area = area;
            region.colorAlpha = sf::Color(
                stringToColor(region.attributes.color).r,
                stringToColor(region.attributes.color).g,
                stringToColor(region.attributes.color).b,
                region.attributes.alpha  * 255
            );

            // Create the region and add to regions vector
            regions.push_back(region);
            DEBUG_MSG("New " << region.type << " region created at (" << region.area.position.x << ", " << region.area.position.y << ") with area (" << region.area.size.x << ", " << region.area.size.y << ")");
        }
    }
}

// Compile each enabled stream's immutable policy view without DB or sensor instances.
void Simulation::initializeMetricPolicies() {
    std::vector<std::string> rawDatabases{config["database"]["db_name"].as<std::string>()};
    for (const auto& sensor : config["sensors"])
        rawDatabases.push_back(sensor["database"]["db_name"].as<std::string>());
    std::vector<PublicationConfiguration> publicationDestinations;
    std::unordered_set<std::string> streamIds;
    for (const auto& sensor : config["sensors"]) {
        const auto aggregation = sensor["aggregation"];
        if (!aggregation || !aggregation["enabled"].as<bool>(false)) continue;
        if (sensor["type"].as<std::string>() != "adaptive-grid-based")
            throw std::invalid_argument("Aggregation/policy integration currently requires an AGBS stream");
        const auto id = sensor["id"].as<std::string>();
        if (!streamIds.insert(id).second) throw std::invalid_argument("Duplicate aggregation sensor ID");
        const auto area = sensor["detection_area"];
        const ump::GridCoverage coverage{area["x"].as<float>(), area["y"].as<float>(),
            area["width"].as<float>(), area["height"].as<float>(), sensor["grid"]["max_depth"].as<int>()};
        const auto applicationId = aggregation["application_id"].as<std::string>("fixed-baseline");
        if (aggregation["diagnostics_directory"].as<std::string>("results/aggregation").empty())
            throw std::invalid_argument("Aggregation diagnostics_directory must not be empty");
        const double rate = sensor["frame_rate"].as<double>();
        if (!std::isfinite(rate) || rate <= 0 || 1000.0 / rate < 1
            || 1000.0 / rate >= static_cast<double>(std::numeric_limits<ump::AggregationTime>::max()))
            throw std::invalid_argument("Aggregation requires a representable positive sensor period");
        const auto period = static_cast<ump::AggregationTime>(std::llround(1000.0 / sensor["frame_rate"].as<float>()));
        const auto budget = aggregation["max_observations_per_window"].as<std::int64_t>(1000000);
        if (budget <= 0) throw std::invalid_argument("Aggregation observation budget must be positive");
        ump::AggregationConfig settings{aggregationRunId, id, applicationId, coverage, period,
            aggregation["window_ms"].as<ump::AggregationTime>(), static_cast<std::uint64_t>(budget)};
        settings.history = readHistoryLimits(aggregation["history"]);
        settings.semanticTaxonomy = readSemanticTaxonomy(aggregation);
        AdaptiveGridBasedSensor::validateAggregationConfig(settings, timeStep,
            sensor["frame_rate"].as<float>(),
            sf::FloatRect({area["x"].as<float>(), area["y"].as<float>()},
                {area["width"].as<float>(), area["height"].as<float>()}),
            sensor["grid"]["cell_size"].as<float>(), coverage.leafDepth);
        AggregationManager checked(settings, [](const auto&) {});
        const auto spatial = readSpatialSelection(aggregation, coverage.leafDepth);
        auto evaluator = makeMetricEvaluator(aggregation, coverage, applicationId, regions, settings.semanticTaxonomy);
        const auto temporal = readTemporalAdaptation(aggregation);
        if (spatial) { ump::SpatialSelector checkedSelector(settings, *spatial); }
        if (temporal) {
            if (temporal->coordination == ump::CoordinationMode::CellLocal) {
                ump::CellLocalAggregation checkedAdaptive(settings, *temporal, *spatial, evaluator,
                    [](const auto&) {}, temporal->maxActiveCells);
            } else { ump::AdaptiveAggregation checkedAdaptive(settings, *temporal, *spatial,
                evaluator, [](const auto&) {}); }
        }
        if (const auto publication = readPublicationConfiguration(aggregation)) {
            validatePublicationDestinations(*publication, rawDatabases);
            ump::PublicationStoreOptions options{publication->database, publication->collection,
                publication->journalDatabase, publication->journalCollection, publication->maxDocumentBytes};
            options.validate();
            ump::PublicationCoordinator checkedPublication(settings, evaluator, {},
                temporal ? std::optional<ump::AggregationTime>{temporal->maxWindowMs} : std::nullopt,
                temporal && temporal->coordination == ump::CoordinationMode::CellLocal);
            publicationDestinations.push_back(*publication);
        }
        metricEvaluators.emplace(id, std::move(evaluator));
    }
    const auto folded = [](std::string name) {
        std::transform(name.begin(), name.end(), name.begin(), [](unsigned char c) { return std::tolower(c); });
        return name;
    };
    // No private journal may share another stream's recipient database.
    for (const auto& a : publicationDestinations)
        for (const auto& b : publicationDestinations)
            if (folded(a.database) == folded(b.journalDatabase))
                throw std::invalid_argument("Recipient database overlaps another stream's private journal");
}

// Initialize the database connection
void Simulation::initializeDatabase() {

    // Load the database configuration
    std::string dbHost = config["database"]["host"].as<std::string>();
    int dbPort = config["database"]["port"].as<int>();
    databaseName = config["database"]["db_name"].as<std::string>();
    collectionName = config["database"]["collection_name"].as<std::string>();
    dbUri = "mongodb://" + dbHost + ":" + std::to_string(dbPort);
    clearDatabase = config["database"]["clear_database"].as<bool>();

    // MongoDB URI
    mongocxx::uri uri(dbUri);

    // Initialize the MongoDB client
    client = std::make_shared<mongocxx::client>(uri);
    mongocxx::database db = (*client)[databaseName];
    collection = db[collectionName];

    // Clear the database if specified
    if(clearDatabase) {
        collection.delete_many({});
    }

    // Post metadata to the database
    postMetadata();
}

// Initialize sensors with YAML configuration
void Simulation::initializeSensors() {

    // Load sensors from the configuration file
    const YAML::Node& sensorNodes = config["sensors"];

    // Iterate over each sensor node in the configuration
    for (const auto& sensorNode : sensorNodes) {

        // Get the sensor type and frame rate
        std::string type = sensorNode["type"].as<std::string>();
        float frameRate = sensorNode["frame_rate"].as<float>();
        sf::Color color = stringToColor(sensorNode["detection_area"]["color"].as<std::string>());
        int alpha = sensorNode["detection_area"]["alpha"].as<float>() * 255;
        sf::Color colorAlpha = sf::Color(color.r, color.g, color.b, alpha);
        std::string databaseName = sensorNode["database"]["db_name"].as<std::string>();
        std::string collectionName = sensorNode["database"]["collection_name"].as<std::string>();

        // Define the detection area for the sensor
        sf::FloatRect detectionArea(
            {sensorNode["detection_area"]["x"].as<float>(), sensorNode["detection_area"]["y"].as<float>()},
            {sensorNode["detection_area"]["width"].as<float>(), sensorNode["detection_area"]["height"].as<float>()}
        );

        // Create the agent-based sensor
        if (type == "agent-based") {
            
            // Create the agent-based sensor and add to sensors vector
            sensors.push_back(std::make_unique<AgentBasedSensor>(frameRate, detectionArea, databaseName, collectionName, client, sensorNode["id"].as<std::string>()));
            sensors.back()->scale = scale;
            sensors.back()->timestamp = timestamp;

            // Clear the database if specified
            if(clearDatabase) {
                sensors.back()->clearDatabase();
            }

            // Post metadata to the database
            sensors.back()->postMetadata();

            // ABS retains its initial observations during its first update.
        }

        // Create the grid-based sensor
        else if (type == "grid-based") {

            float cellSize = sensorNode["grid"]["cell_size"].as<float>();
            bool showGrid = sensorNode["grid"]["show_grid"].as<bool>();

            // Create the grid-based sensor and add to sensors vector
            sensors.push_back(std::make_unique<GridBasedSensor>(frameRate, detectionArea, cellSize, databaseName, collectionName, client, sensorNode["id"].as<std::string>()));
            sensors.back()->scale = scale;
            sensors.back()->timestamp = timestamp;

            // Clear the database if specified
            if(clearDatabase) {
                sensors.back()->clearDatabase();
            }

            // Post metadata to the database
            sensors.back()->postMetadata();
        }

        // Create the grid-based sensor
        else if (type == "adaptive-grid-based") {

            float cellSize = sensorNode["grid"]["cell_size"].as<float>();
            bool showGrid = sensorNode["grid"]["show_grid"].as<bool>();
            int maxDepth = sensorNode["grid"]["max_depth"].as<int>();

            // Create the grid-based sensor and add to sensors vector
            auto sensor = std::make_unique<AdaptiveGridBasedSensor>(frameRate, detectionArea, cellSize,
                maxDepth, databaseName, collectionName, client, sensorNode["id"].as<std::string>());
            const auto aggregation = sensorNode["aggregation"];
            if (aggregation && aggregation["enabled"].as<bool>(false)) {
                if (!std::isfinite(frameRate) || frameRate <= 0)
                    throw std::invalid_argument("Aggregation requires a positive finite sensor frame rate");
                const auto budget = aggregation["max_observations_per_window"].as<std::int64_t>(1000000);
                if (budget <= 0) throw std::invalid_argument("Aggregation observation budget must be positive");
                ump::AggregationConfig settings{aggregationRunId, sensor->sensorId,
                    aggregation["application_id"].as<std::string>("fixed-baseline"),
                    {detectionArea.position.x, detectionArea.position.y, detectionArea.size.x, detectionArea.size.y, maxDepth},
                    static_cast<ump::AggregationTime>(std::llround(1000.0 / frameRate)),
                    aggregation["window_ms"].as<ump::AggregationTime>(), static_cast<std::uint64_t>(budget)};
                settings.history = readHistoryLimits(aggregation["history"]);
                auto evaluator = std::move(metricEvaluators.at(sensor->sensorId));
                settings.semanticTaxonomy = evaluator.semanticTaxonomy();
                auto diagnostics = makeAggregationDiagnosticsSink(
                    aggregation["diagnostics_directory"].as<std::string>("results/aggregation"), timestamp);
                const auto spatialSettings = readSpatialSelection(aggregation, maxDepth);
                const auto temporalSettings = readTemporalAdaptation(aggregation);
                const auto publicationSettings = readPublicationConfiguration(aggregation);
                const bool showProgress = config["renderer"]["show_renderer"].as<bool>();
                std::shared_ptr<ump::SpatialSelector> selector;
                std::shared_ptr<ump::AdaptiveAggregation> adaptive;
                std::shared_ptr<ump::CellLocalAggregation> local;
                const bool localMode = temporalSettings && temporalSettings->coordination == ump::CoordinationMode::CellLocal;
                auto* sensorInstance = sensor.get();
                if (spatialSettings) {
                    auto spatialDiagnostics = makeSpatialDiagnosticsSink(
                        aggregation["diagnostics_directory"].as<std::string>("results/aggregation"), timestamp);
                    std::shared_ptr<ump::PublicationCoordinator> coordinator;
                    std::shared_ptr<ump::PublicationStore> store;
                    std::size_t maxAttempts = 0;
                    if (publicationSettings) {
                        ump::PublicationLimits limits;
                        if (localMode) limits.maxCoordinationNodes = temporalSettings->maxActiveCells * 2;
                        coordinator = std::make_shared<ump::PublicationCoordinator>(settings, evaluator,
                            limits, temporalSettings
                                ? std::optional<ump::AggregationTime>{temporalSettings->maxWindowMs} : std::nullopt, localMode);
                        store = std::make_shared<ump::PublicationStore>(client,
                            ump::PublicationStoreOptions{publicationSettings->database, publicationSettings->collection,
                                publicationSettings->journalDatabase, publicationSettings->journalCollection,
                                publicationSettings->maxDocumentBytes});
                        maxAttempts = publicationSettings->maxAttempts;
                        std::cout << "Recipient releases: " << publicationSettings->database << '.'
                            << publicationSettings->collection << " (private journal: "
                            << publicationSettings->journalDatabase << ")\n";
                    }
                    auto terminal = [coordinator, store, maxAttempts, spatialDiagnostics, sensorInstance,
                        journalEmpty = !publicationSettings || publicationSettings->journalEmptyRetirements]
                        (const ump::SpatialSelection& selected) {
                        auto recorded = std::make_shared<ump::SpatialSelection>(selected);
                        if (coordinator) {
                            const auto now = sensorInstance->getAggregationManager()->history()->debugState().watermarkMs;
                            auto release = coordinator->pendingRelease();
                            if (release) {
                                // The controller retries its immutable selection before any later
                                // work. Resume the held reservation after a transient sink error.
                                const auto& c = selected.candidate;
                                if (release->runId != c.runId || release->sensorId != c.sensorId
                                    || release->applicationId != c.applicationId || release->startMs != c.startMs
                                    || release->endMs != c.endMs
                                    || bool(release->coordinationCell) != bool(selected.coordinationCell)
                                    || (release->coordinationCell && (release->coordinationCell->id != selected.coordinationCell->id
                                        || release->coordinationCell->depth != selected.coordinationCell->depth)))
                                    throw std::logic_error("Retry does not match the reserved local publication");
                            } else release = coordinator->seal(selected, now);
                            // Allocate diagnostic metadata before any possible recipient disclosure.
                            recorded->publicationState = release->cells.empty() ? "retired_without_release" : "committed";
                            recorded->releaseId = release->releaseId;
                            // No recipient payload exists for an empty/suppressed scope. Its
                            // optional private checkpoint is independent of durable disclosure.
                            bool delivered = false;
                            if (release->cells.empty() && !journalEmpty)
                                delivered = coordinator->deliver(now, [](const auto&) {
                                    throw std::logic_error("A no-output retirement invoked a recipient sink");
                                    return ump::SinkResult::Retry;
                                });
                            for (std::size_t attempt = 0; attempt < maxAttempts && !delivered; ++attempt) {
                                try {
                                    store->prepare(*release);
                                    // Empty intervals have no recipient record, but retire durably first.
                                    if (release->cells.empty()) store->commit(*release);
                                    delivered = coordinator->deliver(now, [store](const auto& payload) {
                                        const auto result = store->publish(payload);
                                        if (result == ump::SinkResult::Acknowledged) store->commit(payload);
                                        return result;
                                    });
                                } catch (const mongocxx::exception&) {
                                    if (attempt + 1 == maxAttempts) throw;
                                }
                            }
                            if (!delivered) throw std::runtime_error(
                                "Publication attempts exhausted; private journal and reservation remain pending");
                        }
                        try { spatialDiagnostics(*recorded); }
                        catch (const std::exception& error) {
                            if (!coordinator) throw;
                            // Diagnostic I/O cannot undo acknowledged output or block selector handover.
                            std::cerr << "Committed release retained; diagnostic write failed: " << error.what() << '\n';
                        }
                        sensorInstance->setAggregationDebug(std::move(recorded));
                    };
                    if (localMode)
                        local = std::make_shared<ump::CellLocalAggregation>(settings, *temporalSettings,
                            *spatialSettings, evaluator, terminal, temporalSettings->maxActiveCells);
                    else if (temporalSettings)
                        adaptive = std::make_shared<ump::AdaptiveAggregation>(settings, *temporalSettings,
                            *spatialSettings, evaluator, terminal);
                    else {
                        selector = std::make_shared<ump::SpatialSelector>(settings, *spatialSettings);
                        // The fixed callback below owns the terminal output operation.
                    }
                    sensor->enableAggregation(settings, timeStep, timestamp,
                        [evaluator, diagnostics, selector, terminal, sensorInstance](const auto& candidate) {
                            diagnostics(candidate, evaluator.evaluate(candidate, candidate.closedAtMs));
                            if (selector) {
                                const auto selected = selector->propose(candidate,
                                    *sensorInstance->getAggregationManager()->history(), evaluator);
                                terminal(selected);
                                selector->commit(selected);
                            }
                        });
                    if (local) sensor->setAggregationProgressSink(
                        [local, sensorInstance, showProgress](ump::AggregationTime now, bool finishing) {
                            const auto& history = *sensorInstance->getAggregationManager()->history();
                            if (finishing) local->finish(now, history);
                            else local->advance(now, history);
                            if (showProgress) sensorInstance->setAggregationProgress(
                                std::make_shared<const ump::AggregationProgress>(local->progressSnapshot()));
                        });
                    else if (adaptive) sensor->setAggregationProgressSink(
                        [adaptive, sensorInstance, showProgress](ump::AggregationTime now, bool finishing) {
                            const auto& history = *sensorInstance->getAggregationManager()->history();
                            if (finishing) adaptive->finish(now, history);
                            else adaptive->advance(now, history);
                            if (showProgress) sensorInstance->setAggregationProgress(
                                std::make_shared<const ump::AggregationProgress>(adaptive->progressSnapshot()));
                        });
                    else if (showProgress) sensor->setAggregationProgressSink(
                        [sensorInstance](ump::AggregationTime now, bool finishing) {
                            const auto state = sensorInstance->getAggregationManager()->debugState();
                            ump::AggregationProgress progress;
                            progress.strategy = "temporal_first_spatial_only";
                            progress.startMs = state.windowStartMs;
                            progress.nextEndMs = state.windowEndMs;
                            progress.hardDeadlineMs = state.windowEndMs;
                            progress.observedThroughMs = now;
                            progress.phase = finishing ? ump::AggregationProgressPhase::Finished
                                : ump::AggregationProgressPhase::Collecting;
                            sensorInstance->setAggregationProgress(
                                std::make_shared<const ump::AggregationProgress>(std::move(progress)));
                        });
                } else {
                    sensor->enableAggregation(settings, timeStep, timestamp,
                        [evaluator, diagnostics](const auto& candidate) {
                            diagnostics(candidate, evaluator.evaluate(candidate, candidate.closedAtMs));
                        });
                }
            }
            sensors.push_back(std::move(sensor));
            sensors.back()->scale = scale;
            sensors.back()->timestamp = timestamp;
            
            // Clear the database if specified
            if(clearDatabase) {
                sensors.back()->clearDatabase();
            }

            // Post metadata to the database
            sensors.back()->postMetadata();
        }
    }
}

// Run the simulation
void Simulation::run() {

    // Initialize the clock
    sf::Clock simulationClock;
    simulationClock.restart();

    // Initialize the simulation timers
    sf::Time writeBufferTime = sf::Time::Zero;
    sf::Time totalWriteBufferTime = sf::Time::Zero;
    sf::Time simulationUpdateTime = sf::Time::Zero;
    sf::Time simulationStepTime = sf::Time::Zero;

    simulationRealTime += simulationClock.getElapsedTime();

    const bool renderEnabled = config["renderer"]["show_renderer"].as<bool>();
    std::size_t completedSteps = 0;
    // Headless runs do not retain unused render queues.
    while ((maxFrames == 0 || completedSteps < maxFrames) && !agentBuffer.stop.load()) {

        // Restart the clock
        simulationClock.restart();
        
        // Write the agent current frame to the agent buffer
        agentBufferFrameType currentFramePtr;
        if (renderEnabled) currentFramePtr = std::make_shared<const agentFrameType>(timestamp, agents);
        
        // Update the agentBuffer write time
        writeBufferTime = simulationClock.getElapsedTime();
        totalWriteBufferTime += writeBufferTime;
        
        // Store current ground truth agent data in MongoDB
        postData(agents);

        // Increment the time step
        simulationTime += sf::seconds(timeStep);

        // Update the agents
        update();

        // Update timestamp
        timestamp = generateISOTimestamp(simulationTime, datetime);
        
        // Sensor updates and any measurement-frame writes for t are complete.
        // Receiving this agent frame confirms that no sensor contribution for t is still in flight.
        if (renderEnabled) {
            sensorBuffer.swap();
            agentBuffer.write(currentFramePtr);
            agentBuffer.swap();
        }
        ++completedSteps;
        
        // Update the simulation update time
        simulationUpdateTime += simulationClock.getElapsedTime() - writeBufferTime;
        
        // Calculate the time step for the simulation
        simulationStepTime = simulationClock.getElapsedTime();
        
        // Calculate the simulation time
        simulationRealTime += simulationStepTime;
    }

    // The last processed state precedes this exclusive end. Flush even a partial window.
    for (auto& sensor : sensors) {
        if (auto* adaptive = dynamic_cast<AdaptiveGridBasedSensor*>(sensor.get()))
            adaptive->finishAggregation(timestamp);
    }

    // Signalize the simulation has finished so that the renderer can swap buffers if needed
    // Normal completion drains pending frames; cancellation is signaled by requestStop().

    // End the simulation
    agentBuffer.end();
    sensorBuffer.end();
    
    DEBUG_MSG("Simulation: finished");

    // Print simulation statistics
    STATS_MSG("Total simulation wall time: " << simulationRealTime.asSeconds() << " seconds for " << completedSteps << " frames");
    STATS_MSG("Total simulation time: " << simulationTime.asSeconds() << " seconds" << " for " << numAgents << " agents");
    STATS_MSG("Simulation speedup: " << (maxFrames * timeStep) / simulationRealTime.asSeconds());
    STATS_MSG("Frame rate: " << 1/(simulationRealTime.asSeconds() / completedSteps));
    STATS_MSG("Average simulation update time: " << simulationUpdateTime.asSeconds() / completedSteps);
    STATS_MSG("Average simulation time step: " << simulationRealTime.asSeconds() / completedSteps);
    STATS_MSG("Average write buffer time: " << totalWriteBufferTime.asSeconds() / completedSteps);
}

void Simulation::update() {

    SensorFrameBuilder frame(timestamp);
    // Capture values while sensors remain independent. No sensor writes the render queue.
    for (auto& sensor : sensors) {

        // sensor->update(agents, timeStep, simulationTime, datetime);
        sensor->update(agents, timeStep, timestamp);
        if (auto sample = sensor->takeSample())
            frame.add(sensor->sensorId, sensor->timestamp, std::move(*sample));
        sensor->postData();
        // sensor->postAggregatedData();
    }
    // Send only actual measurements, including identified measured-empty payloads.
    // The agent frame published after update() confirms completion on no-sample steps.
    if (config["renderer"]["show_renderer"].as<bool>()) {
        if (auto measurements = std::move(frame).finish())
            sensorBuffer.write(measurements);
    }

    // Update timestamp
    timestamp = generateISOTimestamp(simulationTime, datetime);
    
    // Clear the grid
    collisionGrid.clear();

    // Loop through all agents and update their positions
    for(auto agent = agents.begin(); agent != agents.end();) {

         // Check if agent is out of bounds
        if (agent->position.x > simulationWidth + agent->bodyRadius || agent->position.x < -agent->bodyRadius ||
            agent->position.y > simulationHeight + agent->bodyRadius || agent->position.y < -agent->bodyRadius) {
            
            // Remove the agent from the vector and update the iterator
            agent = agents.erase(agent); // Increases agent iterator if erased
        } 
        else {

            // Assign the agent to the correct grid cell
            collisionGrid.addAgent(&(*agent));

            // Reset collision state at the start of each frame for each agent
            agent->resetCollisionState();
            
            // Update the agent position
            agent->updatePosition(timeStep);

            // Update the agent timestamp to new timestamp
            agent->timestamp = timestamp;

            // Only update velocity if the agent is not stopped
            if(!agent->stopped) {
                agent->updateVelocity(timeStep, simulationRealTime);
            }
            else {
                if(!agent->collisionPredicted) {
                    agent->resume(agents);
                // agent->updateVelocity(timeStep, simulationRealTime);
                }
            }
            ++agent;
        }
    }

    // Collision detection using grid
    collisionGrid.checkCollisions();
}

void Simulation::postMetadata() {

    // Get the current timestamp
    timestamp = generateISOTimestamp(simulationTime, datetime);

    // Prepare a BSON document for the metadata
    bsoncxx::builder::stream::document document{};

    bsoncxx::builder::stream::document simulationArea{};
    simulationArea << "width" << simulationWidth
                   << "height" << simulationHeight;

    // Append the metadata fields to the document
    document << "timestamp" << bsoncxx::types::b_date{timestamp}
             << "data_type" << "metadata"
             << "simulation_area" << simulationArea
             << "frame_rate" << 1/timeStep
             << "cell_size" << collisionGridCellSize;

    // Insert the metadata document into the collection
    try {
        collection.insert_one(document << bsoncxx::builder::stream::finalize);
    } catch (const mongocxx::exception& e) {
        // Handle errors
        std::cerr << "Error inserting metadata: " << e.what() << std::endl;
    }
}

// Store agent data in MongoDB
void Simulation::postData(const std::vector<Agent>& agents) {

    // Check if there are agents to store
    if (!agents.empty()) {
    
        // Prepare a vector of documents to insert in bulk
        std::vector<bsoncxx::document::value> documents;
        documents.reserve(agents.size());

        // Iterate over each agent and prepare a document for MongoDB
        for (const auto& agent : agents) {

            // Construct a BSON document for each agent
            bsoncxx::builder::stream::document document{},
                                               positionDocument{},
                                               velocityDocument{};

            // Prepare the position and estimated velocity documents
            positionDocument << "x" << agent.position.x
                             << "y" << agent.position.y;
                             
            velocityDocument << "x" << agent.velocity.x
                             << "y" << agent.velocity.y;

            // Append the agent data to the document
            document << "timestamp" << bsoncxx::types::b_date{timestamp}
                     << "data_type" << "agent data"
                     << "agent_id" << agent.agentId
                     << "type" << agent.type
                     << "position" << positionDocument
                     << "velocity" << velocityDocument;

            documents.push_back(document << bsoncxx::builder::stream::finalize);
        }

        // Insert the documents into MongoDB
        try {
            // Insert documents into MongoDB in bulk
            collection.insert_many(documents);
        } catch (const mongocxx::exception& e) {
            std::cerr << "An error occurred while inserting documents: " << e.what() << std::endl;
        }
    }
}
