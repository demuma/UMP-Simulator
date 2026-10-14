#include "../include/Renderer.hpp"
#include "../include/GridBasedSensor.hpp"
#include "../include/AgentBasedSensor.hpp"
#include "../include/AdaptiveGridBasedSensor.hpp"
#include "../include/AggregationPresentation.hpp"
#include <sstream>

// Renderer member functions
Renderer::Renderer(
    SharedBuffer<agentBufferFrameType>& agentBuffer,
    SharedBuffer<sensorBufferFrameType>& sensorBuffer,
    const YAML::Node& config)
:   agentBuffer(agentBuffer), sensorBuffer(sensorBuffer),
    config(config), // Reserve VRAM for the vertex arrays depending on the number of agents
    bufferZonesVertexArray(sf::PrimitiveType::Points), 
    agentBodyVertexArray(sf::PrimitiveType::Triangles, 6), // Note: SFML 2.6.2 or prior -> (Quads, 4)
    agentArrowHeadVertexArray(sf::PrimitiveType::Triangles, 3), 
    agentArrowBodyVertexArray(sf::PrimitiveType::Lines, 2),
    font(), frameText(font,"", 20), frameRateText(font, "", 24), agentCountText(font, "",  24), timeText(font, "", 24), 
    playbackSpeedText(font, "", 24), pauseButton(), pauseButtonText(font, "", 20), resetButton(), resetButtonText(font, "", 20) {

    DEBUG_MSG("Renderer: " << agentBuffer.name << " read buffer " << agentBuffer.currentReadFrameIndex);
    DEBUG_MSG("Renderer: " << sensorBuffer.name << " read buffer " << sensorBuffer.currentReadFrameIndex);

    loadConfiguration();
    loadObstacles();
    initializeSensors();
    initializeWindow();
    initializeGUI();
}

// Function to load the configuration parameters -> TODO: Add error handling
void Renderer::loadConfiguration() {

    // Window parameters
    title = config["display"]["title"].as<std::string>();
    windowWidth = config["display"]["width"].as<int>();
    windowHeight = config["display"]["height"].as<int>();
    scale = config["display"]["pixels_per_meter"].as<float>();
    initialScale = scale;
    simulationWidth = (config["simulation"]["width"].as<int>() * scale) ;
    simulationHeight = (config["simulation"]["height"].as<int>() * scale);
    initialSimulationWidth = simulationWidth;
    initialSimulationHeight = simulationHeight;
    offset = sf::Vector2f((windowWidth - simulationWidth) / 2, (windowHeight - simulationHeight) / 2);
    DEBUG_MSG("Offset: " << offset.x << ", " << offset.y);

    // Renderer parameters
    timeStep = config["simulation"]["time_step"].as<float>();
    playbackSpeed = config["simulation"]["playback_speed"].as<double>();
    playbackClock.emplace(timeStep, playbackSpeed);
    numAgents = config["agents"]["num_agents"].as<int>();
    currentNumAgents = numAgents;
    
    // Set the maximum number of frames if the duration is specified
    if(config["simulation"]["duration_seconds"]) {
        maxFrames = config["simulation"]["duration_seconds"].as<int>() / timeStep;
        targetRenderTime = config["simulation"]["duration_seconds"].as<int>();
    } else {
        maxFrames = config["simulation"]["maximum_frames"].as<int>();
        targetRenderTime = maxFrames * timeStep;
    }

    // Load display parameters
    showInfo = config["renderer"]["show_info"].as<bool>();
    showTrajectories = config["renderer"]["show_trajectories"].as<bool>();
    showObstacles = config["renderer"]["show_obstacles"].as<bool>();
    showCorridors = config["renderer"]["show_corridors"].as<bool>();
    showWaypoints = config["renderer"]["show_waypoints"].as<bool>();
    waypointRadius = config["agents"]["waypoint_radius"].as<float>();
    showGrids = config["renderer"]["show_grids"].as<bool>();
    showAggregation = config["renderer"]["show_aggregation"].as<bool>(false);
    showAggregationProgress = config["renderer"]["show_aggregation_progress"].as<bool>(false);
    overrideSensorGridVisibility = config["renderer"]["show_sensor_grid"].IsDefined();
    showSensorGrid = config["renderer"]["show_sensor_grid"].as<bool>(false);
    if (!overrideSensorGridVisibility) {
        for (const auto& sensor : config["sensors"])
            if (sensor["type"].as<std::string>() == "adaptive-grid-based")
                showSensorGrid = showSensorGrid || sensor["grid"]["show_grid"].as<bool>();
        showSensorGrid = showSensorGrid && showGrids && config["renderer"]["show_sensors"].as<bool>();
    }
    showSensors = config["renderer"]["show_sensors"].as<bool>();
    showBufferZones = config["renderer"]["show_buffer"].as<bool>();
    showArrow = config["renderer"]["show_arrow"].as<bool>();
    showText = config["renderer"]["show_text"].as<bool>();

    // Load collision parameters
    showCollisionGrid = config["collision"]["grid"]["show_grid"].as<bool>();
    collisionGridCellSize = (config["collision"]["grid"]["cell_size"].as<float>());

    // Load font
    if (!font.openFromFile("/Library/Fonts/Arial Unicode.ttf")) {
        ERROR_MSG("Error loading font\n");
    }

    // Resize vertex arrays
    bufferZonesVertexArray.resize(numAgents * 300);
    agentBodyVertexArray.resize(numAgents * 6);
    agentArrowHeadVertexArray.resize(numAgents * 3);
    agentArrowBodyVertexArray.resize(numAgents * 2);
}

// Function to load agents attributes from the YAML configuration file
void Renderer::loadAgentsAttributes() {

    // Extract agent data
    if (config["agents"] && config["agents"]["road_user_taxonomy"]) {
        for (const auto& agent : config["agents"]["road_user_taxonomy"]) {
            std::string type = agent["type"].as<std::string>();
            Agent::AgentTypeAttributes attributes;

            // Load agent attributes from the configuration
            attributes.probability = agent["probability"].as<double>();
            attributes.priority = agent["priority"].as<int>();
            attributes.bodyRadius = agent["radius"].as<double>();
            attributes.color = agent["color"].as<std::string>();
            attributes.velocity.min = agent["velocity"]["min"].as<double>();
            attributes.velocity.max = agent["velocity"]["max"].as<double>();
            attributes.velocity.mu = agent["velocity"]["mu"].as<double>();
            attributes.velocity.sigma = agent["velocity"]["sigma"].as<double>();
            attributes.velocity.noiseScale = agent["velocity"]["noise_scale"].as<double>();
            attributes.velocity.noiseFactor = agent["velocity"]["noise_factor"].as<double>();
            attributes.acceleration.min = agent["acceleration"]["min"].as<double>();
            attributes.acceleration.max = agent["acceleration"]["max"].as<double>();
            attributes.lookAheadTime = agent["look_ahead_time"].as<double>();

            // Store in map
            agentTypeAttributes[type] = attributes;
        }
    }
}

