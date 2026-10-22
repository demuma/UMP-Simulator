#include "PublicationStore.hpp"
#include "AggregationManager.hpp"
#include "AdaptiveAggregation.hpp"
#include <bsoncxx/builder/basic/array.hpp>
#include <bsoncxx/builder/basic/document.hpp>
#include <bsoncxx/json.hpp>
#include <mongocxx/instance.hpp>
#include <mongocxx/uri.hpp>
#include <array>
#include <cmath>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <limits>
#include <random>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace {
using bsoncxx::builder::basic::kvp;
using bsoncxx::builder::basic::make_document;

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

template<class Exception = std::exception, class Operation>
void mustThrow(Operation operation, const std::string& message) {
    bool threw = false;
    try { operation(); }
    catch (const Exception&) { threw = true; }
    require(threw, message);
}

std::string field(bsoncxx::document::view row, const char* key) {
    const auto value = row[key].get_string().value;
    return {value.data(), value.size()};
}

std::string uuid() {
    std::random_device random;
    std::array<unsigned char, 16> bytes{};
    for (auto& value : bytes) value = static_cast<unsigned char>(random());
    bytes[6] = static_cast<unsigned char>((bytes[6] & 0x0f) | 0x40);
    bytes[8] = static_cast<unsigned char>((bytes[8] & 0x3f) | 0x80);
    std::ostringstream text;
    text << std::hex << std::setfill('0');
    for (std::size_t i = 0; i < bytes.size(); ++i) {
        if (i == 4 || i == 6 || i == 8 || i == 10) text << '-';
        text << std::setw(2) << static_cast<unsigned>(bytes[i]);
    }
    return text.str();
}

// Only these two fresh UUID namespaces are owned by this test. No other database
// is enumerated, cleared or modified, including the user's Simulation database.
struct TestDatabases {
    mongocxx::database recipient, journal;
    ~TestDatabases() {
        try { recipient.drop(); journal.drop(); }
        catch (const std::exception& error) {
            std::cerr << "Semantic publication fixture cleanup failed: " << error.what() << '\n';
        }
    }
};

ump::ReleaseSnapshot snapshot(std::int64_t start = 0, bool semantic = true) {
    ump::ReleaseSnapshot release;
    release.runId = "semantic-publication-store-test";
    release.sensorId = "sensor";
    release.applicationId = "application";
    release.startMs = start;
    release.endMs = start + 1000;
    release.sealedAtMs = start + 1000;
    release.policyId = "test-policy";
    release.policyVersion = "v1";
    const auto part = [](const std::string& value) { return std::to_string(value.size()) + ":" + value; };
    release.releaseId = "ump-release-v1/" + part(release.runId) + part(release.sensorId)
        + part(release.applicationId) + "/" + std::to_string(release.startMs)
        + "/" + std::to_string(release.endMs);
    ump::AggregateCounts counts;
    counts.observationContributions = 24;
    counts.distinctContributors = 8;
    counts.meanSampleOccupancy = 2.4;
    release.cells.push_back({{{12, 1, 0, 0, 20, 20}, counts}, "test-policy/effective"});
    if (semantic) {
        ump::SemanticRepresentation representation;
        representation.taxonomyId = "road-user-taxonomy";
        representation.taxonomyVersion = "v1";
        representation.bins = {{"pedestrian", 12, 4}, {"cycle", 12, 4}};
        representation.minimumDistinctContributors = 4;
        representation.maxLoss = .5;
        representation.meanLoss = .25;
        release.cells.front().semantic = std::move(representation);
    }
    return release;
}

void checkSemantic(const ump::ReleaseSnapshot& release) {
    require(release.cells.size() == 1 && release.cells.front().semantic.has_value(),
        "Recovery lost the optional semantic representation");
    const auto& semantic = *release.cells.front().semantic;
    require(semantic.taxonomyId == "road-user-taxonomy" && semantic.taxonomyVersion == "v1"
        && semantic.bins.size() == 2 && semantic.bins[0].categoryId == "pedestrian"
        && semantic.bins[1].categoryId == "cycle"
        && semantic.bins[0].observationContributions == 12 && semantic.bins[0].distinctContributors == 4
        && semantic.bins[1].observationContributions == 12 && semantic.bins[1].distinctContributors == 4
        && semantic.minimumDistinctContributors == 4 && semantic.maxLoss == .5 && semantic.meanLoss == .25,
        "Recovery changed semantic version, category payload or assessed losses");
    require(!release.cells.front().aggregate.counts.semanticEvidence
        && release.cells.front().aggregate.counts.typeObservationContributions.empty(),
        "Recovery created private semantic/type evidence from the public payload");
}

