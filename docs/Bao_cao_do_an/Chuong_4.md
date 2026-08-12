# Chương 4. Thiết kế giải pháp và các đóng góp

## Mở đầu chương

Các chương trước đã trình bày cơ sở lý thuyết của MTCNN, MediaPipe Face Landmarker, YOLOv8, FaceNet, bài toán ước lượng góc quay đầu và nguyên lý kết hợp đa tín hiệu; đồng thời xác định các yêu cầu `FR-*` và `NFR-*` của hệ thống. Vì vậy, chương này không lặp lại cách hoạt động của từng mô hình, mà tập trung vào các vấn đề kỹ thuật đã xuất hiện khi xây dựng một hệ thống giám sát thi hoàn chỉnh và những giải pháp đã được thiết kế, cài đặt để giải quyết các vấn đề đó.

Đóng góp của đồ án không nằm ở việc huấn luyện một mô hình thị giác máy tính mới, mà ở cách tổ chức các mô hình có sẵn thành chuỗi xử lý có trạng thái; kết hợp kết quả thị giác máy tính với dữ liệu toàn vẹn trình duyệt; và xây dựng lớp nền tảng nhiều tổ chức để truyền trạng thái, quản lý bằng chứng và tạo báo cáo có thể truy vết. Mỗi giải pháp trong chương được trình bày theo ba nội dung: bài toán đặt ra, giải pháp thực hiện và kết quả đã được kiểm chứng. Quan hệ giữa giải pháp và yêu cầu được tóm tắt tại mục 4.8.

## 4.1. Giải pháp kiến trúc tổng thể cho hệ thống giám sát thi

### 4.1.1. Bài toán và yêu cầu kiến trúc

Một chương trình chỉ đọc webcam và hiển thị nhãn bất thường chưa đủ để vận hành một kỳ thi. Hệ thống thực tế phải đồng thời giải quyết nhiều nhóm yêu cầu: xử lý hình ảnh tại máy thí sinh; giám sát các thao tác trong trình duyệt; xác thực và phân quyền người dùng; quản lý tổ chức, kỳ thi và phiên thi; chuyển trạng thái đến giám thị theo thời gian thực; lưu bằng chứng; và tổng hợp báo cáo sau kỳ thi.

Nhóm vấn đề này tương ứng với các yêu cầu `FR-SESSION-*`, `FR-RT-*`, `FR-EVID-*`, `FR-REPORT-*`, `NFR-PRIV-*` và `NFR-PORT-01` tại Chương 3.

Nếu ghép toàn bộ trách nhiệm vào một chương trình đơn khối, ba vấn đề sẽ xuất hiện. Thứ nhất, các mô hình thị giác máy tính có chi phí tính toán lớn và không phù hợp để chạy đồng bộ trong dịch vụ phía máy chủ phục vụ nhiều người dùng. Thứ hai, truyền video liên tục làm tăng băng thông, chi phí lưu trữ và phạm vi xử lý dữ liệu nhạy cảm. Thứ ba, giao diện quản trị, dữ liệu phiên và thuật toán nhận diện bị phụ thuộc chặt vào nhau, gây khó khăn cho kiểm thử và mở rộng.

### 4.1.2. Giải pháp

Đồ án tách hệ thống thành ba thành phần triển khai chính:

- **Ứng dụng máy tính để bàn bằng Python** thực hiện chuỗi xử lý thị giác máy tính trên webcam, đăng ký khuôn mặt, kiểm tra sự hiện diện sống cơ bản, tính bảy tín hiệu và tổng hợp điểm rủi ro ngay tại máy thí sinh.
- **Tiện ích mở rộng trình duyệt** quản lý luồng tham gia kỳ thi, kiểm tra chính sách thiết bị và ghi nhận các sự kiện như rời chế độ toàn màn hình, chuyển thẻ, mất trạng thái tập trung, thao tác với bảng tạm, hoặc dừng camera/chia sẻ màn hình.
- **Dịch vụ FastAPI và bảng điều khiển** quản lý tổ chức, tài khoản, kỳ thi, phiên thi, phân quyền, kết nối WebSocket, lưu bằng chứng, hỗ trợ giám thị hậu kiểm sự cố và tạo báo cáo.

Kiến trúc tổng thể được minh họa ở Hình 4.1. Sơ đồ phân biệt bốn vùng trách nhiệm: thu thập và xử lý tại máy thí sinh; tiếp nhận, kiểm chứng và điều phối tại nền tảng; lưu trữ dữ liệu; và khai thác dữ liệu qua các giao diện vận hành. Các đường kết nối cũng cho thấy REST được dùng cho nghiệp vụ có trạng thái, còn WebSocket phục vụ dữ liệu giám sát, nhịp kết nối và cập nhật bảng điều khiển theo thời gian thực.

![Kiến trúc tổng thể hệ thống giám sát thi](image/kien_truc_tong_the_he_thong.svg)

**Hình 4.1. Kiến trúc tổng thể của hệ thống**

Quyết định quan trọng của kiến trúc là không truyền luồng video liên tục đến máy chủ. Ứng dụng phía thí sinh chỉ gửi dữ liệu giám sát đã gom theo chu kỳ, mặc định một giây, cùng ảnh chụp tại thời điểm có sự kiện cần làm bằng chứng. Máy chủ không chạy mô hình CV nhưng cũng không tin hoàn toàn dữ liệu từ máy khách: thông điệp phải đúng lược đồ và chứa đủ bảy tín hiệu; điểm rủi ro, trạng thái, mức nghiêm trọng và tín hiệu đóng góp được tính lại hoặc đối chiếu trước khi lưu và chuyển tiếp.

### 4.1.3. Kết quả đạt được

Kiến trúc trên tạo ranh giới rõ ràng giữa xử lý nhận diện, giám sát trình duyệt, vận hành nền tảng và lưu trữ. Chuỗi xử lý CV vẫn có thể chạy cục bộ khi máy chủ không khả dụng; dịch vụ phía máy chủ và bảng điều khiển không phụ thuộc vào thư viện học sâu; giao diện giám thị chỉ nhận dữ liệu cần thiết thay vì video liên tục. Cách phân tách này giúp giảm băng thông và thu hẹp phạm vi dữ liệu hình ảnh truyền qua mạng.

Hệ thống hiện có hai nhánh phía máy khách: ứng dụng CV trên máy tính để bàn và tiện ích mở rộng trình duyệt. Tuy nhiên, hai nhánh chưa được hợp nhất hoàn toàn vào cùng một phiên bằng cầu nối native messaging. Kiến trúc đã có các hợp đồng dữ liệu chung, nhưng việc phối hợp đồng thời ứng dụng CV và tiện ích mở rộng trong một phiên vẫn là hướng phát triển tiếp theo.

## 4.2. Giải pháp mô hình hóa tác nhân, ca sử dụng và phân quyền

### 4.2.1. Bài toán quản lý nhiều phạm vi người dùng

Trong một hệ thống giám sát thi, “quản trị viên” không phải là một vai trò duy nhất. Người quản trị nền tảng cần quản lý tổ chức nhưng không nên mặc nhiên xem dữ liệu nhạy cảm của thí sinh. Quản trị viên tổ chức cần quản lý thành viên và chính sách nhưng không nhất thiết vận hành kỳ thi. Người tạo kỳ thi, người quản lý kỳ thi và giám thị lại có quyền khác nhau trên từng kỳ thi cụ thể. Ngoài ra, thí sinh chỉ được truy cập đúng phiên của mình, không dùng chung cơ chế xác thực với nhân sự quản trị.

