#include <SFML/Graphics.hpp>
#include <thread>
#include <yaml-cpp/yaml.h>
#include <iostream>
#include <atomic>

#include "../include/SharedBuffer.hpp"
// #include "../include/QuadtreeSnapshot.hpp"
#include "../include/Simulation.hpp"
#include "../include/Renderer.hpp"
#include "../include/Logging.hpp"
#include "../include/Sensor.hpp"

/**************************/
/********** MAIN **********/
/**************************/

// Main function
int main() {

    // Loading configuration file
    YAML::Node config;
    try {
        config = YAML::LoadFile("config.yaml");
    } catch (const YAML::Exception& e) {
        // Startup failures must remain visible independently of optional logging macros.
        std::cerr << "Error loading config.yaml: " << e.what() << '\n'
                  << "Run from the simulator directory: cd simulator && ./build/Simulator\n";
        return 1;
    }

    // A run-stable ID maps database metadata, samples and render instances to one sensor.
    std::unordered_set<std::string> sensorIds;
    for (auto sensor : config["sensors"]) {
        if (!sensor["id"]) sensor["id"] = generateUUID();
        const auto id = sensor["id"].as<std::string>();
        if (id.empty() || !sensorIds.insert(id).second) {
            std::cerr << "Sensor IDs must be nonempty and unique.\n";
            return 1;
        }
    }

    // Shared buffers for agent data
    // SharedBuffer<std::vector<Agent>> agentBuffer;
    // SharedBuffer<std::shared_ptr<const std::vector<Agent>>> agentBuffer("Agents");
    const auto bufferCapacity = config["renderer"]["buffer_capacity"].as<std::size_t>(128);
    if (bufferCapacity == 0) {
        std::cerr << "renderer.buffer_capacity must be greater than zero.\n";
        return 1;
    }
    SharedBuffer<agentBufferFrameType> agentBuffer("Agents", bufferCapacity);
    
    // Shared buffers for sensor data
    // std::unordered_map<std::string,std::shared_ptr<SharedBuffer<std::shared_ptr<QuadtreeSnapshot::Node>>>> sensorBuffers;
    // SharedBuffer<std::unordered_map<std::string, std::vector<int>>> sensorBuffer;
    SharedBuffer<sensorBufferFrameType> sensorBuffer("Sensors", bufferCapacity);

    // Load global configuration data
    bool enableRendering = config["renderer"]["show_renderer"].as<bool>();

    try {
        // Reject invalid playback settings before constructing Simulation and its DB sink.
        if (enableRendering) ump::PlaybackClock::period(config["simulation"]["time_step"].as<float>(),
            config["simulation"]["playback_speed"].as<double>());
        Simulation simulation(agentBuffer, sensorBuffer, config);
        if (enableRendering) {
            // Construct the window before starting a producer that may wait on a full queue.
            Renderer renderer(agentBuffer, sensorBuffer, config);
            std::exception_ptr simulationError;
            std::thread simulationThread([&] {
                try { simulation.run(); }
                catch (...) {
                    simulationError = std::current_exception();
                    agentBuffer.end();
                    sensorBuffer.end();
                }
            });
            try { renderer.run(); }
            catch (...) {
                agentBuffer.requestStop();
                sensorBuffer.requestStop();
                simulationThread.join();
                throw;
            }
            agentBuffer.requestStop();
            sensorBuffer.requestStop();
            simulationThread.join();
            if (simulationError) std::rethrow_exception(simulationError);
        } else {
            simulation.run();
        }
    } catch (const std::exception& error) {
        std::cerr << "Simulation failed: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
