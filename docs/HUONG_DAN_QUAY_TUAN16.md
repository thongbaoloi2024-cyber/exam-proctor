# Hướng dẫn quay & gán nhãn bộ test (Tuần 16)

> Cầm tài liệu này theo khi quay. Khớp đúng định dạng đã thiết kế sẵn ở `docs/DATA_SCHEMAS.md` mục 5 — không tự đổi cấu trúc file, để script đánh giá Tuần 17 đọc được thẳng không cần sửa gì.

---

## 1. Mục tiêu

Quay **~24-30 clip ngắn** (2-5 phút/clip), phủ đủ **6 kịch bản** cố định, mỗi kịch bản tối thiểu 3-5 clip (rủi ro đã ghi ở `KE_HOACH_DO_AN.md` mục 5 — số lượng này đủ để tính Precision/Recall/F1 có ý nghĩa ở mức đồ án, không cần dataset khổng lồ).

Đây là **bộ test để ĐÁNH GIÁ** (không phải dữ liệu huấn luyện) — quay xong, tự xem lại và ghi nhận chính xác THẬT SỰ lúc nào có vi phạm, để Tuần 17 so khớp với output tự động của hệ thống.

## 2. Chuẩn bị trước khi quay

- **Thiết bị quay**: dùng camera của laptop/webcam đúng vị trí giống lúc thi thật (không cần chạy `main.py` lúc quay — xem mục 3). Có thể dùng app Camera có sẵn của Windows, OBS, hoặc điện thoại kê cố định hướng vào màn hình + người ngồi thi — miễn xuất ra được file `.mp4`.
- **Người hỗ trợ**: cần ít nhất **1-2 người khác** cho kịch bản `multi_face` (người thứ 2 xuất hiện) và `impersonation` (người thi hộ) — hẹn trước, không quay được 1 mình cho 2 kịch bản này.
- **Đạo cụ**: 1 điện thoại, 1-2 cuốn sách/tờ ghi chú (cho `phone_usage`), 1 laptop/màn hình có sẵn nội dung để "làm bài" (gõ phím/viết tay bình thường xuyên suốt, để clip trông giống thi thật).
- **Ánh sáng**: đủ sáng, tránh ngược sáng (ngồi quay lưng cửa sổ) — ảnh hưởng trực tiếp tới độ chính xác MTCNN/FaceMesh, không phải chi tiết vặt.

## 3. Cách quay (áp dụng mọi clip)

**Quay video thô trước, chạy pipeline sau** (không chạy `main.py` trong lúc quay) — vì `main.py`/`AppController` hiện chưa lưu lại file video thô của webcam (chỉ xử lý real-time + ghi log số liệu), và vì bắt người quay phải tương tác với cửa sổ OpenCV (nhập tên, đăng ký khuôn mặt...) sẽ làm nhiễu kịch bản diễn. Quay xong, Tuần 17 sẽ dùng `FrameSource(source="đường_dẫn_file.mp4")` (đã hỗ trợ sẵn từ Tuần 3) để chạy lại pipeline offline trên từng clip.

Mỗi clip: đặt máy quay/webcam ở vị trí ổn định trong suốt clip (không di chuyển máy giữa chừng, trừ khi kịch bản yêu cầu), diễn viên coi như đang làm bài thi thật — gõ phím/viết tay xen kẽ, không "diễn" quá lộ liễu, để dữ liệu gần thực tế.

## 4. Kịch bản chi tiết theo từng phút

### 4.1. `normal` — bình thường, KHÔNG vi phạm (3-5 clip, mỗi clip ~2-3 phút)

Dùng để đo **tỉ lệ báo động giả** (false positive) — quan trọng không kém các clip có vi phạm.

```
0:00-3:00  Ngồi làm bài bình thường: nhìn màn hình, gõ phím/viết tay, thỉnh
           thoảng chớp mắt tự nhiên, hơi cúi xuống xem đề rồi ngẩng lên
           (chuyển động đầu NHỎ, tự nhiên — không quay hẳn đi chỗ khác).
           KHÔNG cầm điện thoại, KHÔNG có người khác, KHÔNG nói.
```

Quay **3-5 clip khác nhau** với biến thể tự nhiên khác nhau (1 clip ngồi thẳng suốt, 1 clip có cúi đầu xem đề nhiều hơn, 1 clip có nheo mắt/dụi mắt) — để kiểm tra hệ thống không báo nhầm với các hành vi đời thường vô hại.

### 4.2. `phone_usage` — dùng điện thoại (3-5 clip, ~2.5-3 phút)

Trọng tâm: `OBJECT_DETECTED`. Theo đúng ví dụ mẫu đã có sẵn ở `docs/DATA_SCHEMAS.md`:

```
0:00-0:40  Làm bài bình thường.
0:40-0:58  Cầm điện thoại lên xem (điện thoại RÕ trong khung hình, cầm
           thẳng hướng camera) — ~18 giây.
0:58-1:30  Đặt điện thoại xuống, làm bài tiếp.
1:30-1:36  Cầm điện thoại lên xem NHANH (~6 giây) — kiểm tra phát hiện
           khoảng ngắn.
1:36-3:00  Làm bài bình thường tới hết.
```

