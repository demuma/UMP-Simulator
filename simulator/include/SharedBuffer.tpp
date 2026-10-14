#pragma once
#include "SharedBuffer.hpp"

template<class T>
SharedBuffer<T>::SharedBuffer(std::string name, std::size_t capacity)
    : writeBufferIndex(0), readBufferIndex(1), currentReadFrameIndex(0),
      currentWriteFrameIndex(0), name(std::move(name)), capacity(capacity) {
    // Start with distinct, empty read/write queues; the first read promotes written data.
    currentReadBuffer.store(&buffers[1]);
    currentWriteBuffer.store(&buffers[0]);
    DEBUG_MSG("SharedBuffer " << this->name << ": initialized, write=0 read=1 capacity=" << capacity);
}

template<class T>
void SharedBuffer<T>::write(const T& frame) {
    std::unique_lock<std::mutex> lock(queueMutex);
    // Capacity covers BOTH queues. Waiting releases the mutex so the consumer can pop.
#ifdef DEBUG
    if (capacity && currentWriteFrameIndex.load() - currentReadFrameIndex.load() >= capacity)
        DEBUG_MSG("SharedBuffer " << name << ": waiting for capacity before frame " << currentWriteFrameIndex.load());
#endif
    queueCond.wait(lock, [this] {
        return finished.load() || stop.load() || capacity == 0
            || currentWriteFrameIndex.load() - currentReadFrameIndex.load() < capacity;
    });
    if (finished.load() || stop.load()) {
        DEBUG_MSG("SharedBuffer " << name << ": write rejected after end/stop");
        return;
    }
    DEBUG_MSG("SharedBuffer " << name << ": writing frame " << currentWriteFrameIndex.load()
        << " to buffer " << writeBufferIndex.load());
    currentWriteBuffer.load()->push(frame);
    ++currentWriteFrameIndex;
    queueCond.notify_all(); // A reader may be waiting on either physical queue.
}

template<class T>
void SharedBuffer<T>::promoteLocked() {
    // Never replace a nonempty read queue; doing so would reorder frames.
    if (!currentReadBuffer.load()->empty() || currentWriteBuffer.load()->empty()) return;
    const int previousRead = readBufferIndex.load();
    readBufferIndex.store(writeBufferIndex.load());
    writeBufferIndex.store(previousRead);
    currentReadBuffer.store(&buffers[readBufferIndex.load()]);
    currentWriteBuffer.store(&buffers[writeBufferIndex.load()]);
    DEBUG_MSG("SharedBuffer " << name << ": promoted read=" << readBufferIndex.load()
        << " write=" << writeBufferIndex.load());
}

template<class T>
std::optional<T> SharedBuffer<T>::popLocked() {
    promoteLocked(); // Also exposes the final write queue after end() or requestStop().
    auto& queue = *currentReadBuffer.load();
    if (queue.empty()) return std::nullopt;
    DEBUG_MSG("SharedBuffer " << name << ": reading frame " << currentReadFrameIndex.load()
        << " from buffer " << readBufferIndex.load());
    T frame = std::move(queue.front());
    queue.pop(); // A successful read consumes the frame exactly once.
    ++currentReadFrameIndex;
    queueCond.notify_all(); // Freed capacity lets a blocked producer continue.
    return frame;
}

template<class T>
T SharedBuffer<T>::read() {
    std::unique_lock<std::mutex> lock(queueMutex);
#ifdef DEBUG
    if (currentReadBuffer.load()->empty() && currentWriteBuffer.load()->empty()
        && !finished.load() && !stop.load())
        DEBUG_MSG("SharedBuffer " << name << ": waiting for frame " << currentReadFrameIndex.load());
#endif
    // Shutdown is in the predicate: an empty final queue must not leave a reader asleep.
    queueCond.wait(lock, [this] {
        return finished.load() || stop.load() || !currentReadBuffer.load()->empty()
            || !currentWriteBuffer.load()->empty();
    });
    auto frame = popLocked();
    if (!frame) DEBUG_MSG("SharedBuffer " << name << ": drained after end/stop");
    return frame ? std::move(*frame) : T{}; // Legacy blocking-read EOF convention.
}

template<class T>
std::optional<T> SharedBuffer<T>::tryRead() {
    std::lock_guard<std::mutex> lock(queueMutex);
    // Empty is normal between sensor measurements; avoid a log for every polling attempt.
    return popLocked();
}

template<class T>
bool SharedBuffer<T>::isDrained() {
    std::lock_guard<std::mutex> lock(queueMutex);
    // A temporarily empty live stream is not EOF.
    return (finished.load() || stop.load()) && currentReadBuffer.load()->empty()
        && currentWriteBuffer.load()->empty();
}

template<class T>
void SharedBuffer<T>::swap() {
    std::lock_guard<std::mutex> lock(queueMutex);
    promoteLocked();
    queueCond.notify_all();
}

template<class T>
void SharedBuffer<T>::end() {
    std::lock_guard<std::mutex> lock(queueMutex);
    finished.store(true);
    DEBUG_MSG("SharedBuffer " << name << ": producer finished, pending="
        << currentWriteFrameIndex.load() - currentReadFrameIndex.load());
    queueCond.notify_all(); // Wake readers waiting for data AND writers waiting for capacity.
}

template<class T>
void SharedBuffer<T>::requestStop() {
    std::lock_guard<std::mutex> lock(queueMutex);
    stop.store(true);
    DEBUG_MSG("SharedBuffer " << name << ": stop requested, pending="
        << currentWriteFrameIndex.load() - currentReadFrameIndex.load());
    queueCond.notify_all(); // Cancellation does not clear already accepted frames.
}
