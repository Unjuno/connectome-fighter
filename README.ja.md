# Connectome Fighter

[FightingICE](https://github.com/TeamFightingICE/FightingICE) を既存の対戦環境として使い、Drosophila由来のコネクトーム配線に制約された制御器が、同条件の対照ネットワークと比べて学習・転移で有利かを検証する研究基盤です。

[Dashboard](https://unjuno.github.io/connectome-fighter/) · [English](README.md)

## 現在の範囲

- FightingICE 7.1 / pyftg 2.3 を対象
- 数値観測 → 制御器 → 8操作のbridge
- 勝利 `+1`、敗北 `-1`、引き分け `0` のterminal-only報酬
- 二者の対戦ログを照合する監査層
- 実配線と、次数・符号を保存したrewire対照を比較するためのgraph層
- 疎なconnectome-constrained recurrent controllerの工学的scaffold
- CIとGitHub Pages

## 重要な制限

現時点では、実ハエデータを同梱していません。また `brain.py` のsigmoid再帰モデルはShiuらのLIFモデルの再現ではありません。実コネクトーム、合成fixture、mock test、実ゲーム試行を同じ証拠として扱わないことをルールにしています。

## 最小検査

```bash
python -m pip install -e '.[test]'
python -m pytest -q
python scripts/smoke_core.py
```

ライブ対戦にはFightingICE本体と `pyftg==2.3` が別途必要です。

## 主仮説

実配線の利点を主張するには、観測・行動・報酬・学習予算・seed・評価相手を固定し、実配線と構造対照の差を比較します。「学習した」だけでは「ハエの配線が有利」とは結論しません。

## ライセンス

このリポジトリで新規作成したコードはMIT Licenseです。FightingICE、コネクトームデータ、論文などの外部成果物には各自の利用条件が適用されます。