// Function to load obstacles from the YAML configuration file
void Renderer::loadObstacles() {

    // Check if the 'obstacles' key exists and is a sequence
    int i = 0;
    if (config["obstacles"] && config["obstacles"].IsSequence()) {
        for (const auto& obstacleNode : config["obstacles"]) {
            std::string type = obstacleNode["type"] && obstacleNode["type"].IsScalar()
                ? obstacleNode["type"].as<std::string>() : "unknown";

            if (type == "rectangle") { // Only handle rectangles
                std::vector<float> position = obstacleNode["position"].as<std::vector<float>>();
                std::vector<float> size = obstacleNode["size"].as<std::vector<float>>();
                obstacles.push_back(Obstacle(
                    sf::FloatRect({position[0], position[1]}, {size[0], size[1]}), 
                    stringToColor(obstacleNode["color"].as<std::string>())
                ));
            } else {
                ERROR_MSG("Error: Unknown obstacle type in config file at position " << i);
            }

            ++i;
        }
    } else {
        ERROR_MSG("Error: Could not find 'obstacles' key in config file or it is not a sequence");
    }
}

// Initialize sensors with YAML configuration
void Renderer::initializeSensors() {

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

            {
                sensorNode["detection_area"]["x"].as<float>(),
                sensorNode["detection_area"]["y"].as<float>()
            },
            {
                sensorNode["detection_area"]["width"].as<float>(),
                sensorNode["detection_area"]["height"].as<float>()
            }
        );

        // Create the agent-based sensor
        if (type == "agent-based") {
            
            // Create the agent-based sensor and add to sensors vector
            sensors.push_back(std::make_unique<AgentBasedSensor>(detectionArea, colorAlpha));
            sensors.back()->sensorId = sensorNode["id"].as<std::string>();
            sensors.back()->scale = scale;


        // Create the grid-based sensor
        } else if (type == "grid-based") {

            float cellSize = sensorNode["grid"]["cell_size"].as<float>();
            bool showSensorGrid = sensorNode["grid"]["show_grid"].as<bool>();

            // Create the grid-based sensor and add to sensors vector
            sensors.push_back(std::make_unique<GridBasedSensor>(detectionArea, colorAlpha, cellSize, showSensorGrid));
            sensors.back()->sensorId = sensorNode["id"].as<std::string>();
            sensors.back()->scale = scale;
        } else if (type == "adaptive-grid-based") {

            float cellSize = sensorNode["grid"]["cell_size"].as<float>();
            bool showSensorGrid = sensorNode["grid"]["show_grid"].as<bool>();
            int maxDepth = sensorNode["grid"]["max_depth"].as<int>();

            // Create the grid-based sensor and add to sensors vector
            sensors.push_back(std::make_unique<AdaptiveGridBasedSensor>(detectionArea, colorAlpha, cellSize, maxDepth, showSensorGrid));
            sensors.back()->sensorId = sensorNode["id"].as<std::string>();
            sensors.back()->scale = scale;
        }
    }
}

// Initialize the window
void Renderer::initializeWindow() {

    // Turn on antialiasing
    sf::ContextSettings settings;
    settings.antiAliasingLevel = 16;

    // Create window
    // window.create(sf::VideoMode(windowWidth, windowHeight), title, sf::Style::Default, settings); // Note: SFML 2.6.2 or prior
    window.create(sf::VideoMode({windowWidth, windowHeight}), title, sf::Style::Default, sf::State::Windowed, settings);
}

// Initialize the GUI elements
void Renderer::initializeGUI() {

    // Frame count text
    frameText.setFont(font);
    frameText.setCharacterSize(24);
    frameText.setFillColor(sf::Color::Black);
    // Initial position will be updated in the main loop

    // Frame rate text
    frameRateText.setFont(font);
    frameRateText.setCharacterSize(24);
    frameRateText.setFillColor(sf::Color::Black);
    // Initial position will be updated in the main loop

    // Frame count text
    agentCountText.setFont(font);
    agentCountText.setCharacterSize(24);
    agentCountText.setFillColor(sf::Color::Black);
    // Initial position will be updated in the main loop

    // Frame count text
    timeText.setFont(font);
    timeText.setCharacterSize(24);
    timeText.setFillColor(sf::Color::Black);
    // Initial position will be updated in the main loop

    // Frame count text
    playbackSpeedText.setFont(font);
    playbackSpeedText.setCharacterSize(24);
    playbackSpeedText.setFillColor(sf::Color::Black);
    // Initial position will be updated in the main loop
    
    // Pause button
    pauseButton.setSize(sf::Vector2f(100, 50)); 
    pauseButton.setFillColor(sf::Color::Green);
    pauseButton.setPosition({static_cast<float>(window.getSize().x) - 110, static_cast<float>(window.getSize().y) - 60});

    pauseButtonText.setFont(font);
    pauseButtonText.setString("Pause");
    pauseButtonText.setCharacterSize(20);
    pauseButtonText.setFillColor(sf::Color::Black);
    
    // Center the pause button text
    sf::FloatRect pauseButtonTextRect = pauseButtonText.getLocalBounds();
    pauseButtonText.setOrigin({pauseButtonTextRect.position.x + pauseButtonTextRect.size.x / 2.0f,
                              pauseButtonTextRect.position.y + pauseButtonTextRect.size.y / 2.0f});
    pauseButtonText.setPosition({pauseButton.getPosition().x + pauseButton.getSize().x / 2.0f,
                                pauseButton.getPosition().y + pauseButton.getSize().y / 2.0f});

    // Reset button
    resetButton.setSize(sf::Vector2f(100, 50));
    resetButton.setFillColor(sf::Color::Cyan);
    resetButton.setPosition({static_cast<float>(window.getSize().x) - 110, static_cast<float>(window.getSize().y) - 120}); 

    resetButtonText.setFont(font);
    resetButtonText.setString("Infos");
    resetButtonText.setCharacterSize(20);
    resetButtonText.setFillColor(sf::Color::Black);

    // Center the reset button text
    sf::FloatRect resetButtonTextRect = resetButtonText.getLocalBounds();
    resetButtonText.setOrigin({resetButtonTextRect.position.x + resetButtonTextRect.size.x / 2.0f,
                              resetButtonTextRect.position.y + resetButtonTextRect.size.y / 2.0f});
    resetButtonText.setPosition({resetButton.getPosition().x + resetButton.getSize().x / 2.0f,
                                resetButton.getPosition().y + resetButton.getSize().y / 2.0f});

}

// Function to update the text that displays the current frame count
void Renderer::updateFrameCountText() {

    frameText.setString("Frame " + std::to_string(agentBuffer.currentReadFrameIndex) + " / " + (maxFrames > 0 ? std::to_string(maxFrames) : "∞")); // ∞ for unlimited frames
    sf::FloatRect textRect = frameText.getLocalBounds();
    frameText.setOrigin({textRect.size.x, 0}); // Right-align the text
    frameText.setPosition({static_cast<float>(window.getSize().x) - 10, 40}); // Position with padding
}

// Function to update the text that displays the current agent count
void Renderer::updateAgentCountText() {

    agentCountText.setString("Agents: " + std::to_string(currentNumAgents));
    sf::FloatRect textRect = agentCountText.getLocalBounds();
    agentCountText.setOrigin({textRect.size.x, 0}); // Right-align the text
    agentCountText.setPosition({static_cast<float>(window.getSize().x) - 6, 100}); // Position with padding
}

