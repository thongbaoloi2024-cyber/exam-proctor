# Bản cập nhật đề tài 2026

Đề tài: **Hệ thống ước lượng thời gian làm việc của nhân viên dựa trên sự hiện diện trong khu vực làm việc bằng Computer Vision**.

## Điểm cập nhật chính
- Camera CCTV một nguồn, nhiều nhân viên.
- YOLOv8 phát hiện `person` và `cell phone` trong cùng pipeline.
- ByteTrack theo dõi đa đối tượng.
- Polygon ROI gán khu vực làm việc.
- FaceNet dùng như tín hiệu hỗ trợ xác minh danh tính.
- Presence state machine + grace period + backdating interval.
- Phone usage state machine; chỉ trừ phần thời gian vượt allowance.
- Mô hình backend/web chuyển từ Exam/Candidate sang Employee/Camera/WorkArea/Presence.
- Bổ sung quyền riêng tư, Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15.
- Bổ sung phụ lục API, test cases, annotation và checklist nghiệm thu.

## Lưu ý học thuật quan trọng
Các kết quả định lượng ở Chương 6 hiện được đánh dấu **mô phỏng**. Chúng dùng để hoàn thiện cấu trúc đánh giá và kiểm tra logic báo cáo, **không phải kết quả thực nghiệm CCTV thực tế**. Trước bảo vệ, nếu có dữ liệu thật, cần thay các bảng/hình mô phỏng bằng kết quả chạy từ bộ test có ground truth.

## Biên dịch
Sử dụng XeLaTeX:

```bash
xelatex main.tex
xelatex main.tex
```

PDF hiện tại: 108 trang.