Nếu chỉ kiểm tra một trường `role` toàn cục, một người là quản lý ở kỳ thi A có thể bị hiển thị nhầm quyền quản lý ở kỳ thi B, hoặc người thuộc tổ chức này có thể suy đoán sự tồn tại của tài nguyên thuộc tổ chức khác.

Giải pháp tại mục này đáp ứng các nhóm `FR-AUTH-*`, `FR-ORG-*`, `FR-EXAM-04`, `FR-EXAM-05` và `NFR-SEC-01`.

### 4.2.2. Giải pháp

Đồ án xây dựng kiểm soát truy cập theo ba bước: xác thực danh tính, xác định phạm vi và kiểm tra năng lực trên tài nguyên. Các vai trò và ca sử dụng chính được thể hiện ở Hình 4.2. Ranh giới ca sử dụng mô tả chức năng người dùng nhìn thấy; quyền thực thi cuối cùng vẫn do máy chủ quyết định theo tổ chức, kỳ thi và tài nguyên cụ thể.

![Ca sử dụng tổng quan theo vai trò](image/use_case_tong_quan_he_thong.svg)

**Hình 4.2. Các ca sử dụng theo vai trò của hệ thống**

#### 4.2.2.1. Danh mục tác nhân và ca sử dụng

Để tránh hiểu sơ đồ như một danh sách quyền toàn cục, các ca sử dụng được định danh và gắn với phạm vi tài nguyên cụ thể. Một người có thể đồng thời mang nhiều vai trò, nhưng mỗi thao tác chỉ hợp lệ khi vai trò đó còn hiệu lực trong đúng phạm vi tổ chức hoặc kỳ thi.

| Mã | Ca sử dụng | Tác nhân chính | Phạm vi | Kết quả đầu ra |
|---|---|---|---|---|
| `UC-01` | Quản trị nền tảng | System Admin | Toàn hệ thống | Tổ chức, quota, system policy và audit được cập nhật |
| `UC-02` | Quản trị tổ chức | Organization Admin | Một tổ chức | Thành viên, invitation, policy và access grant được quản lý |
| `UC-03` | Tạo và cấu hình kỳ thi | Exam Manager/Owner | Một kỳ thi | Exam, join code, thời gian, policy và assignment hợp lệ |
| `UC-04` | Kiểm tra readiness và mở kỳ thi | Exam Manager/Owner | Một kỳ thi | Danh sách điều kiện đạt/chưa đạt; trạng thái kỳ thi được chuyển hợp lệ |
| `UC-05` | Tham gia và xác thực thí sinh | Candidate | Một kỳ thi/phiên | Candidate identity, session token và policy hiệu lực |
| `UC-06` | Khởi tạo giám sát thiết bị | Candidate | Phiên của chính mình | Consent, preflight, enrollment/liveness và client connection |
| `UC-07` | Theo dõi phiên thời gian thực | Proctor, Exam Manager | Kỳ thi được phân công | KPI, session state, risk, integrity và cảnh báo mới nhất |
| `UC-08` | Xem evidence và review sự cố | Proctor có capability | Phiên được phân công | Verdict và ghi chú review, không sửa sự kiện gốc |
| `UC-09` | Kết thúc phiên | Candidate hoặc nhân sự có quyền | Một phiên | Trạng thái kết thúc và lý do được ghi nhận |
| `UC-10` | Sinh và tải báo cáo | Exam Manager/Proctor có capability | Một phiên/kỳ thi | Report job và tệp HTML/PDF có thể truy vết |

Quan hệ tác nhân–ca sử dụng không thay thế kiểm tra capability. Ví dụ, `UC-08` chỉ khả dụng nếu Proctor có `exam.evidence.read` trên đúng kỳ thi; System Admin muốn đọc evidence phải có access grant còn hiệu lực thay vì dựa vào vai trò hệ thống.

#### 4.2.2.2. Đặc tả các ca sử dụng cốt lõi

**UC-03 – Tạo và cấu hình kỳ thi**

| Thuộc tính | Nội dung |
|---|---|
| Tác nhân | Exam Owner hoặc Exam Manager có `exam.manage` |
| Tiền điều kiện | Người dùng đã đăng nhập; tổ chức và membership đang hoạt động; quota cho phép |
| Luồng chính | Mở Exam workspace → nhập metadata và thời gian → chọn phương thức xác thực → cấu hình policy → phân công nhân sự → lưu phiên bản cấu hình |
| Luồng thay thế/ngoại lệ | Dữ liệu sai miền bị từ chối; policy yếu hơn sàn hệ thống/tổ chức không được lưu; xung đột phiên bản trả lỗi optimistic locking |
| Hậu điều kiện | Kỳ thi ở trạng thái cấu hình, có policy hiệu lực và danh sách assignment có phạm vi rõ ràng |

**UC-05/UC-06 – Tham gia và khởi tạo giám sát**

| Thuộc tính | Nội dung |
|---|---|
| Tác nhân | Candidate |
| Tiền điều kiện | Join code còn hạn; kỳ thi cho phép tham gia; thiết bị có trình duyệt/desktop client phù hợp |
| Luồng chính | Nhập join code → nhận thông tin và policy → xác thực thủ công hoặc Google → xác nhận consent → chạy preflight → tạo phiên và nhận session token → thực hiện enrollment/liveness nếu dùng desktop CV → mở kênh WebSocket |
| Luồng thay thế/ngoại lệ | Mã sai/hết hạn, kỳ thi chưa mở, consent thiếu, quyền camera/screen share bị từ chối hoặc liveness thất bại thì phiên không chuyển sang giám sát đầy đủ |
| Hậu điều kiện | Phiên thuộc đúng candidate/exam; client chỉ gửi dữ liệu bằng token của phiên đó; trạng thái thiết bị được quan sát trên dashboard |

**UC-07 – Theo dõi phiên thời gian thực**

| Thuộc tính | Nội dung |
|---|---|
| Tác nhân | Proctor hoặc Exam Manager được phân công |
| Tiền điều kiện | Người dùng đã đăng nhập và có `exam.monitor`; kỳ thi tồn tại trong tenant hiện hành |
| Luồng chính | Mở dashboard → tải current state qua REST → lấy WebSocket ticket dùng một lần → nhận telemetry/browser event đã kiểm chứng → lọc và mở session detail |
| Luồng thay thế/ngoại lệ | Ticket hết hạn hoặc đã dùng bị từ chối; khi socket mất kết nối, giao diện phải báo dữ liệu có thể cũ và thực hiện kết nối lại |
| Hậu điều kiện | Người giám thị quan sát được risk, integrity, kết nối và cảnh báo mà không truy cập phiên ngoài assignment |

**UC-08 – Review evidence**

| Thuộc tính | Nội dung |
|---|---|
| Tác nhân | Proctor có quyền đọc evidence/review |
| Tiền điều kiện | Phiên thuộc kỳ thi được phân công; snapshot và log đã qua kiểm tra đường dẫn/phạm vi |
| Luồng chính | Mở session detail → chọn sự kiện trên timeline → xem contributing signals, browser event và snapshot → nhập verdict/ghi chú → xác nhận review |
| Luồng thay thế/ngoại lệ | Evidence thiếu vẫn hiển thị metadata còn lại; truy cập chéo tenant hoặc đường dẫn ngoài thư mục phiên bị từ chối |
| Hậu điều kiện | `IncidentReview` mới được tạo và audit; `ViolationEvent` nguyên bản không bị thay đổi |

