# Chương 6. Kiểm thử và đánh giá

## 6.1. Mục tiêu và phạm vi đánh giá

Chương này đánh giá hai loại thuộc tính khác nhau:

1. **Độ đúng của phần mềm:** module có thực hiện đúng hợp đồng, quyền truy cập và luồng nghiệp vụ hay không.
2. **Hiệu quả phát hiện CV:** hệ thống nhận biết frame vi phạm trên bộ video có ground truth tốt đến mức nào.

Hai loại bằng chứng không thay thế cho nhau. Test pass chứng minh implementation đáp ứng tình huống đã mô tả, nhưng không chứng minh model có độ chính xác cao ngoài thực tế. Ngược lại, Precision/Recall tốt trên một dataset không chứng minh hệ thống an toàn trước truy cập chéo tổ chức hoặc token giả mạo.

Source code và test phần mềm được chạy lại trong repository hiện tại. Bộ 25 video, ground truth, checkpoint thực nghiệm và output đánh giá được tạo ở một môi trường khác, không nằm trong repository này. Các số liệu CV dưới đây được giữ theo kết quả đã xác nhận từ môi trường đó; những chỉ số có thể suy ra từ confusion matrix được tính lại để bảo đảm nhất quán.

## 6.2. Kiểm thử phần mềm trong repository

### 6.2.1. Phương pháp

Bộ test Python được chạy bằng:

```bash
.venv\Scripts\python.exe -m pytest -q backend\tests tests
```

Extension được chạy bằng:

```bash
cd extension
npm test
```

Kết quả ghi nhận ngày 12/08/2026 trên môi trường phát triển Windows hiện tại:

| Nhóm | Kết quả | Thời gian |
|---|---:|---:|
| Python: desktop CV, fusion, reporting và backend | 309 passed, 0 failed | 124,87 giây |
| Extension Node test | 8 passed, 0 failed | 132,55 ms theo Node test runner |

Pytest báo 344 warning, chủ yếu là deprecation warning từ Starlette/httpx, SQLite datetime adapter và protobuf. Warning không làm test thất bại nhưng cần được theo dõi khi nâng phiên bản dependency.

### 6.2.2. Kiểm thử pipeline CV và thuật toán

Các nhóm kiểm thử chính gồm:

- Công thức EAR, tỉ lệ miệng và chuyển đổi tọa độ.
- Debounce thời lượng cho vắng mặt, mắt, vật thể và head pose.
- Lọc confidence của Multi-face.
- PnP trên góc quay tổng hợp biết trước.
- Cosine similarity, enrollment và chu kỳ Identity.
- Liveness mở–nhắm–mở.
- Tính chịu lỗi khi detector ném exception.
- Hợp đồng đủ bảy signal và factory đọc đúng YAML.
- State machine, cửa sổ trượt, hysteresis, rising edge và nhiều tín hiệu đóng góp.
- Smoke test khởi tạo/runs các model thật và integration test trên video mẫu.

Một số test hồi quy xuất phát từ lỗi quan sát được trên webcam thật. Ví dụ, Eye State từng báo nhầm khi một mắt bị nén phối cảnh; test hiện yêu cầu biến dạng một mắt không được coi là nhắm, trong khi hai mắt cùng EAR thấp vẫn phải kích hoạt.

### 6.2.3. Kiểm thử backend và bảo mật

Bộ test backend dùng FastAPI TestClient và database SQLite tạm cho từng ca. Các nhóm được kiểm tra:

- Đăng ký, đăng nhập, cookie, logout và rate limit.
- MFA của System Admin, giới hạn số lần thử và recovery/re-enrollment.
- Phân biệt user token, session token, WebSocket ticket và token rác.
- Membership nhiều tổ chức và chuyển active organization.
- Capability theo từng exam assignment; manager ở kỳ thi A không có quyền manager ở kỳ thi B.
- Cô lập tổ chức trên danh sách phiên, kết thúc phiên, report, snapshot và dashboard WebSocket.
- Policy inheritance và từ chối cấu hình làm yếu sàn hệ thống/tổ chức.
- Lifecycle, optimistic locking, join code và quota phiên đồng thời.
- Google OIDC giả lập, state/PKCE/nonce/grant và device token.
- Validation đủ bảy signal, tính lại risk/integrity phía server và browser event.
- Upload snapshot, chống path traversal, incident review và report job nền.
- Security header, DOM an toàn và các route giao diện.

