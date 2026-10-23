#!/usr/bin/env python3
"""Create an isolated, source-checked live instrumentation overlay; never edit repo."""
import argparse, hashlib, json, shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
root=a.repo.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
shutil.copyfile(Path(__file__).with_name('LiveTiming.hpp'),out/'LiveTiming.hpp')
manifest={}
def patch(path,edits):
 s=(root/path).read_text();manifest[path]=hashlib.sha256(s.encode()).hexdigest()
 for old,new in edits:
  if s.count(old)!=1: raise ValueError(f'{path}: expected one occurrence: {old[:100]!r} got{s.count(old)}')
  s=s.replace(old,new)
 t=out/path;t.parent.mkdir(parents=True,exist_ok=True);t.write_text('#include "LiveTiming.hpp"\n'+s)
patch('simulator/src/Simulation.cpp',[
 ('void Simulation::run() {','void Simulation::run() {\n    ump_live_timing::Flush timingFlush;'),
 ('        // Restart the clock\n        simulationClock.restart();','        ump_live_timing::logicalMs = simulationTime.asMicroseconds() / 1000;\n        ump_live_timing::Scope timingStep("simulation_step");\n        const auto timingInput = ump_live_timing::Clock::now();\n        ump_live_timing::event("source_state", timingInput, agents.size());\n        // Restart the clock\n        simulationClock.restart();'),
 ('        postData(agents);','        { ump_live_timing::Scope timingGt("ground_truth_write"); postData(agents); }'),
 ('    // The last processed state precedes this exclusive end. Flush even a partial window.','    ump_live_timing::logicalMs = simulationTime.asMicroseconds() / 1000;\n    const auto timingFinish = ump_live_timing::Clock::now();\n    // The last processed state precedes this exclusive end. Flush even a partial window.'),
 ('    // Signalize the simulation has finished so that the renderer can swap buffers if needed','    ump_live_timing::event("aggregation_finish", timingFinish);\n    // Signalize the simulation has finished so that the renderer can swap buffers if needed'),
 ('    // Clear the grid\n    collisionGrid.clear();','    ump_live_timing::Scope timingMotion("motion_collision");\n    // Clear the grid\n    collisionGrid.clear();'),
 ('        sensor->update(agents, timeStep, timestamp);','        { ump_live_timing::Scope timingSensor("sensor_update"); sensor->update(agents, timeStep, timestamp); }'),
 ('        sensor->postData();','        { ump_live_timing::Scope timingRawSensor("raw_sensor_write"); sensor->postData(); }'),
 ('                                        const auto result = store->publish(payload);','                                        const auto timingAck = ump_live_timing::Clock::now();\n                                        const auto result = store->publish(payload);\n                                        ump_live_timing::event("publication_ack", timingAck, result == ump::SinkResult::Acknowledged ? 1 : 0, payload.startMs, payload.endMs, payload.sealedAtMs);'),
])
patch('simulator/src/AdaptiveGridBasedSensor.cpp',[
 ('    if (aggregationManager) aggregationManager->advance(observedAtMs);','    if (aggregationManager) { ump_live_timing::Scope timingAdvance("aggregation_advance"); aggregationManager->advance(observedAtMs); }'),
 ('        if (batch) aggregationManager->ingest(*batch); // Also ingest a measured-empty area.','        if (batch) { ump_live_timing::Scope timingIngest("aggregation_ingest"); aggregationManager->ingest(*batch); } // Also ingest a measured-empty area.'),
 ('        pendingSample = AdaptiveGridSensorSample{adaptiveGridData, aggregationDebug, aggregationProgress};','        if (aggregationManager) { const auto state=aggregationManager->history()->debugState(); ump_live_timing::event("history_state", ump_live_timing::Clock::now(), state.bins, state.observations, state.identityBytes, state.buckets); }\n        pendingSample = AdaptiveGridSensorSample{adaptiveGridData, aggregationDebug, aggregationProgress};'),
])
patch('simulator/src/PublicationStore.cpp',[
 ('void PublicationStore::prepare(const ReleaseSnapshot& release) {','void PublicationStore::prepare(const ReleaseSnapshot& release) {\n    ump_live_timing::Scope timingPrepare("publication_prepare");'),
 ('SinkResult PublicationStore::publish(const ReleaseSnapshot& release) {','SinkResult PublicationStore::publish(const ReleaseSnapshot& release) {\n    ump_live_timing::Scope timingPublish("publication_publish");'),
 ('void PublicationStore::commit(const ReleaseSnapshot& release) {','void PublicationStore::commit(const ReleaseSnapshot& release) {\n    ump_live_timing::Scope timingCommit("publication_commit");'),
])
patch('simulator/src/Renderer.cpp',[
 ('void Renderer::run() {','void Renderer::run() {\n    ump_live_timing::Flush timingFlush;'),
 ('            render();','            const auto timingDraw = ump_live_timing::Clock::now();\n            render();\n            ump_live_timing::event("renderer_draw", timingDraw, received ? 1 : 0, agentBuffer.currentWriteFrameIndex.load() - agentBuffer.currentReadFrameIndex.load(), sensorBuffer.currentWriteFrameIndex.load() - sensorBuffer.currentReadFrameIndex.load());'),
 ('    timestamp = received->first;','    ump_live_timing::logicalMs = static_cast<std::int64_t>(std::llround((agentBuffer.currentReadFrameIndex.load() - 1) * double(timeStep) * 1000));\n    const auto timingReceipt = ump_live_timing::Clock::now();\n    ump_live_timing::event("renderer_receipt", timingReceipt, received->second.size(), agentBuffer.currentWriteFrameIndex.load() - agentBuffer.currentReadFrameIndex.load(), sensorBuffer.currentWriteFrameIndex.load() - sensorBuffer.currentReadFrameIndex.load());\n    timestamp = received->first;'),
])
patch('simulator/include/SharedBuffer.tpp',[
 ('    std::unique_lock<std::mutex> lock(queueMutex);\n    // Capacity covers BOTH queues.','    const auto timingWrite = ump_live_timing::Clock::now();\n    std::unique_lock<std::mutex> lock(queueMutex);\n    const auto timingQueueBefore = currentWriteFrameIndex.load() - currentReadFrameIndex.load();\n    // Capacity covers BOTH queues.'),
 ('    ++currentWriteFrameIndex;\n    queueCond.notify_all();','    ++currentWriteFrameIndex;\n    ump_live_timing::event(name == "Agents" ? "agent_queue_write" : "sensor_queue_write", timingWrite, timingQueueBefore, currentWriteFrameIndex.load() - currentReadFrameIndex.load());\n    queueCond.notify_all();'),
])
patch('simulator/src/CellLocalAggregation.cpp',[
 ('    process(now, history, false);\n    lastNowMs = now;', '    process(now, history, false);\n    ump_live_timing::event("local_state", ump_live_timing::Clock::now(), frontier.size(), handoffs.size(), handoffIntents.size(), pending ? 1 : 0);\n    lastNowMs = now;'),
])
(out/'source-hashes.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(out)
