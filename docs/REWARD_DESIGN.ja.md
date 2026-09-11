# Reward design for canonical MaleCNS training

## 目的

この文書は、MaleCNS + pinned Shiu LIF の**行動生成を変えず**、FightingICEから与える外部modulatory signalだけを比較するための仕様である。

現時点では学習を有効化しない。既存trajectoryをofflineで再採点し、reward density / scale / timingを先に固定する。

## 固定条件

reward比較中は次を固定する。

- anatomy: MaleCNS v1.0
- dynamics: pinned Shiu LIF
- sensory stochasticity: observation-driven Poisson spikes
- action readout: output-group spike-count argmax
- external epsilon-greedy / random action injection: なし
- decision interval: 60 FightingICE frames
- action mapping: 固定interface hashで管理
- GARNET / ZEN / LUD / NEZ: 別個体として扱う
- 比較するreward候補は同一trajectoryを再採点する

scheduled baselineではPoisson mechanism自体は固定したまま、workflow chunkごとに決定論的に別seed blockを使う。これにより6時間ごとのrunが同じ乱数列を繰り返すことを避ける。

---

## 初回offline比較の実測

対象: canonical four-character baseline Actions run `34620984683`

- 6 character pairings
- 48 game rounds
- 96 brain-rounds（各試合をP1/P2それぞれの報酬系列として数える）
- 960 decision windows
- 学習/weight更新: **なし**

Actions run `34629201168` でR0/R1/R2をoffline再採点し、PASSした。

### 観測された疎さ

- R0 terminal signが非0: 2 / 960 decisions = **0.2083%**
- 非0 terminal outcome: 2 / 96 brain-rounds = **2.0833%**
- damage差が非0のdecision: 4 / 960 = **0.4167%**
- damage signalが存在したbrain-round: 2 / 96
- 最大final HP margin: 20 HP

このchunkで実際にdamageが生じたのはZEN–NEZの1試合だけだった。damage eventは2 windowあり、双方から見た正負を含めると4 local damage signalsになる。

したがって、現在の主問題は `+1` の絶対値ではなく、**game interactionそのものが少なくreward eventがほぼ発生しないこと**である。

---

## R0 — terminal HP sign（control）

最終HP差だけを使う。

```text
win   +1
 draw   0
loss  -1
```

長所:

- FightingICEの最終目的に最も近い。
- 単純でcontrolとして維持しやすい。

実測上の問題:

- decision-level nonzero rate = 0.2083%。
- 47/48試合が無damageまたは同HPのdrawだったため、ほぼ全trajectoryが無更新になる。

**結論:** controlとして保存するが、最初のlearning rewardとして単独使用する根拠は弱い。

---

## R1 — terminal sign + normalized final HP margin

最終decisionだけで、勝敗signに最終HP差を加える。

```text
R1_terminal = sign(HP_self - HP_opp)
              + (HP_self - HP_opp) / 400
```

初回baselineでは最大marginが20 HPだったため、非0試合では絶対値が `1.00 → 1.05` になっただけだった。

重要なのは、**R1のsignal densityはR0と完全に同じ**だったことである。

- decision-level nonzero rate: 0.2083%
- brain-round nonzero rate: 2.0833%

**結論:** 勝利marginの情報は増えるが、現在の最大問題であるsparsityは解決しない。

---

## R2a — local damage differential + terminal outcome

各decision windowで、次のdecisionまでに変化したHPから局所signalを作る。

```text
damage_component_t = (damage_dealt_t - damage_taken_t) / 10 HP
reward_t = w_damage * damage_component_t
```

最終decisionではさらに terminal win/loss bonus を加える。

```text
reward_T += w_terminal * sign(final HP margin)
```

10 HPを1 damage unitとして、offlineでは以下をgrid searchした。

- `w_damage`: 0.05 / 0.10 / 0.25 / 0.50 / 1.00
- `w_terminal`: 0.25 / 0.50 / 1.00

signal timingはR0より改善したが、初回baselineではdamage自体が2 windowしかなかったため、代表的なR2a系列でもdecision-level nonzero rateは **0.625%** 程度だった。

R0の約3倍だが、依然として非常に疎い。

また、この2 damage windowで選択されていたactionはいずれもBだった。現在のnaive policyはもともとBに強く偏っているため、R2aだけをすぐ有効化すると初期偶然を固定する可能性を否定できない。

**結論:** temporal credit assignment改善には有用だが、単独ではno-contact drawを解決しない。

---

## R2b — R2a + no-damage draw penalty（現在の第一候補、未確定）

R2aに加えて、**ラウンド全体で双方のHPが一度も減らず、最終HPも同じだった場合だけ**、最後のdecisionへ小さい負signalを与える。

これは「前進」「攻撃」「接近」など特定のactionを褒めるものではない。何もゲーム上の結果が起きなかったtimeoutをengineering上の失敗として扱う。

```text
if win/loss:
    terminal = +1 / -1
elif draw and total_damage_exchanged == 0:
    terminal = -δ_stalemate
else:
    terminal = 0

reward_t += w_damage * damage_component_t
```

