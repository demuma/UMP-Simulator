#pragma once

#include <vector>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <iostream>

#include "Agent.hpp"
#include "Logging.hpp"

/*****************************************/
/********** SHARED BUFFER CLASS **********/
/*****************************************/

/*

Shared buffer class for inter-thread communication

Template class for different types: 
- agent data
- adaptive grid data using a quadtree structure

*/


template<typename T>
class SharedBuffer {
public:
    SharedBuffer(std::string name);
    void write(const T& frame);
    T read();
    void swap();
    void end();
    std::atomic<std::queue<T>*> currentReadBuffer;
    std::atomic<std::queue<T>*> currentWriteBuffer;
    std::atomic<int> writeBufferIndex;
    std::atomic<int> readBufferIndex;
    std::atomic<size_t> currentReadFrameIndex;
    std::atomic<size_t> currentWriteFrameIndex;
    std::atomic<bool> stop = false;
    std::string name;

private:
    std::queue<T> buffers[2];
    std::mutex queueMutex;
    std::condition_variable queueCond;
    T currentFrame;
    std::atomic<bool> finished = false;
};

#include "SharedBuffer.tpp"