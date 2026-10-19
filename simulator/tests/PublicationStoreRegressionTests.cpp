#include "PublicationStore.hpp"
#include <bsoncxx/builder/basic/document.hpp>
#include <bsoncxx/json.hpp>
#include <mongocxx/instance.hpp>
#include <mongocxx/uri.hpp>
#include <array>
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <random>
#include <sstream>
#include <stdexcept>

namespace {
using bsoncxx::builder::basic::kvp;
using bsoncxx::builder::basic::make_document;

std::string stringField(bsoncxx::document::view row, const char* key) {
    const auto value = row[key].get_string().value;
    return {value.data(), value.size()};
}

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

// Own only two new UUID databases. Never enumerate, modify or drop any other database.
struct TestDatabases {
    mongocxx::database recipient, journal;
    ~TestDatabases() {
        try { recipient.drop(); journal.drop(); }
        catch (const std::exception& error) {
            std::cerr << "Publication fixture cleanup failed: " << error.what() << '\n';
        }
    }
};

ump::ReleaseSnapshot snapshot(std::int64_t start = 0, bool empty = false) {
    ump::ReleaseSnapshot release;
    release.runId = "publication-store-test-run";
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
    if (!empty) {
        ump::AggregateCounts counts;
        counts.observationContributions = 24;
        counts.distinctContributors = 8;
        counts.meanSampleOccupancy = 2.4;
        release.cells.push_back({{{12, 1, 0, 0, 20, 20}, counts}, "test-policy/effective"});
    }
    return release;
}
}

