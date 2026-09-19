# La_Thi_Linh - LaTeX

## Bản rà soát ngày 19/09/2026

Nội dung hiện tại là báo cáo bảy chương về ước lượng thời gian hiện diện từ camera. Xem [bản ghi chỉnh sửa mới nhất](REVISION_20260919.md) và [đối chiếu tài liệu tham khảo](KIEM_CHUNG_TAI_LIEU.md).

Đã chỉnh văn phong, công thức, thuật ngữ, hình và bảng; biên dịch bằng XeLaTeX và kiểm tra bố cục PDF. Bản nộp nằm tại `output/pdf/Bao_cao_La_Thi_Linh.pdf`; `main.pdf` là bản biên dịch tại thư mục nguồn.

Chương 6 trình bày kết quả thực thi bộ tính khoảng thời gian tham chiếu: 24 kịch bản cố định, 2.000 đầu vào sinh ngẫu nhiên đối chiếu với bộ tính độc lập, 8.000 phép kiểm tra tính bất biến và 2.000 phép kiểm tra tính đơn điệu. Đây là thực nghiệm tính toán trên đầu vào tổng hợp, chưa phải đánh giá hệ thống CCTV trên video thực tế. Các số liệu 12 phiên và 30 ca tổng hợp cũ được giữ nguyên, tính lại chỉ số và ghi rõ nguồn gốc.

Tái tạo dữ liệu, kết quả và hình (cần Python, Matplotlib):

```powershell
python make_figures.py
python check_report_sources.py
xelatex -interaction=nonstopmode -halt-on-error main.tex
xelatex -interaction=nonstopmode -halt-on-error main.tex
```

Chạy XeLaTeX tại thư mục chứa `main.tex` để các tệp mục lục và tham chiếu đồng bộ. `make_figures.py` tạo cả hình PDF vector, nhưng không biên dịch báo cáo. Thông tin đầu vào, phạm vi, hạt giống và mã kiểm tra nằm trong các thư mục `data/interval_evaluation/`, `data/synthetic_evaluation/` và `computational_evaluation/`.

Bản nguồn trước khi sửa được giữ tại `tmp/revision_20260919_before/`. Ghi chép đợt trước vẫn có tại [REVISION_20260918.md](REVISION_20260918.md).

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
