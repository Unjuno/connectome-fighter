"""Software-only fixtures, not biological traces or fighting evidence."""
import pytest
from connectome_fighter.combat_curriculum import training_curriculum


def test_rotation_is_not_locked_by_unchanged_generation():
    assert [training_curriculum(n)['opponent'] for n in range(1, 7)] == ['ZEN', 'LUD', 'NEZ'] * 2
    for start in (39, 40, 1496, 1500):
        rows = [training_curriculum(n) for n in range(start, start + 3)]
        assert {row['opponent'] for row in rows} == {'ZEN', 'LUD', 'NEZ'}
        assert all(row['depends_on_accepted_generation'] is False for row in rows)


def test_retries_are_reproducible_and_do_not_mutate_shared_state():
    original = training_curriculum('1496')
    assert original == training_curriculum(1496)
    assert original['protocol'] == 'workflow-attempt-round-robin-v1'
    original['opponent'] = 'changed'
    assert training_curriculum('1496')['opponent'] == 'LUD'


@pytest.mark.parametrize('value', [None, '', '0', 0, -1, '-1', True, False, 1.0, '1.0', '+1', ' 1', '1 ', '01', 'abc'])
def test_invalid_run_number_fails_closed(value):
    with pytest.raises(ValueError, match='GITHUB_RUN_NUMBER'):
        training_curriculum(value)


def test_trainer_uses_run_number_not_candidate_generation():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / 'scripts/combat_training_run.py').read_text()
    assert "curriculum=training_curriculum(os.environ.get('GITHUB_RUN_NUMBER'))" in source
    assert "opponent=curriculum['opponent']" in source
    assert "opponents[generation%3]" not in source
    assert "train_seed=900001+generation*101+attempt_salt" in source
    assert "train_seed_p2=700001+generation*103+attempt_salt*3" in source


@pytest.mark.parametrize('status', ['PASS', 'REJECTED', 'FAIL'])
@pytest.mark.parametrize('has_update', [True, False])
def test_actual_trainer_finalizer_preserves_diagnostics_without_promoting(tmp_path, capsys, status, has_update):
    import ast
    import json
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / 'scripts/combat_training_run.py').read_text()
    tree = ast.parse(source)
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    write = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'write')
    finalizer = next(node.finalbody for node in main.body if isinstance(node, ast.Try) and node.finalbody)
    accepted = status == 'PASS'
    result = {'status': status, 'accepted_update': accepted, 'generation': 40, 'auto_promotion': False}
    update = {'signals': {'positive': 2, 'negative': 1}, 'updates': {'max_abs_multiplier_delta': 0.01}} if has_update else None
    curriculum = training_curriculum(1496)
    namespace = {'Path': Path, 'json': json, 'result': result, 'update': update,
                 'curriculum': curriculum, 'now': lambda: 'software-fixture-time', 'out': tmp_path}
    # Execute the actual production writer/finalizer, not a reimplementation.
    exec(compile(ast.Module(body=[write, *finalizer], type_ignores=[]), '<trainer-finalizer>', 'exec'), namespace)
    saved = json.loads((tmp_path / 'result.json').read_text())
    assert saved == json.loads(capsys.readouterr().out)
    assert saved['status'] == status and saved['accepted_update'] is accepted
    assert saved['generation'] == 40 and saved['auto_promotion'] is False
    assert saved['training_curriculum'] == curriculum
    if has_update:
        assert saved['signal_summary'] == update['signals']
        assert saved['update_summary'] == update['updates']
    else:
        assert 'signal_summary' not in saved and 'update_summary' not in saved
    assert not list(tmp_path.glob('*.npz'))
