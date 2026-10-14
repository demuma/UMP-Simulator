#pragma once

#include <queue>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <iostream>
#include <optional>
#include <string>
#include <utility>

#include "Logging.hpp"

// Lossless FIFO transport between the simulation producer and one consuming renderer.
// T owns a complete agent or sensor frame; this queue is not a broadcast buffer.
// Both physical queues share one mutex and one total capacity. Swapping changes their
// roles only after the older read queue is empty, preserving chronological order.
// DEBUG_MSG traces lifecycle, backpressure, promotion and frame indices when DEBUG is set.
template<typename T>
class SharedBuffer {
public:
    // capacity == 0 keeps the legacy unbounded mode; normal renderer queues are bounded.
    SharedBuffer(std::string name, std::size_t capacity = 0);
    void write(const T& frame);       // Wait for capacity; ignore new writes after end/stop.
    T read();                        // Wait for data or shutdown; T{} means drained shutdown.
    std::optional<T> tryRead();       // Never wait for a measurement that may not exist.
    bool isDrained();                // Shutdown signalled AND both queues consumed.
    void requestStop();              // Wake blocked readers/writers; keep queued frames drainable.
    void swap();                     // Compatibility entry point: promote only if safe.
    void end();                      // Normal producer completion; drain both queues to EOF.

    // Legacy public diagnostics. Atomics permit counter inspection, not direct queue access.
    // Queue contents/pointer changes must remain under queueMutex via the methods above.
    std::atomic<std::queue<T>*> currentReadBuffer;
    std::atomic<std::queue<T>*> currentWriteBuffer;
    std::atomic<int> writeBufferIndex;
    std::atomic<int> readBufferIndex;
    std::atomic<size_t> currentReadFrameIndex;  // Total frames removed from both queues.
    std::atomic<size_t> currentWriteFrameIndex; // Total accepted writes; difference is occupancy.
    std::atomic<bool> stop = false;            // Use requestStop() so waiters are notified.
    std::string name;

private:
    std::queue<T> buffers[2];
    std::mutex queueMutex;
    std::condition_variable queueCond; // Data arrival, freed capacity and shutdown share this CV.
    std::size_t capacity;
    void promoteLocked();            // Caller owns queueMutex; never overtake unread frames.
    std::optional<T> popLocked();     // Caller owns queueMutex; pop once and wake writers.
    std::atomic<bool> finished = false;
};

#include "SharedBuffer.tpp"
