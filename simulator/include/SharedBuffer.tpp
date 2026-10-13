#pragma once
#include "SharedBuffer.hpp"

template<class T>
SharedBuffer<T>::SharedBuffer(std::string name, std::size_t capacity)
    : writeBufferIndex(0), readBufferIndex(1), currentReadFrameIndex(0),
      currentWriteFrameIndex(0), name(std::move(name)), capacity(capacity) {
    currentReadBuffer.store(&buffers[1]);
    currentWriteBuffer.store(&buffers[0]);
}

template<class T>
void SharedBuffer<T>::write(const T& frame) {
    std::unique_lock<std::mutex> lock(queueMutex);
    queueCond.wait(lock, [this] {
        return finished.load() || stop.load() || capacity == 0
            || currentWriteFrameIndex.load() - currentReadFrameIndex.load() < capacity;
    });
    if (finished.load() || stop.load()) return;
    currentWriteBuffer.load()->push(frame);
    ++currentWriteFrameIndex;
    queueCond.notify_all();
}

template<class T>
void SharedBuffer<T>::promoteLocked() {
    if (!currentReadBuffer.load()->empty() || currentWriteBuffer.load()->empty()) return;
    const int previousRead = readBufferIndex.load();
    readBufferIndex.store(writeBufferIndex.load());
    writeBufferIndex.store(previousRead);
    currentReadBuffer.store(&buffers[readBufferIndex.load()]);
    currentWriteBuffer.store(&buffers[writeBufferIndex.load()]);
}

template<class T>
std::optional<T> SharedBuffer<T>::popLocked() {
    promoteLocked();
    auto& queue = *currentReadBuffer.load();
    if (queue.empty()) return std::nullopt;
    T frame = std::move(queue.front());
    queue.pop();
    ++currentReadFrameIndex;
    queueCond.notify_all();
    return frame;
}

template<class T>
T SharedBuffer<T>::read() {
    std::unique_lock<std::mutex> lock(queueMutex);
    queueCond.wait(lock, [this] {
        return finished.load() || stop.load() || !currentReadBuffer.load()->empty()
            || !currentWriteBuffer.load()->empty();
    });
    auto frame = popLocked();
    return frame ? std::move(*frame) : T{};
}

template<class T>
std::optional<T> SharedBuffer<T>::tryRead() {
    std::lock_guard<std::mutex> lock(queueMutex);
    return popLocked();
}

template<class T>
bool SharedBuffer<T>::isDrained() {
    std::lock_guard<std::mutex> lock(queueMutex);
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
    queueCond.notify_all();
}

template<class T>
void SharedBuffer<T>::requestStop() {
    std::lock_guard<std::mutex> lock(queueMutex);
    stop.store(true);
    queueCond.notify_all();
}
