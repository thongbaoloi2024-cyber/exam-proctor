# Kế hoạch Đồ án tốt nghiệp: Hệ thống Giám sát Thi trực tuyến bằng Thị giác máy tính (Self-built CV Proctoring System)

> File này là bản kế hoạch/prompt chi tiết dùng để định hướng toàn bộ quá trình thực hiện đồ án. Có thể dán lại nội dung file này vào đầu các phiên làm việc với AI coding assistant (Claude Code...) để giữ ngữ cảnh nhất quán xuyên suốt dự án.
>
> **Lịch sử thay đổi**: Bản kế hoạch ban đầu (2026-07-14) hướng tới xây "nền tảng thi trực tuyến đa người dùng" (client-server, FastAPI + PostgreSQL + dashboard React), tái sử dụng trực tiếp code detection của dự án gốc. Ngày 2026-07-15, đã **đổi hướng hoàn toàn**: bỏ nền tảng đa người dùng, tập trung 100% vào việc tự xây dựng lại phần thị giác máy tính (CV) để đây thực sự là sản phẩm do sinh viên tự làm, không phải lắp ráp quanh code người khác. Repo cũ (`exam-proctoring-platform`) đã bị xoá. File này thay thế hoàn toàn bản kế hoạch cũ.

## 1. Bối cảnh & nguồn gốc

- **Dự án tham khảo (reference/related work)**: `exam-cheating-detection` (public, MIT license, tác giả AarambhDevHub/AarambhTech, 2025), nằm tại `C:\Users\admin\Downloads\DATT\exam-cheating-detection`.
- Dự án này là một **script giám sát cục bộ đơn lẻ** (single-machine, single-student), dùng OpenCV + MediaPipe + facenet-pytorch (MTCNN) + YOLOv8 để phát hiện: vắng mặt khuôn mặt, nhiều khuôn mặt, vật thể cấm (điện thoại/sách), chuyển động mắt, chuyển động miệng, âm thanh bất thường. Có sinh báo cáo PDF/HTML đơn giản.
- **Vai trò của dự án này trong đồ án mới**: chỉ dùng làm **tài liệu tham khảo / nguồn cảm hứng / đối chứng (baseline) để so sánh** khi đánh giá — **không copy code**. Toàn bộ pipeline sẽ được viết lại từ đầu bằng kiến trúc và thuật toán riêng.
- **Ranh giới liêm chính học thuật** (quan trọng, cần nêu rõ trong luận văn):
  - Việc dùng các thư viện/model pretrained (OpenCV, MediaPipe, facenet-pytorch, YOLOv8) là **bình thường và bắt buộc** trong mọi đồ án CV — không ai tự viết lại thuật toán MTCNN hay huấn luyện lại YOLO từ đầu cho đồ án cử nhân/kỹ sư. Đây không phải là phần "kế thừa" cần trích dẫn như sản phẩm của người khác, mà là công cụ nền (framework) như mọi đồ án CV khác đều dùng.
  - Phần **thực sự cần là "của bạn"**: kiến trúc pipeline, cách trích xuất đặc trưng, cách kết hợp tín hiệu (fusion), thuật toán ra quyết định cảnh báo, và các kỹ thuật mới bổ sung (mục 3).
  - Trong luận văn, mục "Công nghệ liên quan / Related Work" vẫn nên nhắc tới `exam-cheating-detection` như một ví dụ về hướng tiếp cận đơn giản (naive threshold-based) để làm điểm so sánh/đối chứng khi đánh giá kết quả — điều này càng làm nổi bật cải tiến của bạn, không phải điều cần che giấu.

## 2. Mục tiêu đồ án

Xây dựng một **ứng dụng giám sát thi bằng webcam, chạy trên một máy tính** (không cần server/multi-user), trong đó toàn bộ pipeline nhận diện hành vi nghi vấn là do sinh viên tự thiết kế và cài đặt, có:
- Ít nhất 2 kỹ thuật thị giác máy tính **mới, không có trong bản tham khảo** (head pose estimation bằng solvePnP, xác thực danh tính bằng face embedding).
- Một thuật toán **kết hợp đa tín hiệu (sensor fusion) tự thiết kế** để ra quyết định cảnh báo, thay cho lối if/elif đơn giản của bản tham khảo.
- Đánh giá định lượng (Precision/Recall/F1, độ trễ) trên bộ dữ liệu test tự quay, có so sánh với baseline (mô phỏng lại logic đơn giản kiểu bản tham khảo).

