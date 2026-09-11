# Public spectator / research ledger split

## 目的

Connectome Fighter の公開面を2つに分離する。

1. **Vercel public arena** — 対戦と現在の神経活動を見せる。
2. **GitHub Pages / Actions research ledger** — 報酬、plasticity、checkpoint lineage、実験条件、raw evidenceを残す。

Vercel側を研究ログの保存先にしない。研究上の説明可能性と再現性はGitHub側で担保する。

## Vercel public arena

公開URL: `https://liveunjuno.vercel.app/connectome`

保持・表示するもの:

- current clip + previous two clips の短期rolling buffer
- FightingICE ScreenData動画
- P1/P2 character
- 動画再生位置に同期したMaleCNS body-ID spike activity
- released MaleCNS SWC morphologyのX–Z投影
- 次回clipの概算時刻

保持・表示しないもの:

- 長期match ledger
- reward formula
- plasticity rationale
- checkpoint training history
- optimizer / experiment history
- Actions raw logs

この境界により、観戦ページは presentation surface のまま保つ。

## GitHub research ledger

公開URL: `https://unjuno.github.io/connectome-fighter/`

公開するもの:

- canonical substrate / dynamics
- current phase
- reward contract (`R2d-v0`)
- plasticity contract (`KC-MBON-valence-depression-v0`)
- 固定比較条件
- normalized match ledger
- checkpoint smoke release
- GitHub Actions evidence
- interpretation boundaries

GitHub Pages deploy時に `configs/` のcanonical JSONを `site/research-data/` へコピーするため、表示用の手入力値と実際の設定が乖離しないようにする。

## Training → arena inference handoff

研究checkpointをそのままVercelの表示データとして扱わない。

GitHub Actionsの `publish-arena-inference-snapshot` が、承認済みcanonical checkpointから**推論に必要なstateのみ**を抽出して `arena-inference-latest` releaseへ公開する。

handoff manifestには以下だけを含める。

- character
- generation
- state file name
- state SHA-256
- canonical model identifier
- read-only inference contract

reward式、plasticity rationale、match ledger、研究履歴はhandoffに埋め込まない。

現時点ではcanonical checkpoint resume smokeが成立しているGARNET generation 2だけを対象にする。4キャラすべてがproduction lineageへ昇格するまでは、arena snapshotをproduction-trained leagueと呼ばない。

## Scientific boundary

- MaleCNS anatomy: canonical biological structure
- pinned Shiu LIF: canonical dynamics layer
- game observation → sensory input: project-defined experimental interface
- FightingICE reward: project-defined reinforcement signal
- game reward → valence/plasticity mapping: project-defined learning assumption
- SWC/video visualization: post-hoc spectator only

Vercelへ推論stateを渡しても、この境界は変わらない。
