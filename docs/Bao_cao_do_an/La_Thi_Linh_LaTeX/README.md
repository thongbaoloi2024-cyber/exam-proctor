# La_Thi_Linh - LaTeX

## Bản rà soát ngày 18/09/2026

Nội dung hiện tại là báo cáo bảy chương về ước lượng thời gian hiện diện từ camera. Xem [bản ghi chỉnh sửa](REVISION_20260918.md) và [đối chiếu tài liệu tham khảo](KIEM_CHUNG_TAI_LIEU.md).

Theo yêu cầu trong đợt chỉnh sửa này, không gọi lệnh biên dịch hoặc kiểm tra bố cục PDF. Môi trường đã phát sinh thay đổi ở `main.pdf` trong lúc sửa nguồn, nhưng bản đó chưa được kiểm tra. Dữ liệu đánh giá là dữ liệu tổng hợp có ghi rõ nguồn gốc. Có thể tái tạo dữ liệu và hình bằng `python make_figures.py`, kiểm tra nguồn bằng `python check_report_sources.py`. Cả hai lệnh đều không tạo PDF.

## Ghi chép chuyển đổi ban đầu

Các số lượng hình, bảng và tài liệu dưới đây mô tả lần chuyển đổi ban đầu, không phải thống kê của bản rà soát hiện tại.

Dự án được chuyển từ `La_Thi_Linh.pdf` theo cấu trúc của form `Nguyen_Huu_Sang.zip`.

- Biên dịch bằng **XeLaTeX** (`xelatex main.tex`, chạy 2-3 lần để cập nhật mục lục/danh mục).
- Nội dung văn bản được tái tạo theo đoạn văn ngữ nghĩa, không giữ các ngắt dòng mềm do PDF.
- Danh sách được ghép đúng từng mục, kể cả mục kéo dài qua nhiều dòng/trang.
- 25 hình được trích từ ảnh gốc trong PDF.
- 13 bảng được giữ dưới dạng clip PDF vector để tránh mất ô, mất dòng hoặc sai căn cột khi chuyển đổi.
- Đã sửa các lỗi chính tả/hình thức rõ ràng như `Hà nội` → `Hà Nội`, `thu nhập dữ liệu` → `thu thập dữ liệu`, các từ bị tách bởi ký tự ngắt dòng ẩn.

## Kiểm tra sau chuyển đổi

- Đã đối chiếu lại toàn bộ tiêu đề chương/mục với mục lục PDF gốc.
- Đã sửa lỗi nhận nhầm các số thập phân như `0.0`, `1.0` thành tiêu đề.
- Đã dựng lại các công thức toán học nhiều dòng thay vì giữ thứ tự dòng rời từ PDF.
- Các bảng nhiều trang được tách thành phần tiếp nối để không bị chồng/cắt khi biên dịch.
- Đã kiểm tra đủ 25 hình, 13 bảng và 21 tài liệu tham khảo.
