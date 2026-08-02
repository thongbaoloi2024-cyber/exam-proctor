"""Sinh báo cáo HTML/PDF cuối phiên giám sát (Tuần 11) — điểm vào chính của
module báo cáo, ghép `data_loader` (đọc log) + `aggregator` (thống kê) +
`charts` (biểu đồ) + template Jinja2 tự thiết kế (`templates/report_template.html`).

Xuất PDF bằng `xhtml2pdf` (thuần Python, không cần binary ngoài như
`wkhtmltopdf`, không cần thư viện hệ thống như `weasyprint` cần GTK/Pango —
đã thử cài `weasyprint` trên Windows và xác nhận lỗi thiếu `libgobject-2.0-0`,
không có sẵn ngoài môi trường Linux).

BUG THẬT ĐÃ PHÁT HIỆN VÀ VÁ (chỉ xảy ra trên Windows): `xhtml2pdf` nạp font
TTF cho `@font-face` bằng cách copy ra 1 file tạm (`tempfile.NamedTemporaryFile`,
`delete=True` mặc định, KHÔNG đóng handle) rồi mở lại chính file đó bằng
`reportlab` để đọc — trên Windows, 1 file đang bị giữ handle độc quyền bởi
`NamedTemporaryFile` không mở lại được bằng handle thứ 2, gây
`PermissionError`/`TTFError` (đã xác nhận bằng cách dựng lại lỗi thủ công và
trace vào đúng dòng `tempfile.NamedTemporaryFile(...)` trong
`xhtml2pdf/files.py`). Vá bằng cách ghi đè `BaseFile.get_named_tmp_file` để
dùng `delete=False` + đóng handle trước khi trả về đường dẫn — file tạm vẫn
được ghi ra đĩa bình thường, chỉ khác là không còn bị khoá độc quyền khi
`reportlab` mở lại. Không áp dụng trên Linux/Mac (không có bug này, tránh
đổi hành vi ở nơi không cần)."""

from __future__ import annotations

import base64
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import matplotlib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.fusion.config import load_session_thresholds, resolve_severity_thresholds

from .aggregator import ReportSummary, build_report_summary
from .charts import render_risk_timeline_chart, render_violation_type_chart
from .data_loader import load_session_report_data
from .labels import violation_type_label_vi
from .severity import severity_color, severity_label_vi

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_TEMPLATE_NAME = "report_template.html"
_ALLOWED_SNAPSHOT_SUFFIXES = {".jpg", ".jpeg", ".png"}
_MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
_BROWSER_EVENT_LABELS_VI = {
    "CONTENT_MONITOR_READY": "Bộ giám sát trang đã sẵn sàng",
    "TAB_HIDDEN": "Ẩn tab bài thi",
    "TAB_VISIBLE": "Quay lại tab bài thi",
    "WINDOW_BLUR": "Rời cửa sổ bài thi",
    "WINDOW_FOCUS": "Quay lại cửa sổ bài thi",
    "TAB_SWITCHED": "Chuyển sang tab khác",
    "NEW_TAB": "Mở tab mới",
    "NAVIGATION_AWAY": "Điều hướng khỏi miền bài thi",
    "FULLSCREEN_EXIT": "Thoát toàn màn hình",
    "FULLSCREEN_ENTER": "Vào toàn màn hình",
    "CLIPBOARD_COPY": "Sao chép nội dung",
    "CLIPBOARD_PASTE": "Dán nội dung",
    "CONTEXT_MENU": "Mở menu chuột phải",
    "CAMERA_MUTED": "Camera bị tắt tiếng/tạm dừng",
    "CAMERA_ENDED": "Camera dừng",
    "MICROPHONE_MUTED": "Microphone bị tắt tiếng/tạm dừng",
    "MICROPHONE_ENDED": "Microphone dừng",
    "SCREEN_SHARE_ENDED": "Chia sẻ màn hình dừng",
    "MONITOR_CLOSED": "Cửa sổ giám sát bị đóng",
    "PERMISSION_MISSING": "Thiếu quyền bắt buộc",
}


