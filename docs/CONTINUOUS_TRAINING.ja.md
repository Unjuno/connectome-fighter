# 継続学習リーグと観戦ページ設計

## 目的

Connectome Fighter の主成果物を、単発の実験ではなく「同じハエ由来コネクトーム制御器がcheckpointを引き継ぎながら継続学習し、その世代間・対戦相手との試合をWebで観戦できる系」にする。

## 実行モデル

GitHub-hosted Actions の1 jobを永続プロセスとして扱わない。学習を bounded chunk に分割する。

```text
latest checkpoint
      ↓ restore
bounded training chunk
      ↓
new checkpoint
      ↓
evaluation league
      ↓
replay/metrics export
      ↓
GitHub Pages deploy
      ↓
next scheduled run restores new checkpoint
```

### 学習jobの不変条件

- 同時にcheckpointを書けるtraining jobは1つだけにする。
- job中の対戦ではpolicy versionを固定し、更新はbatch/round境界で行う。
- incomplete / disconnected roundはlossとして学習しない。
- evaluation matchではweightを更新しない。
- checkpointにはmodelだけでなくoptimizer、RNG、generation、match count、code SHA、connectome hash、routing hash、schema versionを含める。
- Actions cacheをcheckpointの唯一の保存先にしない。cacheはimmutableなgraph/runtime依存物に使う。

## checkpoint階層

### latest
次のjobが必ず復元するrolling checkpoint。破損時に検出できるchecksumとmanifestを付ける。

### champion
固定evaluation leagueで過去championを有意に上回った時だけ更新する。

### archive
一定generation間隔またはchampion更新時にimmutable snapshotを残す。全世代を保存するとストレージを浪費するため間引く。

## league

最低限、次を分ける。

1. `latest vs champion`
2. `latest vs archived checkpoints`
3. `latest vs fixed baseline`
4. 将来: `biological topology vs matched rewired topology`

自己対戦だけの勝率は進歩指標にしない。両者が同時に強くなると勝率は約50%のままだからである。

## Pages spectator

Pagesは計算を行わない。Actionsが生成した静的JSONを描画する。

### `site/data/status.json`

- current generation
- total train matches
- checkpoint ID
- champion ID
- Elo / fixed-baseline win rate
- latest evaluation summary
- learning-history points

### `site/data/latest-replay.json`

ブラウザでJava/FightingICEを起動せず観戦できるよう、評価試合のtelemetryをframe列へ変換する。

推奨schema:

```json
{
  "schema_version": 1,
  "match_id": "...",
  "p1": {"checkpoint_id": "...", "label": "latest"},
  "p2": {"checkpoint_id": "...", "label": "champion"},
  "result": {"winner": "P1", "p1_hp": 120, "p2_hp": 0},
  "frames": [
    {
      "frame": 0,
      "p1": {"x": 100, "y": 0, "hp": 400, "action": "NEUTRAL"},
      "p2": {"x": 700, "y": 0, "hp": 400, "action": "NEUTRAL"}
    }
  ]
}
```

最初のviewerはtelemetryから簡易2D表示する。FightingICEの実画面録画は別機能とし、学習パイプラインの必須条件にしない。

## CIから常時学習へ

GitHub-hosted runnerではjob時間に上限があるため、短いjobをcheckpointで連結する。真の24/7学習が必要になった時はself-hosted runnerへtrainerだけ移し、GitHub Actionsをscheduler/orchestrator、Pagesを観戦UIとして残す。

## 研究上の分離

「継続学習して強くなる」と「Drosophila由来topologyが優れている」は別命題である。

- 継続学習リーグ: persistent agentの工学的成立
- A/B研究: biological topology とmatched rewiringの差

前者が成功しても後者の証拠にはしない。
