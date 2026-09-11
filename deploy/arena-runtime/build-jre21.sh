#!/usr/bin/env bash
set -euo pipefail

JAVA_HOME_IN="${1:?usage: build-jre21.sh JAVA_HOME OUT_DIR}"
OUT_DIR="${2:?usage: build-jre21.sh JAVA_HOME OUT_DIR}"

JLINK="$JAVA_HOME_IN/bin/jlink"
test -x "$JLINK"
rm -rf "$OUT_DIR"

# Conservative module set for FightingICE v7.1 + gRPC/LWJGL Java interfaces.
# java.desktop stays present because FightingICE classes reference AWT types,
# even though lightweight mode avoids GraphicManager/font/render initialization.
MODULES="java.base,java.desktop,java.logging,java.management,java.naming,java.security.jgss,java.sql,java.xml,jdk.crypto.ec,jdk.unsupported"

"$JLINK" \
  --add-modules "$MODULES" \
  --strip-debug \
  --no-header-files \
  --no-man-pages \
  --compress=2 \
  --output "$OUT_DIR"

test -x "$OUT_DIR/bin/java"
"$OUT_DIR/bin/java" -version
printf '%s\n' "$MODULES" > "$OUT_DIR/connectome-modules.txt"
echo "built jlink Java 21 runtime: $OUT_DIR"
du -sh "$OUT_DIR"