// Function to update the text that displays the current elapsed time
void Renderer::updateTimeText() {

    // Convert seconds to HH:MM:SS for totalElapsedTime
    auto totalElapsedTime = renderSimulationTime;
    int elapsedHours = static_cast<int>(totalElapsedTime.asSeconds()) / 3600;
    int elapsedMinutes = (static_cast<int>(totalElapsedTime.asSeconds()) % 3600) / 60;
    int elapsedSeconds = static_cast<int>(totalElapsedTime.asSeconds()) % 60;
    int elapsedMilliseconds = (totalElapsedTime.asSeconds() - static_cast<int>(totalElapsedTime.asSeconds())) * 1000;

    std::string targetRenderTimeString = "∞";  // Default to infinity symbol
    if(targetRenderTime > 0) {
        int targetHours = static_cast<int>(targetRenderTime) / 3600;
        int targetMinutes = (static_cast<int>(targetRenderTime)) % 3600 / 60;
        int targetSeconds = static_cast<int>(targetRenderTime) % 60;
        int targetMilliseconds = (targetRenderTime - static_cast<int>(targetRenderTime)) * 1000;

        // Format the duration string using stringstream
        std::ostringstream targetRenderTimeStream;
        targetRenderTimeStream << std::setfill('0') << std::setw(2) << targetHours << ":"
                       << std::setw(2) << targetMinutes << ":"
                       << std::setw(2) << targetSeconds << ":"
                       << std::setw(3) << targetMilliseconds;
        targetRenderTimeString = targetRenderTimeStream.str();
    }

    // Format the time string using stringstream
    std::ostringstream timeStream;
    timeStream << "Time: " << std::setfill('0') << std::setw(2) << elapsedHours << ":"
               << std::setw(2) << elapsedMinutes << ":"
               << std::setw(2) << elapsedSeconds << ":"
               << std::setw(3) << elapsedMilliseconds << " / " << targetRenderTimeString;
    timeText.setString(timeStream.str()); 

    // Right-align and position the text
    sf::FloatRect textRect = timeText.getLocalBounds();
    timeText.setOrigin({textRect.size.x, 0}); 
    timeText.setPosition({static_cast<float>(window.getSize().x) - 10, 10}); 
}

// Count newly consumed agent frames, excluding pause redraws. Producer waits remain
// part of elapsed frame intervals; use frames / elapsed time, not mean(1 / interval).
void Renderer::updateFrameRateText() {
    std::ostringstream text;
    text << std::fixed << std::setprecision(1) << "Agent FPS: ";
    if (paused) text << "paused";
    else if (const auto fps = playbackClock->measuredFps()) text << *fps;
    else text << "--";
    text << " / target " << playbackClock->targetFps();
    if (waitingForFrame) text << " (waiting for input)";
    frameRateText.setString(text.str());
    const auto bounds = frameRateText.getLocalBounds();
    frameRateText.setOrigin({bounds.size.x, 0});
    frameRateText.setPosition({static_cast<float>(window.getSize().x) - 10, 70});
}

void Renderer::updatePlayBackSpeedText() {
    std::ostringstream text;
    text << std::fixed << std::setprecision(2) << "Playback: " << playbackSpeed << "x requested";
    if (paused) text << " | paused";
    else if (const auto speed = playbackClock->measuredSpeed()) text << " | " << *speed << "x measured";
    else text << " | measuring";
    playbackSpeedText.setString(text.str());
    const auto bounds = playbackSpeedText.getLocalBounds();
    playbackSpeedText.setOrigin({bounds.size.x, 0});
    playbackSpeedText.setPosition({static_cast<float>(window.getSize().x) - 6, 130});
}

