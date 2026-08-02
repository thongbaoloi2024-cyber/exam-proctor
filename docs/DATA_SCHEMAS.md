# Thiết kế cấu trúc dữ liệu

> Tuần 2. Thiết kế trước khi code. Các schema dưới đây là hợp đồng dữ liệu (data contract) giữa các tầng trong `docs/DIAGRAMS.md`: `SignalResult` là output chung của Signal Extractors, `ViolationEvent` là output của Risk Fusion Engine, log format là cách các event/state-change được ghi lại, và ground-truth format phục vụ bộ test Tuần 13.

> Cập nhật hardening: protocol mạng dùng schema chặt trong
> `backend/ws_schemas.py`. Client gửi `telemetry_update` chứa đủ 7 signal;
> server tự tính lại risk/state và chỉ lưu snapshot bytes đã kiểm tra. Timestamp
> server là thời gian chuẩn, timestamp client chỉ dùng audit.

---

## 1. Danh mục loại tín hiệu & loại vi phạm (enum dùng xuyên suốt)

Để `SignalResult`, `ViolationEvent`, và ground-truth labeling dùng chung một bộ tên (tránh lệch tên giữa các module — lỗi đã ghi nhận ở dự án tham khảo, mục 3.2.3 của `KE_HOACH_DO_AN.md`), định nghĩa 2 enum cố định:

### 1.1. `signal_name` (7 giá trị, ứng với 7 signal extractor)

| `signal_name` | Signal extractor | Tuần cài đặt |
|---|---|---|
| `FACE_PRESENCE` | FacePresenceSignal | 3 |
| `MULTI_FACE` | MultiFaceSignal | 3 |
| `EYE_STATE` | EyeStateSignal (EAR) | 4 |
| `MOUTH_STATE` | MouthStateSignal | 4 |
| `OBJECT_PRESENCE` | ObjectSignal | 4 |
| `HEAD_POSE` | HeadPoseSignal (solvePnP) | 5 |
| `IDENTITY` | IdentitySignal (FaceNet) | 6 |

### 1.2. `violation_type` (dùng trong `ViolationEvent` và ground-truth labeling)

| `violation_type` | Sinh ra chủ yếu từ signal | Mô tả |
|---|---|---|
| `FACE_ABSENT` | `FACE_PRESENCE` | Không có khuôn mặt trong khung hình liên tục |
| `MULTIPLE_FACES` | `MULTI_FACE` | Nhiều hơn 1 khuôn mặt trong khung hình |
| `EYES_CLOSED` | `EYE_STATE` | Cả hai mắt nhắm kéo dài (EAR thấp bất thường) |
| `TALKING` | `MOUTH_STATE` | Miệng hoạt động bất thường (nói/thì thầm) |
| `OBJECT_DETECTED` | `OBJECT_PRESENCE` | Phát hiện điện thoại/sách trong khung hình |
| `HEAD_POSE_AWAY` | `HEAD_POSE` | Góc yaw/pitch vượt ngưỡng "nhìn ra ngoài màn hình" |
| `IDENTITY_MISMATCH` | `IDENTITY` | Khuôn mặt hiện tại không khớp khuôn mặt enrollment (nghi thi hộ) |

`violation_type` là nhãn ở **mức signal**; một `ViolationEvent` thực tế có thể có nhiều `violation_type` đồng thời làm `contributing_signals` (khác bản tham khảo — xem mục 2).

---

## 2. `SignalResult` — output chung của mọi Signal Extractor

Interface thống nhất (theo kế hoạch chuẩn hoá ở Tuần 7), mọi signal extractor implement `process(frame, perception_result) -> SignalResult`:

```jsonc
{
  "signal_name": "HEAD_POSE",          // enum mục 1.1
  "timestamp": 1721030455.812,          // unix epoch (float, giây) tại thời điểm frame được xử lý
  "value": 27.4,                        // giá trị thô đặc thù signal (VD: độ yaw; với EYE_STATE là EAR; với OBJECT_PRESENCE là 1/0)
  "exceeds_threshold": true,            // cờ nhị phân: value có vượt ngưỡng thô của riêng signal này không
  "confidence": 0.91,                   // độ tin cậy của model nền (VD: landmark detection confidence)
  "state": "SUSPICIOUS",                // NORMAL | SUSPICIOUS | ALERT — do state machine của Risk Fusion Engine set (mục 3.1 DIAGRAMS.md)
  "metadata": {                         // dữ liệu phụ, đặc thù từng signal, phục vụ debug/report/luận văn
    "yaw": 27.4,
    "pitch": -3.1,
    "roll": 1.8
  }
}
```

