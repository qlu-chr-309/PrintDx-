# 固定流水线诊断：KB + KG 一次检索后交给 LLM（非 Agent）
"""印刷缺陷诊断（本机代码 → 远程模型/向量库/图谱）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import CHAT_MODEL, CHROMA_HOST, CHROMA_PORT, KG_URL, OLLAMA_BASE_URL
from app.services import ServiceError, check_services, run_pipeline


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="印刷缺陷诊断（远程 KG + RAG + LLM）")
    parser.add_argument(
        "query",
        nargs="?",
        default="印刷品出现糊版、细网点粘连，可能是什么原因？怎么处理？",
    )
    parser.add_argument("--model", default=CHAT_MODEL)
    parser.add_argument("--mode", default="kb_kg", choices=["none", "kb", "kb_kg", "agent"])
    args = parser.parse_args()

    print(f"Ollama: {OLLAMA_BASE_URL}")
    print(f"Chroma: http://{CHROMA_HOST}:{CHROMA_PORT}")
    print(f"KG:     {KG_URL}")
    print(f"模式:   {args.mode}")
    print(f"查询: {args.query}\n")

    health = check_services()
    if not health["ok"]:
        bad = {k: v for k, v in health["items"].items() if not v.get("ok")}
        raise SystemExit(f"远端服务不可用: {bad}")

    try:
        out = run_pipeline(args.query, mode=args.mode, model=args.model)
    except ServiceError as exc:
        raise SystemExit(f"诊断失败: {exc}") from exc

    print("=" * 60)
    print(out["answer"])
    print(f"\n耗时 {out['elapsed_sec']}s | tools={out.get('tool_calls')}")


if __name__ == "__main__":
    main()
