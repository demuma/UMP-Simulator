#include "Utilities.hpp"
#include <cstdlib>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
struct TimezoneGuard {
    std::string previous;
    bool existed;
    TimezoneGuard() : existed(std::getenv("TZ") != nullptr) {
        if (existed) previous=std::getenv("TZ");
    }
    ~TimezoneGuard() { if (existed) setenv("TZ",previous.c_str(),1);else unsetenv("TZ");tzset(); }
    void use(const char* name) {setenv("TZ",name,1);tzset();}
};
std::string canonical(const std::string& value) {
    return generateISOTimestampString(std::chrono::system_clock::time_point(generateBsonDate(value).value));
}
void explicitTimezoneRoundTrips() {
    TimezoneGuard timezone;
    for (const auto* name : {"UTC","Europe/Berlin","America/New_York"}) {
        timezone.use(name);
        require(canonical("2026-10-23T10:30:00Z")=="2026-10-23T10:30:00.000Z","Explicit UTC depends on host timezone");
        require(canonical("2026-10-23T10:30:00.125+02:00")=="2026-10-23T08:30:00.125Z","Positive offset ignored");
        require(canonical("2026-10-23T10:30:00.5-03:30")=="2026-10-23T14:00:00.500Z","Negative fractional-hour offset ignored");
        require(canonical("2024-02-29T00:00:00.123456789Z")=="2024-02-29T00:00:00.123Z","Leap day or millisecond truncation failed");
        require(canonical("1969-12-31T23:59:59.999Z")=="1969-12-31T23:59:59.999Z","Negative epoch milliseconds do not round-trip");
        const auto later=generateISOTimestamp(sf::milliseconds(250),"2026-10-23T10:30:00.125+02:00");
        require(generateISOTimestampString(later)=="2026-10-23T08:30:00.375Z","Elapsed time does not use the parsed fixed origin");
        const auto origin=generateISOTimestamp(sf::Time::Zero,"2026-10-23T10:30:00Z");
        require(generateISOTimestamp(sf::microseconds(15625),"2026-10-23T10:30:00Z")-origin
            ==std::chrono::microseconds(15625),"Internal elapsed time lost fractional milliseconds");
        const auto before=std::chrono::system_clock::now()-std::chrono::seconds(1);
        const auto now=generateISOTimestamp(sf::Time::Zero,generateISOTimestamp());
        require(now>=before && now<=std::chrono::system_clock::now(),"Current UTC string is local time mislabeled Z");
    }
}
void malformedInputFailsClosed() {
    for (const auto& value : std::vector<std::string>{"","garbage","2026-10-23","2026/10/23T10:30:00Z",
            "2026-13-23T10:30:00Z","2026-00-23T10:30:00Z","2026-02-29T10:30:00Z","2026-04-31T10:30:00Z",
            "2026-10-23T24:00:00Z","2026-10-23T10:60:00Z","2026-10-23T10:30:60Z","2026-10-23T10:30:00.Z",
            "2026-10-23T10:30:00.1234567890Z","2026-10-23T10:30:00+24:00","2026-10-23T10:30:00+01:60",
            "2026-10-23T10:30:00+0200","2026-10-23T10:30:00Zjunk","2026-10-23T10:30:00junk","0000-01-01T00:00:00Z"}) {
        bool rejected=false;
        try { (void)generateBsonDate(value); } catch (const std::invalid_argument&) { rejected=true; }
        require(rejected,"Malformed or unrepresentable timestamp accepted");
        if (!value.empty()) {
            rejected=false;
            try { (void)generateISOTimestamp(sf::Time::Zero,value); } catch (const std::invalid_argument&) { rejected=true; }
            require(rejected,"Origin and BSON timestamp parsers disagree on invalid input");
        }
    }
}
void elapsedOverflowIsRejected() {
    bool rejected=false;
    try { (void)generateISOTimestamp(sf::microseconds(std::numeric_limits<std::int64_t>::max()),"2026-10-23T10:30:00Z"); }
    catch (const std::overflow_error&) {rejected=true;}
    require(rejected,"Elapsed timestamp overflow accepted");
}
void preserveTimezoneFreeLegacyOrigin() {
    TimezoneGuard timezone;
    for (const auto* name : {"UTC","Europe/Berlin"}) {
        timezone.use(name);
        std::tm legacy{};
        legacy.tm_year=126;legacy.tm_mon=9;legacy.tm_mday=23;legacy.tm_hour=10;legacy.tm_min=30;
        const auto expected=std::chrono::system_clock::from_time_t(std::mktime(&legacy));
        require(generateISOTimestamp(sf::Time::Zero,"2026-10-23T10:30:00")==expected,
            "Timezone-free configuration changed legacy absolute origin");
    }
}
}
int main() {
    try {
        explicitTimezoneRoundTrips();malformedInputFailsClosed();elapsedOverflowIsRejected();preserveTimezoneFreeLegacyOrigin();
        std::cout << "UTC/offset, fractional/negative epoch, malformed-input and legacy-origin tests passed.\n";
        return 0;
    } catch (const std::exception& error) {std::cerr << error.what() << '\n';return 1;}
}
