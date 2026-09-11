#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:?usage: stage-fightingice-lightweight.sh SOURCE_DIR OUT_DIR}"
OUT_DIR="${2:?usage: stage-fightingice-lightweight.sh SOURCE_DIR OUT_DIR}"

SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd)"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR/lib/lwjgl" "$OUT_DIR/data/characters"

# Pyftg mode supplies both agents over gRPC. FightingICE's data/ai directory is
# only needed for built-in/round-robin AI discovery, so it is intentionally not
# shipped. Lightweight mode also does not need LWJGL native render libraries or
# screen/image assets. Keep only Java dependencies and character logic tables.
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

# Fail closed if non-policy runtime payloads accidentally re-enter the bundle.
test ! -d "$OUT_DIR/data/ai"
if find "$OUT_DIR" -path '*/natives/*' -type f -print -quit | grep -q .; then
  echo "native render libraries must not be staged for lightweight mode" >&2
  exit 1
fi

test -s "$OUT_DIR/FightingICE.jar"
test -s "$OUT_DIR/data/characters/GARNET/Motion.csv"
test -s "$OUT_DIR/data/characters/ZEN/Motion.csv"
test -s "$OUT_DIR/data/characters/LUD/Motion.csv"
test -s "$OUT_DIR/data/characters/NEZ/Motion.csv"

echo "staged lightweight FightingICE runtime: $OUT_DIR"
du -sh "$OUT_DIR"
