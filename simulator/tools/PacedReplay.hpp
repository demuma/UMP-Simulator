#pragma once

#include <algorithm>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <exception>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace umpReplay {
using ReplayClock = std::chrono::steady_clock;
struct PacedEvent {
    std::int64_t logicalTimeMs;
    bool finishing = false;
};
struct PacedEventTiming {
    PacedEvent event;
    double scheduledArrivalMs = 0, enqueueAttemptMs = 0, enqueuedMs = 0;
    double serviceStartMs = 0, serviceFinishMs = 0;
    std::size_t queueDepthAfterEnqueue = 0;
};
inline double replayOffsetMs(ReplayClock::time_point epoch) {
    return std::chrono::duration<double, std::milli>(ReplayClock::now() - epoch).count();
}

// Only this queue is shared. The consumer alone owns all aggregation state.
// Full means overload: never wait for capacity, silently discard, or shift the
// source schedule. Cancel/failure wakes both a waiting consumer and producer.
class PacedQueue {
public:
    PacedQueue(std::size_t capacity, ReplayClock::time_point epoch) : capacity(capacity), epoch(epoch) {
        if (!capacity) throw std::invalid_argument("Paced queue capacity must be positive");
    }
    bool tryPush(PacedEvent event, double scheduledArrivalMs, double enqueueAttemptMs) {
        std::lock_guard<std::mutex> lock(mutex);
        if (closed || cancelled || queue.size() >= capacity) return false;
        PacedEventTiming timing{event, scheduledArrivalMs, enqueueAttemptMs, replayOffsetMs(epoch)};
        timing.queueDepthAfterEnqueue = queue.size() + 1;
        queue.push_back(timing);
        peak = std::max(peak, queue.size());
        changed.notify_all();
        return true;
    }
    std::optional<PacedEventTiming> pop() {
        std::unique_lock<std::mutex> lock(mutex);
        changed.wait(lock, [&] { return cancelled || closed || !queue.empty(); });
        if (failure) std::rethrow_exception(failure);
        if (cancelled || queue.empty()) return std::nullopt;
        auto value = queue.front(); queue.pop_front();
        return value;
    }
    bool waitUntil(ReplayClock::time_point deadline) {
        std::unique_lock<std::mutex> lock(mutex);
        return !changed.wait_until(lock, deadline, [&] { return cancelled; });
    }
    void close() {
        std::lock_guard<std::mutex> lock(mutex);
        closed = true; changed.notify_all();
    }
    void cancel(std::exception_ptr error = {}) {
        std::lock_guard<std::mutex> lock(mutex);
        if (error && !failure) failure = error;
        cancelled = true; changed.notify_all();
    }
    std::size_t peakDepth() const {
        std::lock_guard<std::mutex> lock(mutex);
        return peak;
    }
private:
    std::size_t capacity, peak = 0;
    ReplayClock::time_point epoch;
    mutable std::mutex mutex;
    std::condition_variable changed;
    std::deque<PacedEventTiming> queue;
    bool closed = false, cancelled = false;
    std::exception_ptr failure;
};

struct PacingReport {
    std::vector<PacedEventTiming> events;
    std::size_t peakQueueDepth = 0;
};
// Bounds apply to diagnostic event storage as well as the pending FIFO. The
// replay's preloaded input and retained result are separate, explicitly named
// memory consumers; this helper does not turn them into a streaming adapter.
inline void validatePacing(const std::vector<PacedEvent>& events, double rate, std::size_t capacity) {
    if (!std::isfinite(rate) || rate <= 0 || rate > 1000 || !capacity || capacity > 100000)
        throw std::invalid_argument("Pacing requires rate in (0,1000] and queue capacity in [1,100000]");
    if (events.empty() || events.size() > 100000)
        throw std::invalid_argument("Pacing requires between 1 and 100000 cadence/finish events");
    std::int64_t previous = 0;
    for (std::size_t i = 0; i < events.size(); ++i) {
        const auto& event = events[i];
        if (event.logicalTimeMs <= previous || event.finishing != (i + 1 == events.size()))
            throw std::invalid_argument("Paced events must increase strictly and end with exactly one finish event");
        previous = event.logicalTimeMs;
    }
    const double durationMs = static_cast<double>(events.back().logicalTimeMs) / rate;
    if (!std::isfinite(durationMs) || durationMs > 86400000)
        throw std::invalid_argument("Paced wall-clock duration must be at most 24 hours");
}

template<class Consume>
PacingReport runPaced(const std::vector<PacedEvent>& events, double rate, std::size_t capacity,
    ReplayClock::time_point epoch, Consume consume) {
    validatePacing(events, rate, capacity);
    PacingReport report;
    report.events.reserve(events.size());
    PacedQueue queue(capacity, epoch);
    std::thread producer([&] {
        try {
            for (const auto& event : events) {
                const double scheduled = static_cast<double>(event.logicalTimeMs) / rate;
                const auto deadline = epoch + std::chrono::duration_cast<ReplayClock::duration>(
                    std::chrono::duration<double, std::milli>(scheduled));
                if (!queue.waitUntil(deadline)) return;
                const double attempted = replayOffsetMs(epoch);
                if (!queue.tryPush(event, scheduled, attempted)) {
                    throw std::runtime_error("Paced replay overloaded/cancelled: logical_time_ms="
                        + std::to_string(event.logicalTimeMs) + ", queue_capacity=" + std::to_string(capacity)
                        + ", peak_queue_depth=" + std::to_string(queue.peakDepth())
                        + ", scheduled_arrival_ms=" + std::to_string(scheduled)
                        + ", enqueue_attempt_ms=" + std::to_string(attempted)
                        + "; no successful replay result was written");
                }
            }
            queue.close();
        } catch (...) { queue.cancel(std::current_exception()); }
    });
    try {
        while (auto timing = queue.pop()) {
            timing->serviceStartMs = replayOffsetMs(epoch);
            consume(timing->event);
            timing->serviceFinishMs = replayOffsetMs(epoch);
            report.events.push_back(*timing);
        }
    } catch (...) {
        queue.cancel(); producer.join(); throw;
    }
    producer.join();
    report.peakQueueDepth = queue.peakDepth();
    return report;
}
} // namespace umpReplay