**Ví dụ `metadata` theo từng signal** (không bắt buộc field cố định — mỗi signal tự định nghĩa nội dung `metadata`, chỉ 5 field đầu là bắt buộc chung):

| `signal_name` | `value` là gì | `metadata` gợi ý |
|---|---|---|
| `FACE_PRESENCE` | 1 nếu có mặt, 0 nếu không | `{"consecutive_absent_sec": 2.3}` |
| `MULTI_FACE` | số khuôn mặt phát hiện được | `{"face_boxes": [[x,y,w,h], ...]}` |
| `EYE_STATE` | giá trị EAR trung bình 2 mắt | `{"ear_left": 0.18, "ear_right": 0.21}` |
| `MOUTH_STATE` | độ mở miệng chuẩn hoá (giá trị tức thời) | `{"mouth_open_ratio": 0.42, "activity_ratio": 0.55}` — `exceeds_threshold` dựa trên `activity_ratio` (tỉ lệ % thời gian mở trong cửa sổ trượt ~2s), không phải `mouth_open_ratio` tức thời, để bắt được cả kiểu nói chuyện (mở/ngậm xen kẽ liên tục) lẫn há miệng giữ nguyên |
| `OBJECT_PRESENCE` | 1 nếu phát hiện vật cấm, 0 nếu không | `{"object_class": "cell phone", "bbox": [x,y,w,h]}` |
| `HEAD_POSE` | góc yaw (độ) | `{"yaw": 27.4, "pitch": -3.1, "roll": 1.8}` |
| `IDENTITY` | cosine similarity với embedding enrollment | `{"cosine_similarity": 0.42, "last_verified_at": 1721030400.0}` |

---

## 3. `ViolationEvent` — output của Risk Fusion Engine

Sinh ra tại **rising edge** của `SessionRiskState` (NORMAL → ALERT, xem mục 3.2 `docs/DIAGRAMS.md`):

```jsonc
{
  "event_id": "b3f1e2a0-7c4d-4e9a-9f0b-1a2b3c4d5e6f",   // uuid4
  "session_id": "session_20260722_140501",               // id phiên giám sát (1 lần chạy app)
  "video_time_sec": 184.6,                                // thời điểm tính từ lúc bắt đầu phiên (giây) — dùng để đối chiếu ground truth
  "timestamp": "2026-07-22T14:08:05.812+07:00",           // wall-clock ISO 8601, phục vụ đọc log trực quan
  "risk_score": 5.0,                                       // điểm rủi ro tổng hợp tại thời điểm sinh event
  "severity": "HIGH",                                      // LOW | MEDIUM | HIGH — suy ra từ risk_score theo ngưỡng cấu hình
  "primary_violation": "IDENTITY_MISMATCH",                 // violation_type của signal có (weight × state_value) cao nhất đang ALERT
  "contributing_signals": [                                 // TẤT CẢ signal đang SUSPICIOUS/ALERT tại thời điểm này (không chỉ 1 cái)
    {
      "signal_name": "IDENTITY",
      "violation_type": "IDENTITY_MISMATCH",
      "state": "ALERT",
      "value": 0.42,
      "weight": 3.0
    },
    {
      "signal_name": "HEAD_POSE",
      "violation_type": "HEAD_POSE_AWAY",
      "state": "SUSPICIOUS",
      "value": 27.4,
      "weight": 1.0
    }
  ],
  "snapshot_path": "sessions/session_20260722_140501/snapshots/evt_b3f1e2a0.jpg",
  "metadata": {
    "fusion_config_version": "v1"                          // để biết event này sinh ra với bộ trọng số/ngưỡng nào (đổi config theo thời gian ở Tuần 14)
  }
}
```

**Điểm khác biệt thiết kế so với bản tham khảo**: `contributing_signals` là **mảng**, không phải 1 giá trị — cho phép ghi nhận nhiều vi phạm đồng thời (VD vừa `HEAD_POSE_AWAY` vừa `IDENTITY_MISMATCH`) thay vì chỉ 1 loại/frame theo if/elif ưu tiên.