Kết quả 309 test pass cho thấy source hiện tại nhất quán với các hợp đồng và quy tắc đã mô tả. Bộ test không phải penetration test độc lập và không bao phủ hành vi của mọi trình duyệt/thiết bị thật.

### 6.2.4. Kiểm thử extension

Tám test Node kiểm tra popup setup, luồng nhập mã, chuẩn hóa backend URL, bắt buộc HTTPS ngoài localhost, so sánh semantic version, parse browser identity, lọc dữ liệu OAuth redirect và cấu trúc gói extension. Ngoài test tự động, các API camera, screen share, fullscreen và behavior của trình duyệt vẫn cần kiểm tra thủ công trên Chrome/Firefox thật vì Node không mô phỏng đầy đủ permission prompt và lifecycle service worker.

## 6.3. Đánh giá hoạt động của hệ thống đã triển khai

### 6.3.1. Phương pháp và tiêu chí đánh giá

Đánh giá hoạt động xem hệ thống có duy trì được một chuỗi nghiệp vụ hoàn chỉnh từ cấu hình kỳ thi đến hậu kiểm hay không. Bằng chứng sử dụng gồm source code, test tự động, cấu trúc giao diện đã triển khai, data contract và trạng thái bền vững trong cơ sở dữ liệu/evidence. Phần này không đồng nhất “route tồn tại” với “sẵn sàng production”: một luồng chỉ được kết luận đạt trong phạm vi test nếu có kiểm tra hành vi và điều kiện lỗi tương ứng; các tương tác phụ thuộc trình duyệt, webcam và permission prompt thật được ghi là cần xác nhận bổ sung.

Các tiêu chí gồm:

- **Tính đầy đủ nghiệp vụ:** có đủ bước chuẩn bị, tham gia, giám sát, kết thúc, review và report.
- **Tính nhất quán dữ liệu:** trạng thái hiển thị trên giao diện có nguồn từ dữ liệu backend đã kiểm chứng; evidence gắn đúng organization, exam và session.
- **Khả năng quan sát:** người dùng nhận biết được trạng thái tải, lỗi, mất kết nối, preflight chưa đạt và report job thất bại.
- **An toàn phạm vi:** chức năng chỉ xuất hiện và chỉ thực thi với vai trò/capability hợp lệ.
- **Khả năng suy giảm có kiểm soát:** lỗi một kênh không làm dữ liệu cũ bị trình bày như dữ liệu realtime hoặc tạo báo cáo thành công giả.

### 6.3.2. Đánh giá các kịch bản đầu-cuối

| Kịch bản | Luồng được kiểm chứng | Bằng chứng hiện có | Đánh giá |
|---|---|---|---|
| Chuẩn bị tổ chức | Tạo tổ chức, membership, role, policy và quota | API/UI route, migration và test auth/RBAC/policy | Đạt trong phạm vi kiểm thử tự động |
| Chuẩn bị kỳ thi | Tạo kỳ thi, cấu hình, assignment, readiness và join code | Lifecycle, optimistic locking, assignment, join-code test | Đạt trong phạm vi kiểm thử tự động |
| Thí sinh tham gia | Kiểm tra mã, xác thực thủ công/Google, consent, cấp session token | Candidate auth, Google OIDC giả lập, token-type test và extension setup test | Đạt về logic; cần kiểm tra OAuth/permission thật |
| Khởi động desktop CV | IDLE → ENROLLMENT → liveness → MONITORING | Controller, enrollment/liveness, smoke và video integration test | Đạt về chức năng; phụ thuộc webcam/môi trường |
| Giám sát trình duyệt | Preflight, tab/focus/fullscreen/clipboard, heartbeat | Extension source, Node test, browser-event validation test | Đạt phần logic; cần chạy Chrome/Firefox thật |
| Truyền dữ liệu realtime | Client hello, telemetry, violation, browser event, heartbeat, dashboard fan-out | WebSocket schema, ticket, sequence/dedup và authorization test | Đạt trong phạm vi backend test |
| Giám sát và mở chi tiết phiên | REST initial state, WebSocket update, filter, risk/evidence timeline | Dashboard route/static source, tenant-isolation và WebSocket test | Đạt về tích hợp phía server; cần kiểm tra UI đa phiên thật |
| Kết thúc và hậu kiểm | End session, incident review, snapshot access và audit | Session-end, review, snapshot/path traversal và audit test | Đạt trong phạm vi kiểm thử tự động |
| Sinh báo cáo | Report job → worker → HTML/PDF → trạng thái completed/failed | Reporting consistency, report-job và tolerant-loader test | Đạt về chức năng |
| Mất kết nối/lỗi dữ liệu | Socket gián đoạn, message sai schema, dữ liệu trùng, backend unavailable | Validation, dedup, connection manager và local best-effort behavior | Đạt một phần; cần thử nghiệm mạng gián đoạn dài |

