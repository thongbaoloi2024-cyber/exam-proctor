# Kịch bản kiểm tra khoảng thời gian

Bộ dữ liệu này được tạo có chủ đích để kiểm tra phép tính tham chiếu, **không phải thực nghiệm CCTV**. Không chạy YOLO, ByteTrack, FaceNet hoặc máy trạng thái của ứng dụng.

- 14 kịch bản cố định, không cần hạt giống ngẫu nhiên.
- 13 kịch bản hợp lệ có đáp án tính trước bằng tay cho hiện diện, điện thoại, mất quan sát, phần vượt và thời gian hiệu lực.
- Một kịch bản chứa khoảng âm phải bị từ chối.
- Đơn vị giây, khoảng nửa kín `[start,end)`. Mốc lớn hơn 86400 thuộc ngày kế tiếp.
- Khoảng chồng lấn được hợp nhất. Khoảng mất quan sát được loại khỏi lịch trước khi tính hiện diện và điện thoại.
- Lịch rỗng có `coverage: null`, không được diễn giải thành độ bao phủ 100%.
- Khi tắt điều chỉnh, vẫn ghi phần vượt nhưng thời gian hiệu lực bằng hiện diện.

Chạy từ thư mục báo cáo:

```powershell
python generate_interval_evaluation.py
```

Chương trình tạo `evaluation.json`, `manifest.json`, `generated/interval_results.tex`, `generated/interval_appendix.tex` và hình `Images/sim_timeline.png`/`.svg`. Không biên dịch LaTeX.

Dòng thời gian và phân tích hạn mức dùng cùng các khoảng đầu vào: hiện diện 485 phút, điện thoại 45 phút, hạn mức 15 phút, phần vượt 30 phút, hiệu lực 455 phút. Phần vượt trên hình được phân bổ theo thứ tự sử dụng điện thoại, không biểu diễn năng suất tại từng thời điểm.

Kết quả đúng trên các kịch bản này không chứng minh bộ tổng hợp trong hệ thống triển khai đã được kiểm thử, và không đo chất lượng nhận biết hoặc độ trễ.
