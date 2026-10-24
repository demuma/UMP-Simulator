#pragma once

#include "PublicationCoordinator.hpp"
#include <algorithm>
#include <array>
#include <cstring>
#include <iomanip>
#include <limits>
#include <sstream>
#include <type_traits>
#include <utility>

namespace umpReplay {
// Portable SHA-256, with no platform/crypto-library dependency. This is an
// equality audit, not a privacy transform: hashes do not anonymize raw inputs.
class ReplaySha256 {
public:
    void update(const void* input, std::size_t size) {
        const auto* bytes = static_cast<const unsigned char*>(input);
        totalBytes += size;
        while (size) {
            const auto take = std::min(size, block.size() - used);
            std::memcpy(block.data() + used, bytes, take);
            used += take; bytes += take; size -= take;
            if (used == block.size()) { transform(); used = 0; }
        }
    }
    void update(const std::string& value) { update(value.data(), value.size()); }
    std::string hex() const {
        auto copy = *this;
        const std::uint64_t bits = copy.totalBytes * 8;
        const unsigned char start = 0x80, zero = 0;
        copy.update(&start, 1);
        while (copy.used != 56) copy.update(&zero, 1);
        unsigned char length[8];
        for (unsigned i = 0; i < 8; ++i) length[i] = static_cast<unsigned char>(bits >> (56 - i * 8));
        copy.update(length, 8);
        std::ostringstream out;
        out << std::hex << std::setfill('0');
        for (auto word : copy.state) out << std::setw(8) << word;
        return out.str();
    }
private:
    static std::uint32_t rotate(std::uint32_t value, unsigned bits) { return (value >> bits) | (value << (32 - bits)); }
    void transform() {
        static constexpr std::array<std::uint32_t, 64> constants{{
            0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
            0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
            0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
            0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
            0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
            0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
            0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
            0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2}};
        std::uint32_t words[64];
        for (unsigned i = 0; i < 16; ++i)
            words[i] = (std::uint32_t(block[i * 4]) << 24) | (std::uint32_t(block[i * 4 + 1]) << 16)
                | (std::uint32_t(block[i * 4 + 2]) << 8) | std::uint32_t(block[i * 4 + 3]);
        for (unsigned i = 16; i < 64; ++i) {
            const auto a = rotate(words[i - 15], 7) ^ rotate(words[i - 15], 18) ^ (words[i - 15] >> 3);
            const auto b = rotate(words[i - 2], 17) ^ rotate(words[i - 2], 19) ^ (words[i - 2] >> 10);
            words[i] = words[i - 16] + a + words[i - 7] + b;
        }
        auto a=state[0],b=state[1],c=state[2],d=state[3],e=state[4],f=state[5],g=state[6],h=state[7];
        for (unsigned i = 0; i < 64; ++i) {
            const auto s1=rotate(e,6)^rotate(e,11)^rotate(e,25);
            const auto first=h+s1+((e&f)^(~e&g))+constants[i]+words[i];
            const auto s0=rotate(a,2)^rotate(a,13)^rotate(a,22);
            const auto second=s0+((a&b)^(a&c)^(b&c));
            h=g;g=f;f=e;e=d+first;d=c;c=b;b=a;a=first+second;
        }
        state[0]+=a;state[1]+=b;state[2]+=c;state[3]+=d;state[4]+=e;state[5]+=f;state[6]+=g;state[7]+=h;
    }
    std::array<std::uint32_t, 8> state{{0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19}};
    std::array<unsigned char, 64> block{};
    std::size_t used = 0;
    std::uint64_t totalBytes = 0;
};

// Canonical typed encoding: tags distinguish scalar types; integers/IEEE-754
// bit patterns use big endian; strings/collections are length-prefixed;
// optionals include presence. No JSON, sampling or float rounding is involved.
// Version the schema if a logical field is added to these source structures.
class ReplayCanonicalHash {
public:
    explicit ReplayCanonicalHash(const char* domain) { text(domain); }
    void unsignedValue(std::uint64_t value) { tag('u'); raw64(value); }
    void signedValue(std::int64_t value) { tag('i'); raw64(static_cast<std::uint64_t>(value)); }
    void flag(bool value) { tag(value ? 'T' : 'F'); }
    void real(double value) {
        static_assert(sizeof(double) == 8 && std::numeric_limits<double>::is_iec559, "Audit requires IEEE-754 doubles");
        std::uint64_t bits; std::memcpy(&bits, &value, sizeof(bits)); tag('d'); raw64(bits);
    }
    void text(const std::string& value) { tag('s'); raw64(value.size()); hash.update(value); }
    template<class T, class F> void optional(const std::optional<T>& value, F append) {
        flag(value.has_value()); if (value) append(*value);
    }
    template<class T, class F> void sequence(const T& values, F append) {
        tag('v'); raw64(values.size()); for (const auto& value : values) append(value);
    }
    template<class E> void enumeration(E value) { signedValue(static_cast<std::underlying_type_t<E>>(value)); }
    std::string hex() const { return hash.hex(); }
private:
    void tag(unsigned char value) { hash.update(&value, 1); }
    void raw64(std::uint64_t value) {
        unsigned char bytes[8];
        for (unsigned i = 0; i < 8; ++i) bytes[i] = static_cast<unsigned char>(value >> (56 - i * 8));
        hash.update(bytes, 8);
    }
    ReplaySha256 hash;
};

class ReplayDecisionDigest {
public:
    ReplayDecisionDigest() : retirements("ump.logical-retirement.sha256.v1"), releases("ump.logical-release.sha256.v1") {}
    void selection(const ump::SpatialSelection& value) {
        ++retirementCount;
        selectedCells += value.selectedCells; suppressedCells += value.suppressedCells;
        auto& h = retirements;
        h.unsignedValue(retirementCount);
        candidate(h,value.candidate); assessment(h,value.assessment);
        candidate(h,value.finest); assessment(h,value.finestAssessment);
        h.sequence(value.decisions,[&](const auto& item) {
            h.signedValue(item.cellId); h.flag(item.selected); h.text(item.reason);
            h.sequence(item.triggerCells,[&](auto id){h.signedValue(id);}); h.text(item.transition);
        });
        h.sequence(value.attempts,[&](const auto& item){aggregate(h,item.cell);cellAssessment(h,item.assessment);});
        h.signedValue(value.minDepth); h.unsignedValue(value.selectedCells);h.unsignedValue(value.suppressedCells);
        h.unsignedValue(value.coarsenedCells);h.unsignedValue(value.refinedCells);h.text(value.strategy);
        h.unsignedValue(value.temporalExtensions);h.text(value.completionReason);
        h.sequence(value.temporalDecisions,[&](const auto& item){
            h.enumeration(item.action);h.signedValue(item.startMs);h.signedValue(item.endMs);
            h.signedValue(item.evaluatedAtMs);h.enumeration(item.status);
        });
        h.text(value.publicationState);h.text(value.releaseId);
        h.optional(value.coordinationCell,[&](const auto& cell){geometry(h,cell);});
        h.optional(value.semanticPriority,[&](const auto& item){
            h.real(item.lossCeiling);optionalReal(h,item.actualMaxLoss);h.unsignedValue(item.attemptedCeilings);
            h.flag(item.terminalFallback);h.text(item.secondaryStrategy);h.text(item.releaseTrigger);h.flag(item.policySatisfiedRelease);
        });
    }
    void release(const ump::ReleaseSnapshot& value) {
        ++releaseCount;auto& h=releases;h.unsignedValue(releaseCount);
        h.text(value.releaseId);h.text(value.runId);h.text(value.sensorId);h.text(value.applicationId);
        h.text(value.model);h.text(value.policyId);h.text(value.policyVersion);
        h.signedValue(value.startMs);h.signedValue(value.endMs);h.signedValue(value.sealedAtMs);
        h.sequence(value.cells,[&](const auto& cell){aggregate(h,cell.aggregate);h.text(cell.effectivePolicyId);
            h.optional(cell.semantic,[&](const auto& item){semantic(h,item);});});
        h.optional(value.coordinationCell,[&](const auto& cell){geometry(h,cell);});
    }
    std::string retirementSha256() const {return retirements.hex();}
    std::string releaseSha256() const {return releases.hex();}
    std::uint64_t retirementCount=0,releaseCount=0,selectedCells=0,suppressedCells=0;
private:
    static void optionalReal(ReplayCanonicalHash& h,const std::optional<double>& v){h.optional(v,[&](auto x){h.real(x);});}
    static void geometry(ReplayCanonicalHash& h,const ump::CellGeometry& v){
        h.signedValue(v.id);h.signedValue(v.depth);h.real(v.x);h.real(v.y);h.real(v.width);h.real(v.height);
    }
    static void counts(ReplayCanonicalHash& h,const ump::AggregateCounts& v){
        h.unsignedValue(v.observationContributions);h.unsignedValue(v.distinctContributors);
        h.sequence(v.typeObservationContributions,[&](const auto& p){h.text(p.first);h.unsignedValue(p.second);});
        optionalReal(h,v.meanSampleOccupancy);
        h.optional(v.semanticEvidence,[&](const auto& e){h.text(e.taxonomyId);h.text(e.taxonomyVersion);
            h.sequence(e.nodes,[&](const auto& p){h.text(p.first);h.unsignedValue(p.second.observationContributions);h.unsignedValue(p.second.distinctContributors);});});
    }
    static void aggregate(ReplayCanonicalHash& h,const ump::AggregatedCell& v){geometry(h,v.cell);counts(h,v.counts);}
    static void candidate(ReplayCanonicalHash& h,const ump::AggregationCandidate& v){
        h.text(v.runId);h.text(v.sensorId);h.text(v.applicationId);
        h.real(v.grid.x);h.real(v.grid.y);h.real(v.grid.width);h.real(v.grid.height);h.signedValue(v.grid.leafDepth);
        h.signedValue(v.startMs);h.signedValue(v.endMs);h.signedValue(v.closedAtMs);h.flag(v.truncated);
        h.unsignedValue(v.expectedSamples);h.unsignedValue(v.measuredSamples);h.unsignedValue(v.unavailableSamples);h.unsignedValue(v.missingSamples);
        h.enumeration(v.coverage);counts(h,v.counts);h.sequence(v.cells,[&](const auto& c){aggregate(h,c);});
    }
    static void semantic(ReplayCanonicalHash& h,const ump::SemanticRepresentation& v){
        h.text(v.taxonomyId);h.text(v.taxonomyVersion);
        h.sequence(v.bins,[&](const auto& b){h.text(b.categoryId);h.unsignedValue(b.observationContributions);h.unsignedValue(b.distinctContributors);});
        h.real(v.minimumDistinctContributors);h.real(v.maxLoss);h.real(v.meanLoss);
    }
    static void requirement(ReplayCanonicalHash& h,const ump::MetricRequirement& v){
        h.enumeration(v.id);optionalReal(h,v.min);optionalReal(h,v.max);
    }
    static void cellAssessment(ReplayCanonicalHash& h,const ump::CellMetricAssessment& v){
        h.signedValue(v.cellId);h.enumeration(v.status);
        h.sequence(v.metrics,[&](const auto& m){h.enumeration(m.id);optionalReal(h,m.value);h.text(m.unavailableReason);});
        h.sequence(v.checks,[&](const auto& c){requirement(h,c.requirement);optionalReal(h,c.observed);h.enumeration(c.status);h.text(c.reason);});
        h.optional(v.effectivePolicyId,[&](const auto& id){h.text(id);});
        h.sequence(v.policySources,[&](const auto& id){h.text(id);});h.flag(v.policyFeasible);
        h.optional(v.semantic,[&](const auto& s){semantic(h,s);});
        h.optional(v.retainedCounts,[&](const auto& c){counts(h,c);});
        h.optional(v.semanticSuppression,[&](const auto& s){
            h.unsignedValue(s.inputObservations);h.unsignedValue(s.inputDistinct);
            h.unsignedValue(s.retainedObservations);h.unsignedValue(s.retainedDistinct);
            h.unsignedValue(s.suppressedObservations);h.unsignedValue(s.suppressedDistinct);
            h.sequence(s.suppressedTypeObservations,[&](const auto& p){h.text(p.first);h.unsignedValue(p.second);});
            h.sequence(s.suppressedLeaves,[&](const auto& leaf){h.text(leaf);});
            h.real(s.fraction);h.real(s.fullInputSemanticLoss);h.real(s.unsuppressedSemanticLoss);h.unsignedValue(s.evaluatedCandidates);
            // evaluationNanoseconds is the sole timing field, never a decision.
        });
    }
    static void assessment(ReplayCanonicalHash& h,const ump::WindowMetricAssessment& v){
        h.signedValue(v.evaluatedAtMs);h.optional(v.policyId,[&](const auto& id){h.text(id);});
        h.optional(v.policyVersion,[&](const auto& id){h.text(id);});h.enumeration(v.coverageStatus);
        h.text(v.coverageReason);h.enumeration(v.status);
        h.sequence(v.cells,[&](const auto& c){cellAssessment(h,c);});h.text(v.policyMode);
    }
    ReplayCanonicalHash retirements,releases;
};
} // namespace umpReplay
