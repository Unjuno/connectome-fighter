// Validate the single public receipt before displaying a completed experiment.
export const EXPERIMENT = 'paired-neural-training-v1';
export type Metrics = {
  outcome: number; combat_score: number; curriculum_score: number;
  p1_hp: number; p2_hp: number; damage_dealt_hp: number; damage_taken_hp: number;
  minimum_observed_distance_px: number; approach_progress: number;
  decision_count: number; elapsed_frame: number; no_damage_draw: boolean;
};
export type Video = { url: string; sha256: string; bytes: number; recording_seconds: number };
export type TrainingReport = {
  status: 'PASS'; experiment: string; cycle: number; completed_at: string;
  accepted_update: boolean; update_reason: string; completed_games: number;
  actual_pipeline_seconds: number; schedule_minutes: number;
  source_commit: string; source_run_id: string; source_run_url: string;
  report_url: string; state_url: string; release_tag: string;
  state: { cycle: number; accepted_updates: number; total_completed_games: number;
    weights_sha256: string; state_file_sha256: string; weights_changed: boolean };
  baseline_curriculum: Metrics; combat_before: Metrics; combat_after: Metrics;
  videos: Record<'before' | 'after' | 'curriculum', Video>;
  history: { cycle: number; completed_at: string; accepted_update: boolean; update_reason: string;
    accepted_updates: number; damage_dealt_hp: number; combat_score: number }[];
};
type Row = Record<string, any>;
const row = (v: unknown): v is Row => !!v && typeof v === 'object' && !Array.isArray(v);
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const integer = (v: unknown, low = 0): v is number => finite(v) && Number.isInteger(v) && v >= low;
const hash = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const metrics = (m: unknown): m is Metrics => row(m)
  && ['outcome','combat_score','curriculum_score','p1_hp','p2_hp','damage_dealt_hp','damage_taken_hp','minimum_observed_distance_px','approach_progress'].every(k => finite(m[k]))
  && [-1,0,1].includes(m.outcome) && Math.abs(m.combat_score) <= 1.02
  && m.curriculum_score >= 0 && m.curriculum_score <= 1
  && ['p1_hp','p2_hp','damage_dealt_hp','damage_taken_hp'].every(k => m[k] >= 0 && m[k] <= 400)
  && integer(m.decision_count,1) && integer(m.elapsed_frame,1) && m.elapsed_frame <= 3600
  && typeof m.no_damage_draw === 'boolean';

export function parseTrainingReport(value: unknown): TrainingReport | null {
  if (!row(value)) return null;
  const s = value.state;
  if (value.status !== 'PASS' || value.experiment !== EXPERIMENT || value.candidate_only !== true
      || value.auto_promotion !== false || value.strength_claim !== false
      || value.parent_source_unchanged !== true || !integer(value.cycle,1)
      || !row(s) || s.cycle !== value.cycle || s.experiment !== EXPERIMENT
      || s.candidate_only !== true || s.auto_promotion !== false || s.production_compatible !== false
      || typeof value.accepted_update !== 'boolean' || s.weights_changed !== value.accepted_update
      || !integer(s.accepted_updates) || s.accepted_updates > s.cycle
      || !integer(s.total_completed_games,1) || !hash(s.weights_sha256) || !hash(s.state_file_sha256)
      || !integer(value.completed_games,1) || value.schedule_minutes !== 10
      || !finite(value.actual_pipeline_seconds) || value.actual_pipeline_seconds <= 0
      || typeof value.update_reason !== 'string' || value.update_reason.length > 200
      || typeof value.completed_at !== 'string' || !Number.isFinite(Date.parse(value.completed_at))
      || typeof value.source_commit !== 'string' || !/^[a-f0-9]{40}$/.test(value.source_commit)
      || typeof value.source_run_id !== 'string' || !/^\d+$/.test(value.source_run_id)
      || typeof value.source_run_attempt !== 'string' || !/^\d+$/.test(value.source_run_attempt)) return null;
  const tag = `paired-cycle-${value.source_run_id}-${value.source_run_attempt}`;
  const base = `https://github.com/Unjuno/connectome-fighter/releases/download/${tag}/`;
  if (value.release_tag !== tag || value.source_run_url !== `https://github.com/Unjuno/connectome-fighter/actions/runs/${value.source_run_id}`
      || value.report_url !== base+'summary.json' || value.state_url !== base+'search-state.npz'
      || !metrics(value.baseline_curriculum) || !metrics(value.combat_before) || !metrics(value.combat_after)
      || !row(value.videos)) return null;
  for (const name of ['before','after','curriculum']) {
    const v=value.videos[name];
    if (!row(v) || v.url !== base+name+'.mp4' || !hash(v.sha256) || !integer(v.bytes,10001)
        || !finite(v.recording_seconds) || v.recording_seconds <= 0 || v.recording_seconds > 90) return null;
  }
  if (!Array.isArray(value.history) || !value.history.length || value.history.length > 30) return null;
  let prior=0;
  for (const h of value.history) {
    if (!row(h) || !integer(h.cycle,1) || h.cycle <= prior || h.cycle > value.cycle
        || !integer(h.accepted_updates) || h.accepted_updates > h.cycle
        || typeof h.accepted_update !== 'boolean' || typeof h.update_reason !== 'string'
        || typeof h.completed_at !== 'string' || !Number.isFinite(Date.parse(h.completed_at))
        || !finite(h.damage_dealt_hp) || h.damage_dealt_hp < 0 || h.damage_dealt_hp > 400
        || !finite(h.combat_score) || Math.abs(h.combat_score)>1.02) return null;
    prior=h.cycle;
  }
  return prior === value.cycle ? value as TrainingReport : null;
}
