# Chương 7. Kết luận và hướng phát triển

## 7.1. Tổng kết đề tài

Đồ án đã xây dựng một hệ thống giám sát thi gồm pipeline thị giác máy tính tại client, browser extension và nền tảng FastAPI/dashboard. So với mục tiêu ban đầu là một ứng dụng webcam cục bộ, phạm vi sản phẩm đã được mở rộng sang quản lý nhiều tổ chức, phân quyền theo kỳ thi, truyền dữ liệu thời gian thực, quản lý evidence, incident review và báo cáo.

Hệ thống không tự động kết luận thí sinh gian lận. Đầu ra của model và extension được biểu diễn thành tín hiệu, trạng thái, điểm số, sự kiện và ảnh bằng chứng để giám thị xem xét trong ngữ cảnh quy chế thi.

## 7.2. Kết quả chính đạt được

### 7.2.1. Pipeline thị giác máy tính có cấu trúc

Đồ án đã triển khai tầng nhận thức dùng chung gồm MTCNN, MediaPipe Face Landmarker và YOLOv8n. Kết quả được đóng gói vào `PerceptionResult` và chia sẻ cho bảy Signal Extractor:

- Face Presence.
- Multi-face.
- Eye State.
- Mouth State.
- Object Presence.
- Head Pose.
- Identity.

Mỗi tín hiệu tuân theo một interface chung và chỉ chịu trách nhiệm cho hiện tượng của mình. Thiếu khuôn mặt không bị diễn giải đồng thời thành mắt nhắm, head pose sai và identity mismatch. Detector lỗi tạm thời có fallback để phiên không bị kết thúc đột ngột.

### 7.2.2. Hai kỹ thuật CV bổ sung so với baseline

Head Pose sử dụng tương ứng landmark 2D–mô hình mặt 3D và `solvePnP` để ước lượng yaw, pitch, roll. Cách này tạo đại lượng góc có ý nghĩa hình học thay cho độ lệch pixel phụ thuộc độ phân giải.

Identity sử dụng InceptionResnetV1 để tạo embedding 512 chiều, trung bình nhiều frame enrollment và so sánh cosine định kỳ. Vùng warning, ngưỡng mismatch và yêu cầu lỗi liên tiếp giúp tránh kết luận từ một quan sát đơn lẻ. Enrollment được ràng buộc với thử thách chớp mắt cơ bản.

### 7.2.3. Risk Fusion Engine có trạng thái và khả năng giải thích

Mỗi tín hiệu có state machine `NORMAL → SUSPICIOUS → ALERT` dựa trên cửa sổ thời gian và hysteresis riêng. Tầng phiên kết hợp state bằng weighted scoring và hysteresis hai ngưỡng. Violation event chỉ sinh tại cạnh chuyển vào cảnh báo, tránh tạo một bản ghi cho mọi frame.

Sự kiện giữ risk score, severity, primary violation và contributing signals. Timeline transition và risk score được lưu riêng, giúp báo cáo giải thích vì sao hệ thống cảnh báo thay vì chỉ đưa ra nhãn cuối.

### 7.2.4. Giám sát trình duyệt và nền tảng thời gian thực

Browser extension đã triển khai luồng nhập mã, xác thực manual/Google, consent, kiểm tra policy và content monitor. Extension theo dõi focus/tab, fullscreen, clipboard, camera, microphone, screen share và heartbeat. Integrity trình duyệt được tính tách biệt với risk CV.

Backend FastAPI đã hỗ trợ:

- Quản lý tổ chức, thành viên, invitation và policy.
- Quản lý lifecycle kỳ thi, join code, assignment và readiness.
- Xác thực nhân sự/thí sinh, MFA và Google OIDC.
- WebSocket client/dashboard với ticket dùng một lần.
- Dashboard thời gian thực và chi tiết phiên.
- Evidence, incident review, report job và retention.
- Docker Compose với PostgreSQL, Redis, backend và report worker.

### 7.2.5. Phân quyền và bảo vệ dữ liệu

Quyền được giải quyết theo System Role, Organization Membership và Exam Assignment. System Admin không mặc nhiên xem dữ liệu thí sinh; quyền ngoại lệ phải được phê duyệt, chỉ đọc và còn thời hạn. Backend kiểm tra tenant/resource scope trên REST, WebSocket và file download.

Client được coi là nguồn không tin cậy. Server kiểm tra schema, timestamp, đủ bảy signal, risk/state/severity/contribution, browser event và ảnh upload. Dữ liệu giao diện được dựng bằng API DOM an toàn; security header và audit log được áp dụng cho các luồng nhạy cảm.

### 7.2.6. Dữ liệu và báo cáo

Đồ án kết hợp SQL cho metadata/trạng thái hiện tại với JSONL cho chuỗi sự kiện. Snapshot được lưu dưới tên server sinh. Incident review tách khỏi violation gốc để nhận định của con người không sửa dữ liệu máy. Report pipeline có thể sinh HTML/PDF từ dữ liệu không hoàn chỉnh; report job chạy ở worker nền.

