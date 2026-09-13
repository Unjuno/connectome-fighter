# Public LIVE / research ledger 分離

## 目的

Connectome Fighter は公開面を明示的に分離します。

1. **Dedicated Vercel LIVE** — 1つの shared FightingICE/MaleCNS read-only inference broadcast と神経駆動FlyBody物理表示。
2. **GitHub Pages / Actions** — training、reward/plasticity contract、checkpoint lineage、runtime provenance、logs、raw evidence。

既存の `Unjuno/live` はこの構成の外です。

## Dedicated Vercel LIVE

専用projectをdeployして検証した後、repository variable `CONNECTOME_PUBLIC_BASE_URL` にcanonical URLを設定します。別サイトへのfallbackはありません。

- `/api/runtime-base`: rolling runtime SHAをpersistent Sandboxへstageし、font + OSMesaを入れてsnapshot化。
- `/api/live`: `connectome-fighter-live-broadcast` という1つのshared ephemeral forkをmaintain/inspect。
- `/`: spectator publication。

固定境界:

- `mode=single-shared-live-broadcast`
- `audience_scope=shared-global`
- `learning_enabled=false`
- `policy_pixel_access=false`
- viewerごとのcompute sessionを作らない
- current Vercel projectは `VERCEL_PROJECT_ID` から取得
- 他project IDをhard-codeしない
- runtime release workflowはVercelを直接stageしない
- warming/capacity/errorを明示
- fake/recorded LIVEへfallbackしない

## Spectator channels

primary game viewはofficial FightingICE ScreenData。

neural side channelは同一decision windowのreal annotated MaleCNS activity。

physical side channelは `TuragaLab/flybody@d015e9bfe441bd90ae431bac24c55cb74bdbce26` のreal MuJoCo bodyで、`malecns-annotated-motor-to-flybody-tripod-v2` から駆動します。

MaleCNS→FlyBody mappingはproject-definedです。FightingICE x/y/actionをFlyBodyのposition/poseへコピーしません。整合条件はspatial copyではなくround/frame/decision identityです。

## GitHub runtime publication

`publish-arena-runtime-bundle → precompile-arena-brian2-cython-cache → publish-flybody-runtime-addon → arena-runtime-latest`

ここでpublicationは終了します。専用Vercel appが必要時にexact SHAをstageします。

## Production gate

`CONNECTOME_PUBLIC_BASE_URL` に対して次が全部PASSするまでdedicated production E2Eは未検証です。

1. exact runtime SHA/base adoption
2. shared LIVE running
3. real FightingICE telemetry + advancing MaleCNS decisions
4. nonblank official ScreenData
5. real body-ID annotated activity
6. FlyBody adapter v2 / OSMesa / 59 actuators / sim_steps>0
7. P1/P2 round/frame/decision exact alignment
8. nonblank 320×240 P1/P2 FlyBody render
9. mobile no-overflow/no-fixed-overlay
10. fake frame / SVG fly / FightingICE-position puppet / learning / policy pixel input 不在
