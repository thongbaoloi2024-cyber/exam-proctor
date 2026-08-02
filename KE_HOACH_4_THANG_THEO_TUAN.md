# Kế hoạch 19 tuần (~4.5 tháng) — Prompt ra lệnh theo từng tuần

> **Lưu ý:** đây là nhật ký/prompt lịch sử theo từng tuần, không phải hướng dẫn
> vận hành source hiện tại. Các endpoint/token/message cũ trong prompt đã được
> thay bằng thiết kế hardening; xem `README.md` và `SECURITY.md`.

> **Cập nhật (sau Tuần 12 cũ)**: đồ án mở rộng từ pipeline CV 1-máy thành 1 platform thương mại hóa được (multi-tenant, dashboard giám thị) — xem `docs/KE_HOACH_PLATFORM.md` cho kiến trúc + lý do. Tuần 12 cũ (UI/UX 1-máy) được thay bằng Tuần 12 mới (backend skeleton); các tuần đánh giá/luận văn cũ (13-16) dời xuống 16-19. File này đã cập nhật theo lộ trình mới.
>
> File này bổ sung cho `KE_HOACH_DO_AN.md` (bản kế hoạch tổng/kiến trúc kỹ thuật). File đó trả lời "làm gì và tại sao", file này trả lời "mỗi tuần ra lệnh gì cho AI coding assistant (Claude Code...) để thực thi".
>
> **Cách dùng**: Mỗi tuần, copy nguyên khối prompt trong mục tương ứng, dán vào đầu phiên làm việc với chatbot. Mỗi prompt đã tự chứa đủ ngữ cảnh cần thiết (không bắt buộc phải dán kèm `KE_HOACH_DO_AN.md`, nhưng nếu chatbot có thể đọc file đó trực tiếp thì càng tốt). Sau khi xong mỗi tuần, đánh dấu ✅ vào checklist bên dưới để theo dõi tiến độ.
>
> **Giả định**: Rút từ 6 tháng xuống 4 tháng (16 tuần) khả thi vì có AI coding assistant hỗ trợ viết code/tài liệu — sinh viên tập trung vào ra quyết định thiết kế, kiểm tra, và viết luận văn; phần code khung do AI hỗ trợ đáng kể.

## Checklist tiến độ

- [x] Tuần 1 — Đề cương & khảo sát kỹ thuật
- [x] Tuần 2 — Kiến trúc pipeline & sơ đồ thiết kế
- [x] Tuần 3 — Setup repo & Perception Layer (face/multi-face)
- [x] Tuần 4 — Signal Extractors cơ bản (eye/mouth/object)
- [x] Tuần 5 — Head Pose Estimation (solvePnP)
- [x] Tuần 6 — Identity Verification (facenet embedding)
- [x] Tuần 7 — Tích hợp signal extractors + interface thống nhất
- [x] Tuần 8 — Demo nội bộ giữa kỳ + viết chương Cơ sở lý thuyết/Khảo sát
- [x] Tuần 9 — Thiết kế & cài đặt Risk Fusion Engine (state machine)
- [x] Tuần 10 — Tầng tổng hợp điểm rủi ro + hysteresis
- [x] Tuần 11 — Module báo cáo PDF/HTML
- [x] ~~Tuần 12 — Hoàn thiện UI/UX + đóng gói app demo được~~ (thay bằng Tuần 12 mới, xem dưới — nội dung cũ dời sang Tuần 13)
- [x] Tuần 12 (mới) — Backend platform skeleton (multi-tenant, auth, WebSocket) — xem `docs/KE_HOACH_PLATFORM.md`
- [x] Tuần 13 — Client↔Backend integration + UI/UX 1-máy (nội dung Tuần 12 cũ, tái sử dụng)
- [x] Tuần 14 — Dashboard giám thị (Jinja2 + WebSocket real-time)
- [x] Tuần 15 — Hoàn thiện multi-tenant + bảo mật cơ bản + demo nhiều phiên đồng thời
- [ ] Tuần 16 — Quay & gán nhãn bộ test (dời từ Tuần 13 cũ)
- [ ] Tuần 17 — Cài baseline + đánh giá định lượng Precision/Recall/F1 (dời từ Tuần 14 cũ)
- [ ] Tuần 18 — Viết chương Thiết kế/Cài đặt/Thực nghiệm + chương "Định hướng thương mại hóa" (dời từ Tuần 15 cũ)
- [ ] Tuần 19 — Hoàn thiện luận văn + slide + demo + rà soát trích dẫn (dời từ Tuần 16 cũ)

---

## THÁNG 1 — Nền tảng thiết kế

### Tuần 1 — Đề cương & khảo sát kỹ thuật

```
Bối cảnh: Tôi đang làm đồ án tốt nghiệp "Hệ thống Giám sát Thi trực tuyến bằng Thị giác máy tính",
tự xây dựng lại toàn bộ pipeline CV (không copy code từ dự án tham khảo exam-cheating-detection
tại C:\Users\admin\Downloads\DATT\exam-cheating-detection — dự án đó chỉ dùng làm baseline/related-work
để so sánh). Đọc file C:\Users\admin\Downloads\DATT\KE_HOACH_DO_AN.md để hiểu đầy đủ kiến trúc,
2 kỹ thuật mới bắt buộc (head pose estimation bằng solvePnP, identity verification bằng facenet
embedding), và Risk Fusion Engine.

Việc cần làm tuần này:
1. Viết đề cương chi tiết (đặt vấn đề, mục tiêu, phạm vi, đối tượng/phạm vi ứng dụng) thành file
   docs/DE_CUONG_CHI_TIET.md trong repo mới của đồ án.
2. Khảo sát kỹ thuật liên quan (không phải khảo sát sản phẩm thương mại) gồm: các phương pháp
   head pose estimation (solvePnP với landmark 3D chuẩn, ưu nhược điểm so với deep learning-based),
   face verification (FaceNet/ArcFace embedding + cosine similarity, ngưỡng quyết định), sensor
   fusion cho hệ thống giám sát (rule-based weighted fusion, hysteresis). Có trích dẫn nguồn tham
   khảo (paper/blog kỹ thuật uy tín).
3. Khảo sát nhanh 2-3 sản phẩm thương mại (Proctorio, Honorlock) chỉ để nêu bối cảnh ứng dụng thực
   tế, 1 đoạn ngắn, không phải trọng tâm.
4. Xuất bản kết quả thành file markdown có cấu trúc rõ ràng, đánh số mục.

Yêu cầu: Nếu cần tra cứu thông tin kỹ thuật/sản phẩm thực tế, hãy tìm kiếm trên web để đảm bảo
chính xác, đừng suy đoán. Sau khi xong, tóm tắt lại cho tôi những gì đã viết trong 5-7 dòng.
```

