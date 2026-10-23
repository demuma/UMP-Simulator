#include "../include/Utilities.hpp"
#include "../include/Logging.hpp"
#include <limits>
#include <stdexcept>

// Generate a unique identifier for the agent
std::string generateUUID() {

    uuid_t uuid;
    uuid_generate(uuid);
    char uuidStr[37];
    uuid_unparse(uuid, uuidStr);

    return std::string(uuidStr);
}

namespace {
std::tm utcParts(std::time_t seconds) {
    std::tm result{};
    if (!gmtime_r(&seconds, &result)) throw std::invalid_argument("Timestamp is outside the UTC calendar range");
    return result;
}

// Explicit Z/offset timestamps are portable instants. A timezone-free value
// keeps the legacy mktime(tm_isdst=0) interpretation for existing configurations;
// use Z or an offset for reproducible input across host timezones.
std::chrono::system_clock::time_point parseTimestamp(const std::string& text) {
    const auto fail = [&]() -> void { throw std::invalid_argument("Invalid or unrepresentable ISO timestamp: " + text.substr(0,64)); };
    const auto digits = [&](std::size_t at, std::size_t count) {
        if (at + count > text.size()) fail();
        int value=0;
        for (std::size_t i=at;i<at+count;++i) {
            if (text[i]<'0' || text[i]>'9') fail();
            value=value*10+text[i]-'0';
        }
        return value;
    };
    if (text.size()<19 || text[4]!='-' || text[7]!='-' || text[10]!='T'
        || text[13]!=':' || text[16]!=':') fail();
    const int year=digits(0,4),month=digits(5,2),day=digits(8,2);
    const int hour=digits(11,2),minute=digits(14,2),second=digits(17,2);
    const bool leap=year%4==0 && (year%100!=0 || year%400==0);
    const int days[]={31,28+(leap?1:0),31,30,31,30,31,31,30,31,30,31};
    if (year<1 || month<1 || month>12 || day<1 || day>days[month-1]
        || hour>23 || minute>59 || second>59) fail();
    std::size_t at=19;
    int milliseconds=0;
    if (at<text.size() && text[at]=='.') {
        const auto begin=++at;
        while (at<text.size() && text[at]>='0' && text[at]<='9') ++at;
        if (at==begin || at-begin>9) fail();
        for (std::size_t i=0;i<3;++i)
            milliseconds=milliseconds*10+(begin+i<at?text[begin+i]-'0':0);
    }
    bool explicitZone=false;
    int offsetSeconds=0;
    if (at<text.size()) {
        explicitZone=true;
        if (text[at]=='Z') { if (++at!=text.size()) fail(); }
        else {
            const int sign=text[at]=='+'?1:(text[at]=='-'?-1:0);
            if (!sign || text.size()-at!=6 || text[at+3]!=':') fail();
            const int hours=digits(at+1,2),minutes=digits(at+4,2);
            if (hours>23 || minutes>59) fail();
            offsetSeconds=sign*(hours*3600+minutes*60);at=text.size();
        }
    }
    if (at!=text.size()) fail();
    std::tm civil{};
    civil.tm_year=year-1900;civil.tm_mon=month-1;civil.tm_mday=day;
    civil.tm_hour=hour;civil.tm_min=minute;civil.tm_sec=second;civil.tm_isdst=0;
    const auto seconds=explicitZone?timegm(&civil):std::mktime(&civil);
    // libc may leave errno set after a successful conversion. Validate the UTC
    // round trip instead; time_t(-1) itself is a valid pre-epoch instant.
    if (explicitZone) {
        const auto roundTrip=utcParts(seconds);
        if (roundTrip.tm_year!=year-1900 || roundTrip.tm_mon!=month-1 || roundTrip.tm_mday!=day
            || roundTrip.tm_hour!=hour || roundTrip.tm_min!=minute || roundTrip.tm_sec!=second) fail();
    }
    const auto epochMilliseconds=static_cast<std::int64_t>(seconds)*1000
        -static_cast<std::int64_t>(offsetSeconds)*1000+milliseconds;
    using Clock=std::chrono::system_clock;
    const auto lower=std::chrono::duration_cast<std::chrono::milliseconds>(Clock::duration::min()).count();
    const auto upper=std::chrono::duration_cast<std::chrono::milliseconds>(Clock::duration::max()).count();
    if (epochMilliseconds<lower || epochMilliseconds>upper) fail();
    return Clock::time_point(std::chrono::duration_cast<Clock::duration>(std::chrono::milliseconds(epochMilliseconds)));
}
}

std::string generateISOTimestamp() {
    const auto now=std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    const auto utc=utcParts(now);
    std::ostringstream output;
    output << std::put_time(&utc,"%FT%TZ");
    return output.str();
}

