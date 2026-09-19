# Dữ liệu tổng hợp phục vụ kiểm tra báo cáo

Bộ `../interval_evaluation/` kiểm tra phép tính trên 24 kịch bản cố định; bộ `../../computational_evaluation/` đánh giá bộ tính với 2.000 đầu vào sinh ngẫu nhiên và bộ tính đối chiếu độc lập. Các bộ có phạm vi khác nhau, không gộp thành số mẫu của một thực nghiệm CCTV. Đợt rà soát ngày 19/09/2026 đã biên dịch và kiểm tra PDF.

**Đây không phải dữ liệu thực nghiệm CCTV.** Không có video được xử lý, mô hình YOLO/ByteTrack/FaceNet được chạy, hoặc người tham gia được quan sát để tạo bộ dữ liệu này. Các phân phối chưa được hiệu chỉnh theo dữ liệu thực địa.

## Tái tạo

Từ thư mục chứa `main.tex`, chạy:

```powershell
python generate_synthetic_evaluation.py
xelatex -interaction=nonstopmode -halt-on-error main.tex
xelatex -interaction=nonstopmode -halt-on-error main.tex
```

Chương trình cần Python và Matplotlib. Hạt giống cố định là `20260917`. Các bảng và biểu đồ được tính từ cùng đối tượng dữ liệu mà chương trình ghi ra `evaluation.json`.

## Tệp và đơn vị

- `evaluation.json`: số đếm nguồn, các bản ghi thời lượng và chỉ số tính được.
- `manifest.json`: giả định, số mẫu, hạt giống, mã SHA-256 và phạm vi sử dụng.
- `../../generated/synthetic_results.tex`: nội dung và bảng của Chương 6.
- `../../generated/synthetic_appendix.tex`: toàn bộ 30 ca ở mức S1 trong Phụ lục E.
- `../../Images/synthetic_*.pdf`: ba biểu đồ vector được báo cáo sử dụng; có bản PNG để xem trước.

Các trường hậu tố `_s` có đơn vị giây. Chỉ số Precision, Recall, F1, FPR, WPAR và coverage là tỉ lệ từ 0 đến 1. `mape_percent` có đơn vị phần trăm. Sai số có dấu bằng ước lượng trừ tham chiếu.

## Các khối dữ liệu độc lập

| Khối | Đơn vị | Quy mô |
|---|---|---|
| `person_counts` | Đối tượng người tại một thời điểm | 10.000 đối tượng tham chiếu |
| `presence_counts` | Người–giây | 36.000 mẫu mỗi mức, cùng 27.000 mẫu dương và 9.000 mẫu âm |
| `phone_counts` | Người–giây và số đếm sự kiện riêng | 3.000 mẫu mỗi điều kiện |
| `phone_sessions` | Phiên tổng hợp | 12 phiên, công bố đầy đủ |
| `shifts` | Ca tổng hợp | 30 ca, mỗi ca có ba mức nhiễu |

Không diễn giải các khối như dữ liệu lấy từ cùng video. Đặc biệt, các sự kiện dùng cho WPAR không có ánh xạ thời gian tới mẫu phân loại người–giây.

S1, S2 và S3 là **mức nhiễu**, không phải tên thuật toán. Các mức dùng chung sai lệch cơ sở nên không phải lần thử độc lập. Bản ghi không bao gồm tọa độ hộp, quỹ đạo hay chuỗi khung hình và không dùng để tính IDF1, HOTA, sai số mốc vào/ra hoặc FPS.

## Quy tắc tính

- Chỉ số tổng hợp phát hiện người được tính từ tổng TP, FP, FN.
- Điều kiện điện thoại chỉ đặt trên bàn không có mẫu dương. Recall và F1 là `null`, không báo một điểm F1 có vẻ tốt trên tập chỉ có mẫu âm.
- WPAR là số sự kiện gán sai người chia số sự kiện được gán. Khi mẫu số bằng 0, giá trị là `null`.
- Thời gian hiệu lực bằng hiện diện trừ phần điện thoại vượt 900 giây. Điện thoại không vượt hiện diện. Hiện diện không vượt thời lượng ca sau khi loại thời gian không quan sát được.
- MAE, MAPE, trung vị, P95 và giá trị lớn nhất được tính từ toàn bộ bản ghi. P95 nội suy tuyến tính tại vị trí `(n-1)*0.95`.
- MAPE chỉ dùng thời lượng tham chiếu dương và có trường `mape_n` công bố mẫu số.

Để xây dựng dữ liệu phản ánh thực tế, cần cung cấp video, nhãn tham chiếu độc lập, kết quả mô hình, cấu hình và thông tin phần cứng. Khi đó có thể ước lượng phân phối sai số thực tế và đánh giá trên tập kiểm tra riêng.
