#include "PublicationStore.hpp"
#include <bsoncxx/builder/basic/array.hpp>
#include <bsoncxx/builder/basic/document.hpp>
#include <mongocxx/exception/exception.hpp>
#include <mongocxx/options/find.hpp>
#include <mongocxx/read_concern.hpp>
#include <mongocxx/read_preference.hpp>
#include <mongocxx/write_concern.hpp>
#include <algorithm>
#include <chrono>
#include <cctype>
#include <cmath>
#include <cstring>
#include <limits>
#include <set>

namespace ump {
namespace {
using bsoncxx::builder::basic::kvp;
using bsoncxx::builder::basic::make_document;
using Document = bsoncxx::document::value;
using View = bsoncxx::document::view;
constexpr std::size_t maximumDocumentBytes = 15 * 1024 * 1024;

bool identical(View first, View second) {
    return first.length() == second.length()
        && std::memcmp(first.data(), second.data(), first.length()) == 0;
}

std::string stringField(View row, const char* key) {
    const auto value = row[key].get_string().value;
    return {value.data(), value.size()};
}

std::int64_t countValue(std::uint64_t value) {
    if (value > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))
        throw std::invalid_argument("Publication count exceeds BSON int64 capacity");
    return static_cast<std::int64_t>(value);
}

std::string keyPart(const std::string& value) {
    return std::to_string(value.size()) + ":" + value;
}

void validateNamespace(const std::string& database, const std::string& collection) {
    if (database.empty() || database.size() > 63 || database.find('\0') != std::string::npos
        || database.find_first_of("/\\. \"$*<>:|?") != std::string::npos
        || collection.empty() || collection.find('\0') != std::string::npos
        || collection.find('$') != std::string::npos || collection.rfind("system.", 0) == 0)
        throw std::invalid_argument("Publication requires valid dedicated MongoDB namespaces");
    std::string lower = database;
    std::transform(lower.begin(), lower.end(), lower.begin(), [](unsigned char value) {
        return static_cast<char>(std::tolower(value));
    });
    if (lower == "simulation" || lower == "admin" || lower == "config" || lower == "local")
        throw std::invalid_argument("Publication must not share a raw/debug or administrative database");
}

Document releaseDocument(const ReleaseSnapshot& release, std::size_t maxBytes) {
    if (release.runId.empty() || release.sensorId.empty() || release.applicationId.empty()
        || release.startMs < 0 || release.endMs <= release.startMs
        || release.sealedAtMs < release.endMs || release.model != "private_final_snapshot")
        throw std::invalid_argument("Publication snapshot has invalid stream, interval or model");
    auto expectedId = std::string(release.coordinationCell ? "ump-release-v2/" : "ump-release-v1/")
        + keyPart(release.runId) + keyPart(release.sensorId)
        + keyPart(release.applicationId) + "/" + std::to_string(release.startMs)
        + "/" + std::to_string(release.endMs);
    if (release.coordinationCell) {
        const auto& scope = *release.coordinationCell;
        if (scope.depth < 1 || scope.depth > 14 || scope.id < 0
            || (scope.id >> (2 * scope.depth)) != 3 || !std::isfinite(scope.x)
            || !std::isfinite(scope.y) || !std::isfinite(scope.width)
            || !std::isfinite(scope.height) || scope.width <= 0 || scope.height != scope.width
            || !std::isfinite(scope.x + scope.width) || !std::isfinite(scope.y + scope.height))
            throw std::invalid_argument("Publication coordination footprint is invalid");
        expectedId += "/" + std::to_string(scope.id) + "/" + std::to_string(scope.depth);
    }
    if (release.releaseId != expectedId)
        throw std::invalid_argument("Publication release ID does not identify its stream interval");
    if (!release.cells.empty() && (release.policyId.empty() || release.policyVersion.empty()))
        throw std::invalid_argument("Selected publication requires a versioned policy");
    std::size_t stringBytes = 0;
    const auto accountString = [&](const std::string& value) {
        if (value.size() > maxBytes - stringBytes)
            throw std::length_error("Publication BSON size limit exceeded");
        stringBytes += value.size();
    };
    for (const auto* value : {&release.releaseId, &release.runId, &release.sensorId,
        &release.applicationId, &release.model, &release.policyId, &release.policyVersion})
        accountString(*value);
    if (release.cells.size() > maxBytes / 128)
        throw std::length_error("Publication BSON cell size limit exceeded");
    bsoncxx::builder::basic::array cells;
    std::set<int> ids;
    for (const auto& released : release.cells) {
        const auto& aggregate = released.aggregate;
        const auto& cell = aggregate.cell;
        const auto& counts = aggregate.counts;
        if (cell.id < 0 || cell.depth < 1 || !ids.insert(cell.id).second
            || !std::isfinite(cell.x) || !std::isfinite(cell.y)
            || !std::isfinite(cell.width) || !std::isfinite(cell.height)
            || cell.width <= 0 || cell.height <= 0 || released.effectivePolicyId.empty()
            || (counts.meanSampleOccupancy && (!std::isfinite(*counts.meanSampleOccupancy)
                || *counts.meanSampleOccupancy < 0)))
            throw std::invalid_argument("Publication selected cell has invalid geometry, policy or counts");
        if (release.coordinationCell) {
            const auto& scope = *release.coordinationCell;
            if (cell.depth < scope.depth || cell.depth > 14
                || (cell.id >> (2 * (cell.depth - scope.depth))) != scope.id)
                throw std::invalid_argument("Publication selected cell lies outside coordination footprint");
            auto expected = scope;
            for (int depth = scope.depth + 1; depth <= cell.depth; ++depth) {
                const int quadrant = (cell.id >> (2 * (cell.depth - depth))) & 3;
                expected.width /= 2; expected.height /= 2;
                expected.x += (quadrant & 1) * expected.width;
                expected.y += (quadrant >> 1) * expected.height;
            }
            const auto close = [&](double actual, double canonical) {
                return std::abs(actual - canonical) <= std::min(expected.width * 1e-4,
                    1e-6 * std::max({1.0, std::abs(actual), std::abs(canonical)}));
            };
            if (!close(cell.x, expected.x) || !close(cell.y, expected.y)
                || !close(cell.width, expected.width) || !close(cell.height, expected.height))
                throw std::invalid_argument("Publication selected geometry differs from coordination footprint");
        }
        accountString(released.effectivePolicyId);
        // Raw evidence is never a recipient channel. Semantic output is the separately
        // approved representation below, not a serialized copy of its private input.
        if (!counts.typeObservationContributions.empty() || counts.semanticEvidence)
            throw std::invalid_argument("Publication may not contain private type or semantic evidence");
        bsoncxx::builder::basic::document countDocument;
        countDocument.append(kvp("observation_contributions", countValue(counts.observationContributions)),
            kvp("distinct_contributors", countValue(counts.distinctContributors)));
        if (counts.meanSampleOccupancy)
            countDocument.append(kvp("mean_sample_occupancy", *counts.meanSampleOccupancy));
        else countDocument.append(kvp("mean_sample_occupancy", bsoncxx::types::b_null{}));
        bsoncxx::builder::basic::document selected;
        selected.append(kvp("cell_id", cell.id), kvp("depth", cell.depth),
            kvp("x", cell.x), kvp("y", cell.y), kvp("width", cell.width), kvp("height", cell.height),
            kvp("counts", countDocument), kvp("effective_policy_id", released.effectivePolicyId));
        if (released.semantic) {
            // This store verifies the structural boundary only. The coordinator must
            // assess the category cut against its trusted versioned taxonomy first.
            // Keeping this optional extension inside v1 preserves every legacy byte
            // when no semantic representation was requested.
            if (release.coordinationCell)
                throw std::invalid_argument("Semantic publication requires common-window coordination");
            const auto& semantic = *released.semantic;
            if (counts.observationContributions > 9007199254740991ULL
                || semantic.taxonomyId.empty() || semantic.taxonomyVersion.empty() || semantic.bins.empty()
                || !std::isfinite(semantic.minimumDistinctContributors)
                || semantic.minimumDistinctContributors <= 0
                || !std::isfinite(semantic.maxLoss) || semantic.maxLoss < 0 || semantic.maxLoss > 1
                || !std::isfinite(semantic.meanLoss) || semantic.meanLoss < 0
                || semantic.meanLoss > semantic.maxLoss)
                throw std::invalid_argument("Publication semantic representation has invalid metadata or loss");
            accountString(semantic.taxonomyId);
            accountString(semantic.taxonomyVersion);
            if (semantic.bins.size() > maxBytes / 64)
                throw std::length_error("Publication BSON semantic category size limit exceeded");
            std::set<std::string> categoryIds;
            std::uint64_t observations = 0, distinct = 0;
            auto minimum = std::numeric_limits<std::uint64_t>::max();
            bsoncxx::builder::basic::array categories;
            for (const auto& bin : semantic.bins) {
                if (bin.categoryId.empty() || !categoryIds.insert(bin.categoryId).second
                    || bin.observationContributions == 0 || bin.distinctContributors == 0
                    || bin.distinctContributors > bin.observationContributions
                    || bin.observationContributions > counts.observationContributions - observations
                    || bin.distinctContributors > counts.distinctContributors - distinct)
                    throw std::invalid_argument("Publication semantic categories have invalid counts or identities");
                accountString(bin.categoryId);
                observations += bin.observationContributions;
                distinct += bin.distinctContributors;
                minimum = std::min(minimum, bin.distinctContributors);
                categories.append(make_document(kvp("category_id", bin.categoryId),
                    kvp("observation_contributions", countValue(bin.observationContributions)),
                    kvp("distinct_contributors", countValue(bin.distinctContributors))));
                if (categories.view().length() > maxBytes)
                    throw std::length_error("Publication BSON semantic category size limit exceeded");
            }
            if (observations != counts.observationContributions || distinct != counts.distinctContributors
                || semantic.minimumDistinctContributors != static_cast<double>(minimum))
                throw std::invalid_argument("Publication semantic categories disagree with approved scalar counts");
            selected.append(kvp("semantic", make_document(kvp("schema", "ump.semantic-release.v1"),
                kvp("taxonomy_id", semantic.taxonomyId), kvp("taxonomy_version", semantic.taxonomyVersion),
                kvp("min_category_distinct_contributors", semantic.minimumDistinctContributors),
                kvp("semantic_max_loss", semantic.maxLoss), kvp("semantic_mean_loss", semantic.meanLoss),
                kvp("categories", categories))));
        }
        cells.append(selected.extract());
        if (cells.view().length() > maxBytes)
            throw std::length_error("Publication BSON size limit exceeded");
    }
    bsoncxx::builder::basic::document result;
    result.append(kvp("_id", release.releaseId),
        kvp("schema", release.coordinationCell ? "ump.release.v2" : "ump.release.v1"),
        kvp("data_role", "recipient_release"), kvp("run_id", release.runId),
        kvp("sensor_id", release.sensorId), kvp("application_id", release.applicationId),
        kvp("model", release.model), kvp("policy_id", release.policyId),
        kvp("policy_version", release.policyVersion), kvp("start_ms", release.startMs),
        kvp("end_ms", release.endMs), kvp("sealed_at_ms", release.sealedAtMs), kvp("cells", cells));
    if (release.coordinationCell) {
        const auto& scope = *release.coordinationCell;
        result.append(kvp("coordination_cell", make_document(kvp("cell_id", scope.id),
            kvp("depth", scope.depth), kvp("x", scope.x), kvp("y", scope.y),
            kvp("width", scope.width), kvp("height", scope.height))));
    }
    if (result.view().length() > maxBytes)
        throw std::length_error("Publication BSON size limit exceeded");
    return result.extract();
}

Document journalDocument(const ReleaseSnapshot& release, View payload, bool committed,
    std::size_t maxBytes) {
    auto result = make_document(kvp("_id", release.releaseId), kvp("schema", "ump.publication-journal.v1"),
        kvp("data_role", "private_publication_journal"), kvp("run_id", release.runId),
        kvp("sensor_id", release.sensorId), kvp("application_id", release.applicationId),
        kvp("start_ms", release.startMs), kvp("end_ms", release.endMs),
        kvp("state", committed ? "committed" : "prepared"), kvp("release", payload));
    if (result.view().length() > maxBytes)
        throw std::length_error("Publication private journal BSON size limit exceeded");
    return result;
}

ReleaseSnapshot parseRelease(View document) {
    ReleaseSnapshot release;
    release.releaseId = stringField(document, "_id");
    release.runId = stringField(document, "run_id");
    release.sensorId = stringField(document, "sensor_id");
    release.applicationId = stringField(document, "application_id");
    release.model = stringField(document, "model");
    release.policyId = stringField(document, "policy_id");
    release.policyVersion = stringField(document, "policy_version");
    release.startMs = document["start_ms"].get_int64().value;
    release.endMs = document["end_ms"].get_int64().value;
    release.sealedAtMs = document["sealed_at_ms"].get_int64().value;
    const auto schema = stringField(document, "schema");
    const bool scoped = schema == "ump.release.v2";
    if ((!scoped && schema != "ump.release.v1")
        || scoped != static_cast<bool>(document["coordination_cell"]))
        throw PublicationConflict("Publication journal schema and coordination footprint disagree");
    if (scoped) {
        const auto scope = document["coordination_cell"].get_document().view();
        release.coordinationCell = CellGeometry{scope["cell_id"].get_int32().value,
            scope["depth"].get_int32().value, scope["x"].get_double().value,
            scope["y"].get_double().value, scope["width"].get_double().value,
            scope["height"].get_double().value};
    }

    const auto nonnegative = [](std::int64_t count) -> std::uint64_t {
        if (count < 0) throw PublicationConflict("Publication journal contains a negative count");
        return static_cast<std::uint64_t>(count);
    };
    for (auto item : document["cells"].get_array().value) {
        const auto row = item.get_document().view();
        ReleasedCell released;
        released.effectivePolicyId = stringField(row, "effective_policy_id");
        released.aggregate.cell = {row["cell_id"].get_int32().value, row["depth"].get_int32().value,
            row["x"].get_double().value, row["y"].get_double().value,
            row["width"].get_double().value, row["height"].get_double().value};
        auto& counts = released.aggregate.counts;
        const auto values = row["counts"].get_document().view();
        counts.observationContributions = nonnegative(values["observation_contributions"].get_int64().value);
        counts.distinctContributors = nonnegative(values["distinct_contributors"].get_int64().value);
        if (values["mean_sample_occupancy"].type() != bsoncxx::type::k_null)
            counts.meanSampleOccupancy = values["mean_sample_occupancy"].get_double().value;
        if (row["semantic"]) {
            const auto semantic = row["semantic"].get_document().view();
            if (scoped || stringField(semantic, "schema") != "ump.semantic-release.v1")
                throw PublicationConflict("Publication journal semantic schema or coordination is invalid");
            SemanticRepresentation representation;
            representation.taxonomyId = stringField(semantic, "taxonomy_id");
            representation.taxonomyVersion = stringField(semantic, "taxonomy_version");
            representation.minimumDistinctContributors = semantic["min_category_distinct_contributors"].get_double().value;
            representation.maxLoss = semantic["semantic_max_loss"].get_double().value;
            representation.meanLoss = semantic["semantic_mean_loss"].get_double().value;
            for (auto category : semantic["categories"].get_array().value) {
                const auto bin = category.get_document().view();
                representation.bins.push_back({stringField(bin, "category_id"),
                    nonnegative(bin["observation_contributions"].get_int64().value),
                    nonnegative(bin["distinct_contributors"].get_int64().value)});
            }
            released.semantic = std::move(representation);
        }
        release.cells.push_back(std::move(released));
    }
    return release;
}
} // namespace

