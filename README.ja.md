# Connectome Fighter

FightingICEを対戦環境として、**MaleCNS v1.0 の実Drosophila connectome**をpinned Shiu LIFで動かし、実body IDの神経活動を記録しながらクラウド上で継続実験する研究・実装基盤です。

[MaleCNS Arena](https://unjuno.github.io/connectome-fighter/) · [Roadmap](ROADMAP.md) · [Status](docs/STATUS.md) · [English](README.md)

## Canonical control path

```text
FightingICE数値観測
      ↓
version管理されたsensory-body Poisson interface
      ↓
MaleCNS v1.0 実配線
      ↓
pinned Shiu et al. LIF dynamics
      ↓
実output bodyのspike count
      ↓
version管理されたaction groups
      ↓
FightingICE操作
```

Canonical経路では、MLP/RNN/GRU/PPO policy/custom sigmoid networkを「ハエ脳本体」の代用品として使いません。旧FlyWire/custom-network系は工学的legacy evidenceとしてのみ残します。

## 現在PASSしているもの

- MaleCNS v1.0 provenance/import
- pinned Shiu LIF reference/runtime
- 現canonical runtime: 156,675 neurons / 6,025,920 recurrent synapses
- MaleCNSで実FightingICE 1 round以上を制御
- GARNET / ZEN / LUD / NEZ の独立神経状態
- 全6キャラpairを8 roundずつ、**48 round/chunk**で継続baseline
- 6時間ごとのGitHub Actions自動実験
- chunkごとに別の決定論的Poisson seed blockを使用
- 実body-ID spike/event log
- FightingICE公式headless rendererの960×640 `ScreenData`を別spectator socketでH.264動画化
- GitHub Pages自動deploy
- body IDを`superclass / class / type / somaNeuromere / side`へjoinした構造活性表示

最新の統合証拠は [`docs/STATUS.md`](docs/STATUS.md) にあります。

## Pagesで見えるもの

[Connectome Fighter Arena](https://unjuno.github.io/connectome-fighter/)

上段の動画はFightingICE本体が描画した実ゲーム画面です。policyにはpixelを渡しておらず、`policy_pixel_access=false`を記録しています。

下段には解析用として、

- HP / position / action telemetry
- action-group spike counts
- top active MaleCNS body IDs
- cell class / type / soma neuromereなどの構造annotation
- experiment history

を表示します。

四角形のcanvasはtelemetry schematicであり、ゲームrendererではありません。

## 現在の実験phase

**学習はまだOFFです。**

報酬設計を先にoffline評価しています。比較中も以下は固定します。

- stochasticity: observation-driven Poisson sensory spikes
- action readout: spike-count argmax
- epsilon-greedy/random action injection: なし
- anatomy / LIF / sensory mapping / action groups: 固定

初回48-round baselineではterminal `+1/0/-1` のdecision-level非ゼロ率が0.2083%しかなく、報酬の大きさより「ほぼ接触しない」ことが主問題でした。

現在はR0/R1/R2aに加え、特定actionを褒めずにno-damage drawだけへ小さい負signalを与えるR2bも同じtrajectoryでoffline比較しています。

詳細: [`docs/REWARD_DESIGN.ja.md`](docs/REWARD_DESIGN.ja.md)

## 次のGate

1. 独立Poisson seed chunkを2つ以上取得する。
2. 同一trajectory上でR0/R1/R2a/R2bのreward density/scale/sign biasを比較する。
3. 最初のreward configをfreezeする。
4. 1キャラ・1matchだけKC→MBON plasticityを有効化し、変更edgeと符号/topology不変を監査する。
5. 別Actions runでcheckpoint resumeを実証する。
6. その後だけcontinuous canonical learningを有効化する。

## 後解析

各decision/windowでgame stateとMaleCNS body-ID spikeを保存するため、後から以下を調べられます。

- action別に使われたbody/type/superclass
- reward/damage event直前のrecruitment
- soma-neuromere別の活動変化
- KC→MBON plasticity変化
- キャラlineage間の回路分化
- 反復して利用される候補経路

ただしactivity correlationだけでは因果回路とは言えません。因果主張にはablation/interventionが必要です。

## 解釈境界

MaleCNS anatomy、Shiu LIF、ゲームI/O、game reward、project-defined plasticityは別レイヤです。FightingICEで強くなったとしても、ハエがin vivoで同じreward signalを使うことを意味しません。

## ライセンス

本リポジトリの新規コードはMIT Licenseです。MaleCNS、FightingICE、Shiu model等の外部成果物にはそれぞれのライセンス/利用条件が適用されます。詳細は [`THIRD_PARTY.md`](THIRD_PARTY.md) を参照してください。
