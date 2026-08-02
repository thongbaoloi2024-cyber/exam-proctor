# Kết quả Demo giữa kỳ — Tuần 8

> Theo dõi kết quả demo thực tế qua webcam (kịch bản chi tiết ở `docs/HUONG_DAN_DEMO_TUAN8.md`) và danh sách bug phát hiện/sửa. Cập nhật dần khi có thêm kết quả test.

## 1. Kết quả theo từng mục (lần test đầu tiên)

| Mục | Kịch bản | Kết quả |
|---|---|---|
| 2.1 | Baseline | OK |
| 2.2 | Head pose (quay trái/phải/lên/xuống) | OK |
| 2.3 | Mắt — nhắm mắt kéo dài | OK (nhắm mắt thật phát hiện đúng), nhưng phát hiện thêm **BUG** khi quay đầu/liếc mắt (xem mục 2) |
| 2.4 | Miệng — nói chuyện | OK |
| 2.5 | Vật thể — điện thoại | Mặt trước OK, **mặt lưng CHƯA phát hiện được** (đã biết từ trước, xem mục 2) |
| 2.6 | Nhiều người | OK |
| 2.7 | Vắng mặt | OK |
| 2.8 | Đổi người (Identity) | **Chưa test** |
| 2.9 | False positive Identity (ánh sáng/góc) | **Chưa test** |

Không ghi nhận crash/traceback trong lần test này.

## 2. Bug phát hiện & xử lý

### 2.1. [ĐÃ SỬA] EYE_STATE báo nhầm "nhắm mắt" khi quay đầu/liếc mắt sang phải hoặc xuống

- **Triệu chứng**: quay đầu/liếc mắt sang phải → bị đánh dấu vi phạm; liếc xuống → bị đánh dấu vi phạm; liếc trái → không bị (không đối xứng).
- **Nguyên nhân**: `EyeStateSignal` quyết định "nhắm mắt" dựa trên EAR **trung bình** của 2 mắt. Khi đầu/mắt quay lệch khỏi hướng chính diện camera, landmark 2D của mắt xa camera hơn bị nén lại do góc nhìn nghiêng (perspective foreshortening), khiến EAR tính ra của riêng mắt đó tụt thấp dù mắt vẫn mở — kéo trung bình xuống dưới ngưỡng dù không mắt nào thực sự nhắm.
- **Đã sửa**: đổi điều kiện sang yêu cầu **CẢ HAI** EAR (không phải trung bình) đều dưới ngưỡng mới coi là nhắm mắt — nhắm mắt thật luôn đối xứng cả 2 mắt, còn méo phối cảnh do quay đầu chỉ ảnh hưởng rõ rệt 1 bên.
- **Giới hạn còn lại**: nếu đầu quay ĐỦ NHIỀU, cả 2 mắt có thể cùng bị méo — cách sửa trên không xử lý được trường hợp này. Về bản chất cần kết hợp thêm góc từ `HEAD_POSE` (giảm độ tin cậy `EYE_STATE` khi góc quay đầu lớn) — đây là **input thiết kế cụ thể cho Risk Fusion Engine (Tuần 9)**, không cố gắng vá tiếp trong nội bộ `EyeStateSignal`.
- Code: `src/signals/eye_state.py`, test hồi quy: `tests/test_eye_state_signal.py` (`test_one_eye_distorted_by_head_turn_does_not_trigger_false_positive`, `test_both_eyes_low_still_triggers_real_closure`).

### 2.2. [CHƯA GIẢI QUYẾT — hạn chế đã biết] OBJECT_PRESENCE không phát hiện mặt lưng điện thoại

- Đã thử revert `imgsz` 320→640 (Tuần 4) — không giải quyết được, xác nhận lại ở lần test Tuần 8 này.
- Đánh giá: nhiều khả năng là hạn chế bản thân model `yolov8n` pretrained trên COCO (dữ liệu huấn luyện thiên lệch ảnh mặt trước điện thoại), không phải bug code.
- **Xếp vào nhóm "lỗi độ chính xác, tinh chỉnh Tháng 3-4"** theo đúng phân loại ưu tiên của Tuần 8 — không chặn tiến độ. Phương án khi quay lại: thử `yolov8s.pt` (model lớn hơn), hoặc fine-tune trên dataset bổ sung (đã khảo sát dataset ở cuộc trò chuyện trước, xem file `fine_tuning.md` của bạn).

## 3. Còn cần test (chưa có dữ liệu)

- **2.8 — Đổi người thi hộ**: đây là 1 trong 2 kỹ thuật mới trọng tâm của đồ án (`IdentitySignal`), **ưu tiên cao nhất cần xác nhận** trong các phần còn thiếu. Cần chờ đủ ~90s (2 chu kỳ re-verify) sau khi đổi người.
- **2.9 — False positive của Identity khi đổi ánh sáng/góc (không đổi người)**: cần đo được `similarity` dao động trong khoảng nào để biết ngưỡng 0.60/0.45 hiện tại có hợp lý không.

## 4. Tổng kết cho báo cáo Tuần 8

**Đã sửa (mức ưu tiên cao — signal phản ứng sai)**:
1. EYE_STATE false positive khi quay đầu/liếc mắt (mục 2.1) — sửa xong, có test hồi quy, đã push.

**Còn tồn đọng, để tinh chỉnh Tháng 3-4 (mức độ chính xác, không chặn tiến độ)**:
1. OBJECT_PRESENCE không phát hiện mặt lưng điện thoại (mục 2.2).
2. Giới hạn EYE_STATE khi đầu quay rất nhiều (cả 2 mắt cùng méo) — cần Risk Fusion Engine Tuần 9 hỗ trợ, không tự giải quyết được ở tầng signal.

**Chưa có đủ dữ liệu để kết luận (cần test tiếp)**:
1. IdentitySignal — đổi người và false positive ánh sáng/góc (mục 2.8, 2.9).
