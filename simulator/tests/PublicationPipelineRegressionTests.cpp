#include "AdaptiveAggregation.hpp"
#include "AggregationManager.hpp"
#include "PublicationStore.hpp"
#include <bsoncxx/builder/basic/document.hpp>
#include <bsoncxx/json.hpp>
#include <mongocxx/instance.hpp>
#include <mongocxx/uri.hpp>
#include <array>
#include <iomanip>
#include <iostream>
#include <random>
#include <sstream>
#include <stdexcept>

namespace {
using namespace ump;
using bsoncxx::builder::basic::kvp;
using bsoncxx::builder::basic::make_document;

void require(bool value, const std::string& message) {
    if (!value) throw std::runtime_error(message);
}

template<class Operation> void mustThrow(Operation operation) {
    try { operation(); }
    catch (const std::exception&) { return; }
    throw std::runtime_error("Finished pipeline unexpectedly accepted more progress");
}

std::string uuid() {
    std::random_device random;
    std::array<unsigned char, 16> bytes{};
    for (auto& value : bytes) value = static_cast<unsigned char>(random());
    bytes[6] = static_cast<unsigned char>((bytes[6] & 0x0f) | 0x40);
    bytes[8] = static_cast<unsigned char>((bytes[8] & 0x3f) | 0x80);
    std::ostringstream result;
    result << std::hex << std::setfill('0');
    for (std::size_t i = 0; i < bytes.size(); ++i) {
        if (i == 4 || i == 6 || i == 8 || i == 10) result << '-';
        result << std::setw(2) << static_cast<unsigned>(bytes[i]);
    }
    return result.str();
}

struct Databases {
    std::shared_ptr<mongocxx::client> client = std::make_shared<mongocxx::client>(mongocxx::uri{
        "mongodb://localhost:27017/?serverSelectionTimeoutMS=3000&socketTimeoutMS=5000"});
    PublicationStoreOptions options;
    Databases() {
        const auto suffix = uuid();
        options.recipientDatabase = "UMP_pipe_public_" + suffix;
        options.journalDatabase = "UMP_pipe_private_" + suffix;
    }
    ~Databases() {
        // Only these two fresh UUID databases belong to this test.
        try {
            (*client)[options.recipientDatabase].drop();
            (*client)[options.journalDatabase].drop();
        } catch (const std::exception& error) {
            std::cerr << "Pipeline fixture cleanup failed: " << error.what() << '\n';
        }
    }
    mongocxx::collection recipients() {
        return (*client)[options.recipientDatabase][options.recipientCollection];
    }
};

AggregationConfig settings(std::string run) {
    AggregationConfig config{std::move(run), "pipeline-sensor", "pipeline-app", {0,0,80,80,3}, 100, 400};
    config.history = HistoryLimits{2000, 32, 2000, 100000, 16};
    return config;
}

struct Pipeline {
    Databases& databases;
    AggregationConfig config;
    MetricEvaluator evaluator;
    PublicationStore store;
    PublicationCoordinator coordinator;
    std::vector<SpatialSelection> selections;
    std::vector<ReleaseSnapshot> releases;
    std::vector<std::pair<AggregationTime, bool>> progress;
    std::size_t fixedCandidates = 0;
    AggregationManager manager;
    AdaptiveAggregation adaptive;

    Pipeline(Databases& db, const std::string& run, AdaptationStrategy strategy,
        double minimumContributors = 2)
        : databases(db), config(settings(run)), evaluator(MetricPolicy{"pipeline-policy", "1",
            {{MetricId::DistinctContributors, minimumContributors, {}}, {MetricId::CellSideM, {}, 40}}}),
          store(db.client, db.options), coordinator(config, evaluator, {}, 800),
          manager(config, [this](const AggregationCandidate&) { ++fixedCandidates; }),
          adaptive(config, {strategy, 100, 800, 32}, {2, 64}, evaluator,
            [this](const SpatialSelection& selection) { publish(selection); }) {
        manager.setProgressSink([this](AggregationTime now, bool finishing) {
            require(manager.history() && manager.history()->debugState().watermarkMs == now,
                "Progress callback ran before shared history advancement");
            progress.emplace_back(now, finishing);
            if (finishing) adaptive.finish(now, *manager.history());
            else adaptive.advance(now, *manager.history());
        });
    }

    CellObservation observation(const std::string& id, int cell = 192) const {
        return {id, "PRIVATE_UNASSESSED_TYPE", historyCell(config.coverage, cell, 3)};
    }
    void sample(AggregationTime time, std::vector<CellObservation> observations = {}) {
        manager.ingest({config.runId, config.sensorId, static_cast<std::uint64_t>(time / 100),
            time, ObservationStatus::Measured, std::move(observations)});
    }
    void finish(AggregationTime time) { manager.finish(time); }

