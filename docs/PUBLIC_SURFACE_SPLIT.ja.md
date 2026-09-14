# Public LIVE / research ledger split

## Purpose

Connectome Fighter has two intentionally separate public surfaces:

1. **Dedicated Vercel LIVE** — one globally shared FightingICE/MaleCNS read-only inference broadcast with a neural-driven FlyBody physics spectator.
2. **GitHub Pages / Actions research ledger** — training workflows, reward/plasticity contracts, checkpoint lineage, runtime provenance, logs, and raw evidence.

The unrelated `Unjuno/live` application is outside this architecture.

## Dedicated Vercel LIVE

The canonical production URL is supplied through the repository variable `CONNECTOME_PUBLIC_BASE_URL` only after a dedicated project is deployed and verified. There is no fallback URL.

Control endpoints:

- `/api/runtime-base` — materialize the current runtime release into a SHA-addressed persistent Sandbox, install fonts + OSMesa, and snapshot it;
- `/api/live` — maintain and inspect one shared ephemeral `connectome-fighter-live-broadcast` fork;
- `/` — spectator publication.

Contract:

- `mode=single-shared-live-broadcast`;
- `audience_scope=shared-global`;
- `learning_enabled=false`;
- `policy_pixel_access=false`;
- one fixed shared broadcast, not one session per viewer;
- current Vercel project identity comes from `VERCEL_PROJECT_ID`;
- no hard-coded unrelated project ID;
- no release workflow directly stages into Vercel;
- explicit warming/capacity/error states;
- no fake or recorded LIVE fallback.

## Spectator channels

Primary game view: official FightingICE ScreenData.

Neural side channel: bounded annotated MaleCNS activity for the same decision window.

Physical side channel: real upstream FlyBody MuJoCo body, pinned to `TuragaLab/flybody@d015e9bfe441bd90ae431bac24c55cb74bdbce26`, driven by `malecns-annotated-motor-to-flybody-tripod-v2`.

The FlyBody mapping is project-defined. FightingICE x/y/action does not position or pose the physical FlyBody. The public contract requires FlyBody and live telemetry to match round/frame/decision identity, not spatial coordinates.

All visual channels are spectator-only and are not policy inputs.

## GitHub runtime publication

```text
publish-arena-runtime-bundle
  → precompile-arena-brian2-cython-cache
  → publish-flybody-runtime-addon
  → arena-runtime-latest
```

Runtime publication ends at the GitHub release. The dedicated Vercel app stages the exact rolling SHA when needed. This separation prevents a publication workflow from mutating an unrelated project.

## Research / training ledger

GitHub publishes or preserves canonical substrate/dynamics, training/evaluation workflows, reward/plasticity contracts, checkpoint lineage, approved inference handoff, public match logs, runtime checksums, Actions artifacts, and interpretation boundaries.

Continuous production reward-driven learning remains OFF. Candidate history is not an auto-promotion path.

## Production verification gate

Dedicated production is PASS only when all of the following hold against `CONNECTOME_PUBLIC_BASE_URL`:

1. exact current runtime SHA/base is adopted;
2. shared LIVE reaches running;
3. GARNET vs ZEN telemetry has real frame/action/HP/position and advancing MaleCNS decisions;
4. official 480×320 FightingICE ScreenData is nonblank;
5. annotated MaleCNS activity contains real body IDs;
6. P1/P2 FlyBody state uses adapter v2, OSMesa, 59 actuators, and `sim_steps > 0`;
7. FlyBody decision identity exactly equals live round/frame/decision for both sides;
8. P1/P2 320×240 FlyBody renders are nonblank;
9. phone-width publication has no horizontal overflow or fixed overlay;
10. no synthetic frame, SVG fly, FightingICE-position puppet, learning, or policy pixel access is substituted.

Until this gate passes on the dedicated project, production E2E status is **NOT YET VERIFIED**.