int main() {
    try {
        mongocxx::instance instance;
        auto client = std::make_shared<mongocxx::client>(mongocxx::uri{
            "mongodb://localhost:27017/?serverSelectionTimeoutMS=3000&socketTimeoutMS=5000"});
        const auto suffix = uuid();
        ump::PublicationStoreOptions options;
        options.recipientDatabase = "UMP_pub_recipient_" + suffix;
        options.journalDatabase = "UMP_pub_private_" + suffix;
        TestDatabases fixture{(*client)[options.recipientDatabase], (*client)[options.journalDatabase]};
        auto recipient = fixture.recipient[options.recipientCollection];
        auto journal = fixture.journal[options.journalCollection];
        ump::PublicationStore store(client, options);
        auto release = snapshot();

        store.prepare(release);
        require(recipient.count_documents({}) == 0 && journal.count_documents({}) == 1,
            "Prepare disclosed output or failed to journal intent");
        require(store.reconcile(release) == ump::SinkResult::Retry,
            "Undelivered intent was acknowledged");
        mustThrow<std::logic_error>([&] { store.commit(release); },
            "Undelivered nonempty intent committed");

        // Reconstructing a store simulates process failure after durable prepare.
        ump::PublicationStore restarted(client, options);
        auto pending = restarted.recoverPending();
        require(pending.size() == 1 && pending[0].releaseId == release.releaseId,
            "Crash recovery lost prepared intent");
        require(restarted.reconcile(pending[0]) == ump::SinkResult::Retry
                && recipient.count_documents({}) == 0,
            "Read-only recovery published a potentially stale pending snapshot");
        require(restarted.publish(pending[0]) == ump::SinkResult::Acknowledged,
            "Policy-authorized replay failed");
        require(store.publish(release) == ump::SinkResult::Acknowledged
                && recipient.count_documents({}) == 1,
            "Identical replay was not exactly once");

        // Ignore the public write acknowledgement and reconstruct before private commit.
        ump::PublicationStore lostAcknowledgement(client, options);
        require(lostAcknowledgement.reconcile(release) == ump::SinkResult::Acknowledged,
            "Visible insert without commit could not be reconciled");
        require(lostAcknowledgement.recoverPending().size() == 1,
            "Public insertion incorrectly erased private pending state");
        lostAcknowledgement.commit(release);
        lostAcknowledgement.commit(release);
        require(lostAcknowledgement.recoverPending().empty(), "Committed intent remained pending");
        auto stream = lostAcknowledgement.recoverStream(release.runId, release.sensorId, release.applicationId);
        require(stream.size() == 1 && stream[0].committed
                && stream[0].release.cells[0].aggregate.counts.typeObservationContributions.empty()
                && stream[0].release.cells[0].aggregate.counts.meanSampleOccupancy == 2.4,
            "Durable stream audit did not preserve payload or commit state");

        // Every selected payload field participates in conflict detection, not just totals.
        auto changed = release;
        changed.policyVersion = "v2";
        mustThrow<ump::PublicationConflict>([&] { store.prepare(changed); }, "Policy conflict accepted");
        mustThrow<ump::PublicationConflict>([&] { store.reconcile(changed); }, "Visible policy conflict accepted");
        changed = release;
        changed.cells[0].aggregate.cell.x = 1;
        mustThrow<ump::PublicationConflict>([&] { store.publish(changed); }, "Geometry conflict accepted");
        changed = release;
        changed.cells[0].aggregate.counts.observationContributions++;
        mustThrow<ump::PublicationConflict>([&] { store.publish(changed); }, "Count conflict accepted");
        changed = release;
        changed.cells[0].effectivePolicyId += "-changed";
        mustThrow<ump::PublicationConflict>([&] { store.publish(changed); }, "Effective policy conflict accepted");
        changed = release;
        changed.cells[0].aggregate.counts.typeObservationContributions["bicycle"]++;
        mustThrow<std::invalid_argument>([&] { store.publish(changed); }, "Unassessed type contribution accepted");
        changed = release;
        changed.sealedAtMs++;
        mustThrow<ump::PublicationConflict>([&] { store.publish(changed); }, "Seal timestamp conflict accepted");
        require(recipient.count_documents({}) == 1, "Conflict handling altered recipient document count");

        // Empty/suppressed windows carry interval intent only in the private database.
        const auto suppressed = snapshot(1000, true);
        store.prepare(suppressed);
        require(store.publish(suppressed) == ump::SinkResult::Acknowledged,
            "Empty window was not acknowledged privately");
        store.commit(suppressed);
        require(recipient.count_documents({}) == 1 && journal.count_documents({}) == 2,
            "Suppression emitted a revealing empty recipient record");
        const auto publicRow = recipient.find_one(make_document(kvp("_id", release.releaseId)));
        require(static_cast<bool>(publicRow), "Recipient output missing");
        const auto publicJson = bsoncxx::to_json(publicRow->view());
        for (const auto* forbidden : {"suppressed", "global", "contributor_id", "missing_samples",
            "expected_samples", "attempts", "source_cells", "type_observation_contributions", "private_publication_journal"})
            require(publicJson.find(forbidden) == std::string::npos,
                std::string("Private field crossed recipient boundary: ") + forbidden);
        require(!publicRow->view()["counts"] && !publicRow->view()["state"]
                && publicRow->view()["cells"].get_array().value.begin() != publicRow->view()["cells"].get_array().value.end(),
            "Public payload contains a whole-window total or lifecycle state");

        const auto waiting = snapshot(2000);
        store.prepare(waiting);
        require(store.recoverPending().size() == 1, "Pending intent audit is inconsistent");
        mustThrow<std::length_error>([&] {
            store.recoverStream(release.runId, release.sensorId, release.applicationId, 1);
        }, "Recovery ignored its record budget");
        auto smallRecovery = options;
        smallRecovery.maxRecoveryBytes = 32;
        ump::PublicationStore recoveryBounded(client, smallRecovery);
        mustThrow<std::length_error>([&] { recoveryBounded.recoverPending(); },
            "Recovery ignored its byte budget");
        require(recipient.count_documents({}) == 1, "Recovery unexpectedly disclosed an undelivered window");

        // Resource and namespace validation must fail before durable intent or disclosure.
        auto tiny = options;
        tiny.maxBytes = 256;
        ump::PublicationStore tinyStore(client, tiny);
        mustThrow<std::length_error>([&] { tinyStore.prepare(snapshot(3000)); }, "BSON byte budget ignored");
        changed = snapshot(3000);
        changed.cells[0].aggregate.counts.observationContributions = std::numeric_limits<std::uint64_t>::max();
        mustThrow<std::invalid_argument>([&] { store.prepare(changed); }, "uint64 count silently overflowed BSON");
        changed = snapshot(3000);
        changed.cells[0].aggregate.cell.width = std::numeric_limits<double>::infinity();
        mustThrow<std::invalid_argument>([&] { store.prepare(changed); }, "Non-finite geometry accepted");
        changed = snapshot(3000);
        changed.releaseId = "unrelated-id";
        mustThrow<std::invalid_argument>([&] { store.prepare(changed); }, "Unstable release ID accepted");
        auto invalid = options;
        invalid.journalDatabase = invalid.recipientDatabase;
        mustThrow<std::invalid_argument>([&] { ump::PublicationStore rejected(client, invalid); },
            "Private and recipient databases were allowed to coincide");
        invalid = options;
        invalid.recipientDatabase = "UMP_Test_Case";
        invalid.journalDatabase = "ump_test_case";
        mustThrow<std::invalid_argument>([&] { invalid.validate(); },
            "Case-only recipient/private database overlap was allowed");
        invalid = options;
        invalid.recipientDatabase = "Simulation";
        mustThrow<std::invalid_argument>([&] { ump::PublicationStore rejected(client, invalid); },
            "Raw Simulation namespace was allowed for recipient output");
        invalid = options;
        invalid.maxBytes = 16 * 1024 * 1024;
        mustThrow<std::invalid_argument>([&] { ump::PublicationStore rejected(client, invalid); },
            "MongoDB hard document limit was not reserved");
        require(recipient.count_documents({}) == 1 && journal.count_documents({}) == 3,
            "Rejected input left partial persistence");
        // Cell-local intervals with equal timestamps have distinct immutable identities.
        // v1 snapshots keep the original byte layout; v2 adds a canonical scope.
        require(stringField(publicRow->view(), "schema") == "ump.release.v1"
                && !publicRow->view()["coordination_cell"],
            "Legacy release BSON gained scoped metadata or changed schema");
        const auto scopedSnapshot = [&](int id) {
            auto scoped = snapshot();
            auto& cell = scoped.cells.front().aggregate.cell;
            cell.id = id;
            cell.x = id == 12 ? 0 : 20;
            scoped.coordinationCell = cell;
            scoped.releaseId = "ump-release-v2/"
                + scoped.releaseId.substr(std::string("ump-release-v1/").size())
                + "/" + std::to_string(id) + "/1";
            return scoped;
        };
        const auto scopedA = scopedSnapshot(12), scopedB = scopedSnapshot(13);
        require(scopedA.releaseId != scopedB.releaseId,
            "Independent scoped intervals collided in their release IDs");
        store.prepare(scopedA);
        auto scopedPending = store.recoverPending();
        const auto recoveredA = std::find_if(scopedPending.begin(), scopedPending.end(),
            [&](const auto& value) { return value.releaseId == scopedA.releaseId; });
        require(recoveredA != scopedPending.end() && recoveredA->coordinationCell
                && recoveredA->coordinationCell->id == 12
                && recoveredA->coordinationCell->width == 20,
            "Prepared scoped recovery lost its coordination footprint");
        require(store.publish(*recoveredA) == ump::SinkResult::Acknowledged
                && store.publish(scopedA) == ump::SinkResult::Acknowledged,
            "Scoped retry did not preserve immutable payload identity");
        store.commit(scopedA);
        store.prepare(scopedB);
        require(store.publish(scopedB) == ump::SinkResult::Acknowledged,
            "Equal-interval adjacent scoped release failed");
        store.commit(scopedB);
        const auto scopedRow = recipient.find_one(make_document(kvp("_id", scopedB.releaseId)));
        require(scopedRow && stringField(scopedRow->view(), "schema") == "ump.release.v2"
                && scopedRow->view()["coordination_cell"].get_document().view()["cell_id"].get_int32().value == 13,
            "Scoped recipient BSON omitted schema or geometry");
        const auto recoveredStream = store.recoverStream(release.runId, release.sensorId, release.applicationId);
        std::size_t scopedCommitted = 0;
        for (const auto& item : recoveredStream)
            if (item.release.coordinationCell) {
                require(item.committed, "Committed scoped intent recovered as pending");
                ++scopedCommitted;
            }
        require(scopedCommitted == 2 && recipient.count_documents({}) == 3
                && journal.count_documents({}) == 5,
            "Scoped recovery, exactly-once inserts or journal accounting failed");
        changed = scopedA;
        changed.coordinationCell->id = 13;
        mustThrow<std::invalid_argument>([&] { store.prepare(changed); },
            "Changed coordination scope retained the same release identity");
        changed = scopedB;
        changed.cells.front().aggregate.cell.id = 12;
        mustThrow<std::invalid_argument>([&] { store.prepare(changed); },
            "Scoped store accepted an out-of-footprint cell");
        changed = scopedB;
        changed.cells.front().aggregate.cell.x += 1;
        mustThrow<std::invalid_argument>([&] { store.prepare(changed); },
            "Scoped store accepted geometry inconsistent with its scope");
        require(recipient.count_documents({}) == 3 && journal.count_documents({}) == 5,
            "Rejected scoped input left partial persistence");
        std::cout << "Publication store regression tests passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Publication store regression failure: " << error.what() << '\n';
        return 1;
    }
}
