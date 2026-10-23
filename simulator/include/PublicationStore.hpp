#pragma once

#include "PublicationCoordinator.hpp"
#include <mongocxx/client.hpp>
#include <memory>
#include <stdexcept>
#include <vector>

namespace ump {

struct PublicationStoreOptions {
    std::string recipientDatabase;
    std::string recipientCollection = "releases";
    std::string journalDatabase;
    std::string journalCollection = "publication_journal";
    std::size_t maxBytes = 8 * 1024 * 1024;
    std::size_t maxRecoveryBytes = 16 * 1024 * 1024;
    void validate() const;
};

struct PublicationJournalEntry {
    ReleaseSnapshot release;
    bool committed;
};

class PublicationConflict : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

// Single-threaded external adapter. Recipient credentials must grant access only to
// recipientDatabase; a separate database name is a boundary, not an ACL provisioner.
// The caller owns policy/time validation before publish. Recovery never publishes.
class PublicationStore {
public:
    PublicationStore(std::shared_ptr<mongocxx::client> client, PublicationStoreOptions options);
    ~PublicationStore();
    PublicationStore(const PublicationStore&) = delete;
    PublicationStore& operator=(const PublicationStore&) = delete;

    // Durable private intent precedes every possible disclosure.
    // Same ID/content is idempotent; changed content under an existing ID is an error.
    void prepare(const ReleaseSnapshot& release);
    SinkResult publish(const ReleaseSnapshot& release);
    // Retire only after an identical recipient document is visible, or for an empty release.
    void commit(const ReleaseSnapshot& release);

    // Empty scopes have no recipient write to bracket. Durably insert their final
    // private record atomically before retiring the in-memory reservation. Identical
    // retries are idempotent; legacy prepared records are checked and completed.
    void retireEmpty(const ReleaseSnapshot& release);

    // Read-only majority reads: never send an undelivered/stale snapshot to recipients.
    // An identical already-visible release can be acknowledged after acknowledgement loss.
    SinkResult reconcile(const ReleaseSnapshot& release) const;
    std::vector<ReleaseSnapshot> recoverPending(std::size_t maxRecords = 1024) const;
    std::vector<PublicationJournalEntry> recoverStream(const std::string& runId,
        const std::string& sensorId, const std::string& applicationId,
        std::size_t maxRecords = 1024) const;

private:
    class Impl;
    std::unique_ptr<Impl> impl;
};
} // namespace ump