## 7.3. Kết quả kiểm thử và thực nghiệm

Source hiện tại đã được chạy lại và đạt:

- 309 test Python pass, bao phủ desktop CV, fusion, reporting, API, authentication, RBAC, tenant isolation, WebSocket và giao diện.
- 8 test extension pass.
- Benchmark CPU tổng hợp khoảng 25,3 FPS; MTCNN là bottleneck lớn nhất.

Trên snapshot thực nghiệm bên ngoài gồm 25 video và 199.470 frame:

| Chỉ số | Kết quả |
|---|---:|
| Precision | 0,7083 |
| Recall | 0,8500 |
| F1-score | 0,7727 |
| Accuracy | 0,9248 |
| Specificity | 0,9380 |
| FPR | 0,0620 |

So với baseline, Precision tăng 0,0562, Recall tăng 0,1270 và F1 tăng 0,0876 theo giá trị tuyệt đối. Các mục tiêu Precision ≥ 0,70, Recall ≥ 0,80 và F1 ≥ 0,75 đạt được trên snapshot này.

Kết quả không được diễn giải thành độ chính xác phổ quát. Dataset và artifact thực nghiệm nằm ngoài repository; cấu hình snapshot khác một phần so với cấu hình hiện tại; số người, thiết bị và điều kiện quay còn hạn chế.

## 7.4. Những hạn chế còn tồn tại

### 7.4.1. Desktop CV và extension chưa hợp nhất hoàn toàn

Desktop client và extension đều có thể tạo/gửi dữ liệu, nhưng chưa có native-messaging bridge để chúng phối hợp như một client thống nhất trong cùng browser session. Việc hợp nhất cần giải quyết ownership của session token, đồng bộ lifecycle, retry và chống sự kiện trùng.

### 7.4.2. Đồng bộ khi mất mạng chưa đầy đủ

Desktop CV vẫn ghi log và sinh báo cáo cục bộ khi backend mất kết nối. Tuy nhiên, dữ liệu phát sinh trong thời gian offline chưa được đồng bộ bù đầy đủ lên server. Extension có hàng đợi reconnect nhưng dung lượng và vòng đời storage vẫn bị giới hạn bởi trình duyệt.

### 7.4.3. Giới hạn của model CV

- MTCNN và landmark chịu ảnh hưởng của ánh sáng, góc lớn và che khuất.
- EAR có thể sai khi cả hai mắt cùng bị biến dạng phối cảnh.
- Head pose không phân biệt chắc chắn quay đầu tự nhiên với nhìn tài liệu.
- YOLOv8n có thể bỏ sót điện thoại nhỏ/mặt lưng hoặc nhận nhầm vật thể.
- Face embedding nhạy với góc, ánh sáng và chất lượng enrollment.
- Liveness chớp mắt không chống được replay/deepfake chuyên dụng.

### 7.4.4. Giới hạn của browser extension

Extension chỉ quan sát dữ liệu mà WebExtensions API cho phép. Nó không nhìn được ứng dụng native khác, máy ảo, remote desktop hoặc điện thoại thứ hai. Nếu extension không được ký và force-install trong managed browser, thí sinh có quyền trên thiết bị vẫn có thể vô hiệu hóa hoặc sửa client.

### 7.4.5. Giới hạn về quy mô và vận hành

Redis đã hỗ trợ lease client và pub/sub dashboard khi cấu hình, nhưng production quy mô lớn vẫn cần:

- Object storage thay cho shared local filesystem.
- Hàng đợi công việc và retry có khả năng quan sát tốt hơn.
- Backup/restore và disaster recovery.
- Metrics, tracing, log tập trung và cảnh báo vận hành.
- Load test nhiều worker/nhiều kỳ thi đồng thời.
- Quy trình migration/rollback chuẩn hóa.

### 7.4.6. Khả năng tái lập thực nghiệm

Repository chưa chứa manifest, label, prediction, checkpoint và environment của bộ 25 video. Vì vậy confusion matrix và metric được giữ như kết quả từ môi trường ngoài nhưng chưa thể tái lập độc lập từ bản bàn giao hiện tại. Đây là giới hạn học thuật cần được ưu tiên khắc phục.

### 7.4.7. Quyền riêng tư và công bằng

Hình ảnh khuôn mặt và dữ liệu hành vi là dữ liệu nhạy cảm. Một triển khai thật cần thông báo minh bạch, consent phù hợp, thời hạn lưu trữ, quy trình khiếu nại, quyền truy cập evidence và đánh giá sai lệch theo nhóm người dùng. Dataset nhỏ hiện tại chưa đủ để kết luận công bằng giữa màu da, kính, đặc điểm khuôn mặt, camera và điều kiện ánh sáng.

## 7.5. Hướng phát triển

### 7.5.1. Ưu tiên 1 – Đóng gói thực nghiệm có thể tái lập

Đây là công việc ưu tiên cao nhất để củng cố kết luận khoa học:

