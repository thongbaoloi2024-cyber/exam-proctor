# Ghi chú hiệu năng: FPS & Bottleneck (Tuần 7)

> Đo bằng `scripts/benchmark_fps.py` trên máy phát triển hiện tại (CPU-only,
> không GPU) — không có webcam nên đo trên frame synthetic (nền đen) lặp lại,
> tách biệt chi phí TÍNH TOÁN THUẦN TUÝ (model inference + logic signal)
> khỏi chi phí đọc webcam/hiển thị màn hình. Số liệu tuyệt đối phụ thuộc
> phần cứng — chạy lại `python scripts/benchmark_fps.py` trên máy thật (có
> webcam) để có số liệu đại diện hơn.

## 1. Kết quả đo (60 frame, sau 5 frame warmup)

| Thành phần | ms/frame trung bình | % tổng chi phí |
|---|---:|---:|
| `perception.face_detect` (MTCNN) | 28.95 | 67% |
| `perception.object_detect` (YOLOv8, đã throttle 0.4s) | 10.32 | 24% |
| `perception.face_mesh` (MediaPipe FaceLandmarker) | 3.45 | 8% |
| `perception.preprocess` (resize + convert màu) | 0.21 | <1% |
| 7 signal (FacePresence, MultiFace, Eye, Mouth, Object, HeadPose, Identity) | ~0.04 (cộng cả 7) | <1% |
| **Tổng** | **42.98 ms/frame** | **100%** |

**FPS tổng thể đo được: ~25.3 FPS** (vòng lặp liên tục, không tính I/O webcam/hiển thị màn hình — số đo trực tiếp từ tổng thời gian 60 lần gọi `orchestrator.process_frame()`). Ước tính lý thuyết từ tổng chi phí từng bước (1000/42.98) ≈ 23.3 FPS — chênh lệch nhỏ so với FPS đo trực tiếp, hợp lý do overhead ngoài phạm vi đo từng bước (in log console...).

**Chi phí riêng của `FaceEmbedder.extract()` (facenet-pytorch, dùng cho `IdentitySignal`): ~27.6 ms/lần gọi** — KHÔNG nằm trong bảng trên vì chỉ chạy 1 lần mỗi `reverify_interval_sec` (mặc định 30s), không phải mỗi frame. Khấu hao trên toàn bộ frame trong 30s đó, đóng góp trung bình chưa tới 0.05ms/frame — không đáng kể cho FPS tổng thể, nhưng **có thể gây giật 1 frame rõ rệt (~28ms, gần bằng 1 frame ở 30fps) đúng thời điểm chạy** vì hiện tại `IdentitySignal.process()` chạy đồng bộ (blocking) trong vòng lặp chính.

## 2. Phân tích bottleneck

**MTCNN (`face_detect`) là bottleneck rõ rệt nhất — chiếm 67% tổng chi phí**, dù chạy MỖI FRAME không throttle (khác YOLO đã throttle từ Tuần 4). Lý do: MTCNN dò khuôn mặt bằng kim tự tháp đa tỉ lệ (image pyramid — 3 mạng con P-Net/R-Net/O-Net chạy lặp qua nhiều scale ảnh), tốn nhiều phép tính hơn so với cảm giác "nhẹ" thường gán cho MTCNN, đặc biệt trên CPU không có tăng tốc phần cứng.

YOLO (`object_detect`) đứng thứ 2 nhưng đã được giảm tải nhiều nhờ throttle theo thời gian từ Tuần 4 (`object_detect_interval_sec=0.4s`) — nếu chạy KHÔNG throttle (mỗi frame), chi phí thật của 1 lần detect sẽ cao hơn con số 10.32ms/frame nhiều lần (con số này đã là "trung bình khấu hao" qua các frame bị bỏ qua).

MediaPipe FaceLandmarker (`face_mesh`) khá nhẹ (3.45ms) dù chạy mỗi frame không throttle — không cần tối ưu thêm.

**7 signal (tầng logic) hoàn toàn không đáng kể** (<0.05ms tổng cộng cho cả 7) — đúng như thiết kế: mọi signal chỉ làm phép toán hình học đơn giản (khoảng cách Euclidean, tỉ lệ, so sánh ngưỡng) trên dữ liệu ĐÃ được các detector ở Perception Layer trích xuất sẵn, không tự chạy model riêng (trừ `IdentitySignal`, đã tách timing riêng ở mục 1).

## 3. Đề xuất tối ưu (nếu cần)

| Đề xuất | Tác động ước tính | Đánh đổi |
|---|---|---|
| **Throttle MTCNN (`face_detect`) theo thời gian**, cùng cơ chế đã áp dụng cho YOLO (`object_detect_interval_sec`) — VD chỉ chạy mỗi 100-150ms thay vì mỗi frame | Giảm ~2/3 chi phí lớn nhất (67% tổng) → có thể tăng FPS lên ~35-40 | `FacePresenceSignal`/`MultiFaceSignal` sẽ "chậm nhận biết" hơn vài chục ms khi khuôn mặt xuất hiện/biến mất — chấp nhận được vì cả 2 signal đã có debounce 2s, không cần phản ứng tức thời từng frame |
| **Chạy `IdentitySignal` re-verification trong thread/tiến trình riêng** (không block vòng lặp chính) | Loại bỏ hẳn hiện tượng giật ~28ms mỗi 30s | Thêm độ phức tạp đồng bộ hoá (cần đảm bảo state thread-safe) — có thể để lại Tuần 12 (hoàn thiện UI/UX) thay vì làm ngay |
| Giảm độ phân giải xử lý cho riêng MTCNN (giống cách đã thử với YOLO ở Tuần 4, sau đó trả lại 640 vì ảnh hưởng recall) | Giảm thêm chi phí `face_detect` | Rủi ro giảm độ chính xác phát hiện khuôn mặt nhỏ/xa camera — cần đo lại bằng thực nghiệm nếu áp dụng, không nên làm mù quáng như đã rút kinh nghiệm với YOLO |

**Đánh giá tổng thể**: ~25 FPS trên CPU không GPU là mức chấp nhận được cho mục tiêu giám sát hành vi (không cần phản ứng tức thời cấp mili-giây như tracking chuyển động nhanh) — CHƯA có nhu cầu bắt buộc phải tối ưu ngay. Đề xuất throttle MTCNN là hướng có lợi ích/chi phí tốt nhất nếu cần tăng tốc sau này (VD nếu máy thi thực tế yếu hơn máy dev), nhưng để quyết định thực hiện tuỳ theo nhu cầu thực tế phát sinh ở các tuần sau (đặc biệt khi tích hợp UI Tuần 12 cần vòng lặp mượt hơn).

## 4. Cách chạy lại benchmark

```bash
python scripts/benchmark_fps.py --frames 60
```

Nên chạy trên máy thật sẽ dùng để demo/thi (đặc biệt nếu yếu hơn máy dev) để có số liệu đại diện — số liệu ở đây chỉ mang tính tham khảo ban đầu.