**Quay thêm 1-2 clip kiểu "khó"**: điện thoại úp xuống bàn/quay lưng vào camera trong lúc dùng (đã biết đây là điểm yếu của YOLOv8n hiện tại — xem `docs/KE_HOACH_PLATFORM.md`/lịch sử Tuần 4/8) — quay lại đúng trường hợp khó để có số liệu Recall thật, không né tránh.

### 4.3. `gaze_away` — nhìn ra ngoài màn hình (3-5 clip, ~2.5-3 phút)

Trọng tâm: `HEAD_POSE_AWAY`. `EYE_STATE` đo EAR nên chỉ phát hiện mắt nhắm
kéo dài (`EYES_CLOSED`), không suy ra hướng nhìn; muốn đánh giá tín hiệu này hãy
quay thêm một đoạn chủ động nhắm mắt.

```
0:00-0:30  Làm bài bình thường.
0:30-0:38  Liếc nhanh sang bên cạnh (~1-2 giây x vài lần) — KHÔNG NÊN đủ
           lâu để hệ thống báo (kiểm tra debounce hoạt động đúng, không
           báo nhầm với liếc mắt bình thường).
0:45-0:55  Quay đầu nhìn sang bên (như nhìn bài người khác) LIÊN TỤC ~10
           giây.
1:10-1:20  Cúi nhìn xuống ngăn bàn ~10 giây.
1:40-1:50  Ngước lên trần nhà ~10 giây.
2:00-2:30  Vươn vai/xoay cổ tự nhiên (KHÔNG phải nhìn ra ngoài, chỉ là cử
           động cổ bình thường) — kiểm tra không báo nhầm.
2:30-3:00  Làm bài bình thường tới hết.
```

### 4.4. `multi_face` — nhiều người trong khung hình (3-5 clip, ~2.5 phút, CẦN người hỗ trợ)

Trọng tâm: `MULTIPLE_FACES`.

```
0:00-1:00  Chỉ 1 người, làm bài bình thường.
1:00-1:20  Người thứ 2 xuất hiện RÕ trong khung hình (VD đứng sau nhìn
           qua vai) ~20 giây rồi rời đi.
1:20-2:10  Lại chỉ 1 người.
2:10-2:30  Người thứ 2 xuất hiện lần 2, lần này chỉ MỘT PHẦN mặt lọt vào
           khung hình (mép khung hình) — kiểm tra ngưỡng confidence của
           MTCNN với mặt bị cắt.
2:30-2:50  Làm bài bình thường tới hết.
```

### 4.5. `talking` — nói chuyện/thì thầm (3-5 clip, ~2.5 phút)

Trọng tâm: `TALKING` (MOUTH_STATE) — nhớ thiết kế hiện tại dùng tỉ lệ hoạt động trong cửa sổ trượt (không phải "mở miệng liên tục"), nên cần quay đúng kiểu nói chuyện thật (mở/ngậm miệng dồn dập theo từng từ), không phải há miệng giữ nguyên.

```
0:00-0:30  Làm bài im lặng.
0:30-0:50  Nói chuyện/đọc to bài làm (nói liên tục, tự nhiên) ~20 giây.
0:55-1:10  Thì thầm nhỏ (như hỏi bài người bên cạnh) ~15 giây.
1:15-1:45  Im lặng làm bài.
1:45-1:47  Ngáp 1 cái (mở miệng giữ nguyên ngắn) — trường hợp khác talking,
           kiểm tra phân biệt được ngáp và nói chuyện hay không (ghi rõ
           trong `notes`, có thể để `violation_type: "TALKING"` hoặc bỏ
           qua tuỳ bạn quan sát hệ thống phản ứng thế nào — ghi chú lại
           để phân tích ở Tuần 18, không bắt buộc đúng/sai).
1:50-3:00  Làm bài im lặng tới hết.
```

### 4.6. `impersonation` — đổi người thi hộ (3-5 clip, ~3-3.5 phút, CẦN người hỗ trợ)

Trọng tâm: `IDENTITY_MISMATCH`. Đây là kịch bản **không có nguồn dữ liệu công khai nào thay thế được** (đã xác nhận qua khảo sát trước đó) — bắt buộc phải tự quay.

```
0:00-1:30  Người A ngồi làm bài bình thường (đây là đoạn dùng để "đăng
           ký" khuôn mặt tham chiếu khi chạy lại pipeline ở Tuần 17 — giữ
           đủ ~5-10 giây đầu người A NHÌN THẲNG CAMERA rõ mặt).
1:30-1:45  Người A đứng dậy, người B ngồi vào NHANH, tiếp tục "làm bài"
           như bình thường (đóng vai thi hộ, không cần diễn lộ liễu).
1:45-3:00  Người B tiếp tục làm bài bình thường tới hết.
```

Quay **ít nhất 2 người khác nhau** cho vai "người thi hộ" nếu có thể (không chỉ 1 cặp A/B lặp lại nhiều clip) — đa dạng hoá để số liệu Recall không bị lệch theo đặc điểm riêng của 1 cặp mặt cụ thể.

