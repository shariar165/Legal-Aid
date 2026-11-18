#!/usr/bin/env bash
# Deploy the lite backend to Railway from a clean staging folder.
#
#   bash scripts/railway_up.sh [railway up flags...]      # run from backend/, after `railway login`
#
# `railway up` honours .gitignore, which would drop the warmed LLM cache (.cache/llm), and `--no-gitignore` would
# also upload .data (local accounts + data key), runs/ and corpus/raw. So we copy exactly what the server reads.
set -euo pipefail
cd "$(dirname "$0")/.."

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT

cp -r ain demo "$stage/"
mkdir -p "$stage/corpus/processed" "$stage/eval" "$stage/.cache"
cp corpus/*.py corpus/*.yaml corpus/acts.json "$stage/corpus/"
cp corpus/processed/*.jsonl corpus/processed/embeddings.json "$stage/corpus/processed/"
cp eval/results_snapshot.json "$stage/eval/" 2> /dev/null || true
cp eval/last_eval.json "$stage/eval/" 2> /dev/null || true
[[ -d .cache/llm ]] && cp -r .cache/llm "$stage/.cache/"
cp requirements-lite.txt railway.json "$stage/"
cp Dockerfile.lite "$stage/Dockerfile"  # Railway always builds a root Dockerfile; dockerfilePath alone fell back to Railpack
find "$stage" -name __pycache__ -type d -prune -exec rm -rf {} +

echo "staged $(du -sh "$stage" | cut -f1) in $stage"
railway up "$stage" --path-as-root "$@"