class PublicationStore::Impl {
public:
    Impl(std::shared_ptr<mongocxx::client> connection, PublicationStoreOptions settings)
        : client(std::move(connection)), options(std::move(settings)) {
        options.validate();
        if (!client) throw std::invalid_argument("Publication store requires a MongoDB client");
        recipient = (*client)[options.recipientDatabase][options.recipientCollection];
        journal = (*client)[options.journalDatabase][options.journalCollection];
        mongocxx::write_concern writes;
        writes.majority(std::chrono::milliseconds{3000});
        writes.journal(true);
        mongocxx::read_concern reads;
        reads.acknowledge_level(mongocxx::read_concern::level::k_majority);
        mongocxx::read_preference primary;
        primary.mode(mongocxx::read_preference::read_mode::k_primary);
        for (auto* collection : {&recipient, &journal}) {
            collection->write_concern(writes);
            collection->read_concern(reads);
            collection->read_preference(primary);
        }
    }

    bool checkJournal(View row, const ReleaseSnapshot& release, View payload) const {
        const auto state = stringField(row, "state");
        if (state != "prepared" && state != "committed")
            throw PublicationConflict("Publication journal has an unknown lifecycle state");
        const bool committed = state == "committed";
        auto expected = journalDocument(release, payload, committed, options.maxBytes);
        if (!identical(row, expected.view()))
            throw PublicationConflict("Publication release ID conflicts with durable private intent");
        return committed;
    }