### Tuần 2 — Kiến trúc pipeline & sơ đồ thiết kế

```
Bối cảnh: Tiếp nối đồ án Giám sát Thi bằng CV (xem KE_HOACH_DO_AN.md và
docs/DE_CUONG_CHI_TIET.md đã viết tuần trước). Tuần này tập trung vào thiết kế trước khi code.

Việc cần làm:
1. Vẽ sơ đồ kiến trúc pipeline chi tiết (Perception Layer → Signal Extractors → Risk Fusion Engine
   → Alert/Report) bằng Mermaid, lưu vào docs/DIAGRAMS.md.
2. Vẽ sequence diagram mô tả luồng xử lý 1 frame từ webcam đến khi ra quyết định cảnh báo.
3. Vẽ state diagram cho Risk Fusion Engine: mỗi tín hiệu có state machine riêng (bình thường →
   nghi vấn → cảnh báo) theo cửa sổ thời gian trượt, và tầng tổng hợp điểm rủi ro có hysteresis
   (2 ngưỡng lên/xuống khác nhau để tránh dao động).
4. Thiết kế cấu trúc dữ liệu: định dạng violation event (JSON schema: type, severity, timestamp,
   confidence, metadata), định dạng log, và định dạng file ground-truth labeling cho bộ test sẽ
   quay ở Tuần 13 (VD: file CSV/JSON ghi start_time-end_time-loại vi phạm cho mỗi clip).
5. Lưu toàn bộ thiết kế cấu trúc dữ liệu vào docs/DATA_SCHEMAS.md.

Không viết code thực thi tuần này — chỉ thiết kế/tài liệu. Tóm tắt ngắn gọn kết quả khi xong.
```

### Tuần 3 — Setup repo & Perception Layer (face/multi-face)

```
Bối cảnh: Đồ án Giám sát Thi bằng CV, đã có thiết kế kiến trúc ở docs/DIAGRAMS.md và
docs/DATA_SCHEMAS.md. Giờ bắt đầu code. KHÔNG copy code từ
C:\Users\admin\Downloads\DATT\exam-cheating-detection — chỉ tham khảo ý tưởng, tự viết lại
kiến trúc class riêng.

Việc cần làm:
1. Tạo repo Python mới (venv, requirements.txt: opencv-python, mediapipe, facenet-pytorch,
   ultralytics, numpy, pyyaml). Cấu trúc thư mục gợi ý:
   src/perception/ (đọc frame, chuẩn hoá), src/signals/ (từng signal extractor),
   src/fusion/ (risk engine, để trống tuần này), src/reporting/, tests/.
2. Cài đặt Perception Layer: class đọc webcam, tiền xử lý frame (resize, convert màu).
3. Viết lại (kiến trúc riêng, interface tự thiết kế theo docs/DATA_SCHEMAS.md) 2 signal extractor
   đầu tiên: FacePresenceSignal (MTCNN, phát hiện có/không có khuôn mặt, dùng thời gian vắng mặt
   liên tục) và MultiFaceSignal (đếm số khuôn mặt độ tin cậy cao).
4. Viết unit test cơ bản cho 2 signal extractor này (dùng ảnh/video mẫu tự chuẩn bị hoặc webcam
   trực tiếp để test thủ công).

Sau khi xong, chạy thử để xác nhận cả 2 signal extractor hoạt động đúng qua webcam, báo cáo kết quả.
```

### Tuần 4 — Signal Extractors cơ bản (eye/mouth/object)

```
Bối cảnh: Tiếp nối Tuần 3, đã có FacePresenceSignal và MultiFaceSignal hoạt động.

Việc cần làm:
1. Cài đặt EyeStateSignal: dùng MediaPipe FaceMesh, tính Eye Aspect Ratio (EAR) theo kiến trúc
   interface đã thống nhất — tự thiết kế công thức/ngưỡng riêng dựa trên hiểu biết về EAR, không
   copy ngưỡng/số liệu từ dự án tham khảo.
2. Cài đặt MouthStateSignal: khoảng cách landmark môi trên/dưới, độ mở miệng theo thời gian.
3. Cài đặt ObjectSignal: YOLOv8 pretrained (COCO), giới hạn lớp cell phone/book, có throttle theo
   FPS để không quá tải CPU/GPU.
4. Viết unit test cho cả 3 signal extractor mới.
5. Viết 1 script demo (main.py tạm thời) chạy đồng thời cả 5 signal extractor qua webcam, in log
   ra console khi tín hiệu vượt ngưỡng tạm thời (chưa có Risk Fusion Engine, chỉ để xác nhận từng
   signal hoạt động).

Chạy thử qua webcam thực tế, xác nhận cả 5 signal phản ứng đúng khi tôi thử nghiệm (che mặt, đưa
điện thoại vào khung hình, mở miệng nói...). Báo cáo lỗi/vấn đề nếu có.
```

---

## THÁNG 2 — Kỹ thuật CV mới (điểm nhấn "tự làm")

### Tuần 5 — Head Pose Estimation (solvePnP)

