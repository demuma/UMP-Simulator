#!/usr/bin/env python3
"""Add diagnostic and publication subscopes to the maintained live timing overlay."""
import argparse, hashlib, json, subprocess
from pathlib import Path
from build_diagnostic_profile import instrument_diagnostics, replace_one


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();root=a.repo.resolve();out=a.output.resolve()
    subprocess.run(['python3',str(root/'tools/profiling/live/stage_instrumentation.py'),'--repo',str(root),'--output',str(out)],check=True)
    timing=out/'LiveTiming.hpp';source=timing.read_text()
    source=source.replace('#include <vector>','#include <vector>\n#include <utility>')
    source=replace_one(source,'inline void flush() {','template<class Function> decltype(auto) call(const char* stage, Function&& function) { Scope scope(stage); return std::forward<Function>(function)(); }\ninline void flush() {','LiveTiming.hpp')
    timing.write_text(source)
    diag=root/'simulator/src/AggregationDiagnostics.cpp'
    (out/'simulator/src/AggregationDiagnostics.cpp').write_text(instrument_diagnostics(diag.read_text()))
    simulation=out/'simulator/src/Simulation.cpp'; source=simulation.read_text()
    source=replace_one(source,
        '(const ump::SpatialSelection& selected) {\n                        auto recorded = std::make_shared<ump::SpatialSelection>(selected);',
        '(const ump::SpatialSelection& selected) {\n                        ump_live_timing::Scope profileTerminal("terminal_total");\n                        const auto profileCopy = ump_live_timing::Clock::now();\n                        auto recorded = std::make_shared<ump::SpatialSelection>(selected);\n                        ump_live_timing::event("selection_copy", profileCopy, selected.candidate.cells.size(), selected.finest.cells.size(), selected.attempts.size());',
        'Simulation.cpp')
    evaluation='evaluator.evaluate(candidate, candidate.closedAtMs)'
    if source.count(evaluation)!=2: raise ValueError('Expected two diagnostic-only candidate evaluations')
    source=source.replace(evaluation,'ump_live_timing::call("diagnostic_candidate_evaluation", [&] { return evaluator.evaluate(candidate, candidate.closedAtMs); })')
    for owner in ['local','adaptive']:
        snapshot='std::make_shared<const ump::AggregationProgress>('+owner+'->progressSnapshot())'
        source=replace_one(source,snapshot,'ump_live_timing::call("renderer_progress_snapshot", [&] { return '+snapshot+'; })','Simulation.cpp')
    simulation.write_text(source)
    renderer=out/'simulator/src/Renderer.cpp';source=renderer.read_text()
    source=replace_one(source,'void Renderer::drawAggregationOverlay(const ump::SpatialSelection& snapshot) {',
        'void Renderer::drawAggregationOverlay(const ump::SpatialSelection& snapshot) {\n    ump_live_timing::event("renderer_aggregation_overlay", ump_live_timing::Clock::now(), snapshot.candidate.cells.size(), snapshot.selectedCells, snapshot.suppressedCells);','Renderer.cpp')
    source=replace_one(source,'    if (checks.empty()) return;\n    sf::VertexArray dashes',
        '    if (checks.empty()) return;\n    ump_live_timing::event("renderer_progress_overlay", ump_live_timing::Clock::now(), checks.size(), progress.cells.size());\n    sf::VertexArray dashes','Renderer.cpp')
    renderer.write_text(source)
    sensor=out/'simulator/src/AdaptiveGridBasedSensor.cpp';source=sensor.read_text()
    source=replace_one(source,'        pendingSample = AdaptiveGridSensorSample{adaptiveGridData, aggregationDebug, aggregationProgress};',
        '        ump_live_timing::event("sensor_debug_snapshot", ump_live_timing::Clock::now(), aggregationDebug ? 1 : 0, aggregationProgress ? 1 : 0, aggregationDebug ? aggregationDebug->candidate.cells.size() : 0);\n        pendingSample = AdaptiveGridSensorSample{adaptiveGridData, aggregationDebug, aggregationProgress};','AdaptiveGridBasedSensor.cpp')
    sensor.write_text(source)
    pub=out/'simulator/src/PublicationStore.cpp';source=pub.read_text()
    for old,new in [
        ('Document releaseDocument(const ReleaseSnapshot& release, std::size_t maxBytes) {','Document releaseDocument(const ReleaseSnapshot& release, std::size_t maxBytes) {\n    ump_live_timing::Scope profileBson("publication_release_bson");'),
        ('    std::size_t maxBytes) {\n    auto result = make_document(kvp("_id", release.releaseId), kvp("schema", "ump.publication-journal.v1"),','    std::size_t maxBytes) {\n    ump_live_timing::Scope profileJournalBson("publication_journal_bson");\n    auto result = make_document(kvp("_id", release.releaseId), kvp("schema", "ump.publication-journal.v1"),'),
        ('journal.find_one(filter.view())','ump_live_timing::call("publication_journal_find", [&] { return journal.find_one(filter.view()); })'),
        ('journal.insert_one(prepared.view())','ump_live_timing::call("publication_journal_insert", [&] { return journal.insert_one(prepared.view()); })'),
        ('recipient.find_one(make_document(kvp("_id", release.releaseId)))','ump_live_timing::call("publication_recipient_find", [&] { return recipient.find_one(make_document(kvp("_id", release.releaseId))); })'),
        ('impl->recipient.insert_one(payload.view())','ump_live_timing::call("publication_recipient_insert", [&] { return impl->recipient.insert_one(payload.view()); })'),
        ('impl->journal.find_one(filter.view())','ump_live_timing::call("publication_journal_find", [&] { return impl->journal.find_one(filter.view()); })'),
        ('''auto result = impl->journal.update_one(expected.view(),
            make_document(kvp("$set", make_document(kvp("state", "committed")))));''',
         '''auto result = ump_live_timing::call("publication_journal_update", [&] { return impl->journal.update_one(expected.view(),
            make_document(kvp("$set", make_document(kvp("state", "committed"))))); });''')
    ]:
        # The journal find is used in separate public/Impl methods; don't match
        # an unqualified call inside an already-qualified impl-> expression.
        if old=='journal.find_one(filter.view())':
            source=source.replace('if (auto existing = '+old+')','if (auto existing = '+new+')')
        else:
            count=source.count(old)
            if not count:raise ValueError(f'Missing PublicationStore anchor: {old}')
            source=source.replace(old,new)
    direct_insert='impl->journal.insert_one(committed.view())'
    if direct_insert in source:
        source=replace_one(source,direct_insert,
            'ump_live_timing::call("publication_journal_insert", [&] { return '+direct_insert+'; })',
            'PublicationStore.cpp')
    pub.write_text(source)
    manifest=json.loads((out/'source-hashes.json').read_text())
    manifest['simulator/src/AggregationDiagnostics.cpp']=hashlib.sha256(diag.read_bytes()).hexdigest()
    (out/'source-hashes.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(out)

if __name__=='__main__':main()