---

## 4. Định dạng log của một phiên giám sát

Mỗi phiên (`session_id`) có thư mục riêng `sessions/<session_id>/` gồm:

```
sessions/session_20260722_140501/
├── session_meta.json        # thông tin phiên: thời điểm bắt đầu/kết thúc, config snapshot, thông tin thí sinh (nếu có)
├── signals.jsonl            # telemetry SignalResult đã được server/client ghi nhận
├── state_transitions.jsonl  # mọi lần đổi trạng thái của per-signal state machine VÀ session state (mục 3, DIAGRAMS.md)
├── violations.jsonl         # danh sách ViolationEvent (mục 3 ở trên), mỗi dòng 1 JSON object
├── browser_events.jsonl     # sự kiện toàn vẹn từ Chrome/Firefox extension; severity/timestamp do server gắn
├── risk_score_timeline.jsonl # risk score theo thời gian để dựng biểu đồ
└── snapshots/                # ảnh chụp kèm mỗi violation event
    └── evt_<event_id>.jpg
```

`browser_events.jsonl` tách khỏi `violations.jsonl` để một thao tác như chuyển
tab hoặc thoát fullscreen không bị trình bày như kết luận CV. Bản ghi gồm
`event_id`, `sequence`, `event_type`, `client_timestamp`, server `timestamp`,
`video_time_sec`, `severity`, `server_duration_ms`, origin đã rút gọn và
`snapshot_path` tùy chọn. Không ghi URL query/fragment hoặc nội dung clipboard.

**`state_transitions.jsonl`** — mỗi dòng 1 lần chuyển trạng thái (không log mỗi frame, chỉ log lúc *đổi* trạng thái — tránh phình log):

```jsonc
{"timestamp": 1721030455.2, "scope": "signal", "signal_name": "EYE_STATE", "from_state": "NORMAL", "to_state": "SUSPICIOUS", "exceed_ratio": 0.31}
{"timestamp": 1721030460.8, "scope": "session", "from_state": "SESSION_NORMAL", "to_state": "SESSION_ALERT", "risk_score": 5.0}
```

`scope`: `"signal"` (per-signal state machine, mục 3.1 DIAGRAMS.md) hoặc `"session"` (tầng tổng hợp hysteresis, mục 3.2 DIAGRAMS.md).

**`session_meta.json`**:

```jsonc
{
  "session_id": "session_20260722_140501",
  "started_at": "2026-07-22T14:05:01+07:00",
  "ended_at": "2026-07-22T14:35:20+07:00",
  "enrollment_snapshot": "sessions/session_20260722_140501/enrollment.jpg",
  "fusion_config_version": "v1",
  "fps_avg": 18.4
}
```

Lý do dùng **JSONL** (JSON Lines) thay vì 1 file JSON lớn: ghi tăng dần theo thời gian thực (append-only) mà không cần đọc/ghi lại toàn bộ file mỗi lần có event mới — phù hợp pipeline chạy real-time.

---

## 5. Định dạng ground-truth labeling (bộ test Tuần 13)

Mục tiêu: gán nhãn thời điểm vi phạm **thật** (con người xem video xác nhận) cho từng clip, để đối chiếu với output của pipeline (`violations.jsonl`) khi tính Precision/Recall/F1 ở Tuần 14.

### 5.1. Tổ chức thư mục

```
data/test_set/
├── manifest.csv                  # danh mục toàn bộ clip + kịch bản (mục 5.3)
├── clip_001_normal/
│   ├── clip_001_normal.mp4
│   └── clip_001_normal.labels.json
├── clip_002_phone/
│   ├── clip_002_phone.mp4
│   └── clip_002_phone.labels.json
├── clip_003_gaze_away/
│   └── ...
└── clip_0xx_impersonation/       # kịch bản đổi người thi hộ
    └── ...
```

### 5.2. `<clip>.labels.json` — nhãn ground truth cho 1 clip