```
Bối cảnh: Đồ án Giám sát Thi bằng CV, đã có 5 signal extractor cơ bản chạy được qua webcam.
Tuần này cài đặt kỹ thuật mới đầu tiên: Head Pose Estimation — đây là điểm khác biệt so với dự án
tham khảo (dự án đó chỉ so lệch pixel mắt-mũi thô, không có góc quay đầu thật).

Việc cần làm:
1. Cài đặt HeadPoseSignal dùng cv2.solvePnP: chọn 6 điểm landmark chuẩn từ MediaPipe FaceMesh
   (đỉnh mũi, cằm, 2 khoé mắt ngoài, 2 khoé miệng), ánh xạ với mô hình khuôn mặt 3D chuẩn (toạ độ
   3D xấp xỉ theo tài liệu tham khảo chuẩn, không cần đo thật), ước lượng camera matrix theo độ
   phân giải webcam (focal length xấp xỉ = độ rộng ảnh).
2. Giải PnP ra rotation vector → chuyển thành góc yaw/pitch/roll (độ).
3. Định nghĩa ngưỡng "nhìn ra ngoài màn hình" theo góc yaw/pitch (không phải theo pixel như bản
   tham khảo) — tự chọn ngưỡng ban đầu hợp lý (VD yaw > 20 độ), sẽ tinh chỉnh bằng thực nghiệm sau.
4. Vẽ trực quan lên khung hình debug: trục 3D (x/y/z) gắn lên mũi để kiểm chứng bằng mắt góc quay
   có đúng không.
5. Viết ghi chú vào docs/ giải thích công thức/cách chọn landmark, camera matrix xấp xỉ, và giới
   hạn của phương pháp (không calibrate camera thật) — để đưa vào luận văn phần Cài đặt.

Test qua webcam: quay đầu sang trái/phải/lên/xuống, xác nhận góc hiển thị hợp lý và trực quan debug
đúng hướng. Báo cáo kết quả + hạn chế quan sát được.
```

### Tuần 6 — Identity Verification (facenet embedding)

```
Bối cảnh: Đồ án Giám sát Thi bằng CV. Tuần này cài đặt kỹ thuật mới thứ 2: xác thực danh tính
xuyên suốt kỳ thi — tính năng hoàn toàn không có trong dự án tham khảo, dùng để phát hiện đổi
người thi hộ giữa chừng.

Việc cần làm:
1. Cài đặt IdentitySignal dùng facenet-pytorch (InceptionResnetV1 pretrained, vggface2), trích
   embedding 512 chiều từ khuôn mặt.
2. Cơ chế Enrollment: lúc bắt đầu phiên giám sát, chụp và lưu embedding "khuôn mặt tham chiếu"
   (có thể chụp trung bình 3-5 frame đầu để ổn định hơn).
3. Cơ chế Re-verification định kỳ (VD mỗi 30 giây hoặc mỗi N frame): trích embedding khuôn mặt
   hiện tại, tính cosine similarity với embedding tham chiếu, nếu dưới ngưỡng → gắn cờ
   IDENTITY_MISMATCH.
4. Xử lý edge case: không phát hiện khuôn mặt lúc enrollment (yêu cầu thử lại), nhiều khuôn mặt
   lúc verify (chọn khuôn mặt lớn nhất/gần camera nhất), ánh sáng thay đổi (cân nhắc ngưỡng có
   biên độ, tránh false positive quá nhạy).
5. Viết ghi chú kỹ thuật (ngưỡng cosine similarity chọn thế nào, giới hạn của phương pháp khi
   ánh sáng/góc nghiêng thay đổi mạnh) để dùng cho luận văn.

Test: enrollment bằng khuôn mặt tôi, sau đó thử để người khác (hoặc ảnh người khác) vào khung hình
giữa chừng, xác nhận hệ thống gắn cờ đúng. Báo cáo tỉ lệ false positive quan sát được khi tôi tự
thay đổi ánh sáng/góc nghiêng nhẹ (không đổi người).
```

### Tuần 7 — Tích hợp signal extractors + interface thống nhất

```
Bối cảnh: Đồ án Giám sát Thi bằng CV. Hiện có 7 signal extractor riêng lẻ (face presence,
multi-face, eye state, mouth state, object, head pose, identity) nhưng có thể mỗi cái interface
hơi khác nhau do viết ở các tuần khác nhau.

Việc cần làm:
1. Rà soát và chuẩn hoá interface chung cho mọi SignalExtractor (VD: abstract base class với
   method process(frame) -> SignalResult, trong đó SignalResult có {signal_name, value, confidence,
   timestamp}) — để tầng Risk Fusion Engine ở Tuần 9 có thể xử lý đồng nhất mọi tín hiệu.
2. Refactor lại 7 signal extractor đã viết theo interface chuẩn này.
3. Viết 1 "PipelineOrchestrator" chạy tất cả signal extractor mỗi frame, thu thập kết quả thành 1
   danh sách SignalResult, log ra console/file tạm thời để kiểm tra (chưa có fusion logic thật).
4. Đo hiệu năng: FPS đạt được khi chạy đủ 7 signal cùng lúc trên máy hiện tại, ghi nhận signal nào
   tốn thời gian xử lý nhiều nhất (để cân nhắc throttle riêng ở các tuần sau nếu cần).
5. Viết test tích hợp (integration test) chạy toàn bộ pipeline trên 1 đoạn video mẫu ngắn.

Báo cáo FPS đo được và signal nào là bottleneck (nếu có), đề xuất hướng tối ưu nếu cần (throttle
theo interval riêng, giảm độ phân giải xử lý...).
```

### Tuần 8 — Demo nội bộ giữa kỳ + viết chương Cơ sở lý thuyết/Khảo sát