// Generate velocity from truncated normal distribution
float generateRandomNumberFromTND(float mean, float stddev, float min, float max) {

    // Generate normal distribution
    static std::random_device rd;
    static std::mt19937 gen(rd());
    std::normal_distribution<float> generateNormal(mean, stddev);

    // Generate random number until it falls within the specified range
    float value;
    do {

        value = generateNormal(gen);

    } while (value < min || value > max);

    return value;
}

// Generate a random velocity vector from a truncated normal distribution
sf::Vector2f generateRandomVelocityVector(float mu, float sigma, float min, float max) {
    
    // Generate distribution for angle
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<float> disAngle(0.0, 2 * M_PI);
    sf::Vector2f velocity;

    // Generate random velocity magnitude
    float velocityMagnitude = generateRandomNumberFromTND(mu, sigma, min, max);
    float angle = disAngle(gen);
    velocity = sf::Vector2f(velocityMagnitude * std::cos(angle), velocityMagnitude * std::sin(angle));
    
    return velocity;
}

// Convert one configured origin plus elapsed simulation time into an instant.
std::chrono::system_clock::time_point generateISOTimestamp(sf::Time elapsed, const std::string& origin) {
    const auto start=origin.empty()?std::chrono::system_clock::now():parseTimestamp(origin);
    using Clock=std::chrono::system_clock;
    const auto originUs=std::chrono::duration_cast<std::chrono::microseconds>(start.time_since_epoch()).count();
    const auto deltaUs=elapsed.asMicroseconds();
    const auto lower=std::chrono::duration_cast<std::chrono::microseconds>(Clock::duration::min()).count();
    const auto upper=std::chrono::duration_cast<std::chrono::microseconds>(Clock::duration::max()).count();
    if ((deltaUs>0 && originUs>upper-deltaUs) || (deltaUs<0 && originUs<lower-deltaUs))
        throw std::overflow_error("Elapsed simulation time exceeds timestamp range");
    return Clock::time_point(std::chrono::duration_cast<Clock::duration>(std::chrono::microseconds(originUs+deltaUs)));
}

std::string generateISOTimestampString(const std::chrono::system_clock::time_point& point) {
    auto epochMilliseconds=std::chrono::duration_cast<std::chrono::milliseconds>(point.time_since_epoch()).count();
    auto seconds=epochMilliseconds/1000;
    auto fraction=epochMilliseconds%1000;
    if (fraction<0) {fraction+=1000;--seconds;}
    const auto utc=utcParts(static_cast<std::time_t>(seconds));
    std::ostringstream output;
    output << std::put_time(&utc,"%Y-%m-%dT%H:%M:%S")
           << '.' << std::setw(3) << std::setfill('0') << fraction << 'Z';
    return output.str();
}

bsoncxx::types::b_date generateBsonDate(const std::string& timestamp) {
    return bsoncxx::types::b_date(parseTimestamp(timestamp));
}

// Convert a string to an sf::Color object
sf::Color stringToColor(std::string colorStr) {

    // Mapping of color names to sf::Color objects
    static const std::unordered_map<std::string, sf::Color> colorMap = {

        {"red", sf::Color::Red},
        {"green", sf::Color::Green},
        {"blue", sf::Color::Blue},
        {"black", sf::Color::Black},
        {"white", sf::Color::White},
        {"yellow", sf::Color::Yellow},
        {"magenta", sf::Color::Magenta},
        {"cyan", sf::Color::Cyan},
        {"pink", sf::Color(255, 192, 203)},
        {"brown", sf::Color(165, 42, 42)},
        {"turquoise", sf::Color(64, 224, 208)},
        {"gray", sf::Color(128, 128, 128)},
        {"purple", sf::Color(128, 0, 128)},
        {"violet", sf::Color(238, 130, 238)},
        {"orange", sf::Color(198, 81, 2)},
        {"indigo", sf::Color(75, 0, 130)},
        {"grey", sf::Color(128, 128, 128)}
    };

    // Convert to lowercase directly for faster comparison
    std::transform(colorStr.begin(), colorStr.end(), colorStr.begin(),
                [](unsigned char c){ return std::tolower(c); }); 

    // Fast lookup using a hash map
    auto it = colorMap.find(colorStr);
    if (it != colorMap.end()) {
        return it->second;
    }

    // Handle hex codes (same as your original implementation)
    if (colorStr.length() == 7 && colorStr[0] == '#') {
        int r, g, b;
        if (sscanf(colorStr.c_str(), "#%02x%02x%02x", &r, &g, &b) == 3) {
            return sf::Color(r, g, b);
        }
    }

    std::cerr << "Warning: Unrecognized color string '" << colorStr << "'. Using black instead." << std::endl;
    return sf::Color::Black;
}