# Ghi chú kỹ thuật: Head Pose Estimation bằng cv2.solvePnP

> Tuần 5. Giải thích công thức, cách chọn landmark, camera matrix xấp xỉ và
> giới hạn của phương pháp — dùng làm nguồn cho chương "Cài đặt hệ thống"
> của luận văn. Code tương ứng: `src/perception/head_pose_math.py` (toán
> học lõi) và `src/signals/head_pose.py` (`HeadPoseSignal` — ngưỡng cảnh
> báo + debounce thời gian). Kiểm chứng bằng test tổng hợp:
> `tests/test_head_pose_math.py`.

## 1. Vì sao cần Head Pose Estimation bằng hình học 3D

Bản tham khảo (`exam-cheating-detection`) xác định "nhìn ra ngoài màn hình"
bằng cách so lệch **pixel tuyệt đối** giữa tâm mắt và mũi trên ảnh 2D
(`eye_tracking.py`, ngưỡng cứng `gaze_sensitivity: 15` pixel — xem
`docs/SO_SANH_KY_THUAT_TUAN4.md` mục 1). Cách này có 2 hạn chế cơ bản:

1. **Không có chiều sâu (depth)**: chỉ so lệch 2D, không biết đầu có
   nghiêng/xoay theo trục nào — quay đầu sang trái 20° và cúi đầu xuống 20°
   có thể cho ra cùng 1 giá trị lệch pixel, dù là 2 hành vi khác hẳn nhau.
2. **Không chuẩn hoá theo khoảng cách/độ phân giải camera**: ngưỡng pixel cố
   định (`15px`) chỉ đúng với đúng 1 độ phân giải/khoảng cách ngồi đã
   hardcode sẵn trong `config.yaml` (`video.resolution: [1280,720]`) — đổi
   webcam hoặc ngồi gần/xa hơn là sai lệch ngay.

`cv2.solvePnP` giải quyết cả 2 vấn đề: cho ra **góc quay thật** (yaw/pitch/
roll, đơn vị độ) dựa trên hình học chiếu phối cảnh (perspective projection)
giữa 1 mô hình khuôn mặt 3D chuẩn và các điểm 2D quan sát được — không phụ
thuộc độ phân giải/khoảng cách camera (miễn camera matrix ước lượng hợp lý,
xem mục 4).

## 2. Chọn 6 điểm landmark

| Điểm | Chỉ số MediaPipe FaceMesh | Cách xác minh |
|---|---|---|
| Đỉnh mũi | `1` | Đối chiếu `canonical_face_model.obj` (model 3D trung tính công khai của Google, không bundle sẵn trong gói pip): điểm 1 nằm ở vùng z lớn nhất (lồi nhất về phía camera) và x≈0 (trục giữa mặt) — khớp quy ước cộng đồng dùng phổ biến trong tutorial solvePnP + MediaPipe |
| Cằm | `152` | Xác minh trực tiếp qua `FaceLandmarksConnections.FACE_LANDMARKS_FACE_OVAL` mà package `mediapipe` cài đặt thực sự expose: điểm 152 nằm giữa `Connection(377,152)` và `Connection(152,148)` — đúng vị trí đáy contour khuôn mặt |
| Khoé mắt ngoài trái/phải | `263` / `33` | Xác minh qua `FACE_LANDMARKS_LEFT_EYE`/`RIGHT_EYE` — dùng lại đúng điểm đã verify cho `EyeStateSignal` (Tuần 4) |
| Khoé miệng trái/phải | `291` / `61` | Xác minh qua `FACE_LANDMARKS_LIPS` — dùng lại đúng điểm đã verify cho `MouthStateSignal` (Tuần 4) |

4/6 điểm (cằm, mắt, miệng) verify được **trực tiếp qua topology mà package
mediapipe cài đặt expose** — không suy đoán. Riêng đỉnh mũi, bản mediapipe
cài đặt (0.10.14) không có tập `FACE_LANDMARKS_NOSE` để verify theo cách
tương tự; đã đối chiếu bổ sung qua file `canonical_face_model.obj` công khai
(dùng phân tích tự động, không đọc thủ công 468 dòng) để tăng độ tin cậy.

## 3. Mô hình khuôn mặt 3D chuẩn (xấp xỉ, không đo thật)