def _patch_xhtml2pdf_windows_tempfile_bug() -> None:
    """Xem docstring module — chỉ vá trên Windows, chỉ vá 1 lần."""
    if sys.platform != "win32":
        return
    import xhtml2pdf.files as filesmod

    if getattr(filesmod.BaseFile, "_datt_patched", False):
        return

    def _patched_get_named_tmp_file(self):
        data = self.get_data()
        tmp_file = tempfile.NamedTemporaryFile(suffix=self.suffix, delete=False)
        if data:
            tmp_file.write(data)
        tmp_file.close()
        filesmod.files_tmp.append(tmp_file)
        if self.path is None:
            self.path = tmp_file.name
        return tmp_file

    filesmod.BaseFile.get_named_tmp_file = _patched_get_named_tmp_file
    filesmod.BaseFile._datt_patched = True


def _dejavu_font_path() -> str:
    """Đường dẫn font DejaVu Sans bundle sẵn trong gói `matplotlib` (đã cài
    của đồ án) — hỗ trợ đủ dấu tiếng Việt (đã kiểm chứng qua bảng cmap của
    font), không phụ thuộc font hệ điều hành cụ thể (portable hơn trỏ thẳng
    `C:/Windows/Fonts/...`)."""
    return str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans.ttf").replace("\\", "/")


def _pdf_font_css() -> str:
    font_path = _dejavu_font_path()
    return f"""
<style>
  @font-face {{ font-family: "DejaVuSansReport"; src: url("{font_path}"); }}
  body, table, th, td {{ font-family: "DejaVuSansReport" !important; }}
</style>
"""


def _resolve_snapshot_path(raw_path: str, session_dir: Path) -> Optional[Path]:
    """Resolve snapshots strictly inside ``session_dir/snapshots``.

    JSONL files can be client-controlled in platform mode.  Never honor an
    absolute path or parent directory from a log record.
    """
    candidate_name = Path(raw_path).name
    if not candidate_name or Path(candidate_name).suffix.lower() not in _ALLOWED_SNAPSHOT_SUFFIXES:
        return None
    session_root = session_dir.resolve()
    unresolved_root = session_dir / "snapshots"
    if unresolved_root.is_symlink():
        return None
    snapshot_root = unresolved_root.resolve()
    if snapshot_root.parent != session_root:
        return None
    unresolved = snapshot_root / candidate_name
    try:
        if unresolved.is_symlink():
            return None
        candidate = unresolved.resolve()
        if (
            candidate.parent == snapshot_root
            and candidate.is_file()
            and 0 < candidate.stat().st_size <= _MAX_SNAPSHOT_BYTES
        ):
            return candidate
    except OSError:
        return None
    return None


def _image_data_uri(path: Optional[Path]) -> Optional[str]:
    if path is None or not path.is_file() or path.suffix.lower() not in _ALLOWED_SNAPSHOT_SUFFIXES:
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    suffix = path.suffix.lower().lstrip(".") or "jpeg"
    return f"data:image/{suffix};base64,{encoded}"