Kết quả cho thấy các phân hệ không tồn tại rời rạc mà đã có hợp đồng nối tiếp: policy từ backend điều khiển preflight; session token xác định đúng phiên; telemetry đã kiểm chứng cập nhật current state và evidence; dashboard/review/report cùng sử dụng session ID làm khóa truy vết. Điểm còn thiếu chủ yếu thuộc môi trường thực: vòng đời service worker của trình duyệt, permission prompt, tải đồng thời nhiều phiên và các kiểu mất mạng kéo dài.

### 6.3.3. Đánh giá luồng dữ liệu và tính nhất quán

Luồng dữ liệu tại Hình 4.9 được đánh giá theo ba chặng. Ở chặng thu thập, desktop client tạo đủ bảy signal và extension chỉ gửi các browser event đã định nghĩa; dữ liệu ảnh không được truyền liên tục. Ở chặng kiểm chứng, backend từ chối trường thừa, miền giá trị sai, timestamp thiếu timezone, sequence trùng và đường dẫn snapshot do client tự quyết định. Ở chặng khai thác, dữ liệu realtime chỉ được fan-out sau authorization/validation, còn SQL và evidence lưu hai biểu diễn phục vụ hai loại tải khác nhau.

Các invariant quan trọng đã được kiểm thử gồm:

- Một telemetry update phải chứa đúng bảy signal và bảy state không trùng.
- Risk score, severity, primary/contributing signal và browser integrity không được tin trực tiếp nếu có thể tính lại phía server.
- `ExamSession` giữ bản sao trạng thái mới nhất để dashboard nạp nhanh; JSONL giữ chuỗi sự kiện để dựng timeline và báo cáo.
- Snapshot phải đúng định dạng, kích thước, hash và nằm trong thư mục phiên do server quản lý.
- Incident review bổ sung kết luận của con người mà không sửa violation nguyên bản.
- WebSocket dashboard dùng ticket ngắn hạn, dùng một lần; quyền vẫn được kiểm tra theo exam assignment.

Nhờ các invariant này, cùng một sự kiện có thể được truy từ card trên dashboard đến session detail, dòng JSONL, snapshot và report. Giới hạn hiện tại là việc đồng bộ desktop CV và extension vào cùng một phiên vẫn phụ thuộc cách triển khai client; chưa có native-messaging bridge hoàn chỉnh để ràng buộc hai tiến trình trên máy thí sinh ở mức chống giả mạo.

### 6.3.4. Đánh giá giao diện và khả năng vận hành

Giao diện đã bao phủ các nhiệm vụ chính được mô tả tại mục 5.8. Shell web tách System, Organization và Exam workspace; extension trình bày luồng tham gia theo bước; desktop client phản ánh state machine; session detail và report phục vụ hậu kiểm. Cách chia này phù hợp với tần suất sử dụng: quản trị viên không cần thấy dữ liệu frame-level, thí sinh không cần thấy dashboard nhiều phiên, còn giám thị cần ưu tiên risk, integrity, alert và evidence.

Về phản hồi trạng thái, dashboard có chỉ báo WebSocket, extension có preflight/status region, report job có trạng thái `pending/processing/failed/completed`, và desktop client có các state `IDLE/ENROLLMENT/MONITORING/GENERATING_REPORT/ENDED`. Đây là nền tảng để người dùng nhận biết tiến trình thay vì thực hiện lại thao tác do không biết hệ thống đã nhận lệnh hay chưa.

Tuy nhiên, đánh giá giao diện trong repository chủ yếu dựa trên route, DOM contract, JavaScript và test backend/Node. Cần bổ sung một vòng nghiệm thu có người dùng với screenshot thật cho các Hình 5.1–5.14, trong đó kiểm tra tối thiểu: màn hình phổ biến 1366×768; dữ liệu bảng dài; trạng thái rỗng/lỗi; tab bằng bàn phím; permission bị từ chối; WebSocket reconnect; và cách hiển thị tiếng Việt trong PDF.