    bool prepare(const ReleaseSnapshot& release, View payload) {
        auto prepared = journalDocument(release, payload, false, options.maxBytes);
        // Reserve the extra byte in "committed" before accepting any intent.
        journalDocument(release, payload, true, options.maxBytes);
        const auto filter = make_document(kvp("_id", release.releaseId));
        if (auto existing = journal.find_one(filter.view()))
            return checkJournal(existing->view(), release, payload);
        try {
            if (!journal.insert_one(prepared.view()))
                throw std::runtime_error("Publication intent was not durably acknowledged");
        } catch (const mongocxx::exception&) {
            // Includes duplicate writers and an acknowledgement lost after a successful insert.
            if (auto existing = journal.find_one(filter.view()))
                return checkJournal(existing->view(), release, payload);
            throw;
        }
        return false;
    }

    SinkResult reconcile(const ReleaseSnapshot& release, View payload) const {
        if (release.cells.empty()) return SinkResult::Acknowledged;
        auto existing = recipient.find_one(make_document(kvp("_id", release.releaseId)));
        if (!existing) return SinkResult::Retry;
        if (!identical(existing->view(), payload))
            throw PublicationConflict("Publication release ID conflicts with immutable recipient content");
        return SinkResult::Acknowledged;
    }

    std::vector<PublicationJournalEntry> recover(View filter, std::size_t maxRecords) const {
        if (!maxRecords || maxRecords >= static_cast<std::size_t>(std::numeric_limits<std::int64_t>::max()))
            throw std::invalid_argument("Publication recovery requires a finite positive record limit");
        mongocxx::options::find settings;
        settings.limit(static_cast<std::int64_t>(maxRecords + 1));
        settings.sort(make_document(kvp("start_ms", 1), kvp("_id", 1)));
        std::vector<PublicationJournalEntry> results;
        std::size_t bytes = 0;
        for (auto row : journal.find(filter, settings)) {
            if (results.size() == maxRecords || row.length() > options.maxRecoveryBytes - bytes)
                throw std::length_error("Publication recovery budget exceeded; narrow the stream query");
            bytes += row.length();
            auto release = parseRelease(row["release"].get_document().view());
            auto payload = releaseDocument(release, options.maxBytes);
            const bool committed = checkJournal(row, release, payload.view());
            results.push_back({std::move(release), committed});
        }
        return results;
    }

