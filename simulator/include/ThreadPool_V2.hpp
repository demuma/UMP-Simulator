// #pragma once

// #include <vector>
// #include <queue>
// #include <thread>
// #include <mutex>
// #include <condition_variable>
// #include <functional>
// #include <future>
// #include <iostream>
// #include <type_traits>
// #include <tuple>

// /***************************************/
// /********** THREAD POOL CLASS **********/
// /***************************************/

// class ThreadPool {
// public:
//     explicit ThreadPool(size_t numThreads = std::thread::hardware_concurrency());
//     ~ThreadPool();

//     // Submit a single task and get its future
//     template <class F, class... Args>
//     auto enqueue(F&& f, Args&&... args)
//         -> std::future<std::invoke_result_t<F, Args...>>;

//     // Submit multiple *nullary* callables at once (batch enqueue)
//     // e.g. std::vector<std::function<void()>> jobs;
//     template <class Container>
//     auto enqueue_bulk(Container&& callables)
//         -> std::vector<std::future<
//             std::invoke_result_t<typename std::decay_t<Container>::value_type&>
//         >>;

//     size_t size() const noexcept { return workers.size(); }

// private:
//     std::vector<std::thread> workers;
//     std::queue<std::function<void()>> tasks;

//     std::mutex queueMutex;
//     std::condition_variable condition;
//     bool stop;
// };

// /*******************************************/
// /************ TEMPLATE METHODS *************/
// /*******************************************/

// // Enqueue a single task and return a future
// template <class F, class... Args>
// auto ThreadPool::enqueue(F&& f, Args&&... args)
//     -> std::future<std::invoke_result_t<F, Args...>>
// {
//     using return_type = std::invoke_result_t<F, Args...>;

//     auto task = std::make_shared<std::packaged_task<return_type()>>(
//         [fn  = std::forward<F>(f),
//          tup = std::make_tuple(std::forward<Args>(args)...)
//         ]() mutable {
//             return std::apply(std::move(fn), std::move(tup));
//         }
//     );

//     std::future<return_type> res = task->get_future();
//     {
//         std::unique_lock<std::mutex> lock(queueMutex);
//         if (stop)
//             throw std::runtime_error("enqueue on stopped ThreadPool");
//         tasks.emplace([task]{ (*task)(); });
//     }
//     condition.notify_one();
//     return res;
// }

// // Enqueue a batch of *nullary* callables (like lambdas with no args)
// template <class Container>
// auto ThreadPool::enqueue_bulk(Container&& callables)
//     -> std::vector<std::future<
//         std::invoke_result_t<typename std::decay_t<Container>::value_type&>
//     >>
// {
//     using Callable = typename std::decay_t<Container>::value_type;
//     using Return   = std::invoke_result_t<Callable&>;

//     std::vector<std::future<Return>> futures;
//     futures.reserve(std::size(callables));

//     {
//         std::unique_lock<std::mutex> lock(queueMutex);
//         if (stop)
//             throw std::runtime_error("enqueue_bulk on stopped ThreadPool");

//         for (auto&& c : callables) {
//             auto task = std::make_shared<std::packaged_task<Return()>>(
//                 std::forward<Callable>(c)
//             );
//             futures.emplace_back(task->get_future());
//             tasks.emplace([task]{ (*task)(); });
//         }
//     }

//     // Wake all threads to start processing
//     condition.notify_all();
//     return futures;
// }