### 6.3.5. Tổng hợp mức độ hoạt động

| Phân hệ | Kết quả chính | Hạn chế cần công bố |
|---|---|---|
| Desktop CV | Đủ vòng đời, bảy signal, fusion, local log và report | FPS và độ ổn định phụ thuộc thiết bị/camera |
| Browser Extension | Có setup, policy, consent, preflight và browser event | Node không mô phỏng đầy đủ browser permission/service worker |
| Backend nền tảng | Đủ auth, tenant/RBAC, exam/session, evidence, review, report | Chưa thay thế pentest và kiểm thử tải production |
| Dashboard realtime | Có initial state, ticket WebSocket và fan-out cập nhật | Cần thử nghiệm nhiều proctor/nhiều process trên hạ tầng thật |
| Lưu trữ và báo cáo | SQL current state kết hợp JSONL/snapshot, report chạy nền | Cần đo dung lượng, retention và khôi phục dữ liệu dài hạn |
| Khả năng truy vết | Có request/audit, session ID, event ID, review và report job | Cần chuẩn hóa observability tập trung khi triển khai phân tán |

Tổng thể, hệ thống đạt mức **prototype tích hợp có thể trình diễn và kiểm thử đầu-cuối**. Kết luận này mạnh hơn một bản demo CV đơn lẻ vì đã có quản trị, phân quyền, realtime, evidence và reporting, nhưng thấp hơn mức “sẵn sàng triển khai diện rộng”. Để nâng mức trưởng thành cần thêm kiểm thử trình duyệt/thiết bị thật, load test nhiều phiên, kiểm thử bảo mật độc lập, giám sát vận hành và quy trình backup/restore.

## 6.4. Đánh giá hiệu năng pipeline

Benchmark có sẵn được chạy trên CPU, dùng 60 frame tổng hợp sau 5 frame warm-up. Nó đo chi phí suy luận và logic, không tính webcam I/O hoặc render UI. Kết quả:

| Thành phần | Thời gian trung bình | Tỉ lệ chi phí |
|---|---:|---:|
| MTCNN face detection | 28,95 ms/frame | 67% |
| YOLOv8 đã throttle | 10,32 ms/frame | 24% |
| MediaPipe Face Landmarker | 3,45 ms/frame | 8% |
| Preprocess | 0,21 ms/frame | <1% |
| Logic của bảy signal | khoảng 0,04 ms/frame | <1% |
| **Tổng** | **42,98 ms/frame** | **100%** |

Vòng lặp đo trực tiếp đạt khoảng 25,3 FPS. MTCNN là bottleneck chính; tầng Signal Extractor gần như không đáng kể vì chỉ xử lý đặc trưng dùng chung. Một lần `FaceEmbedder.extract()` mất khoảng 27,6 ms nhưng mặc định chỉ chạy mỗi 30 giây, nên chi phí khấu hao thấp dù có thể làm một frame bị giật tại thời điểm re-verification.

Kết quả này chứng minh pipeline có thể chạy gần thời gian thực trên máy benchmark, không phải cam kết FPS cho mọi thiết bị. Cần chạy lại `scripts/benchmark_fps.py` trên máy triển khai thật và với frame webcam đại diện.

## 6.5. Thiết kế thực nghiệm 25 video

### 6.5.1. Nguồn dữ liệu và provenance

Bộ đánh giá gồm 25 video tự quay và ground truth được tạo trong môi trường thực nghiệm bên ngoài repository. Bản tổng hợp kết quả ghi nhận 199.470 frame/mẫu đánh giá. Báo cáo cũ mô tả “gần một giờ ở 30 FPS”, nhưng con số này không nhất quán với tổng frame; vì không có metadata video gốc trong repository để kiểm tra lại, phiên bản báo cáo này chỉ công bố số video và số frame đã dùng trong confusion matrix.

Các nhóm kịch bản gồm:

- Hành vi bình thường.
- Sử dụng điện thoại/vật thể cấm.
- Quay đầu hoặc nhìn chuyển hướng.
- Nhiều người trong khung hình.
- Hoạt động miệng/nói chuyện.
- Đổi người trong phiên.

