# Hướng dẫn Demo Tuần 8 — kịch bản chi tiết cho bạn tự chạy

> Vì máy dev không có webcam, việc này cần bạn trực tiếp làm trên máy có webcam. File này là kịch bản chi tiết từng bước — làm xong gửi lại kết quả (console output + nhận xét) theo mẫu ở mục 3, tôi sẽ phân tích và sửa bug ưu tiên cao ngay (mục 2 của Tuần 8).

## 1. Chuẩn bị

```bash
git pull origin main
# activate venv (Windows: venv\Scripts\activate)
pip install -r requirements.txt    # phòng khi requirements.txt đổi
python main.py
```

- Cửa sổ webcam hiện ra → bước **enrollment**: nhìn thẳng camera, giữ yên vài giây tới khi console in `Dang ky khuon mat THANH CONG`. Nếu in `Khong tim thay khuon mat... thu lai` nhiều lần liên tục → tự nó đã là 1 bug cần báo lại (mục 3).
- Sau enrollment, cửa sổ chính hiện overlay 7 dòng tín hiệu (FACE_PRESENCE, MULTI_FACE, EYE_STATE, MOUTH_STATE, OBJECT_PRESENCE, HEAD_POSE, IDENTITY) — màu vàng = bình thường, màu đỏ = đang `exceeds=True`.
- Giữ cửa sổ Terminal/console nhìn thấy được song song để đọc log real-time.

## 2. Kịch bản test theo thứ tự (~8-10 phút)

Làm tuần tự, mỗi bước 30s-2 phút, **nói to hoặc ghi chú lại giờ:phút bạn bắt đầu mỗi bước** (để đối chiếu với log sau) — không cần chính xác tuyệt đối, chỉ cần đủ để tra lại.

### 2.1. Baseline (30 giây)
Ngồi yên, nhìn thẳng màn hình bình thường như đang làm bài thi thật.
**Kỳ vọng**: không tín hiệu nào chuyển đỏ (`exceeds=True`), không dòng `VUOT NGUONG` nào xuất hiện trong console.

### 2.2. Head pose — quay đầu (1 phút)
Quay đầu sang **phải** của chính bạn giữ ~2s, về giữa, sang **trái** giữ ~2s, về giữa, **ngẩng lên** giữ ~2s, về giữa, **cúi xuống** giữ ~2s.
**Quan sát và ghi lại**:
- Giá trị `yaw`/`pitch` hiển thị trên overlay cạnh mũi có tăng/giảm đúng chiều bạn quay không (VD quay phải thì yaw có tăng dần theo hướng nhất quán không, không cần biết dấu đúng hay sai, chỉ cần NHẤT QUÁN).
- Trục màu vẽ từ mũi (đỏ/xanh lá/xanh dương) có xoay theo hướng mặt bạn đang quay không, hay đứng yên/xoay sai hướng.
- Sau khi giữ quay đủ lâu (>1s), `HEAD_POSE` có chuyển đỏ (`exceeds=True`) không.

### 2.3. Mắt — nhắm mắt kéo dài (1 phút)
Nhắm mắt thật chặt, giữ nguyên **>=2 giây**, mở ra, chớp mắt bình thường vài lần (không tính là vi phạm), rồi nhắm lại **>=2 giây** lần nữa.
**Quan sát**: `EYE_STATE` có chuyển đỏ khi nhắm lâu không (đây là bug đã sửa tuần trước — nhắm mắt hẳn giờ phải nhận diện được), và có KHÔNG chuyển đỏ khi chỉ chớp mắt bình thường.

### 2.4. Miệng — nói chuyện (1 phút)
Nói chuyện liên tục ~15-20 giây (đọc to 1 đoạn văn bất kỳ), sau đó im lặng ~15 giây, rồi nói tiếp ~15 giây.
**Quan sát**: `MOUTH_STATE` có chuyển đỏ trong lúc nói (không cần từng từ, chỉ cần trong khoảng nói liên tục nó chuyển đỏ), và trở lại vàng khi im lặng.

