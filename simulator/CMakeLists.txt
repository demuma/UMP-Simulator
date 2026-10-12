cmake_minimum_required(VERSION 3.10)  

# Set the project name
project(Simulator)

# Determine the Homebrew prefix based on the system architecture (for M4 Mac and Homebrew)
if(CMAKE_SYSTEM_PROCESSOR STREQUAL "arm64")
    set(HOMEBREW_PREFIX "/opt/homebrew/opt")
else()
    set(HOMEBREW_PREFIX "/usr/local/Cellar")
endif()

# Set the SFML_DIR to the path containing SFMLConfig.cmake
set(SFML_DIR "${HOMEBREW_PREFIX}/sfml/lib/cmake/SFML")

# Find SFML libraries
find_package(SFML 3.0.0 COMPONENTS Graphics Window System REQUIRED)
# find_package(SFML 2.5 COMPONENTS graphics window system REQUIRED)

# Find the libraries for yaml-cpp and MongoDB C++ driver
find_package(yaml-cpp REQUIRED)
find_package(mongocxx REQUIRED)
find_package(bsoncxx REQUIRED)

# Add the include directories for the libraries
include_directories(include)

# Add the source files to the executable
file(GLOB_RECURSE SOURCES "src/*.cpp")

# Create the executable
add_executable(Simulator ${SOURCES})

# Link libraries to the executable
# target_link_libraries(Simulator sfml-graphics sfml-window sfml-system yaml-cpp::yaml-cpp mongo::mongocxx_shared mongo::bsoncxx_shared) # for macOS
target_link_libraries(Simulator SFML::Graphics SFML::Window SFML::System yaml-cpp::yaml-cpp mongo::mongocxx_shared mongo::bsoncxx_shared) # for macOS SFML 3.0.0
#target_link_libraries(Simulator sfml-graphics sfml-window sfml-system uuid yaml-cpp mongo::mongocxx_shared mongo::bsoncxx_shared) # for Linux

# Additional CMake options for the executable
target_compile_features(Simulator PRIVATE cxx_std_17)

# Set the optimization level
target_compile_options(Simulator PRIVATE -O3)

# Define DEBUG macro when building in debug mode
# target_compile_definitions(Simulator PRIVATE DEBUG)
# target_compile_definitions(Simulator PRIVATE STATS)
# target_compile_definitions(Simulator PRIVATE ERROR)
# target_compile_definitions(Simulator PRIVATE TIMING)

# Opt-in integration test: creates and removes only a UUID-named test database.
option(UMP_BUILD_SENSOR_REGRESSION_TESTS "Build sensor regression tests (requires localhost MongoDB)" OFF)
if(UMP_BUILD_SENSOR_REGRESSION_TESTS)
    enable_testing()
    add_executable(SensorRegressionTests
        tests/SensorRegressionTests.cpp
        src/Sensor.cpp
        src/AgentBasedSensor.cpp
        src/GridBasedSensor.cpp
        src/AdaptiveGridBasedSensor.cpp
        src/Agent.cpp
        src/PerlinNoise.cpp
        src/Quadtree.cpp
        src/CollisionGrid.cpp
        src/CollisionAvoidance.cpp
        src/AggregationManager.cpp
        src/Utilities.cpp
    )
    target_compile_features(SensorRegressionTests PRIVATE cxx_std_17)
    target_link_libraries(SensorRegressionTests PRIVATE
        SFML::Graphics SFML::Window SFML::System
        mongo::mongocxx_shared mongo::bsoncxx_shared)
    add_test(NAME sensor_regression COMMAND SensorRegressionTests)
    set_tests_properties(sensor_regression PROPERTIES LABELS "integration;mongodb" TIMEOUT 30)
endif()