**UC-10 – Sinh báo cáo**

| Thuộc tính | Nội dung |
|---|---|
| Tác nhân | Exam Manager hoặc Proctor có `exam.reports.export` |
| Tiền điều kiện | Phiên tồn tại; người dùng có quyền trên kỳ thi; dữ liệu phiên đã được materialize |
| Luồng chính | Yêu cầu báo cáo → tạo job `pending` → worker đọc SQL và evidence → tổng hợp/charts → xuất HTML/PDF → job chuyển `completed` |
| Luồng thay thế/ngoại lệ | File evidence thiếu được đọc theo chế độ tolerant; lỗi dựng báo cáo chuyển job sang `failed` và lưu lỗi, không công bố output chưa hoàn chỉnh |
| Hậu điều kiện | Báo cáo được gắn đúng session, có đường dẫn do server quản lý và có thể tải theo authorization |

Ở tầng dữ liệu, quyền được biểu diễn bởi ba loại quan hệ:

- `SystemRole` gán vai trò `system_admin` ngoài phạm vi một tổ chức.
- `OrganizationMembership` gán `org_admin` hoặc `exam_manager` trong một tổ chức đang hoạt động.
- `ExamAssignment` gán `owner`, `manager` hoặc `proctor` trên từng kỳ thi.

Backend không phân quyền bằng các câu lệnh điều kiện rải rác trong từng API. Các capability như `exam.manage`, `exam.monitor`, `exam.evidence.read` và `exam.reports.export` được giải quyết tập trung. Khi truy cập một kỳ thi hoặc phiên, hệ thống kiểm tra đồng thời trạng thái tài khoản, tổ chức hiện hành, membership, assignment, thời hạn và loại hành động. Tài nguyên ngoài tenant hoặc kỳ thi chưa được phân công thường trả về `404` để hạn chế tiết lộ sự tồn tại; trường hợp đã đúng phạm vi nhưng thiếu capability trả về `403`.

System Admin phải bật MFA mới có vai trò hệ thống hiệu lực. Vai trò này không có đường truy cập mặc định đến evidence của thí sinh. Khi cần hỗ trợ sự cố, người quản trị phải có `AccessGrant` chỉ đọc, thuộc đúng tổ chức, còn thời hạn và chưa bị thu hồi. Thao tác nhạy cảm được liên kết với `AuditLog` để lưu chủ thể, phạm vi, hành động, kết quả, lý do, request ID và trạng thái trước/sau.

Thí sinh được tách khỏi bảng tài khoản nhân sự. Chế độ thủ công tạo phiên từ mã dự thi và thông tin thí sinh; chế độ Google chỉ lưu các thuộc tính OIDC tối thiểu trong `CandidateIdentity`, không lưu mã truy cập hoặc mã làm mới của Google. Mã xác thực phiên thí sinh và mã xác thực người dùng có loại riêng, không thể dùng thay thế cho nhau.

Các ca sử dụng được triển khai theo nguyên tắc “quyền tối thiểu”: System Admin quản lý mặt bằng nền tảng nhưng không mặc nhiên đọc evidence; Organization Admin quản lý phạm vi tổ chức; Exam Manager chịu trách nhiệm cấu hình và vòng đời kỳ thi; Proctor tập trung vào giám sát, review và báo cáo; Candidate chỉ tham gia và gửi dữ liệu của phiên đã xác thực. Việc tách nhiệm vụ này giảm khả năng một vai trò vừa tạo chính sách, vừa vận hành, vừa tự xác nhận kết quả mà không có dấu vết audit.

### 4.2.3. Kết quả đạt được

Giải pháp đã tạo được mô hình quản trị đa tổ chức và giới hạn quyền theo từng tài nguyên. Một Exam Manager chỉ liệt kê được các kỳ thi mình được phân công; vai trò manager ở kỳ thi này không làm phát sinh quyền quản lý ở kỳ thi khác. Organization Admin được tách khỏi công việc vận hành kỳ thi, còn System Admin chỉ đọc dữ liệu giám sát khi có quyền ngoại lệ hợp lệ.

Các trường hợp cô lập tenant, thu hồi role/assignment, nhầm loại token, quyền WebSocket và quyền trên từng kỳ thi đã được đưa vào kiểm thử hồi quy. Nhờ đó, phân quyền không chỉ tồn tại ở giao diện mà được thực thi tại backend đối với REST, WebSocket và thao tác tải tệp.

## 4.3. Giải pháp pipeline nhận thức và trích xuất tín hiệu dùng chung

### 4.3.1. Bài toán xử lý nhiều mô hình trên mỗi khung hình

Bảy tín hiệu giám sát không hoàn toàn độc lập về dữ liệu đầu vào. Face Presence, Multi-face và Identity cần vùng khuôn mặt; Eye State, Mouth State và Head Pose cần landmark; Object Presence cần kết quả phát hiện vật thể. Nếu mỗi tín hiệu tự tải mô hình và tự xử lý lại khung hình, cùng một phép phát hiện sẽ chạy nhiều lần, làm giảm tốc độ và khiến các tín hiệu sử dụng kết quả không đồng nhất về thời điểm.

Đây là bài toán trung tâm của `FR-CV-01`, `NFR-PERF-01`, `NFR-REL-01` và `NFR-MAIN-02`.

Ngoài ra, YOLOv8 có chi phí lớn hơn các bước xử lý còn lại. Chạy YOLO ở mọi frame gây lãng phí tài nguyên, nhưng nếu bỏ trống kết quả ở các frame không chạy model thì bộ đếm thời gian xuất hiện vật thể sẽ bị ngắt sai.

### 4.3.2. Giải pháp

Pipeline được tổ chức thành ba tầng xử lý nội bộ, minh họa ở Hình 4.3.

```mermaid
flowchart TB
    F["Khung hình BGR"] --> PRE["Tiền xử lý\nresize, BGR → RGB"]

    subgraph P["Tầng nhận thức dùng chung"]
        PRE --> MTCNN["MTCNN\nface boxes và số khuôn mặt"]
        PRE --> MESH["MediaPipe FaceMesh\nlandmark khuôn mặt"]
        PRE --> YOLO["YOLOv8n-COCO\ncell phone, book\nthrottle theo thời gian"]
        MTCNN --> PR["PerceptionResult"]
        MESH --> PR
        YOLO --> PR
    end

    subgraph S["Bảy bộ trích xuất tín hiệu"]
        PR --> S1["FACE_PRESENCE"]
        PR --> S2["MULTI_FACE"]
        PR --> S3["EYE_STATE"]
        PR --> S4["MOUTH_STATE"]
        PR --> S5["OBJECT_PRESENCE"]
        PR --> S6["HEAD_POSE"]
        PR --> S7["IDENTITY"]
    end

    S1 --> SR["Danh sách SignalResult\nname, value, confidence, threshold, metadata"]
    S2 --> SR
    S3 --> SR
    S4 --> SR
    S5 --> SR
    S6 --> SR
    S7 --> SR
    SR --> RF["Risk Fusion Engine"]
```

**Hình 4.3. Kiến trúc pipeline thị giác máy tính**

