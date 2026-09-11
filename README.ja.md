# Connectome Fighter

このプロジェクトは、FightingICE を対戦環境として使い、**実際に公開された Drosophila CNS connectome を神経基盤として**キャラクターを制御し、対戦時にどの神経構造が使われたかを後から解析できるようにする研究・実装基盤です。

## Canonical substrate

現在の canonical target は次です。

- anatomy: **MaleCNS v1.0** (`male-cns:v1.0`)
  - FlyEM / HHMI Janelia + Cambridge + MRC LMB + Google Research
  - brain + optic lobes + ventral nerve cord
  - official: https://male-cns.janelia.org/
- dynamics: **Shiu et al. 2024 の公開 leaky integrate-and-fire (LIF) model**
  - DOI: `10.1038/s41586-024-07763-9`
  - reference code: https://github.com/philshiu/Drosophila_brain_model

重要: MaleCNS は解剖学的connectomeであり、Google公式の膜電位シミュレータではありません。したがって、**構造はMaleCNS、時間発展は公開済みLIF model、ゲームI/Oは本プロジェクト固有interface**として明確に分離します。

詳細: [`docs/SUBSTRATE_CONTRACT.ja.md`](docs/SUBSTRATE_CONTRACT.ja.md)

## NNを脳の代用品にしない

Canonical control path では、MLP/RNN/GRU/GNN/custom sigmoid recurrent network を「ハエ脳本体」として使いません。PyTorch等を高速計算器として使うことはあり得ますが、学習可能な人工NNでconnectomeを置換しません。

## キャラごとの別個体

FightingICE の GARNET / ZEN / LUD / NEZ は、それぞれ独立したsimulation state / RNG / checkpoint / plasticity stateを持ちます。immutableなMaleCNS anatomy assetをメモリ節約のため共有しても、神経状態は共有しません。

## 後解析を第一級要件にする

各decision windowで、少なくとも次を保存します。

- game observation / action
- 刺激した MaleCNS body IDs
- spikeした body IDs と spike count
- membrane-potential summary
- neuron type / superclass / side / soma neuromere
- neurotransmitter identity + confidence
- motor/descending output contribution
- dataset/dynamics/interface hash

これにより、対戦後に「どの神経型・経路・階層が、どの局面と行動で使われたか」を解析できます。

## Legacy pipeline

旧実装の以下は、FightingICE bridgeやloggingの工学的検証としては残しますが、canonicalなハエ脳の結果として扱いません。

- FlyWire v783 substrate
- `brain.py` の custom sigmoid recurrent core
- PPO readout checkpoint
- Release tag `training-state`

旧 continuous-training workflow は自動実行を停止しています。

## 再開gate

MaleCNS版のscheduled learningは、次を確認してから有効化します。

1. official MaleCNS filesのprovenance/hash確認
2. body ID / connection weight / neurotransmitter join検証
3. published LIF equationsのreference一致
4. MaleCNS -> LIF -> FightingICE の1 round完走
5. replayで実MaleCNS body ID/activityを可視化
6. 4キャラの神経状態独立性を確認

## ライセンス

本リポジトリの新規コードはMIT Licenseです。MaleCNS、FightingICE、Shiu model等の外部成果物にはそれぞれのライセンスが適用されます。