// Function to handle events
void Renderer::handleEvents() {

    // Lambda to handle window close events.
    const auto onClose = [this](const sf::Event::Closed&) {
        redrawRequested = true;
        window.close();
        agentBuffer.requestStop();
        sensorBuffer.requestStop();
    };

    // Lambda to handle window resize events.
    const auto onResized = [this](const sf::Event::Resized& resized) {
        redrawRequested = true;
        sf::FloatRect visibleArea({0, 0}, {static_cast<float>(resized.size.x), static_cast<float>(resized.size.y)});
        window.setView(sf::View(visibleArea));
        initializeGUI(); // Reinitialize UI elements

        // Update simulation dimensions and offset.
        windowWidth  = static_cast<float>(resized.size.x);
        windowHeight = static_cast<float>(resized.size.y);
        offset = sf::Vector2f((windowWidth - simulationWidth) / 2,
                              (windowHeight - simulationHeight) / 2);
    };

    // Lambda to handle key pressed events.
    const auto onKeyPressed = [this](const sf::Event::KeyPressed& keyPressed) {
        redrawRequested = true;
        // Toggle pause with Space.
        if (keyPressed.scancode == sf::Keyboard::Scancode::Space) {
            paused = !paused;
            pauseButtonText.setString(paused ? "  Play" : "Pause");
            pauseButton.setFillColor(paused ? sf::Color::Red : sf::Color::Green);
        }
        // Set modifier flags.
        else if (keyPressed.scancode == sf::Keyboard::Scancode::LShift ||
                 keyPressed.scancode == sf::Keyboard::Scancode::RShift) {
            isShiftPressed = true;
        }
        else if (keyPressed.scancode == sf::Keyboard::Scancode::LControl ||
                 keyPressed.scancode == sf::Keyboard::Scancode::RControl) {
            isCtrlPressed = true;
        }
        // Adjust playback speed.
        else if (keyPressed.scancode == sf::Keyboard::Scancode::Left) {
            if (playbackSpeed > 0.1) playbackSpeed = std::max(0.1, playbackSpeed - 0.1);
            DEBUG_MSG("Playback speed decreased to: " << playbackSpeed);
        }
        else if (keyPressed.scancode == sf::Keyboard::Scancode::Right) {
            playbackSpeed = std::min(static_cast<double>(timeStep) / 1e-6, playbackSpeed + 0.1);
            DEBUG_MSG("Playback speed increaased to: " << playbackSpeed);
        }
        
        else if (keyPressed.scancode == sf::Keyboard::Scancode::A) {
            showArrow = !showArrow;
        }

        else if (keyPressed.scancode == sf::Keyboard::Scancode::G) {
            showAggregation = !showAggregation;
        }

        else if (keyPressed.scancode == sf::Keyboard::Scancode::H) {
            showSensorGrid = !showSensorGrid;
            overrideSensorGridVisibility = true;
        }

        else if (keyPressed.scancode == sf::Keyboard::Scancode::P) {
            showAggregationProgress = !showAggregationProgress;
        }

        else if (keyPressed.scancode == sf::Keyboard::Scancode::B) {
            showBufferZones = !showBufferZones;
        }

        else if (keyPressed.scancode == sf::Keyboard::Scancode::C) {
            showCollisionGrid = !showCollisionGrid;
        }

        else if (keyPressed.scancode == sf::Keyboard::Scancode::O) {
            showObstacles = !showObstacles;
        }
        
        else if (keyPressed.scancode == sf::Keyboard::Scancode::Q) {
            window.close();
            agentBuffer.requestStop();
            sensorBuffer.requestStop();
        }

        else if (keyPressed.scancode == sf::Keyboard::Scancode::R) {
            playbackSpeed = 1.0f;
            DEBUG_MSG("Playback speed reset to: " << playbackSpeed);
        }

        else if (keyPressed.scancode == sf::Keyboard::Scancode::S) {
            showSensors = !showSensors;
        }

        else if (keyPressed.scancode == sf::Keyboard::Scancode::T) {
            showTrajectories = !showTrajectories;
        }
        
        else if (keyPressed.scancode == sf::Keyboard::Scancode::W) {
            showWaypoints = !showWaypoints;
        }

        else if (keyPressed.scancode == sf::Keyboard::Scancode::Z) {
            scale = initialScale;
            simulationHeight = initialSimulationHeight;
            simulationWidth = initialSimulationWidth;
            offset.x = (windowWidth - initialSimulationWidth) / 2;
            offset.y = (windowHeight - initialSimulationHeight) / 2;
            
        }

        else if (keyPressed.scancode == sf::Keyboard::Scancode::Escape) {
            window.close();
            agentBuffer.requestStop();
            sensorBuffer.requestStop();
        }
    };

    // Lambda to handle key released events.
    const auto onKeyReleased = [this](const sf::Event::KeyReleased& keyReleased) {
        redrawRequested = true;
        if (keyReleased.scancode == sf::Keyboard::Scancode::LShift ||
            keyReleased.scancode == sf::Keyboard::Scancode::RShift) {
            isShiftPressed = false;
        }
        else if (keyReleased.scancode == sf::Keyboard::Scancode::LControl ||
                 keyReleased.scancode == sf::Keyboard::Scancode::RControl) {
            isCtrlPressed = false;
        }
    };

    // Lambda to handle mouse button pressed events.
    const auto onMouseButtonPressed = [this](const sf::Event::MouseButtonPressed& mouseButton) {
        redrawRequested = true;
        if (mouseButton.button == sf::Mouse::Button::Left) {
            // Get mouse position relative to the window.
            sf::Vector2i mousePosition = sf::Mouse::getPosition(window);
            if (!pauseButton.getGlobalBounds().contains({static_cast<float>(mousePosition.x), static_cast<float>(mousePosition.y)}) &&
                !resetButton.getGlobalBounds().contains({static_cast<float>(mousePosition.x), static_cast<float>(mousePosition.y)})) {
                isPanning = true;
                lastMousePosition = {static_cast<float>(mousePosition.x), static_cast<float>(mousePosition.y)};
            }
            else { 
                if (pauseButton.getGlobalBounds().contains({static_cast<float>(mousePosition.x),
                    static_cast<float>(mousePosition.y)})) {
                    paused = !paused;
                    pauseButtonText.setString(paused ? "  Play" : "Pause");
                    pauseButton.setFillColor(paused ? sf::Color::Red : sf::Color::Green);
                }
                else if (resetButton.getGlobalBounds().contains({static_cast<float>(mousePosition.x),
                                                                static_cast<float>(mousePosition.y)})) {
                    showInfo = !showInfo;
                }
            }
        }
    };

    // Mouse released
    const auto onMouseButtonReleased = [this](const sf::Event::MouseButtonReleased& mouseButton) {
        redrawRequested = true;
        if (mouseButton.button == sf::Mouse::Button::Left) {
            isPanning = false; // Stop dragging
        }
    };

    const auto onMouseMoved = [this](const sf::Event::MouseMoved& mouseMoved) {
        redrawRequested = true;
        if (isPanning) {
            // Current mouse position
            sf::Vector2f currentPosition(static_cast<float>(mouseMoved.position.x), static_cast<float>(mouseMoved.position.y));
    
            // Compute the difference
            sf::Vector2f delta = currentPosition - lastMousePosition;
    
            // Update offset by that difference
            offset += delta;
    
            // Update lastMousePos for next movement
            lastMousePosition = currentPosition;
        }
    };

    // Lambda to handle mouse wheel scroll events.
    const auto onMouseWheelScrolled = [this](const sf::Event::MouseWheelScrolled& scroll) {
        redrawRequested = true;
        if (isShiftPressed) {
            if (scroll.delta > 0) {
                offset.x -= 20;
            } else if (scroll.delta < 0) {
                offset.x += 20;
            }
        }
        else if (isCtrlPressed) {
            if (scroll.delta > 0) {
                offset.y -= 20;
            } else if (scroll.delta < 0) {
                offset.y += 20;
            }
        }
        else {
            int previousWidth = simulationWidth;
            int previousHeight = simulationHeight;
            simulationHeight /= scale;
            simulationWidth /= scale;
            if (scroll.delta > 0) {
                scale += 1.0f;
            } else if (scroll.delta < 0) {
                if (scale != 1.0f) scale -= 1.0f;
            }
            simulationHeight *= scale;
            simulationWidth *= scale;
            offset.x = offset.x - (simulationWidth - previousWidth) / 2;
            offset.y = offset.y - (simulationHeight - previousHeight) / 2;
        }
    };

    // Now pass all these lambdas to the window's handleEvents function.
    window.handleEvents(onClose,
                        onResized,
                        onKeyPressed,
                        onKeyReleased,
                        onMouseButtonPressed,
                        onMouseButtonReleased,
                        onMouseMoved,
                        onMouseWheelScrolled);
}

// One pacing owner for scientific-frame consumption. UI redraws never consume data.
void Renderer::run() {
    using Clock = std::chrono::steady_clock;
    const auto origin = Clock::now();
    const auto nowSeconds = [&] {
        return std::chrono::duration<double>(Clock::now() - origin).count();
    };
    std::optional<std::chrono::system_clock::time_point> firstFrameTimestamp;
    double nextRedraw = 0;
    std::size_t redraws = 0;
    renderSimulationTime = sf::Time::Zero;

    while (window.isOpen()) {
        handleEvents();
        if (!window.isOpen()) break;
        const double now = nowSeconds();
        playbackClock->update(now, playbackSpeed, paused);
        bool received = false;
        const bool wasWaiting = waitingForFrame;
        if (paused) waitingForFrame = false;
        else {
            if (agentBuffer.isDrained()) break;
            if (playbackClock->due(now)) {
                received = readNextFrame();
                waitingForFrame = !received;
                if (received) {
                    playbackClock->consumed(now);
                    if (!firstFrameTimestamp) firstFrameTimestamp = timestamp;
                    renderSimulationTime = sf::microseconds(
                        std::chrono::duration_cast<std::chrono::microseconds>(timestamp - *firstFrameTimestamp).count());
                }
            }
        }
        redrawRequested |= wasWaiting != waitingForFrame;
        // Redraw on new data or interaction. Idle interaction is capped at 30 Hz;
        // repeated drawing does not count as a new observation or advance the clock.
        if (currentAgentFrame && (received || (redrawRequested && now >= nextRedraw))) {
            currentNumAgents = static_cast<int>(currentAgentFrame->size());
            updateAgentCountText();
            updateFrameCountText();
            updateTimeText();
            updateFrameRateText();
            updatePlayBackSpeedText();
            render();
            ++redraws;
            redrawRequested = false;
            nextRedraw = nowSeconds() + 1.0 / 30.0;
        }

        // Short waits keep close/pause/speed controls responsive even at low playback
        // rates. The deadline survives empty-buffer retries and drawing overhead.
        const double afterDraw = nowSeconds();
        double sleep = paused ? .005 : std::min(.005, playbackClock->remaining(afterDraw));
        if (!paused && waitingForFrame && sleep == 0) sleep = .001;
        if (sleep > 0) std::this_thread::sleep_for(std::chrono::duration<double>(sleep));
    }
    playbackClock->update(nowSeconds(), playbackSpeed, paused);
    if (config["renderer"]["log_playback_timing"].as<bool>(false)) {
        std::cout << "Renderer playback: requested=" << playbackClock->requested()
            << " frames=" << playbackClock->consumedFrames() << " redraws=" << redraws
            << " active_s=" << playbackClock->activeSeconds()
            << " paused_s=" << playbackClock->pausedSeconds();
        if (const auto fps = playbackClock->measuredFps()) std::cout << " measured_fps=" << *fps;
        std::cout << '\n';
    }
}

