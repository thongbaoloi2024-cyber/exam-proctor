# Sơ đồ thiết kế hệ thống

> Tuần 2. Thiết kế trước khi code, dựa trên kiến trúc 3 tầng tại `KE_HOACH_DO_AN.md` (mục 3.1) và đề cương `docs/DE_CUONG_CHI_TIET.md`. Toàn bộ sơ đồ dùng cú pháp Mermaid — GitHub/VS Code render trực tiếp; không cần công cụ ngoài.

---

## 1. Sơ đồ kiến trúc pipeline

Bốn tầng: **Perception Layer** (trích xuất landmark/bbox thô từ frame) → **Signal Extractors** (7 tín hiệu, mỗi tín hiệu 1 class độc lập theo interface chung) → **Risk Fusion Engine** (state machine + tổng hợp trọng số + hysteresis) → **Alert/Report** (sinh event, log, chụp ảnh, báo cáo).

```mermaid
flowchart TB
    WC[["Webcam Frame Source"]]

    subgraph PERC["Perception Layer"]
        direction TB
        PRE["Frame Preprocessor<br/>(resize, BGR→RGB)"]
        FM["MediaPipe FaceMesh<br/>468 landmarks"]
        MT["MTCNN<br/>multi-face bbox"]
        YOLO["YOLOv8-COCO<br/>object detection"]
        PRE --> FM
        PRE --> MT
        PRE --> YOLO
    end

    subgraph SIG["Signal Extractors (interface chung: process(frame, PerceptionResult) -> SignalResult)"]
        direction TB
        S1["FacePresenceSignal"]
        S2["MultiFaceSignal"]
        S3["EyeStateSignal (EAR)"]
        S4["MouthStateSignal"]
        S5["ObjectSignal (phone/book)"]
        S6["HeadPoseSignal (solvePnP) [MỚI]"]
        S7["IdentitySignal (FaceNet embedding) [MỚI]"]
    end

    subgraph FUSE["Risk Fusion Engine"]
        direction TB
        SM["7x Per-signal State Machine<br/>NORMAL → SUSPICIOUS → ALERT<br/>(sliding window, hysteresis riêng)"]
        AGG["Weighted Risk Score Aggregator<br/>(trọng số theo config YAML)"]
        HYS["Session Hysteresis Decision<br/>(ngưỡng lên T_enter / ngưỡng xuống T_exit)"]
        SM --> AGG --> HYS
    end

    subgraph OUT["Alert / Report"]
        direction TB
        EVT["Violation Event Generator"]
        SNAP["Frame Snapshot Capture"]
        LOG["Session Log (JSONL)"]
        REP["Báo cáo PDF/HTML<br/>(Tuần 11)"]
        EVT --> SNAP
        EVT --> LOG
        LOG --> REP
    end

    WC --> PRE

    MT --> S1
    MT --> S2
    FM --> S3
    FM --> S4
    FM --> S6
    YOLO --> S5
    MT --> S7
    FM --> S7

    S1 --> SM
    S2 --> SM
    S3 --> SM
    S4 --> SM
    S5 --> SM
    S6 --> SM
    S7 --> SM

    HYS -->|"rising edge: risk_score ≥ T_enter"| EVT
```

**Ghi chú thiết kế:**

- `IdentitySignal` (S7) dùng cả bbox từ MTCNN (crop khuôn mặt lớn nhất) lẫn không cần FaceMesh bắt buộc — mô hình embedding (InceptionResnetV1) nằm bên trong chính signal extractor này, không phải tầng Perception dùng chung, vì đây là model chuyên biệt chỉ một signal cần.
- Tầng Perception chỉ chạy các model nền tảng (dò landmark/bbox/object) **một lần mỗi frame**, kết quả (`PerceptionResult`) được chia sẻ cho nhiều signal extractor — tránh chạy trùng MediaPipe/MTCNN nhiều lần trong 1 frame (tối ưu FPS, liên quan mục đo hiệu năng ở Tuần 7).
- Mỗi signal extractor độc lập, có state machine riêng trong Risk Fusion Engine — khác cách bản tham khảo chỉ ghi 1 loại vi phạm/frame.

---

## 2. Sequence diagram — luồng xử lý 1 frame

Mô tả một chu kỳ xử lý: từ khi webcam trả về 1 frame đến khi (có thể) sinh ra violation event.

