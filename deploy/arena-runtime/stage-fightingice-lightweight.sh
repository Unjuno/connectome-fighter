#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:?usage: stage-fightingice-lightweight.sh SOURCE_DIR OUT_DIR}"
OUT_DIR="${2:?usage: stage-fightingice-lightweight.sh SOURCE_DIR OUT_DIR}"

SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd)"
rm -rf "$OUT_DIR"

PUBLIC_RENDERER="${CONNECTOME_STAGE_PUBLIC_RENDERER:-false}"
if [[ "${TARGET_TAG:-}" == "arena-runtime-latest" ]]; then
  PUBLIC_RENDERER="true"
fi

if [[ "$PUBLIC_RENDERER" == "true" ]]; then
  # The public LIVE needs official FightingICE ScreenData. Preserve the
  # renderer/resource tree and Linux LWJGL natives, but still remove bundled
  # built-in AIs because both fighters are supplied by pyftg.
  cp -a "$SOURCE_DIR" "$OUT_DIR"
  mkdir -p "$OUT_DIR/data/ai"
  find "$OUT_DIR/data/ai" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

  test -s "$OUT_DIR/FightingICE.jar"
  test -d "$OUT_DIR/lib/lwjgl/natives/linux/amd64"
  test -n "$(find "$OUT_DIR/lib/lwjgl/natives/linux/amd64" -type f -print -quit)"
  test -s "$OUT_DIR/data/characters/GARNET/Motion.csv"
  test -s "$OUT_DIR/data/characters/ZEN/Motion.csv"
  test -s "$OUT_DIR/data/characters/LUD/Motion.csv"
  test -s "$OUT_DIR/data/characters/NEZ/Motion.csv"
  echo "staged public headless-capable FightingICE runtime: $OUT_DIR"
  du -sh "$OUT_DIR"
  exit 0
fi

mkdir -p "$OUT_DIR/lib/lwjgl" "$OUT_DIR/data/ai" "$OUT_DIR/data/characters"

# Pyftg mode supplies both agents over gRPC. GameService still enumerates
# ./data/ai unconditionally, so the directory must exist, but no built-in AI
# jars are required. The lightweight diagnostic path avoids LWJGL native render
# payloads and screen/image assets. Keep only Java dependencies and character
# tables.
test -s "$SOURCE_DIR/FightingICE.jar"
cp "$SOURCE_DIR/FightingICE.jar" "$OUT_DIR/FightingICE.jar"

shopt -s nullglob
root_jars=("$SOURCE_DIR"/lib/*.jar)
lwjgl_jars=("$SOURCE_DIR"/lib/lwjgl/*.jar)
if (( ${#root_jars[@]} == 0 || ${#lwjgl_jars[@]} == 0 )); then
  echo "FightingICE dependency jars are missing" >&2
  exit 1
fi
cp "${root_jars[@]}" "$OUT_DIR/lib/"
cp "${lwjgl_jars[@]}" "$OUT_DIR/lib/lwjgl/"
shopt -u nullglob

for character in GARNET ZEN LUD NEZ; do
  src="$SOURCE_DIR/data/characters/$character"
  dst="$OUT_DIR/data/characters/$character"
  mkdir -p "$dst"
  for file in gSetting.txt Motion.csv; do
    test -s "$src/$file"
    cp "$src/$file" "$dst/$file"
  done
done

# The pyftg runtime needs the directory identity, not bundled built-in AIs.
test -d "$OUT_DIR/data/ai"
test -z "$(find "$OUT_DIR/data/ai" -mindepth 1 -print -quit)"

# Fail closed if render-native payloads accidentally re-enter the lightweight
# diagnostic bundle.
if find "$OUT_DIR" -path '*/natives/*' -type f -print -quit | grep -q .; then
  echo "native render libraries must not be staged for lightweight mode" >&2
  exit 1
fi

test -s "$OUT_DIR/FightingICE.jar"
test -s "$OUT_DIR/data/characters/GARNET/Motion.csv"
test -s "$OUT_DIR/data/characters/ZEN/Motion.csv"
test -s "$OUT_DIR/data/characters/LUD/Motion.csv"
test -s "$OUT_DIR/data/characters/NEZ/Motion.csv"

echo "staged lightweight FightingICE diagnostic runtime: $OUT_DIR"
du -sh "$OUT_DIR"