    void publish(const SpatialSelection& selection) {
        const auto now = selection.candidate.closedAtMs;
        const auto release = coordinator.seal(selection, now);
        store.prepare(*release);
        PublicationStore recovered(databases.client, databases.options);
        const auto pending = recovered.recoverPending();
        require(pending.size() == 1 && pending.front().releaseId == release->releaseId,
            "New prepared interval was not durable before delivery");
        const auto before = databases.recipients().count_documents({});
        require(recovered.reconcile(*release) == (release->cells.empty()
                ? SinkResult::Acknowledged : SinkResult::Retry),
            "Read-only reconciliation returned the wrong pre-delivery state");
        require(databases.recipients().count_documents({}) == before,
            "Recovery published undelivered support");
        if (release->cells.empty()) store.commit(*release);
        require(coordinator.deliver(now, [&](const ReleaseSnapshot& payload) {
            require(store.publish(payload) == SinkResult::Acknowledged,
                "Whole snapshot was not durably delivered");
            require(recovered.reconcile(payload) == SinkResult::Acknowledged
                    && !recovered.recoverPending().empty(),
                "Lost acknowledgement could not be resolved before private commit");
            const auto after = databases.recipients().count_documents({});
            require(store.publish(payload) == SinkResult::Acknowledged
                    && databases.recipients().count_documents({}) == after,
                "Duplicate delivery inserted a second recipient document");
            store.commit(payload);
            return SinkResult::Acknowledged;
        }), "Coordinator failed to retire durable output");
        require(!coordinator.pendingRelease() && coordinator.state().retiredThroughMs == release->endMs,
            "Coordinator retained a committed reservation or retired a different endpoint");
        selections.push_back(selection);
        releases.push_back(*release);
    }