bsoncxx::document::value legacyPayload(const ump::ReleaseSnapshot& release) {
    // Independent copy of the pre-semantic v1 BSON field order and scalar types.
    const auto& cell = release.cells.front().aggregate.cell;
    bsoncxx::builder::basic::array cells;
    cells.append(make_document(kvp("cell_id", cell.id), kvp("depth", cell.depth),
        kvp("x", cell.x), kvp("y", cell.y), kvp("width", cell.width), kvp("height", cell.height),
        kvp("counts", make_document(kvp("observation_contributions", std::int64_t{24}),
            kvp("distinct_contributors", std::int64_t{8}), kvp("mean_sample_occupancy", 2.4))),
        kvp("effective_policy_id", "test-policy/effective")));
    return make_document(kvp("_id", release.releaseId), kvp("schema", "ump.release.v1"),
        kvp("data_role", "recipient_release"), kvp("run_id", release.runId),
        kvp("sensor_id", release.sensorId), kvp("application_id", release.applicationId),
        kvp("model", release.model), kvp("policy_id", release.policyId),
        kvp("policy_version", release.policyVersion), kvp("start_ms", release.startMs),
        kvp("end_ms", release.endMs), kvp("sealed_at_ms", release.sealedAtMs), kvp("cells", cells));
}

