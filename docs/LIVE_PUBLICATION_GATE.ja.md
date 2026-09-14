# Public LIVE publication gate

The `/connectome` public surface is publishable only when all of these conditions hold on the exact runtime release being served:

1. One fixed shared Vercel broadcast is used; viewer count never creates one model process per viewer.
2. GARNET approved inference vs ZEN baseline remains read-only unless a separately audited promotion changes that contract.
3. FightingICE v7.1 official `ScreenData` is available as the primary game view. No synthetic game frame may replace it while being labelled LIVE.
4. Screen pixels are spectator-only (`policy_pixel_access=false`) and cannot enter MaleCNS action selection or learning.
5. The same decision window exposes real sensory-body drive, recurrent spike activity, real motor-body contributions, all seven action-group counts, selected action, and actual FightingICE x/y/HP/action.
6. Spectator anatomy uses official released MaleCNS v1.0 SWC context plus real body-ID annotations. Regional highlighting is explicitly bounded observational context, not an all-neuron activity map or functional claim.
7. The Drosophila embodiment uses the pinned TuragaLab/FlyBody MuJoCo body and physics. It is driven from annotated MaleCNS motor/descending activity through an explicit versioned project adapter. FightingICE x/y/action must not be used to puppet the FlyBody body, and no SVG fallback may be presented as the physical fly.
8. FlyBody state/render is shown as synchronized only when round, FightingICE frame and MaleCNS decision index agree with the public neural telemetry. Stale physical-body frames are withheld.
9. The neural-to-FlyBody actuator adapter is identified as a project-defined experimental interface, not a published native Drosophila motor-neuron-to-muscle innervation map.
10. Mobile layout presents the official fight first in a single column and must not require horizontal scrolling at 320 CSS px viewport width.
11. Warming/error states are explicit. The page must never fabricate a fight, screen frame, neural activity, anatomy location, or FlyBody physics frame.
12. GitHub candidate learning/log history remains separate from the Vercel served state; candidate checkpoints are never auto-promoted.

A production smoke must fail if the official ScreenData endpoint, causal neural side channels, same-decision FlyBody state, or nonblank FlyBody MuJoCo renders disappear from a runtime that declares FlyBody support.