Tầng nhận thức chỉ chạy mỗi detector một lần rồi đóng gói dữ liệu vào `PerceptionResult`. Mọi Signal Extractor tuân theo cùng hợp đồng `process(PerceptionResult) -> SignalResult`. Nhờ hợp đồng này, thuật toán từng tín hiệu có thể phát triển và kiểm thử độc lập với camera và model thật.

YOLO được giới hạn tần suất theo thời gian với chu kỳ mặc định 0,4 giây. Trong khoảng giữa hai lần suy luận, pipeline giữ lại kết quả vật thể gần nhất thay vì trả danh sách rỗng. Object Signal sau đó yêu cầu vật thể xuất hiện liên tục tối thiểu một giây. Hai cơ chế phối hợp giúp giảm chi phí suy luận mà vẫn duy trì ngữ nghĩa thời gian.

Mỗi lời gọi detector được bọc bằng cơ chế dự phòng. Nếu một detector lỗi tạm thời trên một frame, pipeline trả kết quả rỗng hoặc dùng kết quả vật thể gần nhất thay vì làm kết thúc toàn bộ phiên thi. Thời gian xử lý của từng bước cũng được ghi lại để xác định nút thắt hiệu năng.

Bảng 4.1 tóm tắt vai trò triển khai của bảy tín hiệu. Công thức chi tiết của EAR, tỉ lệ mở miệng, PnP và cosine similarity đã được trình bày ở Chương 2 nên không lặp lại tại đây.

| Tín hiệu | Dữ liệu dùng chung | Cách ổn định chính | Tham số cấu hình hiện tại |
|---|---|---|---|
| `FACE_PRESENCE` | Face boxes | Chỉ bất thường khi vắng mặt đủ lâu | 2,0 giây |
| `MULTI_FACE` | Face boxes | Lọc khuôn mặt có độ tin cậy thấp | confidence ≥ 0,90 |
| `EYE_STATE` | Face landmarks | Kết hợp hai mắt và thời lượng nhắm | EAR 0,21; 1,0 giây |
| `MOUTH_STATE` | Face landmarks | Tỉ lệ chuẩn hóa và cửa sổ hoạt động theo thời gian | cửa sổ 2,0 giây; activity ratio 0,25 |
| `OBJECT_PRESENCE` | YOLO boxes | Throttle model và debounce thời lượng | 1,0 giây; model lọc phone/book |
| `HEAD_POSE` | Face landmarks | Ngưỡng yaw/pitch và thời lượng quay | 20°; 1,0 giây |
| `IDENTITY` | Face crop/embedding | Hai mức cosine, kiểm tra lại định kỳ và yêu cầu lỗi liên tiếp | 30 giây; warn 0,55; alert 0,40 |

### 4.3.3. Kết quả đạt được

Pipeline đã cài đặt đủ bảy lớp tín hiệu theo một interface chung. Có thể thay detector bằng fake trong unit test, đồng thời vẫn có smoke test với các model thật và kiểm thử tích hợp trên video mẫu. Các trường hợp detector lỗi, thiếu landmark, khuôn mặt xuất hiện lại, vật thể chỉ xuất hiện thoáng qua và identity chưa enrollment đều được xử lý mà không làm crash pipeline.

So với cách dùng bộ đếm số frame, nhiều điều kiện trong đồ án được quy đổi sang giây và cửa sổ thời gian. Vì vậy, ý nghĩa của ngưỡng ít phụ thuộc hơn vào FPS của máy. Việc chuẩn hóa độ mở miệng theo kích thước khuôn mặt cũng giảm ảnh hưởng của khoảng cách giữa thí sinh và camera.

## 4.4. Giải pháp kết hợp đa tín hiệu theo thời gian

### 4.4.1. Bài toán báo động giả và dao động trạng thái

Kết quả của một frame đơn lẻ không đủ để kết luận hành vi bất thường. Người dùng có thể chớp mắt, nhìn sang bên trong thời gian ngắn hoặc một detector có thể nhận nhầm vật thể ở đúng một frame. Nếu ghi một vi phạm cho mọi frame vượt ngưỡng, log sẽ bị ngập bởi các sự kiện lặp và giám thị khó phân biệt hành vi kéo dài với nhiễu tức thời.

Giải pháp tại mục này trực tiếp hiện thực `FR-CV-03`, `FR-CV-04`, `NFR-MAIN-01` và `NFR-EXPL-01`.

Một ngưỡng duy nhất cũng làm trạng thái liên tục bật/tắt khi điểm số dao động gần biên. Ngoài ra, các hành vi không có mức nghiêm trọng như nhau: không khớp danh tính hoặc có điện thoại cần đóng góp nhiều hơn một lần nhắm mắt.

### 4.4.2. Giải pháp

Đồ án áp dụng hai cấp trạng thái. Cấp thứ nhất là một state machine độc lập cho từng tín hiệu. Trong cửa sổ trượt mặc định bốn giây, hệ thống tính:

$$
r_i(t)=\frac{N_{i,\text{vượt ngưỡng}}(t-W,t)}{N_{i,\text{hợp lệ}}(t-W,t)}
$$

với $W$ là độ dài cửa sổ và $r_i(t)$ là tỉ lệ quan sát bất thường của tín hiệu $i$. State machine có ba trạng thái `NORMAL`, `SUSPICIOUS` và `ALERT`. Ngưỡng đi vào trạng thái cao hơn lớn hơn ngưỡng đi ra, tạo hysteresis ngay bên trong từng tín hiệu.

```mermaid
stateDiagram-v2
    [*] --> NORMAL
    NORMAL --> SUSPICIOUS: r >= r_enter_susp
    SUSPICIOUS --> NORMAL: r <= r_exit_susp
    SUSPICIOUS --> ALERT: r >= r_enter_alert
    ALERT --> SUSPICIOUS: r <= r_exit_alert
    NORMAL --> NORMAL: chưa đủ bằng chứng
    SUSPICIOUS --> SUSPICIOUS: trong vùng đệm
    ALERT --> ALERT: bằng chứng vẫn còn
```

**Hình 4.4. State machine độc lập của một tín hiệu**

Ở cấp thứ hai, các trạng thái được ánh xạ thành `NORMAL = 0`, `SUSPICIOUS = 1`, `ALERT = 2`. Điểm rủi ro phiên được tính bằng:

$$
R(t)=\sum_{i=1}^{7} w_i s_i(t)
$$

trong đó $w_i$ là trọng số tín hiệu đọc từ tệp cấu hình và $s_i(t)$ là giá trị trạng thái. Cấu hình hiện tại sử dụng trọng số: Identity 3,0; Object Presence 2,5; Face Presence 2,0; Multi-face 2,0; Eye State 1,0; Mouth State 1,0; Head Pose 1,0. Các giá trị này không được hard-code trong thuật toán mà được tập trung tại `config/fusion.yaml` để có thể hiệu chỉnh có kiểm soát.

Trạng thái phiên sử dụng hai ngưỡng: chuyển từ `SESSION_NORMAL` sang `SESSION_ALERT` khi $R(t) \geq 5,0$ và chỉ trở về bình thường khi $R(t) \leq 2,5$. Vùng giữa hai ngưỡng giữ nguyên trạng thái trước đó. Một `ViolationEvent` chỉ được sinh tại cạnh lên, tức thời điểm phiên vừa chuyển sang cảnh báo; hệ thống không tạo lại sự kiện ở mỗi frame trong khi cảnh báo còn kéo dài.