**Định hướng**: Sản phẩm CV do sinh viên tự làm (self-built CV product), không phải nghiên cứu thuật toán học sâu mới, cũng không phải chỉ lắp ráp hệ thống quanh code có sẵn.

## 3. Thiết kế kỹ thuật

### 3.1. Kiến trúc pipeline (tự thiết kế)

```
Webcam Frame
    │
    ▼
┌─────────────────────────┐
│  Perception Layer        │  MediaPipe FaceMesh (468 landmarks), MTCNN (multi-face),
│  (trích xuất đặc trưng)  │  YOLOv8-COCO (object: phone/book)
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│  Signal Extractors       │  - Head Pose (solvePnP) → yaw/pitch/roll         [MỚI]
│  (tự thiết kế)           │  - Eye/Mouth state (EAR, mouth openness)
│                          │  - Identity similarity (facenet embedding)       [MỚI]
│                          │  - Object presence, Face count, Audio VAD
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│  Risk Fusion Engine      │  State machine theo cửa sổ thời gian trượt cho mỗi tín hiệu
│  (thuật toán tự thiết kế,│  + trọng số kết hợp thành "điểm nghi vấn" liên tục
│  TRỌNG TÂM đóng góp)     │  + hysteresis chống báo động giả (false positive)     [MỚI]
└─────────────────────────┘
    │
    ▼
Cảnh báo (loại vi phạm + mức độ + thời điểm + ảnh chụp) → Log → Báo cáo PDF/HTML
```

### 3.2. Các kỹ thuật mới so với bản tham khảo

1. **Head Pose Estimation (`cv2.solvePnP`)**: dùng 6 điểm landmark chuẩn (mũi, cằm, khoé mắt, khoé miệng) ánh xạ với mô hình khuôn mặt 3D chuẩn, giải PnP để ra góc yaw/pitch/roll thật — thay thế cách bản tham khảo chỉ so lệch pixel mắt so với mũi (không có chiều sâu, dễ sai khi đầu nghiêng).
2. **Xác thực danh tính xuyên suốt kỳ thi (Identity Verification)**: dùng facenet-pytorch (InceptionResnetV1) trích embedding khuôn mặt lúc bắt đầu thi (enrollment), định kỳ so sánh cosine similarity với khuôn mặt hiện tại trong khung hình → phát hiện **đổi người thi hộ giữa chừng**. Bản tham khảo hoàn toàn không có tính năng này.
3. **Risk Fusion Engine**: bản tham khảo có lỗi thiết kế là chỉ ghi 1 loại vi phạm/frame theo thứ tự ưu tiên if/elif (bỏ sót khi nhiều tín hiệu xảy ra đồng thời). Đồ án thiết kế lại: mỗi tín hiệu có state machine riêng theo cửa sổ thời gian trượt (VD 3-5 giây), tổng hợp thành điểm rủi ro liên tục có trọng số, dùng ngưỡng có hysteresis (2 ngưỡng lên/xuống khác nhau) để tránh dao động liên tục quanh 1 ngưỡng.

### 3.3. Đánh giá định lượng (không cần dataset huấn luyện)
- Tự quay một **bộ test nhỏ** (~20-30 clip ngắn 2-5 phút): kịch bản bình thường, dùng điện thoại, nhìn ra ngoài nhiều lần, nhiều người trong khung hình, nói chuyện/thì thầm, đổi người giữa chừng (nhờ bạn bè quay giúp 1-2 clip).
- Gán nhãn thời điểm vi phạm thật (ground truth) thủ công cho từng clip.
- Chạy pipeline của mình + một baseline (cài lại logic if/elif đơn giản kiểu bản tham khảo) trên cùng bộ test, tính Precision/Recall/F1 và độ trễ phát hiện trung bình.
- Đây là chương "Thực nghiệm & Đánh giá" cốt lõi của luận văn — thể hiện cải tiến bằng số liệu, không chỉ bằng lời.

## 4. Lộ trình thực hiện (6 tháng)

### Tháng 1 — Đề cương & thiết kế
- Viết đề cương chi tiết: đặt vấn đề, mục tiêu, phạm vi (mục 2 ở trên).
- Khảo sát kỹ thuật liên quan: các phương pháp head pose estimation (solvePnP, landmark-based), face verification (FaceNet/ArcFace embedding + cosine similarity), sensor fusion cho hệ thống giám sát (rule-based fusion, weighted scoring). Khảo sát nhanh sản phẩm thương mại (Proctorio, Honorlock, ProctorU) chỉ để nêu bối cảnh ứng dụng, không phải trọng tâm.
- Vẽ sơ đồ kiến trúc pipeline (mục 3.1), sequence diagram luồng xử lý 1 frame, state diagram cho Risk Fusion Engine.
- Thiết kế trước cấu trúc dữ liệu: định dạng violation event, cấu trúc log, cấu trúc bộ test (ground truth labeling format).