```
Bối cảnh: Đồ án Giám sát Thi bằng CV, đã qua nửa chặng đường kỹ thuật (7 signal extractor + interface
thống nhất). Tuần này vừa kiểm tra chất lượng vừa viết luận văn song song (để không dồn việc viết
vào cuối).

Việc cần làm:
1. Chạy demo trực tiếp toàn bộ pipeline hiện tại qua webcam trong 5-10 phút, tôi (người dùng) sẽ
   thử nhiều kịch bản (nhìn ra ngoài, dùng điện thoại, nhiều người, đổi người). Ghi lại log/console
   output để rà soát signal nào hoạt động tốt/chưa tốt.
2. Liệt kê các vấn đề/bug phát hiện được trong buổi demo, sửa các lỗi ưu tiên cao (crash, signal
   không phản ứng) — lỗi nhỏ về độ chính xác có thể để lại tinh chỉnh ở Tháng 3-4.
3. Viết chương "Cơ sở lý thuyết" của luận văn: giải thích các khái niệm nền tảng đã dùng (MTCNN,
   MediaPipe FaceMesh & EAR, YOLOv8, PnP-based head pose estimation, face embedding & cosine
   similarity) — dựa trên hiểu biết thực tế đã cài đặt, không chỉ chép định nghĩa sách vở.
4. Viết chương "Khảo sát hệ thống liên quan" hoàn chỉnh dựa trên docs/DE_CUONG_CHI_TIET.md (Tuần 1),
   mở rộng thêm nếu cần.
5. Gộp 2 chương trên vào file docs/LUAN_VAN_CHUONG_2_3.md (đánh số chương tạm, sẽ sắp xếp lại ở
   Tuần 16).

Báo cáo danh sách bug đã sửa và bug còn tồn đọng (nếu có) để tôi biết ưu tiên gì ở tháng sau.
```

---

## THÁNG 3 — Thuật toán ra quyết định & sản phẩm hoàn chỉnh

### Tuần 9 — Thiết kế & cài đặt Risk Fusion Engine (state machine)

```
Bối cảnh: Đồ án Giám sát Thi bằng CV. Đây là phần thuật toán TRỌNG TÂM chứng minh "tự thiết kế",
khác biệt lớn nhất so với dự án tham khảo (dự án đó chỉ ghi 1 loại vi phạm/frame theo if/elif ưu
tiên, bỏ sót khi nhiều tín hiệu xảy ra đồng thời).

Việc cần làm:
1. Cài đặt state machine riêng cho mỗi loại tín hiệu (theo thiết kế ở docs/DIAGRAMS.md Tuần 2):
   mỗi tín hiệu có trạng thái NORMAL → SUSPICIOUS → ALERT dựa trên số lần vượt ngưỡng trong 1 cửa
   sổ thời gian trượt (VD: sliding window 3-5 giây, đếm % frame vượt ngưỡng trong window).
2. Đảm bảo state machine chạy độc lập cho từng tín hiệu (không còn if/elif loại trừ lẫn nhau như
   bản tham khảo) — nhiều tín hiệu có thể ở trạng thái ALERT cùng lúc.
3. Viết unit test cho state machine: giả lập chuỗi input tín hiệu theo thời gian, xác nhận chuyển
   trạng thái đúng (bao gồm cả trường hợp tín hiệu dao động lên xuống quanh ngưỡng).
4. Log lại lịch sử chuyển trạng thái của mỗi tín hiệu ra file, phục vụ debug và minh hoạ cho luận
   văn (biểu đồ trạng thái theo thời gian).

Báo cáo: chạy thử qua webcam 2-3 phút với hành vi hỗn hợp (vừa nhìn ra ngoài vừa nói chuyện), xác
nhận nhiều state machine cùng lên ALERT đồng thời đúng như thiết kế.
```

### Tuần 10 — Tầng tổng hợp điểm rủi ro + hysteresis

```
Bối cảnh: Đồ án Giám sát Thi bằng CV, đã có state machine riêng cho từng tín hiệu ở Tuần 9. Giờ
cần tầng tổng hợp cuối cùng ra quyết định cảnh báo thống nhất.

Việc cần làm:
1. Thiết kế công thức tính "điểm rủi ro tổng hợp" (risk score) tại mỗi thời điểm: tổng có trọng số
   của trạng thái các state machine (VD: NORMAL=0, SUSPICIOUS=1, ALERT=2, nhân với trọng số mức độ
   nghiêm trọng riêng từng loại — identity mismatch và object detected nên có trọng số cao hơn eye
   movement).
2. Cài đặt hysteresis: 2 ngưỡng khác nhau — ngưỡng cao để CHUYỂN sang trạng thái cảnh báo, ngưỡng
   thấp hơn để THOÁT khỏi trạng thái cảnh báo — tránh dao động liên tục khi risk score dao động
   quanh 1 ngưỡng duy nhất.
3. Khi risk score vượt ngưỡng cảnh báo, sinh ra 1 violation event đầy đủ (theo schema đã thiết kế ở
   docs/DATA_SCHEMAS.md): loại vi phạm chính (tín hiệu có trọng số cao nhất đang ALERT), các tín
   hiệu phụ đi kèm, risk score, thời điểm, chụp ảnh khung hình.
4. Cho phép cấu hình trọng số qua file YAML để dễ tinh chỉnh sau này (không hardcode).
5. Viết test end-to-end: đưa vào 1 chuỗi tín hiệu giả lập theo thời gian, xác nhận violation event
   sinh ra đúng thời điểm và đúng nội dung.

Báo cáo bộ trọng số ban đầu bạn chọn và lý do (dựa trên mức độ nghiêm trọng theo nhận định chủ
quan ban đầu — sẽ tinh chỉnh bằng số liệu thực nghiệm ở Tuần 14).
```

### Tuần 11 — Module báo cáo PDF/HTML