```mermaid
stateDiagram-v2
    [*] --> SESSION_NORMAL
    SESSION_NORMAL --> SESSION_ALERT: R(t) >= 5.0 / sinh ViolationEvent
    SESSION_ALERT --> SESSION_NORMAL: R(t) <= 2.5
    SESSION_NORMAL --> SESSION_NORMAL: R(t) < 5.0
    SESSION_ALERT --> SESSION_ALERT: 2.5 < R(t) < 5.0
```

**Hình 4.5. Hysteresis ở cấp phiên thi**

Khi tạo sự kiện, engine lưu điểm rủi ro, mức nghiêm trọng, tín hiệu đóng góp, loại vi phạm chính và đường dẫn ảnh chụp. Vi phạm chính là tín hiệu có tích $w_i \times s_i$ lớn nhất tại thời điểm cạnh lên. Cách chọn này vẫn hoạt động khi cảnh báo được tạo bởi nhiều tín hiệu `SUSPICIOUS` cộng dồn mà chưa có tín hiệu riêng lẻ ở `ALERT`.

### 4.4.3. Kết quả đạt được

Giải pháp loại bỏ việc sinh cảnh báo lặp theo frame và cho phép nhiều tín hiệu tác động đồng thời đến một quyết định. State machine của bảy tín hiệu được cập nhật độc lập nên một tín hiệu trở lại bình thường không xóa lịch sử của tín hiệu khác. Tất cả transition, timeline điểm rủi ro và sự kiện vi phạm đều có thể được lưu để giải thích quyết định sau kỳ thi.

Các kiểm thử đã bao phủ các tình huống: chưa vượt ngưỡng không sinh sự kiện; cạnh lên sinh đúng một sự kiện; trạng thái cảnh báo kéo dài không tạo bản ghi trùng; phiên có thể trở lại bình thường và cảnh báo lại; nhiều tín hiệu cùng đóng góp; mức nghiêm trọng cao; ảnh snapshot và transition được ghi đúng. Tuy nhiên, trọng số và ngưỡng hiện tại là cấu hình khởi tạo đã được kiểm chứng về logic, chưa phải kết quả tối ưu hóa trên một bộ dữ liệu thực lớn có ground truth.

## 4.5. Giải pháp giám sát thời gian thực và kiểm chứng telemetry

### 4.5.1. Bài toán truyền trạng thái từ client không đáng tin cậy hoàn toàn

Giám thị cần thấy thay đổi của nhiều phiên gần như tức thời. Polling REST liên tục tạo độ trễ và tải thừa, trong khi WebSocket cho phép cập nhật hai chiều nhưng phát sinh rủi ro khác: token có thể bị lộ trong URL, message có thể bị giả mạo hoặc gửi quá nhanh, timestamp của client có thể sai và kết nối có thể mất mà dashboard không nhận biết.

Các yêu cầu liên quan gồm `FR-RT-*`, `FR-SESSION-03`, `NFR-SEC-02`, `NFR-SEC-03` và `NFR-PERF-02`.

### 4.5.2. Giải pháp

Hệ thống sử dụng hai kênh WebSocket tách biệt: kênh client của từng phiên và kênh dashboard theo kỳ thi. Browser WebSocket không truyền JWT trong query string. Dashboard trước tiên gọi REST để nhận một ticket dùng một lần, tồn tại ngắn, sau đó đưa ticket qua subprotocol khi mở kết nối. Client desktop sử dụng token phiên riêng.

Trình tự xử lý một phiên được mô tả trong Hình 4.6.

```mermaid
sequenceDiagram
    actor Manager as Exam Manager
    actor Student as Thí sinh
    participant Ext as Extension/Desktop client
    participant API as FastAPI REST
    participant WS as WebSocket Gateway
    participant Data as DB + Evidence Store
    actor Proctor as Giám thị

    Manager->>API: Tạo/cấu hình và mở kỳ thi
    API-->>Manager: Mã tham gia có thời hạn
    Student->>Ext: Nhập mã, thông tin/xác thực Google
    Ext->>API: Kiểm tra chính sách và tham gia
    API-->>Ext: Session token và policy đã resolve
    Ext->>Ext: Consent, kiểm tra thiết bị, khởi tạo monitor
    Proctor->>API: Yêu cầu WebSocket ticket dùng một lần
    API-->>Proctor: Ticket ngắn hạn
    Proctor->>WS: Kết nối dashboard theo exam_id
    Ext->>WS: Kết nối kênh của session

    loop Theo chu kỳ trong phiên thi
        Ext->>WS: heartbeat / telemetry / browser_event
        WS->>WS: Kiểm tra schema, tần suất, quyền và thời gian server
        WS->>WS: Tính/đối chiếu risk và integrity
        WS->>Data: Cập nhật trạng thái + append evidence
        WS-->>Proctor: Fan-out cập nhật phiên
    end

    opt Có vi phạm kèm ảnh
        Ext->>WS: violation_event + snapshot
        WS->>WS: Kiểm tra event và ảnh
        WS->>Data: Lưu tên server sinh và hash
        WS-->>Proctor: Thông báo cảnh báo
    end

    Student->>WS: Kết thúc phiên
    WS->>Data: Chuyển trạng thái ended
    WS-->>Proctor: session_ended
```

**Hình 4.6. Sequence diagram của một phiên thi được giám sát**

Mọi message được ánh xạ vào schema chặt, giới hạn kích thước và tần suất. Backend dùng timestamp nhận tại server làm thời gian chuẩn; timestamp client chỉ phục vụ truy vết. Với telemetry CV, server yêu cầu đủ bảy signal và đối chiếu lại risk/state/severity/contribution. Với sự kiện trình duyệt, server xác định mức nghiêm trọng theo chính sách kỳ thi và tự tính `integrity_score`, không nhận điểm toàn vẹn do extension tự khai báo.

Heartbeat và idle timeout được dùng để phân biệt các trạng thái `pending`, `active`, `disconnected` và `ended`. Khi nhận cập nhật hợp lệ, backend vừa lưu bản sao trạng thái mới nhất vào SQL để dashboard tải nhanh, vừa append dữ liệu chi tiết vào evidence store. Connection manager fan-out bản cập nhật đến các dashboard đúng kỳ thi.

Ảnh bằng chứng chỉ chấp nhận JPEG hoặc PNG, giới hạn 2 MiB, kiểm tra magic bytes, kích thước ảnh và hash. Tên file do server sinh, không sử dụng đường dẫn client gửi. Việc tải ảnh và báo cáo cũng phải đi lại qua kiểm tra quyền của đúng tổ chức và đúng phiên.

### 4.5.3. Kết quả đạt được

Giám thị có thể theo dõi risk CV, integrity trình duyệt, thiết bị, kết nối và phiên thi theo thời gian thực mà không cần tải lại trang. Khi client mất heartbeat, trạng thái phiên được chuyển thành `disconnected` cùng lý do; khi kết nối lại, hệ thống tiếp tục nhận dữ liệu theo phiên hợp lệ.

