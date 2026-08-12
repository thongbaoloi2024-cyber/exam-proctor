# Chương 3. Khảo sát và phân tích yêu cầu

## 3.1. Tổng quan

Chương 2 đã trình bày các kỹ thuật nền tảng. Chương này khảo sát những hướng tiếp cận đang được sử dụng trong giám sát thi trực tuyến, phân tích một dự án mã nguồn mở làm đối chứng và chuyển các khoảng trống tìm được thành yêu cầu cụ thể cho hệ thống.

Phạm vi khảo sát không nhằm khẳng định một sản phẩm “tốt nhất”, vì mỗi giải pháp phục vụ mô hình thi, chính sách và ngân sách khác nhau. Mục tiêu là xác định các năng lực cần thiết, những giới hạn không thể giải quyết chỉ bằng một model CV và vị trí đóng góp của đồ án.

## 3.2. Khảo sát nhóm giải pháp thương mại

Các nền tảng thương mại thường cung cấp ba mô hình dịch vụ: giám sát tự động, ghi lại để con người xem sau và giám sát trực tiếp. Chức năng được cấu hình theo kỳ thi, có thể gồm xác minh người dự thi, ghi webcam/microphone/màn hình, hạn chế trình duyệt, phát hiện sự kiện và báo cáo.

### 3.2.1. Proctorio

Theo tài liệu sản phẩm chính thức, Proctorio cung cấp các nhóm thiết lập recording, verification và lockdown; có thể ghi video, audio, màn hình hoặc web traffic, xác minh danh tính, ép toàn màn hình, hạn chế tab, clipboard và thao tác khác tùy cấu hình của đơn vị tổ chức. Giải pháp sử dụng browser extension trên máy tính để bàn và chỉ kích hoạt trong phiên thi được cấu hình.

Điểm đáng chú ý đối với đồ án là cách tách policy của kỳ thi khỏi client. Mỗi kỳ thi có thể yêu cầu những năng lực khác nhau thay vì mọi phiên đều bật toàn bộ quyền. Tuy nhiên, đây là nền tảng đóng; báo cáo công khai không cung cấp đầy đủ logic nội bộ để tái hiện thuật toán hoặc hiệu chỉnh theo nghiên cứu của đồ án.