void realSemanticPipeline(std::shared_ptr<mongocxx::client> client,
    const ump::PublicationStoreOptions& options) {
    // One acceptance case crosses the real observation accumulator, bounded
    // history, semantic evaluator, selector, immutable coordinator and Mongo store.
    // Every observation belongs to this test's existing UUID-owned namespaces.
    using namespace ump;
    const auto taxonomy = std::make_shared<const SemanticTaxonomy>("acceptance-road-users", "1",
        std::vector<SemanticNode>{{"Root", "", 1, {}}, {"Cyclist", "Root", .5, {}},
            {"Adult", "Cyclist", 0, {"Adult Cyclist"}},
            {"Child", "Cyclist", 0, {"Child Cyclist"}}});
    AggregationConfig config{"semantic-core-acceptance", "agbs", "application", {0, 0, 80, 80, 2}, 100, 400};
    config.history = HistoryLimits{2000, 32, 10000, 1000000, 128};
    config.semanticTaxonomy = taxonomy;
    std::vector<AggregationCandidate> fixedWindows;
    AggregationManager manager(config, [&](const auto& candidate) { fixedWindows.push_back(candidate); });
    const auto cell = historyCell(config.coverage, 48, 2);
    const std::vector<CellObservation> people{{"adult-a", "Adult Cyclist", cell},
        {"adult-b", "Adult Cyclist", cell}, {"child-a", "Child Cyclist", cell},
        {"child-b", "Child Cyclist", cell}};
    for (const int time : {100, 200, 300})
        manager.ingest({config.runId, config.sensorId, static_cast<std::uint64_t>(time / 100),
            time, ObservationStatus::Measured, people});
    manager.advance(400);
    require(fixedWindows.size() == 1 && fixedWindows.front().counts.observationContributions == 12
        && fixedWindows.front().counts.distinctContributors == 4 && manager.history(),
        "Real manager failed to accumulate three samples of four distinct cyclists");
    const auto evidence = manager.history()->queryFinest(0, 400);
    require(evidence.status == HistoryQueryStatus::Complete && evidence.candidate
        && evidence.candidate->cells.size() == 1
        && evidence.candidate->cells.front().counts.semanticEvidence,
        "Real bounded history lost complete exact semantic evidence");
    const auto& privateNodes = evidence.candidate->cells.front().counts.semanticEvidence->nodes;
    require(privateNodes.at("Adult").observationContributions == 6
        && privateNodes.at("Adult").distinctContributors == 2
        && privateNodes.at("Child").observationContributions == 6
        && privateNodes.at("Child").distinctContributors == 2,
        "History confused repeated type samples with independent semantic support");
    MetricEvaluator evaluator(MetricPolicy{"acceptance-semantic-policy", "1", {
        {MetricId::DistinctContributors, 4, {}}, {MetricId::CellSideM, {}, 20},
        {MetricId::MinCategoryDistinctContributors, 4, {}}, {MetricId::SemanticMaxLoss, {}, .5}}}, taxonomy);
    SpatialSelector selector(config, {1, 128, true});
    auto selected = selector.select(*evidence.candidate, *manager.history(), evaluator);
    require(selected.selectedCells == 1 && selected.candidate.cells.front().cell.id == 48,
        "Real semantic support generalized space instead of the permitted taxonomy categories");
    PublicationCoordinator publisher(config, evaluator);
    const auto release = publisher.seal(selected, 400);
    const auto exactSemantic = [&](const ReleaseSnapshot& value) {
        require(value.startMs == 0 && value.endMs == 400 && value.sealedAtMs == 400
            && !value.coordinationCell && value.cells.size() == 1 && value.cells.front().semantic,
            "Acceptance snapshot lost its original interval, scope or semantic output");
        const auto& released = value.cells.front();
        const auto& representation = *released.semantic;
        require(released.aggregate.cell.id == 48
            && released.aggregate.counts.observationContributions == 12
            && released.aggregate.counts.distinctContributors == 4
            && released.aggregate.counts.typeObservationContributions.empty()
            && !released.aggregate.counts.semanticEvidence
            && representation.taxonomyId == "acceptance-road-users" && representation.taxonomyVersion == "1"
            && representation.bins.size() == 1 && representation.bins.front().categoryId == "Cyclist"
            && representation.bins.front().observationContributions == 12
            && representation.bins.front().distinctContributors == 4
            && representation.minimumDistinctContributors == 4
            && representation.maxLoss == .5 && representation.meanLoss == .5,
            "Real coordinator/store did not preserve the approved complete Cyclist representation");
    };
    exactSemantic(*release);
    auto recipient = (*client)[options.recipientDatabase][options.recipientCollection];
    auto journal = (*client)[options.journalDatabase][options.journalCollection];
    const auto initialRecipientCount = recipient.count_documents({});
    const auto initialJournalCount = journal.count_documents({});
    PublicationStore store(client, options);
    store.prepare(*release);
    require(recipient.count_documents({}) == initialRecipientCount
        && journal.count_documents({}) == initialJournalCount + 1,
        "Semantic acceptance prepare disclosed output or omitted durable intent");
    require(!publisher.deliver(400, [&](const auto& immutable) {
        exactSemantic(immutable);
        require(store.publish(immutable) == SinkResult::Acknowledged,
            "Real semantic acceptance publication was not acknowledged by MongoDB");
        return SinkResult::Retry; // Simulate loss after the public write, before coordinator ACK.
    }), "Lost semantic acknowledgement prematurely retired coordinator support");
    require(publisher.pendingRelease() == release && publisher.state().retiredThroughMs == 0
        && recipient.count_documents({}) == initialRecipientCount + 1,
        "Semantic acknowledgement loss changed the immutable pending release or duplicated output");
    PublicationStore restarted(client, options);
    auto durable = restarted.recoverStream(config.runId, config.sensorId, config.applicationId);
    require(durable.size() == 1 && !durable.front().committed,
        "Real semantic pipeline did not recover its prepared post-insert intent");
    exactSemantic(durable.front().release);
    require(restarted.reconcile(durable.front().release) == SinkResult::Acknowledged,
        "Recovered real semantic payload did not match visible MongoDB bytes");
    require(publisher.deliver(400, [&](const auto& immutable) {
        exactSemantic(immutable);
        require(restarted.reconcile(immutable) == SinkResult::Acknowledged,
            "Lost-ACK retry failed to reconcile exact semantic output");
        restarted.commit(immutable);
        return SinkResult::Acknowledged;
    }) && !publisher.pendingRelease() && publisher.state().retiredThroughMs == 400,
        "Reconciled semantic commit failed to retire exactly the approved interval");
    durable = restarted.recoverStream(config.runId, config.sensorId, config.applicationId);
    require(durable.size() == 1 && durable.front().committed,
        "Real semantic pipeline recovery lost committed state");
    exactSemantic(durable.front().release);
    require(restarted.publish(durable.front().release) == SinkResult::Acknowledged
        && recipient.count_documents({}) == initialRecipientCount + 1,
        "Real semantic pipeline recovery changed immutable bytes or inserted a duplicate");
    const auto stored = recipient.find_one(make_document(kvp("_id", release->releaseId)));
    require(static_cast<bool>(stored), "Real semantic recipient payload is missing");
    const auto first = *stored->view()["cells"].get_array().value.begin();
    const auto persistedSemantic = first.get_document().view()["semantic"].get_document().view();
    const auto bin = *persistedSemantic["categories"].get_array().value.begin();
    require(field(persistedSemantic, "taxonomy_id") == "acceptance-road-users"
        && field(persistedSemantic, "taxonomy_version") == "1"
        && field(bin.get_document().view(), "category_id") == "Cyclist"
        && bin.get_document().view()["observation_contributions"].get_int64().value == 12
        && bin.get_document().view()["distinct_contributors"].get_int64().value == 4,
        "Real recipient document does not contain the approved Cyclist counts/version");
    const auto json = bsoncxx::to_json(stored->view());
    for (const auto* forbidden : {"semantic_evidence", "type_observation_contributions", "Adult", "Child",
        "adult-a", "adult-b", "child-a", "child-b", "contributor_ids"})
        require(json.find(forbidden) == std::string::npos,
            std::string("Private semantic source evidence leaked in acceptance payload: ") + forbidden);
}
void realSemanticFirstPipeline(std::shared_ptr<mongocxx::client> client,
    const ump::PublicationStoreOptions& options) {
    using namespace ump;
    const auto taxonomy = std::make_shared<const SemanticTaxonomy>("semantic-first-store", "1",
        std::vector<SemanticNode>{{"road_user", "", 1, {}},
            {"pedestrian", "road_user", 0, {"raw pedestrian"}},
            {"cyclist", "road_user", .5, {}},
            {"adult_cyclist", "cyclist", 0, {"raw adult cyclist"}},
            {"child_cyclist", "cyclist", 0, {"raw child cyclist"}}});
    AggregationConfig config{"semantic-first-store-acceptance", "agbs", "application", {0,0,80,80,2}, 100, 400};
    config.history = HistoryLimits{2000,32,10000,1000000,128};
    config.semanticTaxonomy = taxonomy;
    MetricEvaluator evaluator(MetricPolicy{"original-semantic-first-policy", "1", {
        {MetricId::DistinctContributors,1,{}}, {MetricId::CellSideM,{},40},
        {MetricId::MinCategoryDistinctContributors,5,{}}, {MetricId::SemanticMaxLoss,{},1},
        {MetricId::WindowDurationMs,{},800}, {MetricId::AgeAtEvaluationMs,{},800}}}, taxonomy);
    AggregationHistory history(config,*config.history);
    std::vector<SpatialSelection> selected;
    AdaptiveAggregation engine(config,{AdaptationStrategy::SemanticFirst,100,800,16},{1,128,true},
        evaluator,[&](const auto& proposal) {selected.push_back(proposal);});
    std::vector<CellObservation> rows;
    for (int id=48;id<=51;++id) {
        const auto cell=historyCell(config.coverage,id,2);
        for (int n=0;n<4;++n) rows.push_back({"private-p-"+std::to_string(id)+"-"+std::to_string(n),"raw pedestrian",cell});
        for (int n=0;n<2;++n) {
            rows.push_back({"private-a-"+std::to_string(id)+"-"+std::to_string(n),"raw adult cyclist",cell});
            rows.push_back({"private-c-"+std::to_string(id)+"-"+std::to_string(n),"raw child cyclist",cell});
        }
    }
    for (int time:{100,200,300}) {
        history.append({config.runId,config.sensorId,static_cast<std::uint64_t>(time/100),
            time,ObservationStatus::Measured,rows});
        engine.advance(time,history);
    }
    history.advance(400);engine.advance(400,history);
    require(selected.size()==1 && selected.front().semanticPriority
        && selected.front().semanticPriority->lossCeiling==0
        && selected.front().semanticPriority->actualMaxLoss==0
        && selected.front().selectedCells==1 && selected.front().candidate.cells.front().cell.id==12,
        "Semantic First did not choose the immediately available exact parent");
    PublicationCoordinator publisher(config,evaluator);
    const auto release=publisher.seal(selected.front(),400);
    const auto exact=[&](const ReleaseSnapshot& snapshot) {
        require(snapshot.startMs==0 && snapshot.endMs==400 && snapshot.sealedAtMs==400
            && snapshot.policyId=="original-semantic-first-policy" && snapshot.policyVersion=="1"
            && snapshot.cells.size()==1 && snapshot.cells.front().aggregate.cell.id==12,
            "Semantic First changed immutable scope or original hard-policy provenance");
        const auto& cell=snapshot.cells.front();
        require(cell.aggregate.counts.observationContributions==96
            && cell.aggregate.counts.distinctContributors==32
            && cell.aggregate.counts.typeObservationContributions.empty()
            && !cell.aggregate.counts.semanticEvidence && cell.semantic
            && cell.semantic->maxLoss==0 && cell.semantic->meanLoss==0
            && cell.semantic->minimumDistinctContributors==8 && cell.semantic->bins.size()==3,
            "Semantic First recipient leaked evidence or changed exact counts/loss");
        const auto& bins=cell.semantic->bins;
        require(bins[0].categoryId=="adult_cyclist" && bins[0].observationContributions==24
            && bins[0].distinctContributors==8 && bins[1].categoryId=="child_cyclist"
            && bins[1].observationContributions==24 && bins[1].distinctContributors==8
            && bins[2].categoryId=="pedestrian" && bins[2].observationContributions==48
            && bins[2].distinctContributors==16,"Semantic First recovery changed the approved category partition");
    };
    exact(*release);
    auto recipient=(*client)[options.recipientDatabase][options.recipientCollection];
    const auto initial=recipient.count_documents({});
    PublicationStore store(client,options);store.prepare(*release);
    require(recipient.count_documents({})==initial,"Semantic First prepare disclosed its private trial");
    require(!publisher.deliver(400,[&](const auto& immutable) {
        exact(immutable);
        require(store.publish(immutable)==SinkResult::Acknowledged,"Semantic First store write failed");
        return SinkResult::Retry;
    }),"Semantic First lost acknowledgement retired observed support");
    require(publisher.pendingRelease()==release && publisher.state().retiredThroughMs==0
        && recipient.count_documents({})==initial+1,"Semantic First lost-ACK state or deduplication changed");
    PublicationStore restarted(client,options);
    auto recovered=restarted.recoverStream(config.runId,config.sensorId,config.applicationId);
    require(recovered.size()==1 && !recovered.front().committed,"Semantic First prepared journal was not recovered");
    exact(recovered.front().release);
    require(publisher.deliver(400,[&](const auto& immutable) {
        require(restarted.reconcile(immutable)==SinkResult::Acknowledged,"Semantic First lost-ACK reconciliation failed");
        restarted.commit(immutable);return SinkResult::Acknowledged;
    }) && publisher.state().retiredThroughMs==400,"Semantic First commit did not retire exactly its original interval");
    recovered=restarted.recoverStream(config.runId,config.sensorId,config.applicationId);
    require(recovered.size()==1 && recovered.front().committed,"Semantic First durable commit was lost");
    exact(recovered.front().release);
    require(restarted.publish(recovered.front().release)==SinkResult::Acknowledged
        && recipient.count_documents({})==initial+1,"Semantic First immutable retry duplicated public output");
    const auto stored=recipient.find_one(make_document(kvp("_id",release->releaseId)));
    require(static_cast<bool>(stored),"Semantic First recipient document missing");
    const auto json=bsoncxx::to_json(stored->view());
    for (const auto* forbidden:{"semantic_priority","preferred_max_loss","semantic_evidence",
            "type_observation_contributions","private-p-","private-a-","private-c-","raw pedestrian",
            "raw adult cyclist","raw child cyclist"})
        require(json.find(forbidden)==std::string::npos,
            std::string("Semantic First exposed private preference/source evidence: ")+forbidden);
}

} // namespace

