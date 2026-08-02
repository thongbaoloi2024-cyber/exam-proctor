# Ghi chú kỹ thuật: Xác thực danh tính bằng Face Embedding

> Tuần 6. Giải thích cách chọn ngưỡng cosine similarity, cơ chế enrollment/
> re-verification, và giới hạn của phương pháp khi ánh sáng/góc nghiêng thay
> đổi mạnh — dùng làm nguồn cho chương "Cài đặt hệ thống" của luận văn. Code
> tương ứng: `src/perception/face_embedder.py` (trích embedding) và
> `src/signals/identity.py` (`IdentitySignal` — enrollment + re-verification
> + ngưỡng có biên độ). Kiểm chứng bằng test: `tests/test_identity_signal.py`
> (logic, dùng embedder giả lập), `tests/test_identity_smoke.py` (tích hợp
> model thật, chỉ xác nhận không crash — độ chính xác thật cần webcam).

## 1. Vì sao đây là kỹ thuật mới hoàn toàn (không có trong bản tham khảo)

Bản tham khảo (`exam-cheating-detection`) chỉ đếm **số lượng** khuôn mặt
trong khung hình (`MultiFaceSignal`-kiểu-tương-đương) — không có bất kỳ cơ
chế nào xác minh khuôn mặt đang thấy có đúng là thí sinh đã đăng ký thi hay
không. Hệ quả: nếu 1 người khác thay thế thí sinh giữa chừng (thi hộ) mà
vẫn giữ đúng "1 khuôn mặt trong khung hình", bản tham khảo hoàn toàn không
phát hiện được. Đây là khoảng trống kỹ thuật mà `IdentitySignal` lấp vào —
xem `docs/DE_CUONG_CHI_TIET.md` mục 5.2 cho cơ sở lý thuyết (FaceNet,
Schroff et al. 2015; so sánh với ArcFace).

## 2. Kiến trúc: enrollment + re-verification định kỳ

```
Bắt đầu phiên thi
    │
    ▼
ENROLLMENT (1 lần, tương tác với người dùng)
  - Chụp 3-5 frame đầu, yêu cầu thí sinh nhìn thẳng camera
  - Trích embedding 512 chiều từng frame (facenet-pytorch, InceptionResnetV1
    pretrained vggface2)
  - Lấy TRUNG BÌNH các embedding hợp lệ -> embedding tham chiếu
  - Nếu KHÔNG frame nào tìm thấy khuôn mặt -> yêu cầu thử lại
    │
    ▼
GIÁM SÁT (mỗi frame gọi process(), nhưng chỉ THỰC SỰ tính embedding mỗi
`reverify_interval_sec` giây — mặc định 30s)
  - Trích embedding khuôn mặt hiện tại (MTCNN của facenet-pytorch tự chọn
    khuôn mặt LỚN NHẤT nếu có nhiều khuôn mặt — select_largest=True)
  - Tính cosine similarity với embedding tham chiếu
  - So với 2 ngưỡng (mục 4) -> NORMAL / cảnh báo nhẹ / IDENTITY_MISMATCH
```

**Vì sao lấy trung bình nhiều frame lúc enrollment**: 1 frame đơn lẻ có thể
bị nhiễu (chớp mắt, ánh sáng thoáng qua, góc mặt hơi lệch lúc bấm bắt đầu).
Trung bình embedding của 3-5 frame cho ra 1 điểm đại diện ổn định hơn trong
không gian embedding — kỹ thuật phổ biến khi enrollment 1 người bằng nhiều
ảnh (tương tự "gallery template" trong các hệ face recognition thương mại).

**Vì sao re-verification KHÔNG chạy mỗi frame**: trích embedding (chạy lại
MTCNN + ResNet) tốn tài nguyên hơn hẳn các signal khác (EAR, mouth ratio chỉ
là phép tính hình học đơn giản trên landmark có sẵn) — chạy mỗi 30s vẫn đủ
để phát hiện thi hộ (hành vi này không cần phát hiện tức thời trong vài
trăm ms như "dùng điện thoại", vì người thi hộ không thể "đổi lại" ngay lập
tức) mà không làm giảm FPS tổng thể của pipeline.

## 3. Chọn khuôn mặt khi có nhiều người trong khung hình

