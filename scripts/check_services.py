# 一键检查 Ollama / Chroma / KG 是否可达
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import check_services


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    st = check_services()
    print(json.dumps(st, ensure_ascii=False, indent=2))
    raise SystemExit(0 if st["ok"] else 1)


if __name__ == "__main__":
    main()
