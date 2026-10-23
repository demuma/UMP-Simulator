#!/usr/bin/env python3
"""Build an isolated adapter for same-input production diagnostic cost measurements."""
import argparse
import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_one(text, old, new, context):
    if text.count(old) != 1:
        raise ValueError(f'{context}: expected one exact source anchor, found {text.count(old)}: {old[:100]!r}')
    return text.replace(old, new)


def instrument_diagnostics(source):
    changes = [
        ('    return [file, simulationOrigin](const ump::AggregationCandidate& candidate, const ump::WindowMetricAssessment& assessment, const ump::SpatialSelection* spatial) {',
         '    return [file, simulationOrigin](const ump::AggregationCandidate& candidate, const ump::WindowMetricAssessment& assessment, const ump::SpatialSelection* spatial) {\n        ump_live_timing::Scope profileTotal(spatial ? "spatial_diagnostics_total" : "candidate_diagnostics_total");\n        const auto profileBson = ump_live_timing::Clock::now();\n        const auto profileSelected = ump_live_timing::Clock::now();'),
        ('        const char* coverage = candidate.coverage',
         '        ump_live_timing::event("diagnostics_selected_bson", profileSelected, candidate.cells.size());\n        const char* coverage = candidate.coverage'),
        ('            bsoncxx::builder::basic::array finest, attempts, temporalDecisions;\n            for (std::size_t i = 0; i < spatial->finest.cells.size(); ++i)',
         '            bsoncxx::builder::basic::array finest, attempts, temporalDecisions;\n            const auto profileFinest = ump_live_timing::Clock::now();\n            for (std::size_t i = 0; i < spatial->finest.cells.size(); ++i)'),
        ('                finest.append(cellDocument(spatial->finest.cells[i], spatial->finestAssessment.cells[i]));\n            for (const auto& attempt : spatial->attempts)',
         '                finest.append(cellDocument(spatial->finest.cells[i], spatial->finestAssessment.cells[i]));\n            ump_live_timing::event("diagnostics_source_bson", profileFinest, spatial->finest.cells.size());\n            const auto profileAttempts = ump_live_timing::Clock::now();\n            for (const auto& attempt : spatial->attempts)'),
        ('            for (const auto& decision : spatial->temporalDecisions)',
         '            ump_live_timing::event("diagnostics_attempt_bson", profileAttempts, spatial->attempts.size());\n            for (const auto& decision : spatial->temporalDecisions)'),
        ('''        *file << bsoncxx::to_json(row.view(), bsoncxx::ExtendedJsonMode::k_relaxed) << '\\n';
        file->flush();''',
         '''        ump_live_timing::event("diagnostics_bson_total", profileBson, row.view().length());
        const auto profileJson = ump_live_timing::Clock::now();
        const auto profileText = bsoncxx::to_json(row.view(), bsoncxx::ExtendedJsonMode::k_relaxed);
        ump_live_timing::event("diagnostics_json", profileJson, profileText.size());
        const auto profileWrite = ump_live_timing::Clock::now();
        *file << profileText << '\\n';
        ump_live_timing::event("diagnostics_stream_write", profileWrite, profileText.size()+1);
        const auto profileFlush = ump_live_timing::Clock::now();
        file->flush();
        ump_live_timing::event("diagnostics_flush", profileFlush);''')
    ]
    for old,new in changes:
        source=replace_one(source,old,new,'AggregationDiagnostics.cpp')
    return '#include "LiveTiming.hpp"\n'+source


