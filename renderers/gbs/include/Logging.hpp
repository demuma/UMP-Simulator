#pragma once

#ifdef DEBUG
#define DEBUG_MSG(str) do { std::cout << str << std::endl; } while( false )
#else
#define DEBUG_MSG(str) do { } while ( false )
#endif

#ifdef STATS
#define STATS_MSG(str) do { std::cout << str << std::endl; } while( false )
#else
#define STATS_MSG(str) do { } while ( false )
#endif

#ifdef ERROR
#define ERROR_MSG(str) do { std::cout << str << std::endl; } while( false )
#else
#define ERROR_MSG(str) do { } while ( false )
#endif

#ifdef TIMING
#define TIMING_MSG(str) do { std::cout << str << std::endl; } while( false )
#else
#define TIMING_MSG(str) do { } while ( false )
#endif