`facenet_pytorch.MTCNN` (dùng riêng cho `FaceEmbedder`, tách biệt với
`MTCNNFaceDetector` ở Perception Layer) có tham số `select_largest=True`
(mặc định của thư viện — đã verify qua `inspect.signature()` trong venv,
không đoán): khi phát hiện nhiều khuôn mặt, tự động chọn khuôn mặt có bbox
**lớn nhất** — trong bối cảnh 1 webcam đặt trước 1 thí sinh, khuôn mặt lớn
nhất gần như chắc chắn là khuôn mặt gần camera nhất, tức là thí sinh chính.
Đây chính là cách xử lý edge case "nhiều khuôn mặt lúc verify" theo đúng
yêu cầu.

## 4. Ngưỡng cosine similarity — CÓ BIÊN ĐỘ, không phải 1 ngưỡng nhị phân

```python
cosine_threshold_warn = 0.60   # >= mức này: khớp bình thường
cosine_threshold_alert = 0.45  # < mức này: tính là 1 lần "fail"
consecutive_failures_required = 2  # cần >=2 lần fail LIÊN TIẾP mới kết luận
```

**Cơ sở chọn giá trị khởi tạo**: theo khảo sát ở `docs/DE_CUONG_CHI_TIET.md`
mục 5.2.2, ngưỡng cosine similarity "cùng 1 người" cho embedding
facenet-pytorch không có 1 hằng số phổ quát — phụ thuộc mô hình/tập huấn
luyện, cộng đồng `facenet-pytorch` thường dùng khoảng 0.5–0.7. Đồ án không
có bộ benchmark lớn (kiểu LFW) để tính Equal Error Rate chính xác như cách
làm chuẩn học thuật, nên chọn 2 mức khởi tạo trong khoảng đó (0.60 khớp,
0.45 fail) — đây là điểm khởi tạo hợp lý theo kinh nghiệm cộng đồng, **chưa
có cơ sở thực nghiệm riêng của đồ án**, sẽ tinh chỉnh ở Tuần 14 bằng bộ test
có kịch bản "đổi người" (`KE_HOACH_DO_AN.md` mục 3.3).

**Vì sao có VÙNG ĐỆM giữa 2 ngưỡng thay vì 1 ngưỡng duy nhất**: đúng yêu cầu
edge case "ánh sáng thay đổi, tránh false positive quá nhạy" — ánh sáng/góc
nghiêng thay đổi tự nhiên trong lúc thi (thí sinh cử động, đèn phòng thay
đổi) làm giảm cosine similarity dù vẫn là cùng 1 người. Nếu chỉ có 1 ngưỡng
duy nhất, một lần giảm nhẹ do ánh sáng có thể vô tình vượt qua và bị kết
luận nhầm là đổi người. Vùng đệm (0.45–0.60) được gắn cờ `warning=True`
trong `metadata` nhưng KHÔNG kết luận `IDENTITY_MISMATCH` — chỉ là tín hiệu
"độ giống có giảm", dữ liệu này có thể hữu ích cho Risk Fusion Engine (Tuần
9) sau này kết hợp với tín hiệu khác, dù bản thân nó chưa đủ để cảnh báo.

**Vì sao cần 2 lần fail LIÊN TIẾP, không kết luận ngay từ 1 lần**: tương tự
lý do trên nhưng ở tầng thời gian — 1 lần đọc thấp bất thường (mờ, chuyển
động đúng lúc chụp, ánh sáng chớp) không đủ tin cậy để buộc tội "thi hộ".
Yêu cầu 2 chu kỳ verify liên tiếp (mặc định cách nhau 30s, tức ~60s dữ liệu
thấp liên tục) mới kết luận — nếu có 1 lần khớp lại ở giữa, bộ đếm reset về
0 (không cộng dồn qua các lần khớp xen kẽ).

## 5. Giới hạn của phương pháp