// The received agent frame confirms that all sensor work for this timestamp is complete.
bool Renderer::readNextFrame() {
    auto next = agentBuffer.tryRead();
    if (!next || !*next) return false;
    const auto& received = *next;
    timestamp = received->first;
    sensorFrames.selectCompletedStep(received->first, sensorBuffer);
    currentAgentFrame = std::shared_ptr<const agentFrame>(received, &received->second);
    const auto& selected = sensorFrames.frame();
    currentSensorFrame = selected
        ? std::shared_ptr<const sensorFrame>(selected, &selected->second) : nullptr;

    // Each sensor owns its geometry; route only its own typed payload.
    for (auto& sensor : sensors) {
        auto* agbs = dynamic_cast<AdaptiveGridBasedSensor*>(sensor.get());
        if (!agbs) continue;
        auto& display = adaptiveGridDisplays[agbs->sensorId];
        if (display.update(selected, agbs->sensorId)) {
            agbs->adaptiveGrid.clear();
            agbs->adaptiveGrid.splitFromCellIds(display.cellIds());
        }
    }
    return true;
}

// Read-only overlay of the last closed candidate window. Fine sensor geometry remains
// intact underneath. Coarsening/refinement labels compare adjacent closed windows only.
void Renderer::drawAggregationOverlay(const ump::SpatialSelection& snapshot) {
    for (std::size_t i = 0; i < snapshot.candidate.cells.size(); ++i) {
        const auto& item = snapshot.candidate.cells[i];
        const auto& decision = snapshot.decisions[i];
        const auto& c = item.cell;
        sf::Color edge = decision.selected ? sf::Color(28, 116, 80) : sf::Color(175, 52, 45);
        if (decision.selected && decision.transition == "coarsened") edge = sf::Color(205, 112, 18);
        if (decision.selected && decision.transition == "refined") edge = sf::Color(37, 92, 190);
        sf::RectangleShape box({static_cast<float>(c.width * scale), static_cast<float>(c.height * scale)});
        box.setPosition({static_cast<float>(c.x * scale) + offset.x, static_cast<float>(c.y * scale) + offset.y});
        box.setFillColor(sf::Color(edge.r, edge.g, edge.b, decision.selected ? 36 : 65));
        box.setOutlineColor(edge);
        box.setOutlineThickness(-2.5f);
        window.draw(box);
        if (c.width * scale >= 42) {
            const std::string label = decision.selected
                ? "d" + std::to_string(c.depth) + " RU=" + std::to_string(item.counts.distinctContributors)
                : "SUPPRESSED";
            sf::Text text(font, label, 11);
            text.setFillColor(edge);
            const auto bounds = text.getLocalBounds();
            const auto position = box.getPosition() + sf::Vector2f{4.f, static_cast<float>(c.height * scale) - 19.f};
            text.setPosition(position);
            sf::RectangleShape backing({bounds.size.x + 4.f, bounds.size.y + 5.f});
            backing.setPosition(position + bounds.position - sf::Vector2f{2.f, 2.f});
            backing.setFillColor(sf::Color(255, 255, 255, 220));
            window.draw(backing);
            window.draw(text);
        }
    }
}

// Pending outlines describe the last evaluated finest cells in the active window.
// They are not suppression decisions and never mutate sensor or aggregation state.
void Renderer::drawAggregationProgress(const ump::AggregationProgress& progress) {
    if (!progress.lastCheck || progress.phase == ump::AggregationProgressPhase::Finished) return;
    std::unordered_set<int> pending;
    for (const auto& assessment : progress.lastCheck->assessment.cells)
        if (ump::pendingAggregationCell(assessment.status)) pending.insert(assessment.cellId);
    sf::VertexArray dashes(sf::PrimitiveType::Lines);
    const sf::Color amber(180, 130, 20, 230);
    const auto edge = [&](sf::Vector2f from, sf::Vector2f to) {
        const auto delta = to - from;
        const float length = std::sqrt(delta.x * delta.x + delta.y * delta.y);
        if (length <= 0.f) return;
        const auto direction = delta / length;
        for (float at = 0.f; at < length; at += 8.f) {
            dashes.append(sf::Vertex{from + direction * at, amber});
            dashes.append(sf::Vertex{from + direction * std::min(at + 5.f, length), amber});
        }
    };
    for (const auto& item : progress.lastCheck->candidate.cells) {
        if (!pending.count(item.cell.id)) continue;
        const auto& cell = item.cell;
        const float x = static_cast<float>(cell.x * scale) + offset.x;
        const float y = static_cast<float>(cell.y * scale) + offset.y;
        const float w = static_cast<float>(cell.width * scale);
        const float h = static_cast<float>(cell.height * scale);
        edge({x, y}, {x + w, y});
        edge({x + w, y}, {x + w, y + h});
        edge({x + w, y + h}, {x, y + h});
        edge({x, y + h}, {x, y});
    }
    window.draw(dashes);
}

// Word wrapping follows measured font widths so the sidebar also works after resizing.
float Renderer::drawStatusPanel(const std::vector<std::string>& lines, sf::Vector2f position, float width) {
    if (width < 40.f || lines.empty()) return 0.f;
    const float textWidth = width - 16.f;
    sf::Text measured(font, "", 12);
    std::string wrapped;
    for (const auto& paragraph : lines) {
        std::istringstream words(paragraph);
        std::string word, line;
        while (words >> word) {
            const std::string candidate = line.empty() ? word : line + " " + word;
            measured.setString(candidate);
            if (measured.getLocalBounds().size.x <= textWidth) {
                line = candidate;
                continue;
            }
            if (!line.empty()) {
                wrapped += line + '\n';
                line.clear();
            }
            measured.setString(word);
            if (measured.getLocalBounds().size.x <= textWidth) {
                line = word;
                continue;
            }
            // Split only unusually long identifiers, keeping normal words intact.
            for (const char ch : word) {
                measured.setString(line + ch);
                if (!line.empty() && measured.getLocalBounds().size.x > textWidth) {
                    wrapped += line + '\n';
                    line.clear();
                }
                line += ch;
            }
        }
        wrapped += line + '\n';
    }
    if (!wrapped.empty()) wrapped.pop_back();
    sf::Text text(font, wrapped, 12);
    text.setFillColor(sf::Color(35, 40, 45));
    text.setPosition(position + sf::Vector2f{8.f, 5.f});
    const float height = text.getLocalBounds().size.y + 16.f;
    sf::RectangleShape background({width, height});
    background.setPosition(position);
    background.setFillColor(sf::Color(255, 255, 255, 243));
    background.setOutlineColor(sf::Color(205, 210, 215));
    background.setOutlineThickness(1.f);
    window.draw(background);
    window.draw(text);
    return height;
}