```mermaid
sequenceDiagram
    participant WC as Webcam
    participant ORCH as PipelineOrchestrator
    participant PERC as PerceptionLayer
    participant SIG as SignalExtractors (x7)
    participant FUSE as RiskFusionEngine
    participant EVT as EventLogger/AlertManager
    participant UI as UI Overlay

    WC->>ORCH: raw_frame(BGR, frame_ts)
    ORCH->>PERC: preprocess_and_detect(raw_frame)
    activate PERC
    PERC->>PERC: resize + convert màu
    PERC->>PERC: chạy FaceMesh / MTCNN / YOLOv8
    PERC-->>ORCH: PerceptionResult(landmarks, face_boxes, objects)
    deactivate PERC

    ORCH->>SIG: process(frame, PerceptionResult) [tuần tự trong cùng frame]
    activate SIG
    SIG-->>ORCH: List[SignalResult] (signal_name, value, confidence, ts)
    deactivate SIG

    ORCH->>FUSE: update(List[SignalResult])
    activate FUSE
    FUSE->>FUSE: cập nhật per-signal state machine (sliding window)
    FUSE->>FUSE: tính risk_score = Σ weight_i × state_value_i
    FUSE->>FUSE: áp dụng hysteresis lên session state

    alt risk_score vượt T_enter (rising edge, đang ở SESSION_NORMAL)
        FUSE-->>ORCH: ViolationEvent(type, severity, contributing_signals, risk_score)
        ORCH->>EVT: log_event(ViolationEvent)
        EVT->>EVT: chụp snapshot frame hiện tại
        EVT->>EVT: append vào violations.jsonl
    else risk_score dưới T_exit (falling edge, đang ở SESSION_ALERT)
        FUSE-->>ORCH: SessionStateChanged(ALERT → NORMAL)
        ORCH->>EVT: log_state_change(...)
    else T_exit ≤ risk_score ≤ T_enter (vùng đệm)
        FUSE-->>ORCH: (giữ nguyên trạng thái session, không sinh event)
    end
    deactivate FUSE

    ORCH->>UI: render(overlay: per-signal state, risk_score, session state)
```

**Ghi chú thiết kế:**

- Vùng đệm (`T_exit ≤ risk_score ≤ T_enter`) không sinh event, không đổi trạng thái session — đây chính là cơ chế hysteresis chống dao động (chi tiết mục 3).
- `ViolationEvent` chỉ được tạo tại **rising edge** (thời điểm chuyển từ NORMAL sang ALERT), không tạo lặp lại mỗi frame trong lúc đang ALERT — tránh log bị ngập bởi cùng một vi phạm kéo dài. Trạng thái ALERT kéo dài bao lâu được suy ra từ log state-change (mục 3, docs/DATA_SCHEMAS.md).

---

## 3. State diagram — Risk Fusion Engine

### 3.1. Per-signal state machine (áp dụng cho từng tín hiệu trong 7 signal, độc lập với nhau)

Mỗi signal extractor có `exceed_ratio` = tỉ lệ frame vượt ngưỡng thô (raw threshold, đặc thù từng signal — VD EAR < 0.2, yaw > 25°) trong cửa sổ thời gian trượt W (mặc định 3–5 giây). Bản thân state machine từng tín hiệu **cũng dùng hysteresis riêng** (ngưỡng vào cao hơn ngưỡng ra) để tránh việc một tín hiệu đơn lẻ tự dao động ngay trong nội bộ nó trước khi tới tầng tổng hợp.

```mermaid
stateDiagram-v2
    [*] --> NORMAL

    NORMAL --> SUSPICIOUS: exceed_ratio ≥ r_enter_susp
    SUSPICIOUS --> NORMAL: exceed_ratio ≤ r_exit_susp

    SUSPICIOUS --> ALERT: exceed_ratio ≥ r_enter_alert
    ALERT --> SUSPICIOUS: exceed_ratio ≤ r_exit_alert

    NORMAL --> NORMAL: exceed_ratio < r_enter_susp (giữ nguyên)
    SUSPICIOUS --> SUSPICIOUS: r_exit_susp < exceed_ratio < r_enter_alert (giữ nguyên)
    ALERT --> ALERT: exceed_ratio > r_exit_alert (giữ nguyên)

    note right of ALERT
        r_exit_susp < r_enter_susp
        r_exit_alert < r_enter_alert
        ALERT chỉ thoát qua SUSPICIOUS
        (không nhảy thẳng ALERT → NORMAL)
    end note
```

