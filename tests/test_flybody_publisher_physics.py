"""Real pinned FlyBody integration; fixtures are engineering inputs, not biology."""
from __future__ import annotations

import gc
import importlib.util
import json
import math
import os
from pathlib import Path

import numpy as np
import pytest

# CI requires this dependency. Local core tests may explicitly report a skip.
os.environ.setdefault('MUJOCO_GL', 'osmesa')
if os.environ.get('REQUIRE_FLYBODY_PHYSICS') == '1':
    import flybody  # noqa: F401
else:
    pytest.importorskip('flybody', reason='real FlyBody/MuJoCo is not installed')

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('real_flybody_publisher', ROOT/'scripts/run_live_flybody_publisher.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_real_publisher_step_clock_neural_drive_and_png(tmp_path):
    zero = module.FlyBodySide(seed=1701, width=160, height=120)
    driven = module.FlyBodySide(seed=1701, width=160, height=120)
    try:
        assert zero.names == driven.names
        assert len(driven.names) == 59
        assert np.allclose(zero.env.physics.data.qpos, driven.env.physics.data.qpos, atol=1e-9, rtol=0)
        command = module.neural_fly_command([
            {'body_id':101, 'spikes':24, 'superclass':'vnc_motor', 'soma_neuromere':'T1', 'root_side':'L'},
            {'body_id':102, 'spikes':10, 'superclass':'vnc_motor', 'soma_neuromere':'T2', 'root_side':'R'},
        ])
        driven.set_command(command)
        dt = driven.control_timestep
        for _ in range(4):
            zero.advance(50 * dt)
            driven.advance(50 * dt)
        assert zero.sim_steps == driven.sim_steps == 64
        assert zero.phase == 0
        assert driven.sim_time_seconds == pytest.approx(64 * dt, abs=1e-10)
        assert driven.dropped_time_seconds == pytest.approx(136 * dt, abs=1e-10)
        assert driven.resets == 0
        assert driven.phase == pytest.approx((2 * math.pi * 6 * command.drive * 64 * dt) % (2 * math.pi), abs=1e-10)
        q0 = np.asarray(zero.env.physics.data.qpos).copy()
        q1 = np.asarray(driven.env.physics.data.qpos).copy()
        assert np.isfinite(q0).all() and np.isfinite(q1).all()
        # No norm combining translational/rotational coordinates is reported.
        assert not np.allclose(q0, q1, atol=1e-8, rtol=1e-8)
        pixels = driven.render()
        assert pixels.shape == (120, 160, 3)
        assert pixels.dtype == np.uint8
        assert float(pixels.std()) > 1.0
        evidence = Path(os.environ.get('FLYBODY_EVIDENCE_DIR', str(tmp_path)))
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence/'publisher-physics.png').write_bytes(module.encode_rgb_png(pixels))
        (evidence/'publisher-physics.json').write_text(json.dumps({
            'kind':'real-flybody-engineering-input-integration-test',
            'not_biological_input_evidence':True,
            'not_production_live_evidence':True,
            'publisher':module.PUBLISHER_ID,
            'upstream_commit':module.FLYBODY_COMMIT,
            'seed':1701,
            'backend':os.environ['MUJOCO_GL'],
            'action_dimension':len(driven.names),
            'physical_states_differ':True,
            'physics':driven.physical_state(),
        }, indent=2, allow_nan=False)+'\n')
    finally:
        del zero, driven
        gc.collect()
