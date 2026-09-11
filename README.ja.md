# Connectome Fighter

[FightingICE](https://github.com/TeamFightingICE/FightingICE) を既存の対戦環境として使い、Drosophila由来のコネクトーム配線に制約されたファイターを**checkpointを引き継ぎながら継続学習**させ、その世代間・対戦相手との試合をGitHub Pagesで観戦できるようにする研究・実装基盤です。

[Training Arena](https://unjuno.github.io/connectome-fighter/) · [English](README.md)

## 主目的

```text
latest checkpoint
      ↓
FightingICEで追加学習
      ↓
new checkpoint
      ↓
champion / archive / baseline と評価対戦
      ↓
replay + metrics を出力
      ↓
GitHub Pagesで観戦
      ↓
次のjobがcheckpointを復元して続行
```

GitHub-hosted Actionsは永続プロセスではないため、学習はbounded chunkに分割し、各job間をcheckpointで接続します。真の24/7計算が必要になった場合はtrainerだけself-hosted runnerへ移し、Actionsをscheduler/orchestrator、Pagesを観戦UIとして残す設計です。

詳細: [`docs/CONTINUOUS_TRAINING.ja.md`](docs/CONTINUOUS_TRAINING.ja.md) · [Milestone #5](https://github.com/Unjuno/connectome-fighter/issues/5)

## 現在の範囲

- FightingICE 7.1 / pyftg 2.3 の実対戦bridge
- 数値観測 → 制御器 → 8操作
- 勝利 `+1`、敗北 `-1`、引き分け `0` のterminal-only報酬contract
- 二者の対戦ログを照合する監査層
- FlyWire/Shiu v783由来graphの再現可能なimport pipeline
- 実配線と次数・符号を保存したrewire対照を比較するgraph層
- 疎なconnectome-constrained recurrent controllerの工学的scaffold
- CIとGitHub Pages spectator scaffold

## 現在の制限

継続RL trainerとcheckpoint round-tripはまだ未完成です。Pagesは観戦用data contractとviewerの骨格を持ちますが、実学習リプレイはまだ公開されていません。また `brain.py` のsigmoid再帰モデルはShiuらのLIFモデルの再現ではありません。

## 最小検査

```bash
python -m pip install -e '.[test]'
python -m pytest -q
python scripts/smoke_core.py
```

ライブ対戦にはFightingICE本体と `pyftg==2.3` が必要です。

## 研究上の分離

「同じハエ由来制御器が継続学習して強くなる」と「Drosophila由来topologyが対照配線より有利」は別命題です。後者を主張するには、観測・行動・報酬・学習予算・seed・評価相手を固定し、実配線と構造対照を比較します。

## ライセンス

このリポジトリで新規作成したコードはMIT Licenseです。FightingICE、コネクトームデータ、論文などの外部成果物には各自の利用条件が適用されます。
