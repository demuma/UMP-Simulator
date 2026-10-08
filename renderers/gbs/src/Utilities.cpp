#include "../include/Utilities.hpp"
#include "../include/Logging.hpp"

// Generate a unique identifier for the agent
std::string generateUUID() {

    uuid_t uuid;
    uuid_generate(uuid);
    char uuidStr[37];
    uuid_unparse(uuid, uuidStr);

    return std::string(uuidStr);
}

// Generate a unique identifier for the agent
std::string generateISOTimestamp() {

    auto now = std::chrono::system_clock::now();
    std::time_t time_t_now = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&time_t_now), "%FT%TZ");

    return ss.str();
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

// Generate a BSON Date (UTC) for the current simulation time.
std::chrono::system_clock::time_point generateISOTimestamp(sf::Time simulationWallTime, const std::string& dateTimeString = "") {
    
    using namespace std::chrono;

    system_clock::time_point dateTime;
    if (dateTimeString.empty()) {
        dateTime = system_clock::now();
    } else {
        std::tm dateTimeStart = {};
        std::istringstream ss(dateTimeString);
        ss >> std::get_time(&dateTimeStart, "%Y-%m-%dT%H:%M:%S");
        auto tt = std::mktime(&dateTimeStart);
        dateTime = system_clock::from_time_t(tt);
    }

    auto millis = milliseconds{simulationWallTime.asMilliseconds()};
    system_clock::time_point timestamp = dateTime + millis;

    return timestamp;
}

std::string generateISOTimestampString(const std::chrono::system_clock::time_point& tp) {
    // Separate whole seconds from sub‑seconds
    auto dur       = tp.time_since_epoch();
    auto secs      = std::chrono::duration_cast<std::chrono::seconds>(dur);
    auto millis    = std::chrono::duration_cast<std::chrono::milliseconds>(dur - secs);

    // Convert seconds→time_t→tm
    std::time_t t  = secs.count();
    std::tm utc    = *std::gmtime(&t);

    // Format with fractional part
    std::ostringstream oss;
    oss << std::put_time(&utc, "%Y-%m-%dT%H:%M:%S")
        << '.' << std::setw(3) << std::setfill('0') << millis.count()
        << 'Z';
    return oss.str();
}

// Parses a string like "2025-04-09T11:30:01.123" into a bsoncxx::types::b_date.
bsoncxx::types::b_date generateBsonDate(const std::string& timestamp) {
    // Separate the main datetime portion from the fractional seconds
    std::size_t dotPos = timestamp.find('.');
    std::string mainPart = (dotPos == std::string::npos)
                              ? timestamp
                              : timestamp.substr(0, dotPos);

    // If there's a fractional part, strip off trailing 'Z' if present
    std::string fractionPart;
    if (dotPos != std::string::npos) {
        fractionPart = timestamp.substr(dotPos + 1);
        // If the fraction part ends with 'Z', remove it:
        std::size_t zPos = fractionPart.find('Z');
        if (zPos != std::string::npos) {
            fractionPart = fractionPart.substr(0, zPos);
        }
    }

    // Parse the main date/time up to seconds using std::get_time with format "%Y-%m-%dT%H:%M:%S"
    std::tm tm{};
    std::istringstream iss(mainPart);
    iss >> std::get_time(&tm, "%Y-%m-%dT%H:%M:%S");
    if (iss.fail()) {
        throw std::runtime_error("Failed to parse date/time: " + mainPart);
    }

    // Convert this struct tm to a time_t (local time).
    std::time_t time_c = std::mktime(&tm);
    if (time_c == -1) {
        throw std::runtime_error("Invalid local time conversion.");
    }
    // Convert that to a std::chrono::system_clock::time_point
    auto base_tp = std::chrono::system_clock::from_time_t(time_c);

    // Parse fractional seconds as milliseconds (e.g. .123 => 123 ms).
    long frac_ms = 0;
    if (!fractionPart.empty()) {
        // If fractionPart is more than 3 digits, truncate to 3 for milliseconds
        if (fractionPart.size() > 3) {
            fractionPart = fractionPart.substr(0, 3);  
        }
        // If it's fewer than 3 digits, pad with zeros on the right
        while (fractionPart.size() < 3) {
            fractionPart += '0';
        }
        frac_ms = std::stol(fractionPart);
    }

    // Add the parsed fractional milliseconds to our base time
    auto total_tp = base_tp + std::chrono::milliseconds(frac_ms);

    // Construct the BSON date )bsoncxx::types::b_date holds a std::chrono::milliseconds)
    return bsoncxx::types::b_date(total_tp);
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