Ground truth nhị phân được gán theo frame: `0` là bình thường, `1` là có ít nhất một hành vi vi phạm. Theo quy trình thực nghiệm đã cung cấp, hai người gán nhãn độc lập và trường hợp không thống nhất được phân xử bởi người thứ ba. Dataset gốc và chỉ số đồng thuận giữa người gán nhãn không được lưu trong repository, vì vậy đây là giới hạn về khả năng kiểm tra độc lập.

### 6.5.2. Đơn vị và cách tính

Đơn vị đánh giá là **frame**, không phải số `ViolationEvent`. Ground truth frame được so với trạng thái dự đoán của hệ thống tại cùng thời điểm. Một khoảng cảnh báo kéo dài đóng góp nhiều predicted-positive frame dù engine chỉ sinh một event tại rising edge.

Việc đánh giá theo frame phù hợp để đo thời gian hệ thống ở trạng thái đúng/sai, nhưng các frame liên tiếp có tương quan cao. Vì vậy 199.470 frame không tương đương 199.470 mẫu độc lập. Khi chia train/validation/test hoặc so sánh model, cần chia theo clip/người thay vì trộn frame của cùng clip vào nhiều tập.

### 6.5.3. Baseline

Baseline mô phỏng logic điều kiện đơn giản:

```text
if không có khuôn mặt: cảnh báo
else if nhiều khuôn mặt: cảnh báo
else if EAR thấp đủ điều kiện: cảnh báo
else if có vật thể: cảnh báo
else: bình thường
```

Baseline không có kết hợp đồng thời nhiều tín hiệu, Identity, PnP đầy đủ hoặc hysteresis hai cấp tương đương. Nó được chạy trên cùng bộ test để tạo điểm so sánh.

### 6.5.4. Cấu hình thực nghiệm và cấu hình hiện tại

Tài liệu từ môi trường ngoài ghi nhận quá trình hiệu chỉnh ngưỡng hysteresis, trọng số, EAR và một checkpoint YOLOv8 fine-tuned cho điện thoại. Artifact checkpoint và biểu đồ epoch không nằm trong repository hiện tại. Repository bàn giao mặc định dùng `models/yolov8n.pt` pretrained COCO, trọng số chưa chuẩn hóa và `T_enter=5,0`, `T_exit=2,5`.

Do đó, các metric tại mục 6.6 được hiểu là kết quả của **snapshot thực nghiệm bên ngoài**, không phải phép đo có thể tái lập nguyên trạng chỉ bằng checkout repository hiện tại. Việc tái lập cần lưu thêm commit/config, checkpoint, manifest clip, ground truth và output dự đoán.

## 6.6. Kết quả định lượng

### 6.6.1. Confusion matrix

|  | Dự đoán bình thường | Dự đoán vi phạm | Tổng |
|---|---:|---:|---:|
| Ground truth bình thường | TN = 158.970 | FP = 10.500 | 169.470 |
| Ground truth vi phạm | FN = 4.500 | TP = 25.500 | 30.000 |
| **Tổng** | **163.470** | **36.000** | **199.470** |

Tỉ lệ frame vi phạm trong ground truth là:

$$
\frac{30.000}{199.470}=15,04\%
$$

Dataset mất cân bằng theo hướng frame bình thường chiếm đa số; vì vậy không chỉ dùng Accuracy để kết luận.

### 6.6.2. Các chỉ số suy ra

| Chỉ số | Công thức | Giá trị |
|---|---|---:|
| Accuracy | $(TP+TN)/N$ | 0,9248 |
| Precision | $TP/(TP+FP)$ | 0,7083 |
| Recall | $TP/(TP+FN)$ | 0,8500 |
| F1-score | $2PR/(P+R)$ | 0,7727 |
| Specificity | $TN/(TN+FP)$ | 0,9380 |
| False Positive Rate | $FP/(TN+FP)$ | 0,0620 |

Precision 0,7083 nghĩa là khoảng 70,83% predicted-positive frame trùng với ground truth vi phạm. Recall 0,8500 nghĩa là hệ thống nhận đúng 85% frame vi phạm. F1 0,7727 thể hiện điểm cân bằng giữa hai đại lượng.

Các mục tiêu thực nghiệm đặt trước là Precision ≥ 0,70, Recall ≥ 0,80 và F1 ≥ 0,75; snapshot này đạt cả ba. Kết quả cho thấy cấu hình có tiềm năng hỗ trợ review trong điều kiện dataset đã thu thập, nhưng chưa đủ để khẳng định sẵn sàng cho kỳ thi rủi ro cao hoặc quần thể người dùng rộng.