```
Bối cảnh: Đồ án Giám sát Thi bằng CV, pipeline đã sinh ra violation event đầy đủ. Tuần này xây
module báo cáo cho người dùng cuối (giáo viên/người giám sát xem lại sau khi thi).

Việc cần làm:
1. Cài đặt module đọc toàn bộ violation event của 1 phiên giám sát (từ file log/JSON), tổng hợp
   thống kê: số lượng vi phạm theo loại, biểu đồ risk score theo thời gian (timeline), danh sách
   ảnh chụp kèm mốc thời gian.
2. Sinh báo cáo HTML (dùng Jinja2 template tự thiết kế, không copy template từ dự án tham khảo),
   sau đó xuất PDF (pdfkit/wkhtmltopdf hoặc weasyprint nếu muốn tránh phụ thuộc binary ngoài).
3. Đảm bảo mapping severity/màu sắc hiển thị nhất quán với trọng số đã định nghĩa ở Tuần 10 (đây là
   1 lỗi đã ghi nhận ở dự án tham khảo — severity map không khớp giữa các module — cần tránh lặp lại).
4. Thêm phần tóm tắt "kết luận tự động" đơn giản ở đầu báo cáo (VD: "Phát hiện X vi phạm mức cao,
   Y vi phạm mức trung bình trong Z phút thi") để báo cáo dễ đọc nhanh.

Chạy thử: dùng log từ 1 phiên demo thực tế (có thể lấy từ buổi demo Tuần 8 hoặc chạy demo mới),
sinh ra 1 file PDF mẫu, cho tôi xem để duyệt giao diện/nội dung.
```

### ~~Tuần 12 (cũ) — Hoàn thiện UI/UX + đóng gói app demo được~~

> **Thay thế bởi Tuần 12 (mới) ngay dưới đây** — nội dung UI/UX 1-máy này KHÔNG bị bỏ, mà dời sang Tuần 13 (Client↔Backend integration), sau khi có backend để nối vào. Giữ nguyên toàn bộ quyết định thiết kế cũ (cửa sổ OpenCV, không PyQt, 1 file config.yaml — xem `docs/KE_HOACH_CHI_TIET_TUAN12.md`).

```
Bối cảnh: Đồ án Giám sát Thi bằng CV. Toàn bộ pipeline kỹ thuật đã hoàn chỉnh (perception, 7
signal, risk fusion engine, báo cáo). Tuần này hoàn thiện trải nghiệm sử dụng để có "sản phẩm"
trình diễn được, không chỉ là script chạy tay.

Việc cần làm:
1. Xây màn hình chính đơn giản (có thể vẫn dùng cửa sổ OpenCV hoặc nâng cấp lên giao diện nhẹ như
   PyQt/Tkinter nếu còn thời gian): hiển thị webcam feed, overlay trạng thái các tín hiệu (icon/màu
   theo state machine), risk score hiện tại, nút Bắt đầu/Kết thúc phiên giám sát.
2. Thêm màn hình/bước "Enrollment" rõ ràng lúc bắt đầu (hướng dẫn người dùng nhìn thẳng camera vài
   giây để chụp ảnh tham chiếu cho Identity Verification).
3. Khi kết thúc phiên, tự động gọi module báo cáo Tuần 11 và mở file PDF/HTML kết quả.
4. Đóng gói cấu hình qua 1 file config.yaml duy nhất (ngưỡng, trọng số, đường dẫn output) — tránh
   lỗi đường dẫn tương đối cứng đã thấy ở dự án tham khảo.
5. Viết README hướng dẫn cài đặt và chạy thử từ đầu (dành cho việc demo trước hội đồng).

Chạy thử toàn bộ luồng từ đầu đến cuối (mở app → enrollment → giám sát vài phút → kết thúc → xem
báo cáo) như một buổi demo thật, báo cáo vấn đề UX nếu có.
```

---

## THÁNG 3.5 — Platform (multi-tenant, cloud, dashboard giám thị)

> Mới, xem `docs/KE_HOACH_PLATFORM.md` cho kiến trúc + lý do đầy đủ. Nguyên tắc xuyên suốt: `src/perception/`, `src/signals/`, `src/fusion/`, `src/reporting/` KHÔNG đổi — lớp platform chỉ bọc thêm bên ngoài.

### Tuần 12 (mới) — Backend platform skeleton ✅ Đã xong

```
Đã hoàn thành: backend/ (FastAPI) với models.py/db.py/auth.py (Organization/User/Exam/ExamSession,
JWT cho admin/proctor + session token riêng cho thí sinh), routers/{auth,exams,sessions,ws}.py
(đăng ký/đăng nhập, tạo/liệt kê Exam theo org, join bằng join_code không cần tài khoản, 2 kênh
WebSocket client/dashboard, tải báo cáo qua src/reporting/generate_report() không đổi),
session_materializer.py (dựng thư mục sessions/<id>/ đúng shape cũ), docker-compose.yml +
Dockerfile.backend. 10 test backend (SQLite tạm, không cần Docker) + 153 test CV gốc đều pass.
Chưa nối client thật, chưa có dashboard UI — xem docs/KE_HOACH_PLATFORM.md mục 3.
```

### Tuần 13 — Client↔Backend integration + UI/UX 1-máy ✅ Đã xong

```
Đã hoàn thành: config/fusion.yaml mở rộng (camera/paths/enrollment/report/backend + tham số dựng
từng signal, sửa đúng bug threshold IDENTITY 0.60/0.45→0.55/0.40 đã phát hiện ở Tuần 12 cũ);
src/app_config.py + src/signals/factory.py; src/ui/{app_state,button,text_field,overlay}.py (state
machine IDLE→ENROLLMENT→MONITORING→GENERATING_REPORT→ENDED, IDLE có thêm ô nhập Tên + Mã tham gia);
src/client/backend_client.py (BackendClient qua websockets.sync — không cần asyncio — + join_exam()
REST, thiết kế offline-first: backend không kết nối được thì phiên vẫn chạy đúng y hệt chế độ cục
bộ); backend/routers/ws.py bổ sung message "end_session" để CHÍNH thí sinh tự kết thúc phiên qua
WebSocket đang dùng (khác POST /sessions/{id}/end vốn chỉ admin/proctor gọi được, dùng cho ca
kết thúc hộ); src/app_controller.py (AppController gộp toàn bộ luồng); main.py viết lại thành entry
point mỏng. 43 test mới (config/factory/ui/backend_client/app_controller/end-to-end mô phỏng) +
1 test backend mới đều pass, 196 test CV + 11 test backend tổng cộng không regression. README.md
viết lại đầy đủ. Chưa xây dashboard UI (Tuần 14) — hiện chỉ xem được qua Swagger UI hoặc gọi API
trực tiếp. Chưa test qua webcam thật (máy dev không có webcam, như mọi tuần trước).
```