```jsonc
{
  "clip_id": "clip_002_phone",
  "video_file": "clip_002_phone.mp4",
  "duration_sec": 187.0,
  "scenario": "phone_usage",             // xem danh mục kịch bản mục 5.3
  "annotator": "sinh_vien_thuc_hien",
  "annotated_at": "2026-11-10",
  "violations": [
    {
      "start_time_sec": 42.0,
      "end_time_sec": 58.5,
      "violation_type": "OBJECT_DETECTED",   // dùng đúng enum mục 1.2 để đối chiếu tự động với pipeline output
      "notes": "cầm điện thoại lên xem ~16s"
    },
    {
      "start_time_sec": 120.0,
      "end_time_sec": 126.0,
      "violation_type": "HEAD_POSE_AWAY",
      "notes": "nhìn xuống điện thoại dưới bàn"
    }
  ]
}
```

Quy ước: clip "bình thường" (không vi phạm) vẫn có file `.labels.json` với `"violations": []` — để script đánh giá phân biệt được "không có nhãn" (thiếu file, lỗi) với "có nhãn nhưng rỗng" (đúng là không vi phạm, dùng để đo false positive rate).

### 5.3. `manifest.csv` — danh mục toàn bộ bộ test

Định dạng CSV (dễ mở bằng Excel/Google Sheets để theo dõi tiến độ quay ở Tuần 13):

```csv
clip_id,scenario,duration_sec,num_people,has_impersonation,notes
clip_001_normal,normal,180,1,false,kich ban binh thuong khong vi pham
clip_002_phone,phone_usage,187,1,false,dung dien thoai 2 lan
clip_003_gaze_away,gaze_away,165,1,false,nhin ra ngoai man hinh nhieu lan
clip_004_multi_face,multi_face,150,2,false,co nguoi thu 2 xuat hien giua clip
clip_005_talking,talking,140,1,false,noi chuyen/thi thham
clip_006_impersonation,impersonation,200,1,true,doi nguoi thi ho o giay 90
```

Danh mục `scenario` cố định (khớp mục 3.3 `KE_HOACH_DO_AN.md`): `normal`, `phone_usage`, `gaze_away`, `multi_face`, `talking`, `impersonation`. Mỗi `scenario` cần tối thiểu 3-5 clip (rủi ro đã ghi ở `KE_HOACH_DO_AN.md` mục 5).

### 5.4. Cách dùng cho đánh giá (Tuần 14)

Script đánh giá sẽ: (1) chạy pipeline trên từng clip → thu `violations.jsonl`; (2) so khớp từng `ViolationEvent` (theo `video_time_sec` và `primary_violation`/`contributing_signals`) với các khoảng `[start_time_sec, end_time_sec]` cùng `violation_type` trong `.labels.json` — một event được tính là **True Positive** nếu `video_time_sec` rơi vào (hoặc trong biên độ dung sai vài giây quanh) một khoảng ground-truth cùng loại; nếu không khớp khoảng nào → **False Positive**; khoảng ground-truth không có event nào khớp → **False Negative**. Độ trễ phát hiện = `event.video_time_sec - ground_truth.start_time_sec` (chỉ tính cho True Positive).

---

## 6. Cấu hình trọng số & ngưỡng (fusion config)

Tham chiếu tới mục 3.2 `docs/DIAGRAMS.md` — toàn bộ trọng số (`weight_i`), ngưỡng per-signal (`r_enter_susp`, `r_exit_susp`, `r_enter_alert`, `r_exit_alert`), và ngưỡng session (`T_enter`, `T_exit`) được cấu hình qua 1 file YAML duy nhất (không hardcode — theo yêu cầu Tuần 12), ví dụ cấu trúc:

```yaml
# config/fusion.yaml
window_sec: 4.0

signals:
  FACE_PRESENCE:
    weight: 2.0
    r_enter_susp: 0.3
    r_exit_susp: 0.15
    r_enter_alert: 0.6
    r_exit_alert: 0.4
  MULTI_FACE:
    weight: 2.0
    r_enter_susp: 0.3
    r_exit_susp: 0.15
    r_enter_alert: 0.6
    r_exit_alert: 0.4
  EYE_STATE:
    weight: 1.0
    r_enter_susp: 0.3
    r_exit_susp: 0.15
    r_enter_alert: 0.6
    r_exit_alert: 0.4
  MOUTH_STATE:
    weight: 1.0
    r_enter_susp: 0.3
    r_exit_susp: 0.15
    r_enter_alert: 0.6
    r_exit_alert: 0.4
  OBJECT_PRESENCE:
    weight: 2.5
    r_enter_susp: 0.2
    r_exit_susp: 0.1
    r_enter_alert: 0.4
    r_exit_alert: 0.25
  HEAD_POSE:
    weight: 1.0
    r_enter_susp: 0.3
    r_exit_susp: 0.15
    r_enter_alert: 0.6
    r_exit_alert: 0.4
  IDENTITY:
    weight: 3.0
    reverify_interval_sec: 30
    cosine_threshold_warn: 0.55
    cosine_threshold_alert: 0.40

session:
  T_enter: 5.0
  T_exit: 2.5
```

