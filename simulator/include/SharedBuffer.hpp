#pragma once

#include <vector>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <iostream>
#include <optional>
#include <utility>

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
    SharedBuffer(std::string name, std::size_t capacity = 0);
    void write(const T& frame);
    T read();
    std::optional<T> tryRead();
    bool isDrained();
    void requestStop();
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
    std::size_t capacity;
    void promoteLocked();
    std::optional<T> popLocked();
    std::atomic<bool> finished = false;
};

#include "SharedBuffer.tpp"