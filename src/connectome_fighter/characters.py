"""FightingICE character identities and independent brain lineages."""
from __future__ import annotations

# FightingICE 7.1 GameSetting.CHARACTERS.
CHARACTERS: tuple[str, ...] = ("GARNET", "ZEN", "LUD", "NEZ")

# Deterministic initialization seeds. They deliberately differ by character so
# character brains never start as aliases of the same trainable head.
CHARACTER_SEEDS: dict[str, int] = {
    "GARNET": 1103,
    "ZEN": 2207,
    "LUD": 3313,
    "NEZ": 4421,
}


def validate_character(character: str) -> str:
    value = str(character).upper()
    if value not in CHARACTERS:
        raise ValueError(f"Unsupported FightingICE character: {character!r}; expected {CHARACTERS}")
    return value


def lineage_id(character: str) -> str:
    return f"{validate_character(character).lower()}-main"
