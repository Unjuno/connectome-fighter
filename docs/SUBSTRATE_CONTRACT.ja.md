# Canonical Neural Substrate Contract

## 目的

この文書は Connectome Fighter で「何をハエの脳として扱うか」を固定する。

**canonical control path では、汎用RNN/MLPや自作sigmoid recurrent networkをハエ脳の代用品として使用しない。**

## 1. 解剖学的 substrate

Canonical anatomy は **MaleCNS v1.0** とする。

- dataset: `male-cns:v1.0`
- project: FlyEM / HHMI Janelia + University of Cambridge + MRC LMB + Google Research
- paper: Berg et al., *Cell* (2026), DOI `10.1016/j.cell.2026.08.015`
- official landing page: `https://male-cns.janelia.org/`
- bulk data root: `gs://flyem-male-cns/v1.0/`
- license: CC-BY

MaleCNS v1.0 は brain + optic lobes + ventral nerve cord を連続的に含む雄 Drosophila CNS connectome である。論文は 166,691 neurons と報告している。

Canonical import で最低限使用する一次データ:

- `body-annotations-male-cns-v1.0-minconf-0.5.feather`
- `body-neurotransmitters-male-cns-v1.0.feather`
- `connectome-weights-male-cns-v1.0-minconf-0.5.feather`

必要になった場合のみ synapse-level partner/location table を追加する。最初から 6.8–12.7 GB のsynapse tableを常用しない。

### neuron candidate selection

body annotation の全行をニューロンと見なさない。最初の候補集合は論文repositoryの `supplemental_data/quantify-neuron-connections.ipynb` と同じく、`superclass` が定義され、名前に `tbc` を含まないものとする。v1.0に対してこの基準を再計算し、論文記載数との差は勝手に補正せずmanifestに残す。

## 2. 重要な区別: connectome != executable brain dynamics

MaleCNS は実測・再構成された**配線図、synaptic connection strength、cell annotation、neurotransmitter prediction**であり、膜電位を時間発展させる公式シミュレータそのものではない。

したがって「Googleが公開したモデルを使う」という本プロジェクトの意味を以下のように分離する。

1. **構造**: MaleCNS v1.0 をそのまま使う。
2. **神経ダイナミクス**: 公開済み・論文化済みの Drosophila LIF model を使う。
3. **ゲームとのinterface**: 本プロジェクト固有。生物学的事実と混同しない。

## 3. 神経ダイナミクス

初期 canonical dynamics は Shiu et al. 2024 の leaky integrate-and-fire (LIF) model とする。

- paper: Shiu et al., *Nature* 634, 210–219 (2024)
- DOI: `10.1038/s41586-024-07763-9`
- reference code: `https://github.com/philshiu/Drosophila_brain_model`
- pinned `model.py` commit: `2a83ad611cd9768f8c9723fc613ed27761a5feb5`
- simulator in reference implementation: Brian2

重要: Shiu model 自体は FlyWire female-brain connectome 上で検証されたモデルであり、MaleCNS v1.0 への適用は**本プロジェクトによる移植**である。従って結果を「Google公式の生理モデル」と表現しない。

初期移植では Shiu の neuron equations / threshold / refractory / synaptic delay / per-synapse weight convention を変更せず、MaleCNS の接続強度と neurotransmitter identity を入力する。

Shiu論文の分類では GABA と glutamate を inhibitory、acetylcholine / dopamine / octopamine / serotonin を excitatory とする。MaleCNS v1.0 にはこれに加えて histamine が多数含まれるため、**histamineを無言で既存カテゴリへ押し込まない**。Drosophila視覚系ではhistamine-gated chloride channelによる抑制性伝達が実験的に確立しているので、MaleCNS移植では `histamine = inhibitory` を明示的な拡張ルールとしてversion/hash化する。ただしこれはShiu reference modelそのものではなくMaleCNS adapterの追加仮定である。

`consensus_nt` が `unclear` または欠損するcanonical candidateについても、推定符号を勝手に付与しない。coverageを先に計測し、除外・fallback・感度解析のどれを採るかをmanifestで明示する。

## 4. NN禁止境界

Canonical control path に以下を置かない。

- MLP policy
- GRU/LSTM/RNN policy
- custom sigmoid recurrent brain
- GNN を「脳本体」として使うこと
- trainable latent encoder が神経活動を置換すること

PyTorch等を高速なtensor計算器として使うこと自体は禁止しない。ただし**学習可能な人工NNをハエ脳の代わりにしない**。

## 5. キャラごとの「別の脳」

GARNET / ZEN / LUD / NEZ は同じ immutable MaleCNS anatomy を参照してよいが、以下は共有しない。

- membrane potential / synaptic state
- RNG state
- episode history
- plasticity state（導入時）
- character-specific checkpoint

つまり anatomy asset の共有はメモリ最適化であり、simulation state は4個体で独立する。

## 6. ゲームinterface

FightingICE の状態を MaleCNS sensory populations に注入するmappingと、MaleCNS motor/descending activityをgame actionへ変換するmappingは人工interfaceである。

このinterfaceは必ずversionedし、以下をログへ残す。

- game feature -> stimulated neuron/body IDs
- stimulation rate/current
- selected neuron type / superclass / sensory modality
- output neuron/body IDs
- output aggregation rule
- action chosen and each output group's contribution

interfaceの学習を行う場合でも、脳本体と混同しない。最初のcanonical gateでは固定mappingを優先する。

## 7. 後解析用ログ

「何がどういう構造で起用されたか」を後から解析できることを第一級要件とする。

各decision windowで最低限保存する:

- character / lineage / checkpoint
- frame / game observation / selected action
- externally stimulated neuron IDs and drive
- spiking neuron IDs and spike times/counts
- membrane-potential summary
- neuron type / superclass / class / side / soma neuromere where available
- neurotransmitter identity + confidence
- downstream motor/descending contribution
- graph/dataset hash
- dynamics-model version + parameter hash
- interface version

静的annotationはrunごとに重複保存せず、bodyIdでjoin可能な固定metadata tableとしてhashをpinする。dynamic logは `decisions.jsonl` と event-compressed `spikes.parquet` に分ける。これにより後からstatic connectivity graphへjoinして、局面別recruitment、経路、hub、sensor→motor flowを再解析できる。

raw all-neuron membrane tracesは容量が大きいため、canonical evidenceとしては event-compressed spike logs + selected state summariesを保存し、必要な試合だけfull traceを保持する。

## 8. Legacy扱い

旧 pipeline の以下は canonical evidence ではない。

- FlyWire/Shiu v783 graph を使った continuous trainer
- `brain.py` の custom sigmoid recurrent core
- PPO readout による legacy checkpoint
- Release tag `training-state`

これらは実装検証・FightingICE bridge検証の履歴として残してよいが、MaleCNS個体の学習世代として継承しない。

## 9. Gate

MaleCNS版 continuous training を再開する前に以下を全てPASSさせる。

1. official MaleCNS files のURL・size・hashを記録してimportできる。
2. body IDs / connection weights / transmitter predictions のjoinが一意に検証できる。
3. canonical candidate set とNT coverageがrelease-specificに記録され、unknown signを暗黙補完していない。
4. published LIF equationsの小回路golden testがpinned reference implementationと一致する。
5. FightingICE 1 round が `MaleCNS -> LIF spikes -> action` の経路で完走する。
6. replayに実 MaleCNS body ID とactivity traceが表示される。
7. 4キャラのsimulation stateが独立している。

この7点がPASSするまで scheduled learning は無効のままにする。
