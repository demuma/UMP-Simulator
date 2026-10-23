/* Read-only mongosh audit. Caller supplies `const cfg = <full config JSON>;`.
 * No GT movement or identity map is printed/exported; only compact metrics/hashes.
 * Run only after one full, fresh owned mapped-scene simulation has completed.
 */
(() => {
  const crypto = require('crypto');
  const insist = (ok, text) => { if (!ok) throw new Error('Mapped audit: ' + text); };
  const numeric = value => {
    const n = Number(value && typeof value === 'object' && value._bsontype ? value.toString() : value);
    insist(Number.isFinite(n), 'nonfinite numeric value');
    return n;
  };
  const close = (a, b, tolerance = 1e-6) => Math.abs(numeric(a) - numeric(b)) <= tolerance;
  const plain = value => {
    if (value instanceof Date) return value.toISOString();
    if (value && typeof value === 'object' && ['Long', 'Int32', 'Double', 'Decimal128'].includes(value._bsontype)) return numeric(value);
    if (Array.isArray(value)) return value.map(plain);
    if (value && typeof value === 'object') {
      const result = {};
      for (const key of Object.keys(value).sort()) {
        if (key === '_id' || key === 'run_id') continue;
        result[key] = plain(value[key]);
      }
      return result;
    }
    return value;
  };
  const canonical = value => JSON.stringify(plain(value));
  const digestRows = rows => crypto.createHash('sha256').update(JSON.stringify(rows.map(canonical).sort())).digest('hex');
  const base = cfg.database.db_name;
  insist(/^UMP_Mapped_[0-9a-f]{32}$/.test(base), 'requires fresh owned UMP_Mapped UUID namespace');
  insist(cfg.simulation.scenario === 'mapped_visits', 'wrong scenario');
  const duration = Math.round(cfg.simulation.duration_seconds * 1000);
  const step = Math.round(cfg.simulation.time_step * 1000);
  const sensors = cfg.sensors.filter(sensor => sensor.type === 'adaptive-grid-based');
  insist(sensors.length === 1, 'bounded audit expects exactly one AGBS sensor');
  const sensor = sensors[0], aggregation = sensor.aggregation;
  const period = Math.round(1000 / sensor.frame_rate);
  insist(step === 50 && period === 100 && duration % step === 0, 'unsupported source/sample cadence');
  insist(cfg.simulation.width === 80 && cfg.simulation.height === 80 && sensor.grid.max_depth === 6, 'audit requires 80m D6');
  insist(sensor.database.db_name === base && aggregation.publication.database === base + '_Releases'
    && aggregation.publication.journal_database === base + '_Private', 'configured namespaces do not belong to base');
  const rawDatabase = db.getSiblingDB(base);
  const agentsCollection = rawDatabase.getCollection(cfg.database.collection_name || 'Agents');
  const gt = agentsCollection.find({data_type: 'agent data'}).toArray();
  const events = agentsCollection.find({data_type: 'mapped lifecycle event'}).toArray();
  const summaries = agentsCollection.find({data_type: 'mapped source summary'}).toArray();
  const raw = rawDatabase.getCollection(sensor.database.collection_name).find({data_type: 'adaptive grid data'}).toArray();
  const releases = db.getSiblingDB(aggregation.publication.database).getCollection(aggregation.publication.collection).find({}).toArray();
  const journals = db.getSiblingDB(aggregation.publication.journal_database).getCollection(aggregation.publication.journal_collection).find({}).toArray();
  insist(gt.length > 0 && raw.length > 0 && releases.length > 0, 'source/raw/recipient collections must be nonempty');
  insist(summaries.length === 1, 'exactly one final private source summary required');
  const summary = summaries[0];
  insist(numeric(summary.completed_steps) === duration / step && numeric(summary.source_elapsed_ms) === duration
    && numeric(summary.planned_duration_ms) === duration, 'simulation did not complete its full configured horizon');

  const routes = new Map(cfg.mapped_scene.routes.map(route => [route.id, route]));
  const routeLength = points => points.slice(1).reduce((total, p, i) => total + Math.hypot(p[0] - points[i][0], p[1] - points[i][1]), 0);
  const episodes = new Map(), people = new Map();
  let visits = 0, minimumGap = Infinity;
  for (const person of cfg.mapped_scene.people) {
    insist(!people.has(person.person_id), 'duplicate private person in configuration');
    people.set(person.person_id, person);
    const sorted = [...person.episodes].sort((a, b) => a.start_ms - b.start_ms);
    let previousEnd = null;
    if (sorted.length > 1) visits++;
    for (const episode of sorted) {
      insist(!episodes.has(episode.track_id) && !episode.track_id.includes(person.person_id), 'duplicate or person-derived track token');
      const route = routes.get(episode.route_id);
      insist(route, 'unknown route');
      const end = episode.start_ms + Math.ceil(routeLength(route.points) / person.speed_mps * 1000);
      if (previousEnd !== null) minimumGap = Math.min(minimumGap, episode.start_ms - previousEnd);
      previousEnd = end;
      episodes.set(episode.track_id, {...episode, end_ms: end, person, route});
    }
  }
  insist(minimumGap > aggregation.history.retention_ms, 'fixture permits two tracks of one person in retained history');
  insist(numeric(summary.scheduled_people) === people.size && numeric(summary.scheduled_tracks) === episodes.size,
    'private summary differs from configured population');
  insist([...episodes.values()].every(episode => episode.end_ms <= duration), 'full audit requires every scheduled departure before end');
  const firstEpisode = [...episodes.values()].sort((a, b) => a.start_ms - b.start_ms)[0];
  const firstEvent = events.find(event => event.observation_track_id === firstEpisode.track_id && event.event === 'visible_start');
  insist(firstEvent && firstEvent.timestamp instanceof Date, 'missing earliest start event');
  const origin = firstEvent.timestamp.valueOf() - firstEpisode.start_ms;
  const at = row => {
    insist(row.timestamp instanceof Date, 'expected BSON Date timestamp');
    return row.timestamp.valueOf() - origin;
  };
  const eventKeys = new Set();
  for (const event of events) {
    const episode = episodes.get(event.observation_track_id);
    insist(episode && event.private_person_id === episode.person.person_id && event.route_id === episode.route_id, 'lifecycle identity or route mismatch');
    insist(event.event === 'visible_start' || event.event === 'visible_end', 'unknown lifecycle event');
    const expected = event.event === 'visible_start' ? episode.start_ms : episode.end_ms;
    const portal = event.event === 'visible_start' ? episode.route.start_portal : episode.route.end_portal;
    insist(at(event) === expected && event.portal_id === portal, 'lifecycle timestamp or portal mismatch');
    insist(numeric(event.processed_at_ms) === Math.ceil(expected / step) * step, 'lifecycle processing clock mismatch');
    const key = event.observation_track_id + ':' + event.event;
    insist(!eventKeys.has(key), 'duplicated lifecycle event'); eventKeys.add(key);
  }
  insist(events.length === episodes.size * 2, 'missing scheduled lifecycle start/end events');

  const positionAt = (episode, time) => {
    let remaining = (time - episode.start_ms) / 1000 * episode.person.speed_mps;
    const points = episode.route.points;
    for (let i = 1; i < points.length; i++) {
      const a = points[i - 1], b = points[i], length = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (remaining < length || i === points.length - 1) return {
        x: a[0] + (b[0] - a[0]) * Math.min(remaining / length, 1),
        y: a[1] + (b[1] - a[1]) * Math.min(remaining / length, 1)};
      remaining -= length;
    }
    throw new Error('No route segment');
  };
  const leafId = (x, y) => {
    const gx = Math.floor(x / 1.25), gy = Math.floor(y / 1.25);
    let id = 3;
    for (let bit = 5; bit >= 0; bit--) id = (id << 2) | ((gx >> bit) & 1) | (((gy >> bit) & 1) << 1);
    return id;
  };
  const frames = new Map(), observedPeople = new Set(), observedTracks = new Set(), populationByType = new Map();
  for (const person of people.values()) populationByType.set(person.type, (populationByType.get(person.type) || 0) + 1);
  let sourcePositionMaxError = 0;
  for (const row of gt) {
    const time = at(row), episode = episodes.get(row.agent_id);
    insist(episode && row.observation_track_id === row.agent_id && row.private_person_id === episode.person.person_id,
      'GT person-track boundary mismatch');
    insist(row.type === episode.person.type && time >= episode.start_ms && time < episode.end_ms
      && time >= 0 && time < duration && time % step === 0, 'GT observation during hidden/outside episode');
    const expected = positionAt(episode, time);
    const error = Math.hypot(numeric(row.position.x) - expected.x, numeric(row.position.y) - expected.y);
    sourcePositionMaxError = Math.max(sourcePositionMaxError, error);
    insist(error <= 2e-5, 'GT does not follow declared deterministic arc-length route');
    const frame = frames.get(time) || new Map();
    insist(!frame.has(row.agent_id), 'duplicate GT observation track at a source frame');
    frame.set(row.agent_id, row); frames.set(time, frame);
    observedPeople.add(row.private_person_id); observedTracks.add(row.agent_id);
  }
  insist(observedPeople.size === people.size && observedTracks.size === episodes.size, 'not every scheduled person and track was observed');
  let maximumVisible = 0;
  for (let time = 0; time < duration; time += step) {
    const frame = frames.get(time) || new Map();
    const expected = [...episodes.values()].filter(episode => episode.start_ms <= time && time < episode.end_ms);
    insist(frame.size === expected.length && expected.every(episode => frame.has(episode.track_id)), 'missing/extra visible GT episode');
    maximumVisible = Math.max(maximumVisible, frame.size);
  }

  const privateNames = new Set(people.keys()), trackNames = new Set(episodes.keys());
  const noIdentity = value => {
    if (typeof value === 'string') insist(!privateNames.has(value) && !trackNames.has(value), 'identity value leaked outside GT');
    if (!value || typeof value !== 'object' || value instanceof Date) return;
    if (Array.isArray(value)) { for (const item of value) noIdentity(item); return; }
    for (const [key, item] of Object.entries(value)) {
      insist(!['private_person_id', 'person_id', 'observation_track_id', 'agent_id', 'contributor_id', 'contributorId', 'identityLeaves', 'semantic_evidence', 'type_observation_contributions'].includes(key),
        'private field leaked outside GT: ' + key);
      noIdentity(item);
    }
  };
  const area = sensor.detection_area;
  const inside = row => row.position.x >= area.x && row.position.x < area.x + area.width
    && row.position.y >= area.y && row.position.y < area.y + area.height;
  const observations = new Map(), expectedRaw = new Map();
  let measuredContributions = 0;
  for (let time = period; time < duration; time += period) {
    const values = [...(frames.get(time) || new Map()).values()].filter(inside);
    observations.set(time, values); measuredContributions += values.length;
    for (const row of values) {
      const id = leafId(row.position.x, row.position.y), key = time + ':' + id;
      const expected = expectedRaw.get(key) || {count: 0, types: {}};
      expected.count++; expected.types[row.type] = (expected.types[row.type] || 0) + 1;
      expectedRaw.set(key, expected);
    }
  }
  const rawKeys = new Set();
  for (const row of raw) {
    noIdentity(row);
    const time = at(row), id = numeric(row.cell_id), key = time + ':' + id;
    const expected = expectedRaw.get(key);
    insist(time >= period && time < duration && time % period === 0 && expected && !rawKeys.has(key), 'raw sensor cadence, cell or duplicate mismatch');
    rawKeys.add(key);
    const types = {};
    for (const group of row.agent_type_count) {
      insist(types[group.type] === undefined, 'duplicate raw semantic type'); types[group.type] = numeric(group.count);
    }
    insist(numeric(row.total_agents) === expected.count && canonical(types) === canonical(expected.types), 'raw cell counts differ from measured GT');
    const bits = id - 12288;
    let gx = 0, gy = 0;
    for (let bit = 0; bit < 6; bit++) { gx |= ((bits >> (2 * bit)) & 1) << bit; gy |= ((bits >> (2 * bit + 1)) & 1) << bit; }
    insist(close(row.cell_size, 1.25) && close(row.cell_position.x, gx * 1.25) && close(row.cell_position.y, gy * 1.25), 'raw D6 ID geometry mismatch');
  }
  insist(rawKeys.size === expectedRaw.size, 'missing occupied raw sensor cells');

  const taxonomy = aggregation.semantic_taxonomy;
  const nodes = new Map(taxonomy.nodes.map(node => [node.id, node]));
  const leafByType = new Map();
  for (const node of nodes.values()) for (const label of node.input_types || []) leafByType.set(label, node.id);
  const contains = (ancestor, leaf) => {
    for (let node = nodes.get(leaf); node; node = nodes.get(node.parent)) if (node.id === ancestor) return true;
    return false;
  };
  const types = new Map(cfg.region_taxonomy.map(type => [type.type, type]));
  const regionIds = new Set(aggregation.policy_tree.regions);
  const constraintsFor = cell => {
    const result = {};
    const tighten = requirements => {
      for (const [id, bounds] of Object.entries(requirements || {})) {
        const target = result[id] || {};
        if (bounds.min !== undefined) target.min = Math.max(target.min ?? -Infinity, bounds.min);
        if (bounds.max !== undefined) target.max = Math.min(target.max ?? Infinity, bounds.max);
        result[id] = target;
      }
    };
    tighten(aggregation.policy_tree.root);
    for (const region of cfg.regions) {
      if (!regionIds.has(region.id)) continue;
      const r = region.area;
      if (cell.x < r.x + r.width && r.x < cell.x + cell.width && cell.y < r.y + r.height && r.y < cell.y + cell.height) {
        tighten(types.get(region.type).metric_requirements); tighten(region.metric_requirements);
      }
    }
    return result;
  };
  const ledger = new Map(), semanticCategories = {}, policyCellsByRegion = Object.fromEntries(cfg.regions.map(region => [region.id, 0]));
  let cellsChecked = 0, publishedContributions = 0, trackPersonInflationCells = 0, minimumPublishedSupport = Infinity, maximumPublishedLoss = 0;
  for (const release of releases) {
    noIdentity(release);
    const start = numeric(release.start_ms), end = numeric(release.end_ms), seal = numeric(release.sealed_at_ms);
    insist(start >= 0 && end > start && end <= duration && seal >= end && release.cells.length > 0, 'invalid public interval');
    insist(release.policy_id === aggregation.policy_tree.id && release.policy_version === aggregation.policy_tree.version, 'public policy version mismatch');
    for (const cell of release.cells) {
      const id = numeric(cell.cell_id), depth = numeric(cell.depth), scale = 2 ** (2 * (6 - depth));
      insist(depth >= 1 && depth <= 6 && (id >> (2 * depth)) === 3, 'public cell ID invalid');
      const side = 80 / 2**depth;
      let x = 0, y = 0;
      for (let d = 1; d <= depth; d++) {
        const q = (id >> (2 * (depth - d))) & 3, s = 80 / 2**d;
        x += (q & 1) * s; y += (q >> 1) * s;
      }
      insist(close(cell.x, x) && close(cell.y, y) && close(cell.width, side) && close(cell.height, side), 'public cell ID/geometry mismatch');
      const source = [], tracks = new Set(), persons = new Set();
      let samples = 0;
      for (let time = Math.max(period, Math.ceil(start / period) * period); time < end; time += period) {
        samples++;
        for (const row of observations.get(time) || []) {
          const leaf = leafId(row.position.x, row.position.y);
          if (leaf >= id * scale && leaf < (id + 1) * scale) { source.push(row); tracks.add(row.agent_id); persons.add(row.private_person_id); }
        }
      }
      insist(samples > 0 && numeric(cell.counts.observation_contributions) === source.length
        && numeric(cell.counts.distinct_contributors) === tracks.size
        && close(cell.counts.mean_sample_occupancy, source.length / samples), 'public source count/support/occupancy mismatch');
      if (tracks.size !== persons.size) trackPersonInflationCells++;
      insist(tracks.size === persons.size, 'long-gap fixture has inflated person support');
      const semantic = cell.semantic;
      insist(semantic && semantic.taxonomy_id === taxonomy.id && semantic.taxonomy_version === taxonomy.version, 'missing/wrong public semantic catalog');
      const assigned = new Set(), bins = new Set();
      let sumObs = 0, sumDistinct = 0, minSupport = Infinity, maxLoss = 0, weightedLoss = 0;
      for (const bin of semantic.categories) {
        const category = nodes.get(bin.category_id);
        insist(category && !bins.has(category.id), 'unknown/duplicate public semantic category'); bins.add(category.id);
        const members = source.filter(row => contains(category.id, leafByType.get(row.type)));
        const contributors = new Set(members.map(row => row.agent_id));
        insist(members.length > 0 && numeric(bin.observation_contributions) === members.length
          && numeric(bin.distinct_contributors) === contributors.size, 'public semantic bin differs from private source');
        for (const row of members) {
          const key = row.agent_id + ':' + at(row);
          insist(!assigned.has(key), 'overlapping semantic public categories'); assigned.add(key);
        }
        sumObs += members.length; sumDistinct += contributors.size;
        minSupport = Math.min(minSupport, contributors.size); maxLoss = Math.max(maxLoss, category.loss); weightedLoss += members.length * category.loss;
        semanticCategories[category.id] = (semanticCategories[category.id] || 0) + members.length;
      }
      insist(sumObs === source.length && sumDistinct === tracks.size
        && numeric(semantic.min_category_distinct_contributors) === minSupport
        && close(semantic.semantic_max_loss, maxLoss) && close(semantic.semantic_mean_loss, weightedLoss / source.length), 'public semantic cut/loss does not conserve source');
      const metrics = {observation_contributions: source.length, distinct_contributors: tracks.size,
        mean_sample_occupancy: source.length / samples, cell_side_m: side, cell_area_m2: side * side,
        window_duration_ms: end - start, age_at_evaluation_ms: seal - start,
        post_window_delay_ms: seal - end, measured_sample_fraction: 1,
        min_category_distinct_contributors: minSupport, semantic_max_loss: maxLoss,
        semantic_mean_loss: weightedLoss / source.length};
      const constraints = constraintsFor(cell);
      for (const [metric, bounds] of Object.entries(constraints)) {
        insist(Object.prototype.hasOwnProperty.call(metrics, metric), 'audit lacks metric: ' + metric);
        insist((bounds.min === undefined || metrics[metric] + 1e-9 >= bounds.min)
          && (bounds.max === undefined || metrics[metric] - 1e-9 <= bounds.max), 'public cell violates effective policy: ' + metric);
      }
      for (const region of cfg.regions) {
        const r = region.area;
        if (cell.x < r.x + r.width && r.x < cell.x + cell.width && cell.y < r.y + r.height && r.y < cell.y + cell.height)
          policyCellsByRegion[region.id] = (policyCellsByRegion[region.id] || 0) + 1;
      }
      for (let leaf = id * scale; leaf < (id + 1) * scale; leaf++) {
        const line = ledger.get(leaf) || []; line.push([start, end]); ledger.set(leaf, line);
      }
      cellsChecked++; publishedContributions += source.length;
      minimumPublishedSupport = Math.min(minimumPublishedSupport, tracks.size);
      maximumPublishedLoss = Math.max(maximumPublishedLoss, maxLoss);
    }
  }
  for (const line of ledger.values()) {
    line.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    for (let i = 1; i < line.length; i++) insist(line[i][0] >= line[i - 1][1], 'recipient cells overlap in space-time');
  }
  insist(journals.every(row => row.state === 'committed'), 'private journal contains an uncommitted record');
  const recipientById = new Map(releases.map(row => [row._id, canonical(row)]));
  const nonemptyJournalIds = new Set();
  let privateEmptyRetirements = 0;
  for (const journal of journals) {
    insist(journal.release && Array.isArray(journal.release.cells), 'private journal lacks a valid release-shaped payload');
    if (journal.release.cells.length > 0) {
      insist(!nonemptyJournalIds.has(journal._id), 'duplicated nonempty private journal release');
      nonemptyJournalIds.add(journal._id);
      insist(recipientById.get(journal._id) === canonical(journal.release), 'nonempty journal payload differs from durable recipient release');
    } else {
      privateEmptyRetirements++;
      insist(!recipientById.has(journal._id), 'private empty retirement checkpoint was disclosed as a recipient release');
    }
  }
  insist(nonemptyJournalIds.size === releases.length
    && releases.every(release => nonemptyJournalIds.has(release._id)), 'recipient and nonempty journal payloads are not a bijection');

  const report = {
    status: 'pass', audit_schema: 'ump.mapped-live-audit.v1', owned_base: base,
    completed_steps: numeric(summary.completed_steps), source_elapsed_ms: duration,
    source_gt_rows: gt.length, lifecycle_events: events.length,
    distinct_private_people_observed: observedPeople.size, distinct_visible_tracks_observed: observedTracks.size,
    scheduled_visitors: visits, population_by_observed_profile: Object.fromEntries([...populationByType].sort()),
    maximum_simultaneous_visible_people: maximumVisible, minimum_hidden_gap_ms: minimumGap,
    private_route_position_max_error_m: sourcePositionMaxError,
    measured_sample_slots: observations.size, measured_source_contributions: measuredContributions,
    raw_sensor_cell_rows: raw.length, raw_gt_counts_match: true,
    recipient_release_documents: releases.length, checked_recipient_cells: cellsChecked,
    published_observation_contributions: publishedContributions,
    retained_observation_fraction: publishedContributions / measuredContributions,
    minimum_published_distinct_track_support: minimumPublishedSupport,
    maximum_published_semantic_loss: maximumPublishedLoss,
    published_category_observation_contributions: semanticCategories,
    published_cells_intersecting_policy_region: policyCellsByRegion,
    source_inflation_cells: trackPersonInflationCells,
    checked_policy_violations: 0, recipient_spacetime_overlaps: 0,
    identity_fields_or_values_in_raw_or_recipient: 0,
    committed_journal_documents: journals.length,
    committed_nonempty_journal_payloads: nonemptyJournalIds.size,
    private_empty_retirement_checkpoints: privateEmptyRetirements,
    nonempty_journal_payloads_match_recipient: true,
    private_empty_retirements_absent_from_recipient: true,
    normalized_raw_sha256: digestRows(raw), normalized_recipient_sha256: digestRows(releases),
    normalization: 'Recursively remove only _id and run_id; BSON numeric values become numbers; dates become ISO strings; keys and whole canonical rows are sorted.',
    scope_limits: [
      'This verifies one controlled long-gap source contract, not general person re-identification or formal k-anonymity.',
      'No body clearance or collision solver is claimed; routes are kinematic.',
      'Empty sample slots leave no raw AGBS rows; cadence there follows configured gate and separate sensor tests.',
      'No empirical privacy improvement or fair-baseline advantage follows from policy/count conformance.',
      'Only compact counts and hashes are emitted; GT trajectories and private identity mapping remain in the owned database.'
    ]
  };
  globalThis.umpMappedAuditReport = report;
  print(JSON.stringify(report));
})();