void Renderer::drawAggregationStatusPanels() {
    if (!showAggregation && !showAggregationProgress && !showSensorGrid && !showSensors) return;
    const float availableWidth = static_cast<float>(window.getSize().x) - 24.f;
    const bool besideMap = offset.x >= 205.f;
    const float panelWidth = besideMap ? std::min(offset.x - 24.f, 285.f) : std::min(availableWidth, 430.f);
    sf::Vector2f position{12.f, besideMap ? std::max(12.f, offset.y) : 12.f};
    for (const auto& sensor : sensors) {
        const auto* adaptive = dynamic_cast<const AdaptiveGridBasedSensor*>(sensor.get());
        if (!adaptive) continue;
        const auto it = adaptiveGridDisplays.find(adaptive->sensorId);
        if (it == adaptiveGridDisplays.end()) continue;
        const auto& display = it->second;
        std::vector<std::string> lines{"Sensor " + adaptive->sensorId, "H input grid | G completed | P active | S area"};
        if (showSensorGrid && (overrideSensorGridVisibility || adaptive->showGrid)) {
            if (const auto measuredAt = display.measurementTime()) {
                const auto age = std::chrono::duration_cast<std::chrono::milliseconds>(timestamp - *measuredAt).count();
                lines.push_back("Input grid: last sample " + std::to_string(age) + " ms ago");
            } else lines.push_back("Input grid: waiting for a sample");
        }
        if (showAggregation) {
            lines.emplace_back("");
            const auto closed = ump::aggregationCompletedLines(display.aggregationSnapshot().get());
            lines.insert(lines.end(), closed.begin(), closed.end());
        }
        if (showAggregationProgress) {
            lines.emplace_back("");
            const auto active = ump::aggregationProgressLines(display.progressSnapshot().get());
            lines.insert(lines.end(), active.begin(), active.end());
        }
        position.y += drawStatusPanel(lines, position, panelWidth) + 12.f;
    }
}