**Giá trị khởi tạo tham khảo** (sẽ tinh chỉnh thực nghiệm ở Tuần 5-6 khi cài từng signal, và Tuần 14 khi có số liệu):

| Tham số          | Ý nghĩa                                          | Giá trị khởi tạo |
| ----------------- | -------------------------------------------------- | -------------------- |
| `W` (window)    | Độ dài cửa sổ thời gian trượt              | 4 giây              |
| `r_enter_susp`  | Tỉ lệ frame vượt ngưỡng để vào SUSPICIOUS | 0.3                  |
| `r_exit_susp`   | Tỉ lệ để thoát về NORMAL                     | 0.15                 |
| `r_enter_alert` | Tỉ lệ để vào ALERT                            | 0.6                  |
| `r_exit_alert`  | Tỉ lệ để thoát về SUSPICIOUS                 | 0.4                  |

Riêng `IdentitySignal` không chạy mỗi frame mà theo chu kỳ (VD mỗi 30 giây/N frame) — giữa 2 lần re-verification, state được **giữ nguyên (carry-forward)** từ lần đánh giá gần nhất thay vì tính theo cửa sổ trượt như 6 signal còn lại; đây là ngoại lệ cần ghi chú khi cài đặt (Tuần 6).

### 3.2. Tầng tổng hợp (session-level) với hysteresis 2 ngưỡng

Sau khi có state (NORMAL=0, SUSPICIOUS=1, ALERT=2) của cả 7 signal, tính:

```
risk_score = Σ_i ( weight_i × state_value_i )        với i = 1..7, weight_i đọc từ config YAML
```

Trạng thái phiên thi (`SessionRiskState`) chỉ có 2 giá trị, chuyển đổi theo `risk_score` bằng 2 ngưỡng khác nhau (Schmitt trigger / hysteresis kinh điển):

```mermaid
stateDiagram-v2
    [*] --> SESSION_NORMAL

    SESSION_NORMAL --> SESSION_ALERT: risk_score ≥ T_enter
    SESSION_ALERT --> SESSION_NORMAL: risk_score ≤ T_exit

    SESSION_NORMAL --> SESSION_NORMAL: risk_score < T_enter (giữ nguyên)
    SESSION_ALERT --> SESSION_ALERT: T_exit < risk_score < T_enter (vùng đệm, giữ nguyên)

    note right of SESSION_ALERT
        T_exit < T_enter (hysteresis)
        Rising edge (NORMAL→ALERT) = thời điểm sinh ViolationEvent
    end note
```

`T_enter` và `T_exit` cũng là tham số cấu hình qua YAML (mục 4, `docs/DATA_SCHEMAS.md`), khởi tạo thủ công theo mức độ nghiêm trọng chủ quan, tinh chỉnh bằng thực nghiệm Tuần 14 (so sánh có/không hysteresis, đo tỉ lệ báo động giả — theo kế hoạch mục 3.3 của `KE_HOACH_DO_AN.md`).

---

## 4. Sơ đồ luồng người dùng & quản trị viên (Tuần 12-15, lớp platform)

> Khác 3 mục trên (kiến trúc xử lý CV nội bộ 1 phiên) — mục này mô tả cách **3 vai trò con người** tương tác với hệ thống qua lớp platform (backend + dashboard, xem `docs/KE_HOACH_PLATFORM.md`). Không có video/hình ảnh trực tiếp truyền giữa các vai trò (quyết định đã chốt — xem mục 1 `docs/KE_HOACH_PLATFORM.md`), chỉ có số liệu (risk score, loại vi phạm) và ảnh chụp bằng chứng.
>
> **Lưu ý:** mục 4 phản ánh role `admin/proctor` đang có. Sơ đồ kiến trúc mục
> tiêu System Admin/Organization Admin/Exam Manager nằm ở mục 6.

### 4.1. Vai trò

