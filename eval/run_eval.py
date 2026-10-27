# 固定题集多模式对比评测：none / kb / kb_kg / agent
"""输出 CSV/JSON，供面试说明效果差异。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import ServiceError, check_services, run_pipeline
from config import CHAT_MODEL


def score_answer(answer: str, must_include_any: list[str]) -> float:
    if not answer:
        return 0.0
    hits = sum(1 for k in must_include_any if k and k in answer)
    return round(hits / max(1, len(must_include_any)), 3)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=CHAT_MODEL)
    parser.add_argument(
        "--modes",
        default="none,kb,kb_kg,agent",
        help="comma list: none,kb,kb_kg,agent",
    )
    parser.add_argument("--limit", type=int, default=0, help=">0 时只跑前 N 题")
    args = parser.parse_args()

    health = check_services()
    if not health["ok"]:
        raise SystemExit(f"远端服务不可用: {health}")

    qpath = Path(__file__).with_name("questions.json")
    questions = json.loads(qpath.read_text(encoding="utf-8"))
    if args.limit > 0:
        questions = questions[: args.limit]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]

    rows = []
    for q in questions:
        for mode in modes:
            print(f"RUN {q['id']} mode={mode} ...", flush=True)
            try:
                out = run_pipeline(
                    q["query"],
                    mode=mode,
                    model=args.model,
                    defect_label=q.get("defect_label"),
                )
                answer = out.get("answer") or ""
                err = ""
            except ServiceError as exc:
                answer, err = "", str(exc)
                out = {"tool_calls": [], "elapsed_sec": None}
            sc = score_answer(answer, q.get("must_include_any") or [])
            rows.append(
                {
                    "id": q["id"],
                    "mode": mode,
                    "query": q["query"],
                    "defect_label": q.get("defect_label"),
                    "score": sc,
                    "elapsed_sec": out.get("elapsed_sec"),
                    "tool_calls": json.dumps(out.get("tool_calls") or [], ensure_ascii=False),
                    "answer": answer,
                    "error": err,
                }
            )

    out_dir = Path(__file__).resolve().parents[1] / "eval" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "eval_latest.json"
    csv_path = out_dir / "eval_latest.csv"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # 按 mode 汇总
    print("\n===== 汇总（关键词命中率均值）=====")
    for mode in modes:
        subset = [r for r in rows if r["mode"] == mode and not r["error"]]
        if not subset:
            print(mode, "no success")
            continue
        avg = sum(r["score"] for r in subset) / len(subset)
        print(f"{mode}: avg_score={avg:.3f} n={len(subset)}")
    print(f"\n写入 {json_path}")
    print(f"写入 {csv_path}")


if __name__ == "__main__":
    main()
