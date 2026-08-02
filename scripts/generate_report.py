"""Sinh báo cáo HTML + PDF cuối phiên giám sát (Tuần 11) từ log đã ghi ở
`sessions/<session_id>/` (`violations.jsonl`, `risk_score_timeline.jsonl`,
`state_transitions.jsonl`, `session_meta.json` — xem docs/DATA_SCHEMAS.md
mục 4). Đọc lại đúng ngưỡng T_enter/T_exit/severity từ `config/fusion.yaml`
(cùng file Risk Fusion Engine dùng lúc chạy, xem src/fusion/engine.py) để vẽ
vùng severity trên biểu đồ khớp với quyết định thật lúc giám sát.

Chạy: python scripts/generate_report.py sessions/session_20260722_140501
      python scripts/generate_report.py sessions/session_20260722_140501 --config config/fusion.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.reporting.report_generator import generate_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", help="Thư mục phiên giám sát, VD sessions/session_20260722_140501")
    parser.add_argument("--config", default="config/fusion.yaml", help="Đường dẫn config/fusion.yaml")
    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    if not session_dir.is_dir():
        print(f"LOI: khong tim thay thu muc phien '{session_dir}'")
        raise SystemExit(1)

    print(f"Dang sinh bao cao cho phien '{session_dir.name}'...")
    paths = generate_report(session_dir, fusion_config_path=args.config)
    print(f"Da sinh HTML: {paths['html']}")
    print(f"Da sinh PDF : {paths['pdf']}")


if __name__ == "__main__":
    main()