Backend không còn là bộ chuyển tiếp mù quáng dữ liệu do client khai báo. Các kiểm thử tích hợp đã kiểm tra ticket một lần, schema sự kiện, tính lại điểm ở server, cô lập WebSocket giữa các tổ chức, upload snapshot và kết thúc phiên. Dù vậy, một client chạy trên thiết bị do thí sinh toàn quyền kiểm soát vẫn có thể bị sửa để phát chuỗi telemetry giả nhưng nhất quán. Giải pháp hiện tại làm tăng khả năng phát hiện sai lệch và truy vết, không thay thế remote attestation hoặc lockdown browser.

## 4.6. Giải pháp mô hình dữ liệu lai và luồng bằng chứng

### 4.6.1. Bài toán lưu trạng thái vận hành và dữ liệu chuỗi thời gian

Dashboard cần truy vấn nhanh danh sách kỳ thi, người dùng và trạng thái mới nhất của phiên. Ngược lại, tín hiệu theo thời gian, transition, sự kiện trình duyệt và vi phạm là dữ liệu append-only có số lượng lớn, phù hợp với xử lý tuần tự và sinh báo cáo. Nếu đưa toàn bộ frame-level telemetry vào cơ sở dữ liệu quan hệ, schema trở nên nặng và mỗi frame có thể gây một transaction. Nếu chỉ lưu file, việc lọc theo tổ chức, phân quyền và tải trạng thái ban đầu cho dashboard trở nên khó khăn.

Nhóm vấn đề này tương ứng với `FR-EVID-*`, `FR-REVIEW-01`, `FR-REPORT-*`, `FR-RET-01` và yêu cầu giải thích `NFR-EXPL-01`.

### 4.6.2. Giải pháp

Đồ án sử dụng mô hình dữ liệu lai:

- **Cơ sở dữ liệu quan hệ** lưu identity, tổ chức, membership, role, kỳ thi, assignment, phiên thi, trạng thái hiện tại, review, report job và audit log.
- **Kho evidence theo phiên** lưu metadata, tín hiệu, transition, timeline risk, sự kiện trình duyệt, vi phạm và ảnh snapshot dưới dạng JSON/JSONL và tệp ảnh.

Sơ đồ quan hệ chính được trình bày ở Hình 4.7. ERD chỉ giữ các thực thể và khóa quan trọng để làm rõ phạm vi dữ liệu; các trường kỹ thuật chi tiết tiếp tục được mô tả ở Chương 5.

![ERD rút gọn của lớp nền tảng](image/mo_hinh_du_lieu_erd.svg)

**Hình 4.7. ERD rút gọn của lớp nền tảng**

Trước khi đi vào chi tiết kỹ thuật, Hình 4.8 xác định biên hệ thống và bốn nhóm tác nhân ngoài. Thí sinh cung cấp thông tin tham gia, consent và dữ liệu giám sát; giám thị khai thác trạng thái, evidence và ghi kết luận; Exam Manager quản lý vòng đời kỳ thi; còn quản trị viên cung cấp cấu hình tổ chức, người dùng và policy. Sự phân tách này giúp nhận biết dữ liệu nào đi vào, dữ liệu nào đi ra và ai chịu trách nhiệm với từng luồng.

![Sơ đồ luồng dữ liệu mức ngữ cảnh](image/data_flow_muc_ngu_canh.svg)

**Hình 4.8. Sơ đồ luồng dữ liệu mức ngữ cảnh của hệ thống**

Luồng dữ liệu nội bộ của một phiên thi được thể hiện ở Hình 4.9. Hai nguồn dữ liệu được xử lý song song: CV telemetry/violation từ desktop client và browser event/heartbeat từ extension. Backend kiểm tra phạm vi phiên, schema, sequence và dữ liệu dẫn xuất trước khi cập nhật trạng thái. Dữ liệu đã kiểm chứng vừa được fan-out tới dashboard, vừa được lưu theo hai lớp: trạng thái hiện tại trong SQL và chuỗi bằng chứng trong JSONL/snapshot.

![Luồng dữ liệu chi tiết của một phiên thi](image/data_flow_phien_thi.svg)

**Hình 4.9. Sơ đồ luồng dữ liệu chi tiết của một phiên thi**

Data flow trên cũng làm rõ ba thời điểm sử dụng dữ liệu. Trong khi thi, dashboard cần current state và alert có độ trễ thấp. Khi hậu kiểm, giám thị cần timeline, snapshot và sự kiện nguyên bản. Khi kết thúc, reporting worker tổng hợp cả metadata quan hệ lẫn evidence append-only để dựng HTML/PDF. Vì vậy, một biểu diễn dữ liệu duy nhất không phù hợp cho cả ba tải truy cập.

#### 4.6.2.1. Sơ đồ luồng dữ liệu mức 1

Hình 4.10 phân rã hệ thống thành năm tiến trình nghiệp vụ. `P1` xử lý tham gia, xác thực và chính sách; `P2` tạo ngữ cảnh phiên sau khi ghi nhận sự đồng ý và kiểm tra thiết bị; `P3` tiếp nhận, kiểm chứng dữ liệu giám sát tại biên tin cậy phía máy chủ; `P4` phục vụ bảng điều khiển, bằng chứng và hậu kiểm; `P5` tổng hợp dữ liệu để sinh báo cáo. Ba kho dữ liệu được tách theo tải truy cập: `DS1` lưu siêu dữ liệu và trạng thái hiện tại, `DS2` lưu chuỗi bằng chứng, `DS3` lưu đầu ra báo cáo.

![Sơ đồ luồng dữ liệu mức 1](image/data_flow_level_1.svg)

**Hình 4.10. Sơ đồ luồng dữ liệu mức 1 của hệ thống**

#### 4.6.2.2. Từ điển luồng dữ liệu

| Mã | Nguồn → đích | Nội dung chính | Kênh/tần suất | Kiểm tra và lưu trữ |
|---|---|---|---|---|
| `F01` | Candidate → P1 | Join code, thông tin hoặc kết quả xác thực | REST, khi tham gia | Trạng thái kỳ thi, thời hạn mã, phương thức auth |
| `F02` | P1 → Candidate | Metadata kỳ thi, effective policy, kết quả auth | REST response | Chỉ trả trường cần cho setup; không trả secret |
| `F03` | Admin/Manager → P1 | Organization, exam, policy, assignment | REST, theo thao tác | Cookie/user token, capability, tenant scope, optimistic lock |
| `F04` | P1 → P2 | Candidate identity và policy đã giải quyết | Nội bộ server | Gắn đúng exam/version trước khi tạo session |
| `F05` | Candidate → P2 | Consent, preflight và device identity | REST, một lần hoặc khi retry | Bắt buộc điều kiện theo policy; lưu session/device state |
| `F06` | P2 → P3 | Session ID/token, client type và capability | WebSocket hello | Token đúng loại, session ownership, lease kết nối |
| `F07` | Client → P3 | Telemetry, violation, snapshot, browser event, heartbeat | WebSocket; telemetry theo chu kỳ, event theo phát sinh | Pydantic strict schema, sequence/dedup, giới hạn payload |
| `F08` | P3 → DS1 | Risk/integrity/session/device current state | Mỗi cập nhật hợp lệ | Dữ liệu dẫn xuất được tính/đối chiếu phía server |
| `F09` | P3 → DS2 | Signals, transition, violation, browser event, snapshot | Append theo sự kiện/lô | Tên file cho phép, hash/magic bytes, đường dẫn trong session |
| `F10` | P3 → P4 | Cập nhật phiên đã kiểm chứng | WebSocket realtime | Chỉ fan-out sau authz/validation; Redis pub/sub nếu đa process |
| `F11` | Proctor → P4 | Truy vấn dashboard, filter, session detail, review | REST/WebSocket | User cookie, ticket dùng một lần, exam assignment |
| `F12` | P4 → Proctor | KPI, risk, integrity, alert, timeline, evidence | REST ban đầu + WebSocket cập nhật | Lọc theo tenant/exam; escape dữ liệu trước khi đưa vào DOM |
| `F13` | P4 → DS1 | Verdict, ghi chú review và audit metadata | REST theo thao tác | Capability review, reviewer ID, timestamp server |
| `F14` | Manager/Proctor → P5 | Yêu cầu sinh báo cáo | REST, theo yêu cầu | Capability export; tạo `ReportJob` `pending` |
| `F15` | DS1 → P5 | Metadata kỳ thi/phiên, current state, review | Truy vấn khi worker xử lý | Session/report job phải tồn tại và đúng trạng thái |
| `F16` | DS2 → P5 | Timeline, violation, browser event và snapshot | Đọc tuần tự khi dựng report | Tolerant với file thiếu; snapshot phải nằm trong session root |
| `F17` | P5 → DS3 | HTML/PDF, chart và trạng thái job | Sau khi tổng hợp | Chỉ `completed` khi output thành công; lỗi ghi `failed` |
| `F18` | DS3/P5 → người dùng | Trạng thái job và tệp báo cáo | REST/download | Authorization được kiểm tra lại tại thời điểm tải |