int main() {
    try {
        mongocxx::instance instance;
        auto client = std::make_shared<mongocxx::client>(mongocxx::uri{
            "mongodb://localhost:27017/?serverSelectionTimeoutMS=3000&socketTimeoutMS=5000"});
        const auto suffix = uuid();
        ump::PublicationStoreOptions options;
        options.recipientDatabase = "UMP_sem_recipient_" + suffix;
        options.journalDatabase = "UMP_sem_private_" + suffix;
        TestDatabases fixture{(*client)[options.recipientDatabase], (*client)[options.journalDatabase]};
        auto recipient = fixture.recipient[options.recipientCollection];
        auto journal = fixture.journal[options.journalCollection];
        ump::PublicationStore store(client, options);
        const auto release = snapshot();

        store.prepare(release);
        require(recipient.count_documents({}) == 0 && journal.count_documents({}) == 1,
            "Prepare disclosed semantic data or lost private intent");
        mustThrow<std::logic_error>([&] { store.commit(release); }, "Undelivered semantic payload committed");
        ump::PublicationStore restarted(client, options);
        auto pending = restarted.recoverPending();
        require(pending.size() == 1 && pending.front().releaseId == release.releaseId,
            "Prepared semantic intent was not recovered");
        checkSemantic(pending.front());
        require(restarted.reconcile(pending.front()) == ump::SinkResult::Retry,
            "Recovery silently disclosed an undelivered semantic payload");
        require(restarted.publish(pending.front()) == ump::SinkResult::Acknowledged
            && store.publish(release) == ump::SinkResult::Acknowledged
            && recipient.count_documents({}) == 1,
            "Recovered semantic retry changed payload or inserted duplicates");

        const auto stored = recipient.find_one(make_document(kvp("_id", release.releaseId)));
        require(stored && field(stored->view(), "schema") == "ump.release.v1",
            "Opt-in semantic extension changed the outer common-window schema");
        const auto firstSelected = *stored->view()["cells"].get_array().value.begin();
        const auto selected = firstSelected.get_document().view();
        const auto semantic = selected["semantic"].get_document().view();
        require(field(semantic, "schema") == "ump.semantic-release.v1"
            && field(semantic, "taxonomy_id") == "road-user-taxonomy"
            && field(semantic, "taxonomy_version") == "v1"
            && semantic["min_category_distinct_contributors"].get_double().value == 4
            && semantic["semantic_max_loss"].get_double().value == .5
            && semantic["semantic_mean_loss"].get_double().value == .25,
            "Semantic BSON metadata does not follow its public schema");
        const auto json = bsoncxx::to_json(stored->view());
        for (const auto* forbidden : {"semantic_evidence", "type_observation_contributions", "contributor_ids",
            "source_cells", "suppressed", "terminal_type"})
            require(json.find(forbidden) == std::string::npos,
                std::string("Private field crossed semantic publication boundary: ") + forbidden);

        // Acknowledgement loss is reconciled from identical visible bytes; recovery
        // itself remains read-only and retains the uncommitted private intent.
        ump::PublicationStore acknowledgementLost(client, options);
        require(acknowledgementLost.reconcile(release) == ump::SinkResult::Acknowledged
            && acknowledgementLost.recoverPending().size() == 1,
            "Semantic acknowledgement reconciliation erased or changed private intent");
        acknowledgementLost.commit(release);
        acknowledgementLost.commit(release);
        require(acknowledgementLost.recoverPending().empty(), "Semantic commit was not idempotent");
        auto stream = acknowledgementLost.recoverStream(release.runId, release.sensorId, release.applicationId);
        require(stream.size() == 1 && stream.front().committed, "Committed semantic stream recovery failed");
        checkSemantic(stream.front().release);
        require(acknowledgementLost.publish(stream.front().release) == ump::SinkResult::Acknowledged,
            "Committed semantic recovery did not round-trip exact immutable bytes");

        const auto conflicting = [&](auto change, const char* label) {
            auto changed = release;
            change(*changed.cells.front().semantic);
            mustThrow<ump::PublicationConflict>([&] { store.prepare(changed); }, label);
            mustThrow<ump::PublicationConflict>([&] { store.publish(changed); }, label);
            mustThrow<ump::PublicationConflict>([&] { store.reconcile(changed); }, label);
        };
        conflicting([](auto& value) { value.taxonomyVersion = "v2"; }, "Taxonomy-version conflict accepted");
        conflicting([](auto& value) { value.taxonomyId = "other-taxonomy"; }, "Taxonomy-ID conflict accepted");
        conflicting([](auto& value) { value.bins[0].categoryId = "walking"; }, "Semantic-category conflict accepted");
        conflicting([](auto& value) { ++value.bins[0].observationContributions; --value.bins[1].observationContributions; },
            "Semantic-category contribution conflict accepted");
        conflicting([](auto& value) { ++value.bins[0].distinctContributors; --value.bins[1].distinctContributors;
                value.minimumDistinctContributors = 3; }, "Semantic-category distinct-count conflict accepted");
        conflicting([](auto& value) { value.meanLoss = .3; }, "Semantic-loss conflict accepted");
        auto changed = release;
        changed.cells.front().semantic.reset();
        mustThrow<ump::PublicationConflict>([&] { store.publish(changed); }, "Semantic payload was removed under an existing ID");

        const auto invalid = [&](auto change, const char* label) {
            auto rejected = snapshot(2000);
            change(rejected);
            mustThrow<std::invalid_argument>([&] { store.prepare(rejected); }, label);
        };
        invalid([](auto& r) {
            constexpr std::uint64_t beyond = 9007199254740992ULL;
            auto& cell = r.cells.front();
            cell.aggregate.counts.observationContributions = cell.aggregate.counts.distinctContributors = beyond;
            cell.aggregate.counts.meanSampleOccupancy = static_cast<double>(beyond);
            cell.semantic->bins = {{"road_user", beyond, beyond}};
            cell.semantic->minimumDistinctContributors = static_cast<double>(beyond);
            cell.semantic->maxLoss = cell.semantic->meanLoss = 1;
        }, "Semantic count outside the exact numeric metric range accepted");
        invalid([](auto& r) { r.cells.front().semantic->taxonomyId.clear(); }, "Empty taxonomy ID accepted");
        invalid([](auto& r) { r.cells.front().semantic->taxonomyVersion.clear(); }, "Unversioned taxonomy accepted");
        invalid([](auto& r) { r.cells.front().semantic->bins.clear(); }, "Empty semantic cut accepted");
        invalid([](auto& r) { r.cells.front().semantic->bins[1].categoryId = "pedestrian"; }, "Duplicate semantic categories accepted");
        invalid([](auto& r) { r.cells.front().semantic->bins[0].categoryId.clear(); }, "Empty semantic category accepted");
        invalid([](auto& r) { r.cells.front().semantic->minimumDistinctContributors = 3; }, "Inconsistent minimum support accepted");
        invalid([](auto& r) { r.cells.front().semantic->minimumDistinctContributors = 0; }, "Zero minimum support accepted");
        invalid([](auto& r) { r.cells.front().semantic->maxLoss = std::numeric_limits<double>::infinity(); }, "Infinite semantic loss accepted");
        invalid([](auto& r) { r.cells.front().semantic->meanLoss = std::numeric_limits<double>::quiet_NaN(); }, "NaN semantic loss accepted");
        invalid([](auto& r) { r.cells.front().semantic->maxLoss = 1.01; }, "Semantic loss above one accepted");
        invalid([](auto& r) { r.cells.front().semantic->meanLoss = -.1; }, "Negative semantic loss accepted");
        invalid([](auto& r) { r.cells.front().semantic->meanLoss = .6; }, "Mean loss above maximum accepted");
        invalid([](auto& r) { --r.cells.front().semantic->bins[0].observationContributions; }, "Missing category observations accepted");
        invalid([](auto& r) { --r.cells.front().semantic->bins[0].distinctContributors; }, "Missing category distinct support accepted");
        invalid([](auto& r) { r.cells.front().semantic->bins[0].distinctContributors = 13; }, "Category distinct support above observations accepted");
        invalid([](auto& r) { r.cells.front().semantic->bins[0].observationContributions = std::numeric_limits<std::uint64_t>::max(); },
            "Overflowing category sum accepted");
        invalid([](auto& r) { r.cells.front().aggregate.counts.typeObservationContributions["private_type"] = 1; },
            "Raw per-type evidence accepted with semantic output");
        invalid([](auto& r) { r.cells.front().aggregate.counts.semanticEvidence.emplace(); },
            "Private semantic evidence accepted with semantic output");
        invalid([](auto& r) {
            r.coordinationCell = r.cells.front().aggregate.cell;
            r.releaseId = "ump-release-v2/" + r.releaseId.substr(std::string("ump-release-v1/").size()) + "/12/1";
        }, "Semantic payload accepted in unsupported cell-local coordination");
        auto small = options;
        small.maxBytes = 2048;
        ump::PublicationStore bounded(client, small);
        changed = snapshot(2000);
        changed.cells.front().semantic->taxonomyVersion.assign(2049, 'v');
        mustThrow<std::length_error>([&] { bounded.prepare(changed); }, "Semantic strings bypassed byte budget");
        changed = snapshot(2000);
        changed.cells.front().semantic->bins[0].categoryId.assign(2049, 'c');
        mustThrow<std::length_error>([&] { bounded.prepare(changed); }, "Semantic categories bypassed byte budget");
        require(recipient.count_documents({}) == 1 && journal.count_documents({}) == 1,
            "Rejected semantic data left partial durable or recipient state");

        // Legacy v1 remains byte-for-byte identical and recovers without semantic data.
        const auto legacy = snapshot(1000, false);
        require(store.publish(legacy) == ump::SinkResult::Acknowledged, "Legacy v1 publishing regressed");
        store.commit(legacy);
        const auto legacyRow = recipient.find_one(make_document(kvp("_id", legacy.releaseId)));
        const auto expectedLegacy = legacyPayload(legacy);
        require(legacyRow && legacyRow->view().length() == expectedLegacy.view().length()
            && std::memcmp(legacyRow->view().data(), expectedLegacy.view().data(), expectedLegacy.view().length()) == 0,
            "Disabled semantics changed legacy v1 BSON bytes");
        changed = legacy;
        changed.cells.front().semantic = release.cells.front().semantic;
        mustThrow<ump::PublicationConflict>([&] { store.publish(changed); }, "Semantic data added to immutable legacy release");
        stream = store.recoverStream(release.runId, release.sensorId, release.applicationId);
        require(stream.size() == 2 && stream[0].release.cells.front().semantic
            && !stream[1].release.cells.front().semantic, "Mixed semantic/legacy stream recovery changed optional presence");

        // An untrusted/malformed semantic journal cannot be silently downgraded.
        const auto tampered = snapshot(2000);
        store.prepare(tampered);
        journal.update_one(make_document(kvp("_id", tampered.releaseId)),
            make_document(kvp("$set", make_document(kvp("release.cells.0.semantic.schema", "untrusted.schema")))));
        mustThrow<ump::PublicationConflict>([&] { store.recoverPending(); }, "Unknown semantic journal schema accepted");
        journal.update_one(make_document(kvp("_id", tampered.releaseId)),
            make_document(kvp("$set", make_document(kvp("release.cells.0.semantic.schema", "ump.semantic-release.v1")))));
        pending = store.recoverPending();
        require(pending.size() == 1, "Restored private intent did not recover exactly once");
        checkSemantic(pending.front());
        require(recipient.count_documents({}) == 2, "Read-only semantic recovery disclosed pending data");
        realSemanticPipeline(client, options);
        realSemanticFirstPipeline(client, options);
        std::cout << "Semantic publication store tests passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Semantic publication store failure: " << error.what() << '\n';
        return 1;
    }
}
