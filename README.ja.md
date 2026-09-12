# Connectome Fighter

FightingICE を対戦環境として、**MaleCNS v1.0 の実 Drosophila connectome** を pinned Shiu LIF dynamics で動かし、実 body ID の神経活動・checkpoint lineage・runtime provenance を公開しながらクラウド上で検証する研究・実装基盤です。

**[Public LIVE](https://liveunjuno.vercel.app/connectome)** · [GitHub Pages research ledger](https://unjuno.github.io/connectome-fighter/) · [Status](docs/STATUS.md) · [Roadmap](ROADMAP.md) · [Public surface contract](docs/PUBLIC_SURFACE_SPLIT.md) · [English](README.md)

## Canonical control path

```text
FightingICE 数値観測
      ↓
version 管理された project-defined Poisson sensory interface
      ↓
MaleCNS v1.0 実配線
      ↓
pinned Shiu et al. LIF dynamics
      ↓
実 output body の spike count
      ↓
version 管理された action groups
      ↓
FightingICE 操作
```

Canonical 経路では、MLP / RNN / GRU / PPO policy / custom sigmoid network を「ハエ脳本体」の代用品として使いません。旧 FlyWire / custom-network 系は工学的な legacy evidence としてのみ残します。

## 現在の production 公開構成

Vercel は **1つの shared read-only LIVE broadcast** だけを提供します。viewer ごとに FightingICE/MaleCNS session を増やしません。

```text
GitHub で承認された inference state
        ↓
SHA-addressed persistent runtime snapshot
        ↓
connectome-live-broadcast
        ↓
FightingICE + 2つの MaleCNS/Shiu worker
        ↓
shared live telemetry / neural activity
        ↓
全 viewer が同じ試合を見る
```

Public LIVE の固定境界:

- `mode=single-shared-live-broadcast`
- `audience_scope=shared-global`
- `learning_enabled=false`
- `policy_pixel_access=false`
- public viewer から個別 match を POST 作成できない
- screen pixels / SWC morphology / fly visualization は spectator-only
- recorded clip を LIVE と偽って代替しない

現在の LIVE は **GARNET generation 2 approved inference vs ZEN canonical baseline** です。

## Checkpoint lineage の現在地

- **GARNET generation 2 = APPROVED INFERENCE**
- **ZEN generation 2 = CANDIDATE LINEAGE**
- **LUD generation 2 = CANDIDATE LINEAGE**
- **NEZ generation 2 = CANDIDATE LINEAGE**

ZEN / LUD / NEZ は独立 state / RNG / history と cross-run generation resume を実証していますが、production learned fighter には昇格していません。したがって「4キャラ production-trained league」とは表現しません。

LIVE 画面右下の provenance panel でも、**GARNET G2 approved / ZEN LIVE baseline / ZEN・LUD・NEZ G2 candidate** を分離表示します。

## Runtime

Canonical backend は引き続き **Brian2 Cython** です。Vercel Sandbox に C compiler が無いため、GitHub Actions で production executable path を再現して Cython extension を事前 compile し、compiler を利用不能にした状態でも同じ worker が `ready` になることを gate にしています。

現在の production runtime evidence（2026-09-12）:

- runtime archive SHA-256: `f4016e3a2f79968a3305818ad3b4ef2197802e36c647660c1ab524b098f27205`
- runtime base: `connectome-runtime-f4016e3a2f79968a`
- runtime snapshot: `snap_s5HpePEfgiNNAsLgE9UKsvOVwY5u`
- Python `3.10.21`
- Brian2 `2.5.1`
- Cython `0.29.36`
- NumPy `1.24.0`
- compilerless cache: **30 files / 15 shared objects / 5,776,256 bytes**
- cache tree SHA-256: `772cf23de36484d12e9355334f116bad71b8a8d30e42531cc93b90e3670dcd92`
- host-specific `-march=native`: **excluded**
- **156,675 neurons / 6,025,920 recurrent synapses**
- proof telemetry: **round 1 / frame 181 / GARNET decision 3 / ZEN decision 3 / 9,245 vs 9,098 spikes**
- compilerless release E2E: Actions `34690428080` — **PASS**
- independent production smoke: Actions `34690567057` — **PASS**

Machine-readable proofは [`site/data/runtime-proof.json`](site/data/runtime-proof.json) に固定しています。

この precompile/cache は deployment optimization であり、MaleCNS topology や Shiu dynamics の置換ではありません。

## Public LIVE 可視化

中央 arena のハエ型 avatar は、FightingICE telemetry の実値を表示に使います。

- `x / y` → FightingICE 960×640 stage 上の位置
- `facing` → 左右反転
- `action` → pose
- wingbeat → presentation-only animation

ランダムな平行移動を加えて「ハエが動いているように見せる」処理はしません。ただしこれは実 Drosophila の生体力学的 locomotion model ではなく、MaleCNS/Shiu policy が FightingICE に出した制御結果の可視化です。

## Neural activity / morphology

実 body ID spike を保持し、LIVE では decision-window activity を表示します。Released MaleCNS SWC centerline は X–Z anatomical context として使います。

- coordinate space: MaleCNS EM
- coordinate unit: **8 nm**
- projection: X–Z
- active body を明るく表示

flat annotation に存在しない `pos_x / pos_y / pos_z` は捏造していません。Screen pixels、SWC geometry、annotation は policy 入力には入りません。

## GitHub Pages / Actions の役割

GitHub は研究・学習・provenance の system of record です。

- canonical substrate / dynamics
- baseline match logs
- reward / plasticity contracts
- checkpoint lineage / SHA / resume evidence
- approved inference handoff
- runtime manifest / checksum
- Actions artifacts / logs
- scientific interpretation boundaries

Vercel は inference/presentation surface であり、長期 learning history の保存先ではありません。

## 現在の学習 phase

**continuous production reward-driven learning は OFF です。**

現在の scheduled baseline は重みを更新せず、6時間ごとに全6 pair を評価して public match log を更新します。既存の reward rescore / KC→MBON plasticity / checkpoint resume は research / engineering evidence であり、continuous production learning lineage ではありません。

行動生成は以下で固定されています。

- stochasticity: observation-driven Poisson sensory spikes
- action readout: deterministic spike-count argmax
- epsilon-greedy/random action injection: なし

現在は reward を触る前に **Public Surface Freeze** を完了させています。

## 旧 rolling-video spectator

以前の「GitHub Actions で約1分の ScreenData MP4 を生成し、latest + previous 2 を Vercel で擬似ライブ表示する」経路は、renderer / activity timeline / SWC export の回帰 evidence として残しています。

これは現在の production LIVE ではありません。毎時 schedule は停止し、必要なときだけ手動/実装変更時の regression verification に使います。詳細は [`docs/SPECTATOR_PIPELINE.ja.md`](docs/SPECTATOR_PIPELINE.ja.md) を参照してください。

## 現在の Gate

Public Surface Freeze の最低条件:

1. `/api/connectome/live` が single shared LIVE contract を維持する
2. runtime archive SHA と runtime-base identity が一致する
3. `frame > 0` かつ両 MaleCNS worker の decision が進む
4. `learning_enabled=false` / `policy_pixel_access=false`
5. GARNET approved と ZEN/LUD/NEZ candidate の表記を混同しない
6. README / STATUS / ROADMAP / Pages / Vercel UI が同じ architecture を示す
7. stopped shared Sandbox を supervisor が recycle して復旧できる
8. failure/warming を明示し、偽の LIVE fallback を作らない

shared LIVE のbout切替は public broadcast だけ post-fight/session hold を各1秒へ短縮し、通常one-shot診断の30秒保持は維持しています。実観測では旧 running session → 新 booting を7秒サンプリング以内、新 booting → running をさらに7秒以内で確認しており、旧30秒+30秒のterminal holdは再現していません。これはサンプリング上限であり、厳密なdowntime測定値ではありません。

これを固定してから reward/stalemate semantics の比較へ進みます。

## 後解析

保存済み game state と MaleCNS body-ID spike から、後で以下を解析できます。

- action 別 body / type / superclass recruitment
- damage/reward event 前後の activity
- soma-neuromere 別の活動変化
- KC→MBON plasticity 差分
- character lineage 間の回路分化
- 繰り返し使われる候補経路
- SWC morphology 上の候補構造

ただし activity correlation だけでは因果回路とは言えません。因果主張には ablation / intervention が必要です。

## 解釈境界

MaleCNS anatomy、Shiu LIF、game I/O、spectator data、game reward、project-defined plasticity は別レイヤです。FightingICE で行動性能が上がっても、ハエが in vivo で同じ reward signal を使うことを意味しません。

## ライセンス

本リポジトリの新規コードは MIT License です。MaleCNS、FightingICE、Shiu model 等の外部成果物にはそれぞれのライセンス/利用条件が適用されます。詳細は [`THIRD_PARTY.md`](THIRD_PARTY.md) を参照してください。