Từ điển trên phân biệt rõ dữ liệu điều khiển (`F01`–`F06`), dữ liệu giám sát realtime (`F07`–`F12`) và dữ liệu hậu kiểm/báo cáo (`F13`–`F18`). Việc phân nhóm hỗ trợ kiểm thử từng ranh giới: client không được tự quyết định dữ liệu dẫn xuất hoặc đường dẫn tệp; dashboard không nhận message chưa kiểm chứng; report không đọc tệp ngoài session root.

Mỗi thư mục `sessions/<session_id>/` có cấu trúc thống nhất:

```text
session_meta.json
signals.jsonl
state_transitions.jsonl
browser_events.jsonl
violations.jsonl
risk_score_timeline.jsonl
snapshots/
report.html
report.pdf
```

Các tệp JSONL chỉ được append vào danh sách tên cho phép. `ExamSession.risk_score_current`, `session_state_current`, `integrity_score_current` và trạng thái thiết bị là bản sao mới nhất phục vụ truy vấn nhanh, còn các JSONL là nguồn chi tiết để dựng timeline và báo cáo. `IncidentReview` lưu đánh giá của con người tách khỏi sự kiện vi phạm gốc, nhờ đó kết quả máy không bị sửa khi giám thị xác nhận hoặc bác bỏ một sự cố.

Report job được đưa vào hàng đợi nền với trạng thái `pending`, `processing`, `failed` hoặc `completed`. Retention job có chế độ dry-run trước khi áp dụng; khi dọn dữ liệu hết hạn, hệ thống xử lý evidence, review/report liên quan, ẩn danh phiên và ghi AuditLog.

### 4.6.3. Kết quả đạt được

Mô hình lai đáp ứng đồng thời hai kiểu tải: dashboard lấy trạng thái mới nhất từ SQL mà không phải đọc lại toàn bộ log, trong khi module reporting vẫn đọc được chuỗi thời gian đầy đủ từ thư mục phiên. Schema `SignalResult` và `ViolationEvent` được dùng xuyên suốt từ client, backend đến báo cáo nên không cần chuyển đổi sang một định dạng trung gian khác.

Trình đọc báo cáo có khả năng dung nạp file thiếu hoặc phiên bị dừng giữa chừng; dữ liệu còn lại vẫn được tổng hợp thay vì làm hỏng toàn bộ báo cáo. Hệ thống đã tạo được báo cáo HTML/PDF gồm thống kê, bảng vi phạm, biểu đồ điểm rủi ro, sự kiện integrity và ảnh bằng chứng. Dữ liệu tổng hợp quy mô lớn được dùng để kiểm thử tải và báo cáo, nhưng không được coi là bằng chứng đánh giá độ chính xác của mô hình.

## 4.7. Giải pháp bảo vệ phiên, chính sách và dữ liệu nhạy cảm

### 4.7.1. Bài toán an toàn hệ thống

Hệ thống giám sát thi xử lý thông tin định danh, hành vi và hình ảnh của thí sinh. Các rủi ro không chỉ nằm ở việc đăng nhập sai mật khẩu mà còn gồm lộ token qua URL, nhầm token người dùng với token phiên, truy cập chéo tổ chức, path traversal khi tải ảnh, replay WebSocket ticket, dữ liệu HTML không an toàn, thay đổi cấu hình kỳ thi đồng thời và chính sách cấp dưới làm yếu yêu cầu bảo mật của cấp trên.

Giải pháp này bao phủ các yêu cầu `NFR-SEC-*`, `NFR-PRIV-*`, `FR-AUTH-*`, `FR-ORG-04`, `FR-ORG-05` và `FR-EXAM-06`.

### 4.7.2. Giải pháp

Đồ án triển khai bảo vệ theo nhiều lớp:

