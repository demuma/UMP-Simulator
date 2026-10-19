#include "CellLocalAggregation.hpp"
#include "PolicyTree.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <map>
#include <random>
#include <set>
#include <stdexcept>

namespace {
using namespace ump;
constexpr unsigned seed = 82561;
constexpr int scenarioCount = 120;
constexpr AggregationTime finalTimeMs = 1234;

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
bool contains(const CellGeometry& parent, const CellGeometry& child) {
    return child.x >= parent.x && child.y >= parent.y
        && child.x + child.width <= parent.x + parent.width
        && child.y + child.height <= parent.y + parent.height;
}
bool overlaps(const CellGeometry& a, const CellGeometry& b) {
    return std::max(a.x,b.x) < std::min(a.x+a.width,b.x+b.width)
        && std::max(a.y,b.y) < std::min(a.y+a.height,b.y+b.height);
}
int randomCell(std::mt19937& random, int depth) {
    return (3 << (2*depth)) + static_cast<int>(random() % (1 << (2*depth)));
}
CellGeometry randomDomain(std::mt19937& random, const GridCoverage& grid) {
    const int depth = 1 + static_cast<int>(random() % grid.leafDepth);
    return historyCell(grid,randomCell(random,depth),depth);
}

void checkFrontier(const CellLocalAggregation& engine, const GridCoverage& grid,
    bool finished = false) {
    const auto windows = engine.windows();
    const CellGeometry coverage{3,0,grid.x,grid.y,grid.width,grid.height};
    double area = 0;
    for (std::size_t i=0;i<windows.size();++i) {
        const auto& window = windows[i];
        require(contains(coverage,window.cell),"Ownership escaped the input domain");
        require(window.startMs >= 0 && window.nextEndMs > window.startMs
            && window.hardDeadlineMs >= window.nextEndMs,"Invalid local window schedule");
        if (finished) require(window.startMs == finalTimeMs,
            "Fractional finalization left an unresolved spatial prefix");
        area += window.cell.width * window.cell.height;
        for (std::size_t j=0;j<i;++j)
            require(!overlaps(window.cell,windows[j].cell),"Active frontier overlap");
    }
    require(std::abs(area-grid.width*grid.height)<1e-9,"Active frontier has a coverage hole");
}

// Rectangle/time scanning is independent of history queries, prefix matching,
// support caches and selector decisions. Suppression also retires source support.
void checkTerminalEvidence(const std::vector<SpatialSelection>& outputs,
    const std::vector<ObservationBatch>& raw, const MetricEvaluator& metrics) {
    for (std::size_t i=0;i<outputs.size();++i) {
        const auto& output = outputs[i];
        require(output.coordinationCell.has_value(),"Terminal decision omitted its ownership scope");
        const auto& scope = *output.coordinationCell;
        const auto& candidate = output.candidate;
        require(candidate.startMs >= 0 && candidate.endMs > candidate.startMs
            && candidate.endMs <= finalTimeMs,"Terminal decision has an invalid interval");
        std::uint64_t contributions = 0, measured = 0;
        std::set<std::string> identities;
        std::map<std::string,std::uint64_t> types;
        for (const auto& batch : raw) {
            if (batch.observedAtMs<candidate.startMs || batch.observedAtMs>=candidate.endMs) continue;
            ++measured;
            for (const auto& observation : batch.observations) if (contains(scope,observation.cell)) {
                ++contributions;
                identities.insert(observation.contributorId);
                ++types[observation.type];
            }
        }
        require(candidate.counts.observationContributions==contributions
            && candidate.counts.distinctContributors==identities.size()
            && candidate.counts.typeObservationContributions==types,"Raw support mismatch");
        require(candidate.measuredSamples==measured && candidate.missingSamples==0
            && candidate.unavailableSamples==0,"Raw sampling coverage mismatch");
        if (measured) require(candidate.counts.meanSampleOccupancy.has_value()
            && std::abs(*candidate.counts.meanSampleOccupancy
                - static_cast<double>(contributions)/measured)<1e-12,"Raw sample mean mismatch");
        else require(!candidate.counts.meanSampleOccupancy,"No-sample candidate invented a mean");

        // Fresh production policy evaluation catches stale selected flags. The
        // Python integration suite additionally recomputes requirements independently.
        const auto checked = metrics.evaluate(candidate,candidate.closedAtMs);
        require(checked.cells.size()==output.decisions.size(),"Decision/assessment size mismatch");
        for (std::size_t j=0;j<output.decisions.size();++j) if (output.decisions[j].selected)
            require(checked.cells[j].status==AssessmentStatus::Pass
                && candidate.coverage==WindowCoverage::Complete,
                "A selected cell failed its fresh policy evaluation");
        for (std::size_t j=0;j<i;++j) {
            const auto& other = outputs[j];
            require(!overlaps(scope,*other.coordinationCell)
                || std::max(candidate.startMs,other.candidate.startMs)
                    >=std::min(candidate.endMs,other.candidate.endMs),"Retired support overlap");
        }
    }
    for (const auto& batch : raw) for (const auto& observation : batch.observations) {
        std::size_t owners = 0;
        for (const auto& output : outputs)
            if (batch.observedAtMs>=output.candidate.startMs
                && batch.observedAtMs<output.candidate.endMs
                && contains(*output.coordinationCell,observation.cell)) ++owners;
        require(owners==1,"A source contribution was lost or retired more than once");
    }
}

void runScenario(int trial, std::mt19937& random) {
    const int depth = 2 + static_cast<int>(random()%3);
    AggregationConfig config{"run","sensor","app",{0,0,80,80,depth},100,200};
    config.history = HistoryLimits{2000,32,10000,1000000,1024};
    std::vector<PolicyRegion> regions;
    std::set<int> usedRegions;
    for (int index=0;index<3;++index) {
        int id;
        do { id = randomCell(random,depth); } while (!usedRegions.insert(id).second);
        const auto cell = historyCell(config.coverage,id,depth);
        const double durationMaximum = 100*(1+random()%4);
        regions.push_back({std::to_string(index),"test",cell.x,cell.y,cell.width,cell.height,{},
            {{MetricId::WindowDurationMs,{},durationMaximum}}});
    }
    const auto tree = std::make_shared<const PolicyTree>(
        PolicyTreeConfig{"policy","1","app",config.coverage,
            {{MetricId::DistinctContributors,static_cast<double>(1+random()%5),{}},
             {MetricId::CellSideM,{},40}}},std::move(regions));
    MetricEvaluator metrics(tree);
    AggregationHistory history(config,*config.history);
    std::vector<ObservationBatch> raw;
    std::vector<SpatialSelection> outputs;
    const auto strategy = trial%2 ? AdaptationStrategy::SpatialFirst : AdaptationStrategy::TemporalFirst;
    CellLocalAggregation engine(config,{strategy,100,800,32},{1,4096},metrics,
        [&](const SpatialSelection& selection) { outputs.push_back(selection); });
    checkFrontier(engine,config.coverage);
    for (int time=100;time<=1200;time+=100) {
        std::vector<CellObservation> observations;
        for (int identity=0;identity<12;++identity) if (random()%4)
            observations.push_back({std::to_string(identity),"person",
                historyCell(config.coverage,randomCell(random,depth),depth)});
        raw.push_back({"run","sensor",static_cast<std::uint64_t>(time/100),time,
            ObservationStatus::Measured,std::move(observations)});
        history.append(raw.back());
        engine.advance(time,history);
        checkFrontier(engine,config.coverage);
        if (random()%3==0) {
            engine.scheduleMerge(randomDomain(random,config.coverage));
            checkFrontier(engine,config.coverage);
        }
        if (random()%3==0) {
            engine.requestMerge(randomDomain(random,config.coverage),time,history);
            checkFrontier(engine,config.coverage);
        }
    }
    history.advance(finalTimeMs);
    engine.finish(finalTimeMs,history);
    checkFrontier(engine,config.coverage,true);
    checkTerminalEvidence(outputs,raw,metrics);
}
} // namespace

int main() {
    int trial = 0;
    try {
        std::mt19937 random(seed);
        for (;trial<scenarioCount;++trial) runScenario(trial,random);
        std::cout << "PASS: 120 seeded mixed-policy scenarios, complete ownership frontiers, "
            "future handoffs, parent takeovers, raw accounting and fractional finalization.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: seed=" << seed << " scenario=" << trial << ": " << error.what() << '\n';
        return 1;
    }
}