```python
MODEL_POINTS_3D = [
    (0.0, 0.0, 0.0),           # Đỉnh mũi
    (0.0, -330.0, -65.0),      # Cằm
    (-225.0, 170.0, -135.0),   # Khoé mắt ngoài TRÁI
    (225.0, 170.0, -135.0),    # Khoé mắt ngoài PHẢI
    (-150.0, -150.0, -125.0),  # Khoé miệng TRÁI
    (150.0, -150.0, -125.0),   # Khoé miệng PHẢI
]
```

Bộ số liệu này lấy từ **Satya Mallick, "Head Pose Estimation using OpenCV
and Dlib"** ([learnopencv.com](https://learnopencv.com/head-pose-estimation-using-opencv-and-dlib/))
— một mô hình khuôn mặt trung bình mang tính minh hoạ hình học (đơn vị
tương đối, không phải mm đo thật của bất kỳ ai), được tái sử dụng rất rộng
rãi trong cộng đồng cho cả landmark dlib (68 điểm) lẫn MediaPipe (468 điểm)
vì bản thân mô hình 3D không gắn với bộ landmark cụ thể nào — chỉ cần ánh xạ
đúng 6 điểm tương ứng. Đây là lý do đề bài cho phép "toạ độ 3D xấp xỉ theo
tài liệu tham khảo chuẩn, không cần đo thật".

**Nguyên tắc ghép cặp**: 6 điểm 2D (mục 2) ghép với 6 điểm 3D theo **tên giải
phẫu** (trái/phải theo góc nhìn của chính thí sinh, không phải theo hướng
camera nhìn vào) để đảm bảo nhất quán — xem mục 6 về rủi ro liên quan.

## 4. Camera matrix xấp xỉ (không calibrate thật)

```python
focal_length = frame_width          # xấp xỉ = chiều rộng ảnh
center = (frame_width/2, frame_height/2)
camera_matrix = [[focal_length, 0, center_x],
                 [0, focal_length, center_y],
                 [0, 0, 1]]
dist_coeffs = [0, 0, 0, 0]          # giả định không méo ống kính
```

