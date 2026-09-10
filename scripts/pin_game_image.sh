#!/usr/bin/env bash
set -euo pipefail
IMAGE="${1:-ghcr.io/teamfightingice/fightingice:latest}"
docker pull "$IMAGE" >/dev/null
DIGEST="$(docker image inspect "$IMAGE" --format '{{index .RepoDigests 0}}')"
if [[ "$DIGEST" != ghcr.io/teamfightingice/fightingice@sha256:* ]]; then
  echo "Could not resolve immutable FightingICE digest" >&2
  exit 1
fi
printf 'FIGHTINGICE_IMAGE=%s\n' "$DIGEST" > .env
printf 'Pinned %s\n' "$DIGEST"
