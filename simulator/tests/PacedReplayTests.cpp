#include "../tools/PacedReplay.hpp"
#include <future>
#include <iostream>
#include <limits>

namespace {
using namespace umpReplay;
using namespace std::chrono_literals;
void require(bool condition, const char* reason) {
    if (!condition) throw std::runtime_error(reason);
}
template<class F> void rejects(F operation, const char* reason) {
    try { operation(); } catch (const std::invalid_argument&) { return; }
    throw std::runtime_error(reason);
}
void boundedFifoAndCompletion() {
    const auto epoch = ReplayClock::now();
    PacedQueue queue(2, epoch);
    require(queue.tryPush({100, false}, 10, 11), "First bounded event rejected");
    require(queue.tryPush({200, true}, 20, 21), "Second bounded event rejected");
    require(!queue.tryPush({300, true}, 30, 31), "Full queue accepted an event");
    require(queue.peakDepth() == 2, "Peak capacity accounting is wrong");
    queue.close();
    require(!queue.tryPush({300, true}, 30, 31), "Closed queue accepted an event");
    const auto first = queue.pop(), second = queue.pop();
    require(first && second && first->event.logicalTimeMs == 100 && !first->event.finishing
        && second->event.logicalTimeMs == 200 && second->event.finishing,
        "FIFO close lost/reordered queued events or altered EOF");
    require(first->scheduledArrivalMs == 10 && first->enqueueAttemptMs == 11
        && first->queueDepthAfterEnqueue == 1 && second->queueDepthAfterEnqueue == 2,
        "FIFO changed source timing metadata");
    require(!queue.pop(), "Drained close did not terminate");
}
void cancellationWakesBothWaiters() {
    PacedQueue queue(1, ReplayClock::now());
    std::promise<void> popping, waiting;
    auto reader = std::async(std::launch::async, [&] { popping.set_value(); return queue.pop(); });
    auto sleeper = std::async(std::launch::async, [&] {
        waiting.set_value(); return queue.waitUntil(ReplayClock::now() + 10s);
    });
    popping.get_future().wait(); waiting.get_future().wait();
    queue.cancel();
    require(reader.wait_for(1s) == std::future_status::ready, "Cancellation did not wake consumer");
    require(sleeper.wait_for(1s) == std::future_status::ready, "Cancellation did not wake producer");
    require(!reader.get() && !sleeper.get(), "Cancellation resumed normal processing");
    require(!queue.tryPush({1, true}, 1, 1), "Cancelled queue accepted data");

    PacedQueue failed(1, ReplayClock::now());
    require(failed.tryPush({1, true}, 1, 1), "Failure fixture push rejected");
    failed.cancel(std::make_exception_ptr(std::runtime_error("first failure")));
    failed.cancel(std::make_exception_ptr(std::runtime_error("second failure")));
    bool originalFailure = false;
    try { (void) failed.pop(); }
    catch (const std::runtime_error& error) { originalFailure = std::string(error.what()) == "first failure"; }
    require(originalFailure, "Cancellation lost/replaced original producer failure or drained after failure");
}
void runnerOrderAndClockDomains() {
    const std::vector<PacedEvent> events{{2, false}, {4, false}, {7, true}};
    std::vector<PacedEvent> consumed;
    const auto report = runPaced(events, 2.0, events.size(), ReplayClock::now(),
        [&](const auto& event) { consumed.push_back(event); });
    require(consumed.size() == events.size() && report.events.size() == events.size(),
        "Paced runner skipped/duplicated a callback or timing row");
    double previousEnd = 0;
    for (std::size_t i = 0; i < events.size(); ++i) {
        const auto& timing = report.events[i];
        require(consumed[i].logicalTimeMs == events[i].logicalTimeMs
            && consumed[i].finishing == events[i].finishing
            && timing.event.logicalTimeMs == events[i].logicalTimeMs,
            "Pacing changed logical input or finish order");
        require(timing.scheduledArrivalMs == double(events[i].logicalTimeMs) / 2.0,
            "Speed factor changed scientific time instead of arrival schedule");
        require(timing.enqueueAttemptMs >= timing.scheduledArrivalMs
            && timing.enqueuedMs >= timing.enqueueAttemptMs
            && timing.serviceStartMs >= timing.enqueuedMs
            && timing.serviceStartMs >= previousEnd
            && timing.serviceFinishMs >= timing.serviceStartMs,
            "Monotonic arrival/queue/service clock contract failed");
        previousEnd = timing.serviceFinishMs;
    }
    require(report.peakQueueDepth > 0 && report.peakQueueDepth <= events.size(),
        "Paced runner violated pending queue bound");
}
void callbackExceptionCancelsFutureProducer() {
    const auto started = ReplayClock::now();
    bool original = false;
    try {
        runPaced({{1, false}, {10000, true}}, 1, 1, started,
            [](const auto&) { throw std::runtime_error("consumer failure"); });
    } catch (const std::runtime_error& error) {
        original = std::string(error.what()) == "consumer failure";
    }
    require(original, "Consumer exception did not retain original error");
    // This broad shutdown guard catches an uninterruptible ten-second producer
    // wait; it is deliberately not a millisecond performance requirement.
    require(ReplayClock::now() - started < 1s, "Consumer failure waited for future source deadline");
}
void inputBounds() {
    const std::vector<PacedEvent> valid{{100, false}, {250, true}};
    validatePacing(valid, 1, 2);
    for (double rate : {0., -1., 1001., std::numeric_limits<double>::infinity(),
                        std::numeric_limits<double>::quiet_NaN()})
        rejects([&] { validatePacing(valid, rate, 2); }, "Invalid pace rate accepted");
    for (std::size_t capacity : {std::size_t(0), std::size_t(100001)})
        rejects([&] { validatePacing(valid, 1, capacity); }, "Invalid queue capacity accepted");
    for (const std::vector<PacedEvent>& events : {
            std::vector<PacedEvent>{}, {{0, true}}, {{-1, true}}, {{100, false}},
            {{100, true}, {200, true}}, {{100, false}, {100, true}},
            {{200, false}, {100, true}}})
        rejects([&] { validatePacing(events, 1, 2); }, "Invalid event sequence accepted");
    rejects([&] { validatePacing({{86400001, true}}, 1, 1); }, "Unbounded wall duration accepted");
    rejects([&] { validatePacing(std::vector<PacedEvent>(100001, {1, true}), 1, 1); },
        "Unbounded diagnostic event storage accepted");
    rejects([&] { PacedQueue queue(0, ReplayClock::now()); }, "Zero-capacity queue accepted");
}
}
int main() {
    try {
        boundedFifoAndCompletion(); cancellationWakesBothWaiters(); runnerOrderAndClockDomains();
        callbackExceptionCancelsFutureProducer(); inputBounds();
        std::cout << "PASS: bounded FIFO, completion, failure propagation, interruptible cancellation, paced event order, monotonic timing and input bounds.\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << "FAIL: " << error.what() << '\n'; return 1; }
}
