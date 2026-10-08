#include "../include/ThreadPool.hpp"

// Constructor for the ThreadPool class
// This constructor initializes a thread pool with the specified number of worker threads.
ThreadPool::ThreadPool(size_t numThreads) : stop(false) {
    // Launch numThreads worker threads
    for (size_t i = 0; i < numThreads; ++i) {
        workers.emplace_back([this] {
            // Each worker thread runs an infinite loop to process tasks
            for (;;) {
                std::function<void()> task;
                {
                    // Lock the queue mutex to safely access the task queue
                    std::unique_lock<std::mutex> lock(this->queueMutex);

                    // Wait until there is a task to execute or the thread pool is stopped
                    this->condition.wait(lock, [this] { return this->stop || !this->tasks.empty(); });

                    // If the thread pool is stopped and there are no remaining tasks, exit the loop
                    if (this->stop && this->tasks.empty())
                        return;

                    // Retrieve the next task from the task queue
                    task = std::move(this->tasks.front());
                    this->tasks.pop();
                }

                // Execute the task outside of the lock to avoid blocking other threads
                task();
            }
        });
    }
}

// The destructor joins all threads
ThreadPool::~ThreadPool() {

    // Stop all threads
    {
        std::unique_lock<std::mutex> lock(queueMutex);
        stop = true;
    }

    // Notify all threads
    condition.notify_all();
    for (std::thread& worker : workers)
        worker.join();
}