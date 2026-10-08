cmake_minimum_required(VERSION 3.10)  

# Set the project name
project(Visualizer)   

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

# Find the libraries for yaml-cpp and MongoDB C++ driver
find_package(yaml-cpp REQUIRED)
find_package(mongocxx REQUIRED)
find_package(bsoncxx REQUIRED)

# Add the include directories for the libraries
include_directories(include)

# Add the source files to the executable
file(GLOB_RECURSE SOURCES "src/*.cpp")

# Create the executable
add_executable(Visualizer ${SOURCES})

# Link libraries to the executable
target_link_libraries(Visualizer SFML::Graphics SFML::Window SFML::System yaml-cpp::yaml-cpp mongo::mongocxx_shared mongo::bsoncxx_shared) # for macOS SFML 3.0.0
#target_link_libraries(Simulator sfml-graphics sfml-window sfml-system uuid yaml-cpp mongo::mongocxx_shared mongo::bsoncxx_shared) # for Linux

# Additional CMake options for the executable
target_compile_features(Visualizer PRIVATE cxx_std_17)

# Set the optimization level
target_compile_options(Visualizer PRIVATE -O3)

# Define DEBUG macro when building in debug mode
# target_compile_definitions(Visualizer PRIVATE DEBUG)
target_compile_definitions(Visualizer PRIVATE STATS)
target_compile_definitions(Visualizer PRIVATE ERROR)
# target_compile_definitions(Visualizer PRIVATE TIMING)