Nguồn khảo sát: [Proctorio Online Proctoring](https://proctorio.com/products/online-proctoring), [Secure Exam Proctor Extension](https://proctorio.com/support/hc/articles/1752083369562-proctorio-secure-exam-proctor-extension).

### 3.2.2. Honorlock

Honorlock cung cấp BrowserGuard để hạn chế hoặc đánh dấu truy cập website, tab, ứng dụng, phím tắt và hành vi thu nhỏ cửa sổ, đồng thời có thể ghi màn hình trong phiên thi. Mô hình này cho thấy giám sát trình duyệt là một nguồn tín hiệu riêng, bổ sung cho webcam và không nên bị đồng nhất với kết quả thị giác máy tính.

Nguồn khảo sát: [Honorlock BrowserGuard](https://honorlock.com/browserguard/).

### 3.2.3. ProctorU/Meazure Learning

Nền tảng ProctorU của Meazure Learning cung cấp các mức dịch vụ từ ghi hình và review đến giám sát trực tiếp có can thiệp. Khác biệt chính so với mô hình hoàn toàn tự động là con người tham gia xác minh, theo dõi và xử lý sự cố. Điều này củng cố nguyên tắc của đồ án: thuật toán nên ưu tiên và giải thích bằng chứng; quyết định cuối cùng thuộc về giám thị hoặc đơn vị tổ chức.

Nguồn khảo sát: [ProctorU Proctoring Platform](https://www.meazurelearning.com/exam-technology/proctoru-online-proctoring).

### 3.2.4. Nhận xét từ nhóm sản phẩm thương mại

Các sản phẩm thương mại cho thấy một hệ thống hoàn chỉnh cần nhiều hơn model phát hiện hành vi. Các năng lực chung gồm policy theo kỳ thi, kiểm tra thiết bị, trình duyệt an toàn, giám sát thời gian thực, review và báo cáo. Tuy nhiên, việc triển khai lại toàn bộ phạm vi của sản phẩm thương mại là không phù hợp với đồ án. Hệ thống đề xuất chọn một tập chức năng có thể kiểm chứng bằng source code, đồng thời công bố rõ giới hạn.

## 3.3. Khảo sát dự án mã nguồn mở đối chứng

Đồ án sử dụng dự án `AarambhTech/exam-cheating-detection` như một nguồn tham khảo và baseline về mặt ý tưởng, không sao chép mã nguồn. Dự án này kết hợp OpenCV, MediaPipe, MTCNN và YOLO để quan sát khuôn mặt, mắt, miệng và vật thể trong webcam.

Ưu điểm của giải pháp tham khảo là dễ tiếp cận, chạy cục bộ và minh họa được cách ghép nhiều thư viện CV. Qua rà soát mã nguồn và so sánh kỹ thuật, đồ án nhận thấy các hạn chế sau:

- Một số điều kiện được xử lý bằng chuỗi `if-elif`, làm mất thông tin khi nhiều bất thường xảy ra đồng thời.
- Các ngưỡng dựa trên số frame hoặc khoảng cách pixel phụ thuộc FPS, độ phân giải và khoảng cách camera.
- Độ mở miệng không được chuẩn hóa đầy đủ; có landmark cần được xác minh lại với API MediaPipe thực tế.
- Phần ước lượng hướng nhìn không cho ra yaw/pitch/roll theo mô hình hình học 3D.
- Không có bước face embedding để kiểm tra lại danh tính trong suốt phiên.
- Chưa hình thành lớp nền tảng nhiều tổ chức, phân quyền theo kỳ thi, WebSocket dashboard và quy trình evidence/review/report tương đương hệ thống đề xuất.

Nguồn dự án: [AarambhTech exam-cheating-detection](https://github.com/AarambhTech/exam-cheating-detection). Phân tích chi tiết từng khác biệt kỹ thuật được lưu trong tài liệu nội bộ `docs/SO_SANH_KY_THUAT_TUAN4.md`.

## 3.4. So sánh định hướng giải pháp

| Tiêu chí | Sản phẩm thương mại | Dự án mã nguồn mở đối chứng | Hệ thống của đồ án |
|---|---|---|---|
| Minh bạch thuật toán | Hạn chế do nền tảng đóng | Có thể đọc source | Source và cấu hình được kiểm soát trong repository |
| Webcam/CV | Có, tùy sản phẩm và policy | Một số tín hiệu đơn lẻ | Bảy tín hiệu và pipeline dùng chung |
| Xử lý theo thời gian | Không công bố đầy đủ | Chủ yếu ngưỡng/bộ đếm đơn giản | Debounce, cửa sổ trượt, state machine hai cấp |
| Xác thực trong phiên | Có thể có, chi tiết tùy sản phẩm | Không có embedding xuyên suốt | Enrollment, liveness cơ bản, re-verification định kỳ |
| Toàn vẹn trình duyệt | Thường có | Không phải trọng tâm | Extension và integrity score tách khỏi risk CV |
| Nhiều tổ chức và phân quyền | Có | Không | RBAC, tenant scope và assignment theo kỳ thi |
| Giám sát thời gian thực | Có | Chủ yếu hiển thị cục bộ | WebSocket dashboard theo kỳ thi |
| Evidence và review | Có | Báo cáo cơ bản | JSONL, snapshot, incident review, report job |
| Khả năng triển khai quy mô lớn | Sản phẩm hoàn chỉnh | Không đặt mục tiêu | Mức đồ án/triển khai có kiểm soát; còn giới hạn |
| Khả năng kiểm thử và thay đổi thuật toán | Không kiểm soát source | Có nhưng kiến trúc đơn giản | Interface, config tập trung và test nhiều tầng |

Từ bảng so sánh, đồ án không cạnh tranh về quy mô với nền tảng thương mại. Giá trị chính là một kiến trúc có thể giải thích, kiểm thử và nghiên cứu, đồng thời đi xa hơn script webcam đơn máy bằng lớp nền tảng vận hành.

## 3.5. Xác định tác nhân của hệ thống

Hệ thống có năm nhóm tác nhân chính:

| Tác nhân | Phạm vi trách nhiệm |
|---|---|
| System Admin | Quản lý nền tảng, tổ chức, quota, chính sách sàn, vận hành và nhật ký toàn cục; không mặc nhiên xem evidence |
| Organization Admin | Quản lý hồ sơ, thành viên, lời mời, policy và audit của một tổ chức |
| Exam Manager | Tạo kỳ thi; với assignment `owner/manager` có thể cấu hình, phân công và vận hành kỳ thi tương ứng |
| Proctor | Theo dõi dashboard, xem evidence, review sự cố, kết thúc phiên và xuất báo cáo theo assignment |
| Thí sinh | Xác thực/tham gia đúng kỳ thi, cấp quyền cần thiết và gửi dữ liệu của chính phiên |

Một tài khoản có thể thuộc nhiều tổ chức nhưng chỉ thao tác trong active organization. Quyền trên kỳ thi không suy ra từ role toàn tài khoản mà từ `ExamAssignment` của đúng kỳ thi.

## 3.6. Yêu cầu chức năng

### 3.6.1. Xác thực và tài khoản

| Mã | Yêu cầu |
|---|---|
| FR-AUTH-01 | Hệ thống cho phép nhân sự đăng nhập và đăng xuất bằng phiên được bảo vệ. |
| FR-AUTH-02 | System Admin phải hoàn tất MFA trước khi vai trò hệ thống có hiệu lực. |
| FR-AUTH-03 | Hệ thống phân biệt token nhân sự, token phiên thí sinh, device token và WebSocket ticket. |
| FR-AUTH-04 | Thay đổi trạng thái tài khoản, membership hoặc assignment phải làm quyền cũ mất hiệu lực. |
| FR-AUTH-05 | Hệ thống hỗ trợ thí sinh tham gia theo chế độ thủ công hoặc Google OIDC tùy policy kỳ thi. |

### 3.6.2. Quản lý tổ chức và chính sách

| Mã | Yêu cầu |
|---|---|
| FR-ORG-01 | System Admin quản lý tổ chức, trạng thái, quota phiên đồng thời và retention trong phạm vi được cấp. |
| FR-ORG-02 | Organization Admin quản lý hồ sơ tổ chức, thành viên, role, invitation và audit log. |
| FR-ORG-03 | Người dùng thuộc nhiều tổ chức có thể chuyển active organization an toàn. |
| FR-ORG-04 | Policy hiệu lực phải được resolve theo thứ tự sàn nền tảng → tổ chức → kỳ thi; cấp dưới không được làm yếu yêu cầu bắt buộc. |
| FR-ORG-05 | System Admin chỉ đọc evidence khi có quyền ngoại lệ được phê duyệt, đúng tổ chức, còn hạn và chỉ đọc. |

### 3.6.3. Quản lý kỳ thi

| Mã | Yêu cầu |
|---|---|
| FR-EXAM-01 | Exam Manager tạo kỳ thi và trở thành owner của kỳ thi đó. |
| FR-EXAM-02 | Kỳ thi hỗ trợ lifecycle `draft`, `scheduled`, `open`, `closed`, `archived` và chỉ cho phép transition hợp lệ. |
| FR-EXAM-03 | Mã tham gia phải có thời hạn, có thể xoay và không tự thay đổi lifecycle ngoài ý muốn. |
| FR-EXAM-04 | Owner/manager phân công `owner`, `manager`, `proctor` với trạng thái và thời hạn. |
| FR-EXAM-05 | Hành động trên giao diện và backend phải dựa trên capability của từng kỳ thi. |
| FR-EXAM-06 | Cập nhật kỳ thi phải hỗ trợ optimistic locking để phát hiện chỉnh sửa đồng thời. |
| FR-EXAM-07 | Hệ thống cung cấp readiness checklist từ lịch, policy, mã tham gia, nhân sự và quota. |

### 3.6.4. Tham gia và giám sát phiên thi

| Mã | Yêu cầu |
|---|---|
| FR-SESSION-01 | Thí sinh chỉ tham gia kỳ thi đang cho phép join, bằng mã còn hạn và policy đã resolve. |
| FR-SESSION-02 | Extension kiểm tra phiên bản, consent và quyền camera/microphone/screen share theo policy trước khi monitor. |
| FR-CV-01 | Desktop client xử lý webcam thành đủ bảy `SignalResult` theo interface chung. |
| FR-CV-02 | Enrollment thu nhiều frame, yêu cầu liveness cơ bản nếu được cấu hình và tạo embedding tham chiếu. |
| FR-CV-03 | Mỗi tín hiệu phải ổn định dữ liệu theo thời gian trước khi thay đổi state. |
| FR-CV-04 | Risk Fusion Engine tính risk score từ cấu hình, áp dụng hysteresis cấp phiên và chỉ sinh event ở cạnh lên. |
| FR-BROWSER-01 | Extension ghi nhận focus/tab, fullscreen, clipboard, camera, microphone, screen share và trạng thái monitor. |
| FR-BROWSER-02 | Backend tự xác định severity và integrity từ browser event theo policy, không tin điểm client tự khai báo. |
| FR-SESSION-03 | Hệ thống hỗ trợ heartbeat, trạng thái `pending/active/disconnected/ended` và lý do mất kết nối. |

### 3.6.5. Dashboard, evidence và báo cáo

| Mã | Yêu cầu |
|---|---|
| FR-RT-01 | Dashboard nhận cập nhật phiên theo thời gian thực qua WebSocket trong đúng phạm vi kỳ thi. |
| FR-RT-02 | Backend kiểm tra schema, đủ bảy tín hiệu, thời gian, risk/state/severity và contribution trước khi chấp nhận dữ liệu CV. |
| FR-EVID-01 | Hệ thống lưu metadata, signal, transition, risk timeline, browser event, violation và snapshot theo phiên. |
| FR-EVID-02 | Snapshot phải được giới hạn định dạng/kích thước, kiểm tra nội dung và lưu bằng tên do server sinh. |
| FR-REVIEW-01 | Giám thị có thể ghi trạng thái và ghi chú review mà không sửa sự kiện máy gốc. |
| FR-REPORT-01 | Hệ thống sinh báo cáo HTML/PDF từ dữ liệu phiên, kể cả khi một phần log bị thiếu. |
| FR-REPORT-02 | Report job chạy nền và cho biết trạng thái xử lý/lỗi/kết quả. |
| FR-RET-01 | Tác vụ retention hỗ trợ dry-run trước khi xóa/ẩn danh dữ liệu hết hạn và phải ghi audit. |

## 3.7. Yêu cầu phi chức năng

| Mã | Nhóm | Yêu cầu |
|---|---|---|
| NFR-SEC-01 | Bảo mật | Mọi REST, WebSocket và file download phải kiểm tra authentication, tenant và resource scope tại backend. |
| NFR-SEC-02 | Bảo mật | Không đặt bearer token dài hạn trong URL WebSocket; ticket browser phải ngắn hạn và dùng một lần. |
| NFR-SEC-03 | Bảo mật | Message, ảnh và metadata từ client phải được coi là đầu vào không tin cậy và được kiểm tra chặt. |
| NFR-SEC-04 | Bảo mật | Giao diện phải hạn chế XSS, clickjacking, MIME sniffing và rò rỉ referrer bằng CSP/security header phù hợp. |
| NFR-PRIV-01 | Riêng tư | Không truyền video liên tục; chỉ gửi telemetry theo lô và snapshot tại sự kiện cần bằng chứng. |
| NFR-PRIV-02 | Riêng tư | Không lưu access token/refresh token Google; chỉ lưu claim OIDC tối thiểu và token dạng hash khi có thể. |
| NFR-REL-01 | Tin cậy | Một detector lỗi tạm thời không được làm crash toàn bộ phiên CV. |
| NFR-REL-02 | Tin cậy | Client mất mạng phải được đánh dấu disconnected; desktop CV vẫn có khả năng ghi log/báo cáo cục bộ. |
| NFR-PERF-01 | Hiệu năng | Detector nền dùng chung chỉ chạy một lần cho mỗi frame; YOLO được throttle theo thời gian. |
| NFR-PERF-02 | Hiệu năng | Telemetry mạng được gửi theo lô, mặc định khoảng một giây, không commit database ở mọi frame. |
| NFR-MAIN-01 | Bảo trì | Ngưỡng và trọng số thuật toán phải tập trung trong cấu hình có kiểm tra hợp lệ. |
| NFR-MAIN-02 | Bảo trì | Signal Extractor, data schema và authorization phải có interface/quy tắc tập trung và kiểm thử hồi quy. |
| NFR-EXPL-01 | Giải thích | Mỗi cảnh báo phải truy được risk score, state, tín hiệu đóng góp, thời gian và evidence liên quan. |
| NFR-PORT-01 | Triển khai | Backend có thể chạy local development hoặc Docker Compose; dữ liệu bền vững qua volume phù hợp. |
| NFR-TEST-01 | Kiểm thử | Chức năng lõi phải có unit/integration test; metric CV phải công bố dataset, ground truth và đơn vị đánh giá. |

## 3.8. Ràng buộc và giả định

Các ràng buộc chính của đồ án gồm:

- Model CV nền là pretrained; tài nguyên không cho phép huấn luyện toàn bộ model từ đầu.
- Camera intrinsic không được hiệu chuẩn riêng cho mọi thiết bị, vì vậy PnP sử dụng xấp xỉ camera matrix.
- Desktop CV và browser extension là hai nhánh client; native bridge hợp nhất hoàn toàn hai nhánh trong cùng session chưa thuộc phiên bản hiện tại.
- Connection manager WebSocket hoạt động in-process khi không cấu hình Redis; triển khai nhiều worker phải bật Redis lease/pub-sub như cấu hình Docker Compose hoặc dùng message broker tương đương.
- Dữ liệu sinh tổng hợp dùng để kiểm thử dashboard/report không thay thế bộ video thật trong đánh giá accuracy.
- Bộ 25 video, ground truth và artifact đánh giá nằm ở môi trường thực nghiệm khác, không nằm trong repository bàn giao hiện tại.
- Kết quả tự động chỉ là chỉ báo để review, không phải kết luận kỷ luật.

## 3.9. Tiêu chí nghiệm thu và truy vết

Các yêu cầu được coi là hoàn thành khi có implementation và bằng chứng kiểm tra tương ứng. Bảng 3.1 tóm tắt tuyến truy vết ở cấp nhóm.

| Nhóm yêu cầu | Giải pháp/đóng góp | Thành phần cài đặt | Bằng chứng đánh giá |
|---|---|---|---|
| `FR-CV-*`, `NFR-PERF-*` | Pipeline dùng chung và bảy signal | `src/perception`, `src/signals`, `src/orchestrator.py` | Unit test, model smoke test, video integration, benchmark |
| `FR-CV-04`, `NFR-EXPL-01` | State machine và risk fusion hai cấp | `src/fusion`, `config/fusion.yaml` | Test transition, rising edge, multi-signal, report consistency |
| `FR-BROWSER-*`, `FR-RT-*` | Extension và WebSocket validation | `extension/`, `backend/routers/ws.py` | Extension test, WebSocket integration và auth test |
| `FR-AUTH-*`, `FR-ORG-*`, `FR-EXAM-*` | RBAC và tenant/resource scope | `backend/auth.py`, `authorization.py`, `policies.py` | API, MFA, policy, tenant-isolation và assignment test |
| `FR-EVID-*`, `FR-REPORT-*`, `FR-RET-01` | Dữ liệu lai và chu trình evidence | `session_materializer.py`, `src/reporting`, report worker/retention script | Snapshot, traversal, report và background-job test |
| Metric CV | Đánh giá trên 25 video | Pipeline/baseline trong môi trường thực nghiệm | Confusion matrix, Precision, Recall, F1 và latency tại Chương 6 |

Chi tiết giải pháp được trình bày trong Chương 4, implementation trong Chương 5 và kết quả trong Chương 6.

## 3.10. Kết chương

Chương 3 đã chỉ ra rằng nền tảng thương mại có quy trình vận hành hoàn chỉnh nhưng khó kiểm chứng thuật toán, trong khi dự án mã nguồn mở dễ khảo sát nhưng thường thiếu xử lý theo thời gian, phân quyền và chu trình evidence. Từ đó, chương đã xác định năm tác nhân, các yêu cầu chức năng theo từng miền, yêu cầu phi chức năng, ràng buộc và tuyến truy vết.

Chương 4 tiếp theo trình bày các giải pháp và đóng góp được thiết kế để đáp ứng những yêu cầu này, trong đó mỗi đóng góp được phân tích theo bài toán, giải pháp và kết quả đạt được.
