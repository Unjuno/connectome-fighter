# Reward design for canonical MaleCNS training

## 固定条件

報酬比較の間は、現在の行動生成を変更しない。

- anatomy: MaleCNS v1.0
- dynamics: pinned Shiu LIF
- sensory randomness: observation-driven Poisson spikes
- action readout: output-group spike-count argmax
- action exploration: 外部 epsilon-greedy / random action injection なし
- character brains: GARNET / ZEN / LUD / NEZ を別個体として扱う

これにより、reward designを変更したときの差をaction exploration変更と混同しない。

## R0 — terminal HP sign（現在のbaseline）

ラウンド終了時だけ、残HPが相手より高ければ +1、同値なら 0、低ければ -1。

利点:
- FightingICEの目的と直接一致する。
- 最も単純で比較基準として残しやすい。

問題:
- 報酬が非常に疎い。
- 1回の有効打をラウンド全体の神経活動へ帰属しやすく、credit assignmentが粗い。

現在はR0でtraceだけ取得し、weight更新は無効にしている。

## R1 — terminal outcome + terminal HP margin

勝敗の +1 / 0 / -1 を主信号として残し、最終HP差を小さい補助信号として加える。

狙い:
- 勝敗の目的を維持したまま、同じ勝ちでも圧勝と僅差を区別する。
- 行動そのもの（前進、攻撃、ジャンプ等）へ人為的な好みを与えない。

注意:
- ダメージが一度も発生しないラウンドは依然として無信号。
- temporal credit assignmentは改善しない。

## R2 — damage timing + terminal outcome（第一候補）

各decision windowで「相手に与えたdamage」と「自分が受けたdamage」の差を即時のmodulatory signalとして記録し、ラウンド終了時にはR0の勝敗signalも加える。

狙い:
- どの神経活動の直後に有効打が起きたかを短い時間幅で帰属できる。
- 「前へ進め」「攻撃しろ」のような手作業の行動rewardを入れず、ゲーム目的だけからsignalを作れる。
- 現在のspike/body-ID logからoffline再計算できるため、R0と同じtrajectoryを使って比較可能。

注意:
- hit tradingを単純なdamage差として扱うため、terminal outcomeとの併用が必要。
- signal timingをKC→MBON eligibility traceの時間スケールへどう写像するかは別パラメータとして固定する必要がある。

## R3 — valence-specific DAN gating（生物学的比較条件）

正と負のgame outcomeを同じKC→MBON集合へ単純に逆符号で掛けるのではなく、MaleCNS annotation上のDAN / MBON compartmentを用いてpositive / negative valenceを別経路へ入力する。

背景:
- Drosophila mushroom bodyでは、dopaminergic neuronsがcompartment-specificにKC→MBON plasticityを調節する。
- rewardとpunishmentは単純に同一synapse集合の強化/弱化として表現されるとは限らず、異なるDAN/MBON compartmentsが関与する。

これはR2より実装と生物学的解釈が難しいため、R0/R1/R2のengineering comparison後に行う。

## 採用順序

1. R0を継続baselineとして保存する。
2. 現在のtrajectoryからR1/R2をoffline再計算し、signal densityとcredit timingを比較する。
3. action randomness/readoutを変えずにR2だけを有効化したlineageを作る。
4. R0とR2を同一seed/pairingで比較する。
5. その後にR3のcompartment-specific DAN mappingを実装する。

## 変更しないもの

reward experiment中は次をrewardにしない。

- 前進したこと
- 攻撃ボタンを押したこと
- 相手へ近づいたこと
- action diversityそのもの
- NEUTRALを避けたこと

これらを直接rewardすると、「ゲームに勝つ回路」を見ているのか「設計者が指定した行動を出す回路」を見ているのか分離しにくくなる。

## 関連一次文献

- Hige T, Aso Y, Rubin GM, Turner GC. Plasticity-driven individualization of olfactory coding in mushroom body output neurons. Nature 526, 258–262 (2015). DOI: 10.1038/nature15396.
- Yamada D et al. Cyclic nucleotide-induced bidirectional long-term synaptic plasticity in Drosophila mushroom body. Journal of Physiology (2024). DOI: 10.1113/JP285745.
- Felsenberg J et al. Dopaminergic mechanism underlying reward-encoding of punishment omission during reversal learning in Drosophila. Nature Communications 12, 1115 (2021). DOI: 10.1038/s41467-021-21388-w.

## Interpretation boundary

R0/R1/R2のgame rewardは外部から与えるengineering signalであり、FightingICEの勝敗がハエでそのまま内因性dopamine signalとして表現される、という主張ではない。R3でもMaleCNS anatomyを利用するが、game outcomeからDANへのmapping自体は実験上の人工interfaceとしてversion管理する。