def instrument_replay(source, production_mode_api=False):
    source='#include "LiveTiming.hpp"\n#include "AggregationDiagnostics.hpp"\n#include <cstdlib>\n'+source
    changes=[
        ('    const auto& config = settings.aggregation;\n    const bool localMode', '''    const auto& config = settings.aggregation;
    const char* profileDirectory = std::getenv("UMP_DIAGNOSTIC_PROFILE_DIR");
    if (!profileDirectory || !*profileDirectory) throw std::invalid_argument("UMP_DIAGNOSTIC_PROFILE_DIR is required");
    const std::string profileMode = std::getenv("UMP_DIAGNOSTIC_PROFILE_MODE") ? std::getenv("UMP_DIAGNOSTIC_PROFILE_MODE") : "full";
    if (profileMode != "full" && profileMode != "off" && profileMode != "disabled") throw std::invalid_argument("Profile mode must be full or off");
    if (options.paceRate || input.periodMs != 100 || input.endMs % 50) throw std::invalid_argument("Diagnostic profile requires unpaced 100-ms input and 50-ms aligned endpoint");
    const bool profileSnapshots = std::getenv("UMP_DIAGNOSTIC_PROFILE_SNAPSHOTS") && std::string(std::getenv("UMP_DIAGNOSTIC_PROFILE_SNAPSHOTS")) == "1";
    const auto profileOrigin = std::chrono::system_clock::time_point{};
    auto profileCandidateSink = makeAggregationDiagnosticsSink(profileDirectory, profileOrigin);
    auto profileSpatialSink = makeSpatialDiagnosticsSink(profileDirectory, profileOrigin);
    std::shared_ptr<SpatialSelection> profileLatestSelection;
    std::shared_ptr<const AggregationProgress> profileLatestProgress;
    const bool localMode'''),
        ('        publication.seal(selection, selection.candidate.closedAtMs);', '''        ump_live_timing::Scope profileTerminal("terminal_total");
        const auto profileCopy = ump_live_timing::Clock::now();
        auto profileRecorded = std::make_shared<SpatialSelection>(selection);
        ump_live_timing::event("selection_copy", profileCopy, selection.candidate.cells.size(), selection.finest.cells.size(), selection.attempts.size());
        const auto profilePublication = ump_live_timing::Clock::now();
        const auto profileRelease = publication.seal(selection, selection.candidate.closedAtMs);
        const auto profileMetadata = ump_live_timing::Clock::now();
        profileRecorded->publicationState = profileRelease->cells.empty() ? "retired_without_release" : "committed";
        profileRecorded->releaseId = profileRelease->releaseId;
        ump_live_timing::event("selection_metadata", profileMetadata);'''),
        ('        accountedContributions += selection.candidate.counts.observationContributions;', '''        ump_live_timing::event("publication_and_release_serialization", profilePublication);
        if (profileMode == "full") profileSpatialSink(*profileRecorded);
        profileLatestSelection = std::move(profileRecorded);
        accountedContributions += selection.candidate.counts.observationContributions;'''),
        ('        if (settings.temporal) return;', '''        if (profileMode == "full") {
            const auto profileEvaluation = ump_live_timing::Clock::now();
            auto profileAssessment = settings.evaluator.evaluate(candidate, candidate.closedAtMs);
            ump_live_timing::event("diagnostic_candidate_evaluation", profileEvaluation, candidate.cells.size());
            profileCandidateSink(candidate, profileAssessment);
        }
        if (settings.temporal) return;'''),
        ('            else local->advance(now, *manager.history());', '''            else local->advance(now, *manager.history());
            if (profileSnapshots) {
                const auto profileSnapshot = ump_live_timing::Clock::now();
                profileLatestProgress = std::make_shared<const AggregationProgress>(local->progressSnapshot());
                ump_live_timing::event("renderer_progress_snapshot", profileSnapshot, profileLatestProgress->cells.size());
            }'''),
        ('            else adaptive->advance(now, *manager.history());', '''            else adaptive->advance(now, *manager.history());
            if (profileSnapshots) {
                const auto profileSnapshot = ump_live_timing::Clock::now();
                profileLatestProgress = std::make_shared<const AggregationProgress>(adaptive->progressSnapshot());
                ump_live_timing::event("renderer_progress_snapshot", profileSnapshot, profileLatestProgress->cells.size());
            }'''),
        ('        currentEventMs = time;\n        if (finishing)', '''        currentEventMs = time;
        ump_live_timing::logicalMs = time;
        ump_live_timing::Scope profileStep(finishing ? "profile_finish" : "profile_step");
        if (!finishing) { ump_live_timing::Scope profileAdvance("profile_advance_before_sample"); manager.advance(time); }
        if (finishing)'''),
        ('        else manager.advance(time);\n    };', '        // A missing sample needs no second advance: the sensor already advanced above.\n    };'),
        ('        // Advance every declared sensor cadence, including missing samples.\n        for (AggregationTime time = input.periodMs; time < input.endMs;) {', '''        // Production sensor ordering: advance at t=0 and every 50 ms, then ingest
        // a measured batch at each 100-ms sampling timestamp. Ingest itself
        // advances a second time after appending the endpoint history sample.
        consume(0, false);
        for (AggregationTime time = 50; time < input.endMs;) {'''),
        ('            if (time > std::numeric_limits<AggregationTime>::max() - input.periodMs) break;\n            time += input.periodMs;\n        }\n        consume(input.endMs, true);', '''            if (time > std::numeric_limits<AggregationTime>::max() - 50) break;
            time += 50;
        }
        consume(input.endMs, true);'''),
        ('    try {\n        const auto options', '    ump_live_timing::Flush profileFlush;\n    try {\n        const auto options')
    ]
    for old,new in changes:
        source=replace_one(source,old,new,'AggregationReplay.cpp')
    if production_mode_api:
        source=replace_one(source,
            '    auto profileCandidateSink = makeAggregationDiagnosticsSink(profileDirectory, profileOrigin);\n    auto profileSpatialSink = makeSpatialDiagnosticsSink(profileDirectory, profileOrigin);',
            '    YAML::Node profileConfiguration(YAML::NodeType::Map);\n    profileConfiguration["diagnostics"]["mode"] = profileMode == "full" ? "full" : "off";\n    profileConfiguration["diagnostics_directory"] = std::string(profileDirectory);\n    const auto profileDiagnosticSettings = readDiagnosticsConfiguration(profileConfiguration);\n    AggregationDiagnosticsSink profileCandidateSink;\n    SpatialDiagnosticsSink profileSpatialSink;\n    if (profileDiagnosticSettings.enabled) {\n        profileCandidateSink = makeAggregationDiagnosticsSink(profileDiagnosticSettings.directory, profileOrigin);\n        profileSpatialSink = makeSpatialDiagnosticsSink(profileDiagnosticSettings.directory, profileOrigin);\n    }',
            'production diagnostics mode API')
        source=source.replace('if (profileMode == "full") profileSpatialSink(*profileRecorded);','if (profileSpatialSink) profileSpatialSink(*profileRecorded);')
        source=source.replace('if (profileMode == "full") {','if (profileCandidateSink) {')
    # Adapted measurements include the diagnostic file sink; the stock replay's
    # runtime scope wording would be inaccurate for this executable.
    source=source.replace('core replay and in-memory result serialization; excludes input validation and file I/O',
        'production50ms-order core, enabled diagnostic file I/O, snapshots and in-memory replay serialization; excludes input validation, final result file I/O, motion, MongoDB and drawing')
    return source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    root=args.repo.resolve(); out=args.output.resolve()
    if out.exists() or root==out or root in out.parents:
        raise ValueError('Require a fresh output directory outside the repository')
    original={str(f.relative_to(root)):digest(f) for directory in ['simulator/src','simulator/include'] for f in sorted((root/directory).glob('*')) if f.is_file()}
    original['simulator/tools/AggregationReplay.cpp']=digest(root/'simulator/tools/AggregationReplay.cpp')
    original['simulator/tools/PacedReplay.hpp']=digest(root/'simulator/tools/PacedReplay.hpp')
    original['simulator/CMakeLists.txt']=digest(root/'simulator/CMakeLists.txt')
    out.mkdir(mode=0o700,parents=True); project=out/'project'; project.mkdir()
    for name in ['src','include']: shutil.copytree(root/'simulator'/name,project/name)
    (project/'tools').mkdir()
    shutil.copyfile(root/'simulator/tools/PacedReplay.hpp',project/'tools/PacedReplay.hpp')
    shutil.copyfile(root/'tools/profiling/live/LiveTiming.hpp',project/'include/LiveTiming.hpp')
    production_mode_api='readDiagnosticsConfiguration' in (root/'simulator/include/AggregationConfiguration.hpp').read_text()
    (project/'tools/DiagnosticReplay.cpp').write_text(instrument_replay((root/'simulator/tools/AggregationReplay.cpp').read_text(),production_mode_api))
    (project/'src/AggregationDiagnostics.cpp').write_text(instrument_diagnostics((root/'simulator/src/AggregationDiagnostics.cpp').read_text()))
    cmake=(root/'simulator/CMakeLists.txt').read_text().split('# Add the source files to the executable')[0]
    cmake+='''\nadd_executable(DiagnosticReplay tools/DiagnosticReplay.cpp
        src/AggregationManager.cpp src/AggregationHistory.cpp src/CandidateMetrics.cpp
        src/PolicyTree.cpp src/SpatialSelection.cpp src/AdaptiveAggregation.cpp src/CellLocalAggregation.cpp
        src/PublicationCoordinator.cpp src/AggregationConfiguration.cpp src/PolicyConfiguration.cpp
        src/AggregationDiagnostics.cpp src/Utilities.cpp)
    find_package(Threads REQUIRED)
    target_compile_features(DiagnosticReplay PRIVATE cxx_std_17)
    target_compile_options(DiagnosticReplay PRIVATE -O3)
    target_link_libraries(DiagnosticReplay PRIVATE ump_semantic SFML::Graphics yaml-cpp::yaml-cpp
        mongo::mongocxx_shared mongo::bsoncxx_shared Threads::Threads)
'''
    (project/'CMakeLists.txt').write_text(cmake)
    manifest={'schema':'ump.diagnostic-profile-build.v1','production_sources_sha256':original,
        'production_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'adapter_tool_sha256':digest(Path(__file__)),
        'prepared_sources_sha256':{str(f.relative_to(project)):digest(f) for f in sorted(project.rglob('*')) if f.is_file()},
        'production_modified':False,'production_diagnostics_mode_api':production_mode_api}
    if not args.prepare_only:
        subprocess.run(['cmake','-S',str(project),'-B',str(out/'build'),'-DCMAKE_BUILD_TYPE=Release','-DCMAKE_OSX_ARCHITECTURES='+platform.machine()],check=True)
        subprocess.run(['cmake','--build',str(out/'build'),'--parallel','4'],check=True)
        manifest['binary_sha256']=digest(out/'build/DiagnosticReplay')
    if any(digest(root/path)!=wanted for path,wanted in original.items()):
        raise RuntimeError('Production source changed during isolated build')
    (out/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'prepared':str(project),'binary':str(out/'build/DiagnosticReplay'),'compiled':not args.prepare_only}))

if __name__=='__main__':main()
