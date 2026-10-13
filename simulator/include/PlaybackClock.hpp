#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <deque>
#include <optional>
#include <stdexcept>

namespace ump {
// Wall-clock seconds are supplied by a monotonic clock (or a deterministic test).
// This class paces consumption; sensor timestamps and scientific input are untouched.
class PlaybackClock {
public:
    PlaybackClock(double stepSeconds, double requestedSpeed)
        : step(stepSeconds), speed(requestedSpeed), interval(period(stepSeconds, requestedSpeed)) {}

    static double period(double step, double speed) {
        const double result = step / speed;
        if (!std::isfinite(step) || step < 1e-6 || !std::isfinite(speed) || speed <= 0
            || !std::isfinite(result) || result < 1e-6)
            throw std::invalid_argument("Playback requires a finite time_step >= 1 microsecond and positive finite playback_speed, with a period >= 1 microsecond");
        return result;
    }

    void update(double now, double requestedSpeed, bool pause) {
        const double nextInterval = period(step, requestedSpeed);
        accountTime(now);
        if (requestedSpeed != speed || pause != paused) {
            speed = requestedSpeed;
            interval = nextInterval;
            paused = pause;
            nextDue = now; // Resume/speed change starts a new schedule, never catches up.
            lastFrame.reset();
            frameIntervals.clear();
            intervalSum = 0;
        }
    }

    bool due(double now) const { return !paused && now >= nextDue; }
    double remaining(double now) const { return paused ? 0 : std::max(0.0, nextDue - now); }

    // Call once after a successful read, with the time at which that read began.
    // Expensive reconstruction/drawing therefore counts against this frame's budget.
    void consumed(double now) {
        if (!due(now)) throw std::logic_error("Playback frame consumed before due or while paused");
        accountTime(now);
        if (lastFrame) {
            const double elapsed = now - *lastFrame;
            if (elapsed <= 0) throw std::logic_error("Playback frames require increasing consumption times");
            frameIntervals.push_back(elapsed);
            intervalSum += elapsed;
            if (frameIntervals.size() > 60) {
                intervalSum -= frameIntervals.front();
                frameIntervals.pop_front();
            }
        }
        lastFrame = now;
        ++frames;
        nextDue = now + interval; // Late/slow frames do not accumulate timing debt.
    }

    double requested() const { return speed; }
    double targetFps() const { return 1.0 / interval; }
    std::optional<double> measuredFps() const {
        if (frameIntervals.empty()) return {};
        return frameIntervals.size() / intervalSum;
    }
    std::optional<double> measuredSpeed() const {
        const auto fps = measuredFps();
        return fps ? std::optional<double>(*fps * step) : std::nullopt;
    }
    double activeSeconds() const { return active; }
    double pausedSeconds() const { return pauseTime; }
    std::size_t consumedFrames() const { return frames; }

private:
    void accountTime(double now) {
        if (!std::isfinite(now) || now < lastUpdate)
            throw std::invalid_argument("Playback clock must be finite, nonnegative and monotonic");
        (paused ? pauseTime : active) += now - lastUpdate;
        lastUpdate = now;
    }
    double step, speed, interval;
    double nextDue = 0, lastUpdate = 0, active = 0, pauseTime = 0, intervalSum = 0;
    bool paused = false;
    std::size_t frames = 0;
    std::optional<double> lastFrame;
    std::deque<double> frameIntervals;
};
} // namespace ump