Các con số trên là **giá trị khởi tạo minh hoạ** (đặt theo mức độ nghiêm trọng chủ quan: `IDENTITY` và `OBJECT_PRESENCE` có trọng số cao nhất — theo đúng định hướng mục 5, Tuần 10 của `KE_HOACH_4_THANG_THEO_TUAN.md`), sẽ tinh chỉnh bằng thực nghiệm ở Tuần 14, không phải số liệu cuối cùng.

---

## 7. Data model phía platform (`backend/`, Tuần 12 mới)

> Xem `docs/KE_HOACH_PLATFORM.md` cho kiến trúc đầy đủ. Mục này chỉ ghi lại phần data model để nhất quán với các schema ở mục 1-6.

Nguyên tắc quan trọng nhất: **schema `SignalResult`/`ViolationEvent` ở mục 2-3 và định dạng log ở mục 4 KHÔNG đổi.** Backend không lưu lại nội dung sự kiện trong SQL — nó chỉ dựng đúng thư mục `sessions/<id>/` (mục 4) từ phía server rồi ghi/đọc y hệt định dạng cũ, để `src/reporting/generate_report()` dùng lại nguyên vẹn.

DB (`backend/models.py`, SQLAlchemy) chỉ lưu **con trỏ + trạng thái hiện tại**, phục vụ multi-tenant/auth/dashboard — không phải nơi lưu trữ sự thật (source of truth) của sự kiện giám sát:

| Bảng | Trường chính | Vai trò |
|---|---|---|
| `Organization` | `id, name` | Gốc multi-tenant — mọi User/Exam thuộc về đúng 1 Organization |
| `User` | `id, org_id, email, password_hash, role` | Chỉ `admin`/`proctor` (2 vai trò có tài khoản thật). **Học sinh KHÔNG có row ở đây** |
| `Exam` | `id, org_id, name, join_code, status, candidate_auth_mode, exam_url, require_*, min_extension_version, google_allowed_domain` | Kỳ thi, mã tham gia và chính sách extension/xác thực do giám thị chọn |
| `CandidateIdentity` | `id, provider_subject, email, email_verified, display_name, hosted_domain` | Claim Google OIDC tối thiểu đã được backend xác minh; không lưu Google token |
| `CandidateDevice` | `candidate_identity_id, device_id_hash, token_hash, expires_at, revoked_at` | Opaque token riêng của hệ thống để dùng lại hồ sơ trên một cài đặt extension |
| `CandidateOAuthTransaction` | `state_hash, pkce_verifier, oidc_nonce, grant_hash, expires_at, grant_used_at` | State/PKCE và grant một lần của Google login |
| `ExamSession` | `id, exam_id, student_name, candidate_number/email, authentication_method, client_type, status, risk_score_current, integrity_score_current, browser_event_count` | Phiên giám sát; risk CV và integrity browser luôn tách riêng |

`risk_score_current`/`session_state_current` là bản sao mới nhất của telemetry đã
được server kiểm tra, cập nhật theo lô (mặc định 1 giây), để dashboard tải trạng
thái ban đầu mà không cần đọc lại file `.jsonl`.

## 8. Liên kết tài liệu

- Sơ đồ kiến trúc & state diagram tương ứng: `docs/DIAGRAMS.md`.
- Đề cương & cơ sở lý thuyết (lý do chọn hysteresis, weighted fusion): `docs/DE_CUONG_CHI_TIET.md`, mục 5.3.
- Kế hoạch tổng: `KE_HOACH_DO_AN.md`, mục 3 (thiết kế kỹ thuật) và mục 3.3 (đánh giá định lượng).
- Kiến trúc + lộ trình lớp platform (multi-tenant, cloud, dashboard giám thị): `docs/KE_HOACH_PLATFORM.md` (Tuần 12 mới trở đi).