## 5. Checklist số lượng

| Kịch bản | Số clip tối thiểu | Đã quay |
|---|---|---|
| `normal` | 3-5 | ☐ |
| `phone_usage` | 3-5 (có ít nhất 1 clip "khó" — điện thoại úp) | ☐ |
| `gaze_away` | 3-5 | ☐ |
| `multi_face` | 3-5 | ☐ |
| `talking` | 3-5 | ☐ |
| `impersonation` | 3-5 (ít nhất 2 người khác nhau đóng vai thi hộ) | ☐ |
| **Tổng** | **18-30 clip** | ☐ |

## 6. Lưu trữ file — đúng cấu trúc `docs/DATA_SCHEMAS.md` mục 5.1

```
data/test_set/
├── manifest.csv
├── clip_001_normal/
│   ├── clip_001_normal.mp4
│   └── clip_001_normal.labels.json
├── clip_002_phone/
│   ├── clip_002_phone.mp4
│   └── clip_002_phone.labels.json
└── ...
```

Đặt tên `clip_<số thứ tự 3 chữ số>_<scenario ngắn gọn>` — số thứ tự tăng dần xuyên suốt (không tính riêng theo từng kịch bản), scenario ngắn gọn dùng đúng 1 trong 6 tên: `normal`, `phone`, `gaze_away`, `multi_face`, `talking`, `impersonation` (folder name không cần trùng y hệt giá trị `scenario` trong JSON — giá trị `scenario` trong JSON mới là cái script đánh giá đọc, xem mục 7).

**Dùng script hỗ trợ** (`scripts/scaffold_test_clip.py`, xem mục 8) để tự tạo đúng khung thư mục + file nhãn rỗng, tránh gõ tay JSON sai định dạng.

## 7. Quy trình gán nhãn

1. Copy file video vừa quay vào đúng thư mục `data/test_set/clip_XXX_yyy/clip_XXX_yyy.mp4`.
2. Chạy `scripts/scaffold_test_clip.py` (mục 8) để tạo file `.labels.json` khung sẵn + cập nhật `manifest.csv`.
3. Mở lại video bằng trình phát bất kỳ CÓ HIỂN THỊ THỜI GIAN (VLC, Windows Media Player, hoặc trình phát mặc định của Windows đều hiện thanh thời gian) — tua qua, ghi lại CHÍNH XÁC giây bắt đầu/kết thúc từng vi phạm THẬT (theo mắt bạn quan sát, không phải theo hệ thống báo).
4. Mở file `.labels.json` vừa tạo, điền mảng `"violations"` — mỗi vi phạm 1 phần tử, đúng định dạng:
   ```jsonc
   {
     "start_time_sec": 42.0,
     "end_time_sec": 58.5,
     "violation_type": "OBJECT_DETECTED",
     "notes": "cam dien thoai len xem ~16s"
   }
   ```
   `violation_type` PHẢI dùng đúng 1 trong 7 giá trị cố định ở `docs/DATA_SCHEMAS.md` mục 1.2: `FACE_ABSENT`, `MULTIPLE_FACES`, `EYES_CLOSED`, `TALKING`, `OBJECT_DETECTED`, `HEAD_POSE_AWAY`, `IDENTITY_MISMATCH` — sai chính tả 1 chữ sẽ làm script đánh giá Tuần 17 không so khớp được.
5. Clip `normal` (không vi phạm) vẫn giữ `"violations": []` — KHÔNG xoá file, không để trống — đây là dữ liệu cần thiết để tính tỉ lệ báo động giả.
6. 1 clip có thể có NHIỀU vi phạm chồng lấn thời gian (VD vừa nhìn lệch vừa nói chuyện cùng lúc) — cứ ghi đủ từng cái, không cần gộp.

## 8. Script hỗ trợ dựng khung thư mục/nhãn

```bash
python scripts/scaffold_test_clip.py \
    --clip-id clip_002_phone \
    --scenario phone_usage \
    --duration-sec 187 \
    --num-people 1 \
    --notes "dung dien thoai 2 lan, 1 lan up mat sau"
```

Lệnh trên tạo `data/test_set/clip_002_phone/clip_002_phone.labels.json` (khung rỗng, `violations: []` để bạn tự điền theo mục 7) và tự thêm/cập nhật đúng dòng tương ứng trong `data/test_set/manifest.csv`. Chạy lại nhiều lần cho từng clip đã quay — không ghi đè nếu file nhãn đã tồn tại (an toàn khi chạy nhầm 2 lần).

## 9. Sau khi quay xong — báo lại

Không cần chạy pipeline hay tính số liệu gì lúc này (đó là việc Tuần 17). Chỉ cần: xác nhận đủ số lượng theo checklist mục 5, tất cả file `.mp4`+`.labels.json` đã có trong `data/test_set/`, và `manifest.csv` liệt kê đủ toàn bộ clip — báo lại để tiếp tục Tuần 17 (cài baseline + đo Precision/Recall/F1).