### Tháng 2 — Viết lại Perception Layer & Signal Extractors cơ bản
- Cài đặt lại (kiến trúc riêng, không copy) các signal cơ bản: face presence, multi-face, eye state (EAR), mouth state, object detection — dùng lại thư viện nền nhưng tự viết class/luồng xử lý.
- Viết unit test cho từng signal extractor với ảnh/video mẫu tự chuẩn bị.

### Tháng 3 — Head Pose Estimation + Identity Verification
- Cài đặt head pose estimation bằng solvePnP, hiệu chỉnh camera matrix xấp xỉ (hoặc calibrate nếu có thời gian).
- Cài đặt enrollment + identity verification bằng facenet embedding, xử lý edge case (không phát hiện khuôn mặt lúc enrollment, nhiều khuôn mặt lúc verify).

### Tháng 4 — Risk Fusion Engine & Báo cáo
- Thiết kế và cài đặt state machine theo cửa sổ thời gian trượt cho từng tín hiệu.
- Cài đặt tầng tổng hợp điểm rủi ro có trọng số + hysteresis.
- Xây dựng lại module sinh báo cáo (PDF/HTML) đọc dữ liệu từ pipeline mới, sửa các lỗi severity-mapping đã thấy ở bản tham khảo (mục 5 cũ, xem lịch sử git nếu cần).

### Tháng 5 — Kiểm thử & Đánh giá định lượng
- Quay bộ test (~20-30 clip), gán nhãn ground truth.
- Cài đặt baseline (mô phỏng logic if/elif đơn giản) để so sánh.
- Tính Precision/Recall/F1, độ trễ phát hiện; đánh giá ảnh hưởng của hysteresis lên tỉ lệ báo động giả.
- Viết chương "Thực nghiệm & Đánh giá".

### Tháng 6 — Hoàn thiện luận văn & Bảo vệ
- Viết đầy đủ luận văn theo cấu trúc: Mở đầu → Cơ sở lý thuyết → Khảo sát liên quan → Thiết kế hệ thống → Cài đặt → Thực nghiệm & Đánh giá → Kết luận & hướng phát triển.
- Chuẩn bị slide + kịch bản demo trực tiếp (chạy pipeline live, giả lập 2-3 tình huống vi phạm bao gồm cả đổi người).
- Rà soát phần trích dẫn dự án tham khảo trong luận văn (đúng vai trò: related work/baseline, không phải nguồn code).

## 5. Rủi ro & phương án dự phòng

| Rủi ro | Phương án |
|---|---|
| solvePnP cần camera intrinsic matrix chính xác để chuẩn, không có calibration thật | Dùng xấp xỉ camera matrix chuẩn (focal length ước lượng theo độ phân giải) — chấp nhận sai số, ghi rõ giới hạn trong luận văn |
| Facenet embedding nhạy với ánh sáng/góc nghiêng, có thể false reject người thật | Đặt ngưỡng cosine similarity có biên độ (margin), cho phép "cảnh báo nhẹ" thay vì kết luận ngay là đổi người |
| Không đủ thời gian quay bộ test đa dạng | Ưu tiên tối thiểu 3-5 clip/loại vi phạm, đủ để tính số liệu có ý nghĩa thống kê ở mức đồ án |
| Risk Fusion Engine phức tạp, khó tinh chỉnh trọng số | Bắt đầu bằng trọng số thủ công dựa trên mức độ nghiêm trọng (severity), tinh chỉnh bằng thực nghiệm ở Tháng 5, không cần tối ưu bằng ML |
| Hội đồng hỏi "khác gì bản gốc" | Chuẩn bị sẵn bảng so sánh: kiến trúc, thuật toán fusion, 2 kỹ thuật mới, và bảng số liệu Precision/Recall so với baseline (mục 3.3) |

## 6. Ghi chú khi dùng file này với AI coding assistant

Khi bắt đầu một phiên làm việc mới để code phần nào đó của đồ án, dán lại toàn bộ hoặc một phần file này để AI hiểu: đây là sản phẩm CV độc lập một máy (không phải nền tảng multi-user), dự án tham khảo chỉ đóng vai trò baseline/related-work chứ không phải nguồn code, và các kỹ thuật mới bắt buộc phải có (head pose, identity verification, risk fusion engine, đánh giá định lượng).
