"""Dung khung thu muc + file nhan cho 1 clip bo test (Tuan 16) - xem
docs/HUONG_DAN_QUAY_TUAN16.md va docs/DATA_SCHEMAS.md muc 5. Chi tao khung
("violations": [] rong, cac truong meta co san) - nguoi dung tu xem lai
video that va dien tiep theo dung dinh dang docs/DATA_SCHEMAS.md muc 5.2,
KHONG tu doan/sinh nhan gia.

Vi du:
    python scripts/scaffold_test_clip.py \\
        --clip-id clip_002_phone --scenario phone_usage \\
        --duration-sec 187 --num-people 1 \\
        --notes "dung dien thoai 2 lan"
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path

_SCENARIOS = ("normal", "phone_usage", "gaze_away", "multi_face", "talking", "impersonation")
_TEST_SET_DIR = Path("data/test_set")
_MANIFEST_PATH = _TEST_SET_DIR / "manifest.csv"
_MANIFEST_HEADER = ["clip_id", "scenario", "duration_sec", "num_people", "has_impersonation", "notes"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clip-id", required=True, help='VD "clip_002_phone"')
    parser.add_argument("--scenario", required=True, choices=_SCENARIOS)
    parser.add_argument("--duration-sec", type=float, required=True)
    parser.add_argument("--num-people", type=int, default=1)
    parser.add_argument("--annotator", default="")
    parser.add_argument("--notes", default="")
    return parser.parse_args()


def _write_labels_skeleton(args: argparse.Namespace) -> Path:
    clip_dir = _TEST_SET_DIR / args.clip_id
    clip_dir.mkdir(parents=True, exist_ok=True)
    labels_path = clip_dir / f"{args.clip_id}.labels.json"

    if labels_path.exists():
        print(f"Da ton tai: {labels_path} - KHONG ghi de, tu sua bang tay neu can.")
        return labels_path

    labels = {
        "clip_id": args.clip_id,
        "video_file": f"{args.clip_id}.mp4",
        "duration_sec": args.duration_sec,
        "scenario": args.scenario,
        "annotator": args.annotator or "TODO: dien ten nguoi gan nhan",
        "annotated_at": date.today().isoformat(),
        "violations": [],
    }
    labels_path.write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Da tao: {labels_path}")
    print(f"  -> Copy file video that vao: {clip_dir / (args.clip_id + '.mp4')}")
    print("  -> Xem lai video, dien mang \"violations\" theo dung dinh dang docs/DATA_SCHEMAS.md muc 5.2")
    return labels_path


def _update_manifest(args: argparse.Namespace) -> None:
    _TEST_SET_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    if _MANIFEST_PATH.exists():
        with open(_MANIFEST_PATH, "r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))

    rows = [r for r in rows if r["clip_id"] != args.clip_id]
    rows.append({
        "clip_id": args.clip_id,
        "scenario": args.scenario,
        "duration_sec": args.duration_sec,
        "num_people": args.num_people,
        "has_impersonation": "true" if args.scenario == "impersonation" else "false",
        "notes": args.notes,
    })
    rows.sort(key=lambda r: r["clip_id"])

    with open(_MANIFEST_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_MANIFEST_HEADER)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Da cap nhat: {_MANIFEST_PATH} ({len(rows)} clip)")


def main() -> None:
    args = _parse_args()
    _write_labels_skeleton(args)
    _update_manifest(args)


if __name__ == "__main__":
    main()
