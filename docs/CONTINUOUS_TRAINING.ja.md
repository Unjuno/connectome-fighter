# 継続学習リーグと観戦ページ設計

## 目的

Connectome Fighter の主成果物を、単発実験ではなく **FightingICE の4キャラクターそれぞれに独立したハエ由来connectome制御器のlineageを割り当て、checkpointを引き継いでクラウド上で継続学習し、その対戦と神経活動をWebで観戦できる系** にする。

対象キャラクターは FightingICE 7.1 の `GARNET / ZEN / LUD / NEZ`。

## キャラごとの脳

4キャラは同じ検証済みDrosophila connectome topologyとrouting契約を参照するが、以下はキャラごとに独立させる。

- checkpoint lineage / checkpoint ID
- actor readout parameters
- value-head parameters
- optimizer state
- recurrent neural state
- action-sampling RNG seed series
- generation / training-match counters

固定connectome条件では、読み取り専用の巨大な疎行列テンソルを同一プロセス内で共有してよい。これはメモリ節約であり、trainable stateやrecurrent stateを共有することを意味しない。内部connectome edge weightsをplasticにする実験では共有しない。

## 実行モデル

GitHub-hosted Actions の1 jobを永続プロセスとして扱わない。学習を bounded chunk に分割する。

```text
4 character checkpoints
      ↓ restore
2 training fights / chunk
(each character fights once)
      ↓ PPO readout update
4 new checkpoints
      ↓
1 frozen evaluation fight
      ↓
replay + neural telemetry + metrics
      ↓
GitHub Pages deploy
      ↓
next scheduled run restores new checkpoints
```

4キャラのtraining pairingは3 chunkで6組を一巡するround-robin sliceとし、1 chunkの計算量を固定する。

### 学習jobの不変条件

- 同時にcheckpointを書けるtraining jobは1つだけ。
- 対戦中はpolicy versionを固定し、更新は対戦データ収集後に行う。
- incomplete / disconnected roundはlossとして学習しない。
- evaluation matchではweightを更新しない。
- terminal rewardは勝利 `+1`、敗北 `-1`、引き分け `0`。
- checkpointにはmodel/readout、optimizer、RNG、generation、match count、code SHA、connectome hash、routing hash、schema versionを含める。
- Actions cacheをcheckpointの唯一の保存先にしない。cacheはimmutable graph/runtime依存物に使う。
- rolling learned stateは `training-state` GitHub Release assetsへ保存する。

## 初期学習範囲

最初の継続学習では次を固定する。

- connectome topology: fixed
- connectome edge weights: fixed
- sensory routing: fixed
- trainable: character-specific action readout + value head
- algorithm: `PPO-readout-v1`

したがって、現在の成功は「connectome内部の全シナプスが強化学習した」ことを意味しない。まず巨大な生物由来graphを制御経路に残したまま、継続学習・世代継承・観戦を成立させる段階である。

## Pages spectator

Pagesは計算を行わない。Actionsが生成した静的JSONを描画する。

### character cards

各キャラについて以下を表示する。

- generation
- training matches
- Elo（運用上のleague可視化値）
- checkpoint ID

### fight replay

`latest-replay.json` に以下を含める。

- P1/P2 character
- P1/P2 checkpoint ID
- frame
- HP / energy / x / y
- selected action
- result

FightingICE/Javaはブラウザでは起動しない。telemetryから簡易2D replayを再構成する。

### brain activity

各意思決定について以下を表示する。

- whole-brain activation mean / max
- activation > 0.75 の割合
-直前状態からactivationが最も増えた実FlyWire node ID (`Δ`)
- 高活性descending/readout neuron ID (`D`)

値はこの工学モデルのdimensionless stateであり、実測発火率ではない。annotationに存在しない解剖領域名を推測して表示しない。

## CIから常時学習へ

GitHub-hosted runnerではjob時間に上限があるため、短いjobをcheckpointで連結する。scheduleは毎時1回、single-writer concurrency lockを使う。真の24/7計算が必要になった時だけtrainerをself-hosted cloud runnerへ移し、Actionsをscheduler/orchestrator、Pagesを観戦UIとして残す。

## 研究上の分離

「4キャラのpersistent agentが継続学習する」と「Drosophila由来topologyがmatched rewiringより優れている」は別命題。

- 継続学習系: persistent agentの工学的成立
- A/B研究: biological topology と matched rewiring の差

前者が成功しても後者の証拠にはしない。
