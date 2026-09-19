# Thực nghiệm tính toán trên đầu vào tổng hợp

Kết quả được tạo bằng cách **thực thi** `interval_arithmetic.py` và đối chiếu đầu ra với bộ tính độc lập trong `evaluate_interval_arithmetic.py`. Đầu vào được sinh có kiểm soát; không có video, mô hình thị giác máy tính hoặc dữ liệu nhân viên thực tế tham gia thực nghiệm này.

## Thiết kế và phạm vi

- 2.000 trường hợp, hạt giống `20260919`, chia đều thành tám nhóm: hỗn hợp, khoảng chồng lấn, điện thoại chồng lấn, mất quan sát, lịch rỗng, mất quan sát toàn bộ, hạn mức bằng không và tắt điều chỉnh.
- Bộ tính đối chiếu biểu diễn tập giây bằng mặt nạ bit, không gọi các hàm hợp, giao hoặc hiệu của bộ tính được kiểm tra. Mốc thời gian trong bộ ngẫu nhiên là số nguyên giây.
- Đối chiếu thời lượng lịch, mất quan sát, hiện diện, điện thoại, phần vượt, hiệu lực và độ bao phủ.
- Bốn biến đổi trên mỗi đầu vào: đổi thứ tự khoảng, lặp lại khoảng, tịnh tiến 86.400 giây và chia khoảng thành các đoạn kề nhau; tổng cộng 8.000 phép kiểm tra.
- Tăng hạn mức phải không làm giảm thời gian hiệu lực: 2.000 phép kiểm tra.
- Sáu đầu vào sai định dạng phải bị từ chối; một trường hợp riêng kiểm tra mốc thời gian có phần thập phân.

Các phép kiểm tra này không đánh giá YOLO, ByteTrack, FaceNet, máy trạng thái của ứng dụng, độ trễ hoặc thông lượng xử lý video. Bộ ngẫu nhiên cũng không bao quát đầy đủ sai số số thực, lịch múi giờ hoặc các lỗi vận hành.

## Tái chạy

Từ thư mục chứa `main.tex`:

```powershell
python generate_interval_evaluation.py
python evaluate_interval_arithmetic.py
python check_report_sources.py
```

Lệnh đầu tạo bộ kịch bản cố định mà manifest của thực nghiệm dùng để kiểm tra nguồn gốc. Có thể dùng `python make_figures.py` để tái tạo toàn bộ kết quả và hình của báo cáo.

- `evaluation.json`: lưu đầu vào, kết quả kỳ vọng, kết quả thực thi và các phép kiểm tra của từng trường hợp.
- `manifest.json`: lưu thời điểm chạy UTC, môi trường Python/hệ điều hành, hạt giống, phạm vi và SHA-256 của chương trình, bộ tính và dữ liệu.
- `../generated/computational_results.tex`: bảng kết quả được đưa vào Chương 6.

Trong lần chạy phục vụ bản rà soát 19/09/2026, tất cả các phép kiểm tra trên đều đạt. Số đếm chi tiết nằm trong `evaluation.json`; kiểm tra này chỉ chứng minh sự phù hợp với đặc tả trên các đầu vào đã xét.