    std::shared_ptr<mongocxx::client> client;
    PublicationStoreOptions options;
    mutable mongocxx::collection recipient, journal;
};

void PublicationStoreOptions::validate() const {
    if (!maxBytes || maxBytes > maximumDocumentBytes || !maxRecoveryBytes)
        throw std::invalid_argument("Publication store requires positive bounded byte limits");
    validateNamespace(recipientDatabase, recipientCollection);
    validateNamespace(journalDatabase, journalCollection);
    const auto fold = [](std::string value) {
        std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) { return std::tolower(c); });
        return value;
    };
    if (fold(recipientDatabase) == fold(journalDatabase))
        throw std::invalid_argument("Recipient output and private journal require separate databases");
}

PublicationStore::PublicationStore(std::shared_ptr<mongocxx::client> client, PublicationStoreOptions options)
    : impl(std::make_unique<Impl>(std::move(client), std::move(options))) {}
PublicationStore::~PublicationStore() = default;

void PublicationStore::prepare(const ReleaseSnapshot& release) {
    auto payload = releaseDocument(release, impl->options.maxBytes);
    impl->prepare(release, payload.view());
}

SinkResult PublicationStore::publish(const ReleaseSnapshot& release) {
    auto payload = releaseDocument(release, impl->options.maxBytes);
    try {
        const bool committed = impl->prepare(release, payload.view());
        const auto known = impl->reconcile(release, payload.view());
        if (known == SinkResult::Acknowledged) return known;
        if (committed)
            throw PublicationConflict("Committed publication is missing from recipient storage");
        try {
            if (impl->recipient.insert_one(payload.view())) return SinkResult::Acknowledged;
        } catch (const mongocxx::exception&) {
            // No replacement/update is allowed. Resolve an ambiguous insert by exact comparison.
            return impl->reconcile(release, payload.view());
        }
    } catch (const mongocxx::exception&) {
        return SinkResult::Retry;
    }
    return SinkResult::Retry;
}

