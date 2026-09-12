(() => {
  const escapeHtml = (value = '') => String(value).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number = (value, digits = 4) => {
    const n = Number(value);
    return Number.isFinite(n) ? n.toFixed(digits).replace(/0+$/, '').replace(/\.$/, '') : '—';
  };
  const dateLabel = (value) => {
    const d = new Date(value || '');
    return Number.isNaN(d.getTime()) ? String(value || '—') : d.toLocaleString('en-US', { timeZone: 'UTC', dateStyle: 'medium', timeStyle: 'short' });
  };

  function ensurePanel() {
    let panel = document.getElementById('candidate-training-history');
    if (panel) return panel;
    panel = document.createElement('section');
    panel.id = 'candidate-training-history';
    panel.className = 'panel';
    const current = document.getElementById('candidate-learning');
    const lineage = document.getElementById('lineage');
    (current || lineage)?.insertAdjacentElement('afterend', panel);
    return panel;
  }

  function render(history = {}) {
    const panel = ensurePanel();
    const entries = Array.isArray(history.entries) ? [...history.entries].reverse() : [];
    const recent = entries.slice(0, 16);
    if (!recent.length) {
      panel.innerHTML = '<div class="section-title"><div><div class="eyebrow">candidate learning history</div><h2>Rolling GitHub training timeline</h2></div></div><div class="muted">No candidate generations have been published to the public history yet.</div>';
      return;
    }

    const rows = recent.map((entry) => {
      const signals = entry.signal_summary || {};
      const update = entry.update_summary || {};
      const sha = String(entry.state_sha256 || '—');
      const shortSha = sha.length > 24 ? `${sha.slice(0, 12)}…${sha.slice(-8)}` : sha;
      const source = String(entry.source_run_url || '#');
      return `<details>
        <summary><strong>G${Number(entry.generation).toLocaleString()}</strong> · vs ${escapeHtml(entry.opponent || '—')} · signal ${escapeHtml(number(signals.sum, 6))} · ${Number(update.changed_edges || 0).toLocaleString()} changed edges · ${escapeHtml(dateLabel(entry.updated_at))}</summary>
        <div class="muted" style="padding:8px 0 0;line-height:1.7">
          candidate matches: ${Number(entry.matches || 0).toLocaleString()}<br>
          trace status: ${escapeHtml(entry.match_status || '—')}<br>
          nonzero decision signals: ${Number(signals.nonzero || 0).toLocaleString()} (${Number(signals.positive || 0).toLocaleString()} positive / ${Number(signals.negative || 0).toLocaleString()} negative)<br>
          multiplier min / mean / max: ${escapeHtml(number(update.min_multiplier, 7))} / ${escapeHtml(number(update.mean_multiplier, 7))} / ${escapeHtml(number(update.max_multiplier, 7))}<br>
          state SHA: <code title="${escapeHtml(sha)}">${escapeHtml(shortSha)}</code><br>
          status: ${escapeHtml(entry.status || 'candidate-only-not-arena-approved')} · served_by_vercel=${String(entry.served_by_vercel === true)} · auto_promotion=${String(entry.auto_promotion === true)}<br>
          <a href="${escapeHtml(source)}">source Actions run ↗</a>
        </div>
      </details>`;
    }).join('');

    panel.innerHTML = `
      <div class="section-title">
        <div><div class="eyebrow">candidate learning history</div><h2>Rolling GitHub training timeline</h2></div>
        <span class="muted">${Number(history.entry_count || entries.length).toLocaleString()} recorded states</span>
      </div>
      <div class="notice"><strong>Candidate-only ledger.</strong> Each row records a successful GitHub candidate update. It is not arena approval and it is not evidence of improved fighting performance until a separate fixed evaluation establishes that.</div>
      <div style="margin-top:12px">${rows}</div>
      <p class="boundary">${escapeHtml(history.interpretation_boundary || 'This is an append-only public record of research-candidate state transitions. Vercel continues to serve only separately approved inference state.')}</p>
      <div class="actions"><a class="btn" href="./data/training-history.json">training history JSON ↗</a><a class="btn" href="https://github.com/Unjuno/connectome-fighter/actions/workflows/continuous-training.yml">candidate trainer ↗</a></div>`;
  }

  fetch('./data/training-history.json', { cache: 'no-store' })
    .then((response) => response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`)))
    .then(render)
    .catch((error) => {
      const panel = ensurePanel();
      panel.innerHTML = `<div class="section-title"><div><div class="eyebrow">candidate learning history</div><h2>Rolling GitHub training timeline</h2></div></div><div class="muted">history unavailable: ${escapeHtml(error.message)}</div>`;
    });
})();
