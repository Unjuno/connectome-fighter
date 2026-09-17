import { metric, stamp } from './observatory';
import styles from './research-dashboard.module.css';

type Json = Record<string, any>;

function signed(value: unknown) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  return value > 0 ? `+${value}` : String(value);
}

function percent(value: unknown, maximum: number) {
  if (typeof value !== 'number' || !Number.isFinite(value) || maximum <= 0) return 0;
  return Math.max(0, Math.min(100, value / maximum * 100));
}

export function ResearchDashboard({ research, training, latest }: { research: Json | null; training: Json | null; latest: Json | null }) {
  const control = research?.control_contract;
  const holdout = research?.heldout_readout;
  const search = research?.paired_search;
  const live = research?.live_compute_snapshot;
  const result = latest?.result;
  const actualReadout = training?.readout_mode || latest?.readout_mode;
  const selectedReadout = control?.readout_mode;
  const readoutValue = actualReadout || selectedReadout || '—';
  const readoutMeta = actualReadout
    ? `${training?.readout_contract || latest?.readout_contract || control?.readout_contract || 'versioned neural readout'}`
    : selectedReadout
      ? 'Selected experiment control · scheduled lane has not published this field yet'
      : 'No control record';
  const maxDamage = Math.max(1, Number(holdout?.canonical_damage_dealt_hp_total) || 0, Number(holdout?.ema_damage_dealt_hp_total) || 0);
  const accepted = search?.accepted_update === true;
  const rejected = search?.accepted_update === false;

  return <section id="research" className={styles.shell} aria-labelledby="research-title">
    <div className={styles.header}>
      <div><span className={styles.eyebrow}>03 / ACTIVE RESEARCH STATUS</span><h2 id="research-title">Current control, measured evidence, and the next gate.</h2></div>
      <div className={styles.badges}><span className={`${styles.badge} ${styles.badgeAccent}`}>CANDIDATE ONLY</span><span className={styles.badge}>AUTO PROMOTION OFF</span><span className={styles.badge}>NO STRENGTH CLAIM</span></div>
    </div>

    <div className={styles.summary}>
      <div className={styles.metric}><span className={styles.metricLabel}>CURRENT CANDIDATE</span><strong className={styles.metricValue}>Gen {metric(training?.generation ?? latest?.generation)}</strong><span className={styles.metricMeta}>{training?.reward_id || latest?.reward_id || 'Reward not recorded'} · {metric(training?.matches ?? latest?.matches)} completed matches</span></div>
      <div className={styles.metric}><span className={styles.metricLabel}>LATEST FIXED EVALUATION</span><strong className={styles.metricValue}>{metric(result?.damage_dealt_hp)} dealt / {metric(result?.damage_taken_hp)} taken</strong><span className={styles.metricMeta}>HP {metric(result?.p1_hp)}–{metric(result?.p2_hp)} · {result?.winner || 'result unavailable'}</span></div>
      <div className={styles.metric}><span className={styles.metricLabel}>NEURAL READOUT</span><strong className={styles.metricValue}>{readoutValue}</strong><span className={styles.metricMeta}>{readoutMeta}</span></div>
      <div className={styles.metric}><span className={styles.metricLabel}>LIVE COMPUTE</span><strong className={styles.metricValue}>{live?.status || 'not recorded'}</strong><span className={styles.metricMeta}>{live?.status === 'capacity-blocked' ? `Provider reset ${stamp(live?.blocked_until)}` : 'Operational state is separate from model evidence'}</span></div>
    </div>

    <div className={styles.grid}>
      <article className={styles.card}>
        <div className={styles.cardHead}><div><span className={styles.eyebrow}>READOUT SELECTION / HELD-OUT</span><h3>Temporal residuals unlocked combat.</h3></div><span className={`${styles.status} ${styles.statusAccept}`}>{holdout?.status ? 'CONTROL CANDIDATE' : 'NO DATA'}</span></div>
        <div className={styles.cardBody}>
          <div className={styles.compareRows}>
            <div className={styles.compareRow}><span className={styles.compareName}>canonical</span><div className={styles.track}><div className={styles.fill} style={{width:`${percent(holdout?.canonical_damage_dealt_hp_total,maxDamage)}%`}} /></div><span className={styles.compareValue}>{metric(holdout?.canonical_damage_dealt_hp_total)} HP</span></div>
            <div className={styles.compareRow}><span className={styles.compareName}>EMA residual</span><div className={styles.track}><div className={`${styles.fill} ${styles.fillEma}`} style={{width:`${percent(holdout?.ema_damage_dealt_hp_total,maxDamage)}%`}} /></div><span className={styles.compareValue}>{metric(holdout?.ema_damage_dealt_hp_total)} HP</span></div>
          </div>
          <div className={styles.deltaStrip}>
            <div className={styles.deltaCell}><span>SEED PAIRS IMPROVED</span><strong>{metric(holdout?.improved_pairs)} / {metric(holdout?.seed_pairs)}</strong></div>
            <div className={styles.deltaCell}><span>CANONICAL NET HP</span><strong>{signed(holdout?.canonical_aggregate_net_hp)}</strong></div>
            <div className={styles.deltaCell}><span>EMA NET HP</span><strong>{signed(holdout?.ema_aggregate_net_hp)}</strong></div>
          </div>
          <p className={styles.boundary}>{holdout?.interpretation || 'No held-out readout evidence recorded.'}</p>
        </div>
      </article>

      <article className={styles.card}>
        <div className={styles.cardHead}><div><span className={styles.eyebrow}>WEIGHT SEARCH / STRICT GATE</span><h3>{accepted ? 'Candidate update accepted.' : rejected ? 'Measured signal, update rejected.' : 'Awaiting search decision.'}</h3></div><span className={`${styles.status} ${accepted ? styles.statusAccept : rejected ? styles.statusReject : ''}`}>{accepted ? 'ACCEPTED' : rejected ? 'REJECTED' : 'PENDING'}</span></div>
        <div className={styles.cardBody}>
          <div className={styles.decision}><span>Actual games</span><strong>{metric(search?.completed_games)}</strong></div>
          <div className={styles.decision}><span>Best measured probe</span><strong>{metric(search?.best_measured_probe_score,5)}</strong></div>
          <div className={styles.decision}><span>Parent → proposal curriculum</span><strong>{metric(search?.baseline_curriculum_score,5)} → {metric(search?.proposal_curriculum_score,5)}</strong></div>
          <div className={styles.decision}><span>Combat damage, parent → proposal</span><strong>{metric(search?.combat_before?.damage_dealt_hp)} → {metric(search?.combat_proposal?.damage_dealt_hp)} HP</strong></div>
          <div className={styles.decision}><span>Weights changed</span><strong>{search?.weights_changed === true ? 'YES' : search?.weights_changed === false ? 'NO' : '—'}</strong></div>
          <p className={styles.reason}>{search?.update_reason || 'No search result recorded.'}</p>
          <p className={styles.boundary}>{search?.interpretation || 'Candidate search evidence is separate from approved inference.'}</p>
          {typeof search?.source_run_url === 'string' ? <a className={styles.link} href={search.source_run_url}>Open audited Actions run ↗</a> : null}
        </div>
      </article>
    </div>

    {live?.status === 'capacity-blocked' ? <div className={styles.operations}><div><strong>OPERATIONS / LIVE COMPUTE BLOCKED</strong><p>{live?.provider || 'Provider'} reported {live?.provider_error_code || 'capacity unavailable'}. Recorded evaluations and offline research evidence remain valid and separate.</p></div><time>{stamp(live?.blocked_until)}</time></div> : null}
  </section>;
}