Actions run `34629518296` でoffline比較し、PASSした。

初回baselineではno-damage drawが94/96 brain-rounds = **97.92%** だった。

R2bではδが0より大きい限り、同じtrajectory上で:

- decision-level nonzero rate: **100 / 960 = 10.4167%**
- brain-round nonzero rate: **96 / 96 = 100%**

となる。

ただし100 nonzero decisionsのうち97が負signalになるため、δを大きくすると全体を負側へ強く偏らせる。

### 現在の暫定scale候補

最初に試すなら次の階層を候補とする。

```text
terminal win/loss : ±1.00
10 HP damage      : ±0.10
no-damage draw    : -0.02 ～ -0.05
```

`δ=0.02` のoffline統計:

- decision nonzero: 10.4167%
- mean |decision reward|: 0.00446
- max |decision reward|: 1.0
- 全brain-roundに非0signal

`δ=0.05`:

- decision nonzero: 10.4167%
- mean |decision reward|: 0.00740
- max |decision reward|: 1.0
- 全brain-roundに非0signal

**現時点の判断:** `w_damage=0.10, w_terminal=1.0, δ_stalemate=0.02～0.05` を最初のlearning experiment候補に残す。ただし次の独立Poisson seed chunkでもno-contact率とdamage頻度を再測定してからfreezeする。

### 注意

R2bはzero-sum rewardではない。no-damage drawでは両個体が同時に負signalを受ける。これは生物学的事実ではなく、探索を開始させるための明示的engineering shaping conditionである。

---

## R3 — valence/compartment-specific DAN gating（後段の生物学的比較条件）

R0/R1/R2ではgame outcomeを外部scalar signalとして扱う。一方、Drosophila mushroom bodyではdopaminergic modulationはcompartment-specificであり、KC→MBON plasticityは単一の全MB scalar updateとして理解すべきではない。

後段ではMaleCNS annotation上のDAN / MBON compartmentを利用し、positive / negative valenceを別経路へmappingする比較条件を作る。

これはgame outcome→DAN mapping自体が人工interfaceであるため、解剖学的配線と混同せずversion管理する。

---

## Plasticity ruleとの分離

現在の `reward_plasticity.py` はproject extensionとして:

- real KC→MBON candidate edgeのみ変更可能
- topology固定
- transmitter sign固定
- terminal reward `-1/0/+1` 専用
- positive rewardでeligible KC→MBON magnitudeをdepress
- negative rewardでstrengthen

というanti-Hebbian型を実装している。

R2a/R2bを採用する場合、rewardはtime-localかつ連続値になるため、**reward definitionをfreezeした後にplasticity APIを時系列modulatory signalへ拡張する必要がある**。

rewardの選択とplasticity direction/learning rateの選択を同時に変更してはいけない。

---

## 採用Gate

最初のcanonical learning rewardをfreezeする条件:

1. 少なくとも2つ以上の独立Poisson seed chunksでR0/R1/R2a/R2bをoffline採点する。
2. reward density / mean absolute signal / max signal / sign imbalanceを比較する。
3. action randomness、readout、anatomy、LIF、game interfaceは変更しない。
4. 採用rewardの係数をversioned configへ固定する。
5. その後、1キャラ・1matchだけplasticityを有効化してweight変化を監査する。
6. 連続学習はさらにcheckpoint resumeを別Actions runで実証してから有効化する。

---

## rewardにしないもの

少なくとも最初の比較では次を直接rewardにしない。

- 前進したこと
- 攻撃ボタンを押したこと
- 相手へ近づいたこと
- action diversityそのもの
- NEUTRALを避けたこと

これらを直接rewardすると、「ゲーム結果を改善した回路」と「設計者指定actionを出す回路」を分離しにくくなる。

---

## 関連一次文献

- Hige T, Aso Y, Rubin GM, Turner GC. *Plasticity-driven individualization of olfactory coding in mushroom body output neurons.* Nature 526, 258–262 (2015). DOI: `10.1038/nature15396`.
- Felsenberg J et al. *Re-evaluation of learned information in Drosophila.* Nature 544, 240–244 (2017). DOI: `10.1038/nature21716`.
- Felsenberg J et al. *Dopaminergic mechanism underlying reward-encoding of punishment omission during reversal learning in Drosophila.* Nature Communications 12, 1115 (2021). DOI: `10.1038/s41467-021-21388-w`.
- *Dopamine-mediated interactions between short- and long-term memory dynamics.* Nature (2024). DOI: `10.1038/s41586-024-07819-w`. The study/model explicitly examines compartmental DAN/MBON interactions and bidirectional anti-Hebbian KC→MBON plasticity.

## Interpretation boundary

R0/R1/R2 game rewardは外部engineering signalであり、FightingICEの勝敗・damage・stalemateがハエの内因性dopamine signalそのものである、という主張ではない。R3でもMaleCNS anatomyを利用するが、game outcomeからDANへのmappingは人工interfaceである。
