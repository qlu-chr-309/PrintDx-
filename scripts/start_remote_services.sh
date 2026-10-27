#!/usr/bin/env bash
# 在服务器 /mnt/sda2/chr/print-defect-kg 执行：启动 Chroma + KG HTTP
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate

mkdir -p logs
echo "[1/2] Chroma :8000"
nohup chroma run --path kb/chroma_db --host 0.0.0.0 --port 8000 >logs/chroma.log 2>&1 &
echo "[2/2] KG http.server :8001"
nohup python -m http.server 8001 --bind 0.0.0.0 --directory kg >logs/kg_http.log 2>&1 &
echo "done. check: curl -s localhost:8000/api/v2/heartbeat ; curl -s localhost:8001/graph.json | head"