// Main rendering function
void Renderer::render() {  // Input: meters, Output: pixels

    // Clear the window
    window.clear(sf::Color::White);

    // Get the current number of agents
    // currentNumAgents = currentFrame.size();
    // currentNumAgents = currentFrame ? static_cast<int>(currentFrame->size()) : 0;
    currentNumAgents = static_cast<int>(currentAgentFrame->size());

    // Loop through all agents and render them
    if (currentNumAgents != 0 || agentBuffer.currentReadFrameIndex != maxFrames) {

        // Draw the grid if enabled
        {
            // The collision grid is independent of sensor and aggregation visibility.
            if(showGrids && showCollisionGrid) {

                // Draw outer rectangle
                sf::RectangleShape gridBoundaries(sf::Vector2f(simulationWidth, simulationHeight));
                gridBoundaries.setPosition(offset); // Set position in pixels
                gridBoundaries.setFillColor(sf::Color::Transparent);
                gridBoundaries.setOutlineColor(sf::Color::Red);
                gridBoundaries.setOutlineThickness(1);
                window.draw(gridBoundaries);

                // Draw vertical lines
                for (int x = 0; x <= (simulationWidth / (collisionGridCellSize * scale)); x++) {
                    sf::Vertex line[] = {
                        sf::Vertex({sf::Vector2f((x * collisionGridCellSize * scale), 0) + offset, sf::Color(220, 220, 220)}),
                        sf::Vertex({sf::Vector2f((x * collisionGridCellSize * scale), simulationHeight) + offset, sf::Color(220, 220, 220)})
                    };
                    window.draw(line, 2, sf::PrimitiveType::Lines);
                }

                // Draw horizontal lines
                for (int x = 0; x <= (simulationHeight / (collisionGridCellSize * scale)); x++) {
                    sf::Vertex line[] = {
                        sf::Vertex({sf::Vector2f(0, (x * collisionGridCellSize * scale)) + offset, sf::Color(220, 220, 220)}),
                        sf::Vertex({sf::Vector2f(simulationWidth, (x * collisionGridCellSize * scale)) + offset, sf::Color(220, 220, 220)})
                    };
                    window.draw(line, 2, sf::PrimitiveType::Lines);
                }
            }

            // Loop through sensors pointer
            for (const auto& sensor : sensors) {

                // Check if the sensor is grid-based
                if(auto agentBasedSensor = dynamic_cast<AgentBasedSensor*>(sensor.get())) {

                    // Draw the grid if enabled
                    if(showSensors) {

                        // Draw outer rectangle
                        sf::RectangleShape gridBoundaries(sf::Vector2f(agentBasedSensor->detectionArea.size.x * scale, agentBasedSensor->detectionArea.size.y * scale));
                        gridBoundaries.setPosition({agentBasedSensor->detectionArea.position.x * scale + offset.x, agentBasedSensor->detectionArea.position.y * scale + offset.y}); // Set position in pixels
                        // gridBoundaries.setFillColor(sf::Color::Transparent);
                        gridBoundaries.setFillColor(agentBasedSensor->detectionAreaColor);
                        gridBoundaries.setOutlineColor(sf::Color::Black);
                        gridBoundaries.setOutlineThickness(3);
                        window.draw(gridBoundaries);
                    }
                }

                // Check if the sensor is grid-based
                else if(auto gridBasedSensor = dynamic_cast<GridBasedSensor*>(sensor.get())) {

                    // Draw the grid if enabled
                    if(gridBasedSensor->showGrid && showSensors && showGrids) {

                        // Draw outer rectangle
                        sf::RectangleShape gridBoundaries(sf::Vector2f(gridBasedSensor->detectionArea.size.x * scale, gridBasedSensor->detectionArea.size.y * scale));
                        gridBoundaries.setPosition({gridBasedSensor->detectionArea.position.x * scale + offset.x, gridBasedSensor->detectionArea.position.y * scale + offset.y}); // Set position in pixels
                        // gridBoundaries.setFillColor(sf::Color::Transparent);
                        gridBoundaries.setFillColor(gridBasedSensor->detectionAreaColor);
                        gridBoundaries.setOutlineColor(sf::Color::Black);
                        gridBoundaries.setOutlineThickness(3);
                        window.draw(gridBoundaries);

                        // Draw vertical lines
                        for (int x = 0; x <= (gridBasedSensor->detectionArea.size.x / gridBasedSensor->cellSize); x++) {
                            sf::Vertex line[] = {
                                sf::Vertex({sf::Vector2f((gridBasedSensor->detectionArea.position.x + x * gridBasedSensor->cellSize) * scale, gridBasedSensor->detectionArea.position.y * scale) + offset, sf::Color(220, 220, 220)}),
                                sf::Vertex({sf::Vector2f((gridBasedSensor->detectionArea.position.x + x * gridBasedSensor->cellSize) * scale, (gridBasedSensor->detectionArea.size.y + gridBasedSensor->detectionArea.position.y) * scale) + offset, sf::Color(220, 220, 220)})
                            };
                            window.draw(line, 2, sf::PrimitiveType::Lines);
                        }

                        // Draw horizontal lines
                        for (int x = 0; x <= (gridBasedSensor->detectionArea.size.y / gridBasedSensor->cellSize); x++) {
                            sf::Vertex line[] = {
                                sf::Vertex({sf::Vector2f((gridBasedSensor->detectionArea.position.x) * scale, (gridBasedSensor->detectionArea.position.y + x * gridBasedSensor->cellSize) * scale) + offset, sf::Color(220, 220, 220)}),
                                sf::Vertex({sf::Vector2f((gridBasedSensor->detectionArea.position.x + gridBasedSensor->detectionArea.size.x) * scale, (gridBasedSensor->detectionArea.position.y + x * gridBasedSensor->cellSize) * scale) + offset, sf::Color(220, 220, 220)})
                            };
                            window.draw(line, 2, sf::PrimitiveType::Lines);
                        }
                    }
                }

                else if(auto adaptiveGridBasedSensor = dynamic_cast<AdaptiveGridBasedSensor*>(sensor.get())) {
                    // Sensor coverage, acquisition geometry and aggregation evidence are
                    // separate layers. H, G and P remain usable when S is hidden.
                    if (showSensors) {
                        sf::RectangleShape boundary({adaptiveGridBasedSensor->detectionArea.size.x * scale,
                                                     adaptiveGridBasedSensor->detectionArea.size.y * scale});
                        boundary.setPosition({adaptiveGridBasedSensor->detectionArea.position.x * scale + offset.x,
                                              adaptiveGridBasedSensor->detectionArea.position.y * scale + offset.y});
                        boundary.setFillColor(adaptiveGridBasedSensor->detectionAreaColor);
                        boundary.setOutlineColor(sf::Color::Black);
                        boundary.setOutlineThickness(2.f);
                        window.draw(boundary);
                    }
                    if (showSensorGrid && (overrideSensorGridVisibility || adaptiveGridBasedSensor->showGrid)) {
                        adaptiveGridBasedSensor->adaptiveGrid.showCellId = showText;
                        adaptiveGridBasedSensor->adaptiveGrid.draw(window, font, scale, offset);
                    }
                    const auto& display = adaptiveGridDisplays.at(adaptiveGridBasedSensor->sensorId);
                    if (showAggregation && display.aggregationSnapshot())
                        drawAggregationOverlay(*display.aggregationSnapshot());
                    if (showAggregationProgress && display.progressSnapshot())
                        drawAggregationProgress(*display.progressSnapshot());
                }
            }
        }

        // Draw obstacles if enabled
        if(showObstacles) {

            // Draw obstacles
            for (const Obstacle& obstacle : obstacles) {
                
                sf::RectangleShape obstacleShape(sf::Vector2f(obstacle.getBounds().size.x * scale, obstacle.getBounds().size.y * scale));
                obstacleShape.setPosition({obstacle.getBounds().position.x * scale + offset.x, obstacle.getBounds().position.y * scale + offset.y}); // Scale only position here
                obstacleShape.setFillColor(obstacle.getColor());
                window.draw(obstacleShape);
            }
        }

        // Clear the vertex arrays
        bufferZonesVertexArray.clear();
        agentBodyVertexArray.clear();
        agentArrowHeadVertexArray.clear();
        agentArrowBodyVertexArray.clear();

        // Prepare render agents
        renderAgents.clear();
        renderAgents.reserve(currentAgentFrame->size());

        // Prepare and scale render agent 
        for (const auto& currentAgent: *currentAgentFrame) {

            // Scale agent properties from meters to pixels
            RenderAgent agent;
            agent.position = currentAgent.position * scale; // Pixels
            agent.initialPosition = currentAgent.initialPosition * scale; // Pixels
            agent.targetPosition = currentAgent.targetPosition * scale; // Pixels
            agent.bodyRadius = currentAgent.bodyRadius * scale; // Pixels
            agent.velocity = currentAgent.velocity * scale; // Pixels
            agent.bufferZoneRadius = currentAgent.bufferZoneRadius * scale; // Pixels
            agent.velocityMagnitude = currentAgent.velocityMagnitude * scale; // Pixels
            agent.bufferZoneColor = currentAgent.bufferZoneColor;
            agent.heading = currentAgent.heading;
            agent.waypointColor = sf::Color::Red;
            agent.color = currentAgent.color;
            agent.type = currentAgent.type;
            agent.waypointDistance = currentAgent.waypointDistance * scale; // Pixels
            agent.nextWaypointIndex = currentAgent.nextWaypointIndex;

            for(auto& waypoint : currentAgent.trajectory) {
                agent.trajectory.push_back(waypoint * scale);
            }

            // Determine the next waypoint index that is ahead of the agent
            if(showWaypoints) {
                
                sf::VertexArray waypoints(sf::PrimitiveType::Triangles, 6);

                // Calculate the next waypoint
                // Get the next waypoint based on trajectory, position, and velocity
                for (int i = 0; i < agent.trajectory.size(); ++i) {
                    sf::Vector2f directionToWaypoint = agent.trajectory[i] - agent.position;
                    float dotProduct = directionToWaypoint.x * agent.velocity.x + directionToWaypoint.y * agent.velocity.y;
                    if (dotProduct > 0) {
                        agent.nextWaypointIndex = i;
                        break;
                    }
                }
                // agent.getNextWaypoint();

                // Calculate the neighboring pixels for the quad
                if (agent.nextWaypointIndex != -1) {
                    for (size_t i = agent.nextWaypointIndex; i < agent.trajectory.size(); ++i) {
                        sf::Vector2f center = agent.trajectory[i];
                        sf::Color color = agent.waypointColor;

                        // Calculate quad vertices
                        sf::Vector2f topLeft(center.x - waypointRadius + offset.x, center.y - waypointRadius + offset.y);
                        sf::Vector2f topRight(center.x + waypointRadius + offset.x, center.y - waypointRadius + offset.y);
                        sf::Vector2f bottomRight(center.x + waypointRadius + offset.x, center.y + waypointRadius + offset.y);
                        sf::Vector2f bottomLeft(center.x - waypointRadius + offset.x, center.y + waypointRadius + offset.y);

                        // // First triangle
                        waypoints.append(sf::Vertex({topLeft, color}));
                        waypoints.append(sf::Vertex({bottomLeft, color}));
                        waypoints.append(sf::Vertex({bottomRight, color}));

                        // // Second triangle
                        waypoints.append(sf::Vertex({topLeft, color}));
                        waypoints.append(sf::Vertex({topRight, color}));
                        waypoints.append(sf::Vertex({bottomRight, color}));
                    }
                }

                // Draw waypoints quads
                window.draw(waypoints);
            }   

            // Draw the trajectory lines from initial position to current position respectively to target position
            if(showTrajectories) {
                
                sf::Vertex pastTrajectory[] = {
                    sf::Vertex({agent.initialPosition + offset, sf::Color::Blue}), 
                    sf::Vertex({agent.position + offset, sf::Color::Blue})
                };
                sf::Vertex futureTrajectory[] = {
                    sf::Vertex({agent.position + offset, sf::Color::Red}),
                    sf::Vertex({agent.targetPosition + offset, sf::Color::Red})
                };
                window.draw(pastTrajectory, 2, sf::PrimitiveType::Lines);
                window.draw(futureTrajectory, 2, sf::PrimitiveType::Lines);

            }

            // Draw the arrow (a triangle) representing the velocity vector
            if(showArrow) {

                sf::Vector2f direction = agent.velocity;  // Direction of the arrow from velocity vector
                float theta = std::atan2(agent.heading.y, agent.heading.x) * 180.0f / M_PI; // Convert to degrees
                sf::Angle thetaAngle = sf::degrees(theta);
                float arrowLength = 5.0;

                // Normalize the direction vector for consistent arrow length
                float magnitude = std::sqrt(direction.x * direction.x + direction.y * direction.y);
                sf::Vector2f normalizedDirection;
                
                // Normalize the direction vector if its magnitude is greater than a small threshold
                if (magnitude > EPSILON) {

                    // Normalize the direction vector
                    normalizedDirection = direction / magnitude;

                    // Arrow shape factor
                    float arrowHeadLength = 0.4 * scale;
                    float arrowHeadWidth = 0.25 * scale;
                    int lineThickness = 4;

                    // Arrowhead (triangle) - Offset the tip by the agent's radius
                    sf::ConvexShape arrow(3);
                    arrow.setPoint(0, sf::Vector2f(0, 0)); // Tip of the arrow
                    arrow.setPoint(1, sf::Vector2f(-arrowHeadLength, arrowHeadWidth / 2));
                    arrow.setPoint(2, sf::Vector2f(-arrowHeadLength , -arrowHeadWidth / 2));
                    arrow.setFillColor(sf::Color::Black);

                    sf::Vertex line[] =
                    {
                        sf::Vertex({agent.position + offset, sf::Color::Black}),  // Offset start point
                        sf::Vertex({line[0].position + normalizedDirection * (agent.bodyRadius + arrowHeadLength + agent.velocityMagnitude / arrowLength), sf::Color::Black}) // Ending point (base of arrowhead)
                    };

                    // Append the arrow lines to the vertex array
                    agentArrowBodyVertexArray.append(line[0]);
                    agentArrowBodyVertexArray.append(line[1]);

                    // Create a triangle shape for the arrowhead
                    sf::Vertex triangle[] =
                    {
                        sf::Vertex({line[1].position, sf::Color::Black}),  // Tip of the arrowhead
                        sf::Vertex({triangle[0].position + sf::Vector2f(-arrowHeadLength, arrowHeadWidth / 2), sf::Color::Black}),  // Left point of the arrowhead
                        sf::Vertex({triangle[0].position + sf::Vector2f(-arrowHeadLength, -arrowHeadWidth / 2), sf::Color::Black})  // Right point of the arrowhead
                    };

                    // Rotate the triangle shape based on the agent's heading
                    sf::Transform transform;
                    transform.rotate(thetaAngle, triangle[0].position);

                    // Apply the transformation to the triangle vertices and append them to the vertex array
                    for(int i = 0; i < 3; i++) {
                        triangle[i].position = transform.transformPoint(triangle[i].position);
                        agentArrowHeadVertexArray.append(triangle[i]);
                    }
                } else {
                    normalizedDirection = sf::Vector2f(0, 0);
                }
            }

            // Append the agent bodies and agentBuffer zones to the vertex arrays
            appendAgentBodies(agentBodyVertexArray, agent);

            // Draw the agentBuffer zones
            if(showBufferZones){ 

                appendBufferZones(bufferZonesVertexArray, agent);
            }
        }

        // Draw the sensor detection areas
        // if(showSensors) {

        //     // Draw sensor detection area of each sensor
        //     for (const auto& sensorPtr : sensors) { // Iterate over all sensor pointers

        //         // Dereference the sensor pointer
        //         const Sensor& sensor = *sensorPtr;

        //         // Draw the detection area for each sensor
        //         sf::RectangleShape detectionAreaShape(sf::Vector2f(sensor.detectionArea.size.x * scale, sensor.detectionArea.height * scale));
        //         detectionAreaShape.setPosition(sensor.detectionArea.position.x * scale + offset.x, sensor.detectionArea.top * scale + offset.y);
        //         detectionAreaShape.setFillColor(sensor.detectionAreaColor); // Set the color with alpha
        //         window.draw(detectionAreaShape);
        //     }
        // }

        // Draw the vertex arrays
        window.draw(bufferZonesVertexArray);
        window.draw(agentArrowBodyVertexArray);
        window.draw(agentBodyVertexArray);
        window.draw(agentArrowHeadVertexArray);

        // Draw simulation canvas
        sf::RectangleShape canvas(sf::Vector2f(simulationWidth, simulationHeight));
        canvas.setPosition(offset);
        canvas.setFillColor(sf::Color::Transparent);
        canvas.setOutlineColor(sf::Color::Black);
        canvas.setOutlineThickness(2.0f);
        window.draw(canvas);

        // Draw the text elements
        if(showInfo) {
            window.draw(frameText);
            window.draw(frameRateText);
            window.draw(agentCountText);
            window.draw(timeText);
            window.draw(playbackSpeedText);
        }

        // Diagnostics remain legible above the moving road users.
        drawAggregationStatusPanels();

        // Draw buttons
        window.draw(pauseButton);
        window.draw(pauseButtonText);
        window.draw(resetButton);
        window.draw(resetButtonText);

        window.display();
    }
}

