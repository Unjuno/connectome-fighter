#!/usr/bin/env bash
set -euo pipefail

P1="GARNET"
P2="ZEN"
MANIFEST_URL="https://github.com/Unjuno/connectome-fighter/releases/download/arena-inference-latest/manifest.json"
LISTEN=8080
SESSION_ID=""
UV_VERSION="0.12.12"

while (($#)); do
  case "$1" in
    --p1) P1="$2"; shift 2 ;;
    --p2) P2="$2"; shift 2 ;;
    --manifest-url) MANIFEST_URL="$2"; shift 2 ;;
    --listen) LISTEN="$2"; shift 2 ;;
    --session-id) SESSION_ID="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

case "$P1" in GARNET|ZEN|LUD|NEZ) ;; *) echo "invalid P1" >&2; exit 2;; esac
case "$P2" in GARNET|ZEN|LUD|NEZ) ;; *) echo "invalid P2" >&2; exit 2;; esac
if [[ "$P1" == "$P2" ]]; then echo "fighters must differ" >&2; exit 2; fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${CONNECTOME_SESSION_ROOT:-/tmp/connectome-arena-session}"
mkdir -p "$WORK/bin"

if [[ -z "$SESSION_ID" ]]; then
  SESSION_ID="arena-$(date +%s)-$RANDOM"
fi

if ! command -v curl >/dev/null 2>&1 || ! command -v java >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openjdk-21-jre-headless ca-certificates curl
  else
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openjdk-21-jre-headless ca-certificates curl
  fi
fi

UV="$WORK/bin/uv"
if [[ ! -x "$UV" ]]; then
  export UV_INSTALL_DIR="$WORK/bin"
  export UV_NO_MODIFY_PATH=1
  curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | sh
fi
"$UV" --version

export UV_PYTHON_INSTALL_DIR="$WORK/uv-python"
export UV_CACHE_DIR="$WORK/uv-cache"
"$UV" python install 3.10 3.11

REF_ENV="$WORK/ref-py310"
BRIDGE_ENV="$WORK/bridge-py311"
"$UV" venv --python 3.10 "$REF_ENV"
"$UV" pip install --python "$REF_ENV/bin/python" \
  'numpy==1.24.0' 'pandas==1.5.3' 'pyarrow==10.0.1' 'joblib==1.2.0' 'Cython==0.29.36' 'brian2==2.5.1'
"$UV" venv --python 3.11 "$BRIDGE_ENV"
"$UV" pip install --python "$BRIDGE_ENV/bin/python" \
  'numpy==2.3.5' 'pandas==2.3.3' 'pyarrow==23.0.1' 'pyftg==2.3'

SNAPSHOT_DIR="$WORK/snapshot"
mkdir -p "$SNAPSHOT_DIR"
curl -fL --retry 4 --retry-all-errors -o "$SNAPSHOT_DIR/manifest.json" "$MANIFEST_URL"
BASE_URL="${MANIFEST_URL%/manifest.json}"