```
Bối cảnh: Đồ án Giám sát Thi bằng CV đã có backend (Tuần 12 mới, xem docs/KE_HOACH_PLATFORM.md).
Tuần này nối client thật vào backend, đồng thời hoàn thiện UI/UX 1-máy (nội dung Tuần 12 cũ ở trên,
tái sử dụng nguyên quyết định thiết kế: cửa sổ OpenCV, không PyQt).

Việc cần làm:
1. Xây AppState/AppController theo đúng thiết kế docs/KE_HOACH_CHI_TIET_TUAN12.md (IDLE→ENROLLMENT→
   MONITORING→GENERATING_REPORT→ENDED), nhưng ở bước IDLE thêm màn hình nhập tên + join-code, gọi
   POST /exams/join lấy session_token trước khi vào ENROLLMENT.
2. Viết BackendClient (WebSocket) gửi telemetry theo lô + ViolationEvent lên
   /ws/client bằng Authorization header — vẫn ghi JSONL
   local song song (offline-first, không phụ thuộc backend còn sống để phiên tiếp tục chạy được).
3. Lúc End: gọi POST /sessions/{id}/end, vẫn giữ khả năng sinh báo cáo local như cũ (không phụ
   thuộc backend để xem báo cáo ngay tại máy học sinh).
4. Test end-to-end mô phỏng (không cần webcam thật, dùng frame giả như các tuần trước) chạy được
   với docker compose up (backend local) - xác nhận file sessions/<id>/ trên server khớp đúng.

Báo cáo: chạy thử toàn luồng mô phỏng, xác nhận dữ liệu đến đúng backend.
```

### Tuần 14 — Dashboard giám thị ✅ Đã xong

```
Đã hoàn thành: backend/templates/ (base/login/register/exams/dashboard/session_detail.html, Jinja2
kế thừa base.html) + backend/static/ (style.css tự viết — không CDN, để demo Docker Compose không
cần internet — + api.js dùng chung cho auth/fetch/logout + 1 file JS riêng mỗi trang, vanilla,
không React). backend/routers/pages.py phục vụ trang, mount tại /ui/... (KHÔNG phải /exams — phát
hiện bug thật lúc code: trang HTML /exams trùng path với API JSON /exams, router đăng ký trước
thắng nên trang không bao giờ hiện ra, luôn trả 401 từ API; sửa bằng cách tách hẳn tiền tố /ui/...
cho mọi trang). Thêm 2 endpoint JSON mới ở backend/routers/sessions.py: GET /sessions/{id}/detail
(tái dùng load_session_report_data() của Tuần 11, không tự parse JSONL lại) và GET
/sessions/{id}/snapshots/{filename} (dùng Path(...).name để chặn path traversal). Bản hardening
hiện dùng cookie HttpOnly cùng origin cho dashboard/report/snapshot, không còn lưu token trong
localStorage hay gắn token vào URL. 24 test backend (13 test mới) đều pass. Đã chạy uvicorn thật
(không chỉ TestClient)
và xác nhận toàn luồng qua HTTP/WebSocket thật: đăng ký → đăng nhập → tạo exam → 2 thí sinh join →
gửi telemetry_update/violation_event/end_session qua WebSocket → dashboard WebSocket nhận đúng fan-out
real-time → GET .../detail trả đúng violations sắp xếp theo thời gian. 220 test (196 CV + 24
backend) không regression. Giới hạn: chưa kiểm được hành vi JS/WebSocket qua trình duyệt thật (cần
trình duyệt, không có ở môi trường này) — đã xác nhận đúng qua script Python mô phỏng WebSocket
client thay vì trình duyệt, xem docs/BAO_CAO_TUAN14.md.
```

```
Bối cảnh: Đồ án Giám sát Thi bằng CV, backend đã nhận được dữ liệu real-time từ client (Tuần 13).
Tuần này xây dashboard cho giám thị xem nhiều thí sinh cùng lúc — KHÔNG phải video trực tiếp, chỉ
bảng điểm rủi ro + trạng thái + ảnh chụp bằng chứng (đã chốt với người dùng, xem
docs/KE_HOACH_PLATFORM.md mục 1).

Việc cần làm:
1. Trang đăng nhập (admin/proctor), trang tạo Exam (admin) hiển thị join_code để phát cho thí sinh.
2. Trang dashboard: lưới các phiên đang active trong 1 Exam, tên + điểm rủi ro hiện tại + màu theo
   session_state, cập nhật real-time qua WebSocket /ws/dashboard/{exam_id} (vanilla JS, không React
   — xem lý do trong docs/KE_HOACH_PLATFORM.md).
3. Trang chi tiết 1 phiên: timeline vi phạm (đọc từ violations.jsonl qua API), ảnh chụp bằng chứng,
   nút tải báo cáo HTML/PDF (gọi lại endpoint Tuần 12 mới, không đổi backend).
4. CSS nhẹ (Pico.css hoặc tương tự, không cần build step) để trông chuyên nghiệp.

Chạy thử: mở 2-3 tab giả lập client (script gửi WS) + 1 tab dashboard, xác nhận cập nhật real-time.
```

### Tuần 15 — Hoàn thiện multi-tenant + bảo mật cơ bản ✅ Đã xong