1. **Xác thực và phiên:** mật khẩu được băm; JWT giao diện quản trị nằm trong cookie `HttpOnly`, `SameSite=Strict`; System Admin bắt buộc MFA; thay đổi membership hoặc assignment làm phiên cũ mất hiệu lực thông qua version thu hồi.
2. **OAuth:** luồng Google sử dụng state, PKCE, nonce và grant một lần. Hệ thống chỉ lưu claim tối thiểu và hash của device token.
3. **Kênh truyền:** WebSocket dashboard dùng ticket ngắn hạn dùng một lần, không đặt bearer token trong URL. Message bị giới hạn schema, kích thước, tần suất và có heartbeat.
4. **Cô lập dữ liệu:** mọi truy vấn kỳ thi/phiên đi qua kiểm tra tenant và assignment. Evidence chỉ được phục vụ từ thư mục phiên đã xác định bởi server.
5. **Bảo vệ giao diện và tệp:** dashboard dựng dữ liệu động bằng API DOM an toàn; backend đặt CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` và HSTS khi dùng HTTPS. Ảnh upload được kiểm tra nội dung và tên file do server sinh.
6. **Chính sách phân tầng:** policy kỳ thi được resolve theo sàn nền tảng, chính sách tổ chức và cấu hình kỳ thi. Cấp dưới không thể làm yếu trường bắt buộc của cấp trên.
7. **Tính nhất quán vận hành:** kỳ thi có lifecycle `draft`, `scheduled`, `open`, `closed`, `archived`; join code có hạn và có thể xoay; trường `version` hỗ trợ optimistic locking khi nhiều người cùng chỉnh sửa.

### 4.7.3. Kết quả đạt được

Các đường REST, WebSocket và download evidence cùng sử dụng một mô hình phạm vi thay vì chỉ ẩn nút ở frontend. Hệ thống đã có kiểm thử cho rate limit đăng nhập, MFA, token confusion, policy inheritance, quota phiên đồng thời, cô lập tổ chức, quyền truy cập theo assignment, snapshot traversal và security header.

Giải pháp làm cho hệ thống phù hợp với mục tiêu nghiên cứu và triển khai có kiểm soát, nhưng chưa thể được xem là một lockdown browser hoàn chỉnh. Extension không quan sát được ứng dụng ngoài trình duyệt, điện thoại thứ hai hoặc máy ảo; Google login chỉ chứng minh quyền sở hữu tài khoản, không chứng minh người ngồi trước camera; blink liveness cơ bản chặn ảnh tĩnh nhưng không thay thế anti-spoofing chuyên dụng trước video replay hoặc deepfake. Với kỳ thi rủi ro cao, cần thêm managed browser, extension/client được ký và force-install, secure boot/attestation, HTTPS bắt buộc, object storage, backup và quy trình bảo vệ dữ liệu chính thức.

## 4.8. Đánh giá tổng hợp các đóng góp

### 4.8.1. Bài toán đánh giá đóng góp ở cấp hệ thống

Một hệ thống có nhiều module dễ tạo cảm giác “nhiều chức năng”, nhưng số lượng màn hình không phản ánh chất lượng kỹ thuật. Đóng góp cần được xem xét theo khả năng giải quyết các mâu thuẫn thực tế: độ nhạy và báo động giả; tính thời gian thực và băng thông; khả năng truy vấn và khả năng lưu chuỗi sự kiện; quyền quản trị và quyền riêng tư; tự động phát hiện và quyền kết luận của con người.

### 4.8.2. Giải pháp và giá trị đóng góp

Các đóng góp chính của đồ án có thể tổng quát hóa như sau:

- **Kiến trúc phân rã theo trách nhiệm:** đưa xử lý CV về client, đưa quản trị và kiểm chứng dữ liệu về backend, tách browser integrity khỏi risk CV nhưng hợp nhất hai loại bằng chứng trên dashboard và báo cáo.
- **Pipeline nhận thức dùng chung:** chạy detector nền tảng một lần cho mỗi frame, chia sẻ `PerceptionResult` cho bảy Signal Extractor và dùng interface thống nhất để kiểm thử độc lập.
- **Mô hình quyết định hai cấp có trạng thái:** kết hợp cửa sổ thời gian, hysteresis trên từng tín hiệu, weighted fusion và hysteresis cấp phiên; chỉ sinh sự kiện ở cạnh lên để hạn chế log trùng.
- **Dữ liệu có khả năng giải thích:** lưu tín hiệu đóng góp, chuyển trạng thái, diễn biến điểm rủi ro, sự kiện trình duyệt và ảnh chụp thay vì chỉ lưu một nhãn “gian lận”.
- **Nền tảng nhiều tổ chức có phân quyền theo tài nguyên:** tách System Admin, Organization Admin, Exam Manager và nhiệm vụ theo kỳ thi; cung cấp quyền truy cập ngoại lệ có phê duyệt đối với dữ liệu nhạy cảm.
- **Phòng thủ phía máy chủ:** không tin điểm và đường dẫn do máy khách khai báo; kiểm tra lược đồ, dùng thời gian máy chủ, tính lại hoặc đối chiếu điểm rủi ro/toàn vẹn, kiểm tra ảnh và ghi nhật ký kiểm toán.
- **Chu trình sau phát hiện:** hỗ trợ giám thị xem diễn biến, thực hiện hậu kiểm sự cố và tạo tác vụ báo cáo HTML/PDF, đồng thời giữ kết luận của con người tách khỏi sự kiện máy.

Bảng 4.2 tổng hợp tuyến liên kết từ đóng góp đến nhóm yêu cầu chính.

| Đóng góp | Nhóm yêu cầu chính |
|---|---|
| Kiến trúc ứng dụng CV–tiện ích–máy chủ | `FR-SESSION-*`, `FR-RT-*`, `NFR-PRIV-*`, `NFR-PORT-01` |
| Tầng nhận thức và bảy tín hiệu | `FR-CV-01..03`, `NFR-PERF-01`, `NFR-REL-01` |
| Bộ tổng hợp rủi ro hai cấp | `FR-CV-04`, `NFR-MAIN-01`, `NFR-EXPL-01` |
| RBAC và chính sách phân tầng | `FR-AUTH-*`, `FR-ORG-*`, `FR-EXAM-*`, `NFR-SEC-01` |
| WebSocket và kiểm chứng dữ liệu giám sát | `FR-RT-*`, `FR-BROWSER-02`, `NFR-SEC-02..03`, `NFR-PERF-02` |
| Bằng chứng, hậu kiểm, báo cáo và lưu trữ | `FR-EVID-*`, `FR-REVIEW-01`, `FR-REPORT-*`, `FR-RET-01` |

### 4.8.3. Kết quả đạt được và giới hạn đánh giá

Trong lần rà soát ngày 12/08/2026, bộ kiểm thử tiện ích mở rộng đạt 8/8 ca. Bộ kiểm thử Python đạt 309/309 ca ở lần chạy toàn bộ thứ hai; lần chạy đầu đạt 308 ca và có một ca lỗi không tái hiện khi chạy riêng. Ngoài kiểm thử đơn vị, dự án có kiểm thử khởi tạo mô hình thật, kiểm thử tích hợp trên video mẫu và luồng mô phỏng đầu-cuối tạo báo cáo. Các kết quả cung cấp bằng chứng rằng kiến trúc và hợp đồng dữ liệu có thể vận hành xuyên suốt các mô-đun, đồng thời cho thấy cần tiếp tục theo dõi tính ổn định của ca kiểm thử sắp xếp nhật ký. Chi tiết được trình bày tại Chương 6.

Tuy nhiên, số lượng ca kiểm thử phần mềm không đồng nghĩa với độ chính xác nhận diện trong thực tế. Để đánh giá Precision, Recall, F1-score hoặc tỉ lệ cảnh báo sai của từng tín hiệu, hệ thống cần video đủ đa dạng về ánh sáng, thiết bị, góc mặt và đặc điểm người dùng, kèm nhãn tham chiếu độc lập. Vì vậy, chương này chỉ kết luận về chức năng, tính nhất quán, khả năng chịu lỗi và an toàn truy cập trong phạm vi kiểm thử; số liệu nhận diện và giới hạn tái lập được phân tích riêng ở Chương 6.

## 4.9. Kết chương

Chương 4 đã trình bày thiết kế giải pháp và các đóng góp của đồ án ở cấp hệ thống. Thay vì xử lý từng khung hình bằng các luật độc lập, đồ án xây dựng tầng nhận thức dùng chung, bảy tín hiệu có hợp đồng thống nhất và cơ chế kết hợp hai cấp theo thời gian. Hệ thống mở rộng ứng dụng webcam bằng tiện ích giám sát trình duyệt, dịch vụ nhiều tổ chức, bảng điều khiển thời gian thực, mô hình phân quyền theo tài nguyên, kho bằng chứng và quy trình báo cáo.

Hệ thống đã hình thành chuỗi xử lý có thể truy vết từ dữ liệu đầu vào, trạng thái tín hiệu, quyết định rủi ro, truyền nhận thời gian thực đến hậu kiểm và báo cáo. Chương cũng xác định rõ giới hạn của máy khách chạy trên thiết bị người dùng, kiểm tra sự hiện diện sống cơ bản, phạm vi quan sát của tiện ích mở rộng và nhu cầu đánh giá trên dữ liệu thực tế. Chương 5 tiếp theo trình bày cách các giải pháp này được cài đặt trong phiên bản bàn giao.