"$BRIDGE_ENV/bin/python" - "$SNAPSHOT_DIR/manifest.json" "$BASE_URL" "$SNAPSHOT_DIR" <<'PY'
import hashlib, json, pathlib, subprocess, sys
manifest_path, base_url, out_dir = sys.argv[1:]
m = json.load(open(manifest_path, encoding='utf-8'))
assert m.get('kind') == 'connectome-fighter-arena-inference-snapshot'
assert m.get('canonical_model') == 'MaleCNS v1.0 + pinned Shiu LIF'
assert m.get('mutability') == 'read-only-inference'
assert m.get('research_metadata_embedded') is False
root = pathlib.Path(out_dir)
verified = []
for character, entry in (m.get('characters') or {}).items():
    name = str(entry['state_file'])
    target = root / name
    subprocess.run(['curl','-fL','--retry','4','--retry-all-errors','-o',str(target),f'{base_url}/{name}'], check=True)
    sha = hashlib.sha256(target.read_bytes()).hexdigest()
    if sha != str(entry['state_sha256']):
        raise RuntimeError(f'{character} state sha256 mismatch')

    meta_name = str(entry.get('runtime_state_meta_file') or '')
    meta_expected_sha = str(entry.get('runtime_state_meta_sha256') or '')
    if not meta_name or not meta_expected_sha:
        raise RuntimeError(f'{character} runtime state metadata missing from inference manifest')
    meta_target = root / meta_name
    subprocess.run(['curl','-fL','--retry','4','--retry-all-errors','-o',str(meta_target),f'{base_url}/{meta_name}'], check=True)
    meta_sha = hashlib.sha256(meta_target.read_bytes()).hexdigest()
    if meta_sha != meta_expected_sha:
        raise RuntimeError(f'{character} runtime state metadata sha256 mismatch')
    meta = json.load(open(meta_target, encoding='utf-8'))
    if meta.get('state_sha256') != sha:
        raise RuntimeError(f'{character} runtime metadata does not bind the downloaded state')
    if meta.get('character') != character:
        raise RuntimeError(f'{character} runtime metadata character mismatch')
    if int(meta.get('generation', -1)) != int(entry.get('generation', -2)):
        raise RuntimeError(f'{character} runtime metadata generation mismatch')
    verified.append(character)
print(json.dumps({'verified_characters': sorted(verified)}))
PY

BASE_ADAPTER="$ROOT/data/malecns-shiu-strict-v1"
CANDIDATES="$ROOT/data/malecns-valence-v1/kc_mbon_valence_candidates.parquet"
P1_ADAPTER=""
P2_ADAPTER=""

materialize_if_available() {
  local character="$1"
  local out="$2"
  local state_file
  state_file="$($BRIDGE_ENV/bin/python - "$SNAPSHOT_DIR/manifest.json" "$character" <<'PY'
import json, sys
m=json.load(open(sys.argv[1],encoding='utf-8'))
e=(m.get('characters') or {}).get(sys.argv[2])
print(e.get('state_file','') if e else '')
PY
)"
  if [[ -z "$state_file" ]]; then
    return 1
  fi
  PYTHONPATH="$ROOT/repo/src" "$BRIDGE_ENV/bin/python" "$ROOT/repo/scripts/materialize_malecns_valence_adapter.py" \
    --base-adapter "$BASE_ADAPTER" \
    --candidates "$CANDIDATES" \
    --state "$SNAPSHOT_DIR/$state_file" \
    --character "$character" \
    --plasticity-config "$ROOT/repo/configs/plasticity_valence_v0.json" \
    --out "$out"
}

if materialize_if_available "$P1" "$WORK/p1-adapter"; then P1_ADAPTER="$WORK/p1-adapter"; fi
if materialize_if_available "$P2" "$WORK/p2-adapter"; then P2_ADAPTER="$WORK/p2-adapter"; fi

CMD=(
  "$BRIDGE_ENV/bin/python" "$ROOT/repo/scripts/run_live_arena_server.py"
  --listen "$LISTEN"
  --session-id "$SESSION_ID"
  --p1 "$P1" --p2 "$P2"
  --reference-python "$REF_ENV/bin/python"
  --reference-model "$ROOT/shiu/model.py"
  --adapter-dir "$BASE_ADAPTER"
  --interface "$ROOT/data/interface.json"
  --game-jar "$ROOT/fightingice/FightingICE.jar"
  --decision-interval 60
  --out "$WORK/live"
)
if [[ -n "$P1_ADAPTER" ]]; then CMD+=(--adapter-dir-p1 "$P1_ADAPTER"); fi
if [[ -n "$P2_ADAPTER" ]]; then CMD+=(--adapter-dir-p2 "$P2_ADAPTER"); fi

export PYTHONPATH="$ROOT/repo/src"
exec "${CMD[@]}"