```
Đã hoàn thành: backend/tests/test_org_isolation.py (5 test — 1 org không đọc/sửa/xóa được dữ liệu
org khác qua list sessions, end session, tải báo cáo, xem ảnh chụp, kết nối WS dashboard; kèm 1
test xác nhận proctor cũng bị cách ly đúng org, không chỉ admin) và
backend/tests/test_auth_token_confusion.py (3 test — session_token của thí sinh không dùng được làm
Bearer token của admin/proctor và ngược lại, dựa trên field "type" đã tách sẵn từ Tuần 12; token rác
bị từ chối). Toàn bộ 9 test PASS ngay từ lần chạy đầu — xác nhận thiết kế cách ly/JWT từ Tuần 12 vốn
đã đúng, tuần này bổ sung bằng chứng test tự động thay vì chỉ tin vào thiết kế. Viết
scripts/simulate_concurrent_students.py (giả lập N thí sinh + 1 dashboard nối tới backend THẬT qua
HTTP/WebSocket, không phải TestClient) — đã tự chạy thử với uvicorn thật (3 thí sinh, 30 giây),
log server sạch không lỗi, dashboard nhận đúng toàn bộ cập nhật real-time từ cả 3 phiên đồng thời.
README.md thêm mục "Bảo mật" (JWT_SECRET_KEY demo cần đổi khi deploy thật, tóm tắt cơ chế cách ly)
và mục hướng dẫn dùng script mô phỏng nhiều phiên. docker-compose.yml thêm comment cảnh báo
JWT_SECRET_KEY. 229 test (196 CV + 33 backend) đều pass, không regression.
```

```
Bối cảnh: Đồ án Giám sát Thi bằng CV, đã có đủ backend + dashboard (Tuần 12-14 mới). Tuần này rà
soát lại tính đúng đắn multi-tenant và bảo mật trước khi chuyển sang giai đoạn đánh giá/luận văn.

Việc cần làm:
1. Viết thêm test xác nhận cách ly giữa các Organization (1 org không xem/sửa được dữ liệu org khác)
   ở mọi endpoint, không chỉ /exams (đã có ở Tuần 12 mới) — bổ sung cho /exams/{id}/sessions,
   /sessions/{id}/report.
2. Rà soát JWT: thời hạn hợp lý, secret key đọc từ biến môi trường (không hardcode khi deploy thật),
   session_token (thí sinh) không dùng lẫn được với user token (đã tách type "user"/"exam_session"
   trong backend/auth.py — viết test xác nhận không thể giả mạo chéo).
3. README hướng dẫn chạy docker compose up từ đầu, kèm hướng dẫn demo cho hội đồng.
4. Demo thử 2-3 phiên đồng thời (script giả lập nhiều client) + 1 dashboard xem cùng lúc, xác nhận
   ổn định không bug rõ ràng.

Báo cáo: danh sách bug/rủi ro bảo mật tìm được và đã sửa, xác nhận demo nhiều phiên ổn định.
```

---

## THÁNG 4 — Đánh giá & Luận văn

### Tuần 16 — Quay & gán nhãn bộ test (dời từ Tuần 13 cũ)

> **Tài liệu chuẩn bị đã xong**: `docs/HUONG_DAN_QUAY_TUAN16.md` (kịch bản chi tiết từng phút cho cả 6 loại, đúng định dạng `docs/DATA_SCHEMAS.md` mục 5) + `scripts/scaffold_test_clip.py` (tự dựng khung thư mục/`labels.json`/cập nhật `manifest.csv`, đã test chạy đúng). **Phần quay/gán nhãn thật vẫn CHƯA làm** — việc này cần người dùng tự thực hiện (cần webcam + người hỗ trợ đóng vai `multi_face`/`impersonation`), không phải việc code.

```
Bối cảnh: Đồ án Giám sát Thi bằng CV, sản phẩm đã hoàn chỉnh. Tuần này chuẩn bị dữ liệu cho chương
Thực nghiệm & Đánh giá — đây là bộ TEST để đánh giá (không phải dữ liệu huấn luyện).

Việc cần làm:
1. Lên kịch bản quay ~20-30 clip ngắn (2-5 phút/clip), phủ các trường hợp: bình thường (baseline
   không vi phạm), dùng điện thoại, nhìn ra ngoài màn hình nhiều lần, nhiều người trong khung hình,
   nói chuyện/thì thầm, đổi người thi hộ giữa clip (nhờ 1-2 người khác quay giúp).
2. Quay bằng chính app đã xây (chạy pipeline trong lúc quay để có sẵn log, hoặc quay video thô rồi
   chạy pipeline lại sau — chọn cách nào tiện hơn).
3. Gán nhãn ground truth thủ công cho từng clip theo định dạng đã thiết kế ở docs/DATA_SCHEMAS.md
   (Tuần 2): mốc thời gian bắt đầu/kết thúc mỗi vi phạm thật, loại vi phạm.
4. Tổ chức lưu trữ: thư mục data/test_set/ chứa video + file nhãn tương ứng, có README mô tả từng
   clip là kịch bản gì.

Báo cáo số lượng clip đã quay theo từng loại kịch bản, xác nhận đã đủ đa dạng để đánh giá có ý
nghĩa (tối thiểu 3-5 clip/loại).
```

### Tuần 17 — Cài baseline + đánh giá định lượng (Precision/Recall/F1) (dời từ Tuần 14 cũ)