Đây là quy ước xấp xỉ phổ biến khi không có bộ camera intrinsic thật (không
làm chessboard calibration) — chấp nhận được cho mục tiêu **định tính/bán
định lượng** (phát hiện xu hướng quay đầu rõ rệt), không phù hợp cho đo đạc
góc chính xác tuyệt đối. Rủi ro này đã được ghi nhận trước trong
`KE_HOACH_DO_AN.md` mục 5 ("solvePnP cần camera intrinsic matrix chính xác
để chuẩn, không có calibration thật → dùng xấp xỉ, chấp nhận sai số").

## 5. Từ rotation vector ra góc yaw/pitch/roll

```
cv2.solvePnP(...)              -> rotation_vector (Rodrigues, 3x1)
cv2.Rodrigues(rotation_vector) -> rotation_matrix (3x3)
phân rã rotation_matrix        -> (pitch, yaw, roll), độ
```

Công thức phân rã (quy ước `R = Rz(roll) · Ry(yaw) · Rx(pitch)`):

```
sy = sqrt(R[0,0]² + R[1,0]²)
pitch = atan2(R[2,1], R[2,2])
yaw   = atan2(-R[2,0], sy)
roll  = atan2(R[1,0], R[0,0])
```

(công thức kinh điển, xem Slabaugh, *"Computing Euler Angles from a
Rotation Matrix"*). **Đã tự kiểm chứng bằng thực nghiệm số** trước khi đưa
vào code: dựng ma trận xoay ứng với góc yaw/pitch/roll biết trước (VD yaw
đơn thuần 30°), decode lại bằng công thức trên, xác nhận khớp — thay vì chỉ
tin vào việc nhớ đúng công thức. Đi xa hơn, `tests/test_head_pose_math.py`
kiểm chứng **toàn bộ pipeline end-to-end**: chiếu 6 điểm `MODEL_POINTS_3D`
qua 1 phép quay biết trước + camera matrix ước lượng ra toạ độ 2D, đưa
ngược 6 điểm đó vào `solve_head_pose()`, xác nhận góc khôi phục được khớp
góc đã biết trước (sai số < 0.5° trên dữ liệu tổng hợp không nhiễu) — đây là
cách kiểm chứng chặt nhất có thể làm mà không cần webcam/khuôn mặt thật.

## 6. Giới hạn của phương pháp

1. **Không calibrate camera thật** (mục 4) — góc tuyệt đối có sai số, chỉ
   dùng được cho mục tiêu định tính/bán định lượng ("có nhìn lệch rõ rệt hay
   không"), không phải đo góc chính xác cấp độ nghiên cứu.
2. **Mô hình khuôn mặt 3D là trung bình chung**, không cá nhân hoá theo từng
   thí sinh — người có tỉ lệ khuôn mặt khác biệt lớn so với mức trung bình
   (VD mặt rất dài/ngắn) có thể có sai số góc lớn hơn.
3. **Sai số landmark truyền trực tiếp vào sai số góc** — MediaPipe FaceMesh
   đôi khi dao động nhẹ giữa các frame (jitter), nhất là điều kiện ánh sáng
   yếu, có thể khiến góc yaw/pitch dao động dù đầu đứng yên; đây là lý do
   `HeadPoseSignal` dùng debounce thời gian (`min_away_duration_sec`), không
   quyết định theo 1 frame đơn lẻ.
4. **Rủi ro đảo dấu yaw/pitch chưa xác nhận được bằng thực nghiệm thật**
   (quan trọng nhất, xem chi tiết bên dưới).

### 6.1. Rủi ro đảo dấu — cần xác nhận bằng webcam thật

Việc ghép 6 điểm 2D với 6 điểm 3D theo tên giải phẫu (mục 3) đã được suy
luận nhất quán, và **toàn bộ toán học đã kiểm chứng đúng bằng dữ liệu tổng
hợp** (mục 5) — nghĩa là nếu đưa vào đúng toạ độ landmark, góc khôi phục
được chắc chắn đúng về mặt số học. Tuy nhiên, việc góc "yaw dương" có tương
ứng đúng với "thí sinh quay đầu sang phải của chính họ" (hay ngược lại) trên
khung hình thật phụ thuộc thêm vào 1 yếu tố **không thể xác nhận nếu không
có webcam thật**: liệu frame trả về từ `cv2.VideoCapture` trên máy chạy có
bị lật gương (mirror) hay không — điều này khác nhau tuỳ driver/thiết bị.

**Cách xác nhận khi test qua webcam thật** (không có trong khả năng của
phiên làm việc này do máy phát triển không có webcam):
- Quay đầu sang phải của chính bạn, quan sát giá trị `yaw` hiển thị trên
  overlay debug (`main.py`) — ghi lại dấu (dương/âm).
- Quan sát trục Z (màu xanh dương, vẽ từ mũi) trên overlay — trục này phải
  hướng theo chiều mũi đang chỉ tới khi đầu nghiêng/quay.
- Nếu dấu bị ngược trực giác (VD quay phải nhưng `yaw` hiển thị âm trong khi
  bạn kỳ vọng dương, hoặc trục vẽ sai hướng rõ rệt): chỉ cần đảo dấu tại 1
  chỗ duy nhất — dòng tính `yaw` trong `_rotation_matrix_to_euler_deg()`
  (`src/perception/head_pose_math.py`), thêm dấu `-` phía trước. Không cần
  sửa gì khác vì toàn bộ phần còn lại (ngưỡng, debounce, trực quan hoá) chỉ
  phụ thuộc vào giá trị `yaw`/`pitch` cuối cùng, không giả định dấu cụ thể.

## 7. Ngưỡng "nhìn ra ngoài màn hình"

```python
is_away = abs(yaw) >= 20.0 or abs(pitch) >= 20.0   # độ
```

20° cho cả yaw và pitch là điểm khởi tạo hợp lý theo trực giác hình học (một
màn hình máy tính đặt trước mặt thường nằm trong góc nhìn ±20-25° khi ngồi ở
khoảng cách bình thường), **chưa có cơ sở thực nghiệm** — sẽ tinh chỉnh ở
Tuần 14 bằng bộ test có gán nhãn thật (`KE_HOACH_DO_AN.md` mục 3.3), tương
tự cách xử lý ngưỡng ở các signal khác (`docs/SO_SANH_KY_THUAT_TUAN4.md`).
Kèm debounce thời gian (`min_away_duration_sec=1.0s`, cùng triết lý các
signal Tuần 3-4) để 1 lần liếc nhanh không bị tính là vi phạm.

## 8. Liên kết tài liệu

- Đề cương & lý do chọn solvePnP thay vì deep learning: `docs/DE_CUONG_CHI_TIET.md` mục 5.1.
- So sánh với cách làm bản tham khảo: `docs/SO_SANH_KY_THUAT_TUAN4.md`.
- Rủi ro đã lường trước: `KE_HOACH_DO_AN.md` mục 5.
- Code: `src/perception/head_pose_math.py`, `src/signals/head_pose.py`.
- Test kiểm chứng: `tests/test_head_pose_math.py`, `tests/test_head_pose_signal.py`.
