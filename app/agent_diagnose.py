# LangGraph 智能体版诊断：命令行入口（复用 services）
"""面试可演示：Agent + Tool Calling + 远程 RAG/KG。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import CHAT_MODEL, CHROMA_HOST, CHROMA_PORT, KG_URL, OLLAMA_BASE_URL
from app.services import ServiceError, check_services, run_agent


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="LangGraph 印刷缺陷诊断智能体")
    parser.add_argument(
        "query",
        nargs="?",
        default="印刷出现糊版、细网点粘连，原因和怎么处理？",
    )
    parser.add_argument("--model", default=CHAT_MODEL)
    parser.add_argument("--defect", default=None, help="可选：显式缺陷类型标签")
    args = parser.parse_args()

    print("框架: LangChain create_agent（底层 LangGraph）")
    print("工具: search_knowledge_base | query_knowledge_graph")
    print(f"模型: {args.model} @ {OLLAMA_BASE_URL}")
    print(f"Chroma: http://{CHROMA_HOST}:{CHROMA_PORT}")
    print(f"KG:     {KG_URL}")
    print(f"查询: {args.query}\n")

    health = check_services()
    if not health["ok"]:
        bad = {k: v for k, v in health["items"].items() if not v.get("ok")}
        raise SystemExit(f"远端服务不可用: {bad}")

    try:
        out = run_agent(args.query, model=args.model, defect_label=args.defect)
    except ServiceError as exc:
        raise SystemExit(f"Agent 失败: {exc}") from exc

    print("===== 工具调用 =====")
    for i, tc in enumerate(out.get("tool_calls") or [], 1):
        print(f"  {i}. {tc.get('name')}({tc.get('args')})")
    if not out.get("tool_calls"):
        print("  （未调用工具）")

    print("\n===== 最终回答 =====")
    print(out["answer"])
    print(f"\n耗时 {out['elapsed_sec']}s | trace → logs/traces.jsonl")


if __name__ == "__main__":
    main()