```
Bối cảnh: Đồ án Giám sát Thi bằng CV, đã có bộ test gán nhãn ở Tuần 16. Tuần này là trọng tâm
chương Thực nghiệm — so sánh định lượng pipeline tự thiết kế với baseline.

Việc cần làm:
1. Cài đặt 1 phiên bản "baseline" đơn giản: mô phỏng lại logic if/elif có thứ tự ưu tiên, chỉ ghi
   1 loại vi phạm/frame, không có head pose/identity verification, không có hysteresis — đại diện
   cho cách tiếp cận kiểu dự án tham khảo (KHÔNG copy code, chỉ mô phỏng logic tương đương để so
   sánh công bằng).
2. Chạy cả pipeline chính và baseline trên toàn bộ bộ test (Tuần 16), thu kết quả phát hiện của
   từng cái.
3. Tính Precision, Recall, F1-score cho từng loại vi phạm (so với ground truth), so sánh giữa
   pipeline chính và baseline. Tính thêm độ trễ phát hiện trung bình (từ lúc vi phạm thật xảy ra
   đến lúc hệ thống cảnh báo).
4. Phân tích riêng: đánh giá tác động của hysteresis lên tỉ lệ báo động giả (so sánh có/không có
   hysteresis), và đánh giá riêng độ chính xác Identity Verification (bao nhiêu % lần đổi người bị
   phát hiện đúng, có false positive khi cùng 1 người đổi ánh sáng/góc nghiêng không).
5. Xuất toàn bộ kết quả thành bảng số liệu + biểu đồ (matplotlib), lưu vào docs/KET_QUA_THUC_NGHIEM.md.

Báo cáo tóm tắt số liệu chính (Precision/Recall/F1 trung bình của pipeline chính vs baseline) ngay
khi có kết quả.
```

### Tuần 18 — Viết chương Thiết kế/Cài đặt/Thực nghiệm (dời từ Tuần 15 cũ)

```
Bối cảnh: Đồ án Giám sát Thi bằng CV, đã có đầy đủ số liệu thực nghiệm (Tuần 17) và toàn bộ code
đã hoàn chỉnh, bao gồm cả lớp platform (Tuần 12-15 mới). Tuần này dồn vào viết luận văn dựa trên
tài liệu kỹ thuật đã tích luỹ suốt 17 tuần.

Việc cần làm:
1. Viết chương "Phân tích & Thiết kế hệ thống": dựa trên docs/DIAGRAMS.md, docs/DATA_SCHEMAS.md và
   docs/KE_HOACH_PLATFORM.md, trình bày lại mạch lạc kiến trúc pipeline CV + kiến trúc platform,
   giải thích lý do thiết kế (tại sao chọn state machine + hysteresis, solvePnP thay vì deep
   learning cho head pose, và tại sao không xây video-conferencing thật cho phần platform).
2. Viết chương "Cài đặt hệ thống": mô tả các module đã code (perception, signals, fusion,
   reporting, backend, dashboard), kèm đoạn code minh hoạ quan trọng nhất (không paste toàn bộ code,
   chỉ đoạn cốt lõi thể hiện thuật toán).
3. Viết chương "Thực nghiệm & Đánh giá" dựa trên docs/KET_QUA_THUC_NGHIEM.md: trình bày phương
   pháp đánh giá, bảng số liệu, biểu đồ, phân tích kết quả (giải thích tại sao pipeline chính tốt
   hơn/kém hơn baseline ở từng khía cạnh, không chỉ liệt kê số).
4. Viết chương ngắn mới "Định hướng thương mại hóa": đối tượng khách hàng (xem
   docs/KE_HOACH_PLATFORM.md mục 1), so sánh chi phí/mô hình với Proctorio/Honorlock/ProctorU
   (Chương 3), giới hạn hiện tại (chỉ demo Docker Compose local, chưa deploy cloud thật, chưa có
   video live) và hướng phát triển tiếp (deploy cloud thật, dashboard React, video-conferencing nếu
   có nguồn lực).
5. Gộp với chương Cơ sở lý thuyết/Khảo sát đã viết ở Tuần 8, sắp xếp lại thành 1 file luận văn nháp
   hoàn chỉnh theo đúng cấu trúc chương đã định (Mở đầu → Cơ sở lý thuyết → Khảo sát → Thiết kế →
   Cài đặt → Thực nghiệm → Định hướng thương mại hóa → Kết luận).

Đưa ra bản nháp đầy đủ để tôi đọc và góp ý chỉnh sửa.
```

### Tuần 19 — Hoàn thiện luận văn + slide + demo + rà soát trích dẫn (dời từ Tuần 16 cũ)

```
Bối cảnh: Đồ án Giám sát Thi bằng CV (nay là platform), tuần cuối cùng trước khi nộp/bảo vệ.

Việc cần làm:
1. Viết nốt chương "Mở đầu" (đặt vấn đề, lý do chọn đề tài, mục tiêu, phạm vi — dựa trên
   docs/DE_CUONG_CHI_TIET.md) và chương "Kết luận & Hướng phát triển" (tóm tắt đóng góp, hạn chế,
   đề xuất mở rộng như: nhận diện giọng nói theo từ khóa, train custom object detector, deploy cloud
   thật, dashboard React, video-conferencing tích hợp nếu làm tiếp).
2. Rà soát toàn bộ luận văn: đảm bảo mục "Công nghệ liên quan/Related Work" trích dẫn rõ ràng dự án
   exam-cheating-detection (AarambhTech, MIT) đúng vai trò baseline/tham khảo, không để người đọc
   hiểu nhầm là đã copy code.
3. Chuẩn bị slide bảo vệ (10-15 slide): vấn đề, kiến trúc CV + platform, 2 kỹ thuật CV mới nổi bật
   (head pose, identity verification), thuật toán risk fusion, kiến trúc multi-tenant, số liệu thực
   nghiệm so với baseline, định hướng thương mại hóa, demo.
4. Chuẩn bị kịch bản demo trực tiếp: `docker compose up` → 2 máy/2 tab client join bằng join-code →
   dashboard giám thị xem real-time → 1 client vi phạm (VD dùng điện thoại) → dashboard cập nhật →
   kết thúc phiên → tải báo cáo PDF, tính thời gian demo vừa đủ (5-7 phút).
5. Chuẩn bị trước danh sách câu hỏi hội đồng có thể hỏi và câu trả lời gợi ý (đặc biệt câu "khác gì
   dự án gốc" và "vì sao không dùng Zoom/Meet" — trả lời dựa trên docs/KE_HOACH_PLATFORM.md mục 1).

Xuất bản checklist cuối cùng những gì đã hoàn thành và những gì (nếu có) còn thiếu trước ngày bảo vệ.
```