ROC-AUC và PR-AUC không được giữ trong bản sửa đổi. Hai chỉ số này cần score/curve ở nhiều ngưỡng; confusion matrix tại một ngưỡng không đủ để kiểm chứng các giá trị AUC từng ghi trong bản cũ.

## 6.7. So sánh với baseline

| Chỉ số | Baseline | Hệ thống thực nghiệm | Tăng tuyệt đối | Tăng tương đối |
|---|---:|---:|---:|---:|
| Precision | 0,6521 | 0,7083 | +0,0562 | +8,62% |
| Recall | 0,7230 | 0,8500 | +0,1270 | +17,57% |
| F1-score | 0,6851 | 0,7727 | +0,0876 | +12,79% |
| Specificity | 0,9128 | 0,9380 | +0,0252 | +2,76% |

Hệ thống thực nghiệm cao hơn baseline ở bốn chỉ số được báo cáo. Mức tăng lớn nhất về tuyệt đối nằm ở Recall, phù hợp với kỳ vọng rằng nhiều tín hiệu có trạng thái và Identity giúp giảm bỏ sót so với chuỗi điều kiện chỉ giữ một nhánh.

Tuy nhiên, so sánh chỉ công bằng nếu hai hệ thống dùng cùng input, cùng ground truth, cùng đơn vị frame và không fine-tune trên tập test. Do artifact chia tập không có trong repository, kết quả được báo cáo như bằng chứng thực nghiệm của đồ án, đồng thời giữ giới hạn về khả năng audit độc lập.

## 6.8. Độ trễ phát hiện

Môi trường thực nghiệm bên ngoài ghi nhận:

| Thống kê | Độ trễ |
|---|---:|
| Trung bình | 2,3 giây |
| Nhỏ nhất | 0,1 giây |
| Lớn nhất | 8,5 giây |
| Phân vị 95 | 5,2 giây |

Độ trễ là khoảng cách giữa thời điểm bắt đầu đoạn ground truth và thời điểm hệ thống chuyển sang cảnh báo. Nó chịu ảnh hưởng trực tiếp của debounce, cửa sổ state machine, chu kỳ model và hysteresis. Không nên diễn giải 2,3 giây như SLA chung cho mọi tín hiệu: Identity trong repository hiện chỉ re-verify định kỳ 30 giây, còn một số tín hiệu khác có thể phản ứng sau khoảng 1–2 giây.

Do file latency theo từng loại sự kiện không có trong repository, báo cáo chưa phân tích được median, phân bố theo signal hoặc confidence interval.

## 6.9. Phân tích lỗi

### 6.9.1. False Negative

Confusion matrix có 4.500 FN. Tài liệu phân tích bên ngoài đã phân loại 4.180 trường hợp; 320 trường hợp còn lại chưa có nhãn nguyên nhân chi tiết.

| Nguyên nhân trong phần đã phân loại | Số frame | Tỉ lệ trên 4.180 frame đã phân loại |
|---|---:|---:|
| Quay đầu nhẹ, chưa vượt điều kiện | 1.200 | 28,7% |
| Similarity Identity nằm trong vùng biên | 800 | 19,1% |
| Nhắm mắt quá ngắn | 650 | 15,6% |
| Ánh sáng xấu | 450 | 10,8% |
| Vật thể nhỏ/ở rìa ảnh | 400 | 9,6% |
| Nguyên nhân khác | 680 | 16,3% |

Các nhóm này cho thấy Recall không chỉ phụ thuộc model mà còn phụ thuộc định nghĩa ground truth. Ví dụ, nếu ground truth coi mọi lần quay nhẹ là vi phạm nhưng policy hệ thống chỉ cảnh báo sau một góc/thời lượng nhất định, một phần FN là khác biệt chính sách chứ không hoàn toàn là lỗi nhận diện.

### 6.9.2. False Positive

10.500 FP được phân loại như sau:

| Nguyên nhân | Số frame | Tỉ lệ FP |
|---|---:|---:|
| Quay đầu tự nhiên | 3.500 | 33,3% |
| Nhắm mắt tự nhiên/mệt | 2.100 | 20,0% |
| Object detection nhầm | 2.800 | 26,7% |
| Ánh sáng hoặc góc mặt | 1.200 | 11,4% |
| Khác | 900 | 8,6% |