1. **Ngưỡng chưa hiệu chỉnh bằng thực nghiệm thật** (mục 4) — 0.60/0.45 là
   điểm khởi tạo theo kinh nghiệm cộng đồng, không phải kết quả đo trên dữ
   liệu của chính đồ án. Rủi ro đã lường trước ở `KE_HOACH_DO_AN.md` mục 5
   ("Facenet embedding nhạy với ánh sáng/góc nghiêng, có thể false reject
   người thật").
2. **Không chống giả mạo (anti-spoofing)** — hệ thống so khớp embedding
   khuôn mặt, KHÔNG phân biệt được khuôn mặt thật trước camera với 1 tấm
   ảnh/video của đúng người đó giơ lên camera (đề bài xác định rõ đây là
   ngoài phạm vi — `docs/DE_CUONG_CHI_TIET.md` mục 3.2). Nếu người thi hộ
   dùng ảnh/video của thí sinh thật để "qua mặt" enrollment/re-verification,
   hệ thống hiện tại không phát hiện được.
3. **Nhạy với thay đổi ánh sáng/góc nghiêng mạnh** — đã giảm nhẹ bằng vùng
   đệm + debounce (mục 4), nhưng thay đổi CỰC ĐOAN (VD tắt hết đèn phòng,
   quay lưng gần như hoàn toàn về camera) vẫn có thể đẩy cosine similarity
   xuống dưới ngưỡng fail dù không đổi người — đây là **false positive**
   (báo động giả) tiềm ẩn, cần đo tỉ lệ thật qua thực nghiệm thật (mục 6).
4. **Enrollment ở đầu phiên quyết định toàn bộ độ chính xác sau này** — nếu
   3-5 frame enrollment đầu có chất lượng kém (ánh sáng xấu, góc mặt lệch),
   embedding tham chiếu sẽ kém đại diện, ảnh hưởng toàn bộ các lần
   re-verification suốt phiên thi. Không có cơ chế "cập nhật lại" embedding
   tham chiếu giữa phiên (cố ý — nếu cho phép cập nhật tham chiếu bất kỳ
   lúc nào, kẻ thi hộ có thể "huấn luyện lại" hệ thống để chấp nhận mình).
5. **Chỉ xác thực khuôn mặt LỚN NHẤT trong khung hình** (mục 3) — nếu người
   thi hộ đứng gần camera hơn thí sinh thật (hoặc thay thế hoàn toàn vị trí
   ngồi), hệ thống verify đúng người "chính" hiện diện, đây là hành vi mong
   muốn; nhưng nếu 2 người cùng ở trong khung hình với kích thước khuôn mặt
   gần bằng nhau, việc chọn nhầm khuôn mặt phụ có thể xảy ra — trường hợp
   này `MultiFaceSignal` (Tuần 3) đã gắn cờ riêng (`MULTIPLE_FACES`) nên vẫn
   được phát hiện qua tín hiệu khác dù `IdentitySignal` chọn nhầm.

## 6. Test qua webcam thật (cần xác nhận, chưa thực hiện được ở phiên này)

Máy phát triển không có webcam (đã ghi nhận từ Tuần 3) — chưa tự chạy được
enrollment + re-verification bằng khuôn mặt thật. Cần bạn xác nhận qua
webcam thật:

1. **Enrollment**: nhìn thẳng camera, chạy enrollment, xác nhận thành công
   (không phải thử lại nhiều lần trong điều kiện ánh sáng bình thường).
2. **Đúng người, thử ánh sáng/góc nghiêng nhẹ** (không đổi người): quan sát
   giá trị `similarity` hiển thị dao động trong khoảng nào — đây chính là
   **tỉ lệ false positive** cần báo cáo lại (bao nhiêu % thời gian rơi vào
   vùng `warning`, có bao giờ rơi xuống dưới `cosine_threshold_alert` dù
   không đổi người hay không).
3. **Đổi người** (nhờ người khác/ảnh người khác vào khung hình giữa chừng):
   xác nhận `IDENTITY_MISMATCH` (`exceeds_threshold=True`) được gắn cờ đúng
   sau tối đa 2 chu kỳ re-verify (~60s theo mặc định).

## 7. Liên kết tài liệu

- Đề cương & khảo sát FaceNet/ArcFace: `docs/DE_CUONG_CHI_TIET.md` mục 5.2.
- Rủi ro đã lường trước: `KE_HOACH_DO_AN.md` mục 5.
- Code: `src/perception/face_embedder.py`, `src/signals/identity.py`.
- Test: `tests/test_identity_signal.py` (logic), `tests/test_identity_smoke.py` (tích hợp model thật).