| Vai trò                           | Có tài khoản?                                       | Giao diện dùng                                                     | Quyền chính                                                                                                           |
| ---------------------------------- | ------------------------------------------------------ | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **Quản trị viên (Admin)** | Có (email/mật khẩu)                                 | Web (`/ui/exams`, `/ui/register`)                                | Tạo tổ chức, tạo kỳ thi (sinh`join_code`), tạo tài khoản giám thị                                           |
| **Giám thị (Proctor)**     | Có (do Admin tạo)                                    | Web (`/ui/exams/{id}/dashboard`, `/ui/exams/{id}/sessions/{id}`) | Xem dashboard real-time, xem chi tiết phiên, tải báo cáo —**không tạo được kỳ thi/tài khoản khác** |
| **Thí sinh (Student)**      | Không có tài khoản, chỉ nhập tên +`join_code` | App desktop cục bộ (`main.py`, cửa sổ OpenCV)                  | Tham gia 1 kỳ thi, được giám sát — không truy cập được dashboard/dữ liệu thí sinh khác                  |

### 4.2. Sơ đồ luồng theo từng vai trò

```mermaid
flowchart TB
    subgraph ADMIN["Quan tri vien (Admin)"]
        direction TB
        A1["Dang ky to chuc + tai khoan admin<br/>POST /auth/register - trang /ui/register"]
        A2["Dang nhap<br/>POST /auth/login - trang /ui/login"]
        A3["Tao ky thi<br/>POST /exams - trang /ui/exams<br/>-> nhan join_code"]
        A4["Tao tai khoan giam thi<br/>POST /auth/proctors"]
        A5["Phat join_code cho thi sinh<br/>(ngoai he thong)"]
        A1 --> A2 --> A3 --> A4
        A3 --> A5
    end

    subgraph PROCTOR["Giam thi (Proctor)"]
        direction TB
        P1["Dang nhap<br/>trang /ui/login (tai khoan Admin da tao)"]
        P2["Xem danh sach ky thi<br/>trang /ui/exams"]
        P3["Mo dashboard real-time<br/>trang .../dashboard - WS /ws/dashboard/{exam_id}"]
        P4["Theo doi diem rui ro + trang thai<br/>tung thi sinh, cap nhat lien tuc"]
        P5["Xem chi tiet 1 phien<br/>timeline vi pham + anh chup + bieu do risk score"]
        P6["Tai bao cao PDF/HTML"]
        P1 --> P2 --> P3 --> P4 --> P5 --> P6
    end

    subgraph STUDENT["Thi sinh (Student)"]
        direction TB
        S1["Mo main.py tren may minh"]
        S2["Nhap Ten + Ma tham gia<br/>man hinh IDLE"]
    S3["Liveness chop mat + dang ky khuon mat<br/>ENROLLMENT"]
        S4["Lam bai - he thong giam sat ngam<br/>MONITORING (CV chay CUC BO)"]
        S5["Bam Ket thuc / phim q, ESC"]
        S6["Xem bao cao cuc bo<br/>(luon co, khong phu thuoc backend)"]
        S1 --> S2 --> S3 --> S4 --> S5 --> S6
    end

    A5 -.->|"join_code"| S2
    A4 -.->|"tai khoan"| P1
    S4 -.->|"telemetry_update / violation_event<br/>qua WebSocket"| P4
    S5 -.->|"end_session"| P4
```

### 4.3. Sequence diagram — 1 kỳ thi đầy đủ, cả 3 vai trò

```mermaid
sequenceDiagram
    participant Admin
    participant Backend
    participant Student as Thi sinh
    participant Proctor as Giam thi

    Admin->>Backend: POST /auth/register (tao to chuc + tai khoan admin)
    Admin->>Backend: POST /exams (tao ky thi)
    Backend-->>Admin: join_code
    Admin->>Backend: POST /auth/proctors (tao tai khoan giam thi)
    Admin->>Proctor: phat tai khoan giam thi (ngoai he thong)
    Admin->>Student: phat join_code (ngoai he thong)

    Proctor->>Backend: POST /auth/login
    Proctor->>Backend: mo trang /ui/exams/{id}/dashboard
    Proctor->>Backend: WS /ws/dashboard/{exam_id} (cookie HttpOnly)

    Student->>Backend: POST /exams/join (join_code + ten)
    Backend-->>Student: session_token
    Note over Student: Blink liveness + ENROLLMENT (CUC BO)
    Student->>Backend: WS /ws/client (Authorization: Bearer session_token)

    loop Moi lo telemetry (~1 giay) trong luc thi
        Note over Student: Chay pipeline CV cuc bo (7 signal + Risk Fusion Engine)
        Student->>Backend: telemetry_update / violation_event (WS)
        Note over Backend: validate schema + tinh lai risk/state/severity
        Backend->>Proctor: fan-out real-time (WS dashboard)
    end

    Student->>Backend: end_session (WS)
    Backend->>Proctor: session_ended (WS)
    Proctor->>Backend: GET /sessions/{id}/detail (xem timeline + bieu do)
    Proctor->>Backend: GET /sessions/{id}/report/{fmt} (tai bao cao)
```

