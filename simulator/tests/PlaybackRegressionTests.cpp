#include "PlaybackClock.hpp"
#include "SharedBuffer.hpp"
#include <chrono>
#include <future>
#include <iostream>
#include <limits>
#include <thread>
#include <vector>

namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
void near(double actual, double expected, const char* message) {
    require(std::abs(actual - expected) < 1e-9, message);
}
template<class F> void rejects(F work) {
    bool failed = false;
    try { work(); } catch (const std::exception&) { failed = true; }
    require(failed, "Invalid playback operation accepted");
}

void cadenceAndOverload() {
    for (double speed : {.5, 1., 2.}) {
        ump::PlaybackClock playback(.05, speed);
        const double period = .05 / speed;
        playback.consumed(0);
        near(playback.targetFps(), 20 * speed, "Incorrect target cadence");
        for (int frame = 1; frame <= 100; ++frame) {
            // Drive the exact deadline; modest rendering work fits inside this period.
            const double previous = (frame - 1) * period;
            const double due = previous + playback.remaining(previous);
            require(!playback.due(due - period / 2), "Consumed a frame too early");
            playback.update(due, speed, false);
            playback.consumed(due);
        }
        near(*playback.measuredFps(), 20 * speed, "Steady cadence drift");
        near(*playback.measuredSpeed(), speed, "Measured speed mismatch");
        require(playback.consumedFrames() == 101, "Lost or invented frame");
    }
    ump::PlaybackClock slow(.05, 1);
    slow.consumed(0);
    slow.update(.08, 1, false); // Rendering took longer than 50 ms.
    slow.consumed(.08);
    near(*slow.measuredSpeed(), .625, "Overload not reflected in measured speed");
    near(slow.requested(), 1, "Overload changed the user's request");
    require(!slow.due(.081), "Overload created a catch-up burst");
    slow.update(1, 1, false); // The producer was starved for a long time.
    slow.consumed(1);
    near(*slow.measuredFps(), 2, "Producer waiting excluded from rate");
    require(!slow.due(1.001), "Producer recovery created a catch-up burst");
    near(slow.activeSeconds(), 1, "Active wall time omitted producer waiting");
}

void pauseAndChanges() {
    ump::PlaybackClock playback(.05, 1);
    playback.consumed(0);
    playback.update(.02, 1, true);
    require(!playback.due(5), "Pause consumed frames");
    rejects([&] { playback.consumed(.03); });
    playback.update(5.02, 1, false);
    near(playback.pausedSeconds(), 5, "Paused wall time not separate");
    near(playback.activeSeconds(), .02, "Pause contaminated active wall time");
    require(!playback.measuredFps(), "Pre-pause rate reused after resume");
    playback.consumed(5.02);
    require(!playback.due(5.03), "Resume attempted to catch up missed frames");
    playback.update(5.08, 2, false);
    playback.consumed(5.08);
    near(playback.remaining(5.08), .025, "Speed change used old target");
    require(!playback.measuredFps(), "Rate mixed different speed settings");
    playback.update(5.18, 2, false); playback.consumed(5.18);
    playback.update(5.205, 2, false); playback.consumed(5.205);
    near(*playback.measuredFps(), 16, "FPS averages reciprocals instead of elapsed intervals");
}

void invalidSettings() {
    for (double invalid : {0., -1., std::numeric_limits<double>::infinity(),
            std::numeric_limits<double>::quiet_NaN()}) {
        rejects([&] { ump::PlaybackClock clock(invalid, 1); });
        rejects([&] { ump::PlaybackClock clock(.05, invalid); });
    }
    rejects([] { ump::PlaybackClock clock(.05, 1e9); });
    rejects([] { ump::PlaybackClock clock(.5e-6, .1); });
    ump::PlaybackClock clock(.05, 1);
    clock.update(.1, 1, false);
    rejects([&] { clock.update(.09, 1, false); });
    rejects([&] { clock.update(std::numeric_limits<double>::quiet_NaN(), 1, false); });
    clock.consumed(.1);
    rejects([&] { clock.consumed(.11); });
}

// Real monotonic clock plus the production bounded queue. No window or database.
// Timing tolerances are deliberately separate from the exact fake-clock assertions.
void boundedReplay() {
    using Clock = std::chrono::steady_clock;
    for (double speed : {.5, 1., 2.}) {
        SharedBuffer<int> buffer("pacing replay", 2);
        constexpr int count = 18;
        auto producer = std::async(std::launch::async, [&] {
            for (int frame = 0; frame < count; ++frame) buffer.write(frame);
            buffer.end();
        });
        ump::PlaybackClock playback(.05, speed);
        const auto origin = Clock::now();
        const auto now = [&] { return std::chrono::duration<double>(Clock::now() - origin).count(); };
        std::vector<double> times;
        int received = 0;
        bool ordered = true;
        while (received < count && now() < 8) {
            const double current = now();
            playback.update(current, speed, false);
            if (playback.due(current)) {
                if (auto frame = buffer.tryRead()) {
                    ordered &= *frame == received;
                    playback.consumed(current);
                    times.push_back(current);
                    ++received;
                }
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        buffer.requestStop(); producer.get();
        require(ordered && received == count, "Bounded replay lost, duplicated or reordered input");
        const double expected = (count - 1) * .05 / speed;
        const double elapsed = times.back() - times.front();
        require(elapsed >= expected - 1e-6, "Replay exceeded configured speed");
        require(elapsed <= expected * 1.1 + .005, "Replay outside 10% + 5 ms timing tolerance");
        double maxJitter = 0;
        for (std::size_t i = 1; i < times.size(); ++i)
            maxJitter = std::max(maxJitter, times[i] - times[i - 1] - .05 / speed);
        std::cout << "Replay " << speed << "x: " << (count - 1) / elapsed
                  << " agent FPS; max lateness " << maxJitter * 1000 << " ms\n";
        near(playback.requested(), speed, "Backpressure changed requested speed");
    }
}
}

int main() {
    try {
        cadenceAndOverload(); pauseAndChanges(); invalidSettings(); boundedReplay();
        std::cout << "PASS: playback cadence, overload/starvation, pause, speed changes and bounded replay.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
