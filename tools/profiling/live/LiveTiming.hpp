#pragma once
// Measurement-only instrumentation. No state/decision hooks and no public payload fields.
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <mutex>
#include <string>
#include <vector>
namespace ump_live_timing {
using Clock = std::chrono::steady_clock;
inline const auto origin = Clock::now();
inline std::mutex outputMutex;
inline thread_local std::int64_t logicalMs = -1;
struct Event { const char* stage; double offsetMs, durationMs; std::int64_t logicalMs, count, a, b, c; };
inline thread_local std::vector<Event> events;
inline double millis(Clock::duration value) { return std::chrono::duration<double, std::milli>(value).count(); }
inline void event(const char* stage, Clock::time_point start, std::int64_t count=0, std::int64_t a=0, std::int64_t b=0, std::int64_t c=0) {
    events.push_back({stage, millis(start-origin), millis(Clock::now()-start), logicalMs, count, a, b, c});
}
struct Scope { const char* stage; Clock::time_point start=Clock::now(); explicit Scope(const char* stage):stage(stage){} ~Scope(){event(stage,start);} };
inline void flush() {
    const char* file=std::getenv("UMP_LIVE_TIMING_PATH");
    if (!file || events.empty()) return;
    event("timing_buffer", Clock::now(), sizeof(Event), events.capacity(), events.size());
    std::lock_guard<std::mutex> lock(outputMutex);
    std::ofstream out(file,std::ios::app);
    out.precision(12);
    for (const auto& row:events) out << "{\"stage\":\"" << row.stage << "\",\"offset_ms\":" << row.offsetMs
      << ",\"duration_ms\":" << row.durationMs << ",\"logical_ms\":" << row.logicalMs
      << ",\"count\":" << row.count << ",\"a\":" << row.a << ",\"b\":" << row.b << ",\"c\":" << row.c << "}\n";
    events.clear();
}
struct Flush { ~Flush(){flush();} };
}
