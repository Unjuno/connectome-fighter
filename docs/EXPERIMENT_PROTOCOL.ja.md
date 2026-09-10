# Experiment protocol v0

## 目的

FightingICEを固定した対戦環境として用い、Drosophila由来connectome topologyが、構造的に対応させた対照networkよりも競争課題の学習・転移に有用なinductive biasを与えるか検証する。

## Evidence classes

結果には必ず次の区分を付ける。

1. `synthetic_fixture`: 合成graph・mock APIのみ。
2. `live_game_control`: FightingICEを実行したがbiological graphを使っていない。
3. `live_game_biological`: 来歴検証済みbiological graphを使用。
4. `confirmatory`: 事前固定した条件・seed集合・評価相手で行った確証試験。

低いclassの結果を高いclassとして報告しない。

## A/B設計

### A: biological topology

- source/version/checksum/license/preprocessingをmanifestに固定する。
- 観測、行動集合、報酬、optimizer、学習量、seed、評価相手をBと一致させる。

### B: rewired control

- node数、edge数、各nodeのin/out-degree、符号別in/out-degreeを保存する。
- edge targetを交換する。
- rewiring seed、accepted swaps、edge overlapを保存する。
- rewiringのmixingが証明されていない場合はその旨を記録する。

### 工学参照

MLP/RNN等を別枠で置けるが、A対Bの生物学的主比較と混同しない。

## 報酬

初期主条件はterminal-only。

- win: +1
- loss: -1
- draw: 0
- incomplete/disconnected episode: 学習対象外

途中のdamage reward等は別A/B条件として扱う。

## 評価量

主評価候補:

- held-out opponent win rate
- learning-curve area under curve
- matches-to-threshold
- cross-opponent generalization
- policy robustness after action removal

自己対戦中の当事者間勝率だけを進歩指標にしない。

## H / T / D / C / U

**H — 反証可能仮説**  
実connectome topologyは、matched rewired controlより、未使用対戦相手に対するsample efficiencyまたは最終性能を改善する。

**T — 最小検証**  
同じ初期化規則・学習予算で独立seedを複数用意し、A/Bを対応付きで学習させる。探索に使ったseedと確証用seedを分離する。

**D — 判定**  
事前に定めたeffect metricについて、A-B差の区間推定が実用差の正側に十分離れた場合のみPASS。区間が実用差をまたぐ場合はUNCERTAIN。実用差に届かないことを支持する場合はFAIL。

**C — 対立仮説**  
差がconnectome topologyではなく、input/output routing、weight scale、network size、optimizer interaction、特定相手へのoverfitで生じる可能性を個別に検査する。

**U — 不確かさ**  
主要源はbiological annotation、synaptic sign/strength model、routing assumption、RL seed variance、opponent distribution。生物学的不確かさと統計的sampling errorを別に報告する。

## 最初の実装順序

1. Random vs Randomのlive FightingICEをheadlessで完走。
2. P1/P2の観測、action request、remaining HP、terminal rewardを二者ログで照合。
3. synthetic graph controllerを接続し、ゲームbridgeを検証。
4. biological data importerを追加し、manifest/checksumでfail-closedにする。
5. fixed-connectome + trainable readoutを学習。
6. matched rewired controlとのA/B。
7. topology固定・既存edge weightのみ学習する条件を別実験として追加。
8. held-out opponentsで確証試験。

## 解釈上の禁止事項

- 格ゲーを学習しただけで「ハエの知能を再現した」としない。
- artificial encoder/readoutの性能をconnectome固有能力としない。
- synthetic graphをbiological resultとして扱わない。
- 同一学習済みpolicyの大量対戦を、独立学習seed数として数えない。