void PublicationStore::commit(const ReleaseSnapshot& release) {
    auto payload = releaseDocument(release, impl->options.maxBytes);
    const auto filter = make_document(kvp("_id", release.releaseId));
    auto existing = impl->journal.find_one(filter.view());
    if (!existing) throw std::logic_error("Publication commit requires durable prepared intent");
    const bool committed = impl->checkJournal(existing->view(), release, payload.view());
    if (impl->reconcile(release, payload.view()) != SinkResult::Acknowledged)
        throw std::logic_error("Publication commit requires acknowledged recipient content");
    if (committed) return;
    auto expected = make_document(kvp("_id", release.releaseId), kvp("state", "prepared"),
        kvp("release", payload.view()));
    try {
        auto result = impl->journal.update_one(expected.view(),
            make_document(kvp("$set", make_document(kvp("state", "committed")))));
        if (!result || result->matched_count() != 1)
            throw PublicationConflict("Publication intent changed before durable commit");
    } catch (const mongocxx::exception&) {
        auto retried = impl->journal.find_one(filter.view());
        if (retried && impl->checkJournal(retried->view(), release, payload.view())) return;
        throw;
    }
}

SinkResult PublicationStore::reconcile(const ReleaseSnapshot& release) const {
    auto payload = releaseDocument(release, impl->options.maxBytes);
    try { return impl->reconcile(release, payload.view()); }
    catch (const mongocxx::exception&) { return SinkResult::Retry; }
}

std::vector<ReleaseSnapshot> PublicationStore::recoverPending(std::size_t maxRecords) const {
    auto records = impl->recover(make_document(kvp("state", "prepared")), maxRecords);
    std::vector<ReleaseSnapshot> releases;
    releases.reserve(records.size());
    for (auto& record : records) releases.push_back(std::move(record.release));
    return releases;
}

std::vector<PublicationJournalEntry> PublicationStore::recoverStream(const std::string& runId,
    const std::string& sensorId, const std::string& applicationId, std::size_t maxRecords) const {
    if (runId.empty() || sensorId.empty() || applicationId.empty())
        throw std::invalid_argument("Publication recovery requires an explicit stream");
    return impl->recover(make_document(kvp("run_id", runId), kvp("sensor_id", sensorId),
        kvp("application_id", applicationId)), maxRecords);
}
} // namespace ump