### 2.5. Vật thể — điện thoại (1-2 phút)
- Đưa điện thoại vào khung hình, **màn hình/mặt trước hướng về camera**, giữ ~3 giây.
- Cất đi, đợi vài giây.
- Đưa lại nhưng lần này **úp mặt lưng điện thoại** về phía camera, giữ ~3 giây.
**Quan sát**: `OBJECT_PRESENCE` có chuyển đỏ ở cả 2 trường hợp không, hay chỉ ở trường hợp mặt trước (đây là vấn đề đã biết, đang muốn xác nhận đã cải thiện chưa sau khi trả `imgsz` về 640).

### 2.6. Nhiều người (1 phút)
Nhờ 1 người khác đứng/ngồi vào khung hình cùng bạn ~10-15 giây, sau đó họ ra khỏi khung hình.
**Quan sát**: `MULTI_FACE` có chuyển đỏ khi có 2 người, và trở lại vàng khi chỉ còn 1 người.

### 2.7. Vắng mặt (30 giây)
Bước hẳn ra khỏi khung hình / che kín camera trong >=3 giây, rồi quay lại.
**Quan sát**: `FACE_PRESENCE` có chuyển đỏ sau ~2 giây vắng mặt, trở lại vàng khi bạn xuất hiện lại.

### 2.8. Đổi người — quan trọng nhất (2-3 phút, cần chờ đủ thời gian)
`IdentitySignal` chỉ re-verify mỗi 30 giây và cần **2 lần fail liên tiếp** (~60-90 giây) mới báo `IDENTITY_MISMATCH` — bước này cần kiên nhẫn chờ, không phản ứng ngay như các signal khác.
- Nhờ người khác ngồi thay vào vị trí của bạn trước camera, giữ nguyên **liên tục ít nhất 90 giây** (đừng đổi qua đổi lại).
**Quan sát**: sau khoảng 60-90 giây, `IDENTITY` có chuyển đỏ (`exceeds=True`) và console có in `[IDENTITY] VUOT NGUONG` không. Ghi lại giá trị `value` (chính là cosine similarity) hiển thị lúc đó.

### 2.9. False positive của Identity — ánh sáng/góc (2-3 phút)
Vẫn là bạn (KHÔNG đổi người), thử lần lượt: bật/tắt bớt đèn phòng, nghiêng đầu nhẹ, ngồi lệch sang 1 bên — mỗi kiểu giữ vài chục giây.
**Quan sát và ghi lại**: giá trị `similarity`/`warning` hiển thị trong overlay dao động trong khoảng nào — có bao giờ tụt xuống mức cảnh báo (`warning=True`) hoặc tệ hơn là báo `IDENTITY_MISMATCH` dù bạn không hề đổi người không. Đây chính là **tỉ lệ false positive** cần đo.

## 3. Cách gửi lại kết quả cho tôi

Chỉ cần gửi những gì bạn có, không cần làm màu mè:

1. **Copy toàn bộ hoặc phần liên quan của console output** — đặc biệt mọi dòng chứa `VUOT NGUONG` (kèm timestamp nếu terminal có hiển thị, hoặc ước lượng "khoảng phút thứ mấy trong lúc test").
2. **Đoạn báo cáo hiệu năng cuối cùng** khi bạn nhấn `q`/ESC thoát — phần in ra bắt đầu bằng `--- Bao cao hieu nang ---` (để tôi so với số liệu tôi đo trên máy dev ở Tuần 7, xem máy bạn có khác biệt lớn không).
3. **Nhận xét bằng lời** theo từng mục 2.1-2.9 ở trên: tín hiệu nào đúng, tín hiệu nào sai/không phản ứng/phản ứng chậm/phản ứng nhầm.
4. (Không bắt buộc) File `sessions/demo_session.jsonl` sinh ra sau khi chạy — nếu tiện, dán vài dòng mẫu hoặc mô tả sơ qua, không cần gửi cả file.

Nếu có bất kỳ **crash/treo máy/lỗi đỏ (traceback)** ở bất kỳ bước nào — dừng lại, copy nguyên traceback, đó là bug ưu tiên cao nhất cần sửa trước tiên.

## 4. Sau khi có kết quả

Tôi sẽ: (1) đối chiếu với danh sách bug đã biết (đã liệt kê ở tin nhắn trước), (2) sửa ngay các lỗi mức "crash / signal hoàn toàn không phản ứng", (3) ghi nhận các lỗi về độ chính xác (false positive/negative nhẹ) lại làm việc tinh chỉnh Tháng 3-4 theo đúng tinh thần đề bài Tuần 8.
