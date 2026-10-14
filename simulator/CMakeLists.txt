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
        src/AggregationHistory.cpp
        src/Utilities.cpp
    )
    target_compile_features(SensorRegressionTests PRIVATE cxx_std_17)
    target_link_libraries(SensorRegressionTests PRIVATE
        SFML::Graphics SFML::Window SFML::System
        mongo::mongocxx_shared mongo::bsoncxx_shared)
    add_test(NAME sensor_regression COMMAND SensorRegressionTests)
    set_tests_properties(sensor_regression PROPERTIES LABELS "integration;mongodb" TIMEOUT 30)
endif()

option(UMP_BUILD_FRAME_TESTS "Build frame transport regression tests (no MongoDB/window)" ON)
if(UMP_BUILD_FRAME_TESTS)
    enable_testing()
    find_package(Threads REQUIRED)
    add_executable(FrameRegressionTests tests/FrameRegressionTests.cpp)
    target_compile_features(FrameRegressionTests PRIVATE cxx_std_17)
    target_link_libraries(FrameRegressionTests PRIVATE SFML::System Threads::Threads)
    add_test(NAME frame_regression COMMAND FrameRegressionTests)
    set_tests_properties(frame_regression PROPERTIES LABELS "unit;frames" TIMEOUT 15)
endif()

option(UMP_BUILD_AGGREGATION_TESTS "Build fixed aggregation core tests (standard C++ only)" ON)
if(UMP_BUILD_AGGREGATION_TESTS)
    enable_testing()
    add_executable(AggregationRegressionTests tests/AggregationRegressionTests.cpp src/AggregationManager.cpp src/AggregationHistory.cpp)
    target_compile_features(AggregationRegressionTests PRIVATE cxx_std_17)
    add_test(NAME aggregation_regression COMMAND AggregationRegressionTests)
    set_tests_properties(aggregation_regression PROPERTIES LABELS "unit;aggregation" TIMEOUT 15)
endif()

option(UMP_BUILD_METRIC_TESTS "Build candidate metric tests (standard C++ only)" ON)
if(UMP_BUILD_METRIC_TESTS)
    enable_testing()
    add_executable(MetricRegressionTests tests/MetricRegressionTests.cpp src/CandidateMetrics.cpp src/PolicyTree.cpp)
    target_compile_features(MetricRegressionTests PRIVATE cxx_std_17)
    add_test(NAME metric_regression COMMAND MetricRegressionTests)
    set_tests_properties(metric_regression PROPERTIES LABELS "unit;metrics" TIMEOUT 15)
endif()

option(UMP_BUILD_PLAYBACK_TESTS "Build playback clock and bounded replay tests (no window/database)" ON)
if(UMP_BUILD_PLAYBACK_TESTS)
    enable_testing()
    find_package(Threads REQUIRED)
    add_executable(PlaybackRegressionTests tests/PlaybackRegressionTests.cpp)
    target_compile_features(PlaybackRegressionTests PRIVATE cxx_std_17)
    target_link_libraries(PlaybackRegressionTests PRIVATE Threads::Threads)
    add_test(NAME playback_regression COMMAND PlaybackRegressionTests)
    set_tests_properties(playback_regression PROPERTIES LABELS "unit;playback" TIMEOUT 30)
endif()

option(UMP_BUILD_POLICY_TESTS "Build regional policy core and YAML adapter tests (no window/database)" ON)
if(UMP_BUILD_POLICY_TESTS)
    enable_testing()
    add_executable(PolicyRegressionTests tests/PolicyRegressionTests.cpp src/PolicyTree.cpp src/CandidateMetrics.cpp)
    target_compile_features(PolicyRegressionTests PRIVATE cxx_std_17)
    add_test(NAME policy_regression COMMAND PolicyRegressionTests)
    add_executable(PolicyConfigurationTests tests/PolicyConfigurationTests.cpp src/PolicyTree.cpp
        src/CandidateMetrics.cpp src/PolicyConfiguration.cpp src/AggregationConfiguration.cpp src/Region.cpp)
    target_compile_features(PolicyConfigurationTests PRIVATE cxx_std_17)
    target_link_libraries(PolicyConfigurationTests PRIVATE SFML::Graphics yaml-cpp::yaml-cpp)
    add_test(NAME policy_configuration COMMAND PolicyConfigurationTests)
    set_tests_properties(policy_regression policy_configuration PROPERTIES LABELS "unit;policies" TIMEOUT 15)
endif()

option(UMP_BUILD_HISTORY_TESTS "Build bounded history and logical bucket tests (standard C++ only)" ON)
if(UMP_BUILD_HISTORY_TESTS)
    enable_testing()
    add_executable(HistoryRegressionTests tests/HistoryRegressionTests.cpp src/AggregationHistory.cpp
        src/AggregationManager.cpp src/CandidateMetrics.cpp src/PolicyTree.cpp)
    target_compile_features(HistoryRegressionTests PRIVATE cxx_std_17)
    add_test(NAME history_regression COMMAND HistoryRegressionTests)
    set_tests_properties(history_regression PROPERTIES LABELS "unit;aggregation;history" TIMEOUT 15)
endif()

option(UMP_BUILD_SPATIAL_TESTS "Build fixed-window spatial selection tests (standard C++ only)" ON)
if(UMP_BUILD_SPATIAL_TESTS)
    enable_testing()
    add_executable(SpatialRegressionTests tests/SpatialRegressionTests.cpp src/SpatialSelection.cpp
        src/AggregationManager.cpp src/AggregationHistory.cpp src/CandidateMetrics.cpp src/PolicyTree.cpp)
    target_compile_features(SpatialRegressionTests PRIVATE cxx_std_17)
    add_test(NAME spatial_regression COMMAND SpatialRegressionTests)
    set_tests_properties(spatial_regression PROPERTIES LABELS "unit;aggregation;spatial" TIMEOUT 15)
endif()