**Ghi chú thiết kế:**

- Backend **không chạy model CV**, nhưng không chuyển tiếp mù quáng: nó kiểm tra
  schema, đủ bảy signal, tính lại risk/hysteresis, đối chiếu violation và dùng
  timestamp server trước khi ghi/fan-out.
- Thí sinh **không có tài khoản** — `session_token` (không phải JWT admin/proctor) là "vé" duy nhất, chỉ mở khóa đúng 1 phiên của chính nó (xem `backend/tests/test_auth_token_confusion.py`).
- Nếu backend không kết nối được (Admin/Proctor chưa `docker compose up`, hoặc thí sinh mất mạng), nhánh Thí sinh vẫn chạy hết tới `S6` bình thường — thiết kế offline-first (xem `docs/KE_HOACH_PLATFORM.md` mục 3b).

---

## 5. Tổng hợp liên kết tài liệu

- Kiến trúc pipeline gốc: `KE_HOACH_DO_AN.md`, mục 3.1.
- Đề cương & khảo sát kỹ thuật (cơ sở lý thuyết cho hysteresis, state machine): `docs/DE_CUONG_CHI_TIET.md`, mục 5.3.
- Cấu trúc dữ liệu tương ứng các sơ đồ trên (JSON schema, log format, ground-truth format): `docs/DATA_SCHEMAS.md` (mục 1-6 cho CV, mục 7 cho data model platform).
- Kiến trúc + quyết định thiết kế lớp platform (multi-tenant, backend, dashboard): `docs/KE_HOACH_PLATFORM.md`.

---

## 6. Sơ đồ phân quyền quản trị mục tiêu

```mermaid
flowchart TB
    REQ["REST / WebSocket / file download"] --> AUTHN["Xác thực identity<br/>account + token type + session version"]
    AUTHN --> TENANT["Xác định scope<br/>system hoặc active org_id"]
    TENANT --> CAP["Kiểm tra capability RBAC"]
    CAP --> RESOURCE["Kiểm tra resource scope<br/>org_id + ExamAssignment"]
    RESOURCE --> STATE["Kiểm tra trạng thái/policy<br/>user, org, exam, expiry, deny"]
    STATE --> DECISION{"Cho phép?"}
    DECISION -->|Có| ACTION["Thực hiện transaction"]
    DECISION -->|Không| DENY["404 ngoài scope<br/>403 thiếu capability"]
    ACTION --> AUDIT["Ghi AuditLog bất biến<br/>actor + scope + action + outcome"]
    DENY --> AUDIT

    SYS["System Admin<br/>platform capability<br/>evidence cần quyền truy cập ngoại lệ"] -.-> CAP
    ORG["Organization Admin<br/>membership theo org"] -.-> TENANT
    EXAM["Exam Manager/Giáo viên<br/>owner/manager/proctor"] -.-> RESOURCE
```

Quan hệ phạm vi dữ liệu:

```mermaid
erDiagram
    USER ||--o{ SYSTEM_ROLE : has
    USER ||--o{ ORGANIZATION_MEMBERSHIP : joins
    ORGANIZATION ||--o{ ORGANIZATION_MEMBERSHIP : contains
    ORGANIZATION ||--o{ EXAM : owns
    USER ||--o{ EXAM_ASSIGNMENT : receives
    EXAM ||--o{ EXAM_ASSIGNMENT : scopes
    EXAM ||--o{ EXAM_SESSION : contains
    USER ||--o{ AUDIT_LOG : acts
    ORGANIZATION ||--o{ AUDIT_LOG : scopes
    USER ||--o{ ACCESS_GRANT : requests
    ORGANIZATION ||--o{ ACCESS_GRANT : protects
```

System Admin không có đường truy cập mặc định tới `ExamSession`/evidence. Muốn
hỗ trợ dữ liệu nhạy cảm phải có `AccessGrant` còn hạn; Organization Admin đi
qua membership cùng `org_id`; Exam Manager phải có thêm `ExamAssignment` của
đúng kỳ thi. Chi tiết ma trận quyền và sitemap xem
`docs/QUAN_TRI_VA_PHAN_QUYEN.md`.