    void verify(AggregationTime end, std::size_t publicDocuments) {
        require(manager.debugState().finished && adaptive.debugState().finished,
            "Final flush did not finish manager and adaptive coordinator");
        require(coordinator.state().retiredThroughMs == end && !coordinator.pendingRelease(),
            "Final watermark did not retire all input support");
        auto journal = store.recoverStream(config.runId, config.sensorId, config.applicationId);
        require(journal.size() == releases.size() && store.recoverPending().empty(),
            "Durable journal lost an interval or retained committed pending state");
        AggregationTime through = 0;
        std::size_t visible = 0;
        for (std::size_t i = 0; i < journal.size(); ++i) {
            const auto& entry = journal[i];
            require(entry.committed && entry.release.startMs == through && entry.release.endMs > through
                    && entry.release.releaseId == releases[i].releaseId,
                "Journal intervals overlap, skip support, duplicate IDs or fail to commit");
            through = entry.release.endMs;
            auto document = databases.recipients().find_one(make_document(kvp("_id", entry.release.releaseId)));
            require(static_cast<bool>(document) == !entry.release.cells.empty(),
                "Suppressed interval became public or selected interval disappeared");
            for (const auto& cell : entry.release.cells)
                require(cell.aggregate.counts.typeObservationContributions.empty(),
                    "Journal retained an unapproved type breakdown in its release payload");
            if (!document) continue;
            ++visible;
            const auto json = bsoncxx::to_json(document->view());
            for (const auto* forbidden : {"PRIVATE_", "type_observation_contributions", "suppressed",
                "source_cells", "attempts", "contributor_id", "expected_samples", "private_publication_journal"})
                require(json.find(forbidden) == std::string::npos,
                    std::string("Private pipeline data reached recipients: ") + forbidden);
            require(!document->view()["counts"] && !document->view()["state"],
                "Public document exposes whole-window totals or private lifecycle");
        }
        require(through == end && visible == publicDocuments, "Unexpected durable final extent or public record count");
        require(databases.recipients().count_documents(make_document(kvp("run_id", config.runId)))
                == static_cast<std::int64_t>(publicDocuments),
            "Recipient database contains an extra output for this stream");
        mustThrow([&] { manager.advance(end + 100); });
    }
};

std::uint64_t contributions(const Pipeline& pipeline) {
    std::uint64_t total = 0;
    for (const auto& release : pipeline.releases)
        for (const auto& cell : release.cells) total += cell.aggregate.counts.observationContributions;
    return total;
}

void strategiesAndRepeatedDelivery(Databases& db) {
    Pipeline temporal(db, "temporal-first", AdaptationStrategy::TemporalFirst);
    Pipeline spatial(db, "spatial-first", AdaptationStrategy::SpatialFirst);
    for (auto* pipeline : {&temporal, &spatial}) {
        for (int time : {100,200,300}) pipeline->sample(time,
            {pipeline->observation("PRIVATE_A"), pipeline->observation("PRIVATE_B",193)});
        pipeline->sample(400, {pipeline->observation("PRIVATE_C"), pipeline->observation("PRIVATE_D",193)});
    }
    require(temporal.releases.size() == 1 && temporal.releases[0].endMs == 400
            && temporal.releases[0].cells.size() == 1 && temporal.releases[0].cells[0].aggregate.cell.id == 48,
        "Temporal First did not publish a coarsened initial interval");
    require(spatial.releases.empty(), "Spatial First disclosed support before its finest cut passed");
    for (auto* pipeline : {&temporal, &spatial})
        pipeline->sample(500, {pipeline->observation("PRIVATE_C"), pipeline->observation("PRIVATE_D",193)});
    require(spatial.releases.size() == 1 && spatial.releases[0].endMs == 500
            && spatial.releases[0].cells.size() == 2
            && spatial.releases[0].cells[0].aggregate.cell.depth == 3,
        "Spatial First failed to publish the extended finest cut");
    for (auto* pipeline : {&temporal, &spatial}) {
        const auto completed = pipeline->releases.size();
        pipeline->manager.advance(500);
        require(pipeline->releases.size() == completed, "Repeated progress emitted duplicate interval support");
        pipeline->finish(550);
        pipeline->verify(550, 2);
        require(pipeline->releases.back().startMs == (pipeline == &temporal ? 400 : 500)
                && pipeline->selections.back().candidate.truncated
                && pipeline->selections.back().completionReason == "end_of_stream",
            "Partial final release lost its disjoint boundary or termination marker");
        require(contributions(*pipeline) == 10, "Adaptive release intervals duplicated or lost measured contributions");
    }
}

void suppressedAndEmpty(Databases& db) {
    Pipeline suppressed(db, "suppressed", AdaptationStrategy::SpatialFirst, 5);
    for (int time = 100; time <= 800; time += 100)
        suppressed.sample(time, {suppressed.observation("PRIVATE_ONLY_ONE")});
    require(suppressed.releases.size() == 1 && suppressed.releases.front().endMs == 800
            && suppressed.releases.front().cells.empty(),
        "Maximum-window suppression did not retire privately");
    suppressed.finish(850);
    suppressed.verify(850, 0);
    require(suppressed.releases.size() == 2 && suppressed.releases.back().cells.empty(),
        "Final suppressed remainder was not journalled");

    Pipeline measuredEmpty(db, "measured-empty", AdaptationStrategy::TemporalFirst);
    for (int time : {100,200,300}) measuredEmpty.sample(time);
    measuredEmpty.finish(400);
    measuredEmpty.verify(400, 0);
    require(measuredEmpty.releases.size() == 1, "Measured-empty final window was not privately retired");

    Pipeline unsampled(db, "no-samples", AdaptationStrategy::SpatialFirst);
    unsampled.finish(50);
    unsampled.verify(50, 0);
    require(unsampled.releases.size() == 1 && unsampled.selections.front().candidate.expectedSamples == 0,
        "Short stream with no scheduled observations did not retire privately");

    Pipeline missing(db, "all-samples-missing", AdaptationStrategy::SpatialFirst);
    missing.finish(450);
    missing.verify(450, 0);
    require(!missing.releases.empty(), "Entirely unobserved stream did not create private interval intent");

    Pipeline zero(db, "zero-duration", AdaptationStrategy::TemporalFirst);
    zero.finish(0);
    zero.verify(0, 0);
    require(zero.releases.empty(), "Zero-duration stream invented an output interval");
}

void exactFinalBoundary(Databases& db) {
    for (const auto strategy : {AdaptationStrategy::TemporalFirst, AdaptationStrategy::SpatialFirst}) {
        Pipeline pipeline(db, strategy == AdaptationStrategy::TemporalFirst ? "exact-temporal" : "exact-spatial", strategy);
        for (int time : {100,200,300}) pipeline.sample(time,
            {pipeline.observation("PRIVATE_A"), pipeline.observation("PRIVATE_B",193)});
        const auto callbacksBeforeFinish = pipeline.progress.size();
        pipeline.finish(400);
        pipeline.verify(400, 1);
        require(pipeline.releases.size() == 1 && pipeline.releases.front().endMs == 400,
            "Exact final boundary emitted a duplicate or extended interval");
        require(pipeline.progress.size() == callbacksBeforeFinish + 1
                && pipeline.progress.back() == std::make_pair<AggregationTime,bool>(400,true),
            "Final manager advance dispatched ordinary progress before finalization");
        require(pipeline.selections.front().completionReason == "end_of_stream"
                && pipeline.selections.front().candidate.truncated,
            "Exact final boundary was processed as ordinary progress");
        for (const auto& decision : pipeline.selections.front().temporalDecisions)
            require(decision.endMs <= 400,
                "Exact finalization scheduled a temporal extension beyond the stream end");
    }
}
}

int main() {
    try {
        mongocxx::instance instance;
        Databases databases;
        strategiesAndRepeatedDelivery(databases);
        suppressedAndEmpty(databases);
        exactFinalBoundary(databases);
        std::cout << "Publication pipeline regression tests passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Publication pipeline regression failure: " << error.what() << '\n';
        return 1;
    }
}
