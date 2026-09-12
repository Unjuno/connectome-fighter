from __future__ import annotations

from pathlib import Path

from connectome_fighter.malecns_worker_policy import _load_body_annotations


def test_load_body_annotations_from_canonical_completeness(tmp_path: Path):
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "completeness.csv").write_text(
        "bodyId,superclass,class,subclass,type,somaNeuromere,rootSide,somaSide\n"
        "10,descending,central,DN,DNfoo,ANm,L,L\n"
        "11,motor,peripheral,MN,,T1,R,\n",
        encoding="utf-8",
    )
    rows = _load_body_annotations(adapter)
    assert rows[10] == {
        "superclass": "descending",
        "class": "central",
        "subclass": "DN",
        "type": "DNfoo",
        "soma_neuromere": "ANm",
        "root_side": "L",
        "soma_side": "L",
    }
    assert rows[11]["superclass"] == "motor"
    assert rows[11]["soma_neuromere"] == "T1"
    assert "type" not in rows[11]
