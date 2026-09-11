# Connectome Fighter

FightingICEを対戦環境として、**MaleCNS v1.0 の実Drosophila connectome**をpinned Shiu LIFで動かし、実body IDの神経活動を記録しながらクラウド上で継続実験する研究・実装基盤です。

**[Rolling MaleCNS Arena](https://liveunjuno.vercel.app/connectome)** · [Roadmap](ROADMAP.md) · [Status](docs/STATUS.md) · [Spectator仕様](docs/SPECTATOR_PIPELINE.ja.md) · [English](README.md)

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
- canonical runtime: **156,675 neurons / 6,025,920 recurrent synapses**
- MaleCNSで実FightingICEを制御
- GARNET / ZEN / LUD / NEZ の独立神経状態/RNG
- 全6キャラpairの継続baseline
- 実body-ID spike/event log
- FightingICE公式960×640 `ScreenData`を別spectator socketでH.264動画化
- **6 real rounds ≈ 1分**の観戦clip
- `latest / previous-1 / previous-2` の3本rolling queue
- Vercel 30秒poll + 次clip countdown + 自動切替
- 動画再生位置と同期したP1/P2 MaleCNS活動
- `somaNeuromere / superclass / type / body ID`表示
- 公式MaleCNS SWC centerlineの実座標X–Z投影
- 現在decisionで強く発火したbody形態の強調表示

最新実証値は [`docs/STATUS.md`](docs/STATUS.md) にあります。

## 観戦構成

計算はGitHub Actions、観戦UIはVercelへ分離しています。

```text
GitHub Actions（毎時）
  ↓
次のキャラpairを選択
  ↓
MaleCNS + Shiu LIFでFightingICE 6 round
  ↓
FightingICE公式ScreenData
  ↓
約1分H.264
  ↓
body-ID activity timeline
  + 公式SWC morphology
  ↓
3本rolling queue
  ↓
Vercel /connectome が30秒poll
```

新しい動画ができるたびにVercelを再deployする必要はありません。`current_clip_id`が更新されるとviewerが自動でNOWへ戻り、`next_expected_at`から次更新までのカウントダウンを表示します。

過去2clipも手動で選べます。4キャラのW/L/D・勝率とexperiment logも同じ画面で見られます。

## 脳活動可視化

flat MaleCNS annotationには物理`pos_x / pos_y / pos_z`が無かったため、座標を捏造していません。

カテゴリ表示は実body IDを公式annotationへjoinして、

- soma neuromere
- superclass
- type
- body ID

を表示します。

物理形態には別途公式公開されたMaleCNS SWC centerlineを使います。

- coordinate space: MaleCNS EM
- coordinate unit: **8 nm**
- projection: X–Z
- fighterごとに上位6 active bodyを表示
- bodyごと最大180 segmentへ軽量化
- 動画の現在decisionでactiveなbodyを明るく/太く表示

Screen pixels、SWC geometry、可視化annotationはいずれも**policy入力には入りません**。

## 現在の実験phase

**production学習は意図的にOFFです。**

今はP6として、観戦・queue・activity・SWC・ログschemaを固定し、毎時runで壊れないことを確認しています。

過去に実装済みのreward rescore / KC→MBON plasticity / checkpoint resumeは工学的smoke evidenceとして残しますが、production learning lineageには昇格させていません。

行動生成は固定です。

- stochasticity: observation-driven Poisson sensory spikes
- action readout: deterministic spike-count argmax
- epsilon-greedy/random action injection: なし

## 次のGate

1. rolling spectatorを複数scheduled runでregression確認する。
2. queue/activity/SWC data contractをfreezeする。
3. timeout/stalemateを含むproduction reward仕様を決める。
4. 報酬をfreezeしてから、4キャラ別のplasticity/checkpoint lineageを開始する。
5. train/evalを分離したcontinuous learningへ移る。
6. 後段でchampion/archive leagueとcausal interventionを追加する。

## 後解析

保存済みgame stateとMaleCNS body-ID spikeから、後で以下を調べられます。

- action別に使われたbody/type/superclass
- damage/reward event直前のrecruitment
- soma-neuromere別の活動変化
- KC→MBON plasticity変化
- キャラlineage間の回路分化
- 反復して利用される候補経路
- 実SWC morphology上の候補構造

ただしactivity correlationだけでは因果回路とは言えません。因果主張にはablation/interventionが必要です。

## 解釈境界

MaleCNS anatomy、Shiu LIF、ゲームI/O、spectator data、game reward、project-defined plasticityは別レイヤです。FightingICEで強くなったとしても、ハエがin vivoで同じreward signalを使うことを意味しません。

## ライセンス

本リポジトリの新規コードはMIT Licenseです。MaleCNS、FightingICE、Shiu model等の外部成果物にはそれぞれのライセンス/利用条件が適用されます。詳細は [`THIRD_PARTY.md`](THIRD_PARTY.md) を参照してください。
