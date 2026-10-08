#pragma once

#include <vector>
#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <functional>
#include <future>
#include <iostream>

#include "Agent.hpp"

/***************************************/
/********** THREAD POOL CLASS **********/
/***************************************/

class ThreadPool {
public:
    ThreadPool(size_t numThreads);
    ~ThreadPool();
    template <class F, class... Args>
    auto enqueue(F&& f, Args&&... args) -> std::future<typename std::invoke_result<F, Args...>::type>;
    
private:
    std::vector<std::thread> workers;
    std::queue<std::function<void()>> tasks;
    std::mutex queueMutex;
    std::condition_variable condition;
    bool stop;
};

// Enqueue a task into the thread pool and return a future to obtain the result
template <class F, class... Args>
auto ThreadPool::enqueue(F&& f, Args&&... args) -> std::future<typename std::invoke_result<F, Args...>::type> {
    
    // Determine the return type of the callable object
    using returnType = typename std::invoke_result<F, Args...>::type;
    
    // Create a shared pointer to a packaged_task that wraps the callable object
    // The packaged_task allows the task to be executed asynchronously and provides
    // a future to retrieve the result.
    auto task = std::make_shared<std::packaged_task<returnType()>>(std::bind(std::forward<F>(f), std::forward<Args>(args)...));
    
    // Get the future associated with the packaged task to return to the caller.
    std::future<returnType> res = task->get_future();
    
    // Add the task to the task queue
    {
        // Lock the mutex to ensure exclusive access to the task queue
        std::unique_lock<std::mutex> lock(queueMutex);

        // Check if the thread pool has been stopped; if so, throw an exception
        // to prevent adding new tasks to a stopped thread pool.
        if (stop)
            throw std::runtime_error("Enqueue on stopped ThreadPool");

        // Add the task to the queue as a lambda that will invoke the packaged_task
        tasks.emplace([task]() { (*task)(); });
    }
    
    // Notify one of the waiting threads that a new task is available
    condition.notify_one();
    
    // Return the future to the caller so they can obtain the result later
    return res;
}