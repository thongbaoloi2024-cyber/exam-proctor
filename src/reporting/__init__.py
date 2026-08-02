# Module báo cáo PDF/HTML (Tuần 11) — xem docs/DATA_SCHEMAS.md mục 4 cho
# định dạng log đầu vào.
#
# data_loader.py    : đọc violations.jsonl / risk_score_timeline.jsonl /
#                     state_transitions.jsonl / session_meta.json thô.
# aggregator.py     : tổng hợp thống kê + câu "kết luận tự động".
# severity.py       : nguồn DUY NHẤT ánh xạ severity -> màu (đồng bộ với
#                     Tuần 10, tránh lỗi severity map lệch giữa các module).
# labels.py         : nhãn tiếng Việt cho violation_type (chỉ hiển thị).
# charts.py         : 2 biểu đồ matplotlib (risk score theo thời gian, số vi
#                     phạm theo loại), trả về base64 PNG.
# templates/        : template Jinja2 tự thiết kế.
# report_generator.py: ghép tất cả -> report.html + report.pdf.

from .aggregator import ReportSummary, SnapshotEntry, build_report_summary
from .data_loader import SessionReportData, load_session_report_data
from .report_generator import generate_html_report, generate_pdf_report, generate_report

__all__ = [
    "SessionReportData",
    "load_session_report_data",
    "ReportSummary",
    "SnapshotEntry",
    "build_report_summary",
    "generate_html_report",
    "generate_pdf_report",
    "generate_report",
]
