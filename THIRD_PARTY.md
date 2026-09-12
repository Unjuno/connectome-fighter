# Third-party sources and redistribution

This project does not vendor FightingICE release assets, MaleCNS source datasets,
or Shiu reference source in the Git repository. Deployment workflows obtain and
verify those external resources separately. Review source-specific code, asset,
and dataset licenses before publishing a derivative artifact; a repository's
code license does not itself establish permissions for all associated datasets
and game assets.

The public arena runtime may package the pinned **TuragaLab/flybody** Python
software and its Python dependencies for the spectator-only MuJoCo fruit-fly
physics view. The inspected upstream FlyBody repository is distributed under
**Apache License 2.0**. Its supplementary datasets, trained policies and other
external downloads remain separate resources and are not automatically granted
the same terms merely by the software license. The current public runtime uses
the FlyBody software/body model and does not claim that the project-defined
MaleCNS-to-actuator adapter is part of upstream FlyBody or a published native
motor-neuron-to-muscle map.

Public references and pins are recorded in `docs/SOURCES.md`.
Newly authored project code is distributed under the repository MIT License.
No global license is asserted for external sources, datasets, game assets, or papers.