// Function to append agentBuffer zones to the vertex array
void Renderer::appendBufferZones(sf::VertexArray& vertices, const RenderAgent& agent) {

    // Calculate the number of segments depending on the agentBuffer zone radius
    int numSegments = std::max(100, static_cast<int>(agent.bufferZoneRadius * 6.0f));
    
    // Loop through each segment and calculate the position of the vertices
    for (int i = 0; i < numSegments; ++i) {
        float angle = 2 * M_PI * i / numSegments;
        sf::Vector2f radius(agent.bufferZoneRadius * std::cos(angle), agent.bufferZoneRadius * std::sin(angle));
        sf::Vector2f radius2((agent.bufferZoneRadius - 1) * std::cos(angle), agent.bufferZoneRadius * std::sin(angle));
        vertices.append(sf::Vertex({agent.position + offset + radius, agent.bufferZoneColor}));
        vertices.append(sf::Vertex({agent.position + offset + radius2, agent.bufferZoneColor}));
    }
}

// Function to append agent bodies to the vertex array
void Renderer::appendAgentBodies(sf::VertexArray& triangles, const RenderAgent& agent) {

    // Extract the type of the agent
    std::stringstream ss(agent.type);
    std::string word1, word2;
    ss >> word1 >> word2;

    sf::Vector2f position = agent.position + offset;
    float theta = std::atan2(agent.heading.y, agent.heading.x) * 180.0f / M_PI; // Convert to degrees
    sf::Angle thetaAngle = sf::degrees(theta);
    float minRadius = std::ceil(sin(M_PI/4) * agent.bodyRadius);
    float maxRadius = std::ceil(agent.bodyRadius);
    float divX, divY;

    // Determine the division factors for the agent body based on its type // TO-DO: all types?
    if(word2 == "Cyclist") {
        divX = 1;
        divY = 2;
    }
    else if(word2 == "E-Scooter") {
        divX = 1;
        divY = 2.5;
    }
    else if(word2 == "Cargo") {
        divX = 1;
        divY = 3;
    }
    else if(word2 == "Pedestrian") {
        divX = 1;
        divY = 1;
    }
    else {
        divX = 1;
        divY = 1;
    }

    // Calculate the positions of the quad vertices
    sf::Vector2f topLeft = sf::Vector2f(position.x - minRadius/divX, position.y - minRadius/divY);
    sf::Vector2f topRight = sf::Vector2f(position.x + minRadius/divX, position.y - minRadius/divY);
    sf::Vector2f bottomRight = sf::Vector2f(position.x + minRadius/divX, position.y + minRadius/divY);
    sf::Vector2f bottomLeft = sf::Vector2f(position.x - minRadius/divX, position.y + minRadius/divY);

    // Create the quad and transform it based on the agent's heading
    sf::VertexArray body(sf::PrimitiveType::Triangles, 6);

    // First triangle: topLeft, topRight, bottomRight
    body[0] = sf::Vertex({topLeft, agent.color});
    body[1] = sf::Vertex({bottomLeft, agent.color});
    body[2] = sf::Vertex({bottomRight, agent.color});
    
    // Second triangle: bottomRight, bottomLeft, topLeft
    body[3] = sf::Vertex({topLeft, agent.color});
    body[4] = sf::Vertex({topRight, agent.color});
    body[5] = sf::Vertex({bottomRight, agent.color});

    sf::Transform transform;
    // transform.rotate(theta, position); // Note: SFML 2.6.1 and prior
    transform.rotate(thetaAngle, position);

    // Apply the transformation to the quad vertices and append them to the vertex array
    for(int i = 0; i < 6; i++) {
        body[i].position = transform.transformPoint(body[i].position);
        triangles.append(body[i]);
    }
}