def _build_template_context(
    session_dir: Path,
    summary: ReportSummary,
    session_meta: Dict[str, Any],
    violations: List[Dict[str, Any]],
    browser_events: List[Dict[str, Any]],
    risk_timeline_chart: Optional[str],
    violation_type_chart: Optional[str],
) -> Dict[str, Any]:
    snapshots = []
    for snap in summary.snapshots:
        image_path = _resolve_snapshot_path(snap.snapshot_path, session_dir)
        snapshots.append(
            {
                "video_time_sec": snap.video_time_sec,
                "severity": snap.severity,
                "primary_violation": snap.primary_violation,
                "image_data_uri": _image_data_uri(image_path),
            }
        )

    rendered_browser_events = []
    for event in sorted(browser_events, key=lambda item: item.get("video_time_sec", 0)):
        rendered = dict(event)
        image_path = _resolve_snapshot_path(str(event.get("snapshot_path") or ""), session_dir)
        rendered["image_data_uri"] = _image_data_uri(image_path)
        rendered_browser_events.append(rendered)

    return {
        "summary": summary,
        "session_meta": session_meta,
        "violations": sorted(violations, key=lambda v: v["video_time_sec"]),
        "browser_events": rendered_browser_events,
        "snapshots": snapshots,
        "risk_timeline_chart": risk_timeline_chart,
        "violation_type_chart": violation_type_chart,
        "severity_color": severity_color,
        "severity_label": severity_label_vi,
        "violation_type_label": violation_type_label_vi,
        "browser_event_label": lambda name: _BROWSER_EVENT_LABELS_VI.get(name, name),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def generate_html_report(
    session_dir: Union[str, Path],
    fusion_config_path: Union[str, Path] = "config/fusion.yaml",
    output_path: Optional[Union[str, Path]] = None,
) -> str:
    """Đọc log 1 phiên (`session_dir`), tổng hợp thống kê, vẽ biểu đồ, và
    render ra chuỗi HTML hoàn chỉnh (tự chứa — ảnh/biểu đồ nhúng base64).
    Nếu `output_path` được truyền, ghi thêm ra file (dùng xem trực tiếp bằng
    trình duyệt, KHÔNG qua bước xuất PDF)."""
    session_dir = Path(session_dir)
    data = load_session_report_data(session_dir)
    summary = build_report_summary(data)
    thresholds = load_session_thresholds(fusion_config_path)
    # DUY NHAT 1 noi ap dung mac dinh (resolve_severity_thresholds, dung
    # chung voi RiskFusionEngine that o Tuan 10) - tranh bieu do to sai vung
    # severity so voi nhan severity that neu 2 noi tu tinh mac dinh rieng.
    severity_medium_min, severity_high_min = resolve_severity_thresholds(
        thresholds.t_enter, thresholds.severity_medium_min, thresholds.severity_high_min,
    )

    risk_timeline_chart = render_risk_timeline_chart(
        data.risk_timeline, data.violations, thresholds.t_enter, thresholds.t_exit,
        severity_medium_min, severity_high_min,
    )
    violation_type_chart = render_violation_type_chart(summary.count_by_type)

    context = _build_template_context(
        session_dir,
        summary,
        data.session_meta,
        data.violations,
        data.browser_events,
        risk_timeline_chart,
        violation_type_chart,
    )

    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=select_autoescape(["html"]))
    html = env.get_template(_TEMPLATE_NAME).render(**context)

    if output_path is not None:
        Path(output_path).write_text(html, encoding="utf-8")
    return html


def generate_pdf_report(html: str, output_path: Union[str, Path]) -> None:
    """Chuyển chuỗi HTML (thường lấy từ `generate_html_report`) thành PDF.
    Chèn thêm CSS @font-face (font DejaVu Sans nhúng, xem `_pdf_font_css`)
    RIÊNG cho bước xuất PDF — không đụng vào bản HTML gốc (bản HTML xem qua
    trình duyệt dùng font hệ thống bình thường, không cần font nhúng)."""
    _patch_xhtml2pdf_windows_tempfile_bug()
    from xhtml2pdf import pisa

    html_with_font = html.replace("</style>", "</style>" + _pdf_font_css(), 1)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        result = pisa.CreatePDF(html_with_font, dest=f)
    if result.err:
        raise RuntimeError(f"xhtml2pdf bao loi khi xuat PDF ({result.err} loi) - {output_path}")


def generate_report(
    session_dir: Union[str, Path],
    fusion_config_path: Union[str, Path] = "config/fusion.yaml",
    output_dir: Optional[Union[str, Path]] = None,
    formats: Optional[List[str]] = None,
) -> Dict[str, Path]:
    """Generate only the requested formats (defaults to HTML and PDF)."""
    session_dir = Path(session_dir)
    output_dir = Path(output_dir) if output_dir is not None else session_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    requested = list(dict.fromkeys(formats or ["html", "pdf"]))
    unsupported = set(requested) - {"html", "pdf"}
    if unsupported or not requested:
        raise ValueError(f"Dinh dang bao cao khong hop le: {sorted(unsupported)}")

    html_path = output_dir / "report.html"
    pdf_path = output_dir / "report.pdf"

    html = generate_html_report(
        session_dir,
        fusion_config_path,
        output_path=html_path if "html" in requested else None,
    )
    paths: Dict[str, Path] = {}
    if "html" in requested:
        paths["html"] = html_path
    if "pdf" in requested:
        generate_pdf_report(html, pdf_path)
        paths["pdf"] = pdf_path

    return paths
