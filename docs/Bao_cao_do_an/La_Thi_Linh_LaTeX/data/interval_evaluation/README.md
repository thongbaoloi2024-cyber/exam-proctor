# Kịch bản kiểm tra khoảng thời gian

Bộ dữ liệu này được tạo có chủ đích để kiểm tra phép tính tham chiếu, **không phải thực nghiệm CCTV**. Không chạy YOLO, ByteTrack, FaceNet hoặc máy trạng thái của ứng dụng.

- 24 kịch bản cố định, không cần hạt giống ngẫu nhiên.
- 20 kịch bản hợp lệ có đáp án tính trước bằng tay cho hiện diện, điện thoại, mất quan sát, phần vượt và thời gian hiệu lực.
- Bốn kịch bản không hợp lệ phải bị từ chối: khoảng đảo chiều, hạn mức âm, hạn mức có kiểu boolean và cờ điều chỉnh không có kiểu boolean.
- Đơn vị giây, khoảng nửa kín `[start,end)`. Mốc lớn hơn 86400 thuộc ngày kế tiếp.
- Khoảng chồng lấn được hợp nhất. Khoảng mất quan sát được loại khỏi lịch trước khi tính hiện diện và điện thoại.
- Lịch rỗng có `coverage: null`, không được diễn giải thành độ bao phủ 100%.
- Khi tắt điều chỉnh, vẫn ghi phần vượt nhưng thời gian hiệu lực bằng hiện diện.

Chạy từ thư mục báo cáo:

```powershell
python generate_interval_evaluation.py
```

Chương trình gọi bộ tính tham chiếu `interval_arithmetic.py`, tạo `evaluation.json`, `manifest.json`, `generated/interval_results.tex`, `generated/interval_appendix.tex` và hình `Images/sim_timeline.png`/`.svg`/`.pdf`. Không biên dịch LaTeX. Phụ lục F công bố đầu vào và đáp án của cả 24 kịch bản. Tệp manifest lưu mã SHA-256 của chương trình sinh dữ liệu, bộ tính và dữ liệu kết quả.

Dòng thời gian và phân tích hạn mức dùng cùng các khoảng đầu vào: lịch 510 phút, hiện diện 485 phút, điện thoại 45 phút, hạn mức 15 phút, phần vượt 30 phút, hiệu lực 455 phút. Độ bao phủ quan sát là 100%; tỷ lệ hiện diện trên lịch là 95,10%. Phần vượt trên hình được phân bổ theo thứ tự sử dụng điện thoại, không biểu diễn năng suất tại từng thời điểm.

Kết quả đúng trên các kịch bản này không chứng minh bộ tổng hợp trong hệ thống triển khai đã được kiểm thử, và không đo chất lượng nhận biết hoặc độ trễ.
