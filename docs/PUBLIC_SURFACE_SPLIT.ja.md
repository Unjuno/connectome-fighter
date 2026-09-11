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
- checkpoint smoke releases
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

### checkpoint lineage の現在地

- **GARNET generation 2** — `arena-inference-latest` に承認済みのread-only inference state。現行public arenaが利用できる学習済みstateはこれだけ。
- **ZEN / LUD / NEZ generation 2** — `canonical-missing-lineage-smoke-v1` で、各キャラ独立state・RNG・履歴を持つgeneration 1 seedと、別GitHub Actions runからgeneration 2へresumeするcross-run smokeを実証済み。ただし `R2d-v0` / `KC-MBON-valence-depression-v0` は依然として**candidate smoke contract**であり、これら3キャラはproduction arenaへ未昇格。

したがって「4キャラすべてにcross-run resume可能なcandidate lineageが存在する」とは言えるが、「4キャラproduction-trained leagueが成立した」とはまだ言わない。ZEN/LUD/NEZを `arena-inference-latest` へ入れるには、報酬・plasticity実験の採用判断と明示的なpromotion gateが別途必要。

## Runtime snapshot boundary

Vercel側の実行環境は、GitHub Releaseのruntime bundleをviewerごとに再取得せず、SHA-addressed persistent Sandboxへ一度だけstageし、そのfilesystem snapshotから短命viewer Sandboxをforkする。

runtime baseにはimmutable runtimeだけを置き、character stateは `arena-inference-latest` のmanifest/SHAで別途検証する。viewer sessionでは `learning_enabled=false`、`policy_pixel_access=false` を固定する。

このruntime snapshotは計算環境のcold-start最適化であり、学習checkpointの承認状態を変更しない。

## Scientific boundary

- MaleCNS anatomy: canonical biological structure
- pinned Shiu LIF: canonical dynamics layer
- game observation → sensory input: project-defined experimental interface
- FightingICE reward: project-defined reinforcement signal
- game reward → valence/plasticity mapping: project-defined learning assumption
- SWC/video visualization: post-hoc spectator only

Vercelへ推論stateを渡しても、この境界は変わらない。
