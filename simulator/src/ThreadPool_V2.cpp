// #include "ThreadPool.hpp"

// /*
// Usage:

// #include "ThreadPool.hpp"
// #include "World.hpp"
// #include "Agent.hpp"

// int main() {
//     ThreadPool pool(8);

//     std::vector<Agent> agents(1000);
//     World world;

//     // Build per-agent jobs
//     std::vector<std::function<void()>> jobs;
//     jobs.reserve(agents.size());
//     for (auto& agent : agents) {
//         jobs.emplace_back([&world, &agent]{
//             plan_path(agent, world);
//         });
//     }

//     // Submit all jobs in one go
//     auto futures = pool.enqueue_bulk(jobs);

//     // Wait for all tasks (if necessary)
//     for (auto& f : futures) f.get();

//     return 0;
// }
// */

// ThreadPool::ThreadPool(size_t numThreads)
//     : stop(false)
// {
//     if (numThreads == 0)
//         numThreads = 1;

//     workers.reserve(numThreads);

//     for (size_t i = 0; i < numThreads; ++i) {
//         workers.emplace_back([this, i] {
//             for (;;) {
//                 std::function<void()> task;

//                 {
//                     std::unique_lock<std::mutex> lock(this->queueMutex);
//                     this->condition.wait(lock, [this] {
//                         return this->stop || !this->tasks.empty();
//                     });

//                     if (this->stop && this->tasks.empty())
//                         return;

//                     task = std::move(this->tasks.front());
//                     this->tasks.pop();
//                 }

//                 try {
//                     task();
//                 } catch (const std::exception& e) {
//                     std::cerr << "ThreadPool worker " << i
//                               << " caught exception: " << e.what() << '\n';
//                 } catch (...) {
//                     std::cerr << "ThreadPool worker " << i
//                               << " caught unknown exception.\n";
//                 }
//             }
//         });
//     }
// }

// ThreadPool::~ThreadPool()
// {
//     {
//         std::unique_lock<std::mutex> lock(queueMutex);
//         stop = true;
//     }
//     condition.notify_all();

//     for (std::thread& worker : workers)
//         if (worker.joinable()) worker.join();
// }