Head Pose và object detection đóng góp lớn vào FP. Điều này phù hợp với giới hạn quan sát: quay đầu không đồng nghĩa nhìn tài liệu, còn YOLO pretrained/fine-tuned vẫn có thể nhầm vật thể. Vì vậy dashboard cần hiển thị ảnh và contributing signals thay vì chỉ hiện nhãn cuối.

## 6.10. Đe dọa đến tính hợp lệ

### 6.10.1. Tính hợp lệ nội tại

- Artifact gốc không nằm trong repository nên không thể chạy lại toàn bộ đánh giá trong môi trường hiện tại.
- Chưa có commit hash, seed và cấu hình đầy đủ của snapshot thực nghiệm.
- Chưa có bằng chứng về cách tách clip cho fine-tuning; nếu frame cùng video xuất hiện ở train và test, metric có thể lạc quan.
- Ground truth nhị phân gộp nhiều loại vi phạm, che khuất khác biệt giữa từng signal.
- Chưa báo Cohen's kappa hoặc thước đo đồng thuận giữa người gán nhãn.

### 6.10.2. Tính hợp lệ bên ngoài

- 25 video chưa đại diện đầy đủ cho camera, ánh sáng, màu da, kính, khẩu trang và thiết bị khác nhau.
- Dữ liệu do một nhóm nhỏ tự quay có thể khác hành vi trong kỳ thi thật.
- Metric frame-level bị chi phối bởi độ dài đoạn và tương quan giữa frame liên tiếp.
- Kết quả không chứng minh khả năng chống client bị sửa, camera ảo, replay hoặc deepfake.

### 6.10.3. Khả năng tái lập cần bổ sung

Một gói thực nghiệm hoàn chỉnh nên lưu:

```text
evaluation/
├── manifest.csv
├── labels/<clip>.labels.json
├── splits.json
├── config/fusion.yaml
├── model/checkpoint + hash
├── predictions/<clip>.jsonl
├── metrics.json
├── environment.txt
└── generate_figures.py
```

Ngoài dữ liệu nhạy cảm không thể công khai, có thể lưu hash và manifest để chứng minh artifact dùng trong tính toán không thay đổi.

## 6.11. Đánh giá theo tiêu chí nghiệm thu

| Nhóm yêu cầu | Bằng chứng | Kết luận |
|---|---|---|
| Pipeline và bảy signal | Unit, smoke, video integration test | Đạt về chức năng |
| Fusion, giải thích và report | State/rising-edge/report consistency test | Đạt về chức năng |
| Auth, RBAC và tenant isolation | API/WebSocket/security regression test | Đạt trong phạm vi test |
| Extension | 8 Node test và source review | Đạt phần logic tự động; cần test trình duyệt thật bổ sung |
| Hiệu năng local CV | Benchmark CPU tổng hợp khoảng 25,3 FPS | Đạt trên máy benchmark, không khái quát mọi thiết bị |
| Precision/Recall/F1 mục tiêu | 0,7083 / 0,8500 / 0,7727 | Đạt trên snapshot 25 video bên ngoài |
| Tái lập thực nghiệm | Artifact gốc không có trong repository | Chưa đạt đầy đủ |
| Lockdown/attestation | Ngoài phạm vi | Không đánh giá |

## 6.12. Kết chương

Chương 6 đã tách biệt kiểm thử phần mềm, đánh giá hoạt động hệ thống và đánh giá độ chính xác CV. Source hiện tại vượt qua 309 test Python và 8 test extension; các luồng quản trị, tham gia, realtime, evidence, review và report đạt trong phạm vi kiểm thử đã mô tả. Benchmark cho thấy pipeline đạt khoảng 25,3 FPS trên môi trường CPU đã đo. Trên snapshot thực nghiệm 25 video với 199.470 frame, hệ thống đạt Precision 0,7083, Recall 0,8500 và F1 0,7727, cao hơn baseline được báo cáo.

Kết quả thực nghiệm được giữ như bằng chứng từ môi trường ngoài, đồng thời báo cáo công khai các giới hạn: artifact chưa được bàn giao trong repository, cấu hình hiện tại không hoàn toàn trùng snapshot, và dataset còn nhỏ. Chương 7 sử dụng các kết quả này để kết luận ở mức phù hợp, không mở rộng thành tuyên bố sẵn sàng triển khai ở mọi kỳ thi.
