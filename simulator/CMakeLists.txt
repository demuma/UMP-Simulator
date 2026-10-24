cmake_minimum_required(VERSION 3.12)

# Set the project name
project(Simulator)

# Keep editor diagnostics aligned with the compiler flags and dependency headers.
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

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

# Reusable semantic model shared by aggregation, metrics and release tests.
add_library(ump_semantic STATIC src/SemanticTaxonomy.cpp)
target_compile_features(ump_semantic PUBLIC cxx_std_17)
target_include_directories(ump_semantic PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)

# Add the source files to the executable
file(GLOB_RECURSE SOURCES "src/*.cpp")
list(REMOVE_ITEM SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/src/SemanticTaxonomy.cpp")

# Create the executable
add_executable(Simulator ${SOURCES})

# Link libraries to the executable
# target_link_libraries(Simulator sfml-graphics sfml-window sfml-system yaml-cpp::yaml-cpp mongo::mongocxx_shared mongo::bsoncxx_shared) # for macOS
target_link_libraries(Simulator PRIVATE SFML::Graphics SFML::Window SFML::System yaml-cpp::yaml-cpp mongo::mongocxx_shared mongo::bsoncxx_shared) # for macOS SFML 3.0.0
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

# Timestamp regression checks need BSON/SFML types but no database or window.
option(UMP_BUILD_TIMESTAMP_TESTS "Build ISO/UTC timestamp utility tests" ON)
if(UMP_BUILD_TIMESTAMP_TESTS)
    enable_testing()
    add_executable(UtilitiesRegressionTests tests/UtilitiesRegressionTests.cpp src/Utilities.cpp)
    target_compile_features(UtilitiesRegressionTests PRIVATE cxx_std_17)
    target_link_libraries(UtilitiesRegressionTests PRIVATE SFML::Graphics SFML::System mongo::bsoncxx_shared)
    add_test(NAME timestamp_utilities COMMAND UtilitiesRegressionTests)
    set_tests_properties(timestamp_utilities PROPERTIES LABELS "unit;timing" TIMEOUT 15)
endif()

# Opt-in integration test: creates and removes only a UUID-named test database.
option(UMP_BUILD_SENSOR_REGRESSION_TESTS "Build sensor regression tests (requires localhost MongoDB)" OFF)
if(UMP_BUILD_SENSOR_REGRESSION_TESTS)
    enable_testing()
    add_executable(SensorRegressionTests
        tests/SensorRegressionTests.cpp
        src/MappedScene.cpp
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
    add_executable(PolicyRegressionTests tests/PolicyRegressionTests.cpp src/PolicyTree.cpp src/CandidateMetrics.cpp
        src/CellLocalAggregation.cpp src/AdaptiveAggregation.cpp src/SpatialSelection.cpp src/AggregationHistory.cpp)
    target_compile_features(PolicyRegressionTests PRIVATE cxx_std_17)
    add_test(NAME policy_regression COMMAND PolicyRegressionTests)
    add_executable(PolicyConfigurationTests tests/PolicyConfigurationTests.cpp src/PolicyTree.cpp
        src/CandidateMetrics.cpp src/PolicyConfiguration.cpp src/AggregationConfiguration.cpp src/Region.cpp)
    target_compile_features(PolicyConfigurationTests PRIVATE cxx_std_17)
    target_link_libraries(PolicyConfigurationTests PRIVATE SFML::Graphics yaml-cpp::yaml-cpp)
    add_test(NAME policy_configuration COMMAND PolicyConfigurationTests)
    set_tests_properties(policy_regression policy_configuration PROPERTIES LABELS "unit;policies" TIMEOUT 15)
endif()

# No window or MongoDB connection; only BSON JSON serialization and temp files.
option(UMP_BUILD_DIAGNOSTIC_TESTS "Build aggregation diagnostic artifact tests" ON)
if(UMP_BUILD_DIAGNOSTIC_TESTS)
    enable_testing()
    add_executable(AggregationDiagnosticsTests tests/AggregationDiagnosticsTests.cpp
        src/AggregationDiagnostics.cpp src/Utilities.cpp src/CandidateMetrics.cpp src/PolicyTree.cpp
        src/SpatialSelection.cpp src/AggregationManager.cpp src/AggregationHistory.cpp)
    target_compile_features(AggregationDiagnosticsTests PRIVATE cxx_std_17)
    target_link_libraries(AggregationDiagnosticsTests PRIVATE ump_semantic SFML::Graphics
        SFML::Window SFML::System mongo::bsoncxx_shared)
    add_test(NAME aggregation_diagnostics COMMAND AggregationDiagnosticsTests)
    set_tests_properties(aggregation_diagnostics PROPERTIES LABELS "unit;aggregation;diagnostics" TIMEOUT 15)
endif()

option(UMP_BUILD_HISTORY_TESTS "Build bounded history and logical bucket tests (standard C++ only)" ON)
if(UMP_BUILD_HISTORY_TESTS)
    enable_testing()
    add_executable(HistoryRegressionTests tests/HistoryRegressionTests.cpp src/AggregationHistory.cpp
        src/AggregationManager.cpp src/CandidateMetrics.cpp src/PolicyTree.cpp)
    target_compile_features(HistoryRegressionTests PRIVATE cxx_std_17)
    add_test(NAME history_regression COMMAND HistoryRegressionTests)
    set_tests_properties(history_regression PROPERTIES LABELS "unit;aggregation;history" TIMEOUT 15)
    add_executable(OccupiedHistoryTests tests/OccupiedHistoryTests.cpp src/AggregationHistory.cpp)
    add_test(NAME occupied_history COMMAND OccupiedHistoryTests)
    set_tests_properties(occupied_history PROPERTIES LABELS "unit;aggregation;history;semantic" TIMEOUT 30)
    add_executable(HistoryQueryRangeTests tests/HistoryQueryRangeTests.cpp src/AggregationHistory.cpp)
    add_test(NAME history_query_range COMMAND HistoryQueryRangeTests)
    set_tests_properties(history_query_range PROPERTIES LABELS "unit;aggregation;history;semantic" TIMEOUT 30)
endif()

option(UMP_BUILD_SPATIAL_TESTS "Build fixed-window spatial selection tests (standard C++ only)" ON)
if(UMP_BUILD_SPATIAL_TESTS)
    enable_testing()
    add_executable(SpatialRegressionTests tests/SpatialRegressionTests.cpp src/SpatialSelection.cpp
        src/AggregationManager.cpp src/AggregationHistory.cpp src/CandidateMetrics.cpp src/PolicyTree.cpp)
    target_compile_features(SpatialRegressionTests PRIVATE cxx_std_17)
    add_test(NAME spatial_regression COMMAND SpatialRegressionTests)
    set_tests_properties(spatial_regression PROPERTIES LABELS "unit;aggregation;spatial" TIMEOUT 15)

    add_executable(SelectiveSuppressionRegressionTests tests/SelectiveSuppressionRegressionTests.cpp
        src/SpatialSelection.cpp src/AdaptiveAggregation.cpp src/CellLocalAggregation.cpp
        src/PublicationCoordinator.cpp src/AggregationManager.cpp src/AggregationHistory.cpp
        src/CandidateMetrics.cpp src/PolicyTree.cpp)
    target_compile_features(SelectiveSuppressionRegressionTests PRIVATE cxx_std_17)
    add_test(NAME selective_suppression_regression COMMAND SelectiveSuppressionRegressionTests)
    set_tests_properties(selective_suppression_regression PROPERTIES
        LABELS "unit;aggregation;spatial;publication" TIMEOUT 30)
endif()

option(UMP_BUILD_PUBLICATION_TESTS "Build fixed-window publication coordination tests (standard C++ only)" ON)
if(UMP_BUILD_PUBLICATION_TESTS)
    enable_testing()
    add_executable(PublicationRegressionTests tests/PublicationRegressionTests.cpp src/PublicationCoordinator.cpp
        src/SpatialSelection.cpp src/AggregationManager.cpp src/AggregationHistory.cpp
        src/CandidateMetrics.cpp src/PolicyTree.cpp)
    target_compile_features(PublicationRegressionTests PRIVATE cxx_std_17)
    add_test(NAME publication_regression COMMAND PublicationRegressionTests)
    set_tests_properties(publication_regression PROPERTIES LABELS "unit;aggregation;publication" TIMEOUT 15)
endif()

option(UMP_BUILD_ADAPTIVE_TESTS "Build temporal strategy tests (standard C++ only)" ON)
if(UMP_BUILD_ADAPTIVE_TESTS)
    enable_testing()
    add_executable(AdaptiveAggregationRegressionTests tests/AdaptiveAggregationRegressionTests.cpp
        src/AdaptiveAggregation.cpp src/SpatialSelection.cpp src/AggregationHistory.cpp
        src/AggregationManager.cpp src/CandidateMetrics.cpp src/PolicyTree.cpp)
    target_compile_features(AdaptiveAggregationRegressionTests PRIVATE cxx_std_17)
    add_test(NAME adaptive_aggregation_regression COMMAND AdaptiveAggregationRegressionTests)
    set_tests_properties(adaptive_aggregation_regression PROPERTIES LABELS "unit;aggregation;temporal" TIMEOUT 30)
endif()

# Opt-in MongoDB publication tests create and remove only fresh UUID databases.
option(UMP_BUILD_PUBLICATION_STORE_TESTS "Build durable publication tests (requires localhost MongoDB)" OFF)
if(UMP_BUILD_PUBLICATION_STORE_TESTS)
    enable_testing()
    add_executable(PublicationStoreRegressionTests tests/PublicationStoreRegressionTests.cpp src/PublicationStore.cpp)
    target_compile_features(PublicationStoreRegressionTests PRIVATE cxx_std_17)
    target_link_libraries(PublicationStoreRegressionTests PRIVATE mongo::mongocxx_shared mongo::bsoncxx_shared)
    add_test(NAME publication_store_regression COMMAND PublicationStoreRegressionTests)
    set_tests_properties(publication_store_regression PROPERTIES LABELS "integration;mongodb;publication" TIMEOUT 60)
endif()

if(UMP_BUILD_PUBLICATION_STORE_TESTS)
    add_executable(PublicationPipelineRegressionTests tests/PublicationPipelineRegressionTests.cpp
        src/PublicationStore.cpp src/PublicationCoordinator.cpp src/AdaptiveAggregation.cpp
        src/AggregationManager.cpp src/AggregationHistory.cpp src/SpatialSelection.cpp
        src/CandidateMetrics.cpp src/PolicyTree.cpp)
    target_compile_features(PublicationPipelineRegressionTests PRIVATE cxx_std_17)
    target_link_libraries(PublicationPipelineRegressionTests PRIVATE mongo::mongocxx_shared mongo::bsoncxx_shared)
    add_test(NAME publication_pipeline_regression COMMAND PublicationPipelineRegressionTests)
    set_tests_properties(publication_pipeline_regression PROPERTIES LABELS "integration;mongodb;publication;temporal" TIMEOUT 60)
endif()

if(UMP_BUILD_FRAME_TESTS)
    add_executable(AggregationPresentationTests tests/AggregationPresentationTests.cpp)
    target_compile_features(AggregationPresentationTests PRIVATE cxx_std_17)
    add_test(NAME aggregation_presentation COMMAND AggregationPresentationTests)
    set_tests_properties(aggregation_presentation PROPERTIES LABELS "unit;frames;presentation" TIMEOUT 15)
endif()

# Offline research adapter: same decision cores, no MongoDB or renderer at runtime.
option(UMP_BUILD_REPLAY "Build frozen observation replay and evaluation tests" ON)
if(UMP_BUILD_REPLAY)
    find_package(Threads REQUIRED)
    set(UMP_REPLAY_CORE_SOURCES
        src/AggregationManager.cpp src/AggregationHistory.cpp src/CandidateMetrics.cpp
        src/PolicyTree.cpp src/SpatialSelection.cpp src/AdaptiveAggregation.cpp src/CellLocalAggregation.cpp
        src/PublicationCoordinator.cpp src/AggregationConfiguration.cpp src/PolicyConfiguration.cpp)
    add_executable(AggregationReplay tools/AggregationReplay.cpp ${UMP_REPLAY_CORE_SOURCES})
    target_compile_features(AggregationReplay PRIVATE cxx_std_17)
    target_compile_options(AggregationReplay PRIVATE -O3)
    target_link_libraries(AggregationReplay PRIVATE SFML::Graphics yaml-cpp::yaml-cpp Threads::Threads)

    enable_testing()
    add_executable(PacedReplayTests tests/PacedReplayTests.cpp)
    target_compile_features(PacedReplayTests PRIVATE cxx_std_17)
    target_link_libraries(PacedReplayTests PRIVATE Threads::Threads)
    add_test(NAME paced_replay COMMAND PacedReplayTests)
    set_tests_properties(paced_replay PROPERTIES LABELS "unit;replay;timing" TIMEOUT 15)
    add_executable(ReplayRegressionTests tests/ReplayRegressionTests.cpp ${UMP_REPLAY_CORE_SOURCES})
    target_compile_features(ReplayRegressionTests PRIVATE cxx_std_17)
    target_link_libraries(ReplayRegressionTests PRIVATE SFML::Graphics yaml-cpp::yaml-cpp Threads::Threads)
    add_test(NAME replay_regression COMMAND ReplayRegressionTests)
    set_tests_properties(replay_regression PROPERTIES LABELS "unit;replay;evaluation" TIMEOUT 30)
    find_package(Python3 3.9 COMPONENTS Interpreter REQUIRED)
    add_test(NAME live_measurement_helpers COMMAND ${Python3_EXECUTABLE} -m unittest discover
        -s ${CMAKE_CURRENT_SOURCE_DIR}/../tools/profiling/live -p "test_live*.py")
    set_tests_properties(live_measurement_helpers PROPERTIES LABELS "unit;timing"
        ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1" TIMEOUT 15)
    add_test(NAME paced_replay_summary COMMAND ${Python3_EXECUTABLE} -m unittest discover
        -s ${CMAKE_CURRENT_SOURCE_DIR}/../tools/profiling -p test_summarize_paced_replay.py)
    set_tests_properties(paced_replay_summary PROPERTIES LABELS "unit;replay;timing"
        ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1" TIMEOUT 15)
    foreach(evaluation occupancy privacy comparison capture oracle privacy_dataset empirical_privacy privacy_study coordination coordination_metrics coordination_scenarios coordination_study plot_coordination_study
        compare_coordination_studies plot_privacy_coordination robustness_attacks run_privacy_robustness plot_privacy_robustness privacy_repair causal_privacy online_occupancy run_privacy_prefix_study selective_suppression semantic_adaptation semantic_tradeoffs semantic_queries scoped_semantic_queries run_scoped_semantic_utility recipient_support run_recipient_contract_study run_semantic_priority_study semantic_first moving_comparison moving_scoped_audit run_moving_scoped_comparison cell_size_caps four_second_window semantic_release local_policy_replay semantic_local_policy semantic_suppression_audit run_suppression_study replay_data)
        add_test(NAME ${evaluation}_evaluation COMMAND ${Python3_EXECUTABLE} -m unittest discover
            -s ${CMAKE_CURRENT_SOURCE_DIR}/../tools/evaluation -p test_${evaluation}.py)
        set_tests_properties(${evaluation}_evaluation PROPERTIES LABELS "unit;evaluation"
            ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1;UMP_REPLAY_BINARY=$<TARGET_FILE:AggregationReplay>" TIMEOUT 30)
        if(evaluation STREQUAL "privacy_study" OR evaluation STREQUAL "coordination" OR evaluation STREQUAL "coordination_study" OR evaluation STREQUAL "run_privacy_robustness" OR evaluation STREQUAL "privacy_repair" OR evaluation STREQUAL "run_privacy_prefix_study" OR evaluation STREQUAL "selective_suppression")
            set_tests_properties(${evaluation}_evaluation PROPERTIES TIMEOUT 120)
        endif()
    endforeach()
    add_test(NAME replay_viewer_evaluation COMMAND ${Python3_EXECUTABLE} -m unittest discover
        -s ${CMAKE_CURRENT_SOURCE_DIR}/../tools/replay_viewer -p test_viewer.py)
    set_tests_properties(replay_viewer_evaluation PROPERTIES LABELS "unit;evaluation;viewer"
        ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1" TIMEOUT 30)
    add_test(NAME replay_viewer_compact_projection COMMAND ${Python3_EXECUTABLE} -m unittest discover
        -s ${CMAKE_CURRENT_SOURCE_DIR}/../tools/replay_viewer -p test_compact_bundle.py)
    set_tests_properties(replay_viewer_compact_projection PROPERTIES LABELS "unit;evaluation;viewer"
        ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1" TIMEOUT 30)
    find_program(UMP_NODE_EXECUTABLE node)
    if(UMP_NODE_EXECUTABLE)
        add_test(NAME replay_viewer_model COMMAND ${UMP_NODE_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/../tools/replay_viewer/test_model.js)
        set_tests_properties(replay_viewer_model PROPERTIES LABELS "unit;viewer" TIMEOUT 30)
    endif()
endif()

# Cell-local space-time coordination and scoped recipient retirement.
option(UMP_BUILD_COORDINATION_TESTS "Build independent cell-local coordination regressions" ON)
if(UMP_BUILD_COORDINATION_TESTS)
    enable_testing()
    add_executable(CoordinationRegressionTests tests/CoordinationRegressionTests.cpp
        src/CellLocalAggregation.cpp src/AdaptiveAggregation.cpp src/SpatialSelection.cpp
        src/AggregationHistory.cpp src/CandidateMetrics.cpp src/PolicyTree.cpp)
    target_compile_features(CoordinationRegressionTests PRIVATE cxx_std_17)
    add_test(NAME cell_local_coordination COMMAND CoordinationRegressionTests)
    set_tests_properties(cell_local_coordination PROPERTIES LABELS "unit;aggregation;coordination" TIMEOUT 60)
    add_executable(CoordinationStressTests tests/CoordinationStressTests.cpp
        src/CellLocalAggregation.cpp src/AdaptiveAggregation.cpp src/SpatialSelection.cpp
        src/AggregationHistory.cpp src/CandidateMetrics.cpp src/PolicyTree.cpp)
    target_compile_features(CoordinationStressTests PRIVATE cxx_std_17)
    add_test(NAME cell_local_coordination_stress COMMAND CoordinationStressTests)
    set_tests_properties(cell_local_coordination_stress PROPERTIES LABELS "unit;aggregation;coordination;stress" TIMEOUT 60)
    add_executable(ScopedPublicationRegressionTests tests/ScopedPublicationRegressionTests.cpp
        src/PublicationCoordinator.cpp src/AggregationHistory.cpp src/CandidateMetrics.cpp src/PolicyTree.cpp)
    target_compile_features(ScopedPublicationRegressionTests PRIVATE cxx_std_17)
    add_test(NAME scoped_publication COMMAND ScopedPublicationRegressionTests)
    set_tests_properties(scoped_publication PROPERTIES LABELS "unit;publication;coordination" TIMEOUT 30)
endif()


# Sequential semantic adaptation acceptance gates; no window/database for core tests.
if(UMP_BUILD_METRIC_TESTS AND UMP_BUILD_SPATIAL_TESTS)
    add_executable(SemanticTaxonomyTests tests/SemanticTaxonomyTests.cpp)
    add_test(NAME semantic_taxonomy COMMAND SemanticTaxonomyTests)
    add_executable(SemanticHistoryTests tests/SemanticHistoryTests.cpp
        src/AggregationHistory.cpp src/AggregationManager.cpp)
    add_test(NAME semantic_history COMMAND SemanticHistoryTests)
    add_executable(SemanticPipelineTests tests/SemanticPipelineTests.cpp
        src/AggregationManager.cpp src/AggregationHistory.cpp src/CandidateMetrics.cpp
        src/PolicyTree.cpp src/SpatialSelection.cpp src/AdaptiveAggregation.cpp
        src/PublicationCoordinator.cpp)
    add_test(NAME semantic_pipeline COMMAND SemanticPipelineTests)
    add_executable(SemanticSuppressionTests tests/SemanticSuppressionTests.cpp
        src/AggregationManager.cpp src/AggregationHistory.cpp src/CandidateMetrics.cpp
        src/PolicyTree.cpp src/SpatialSelection.cpp src/AdaptiveAggregation.cpp
        src/CellLocalAggregation.cpp src/PublicationCoordinator.cpp)
    add_test(NAME semantic_suppression COMMAND SemanticSuppressionTests)
    set_tests_properties(semantic_suppression PROPERTIES LABELS "unit;aggregation;semantic;suppression" TIMEOUT 30)
    add_executable(SemanticFirstTests tests/SemanticFirstTests.cpp
        src/AdaptiveAggregation.cpp src/SpatialSelection.cpp src/AggregationHistory.cpp
        src/CandidateMetrics.cpp src/PolicyTree.cpp src/PublicationCoordinator.cpp)
    add_test(NAME semantic_first_core COMMAND SemanticFirstTests)
    set_tests_properties(semantic_first_core PROPERTIES LABELS "unit;aggregation;semantic" TIMEOUT 30)
    if(UMP_BUILD_COORDINATION_TESTS)
        add_executable(SemanticCellLocalTests tests/SemanticCellLocalTests.cpp
            src/CellLocalAggregation.cpp src/AdaptiveAggregation.cpp src/SpatialSelection.cpp
            src/AggregationHistory.cpp src/CandidateMetrics.cpp src/PolicyTree.cpp
            src/PublicationCoordinator.cpp)
        add_test(NAME semantic_cell_local COMMAND SemanticCellLocalTests)
        set_tests_properties(semantic_cell_local PROPERTIES LABELS "unit;aggregation;semantic;coordination" TIMEOUT 60)
    endif()
    set_tests_properties(semantic_taxonomy semantic_history semantic_pipeline PROPERTIES
        LABELS "unit;aggregation;semantic" TIMEOUT 30)
endif()

if(UMP_BUILD_PUBLICATION_STORE_TESTS)
    add_executable(SemanticPublicationStoreTests tests/SemanticPublicationStoreTests.cpp src/PublicationStore.cpp
        src/AdaptiveAggregation.cpp src/AggregationManager.cpp src/AggregationHistory.cpp src/CandidateMetrics.cpp
        src/PolicyTree.cpp src/SpatialSelection.cpp src/PublicationCoordinator.cpp)
    target_link_libraries(SemanticPublicationStoreTests PRIVATE mongo::mongocxx_shared mongo::bsoncxx_shared)
    add_test(NAME semantic_publication_store COMMAND SemanticPublicationStoreTests)
    set_tests_properties(semantic_publication_store PROPERTIES LABELS "integration;mongodb;semantic" TIMEOUT 60)
endif()

foreach(core_target Simulator SensorRegressionTests AggregationRegressionTests MetricRegressionTests
    PolicyRegressionTests PolicyConfigurationTests HistoryRegressionTests OccupiedHistoryTests HistoryQueryRangeTests SpatialRegressionTests
    SelectiveSuppressionRegressionTests PublicationRegressionTests AdaptiveAggregationRegressionTests
    PublicationStoreRegressionTests PublicationPipelineRegressionTests AggregationPresentationTests
    AggregationReplay ReplayRegressionTests CoordinationRegressionTests CoordinationStressTests
    ScopedPublicationRegressionTests SemanticTaxonomyTests SemanticHistoryTests SemanticPipelineTests
    SemanticPublicationStoreTests SemanticFirstTests SemanticCellLocalTests SemanticSuppressionTests)
    if(TARGET ${core_target})
        target_compile_features(${core_target} PRIVATE cxx_std_17)
        target_link_libraries(${core_target} PRIVATE ump_semantic)
    endif()
endforeach()

# Standard-C++ mapped source + strict YAML adaptation; no DB/window in these tests.
option(UMP_BUILD_MAPPED_SCENE_TESTS "Build mapped route, lifecycle, identity and semantic tests" ON)
if(UMP_BUILD_MAPPED_SCENE_TESTS)
    enable_testing()
    add_executable(MappedSceneTests tests/MappedSceneTests.cpp src/MappedScene.cpp)
    target_compile_features(MappedSceneTests PRIVATE cxx_std_17)
    add_test(NAME mapped_scene COMMAND MappedSceneTests)
    add_executable(MappedSceneConfigurationTests tests/MappedSceneConfigurationTests.cpp
        src/MappedScene.cpp src/MappedSceneConfiguration.cpp)
    target_compile_features(MappedSceneConfigurationTests PRIVATE cxx_std_17)
    target_link_libraries(MappedSceneConfigurationTests PRIVATE yaml-cpp::yaml-cpp)
    add_test(NAME mapped_scene_configuration COMMAND MappedSceneConfigurationTests)
    # Aggregate-only finite motion probe; never writes track IDs or motion data.
    add_executable(MappedMotionProbe tests/MappedMotionProbe.cpp
        src/MappedScene.cpp src/MappedSceneConfiguration.cpp)
    target_compile_features(MappedMotionProbe PRIVATE cxx_std_17)
    target_link_libraries(MappedMotionProbe PRIVATE yaml-cpp::yaml-cpp)
    # Standard-library contract checks stay available without the map-tool venv.
    if(NOT Python3_EXECUTABLE)
        find_package(Python3 3.9 COMPONENTS Interpreter QUIET)
    endif()
    if(Python3_EXECUTABLE)
        add_test(NAME mapped_motion_probe_contract COMMAND "${Python3_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/../tools/mapped_scene/test_motion_probe.py")
        set_tests_properties(mapped_motion_probe_contract PROPERTIES
            LABELS "unit;mapped_scene;tools" TIMEOUT 15
            ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1;UMP_MAPPED_MOTION_PROBE_BINARY=$<TARGET_FILE:MappedMotionProbe>")
    endif()
    add_executable(MappedPedestrianSemanticTests tests/MappedPedestrianSemanticTests.cpp)
    target_compile_features(MappedPedestrianSemanticTests PRIVATE cxx_std_17)
    target_link_libraries(MappedPedestrianSemanticTests PRIVATE ump_semantic)
    add_test(NAME mapped_pedestrian_semantics COMMAND MappedPedestrianSemanticTests)
    set_tests_properties(mapped_scene mapped_scene_configuration mapped_pedestrian_semantics
        PROPERTIES LABELS "unit;mapped_scene" TIMEOUT 15)
endif()

# Optional Python environment for the mapped recorder/geometry tools. Dependencies
# are isolated from the normal simulator build; see tools/mapped_scene/requirements.txt.
set(UMP_MAPPED_SCENE_PYTHON "" CACHE FILEPATH "Python with mapped-scene requirements for recorder/tool tests")
if(UMP_BUILD_MAPPED_SCENE_TESTS AND UMP_MAPPED_SCENE_PYTHON)
    if(NOT EXISTS "${UMP_MAPPED_SCENE_PYTHON}")
        message(FATAL_ERROR "UMP_MAPPED_SCENE_PYTHON does not exist")
    endif()
    foreach(mapped_test audit_building_access build_mapped_scene storefront_router transit_access export_replay analyze_tracks run_comparison plot_policy_comparison plot_spatial_portfolio)
        if(mapped_test STREQUAL "build_mapped_scene")
            # Keep geometry/config checks fast. Native finite-drain cases have
            # separate budgets below, independent of inherited shell settings.
            add_test(NAME mapped_${mapped_test}_tools COMMAND "${CMAKE_COMMAND}" -E env
                --unset=UMP_MAPPED_CORE_TEST_BINARY "${UMP_MAPPED_SCENE_PYTHON}"
                "${CMAKE_CURRENT_SOURCE_DIR}/../tools/mapped_scene/test_${mapped_test}.py")
        else()
            add_test(NAME mapped_${mapped_test}_tools COMMAND "${UMP_MAPPED_SCENE_PYTHON}"
                "${CMAKE_CURRENT_SOURCE_DIR}/../tools/mapped_scene/test_${mapped_test}.py")
        endif()
        set_tests_properties(mapped_${mapped_test}_tools PROPERTIES
            LABELS "unit;mapped_scene;tools" TIMEOUT 60
            ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1;UMP_REPLAY_BINARY=$<TARGET_FILE:AggregationReplay>;UMP_MAPPED_CORE_TEST_BINARY=$<TARGET_FILE:MappedSceneConfigurationTests>")
    endforeach()
    # The seeded multi-geometry suite takes about 53 s in isolation; allow
    # bounded headroom for parallel CI without including native drainage here.
    set_tests_properties(mapped_build_mapped_scene_tools PROPERTIES TIMEOUT 120)
    # Includes the opt-in mixed traffic mode-space and legacy topology regressions.
    set_tests_properties(mapped_storefront_router_tools PROPERTIES TIMEOUT 120)
    add_test(NAME mapped_transit_access_drain_tools COMMAND "${UMP_MAPPED_SCENE_PYTHON}"
        "${CMAKE_CURRENT_SOURCE_DIR}/../tools/mapped_scene/test_transit_access.py"
        TransitAccessTests.test_native_combined_source_drains_and_all_tracks_are_observed)
    set_tests_properties(mapped_transit_access_drain_tools PROPERTIES
        LABELS "integration;mapped_scene;tools" TIMEOUT 150 RUN_SERIAL TRUE
        ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1;UMP_TRANSIT_DRAIN_TEST_BINARY=$<TARGET_FILE:MappedSceneConfigurationTests>")
    add_test(NAME mapped_dense_corridor_drain_tools COMMAND "${UMP_MAPPED_SCENE_PYTHON}"
        "${CMAKE_CURRENT_SOURCE_DIR}/../tools/mapped_scene/test_build_mapped_scene.py"
        MappedSceneGeneratorTests.test_dense_corridor_native_config_drains_without_dropped_tracks)
    add_test(NAME mapped_building_drain_tools COMMAND "${UMP_MAPPED_SCENE_PYTHON}"
        "${CMAKE_CURRENT_SOURCE_DIR}/../tools/mapped_scene/test_build_mapped_scene.py"
        MappedSceneGeneratorTests.test_building_native_sources_drain_without_lost_tracks_or_overlap)
    add_test(NAME mapped_storefront_drain_tools COMMAND "${UMP_MAPPED_SCENE_PYTHON}"
        "${CMAKE_CURRENT_SOURCE_DIR}/../tools/mapped_scene/test_build_mapped_scene.py"
        MappedSceneGeneratorTests.test_storefront_native_sources_drain_without_lost_tracks_or_overlap)
    add_test(NAME mapped_urban_traffic_drain_tools COMMAND "${UMP_MAPPED_SCENE_PYTHON}"
        "${CMAKE_CURRENT_SOURCE_DIR}/../tools/mapped_scene/test_build_mapped_scene.py"
        MappedSceneGeneratorTests.test_urban_traffic_native_source_drains_without_lost_tracks_or_overlap)
    set_tests_properties(mapped_dense_corridor_drain_tools mapped_building_drain_tools mapped_storefront_drain_tools mapped_urban_traffic_drain_tools PROPERTIES
        LABELS "integration;mapped_scene;drain" RUN_SERIAL TRUE
        ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1;UMP_MAPPED_CORE_TEST_BINARY=$<TARGET_FILE:MappedSceneConfigurationTests>")
    set_tests_properties(mapped_dense_corridor_drain_tools PROPERTIES TIMEOUT 150)
    set_tests_properties(mapped_building_drain_tools PROPERTIES TIMEOUT 300)
    set_tests_properties(mapped_storefront_drain_tools PROPERTIES TIMEOUT 420)
    set_tests_properties(mapped_urban_traffic_drain_tools PROPERTIES TIMEOUT 300)
endif()
