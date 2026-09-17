# Ghi nhận rà soát nội dung

Đã chỉnh sửa trên bản thảo đang có, bảo toàn bản trước khi sửa tại `tmp/editorial_backup_20260917/`. Thư mục sao lưu này có cả PDF và các chương trước đợt rà soát.

## Nội dung đã sửa

| Phần | Điều chỉnh chính |
|---|---|
| Chương 1 | Chuẩn hóa mục tiêu, phạm vi, thuật ngữ và nguồn kết quả. Sửa ký hiệu phép giao thời gian điện thoại để tránh cộng trùng. |
| Chương 2 | Chuẩn hóa diễn đạt lý thuyết. Làm rõ điều kiện tính MAPE và quy tắc hợp nhất khoảng thời gian. |
| Chương 3 | Sửa diễn đạt yêu cầu, lỗi chính tả và nguyên tắc xác định ngưỡng nghiệm thu trước tập kiểm tra. |
| Chương 4 | Làm rõ trạng thái SUSPENDED và điều kiện mở/duy trì phiên điện thoại, thống nhất với quy tắc hiện diện. |
| Chương 5 | Phân biệt đặc tả triển khai với bằng chứng hoàn thành. Sửa cấu hình lọc người để giữ các quan sát độ tin cậy thấp cho ByteTrack. Hiệu chỉnh mã giả truy cập đầu ra YOLO. |
| Chương 6 | Thay số liệu nhập tay bằng dữ liệu tổng hợp có nguồn, chương trình sinh và kiểm tra số học. Chuyển những so sánh thuật toán và hiệu năng không có dữ liệu chạy sang phương pháp đánh giá. |
| Chương 7 | Viết lại phần tổng kết theo bài toán hiện tại và phạm vi kết quả được hỗ trợ. |
| Các phần khác | Đồng bộ tóm tắt, mở đầu, thuật ngữ và phụ lục. Thêm phụ lục 30 ca tổng hợp. |

Dấu chấm phẩy trong nội dung đã được loại bỏ. Dấu kết thúc lệnh TikZ ở trang bìa được giữ nguyên để LaTeX hoạt động đúng. Không còn chuỗi HTML `&#x20;` trong nguồn tài liệu.

## Số liệu và giới hạn

Bộ số liệu mới có 12 phiên điện thoại, 30 ca và các số đếm phân loại. Các bảng được tính từ số liệu nguồn và có thể tái tạo bằng `generate_synthetic_evaluation.py`. Không có giá trị được gán thành kết quả thực nghiệm thực địa.

Các sai lệch trong bản trước đã được xử lý:

- Recall và số giây bỏ sót của bảng hiện diện chưa dùng cùng số mẫu dương.
- MAE của 12 phiên điện thoại không có đủ 12 bản ghi công bố để đối chiếu.
- Các chỉ số so sánh bộ theo dõi chưa có quỹ đạo nguồn hoặc kết quả chạy.
- Tổng độ trễ diễn giải là 39 ms không khớp tổng 45 ms của các thành phần thường xuyên.
- Bảng chỉ có điện thoại trên bàn cần được đánh giá như đối chứng âm, không gán Recall và F1 khi không có mẫu sử dụng thực.

Việc chọn phân phối nhiễu hợp lý về mặt số học không chứng minh mức sát với dữ liệu thực tế. Cần bộ dữ liệu thực địa có nguồn để hiệu chỉnh và kiểm chứng nhận định đó.

## Nguồn đã đối chiếu

- [Ultralytics YOLOv8](https://docs.ultralytics.com/models/yolov8/): mô hình và cách trích dẫn tài liệu phần mềm.
- [Ultralytics Tracking](https://docs.ultralytics.com/modes/track/): ngưỡng phát hiện và cấu hình theo dõi.
- [Công báo Chính phủ – Luật 91/2025/QH15](https://congbao.chinhphu.vn/van-ban/luat-so-91-2025-qh15-45578.htm): thông tin văn bản được trích dẫn trong báo cáo.
