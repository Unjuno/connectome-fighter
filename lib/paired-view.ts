/** Validate one coherent, recorded paired result before displaying it. */
type Row = Record<string, any>;
const object = (v: unknown): v is Row => !!v && typeof v === 'object' && !Array.isArray(v);
const hash = (v: unknown) => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const integer = (v: unknown, min = 0) => typeof v === 'number' && Number.isSafeInteger(v) && v >= min;
const finite = (v: unknown) => typeof v === 'number' && Number.isFinite(v);

export function isPairedView(value: unknown): value is Row {
  if (!object(value) || value.schema_version !== 1 || value.rollout !== 'paired-neural-rollout-v1'
      || value.ready !== true || value.status !== 'paired-evaluation-ready'
      || !integer(value.cycle_index, 1) || !integer(value.accepted_update_count)
      || value.accepted_update_count > value.cycle_index || !hash(value.protocol_sha256)) return false;
  const source = value.source_run_url;
  if (typeof source !== 'string' || !/^https:\/\/github\.com\/Unjuno\/connectome-fighter\/actions\/runs\/[0-9]+$/.test(source)) return false;
  const runId = source.split('/').pop();
  for (const [key, phase] of [['previous', 'before'], ['latest', 'after']]) {
    const row = value[key];
    if (!object(row) || row.status !== 'COMPLETED' || row.candidate_only !== true || row.auto_promotion !== false
        || row.policy_pixel_access !== false || row.served_by_vercel !== false || row.comparison_phase !== phase
        || row.source_training_run_url !== source || !hash(row.state_sha256) || !integer(row.generation)
        || row.reward_id !== 'outcome-hp-epsilon002-v1' || !object(row.video) || !hash(row.video.sha256)
        || !object(row.result) || !object(row.evaluation)) return false;
    const video = row.video.asset_url;
    if (typeof video !== 'string' || !new RegExp('^https://github\\.com/Unjuno/connectome-fighter/releases/download/paired-cycle-' + runId + '-[0-9]+/' + phase + '\\.mp4$').test(video)) return false;
    const protocol = row.evaluation;
    if (protocol.protocol !== 'paired-rollout-combat-v1' || protocol.round_frame_limit !== 3600
        || protocol.decision_interval_frames !== 60 || protocol.seed_p1 !== 800101 || protocol.seed_p2 !== 20202) return false;
    for (const hp of [row.result.p1_hp, row.result.p2_hp]) if (!finite(hp) || hp < 0 || hp > 400) return false;
    if (!finite(row.result.combat_score) || Math.abs(row.result.combat_score) > 1.020001) return false;
  }
  if (value.previous.video.asset_url.replace('/before.mp4', '/after.mp4') !== value.latest.video.asset_url) return false;
  const t = value.training;
  if (!object(t) || t.cycle_index !== value.cycle_index || t.accepted_update_count !== value.accepted_update_count
      || t.source_run_url !== source || t.auto_promotion !== false || t.served_by_vercel !== false
      || t.state_sha256 !== value.latest.state_sha256 || typeof t.accepted_update !== 'boolean'
      || !['curriculum', 'combat'].includes(t.phase) || t.strength_claim !== false) return false;
  const changed = value.latest.state_sha256 !== value.previous.state_sha256;
  if (changed !== t.accepted_update || value.latest.generation !== value.previous.generation + Number(changed)) return false;
  return true;
}