- Lưu manifest clip và hash của video.
- Lưu ground truth theo khoảng thời gian và loại vi phạm.
- Công bố cách chia train/validation/test theo clip/người.
- Lưu commit hash, config, checkpoint và dependency lock.
- Lưu prediction JSONL và script tính metric/biểu đồ.
- Báo cáo đồng thuận giữa người gán nhãn và kết quả theo từng signal.

Khi có artifact, cần chạy lại cả cấu hình snapshot thực nghiệm và cấu hình repository hiện tại trên cùng test set.

### 7.5.2. Ưu tiên 2 – Hợp nhất desktop CV với extension

Có thể phát triển native companion được ký và giao tiếp với extension qua native messaging. Extension quản lý browser session/policy; companion quản lý webcam/model; cả hai dùng cùng session ID và sequence. Thiết kế cần có mutual authentication, version policy và cơ chế chống replay.

### 7.5.3. Ưu tiên 3 – Cải thiện chất lượng nhận diện

- Thu thập dữ liệu đa dạng hơn theo người, camera và ánh sáng.
- Hiệu chuẩn EAR/identity trong enrollment theo từng người.
- Kết hợp confidence của head pose với eye state.
- Đánh giá YOLOv8s hoặc fine-tune có train/test split rõ ràng.
- Xử lý Identity bất đồng bộ để tránh giật frame.
- Thử RetinaFace/ArcFace hoặc model robust hơn khi có đủ tài nguyên.
- Tích hợp liveness/anti-spoofing được đánh giá trên replay/deepfake.

Mọi cải tiến cần được đo bằng ablation study thay vì chỉ thay ngưỡng theo cảm nhận.

### 7.5.4. Ưu tiên 4 – Hoàn thiện sản phẩm và hạ tầng

- Ký và force-install extension trong managed browser.
- Ký native companion, kiểm tra version và cập nhật an toàn.
- Dùng HTTPS bắt buộc, secret manager và key rotation.
- Chuyển snapshot/report sang object storage có signed URL ngắn hạn.
- Bổ sung operations center, queue monitoring và storage/quota alert.
- Load test nhiều tổ chức/kỳ thi/worker và thiết kế capacity plan.
- Chuẩn hóa migration bằng công cụ có version/rollback.

### 7.5.5. Ưu tiên 5 – Quản trị dữ liệu và trải nghiệm người dùng

- Xây dựng data-subject request, export/xóa và legal hold.
- Watermark report/evidence và thông báo khi truy cập nhạy cảm.
- Cải thiện preflight theo từng bước và hướng dẫn khắc phục lỗi.
- Thiết kế resume/rejoin an toàn sau crash hoặc đổi thiết bị.
- Đánh giá accessibility và hỗ trợ đa ngôn ngữ/timezone.
- Xây dựng quy trình appeal để thí sinh có thể phản hồi cảnh báo sai.

## 7.6. Bài học kinh nghiệm

Quá trình thực hiện cho thấy một số bài học có thể tổng quát hóa:

1. Công thức đúng chưa bảo đảm implementation đúng; tọa độ chuẩn hóa sai tỉ lệ chỉ được phát hiện khi thử webcam thật.
2. Ngưỡng theo số frame không ổn định khi FPS thay đổi; thời lượng và cửa sổ theo giây phù hợp hơn.
3. Một tín hiệu không nên tự diễn giải lỗi của tầng khác; thiếu landmark cần trả “không đủ dữ liệu”.
4. Cảnh báo cần state và hysteresis; nhãn từng frame tạo quá nhiều nhiễu.
5. Frontend không phải ranh giới bảo mật; capability và tenant scope phải được thực thi ở backend.
6. Dữ liệu tổng hợp hữu ích cho tải/report nhưng không thay thế video thật có ground truth.
7. Kết quả metric chỉ có giá trị khoa học khi đi kèm artifact và quy trình tái lập.

## 7.7. Kết luận

Đồ án đã đạt mục tiêu xây dựng một nền tảng giám sát thi có cấu trúc, kết hợp bảy tín hiệu CV, state machine, Risk Fusion Engine, extension theo dõi trình duyệt, dashboard thời gian thực, phân quyền nhiều tổ chức và quy trình evidence/report. Bộ kiểm thử xác nhận tính nhất quán của implementation trong phạm vi đã mô tả. Snapshot thực nghiệm 25 video đạt Precision 0,7083, Recall 0,8500 và F1 0,7727, cho thấy hướng kết hợp đa tín hiệu có tiềm năng tốt hơn baseline đơn giản.

Đóng góp quan trọng nhất không phải một model mới mà là cách tổ chức nhiều model và thành phần phần mềm thành một chuỗi xử lý có trạng thái, có thể giải thích và có kiểm soát truy cập. Hệ thống hiện phù hợp cho nghiên cứu, đồ án và triển khai thử nghiệm có kiểm soát. Để sử dụng cho kỳ thi rủi ro cao, cần tiếp tục hoàn thiện khả năng tái lập, anti-spoofing, tích hợp client, hạ tầng production và quản trị dữ liệu.
