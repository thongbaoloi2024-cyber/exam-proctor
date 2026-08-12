# Chương 2. Cơ sở lý thuyết

## 2.1. Tổng quan

Hệ thống giám sát thi trong đồ án là sự kết hợp của thị giác máy tính, xử lý tín hiệu theo thời gian và một nền tảng phần mềm thời gian thực. Dữ liệu đầu vào không được chuyển trực tiếp thành kết luận gian lận. Thay vào đó, ảnh webcam được biến đổi thành đặc trưng; đặc trưng được biến đổi thành các tín hiệu; tín hiệu được ổn định theo thời gian; cuối cùng nhiều trạng thái được kết hợp thành điểm rủi ro và bằng chứng để giám thị xem xét.

Chương này trình bày nền tảng cần thiết để hiểu các lựa chọn kỹ thuật đó. Các chi tiết về giải pháp do đồ án thiết kế được dành cho Chương 4, còn cách cài đặt cụ thể nằm ở Chương 5.

## 2.2. Thị giác máy tính và xử lý video

Thị giác máy tính nghiên cứu phương pháp trích xuất thông tin có ý nghĩa từ ảnh hoặc video. Một ảnh màu có thể biểu diễn bằng tensor $I \in \mathbb{R}^{H\times W\times C}$, trong đó $H$, $W$ và $C$ lần lượt là chiều cao, chiều rộng và số kênh màu. Video là chuỗi các ảnh $I_t$ được lấy tại những thời điểm khác nhau.

Trong bài toán giám sát, mỗi frame chỉ là một quan sát có nhiễu. Điều kiện ánh sáng, motion blur, tự động lấy nét và che khuất có thể làm đầu ra model thay đổi dù hành vi thực tế không đổi. Vì vậy cần phân biệt:

- **Đặc trưng tức thời:** bounding box, landmark, độ tin cậy và lớp vật thể tại thời điểm $t$.
- **Tín hiệu:** đại lượng có ý nghĩa nghiệp vụ được suy ra từ đặc trưng, ví dụ có khuôn mặt, mắt nhắm hoặc góc yaw vượt ngưỡng.
- **Sự kiện:** kết luận rằng tín hiệu bất thường đã đủ mạnh hoặc đủ lâu để cần ghi nhận.

Việc resize frame giúp giới hạn chi phí tính toán nhưng phải giữ tỉ lệ khung hình để không làm biến dạng hình học khuôn mặt. Chuyển đổi BGR–RGB cũng cần được thực hiện đúng vì OpenCV và nhiều model học sâu sử dụng thứ tự kênh khác nhau.

## 2.3. Phát hiện khuôn mặt bằng MTCNN

### 2.3.1. Bài toán phát hiện khuôn mặt

Face detection xác định số lượng và vị trí khuôn mặt trong ảnh. Đầu ra phổ biến là bounding box $b=(x_1,y_1,x_2,y_2)$, độ tin cậy $c$ và một số điểm mốc cơ bản. Khác với face recognition, bước này không xác định người trong ảnh là ai.

Các phương pháp cổ điển như Viola–Jones sử dụng Haar-like feature và cascade classifier. Các phương pháp học sâu hiện đại học trực tiếp đặc trưng từ dữ liệu, xử lý tốt hơn biến thiên về tư thế và ánh sáng nhưng có chi phí tính toán lớn hơn.

### 2.3.2. Kiến trúc MTCNN

MTCNN (Zhang và cộng sự, 2016) sử dụng chuỗi ba mạng tích chập:

1. **P-Net** tạo nhanh các vùng có khả năng chứa khuôn mặt ở nhiều tỉ lệ.
2. **R-Net** loại bỏ vùng sai và hiệu chỉnh bounding box.
3. **O-Net** tinh chỉnh lần cuối và dự đoán năm landmark cơ bản.

Ở mỗi tầng, Non-Maximum Suppression loại các bounding box trùng lặp. Cấu trúc cascade giúp giảm số vùng cần xử lý ở tầng sau. Trong đồ án, bounding box MTCNN phục vụ Face Presence và Multi-face. Một MTCNN riêng trong `facenet-pytorch` còn được dùng để crop và align khuôn mặt trước khi tạo embedding; hai vai trò này không nên nhầm lẫn.

MTCNN vẫn có thể bỏ sót khi khuôn mặt quá nhỏ, quay góc lớn, bị che hoặc ánh sáng yếu. Vì vậy, “không phát hiện” là thiếu quan sát của model và chỉ trở thành tín hiệu bất thường sau khi được kiểm tra theo thời gian.

## 2.4. Landmark khuôn mặt với MediaPipe Face Landmarker

Landmark khuôn mặt là tập các điểm đặc trưng mô tả đường viền mắt, môi, mũi, cằm và bề mặt khuôn mặt. MediaPipe Face Mesh/Face Landmarker dự đoán 468 điểm bề mặt từ ảnh camera đơn và có thể chạy gần thời gian thực (Kartynnik và cộng sự, 2019).

Tọa độ MediaPipe thường được chuẩn hóa theo kích thước ảnh. Với landmark $p_i=(x_i,y_i)$ chuẩn hóa và frame có kích thước $(W,H)$, tọa độ pixel là:

$$
p_i^{pixel}=(x_iW,\ y_iH)
$$

Quy đổi này quan trọng khi tính khoảng cách Euclidean. Nếu lấy trực tiếp $x$ đã chia cho $W$ và $y$ đã chia cho $H$ trên ảnh không vuông, hai trục có tỉ lệ khác nhau và đại lượng hình học sẽ bị méo. Đồ án sử dụng tọa độ pixel cho EAR, tỉ lệ mở miệng và PnP.

Không phải mọi tín hiệu đều cần nhiều khuôn mặt có landmark chi tiết. Face Landmarker chỉ theo dõi khuôn mặt chính để phục vụ mắt, miệng và head pose; MTCNN chịu trách nhiệm đếm nhiều khuôn mặt. Sự tách này giảm chi phí và làm rõ trách nhiệm của từng model.

## 2.5. Phát hiện trạng thái mắt bằng EAR

Eye Aspect Ratio (EAR) là tỉ lệ hình học được Soukupová và Čech (2016) đề xuất để biểu diễn độ mở mắt. Với sáu điểm $P_1,...,P_6$ quanh một mắt:

$$
EAR=\frac{\lVert P_2-P_6\rVert_2+\lVert P_3-P_5\rVert_2}
{2\lVert P_1-P_4\rVert_2}
$$

Tử số đo hai khoảng mở theo chiều dọc, mẫu số đo chiều rộng mắt. Vì là một tỉ lệ, EAR ít phụ thuộc hơn vào kích thước khuôn mặt trên ảnh. Khi mắt khép, khoảng cách dọc giảm và EAR giảm.

EAR không đo hướng nhìn. Một người quay đầu có thể làm một mắt bị nén phối cảnh và tạo EAR thấp giả. Do nhắm mắt tự nhiên thường ảnh hưởng cả hai mắt, đồ án chỉ coi trạng thái nhắm khi EAR của cả hai mắt cùng dưới ngưỡng. Head Pose Signal đảm nhận việc nhận biết quay đầu.

Ngưỡng EAR không phải hằng số cho mọi người và mọi camera. Nó cần được kết hợp với thời lượng nhắm và được hiệu chỉnh trên dữ liệu thực nghiệm. Một frame có EAR thấp không đủ để tạo cảnh báo.

## 2.6. Phát hiện hoạt động miệng

Miệng mở có thể đo bằng tỉ lệ giữa khoảng cách dọc của môi trong và khoảng cách hai khóe miệng:

$$
MOR=\frac{\lVert P_{upper}-P_{lower}\rVert_2}
{\lVert P_{left}-P_{right}\rVert_2}
$$

Trong đó $MOR$ là Mouth Open Ratio. Việc chia cho chiều rộng miệng giúp đại lượng ít phụ thuộc vào khoảng cách giữa thí sinh và camera.

Khác với ngáp, nói chuyện làm miệng mở và đóng xen kẽ. Nếu thuật toán yêu cầu miệng mở liên tục trong nhiều giây, hành vi nói có thể không bao giờ vượt ngưỡng. Vì vậy cần theo dõi tỉ lệ quan sát miệng mở trong cửa sổ thời gian:

$$
a_{mouth}(t)=\frac{N_{open}(t-W,t)}{N_{valid}(t-W,t)}
$$

Khi $a_{mouth}$ vượt ngưỡng và cửa sổ đã có đủ độ phủ, tín hiệu mới được coi là bất thường. Cách này không phụ thuộc trực tiếp vào số FPS và phản ánh đúng hơn mẫu mở–đóng lặp lại.

Tuy nhiên, chuyển động miệng không chứng minh thí sinh trao đổi nội dung. Tín hiệu này chỉ đóng vai trò phụ và cần được giám thị đối chiếu với tín hiệu khác.

## 2.7. Phát hiện vật thể bằng YOLO

YOLO là họ mô hình object detection một giai đoạn, dự đoán bounding box và lớp vật thể trong một lần forward pass. So với các phương pháp hai giai đoạn, YOLO thường phù hợp hơn cho xử lý thời gian thực. Đồ án sử dụng YOLOv8n pretrained trên COCO thông qua thư viện Ultralytics.

Đầu ra của một object detector gồm lớp $k$, bounding box $b$ và confidence $c$. Chỉ các dự đoán có $c$ lớn hơn ngưỡng và thuộc lớp quan tâm mới được giữ lại. Model hiện tại lọc hai lớp COCO là `cell phone` và `book`; laptop không nằm trong tập lớp được code chấp nhận.

YOLO có chi phí lớn hơn phát hiện landmark. Một chiến lược thường dùng là chạy model theo chu kỳ thay vì mọi frame, sau đó giữ kết quả gần nhất trong khoảng giữa hai lần suy luận. Để một false detection thoáng qua không trở thành vi phạm, tín hiệu vật thể còn cần debounce theo thời lượng.

Model pretrained chịu ảnh hưởng của miền dữ liệu huấn luyện. Điện thoại nhỏ, bị che, ở rìa ảnh hoặc quay mặt lưng có thể bị bỏ sót. Fine-tuning có thể cải thiện một miền cụ thể nhưng đòi hỏi dataset, cách chia train/validation/test và artifact model được quản lý rõ ràng.

## 2.8. Ước lượng góc quay đầu bằng Perspective-n-Point

### 2.8.1. Mô hình hình học

Head pose thường được biểu diễn bởi ba góc Euler:

- **Yaw:** quay trái–phải quanh trục dọc.
- **Pitch:** cúi–ngẩng quanh trục ngang.
- **Roll:** nghiêng đầu quanh trục hướng nhìn.

Bài toán Perspective-n-Point tìm tư thế camera hoặc vật thể từ các cặp điểm 3D–2D. Với điểm khuôn mặt 3D $P_i=(X_i,Y_i,Z_i)$, điểm ảnh $p_i=(u_i,v_i)$, ma trận nội tại camera $K$, ma trận quay $R$ và vector tịnh tiến $t$:

$$
s\begin{bmatrix}u_i\\v_i\\1\end{bmatrix}
=K\left[R\mid t\right]
\begin{bmatrix}X_i\\Y_i\\Z_i\\1\end{bmatrix}
$$

`solvePnP` ước lượng $R$ và $t$ sao cho sai số chiếu của các điểm 3D lên ảnh 2D là nhỏ. Từ rotation vector có thể tạo rotation matrix bằng Rodrigues, sau đó phân rã thành yaw, pitch và roll.

### 2.8.2. Mô hình camera xấp xỉ

Khi không hiệu chuẩn camera riêng cho từng thiết bị, có thể xấp xỉ:

$$
K=\begin{bmatrix}
f&0&W/2\\
0&f&H/2\\
0&0&1
\end{bmatrix}
$$

với $f$ xấp xỉ theo chiều rộng ảnh và distortion coefficient đặt bằng 0. Đây là giả định thực dụng, không cho độ chính xác như camera calibration nhưng cho góc có ý nghĩa hình học hơn độ lệch pixel thuần túy.

Độ chính xác của PnP phụ thuộc vào landmark 2D, mô hình mặt 3D, camera intrinsic và quy ước trục. Góc lớn hoặc che khuất làm landmark sai, kéo theo sai số head pose. Do đó cần ngưỡng thời lượng và không nên coi góc tức thời là kết luận.

## 2.9. Xác thực danh tính bằng face embedding

### 2.9.1. Biểu diễn embedding

Face verification trả lời câu hỏi hai ảnh có thuộc cùng một người hay không. FaceNet học ánh xạ $f(x)\in\mathbb{R}^d$ từ ảnh mặt sang vector embedding bằng triplet loss (Schroff, Kalenichenko và Philbin, 2015). Với anchor $a$, positive $p$ và negative $n$:

$$
L=\max\left(0,\lVert f(a)-f(p)\rVert_2^2
-\lVert f(a)-f(n)\rVert_2^2+\alpha\right)
$$

Mục tiêu là đưa embedding của cùng người lại gần và đẩy embedding của người khác ra xa ít nhất một margin $\alpha$.

Đồ án sử dụng InceptionResnetV1 pretrained trên VGGFace2 qua `facenet-pytorch`, tạo vector 512 chiều. Trong enrollment, embedding tham chiếu là trung bình của nhiều frame hợp lệ để giảm ảnh hưởng của một quan sát riêng lẻ.

### 2.9.2. Cosine similarity và quyết định có biên

Độ tương tự cosine giữa hai vector $x$ và $y$ là:

$$
sim(x,y)=\frac{x\cdot y}{\lVert x\rVert_2\lVert y\rVert_2}
$$

Giá trị cao cho biết hai hướng vector gần nhau. Ngưỡng xác thực phụ thuộc model và miền dữ liệu, không có một giá trị phổ quát. Một thiết kế an toàn nên có vùng cảnh báo và vùng mismatch thay vì một ngưỡng duy nhất. Đồ án còn yêu cầu nhiều lần mismatch liên tiếp và chỉ re-verify theo chu kỳ để tránh chi phí embedding ở mọi frame.

Nếu không tìm thấy khuôn mặt tại thời điểm re-verification, hệ thống không được đồng nhất tình huống này với “không đúng người”. Face Presence chịu trách nhiệm cho sự vắng mặt; Identity chỉ kết luận khi có embedding hợp lệ để so sánh.

### 2.9.3. Liveness cơ bản

Face verification có thể bị đánh lừa bởi ảnh tĩnh nếu không kiểm tra liveness. Thử thách chớp mắt `mở → nhắm → mở` xác nhận có chuyển động sinh học đơn giản trước enrollment. Giải pháp này chặn một số trường hợp sử dụng ảnh in hoặc ảnh trên màn hình, nhưng không chống được video replay, mặt nạ hoặc deepfake tinh vi. Vì vậy nó được gọi là liveness cơ bản, không phải anti-spoofing hoàn chỉnh.

## 2.10. Xử lý tín hiệu theo thời gian

### 2.10.1. Debounce dựa trên thời lượng

Debounce chỉ chấp nhận một điều kiện khi nó duy trì đủ lâu. Nếu $q(t)\in\{0,1\}$ biểu diễn điều kiện thô và $D$ là thời lượng tối thiểu, tín hiệu chỉ vượt ngưỡng khi $q(t)=1$ liên tục trong khoảng $D$. Cách đo bằng giây ổn định hơn đếm số frame vì FPS có thể thay đổi theo thiết bị và tải xử lý.

### 2.10.2. Cửa sổ thời gian trượt

Với cửa sổ độ dài $W$, tỉ lệ bất thường của tín hiệu $i$ tại thời điểm $t$ là:

$$
r_i(t)=\frac{\sum_{\tau\in(t-W,t]}\mathbb{1}[q_i(\tau)=1]}
{\sum_{\tau\in(t-W,t]}\mathbb{1}[q_i(\tau)\text{ hợp lệ}]}
$$

Cửa sổ trượt giữ lại lịch sử gần nhất, loại bỏ ảnh hưởng lâu dài của sự kiện cũ và hỗ trợ các mẫu không liên tục như hoạt động miệng.

### 2.10.3. Máy trạng thái hữu hạn

Finite State Machine biểu diễn hệ thống bằng tập trạng thái và điều kiện chuyển. Ba trạng thái `NORMAL`, `SUSPICIOUS`, `ALERT` cho phép phân biệt quan sát ban đầu với bằng chứng kéo dài. Máy trạng thái của mỗi tín hiệu độc lập để nhiều hành vi có thể tồn tại đồng thời.

## 2.11. Kết hợp đa tín hiệu và hysteresis

### 2.11.1. Weighted scoring

Sau khi ổn định từng tín hiệu, trạng thái có thể ánh xạ thành giá trị $s_i$ và kết hợp bằng tổng có trọng số:

$$
R(t)=\sum_{i=1}^{n}w_is_i(t)
$$

Trọng số $w_i$ biểu diễn mức đóng góp tương đối. Weighted scoring có ưu điểm dễ giải thích, dễ cấu hình và không đòi hỏi tập huấn luyện lớn. Hạn chế là quan hệ tuyến tính không tự học được các tương tác phức tạp giữa tín hiệu.

### 2.11.2. Hysteresis

Nếu chỉ dùng một ngưỡng $T$, nhiễu quanh $T$ làm trạng thái bật/tắt liên tục. Hysteresis sử dụng hai ngưỡng:

$$
state(t)=
\begin{cases}
ALERT,&state(t-1)=NORMAL\land R(t)\ge T_{enter}\\
NORMAL,&state(t-1)=ALERT\land R(t)\le T_{exit}\\
state(t-1),&\text{các trường hợp còn lại}
\end{cases}
$$

với $T_{exit}<T_{enter}$. Khoảng $(T_{exit},T_{enter})$ là vùng đệm giữ nguyên trạng thái cũ. Hysteresis có thể được áp dụng ở cả cấp tín hiệu và cấp phiên.

### 2.11.3. Cạnh chuyển trạng thái và sự kiện

Một cảnh báo kéo dài không nên tạo một event ở mọi frame. Sự kiện chỉ cần sinh ở cạnh chuyển từ `NORMAL` sang `ALERT`; thời gian kéo dài có thể suy ra từ transition trở về bình thường. Cách này giảm kích thước log và tránh hiển thị nhiều bản ghi cho cùng một hành vi.

## 2.12. Giao tiếp thời gian thực và hợp đồng dữ liệu

REST phù hợp với thao tác request–response như đăng nhập, tạo kỳ thi và lấy danh sách phiên. WebSocket theo RFC 6455 duy trì kênh song công để client gửi heartbeat/telemetry và backend đẩy cập nhật đến dashboard mà không cần polling liên tục.

Kênh thời gian thực không loại bỏ nhu cầu xác thực và kiểm tra dữ liệu. Một message từ client cần:

- Có type và schema xác định.
- Giới hạn kích thước, tần suất và số phần tử.
- Phân biệt timestamp client với thời gian server nhận.
- Gắn với đúng loại token và đúng phiên.
- Có cơ chế heartbeat, idle timeout và trạng thái mất kết nối.

Data contract giúp các thành phần thống nhất ý nghĩa trường dữ liệu. `SignalResult`, `ViolationEvent` và browser event phải dùng tên enum cố định, số hữu hạn và metadata có giới hạn. Backend có thể tính lại hoặc đối chiếu giá trị dẫn xuất thay vì tin trực tiếp điểm do client gửi.

## 2.13. Phân quyền và cô lập nhiều tổ chức

Role-Based Access Control gán quyền cho vai trò thay vì từng người dùng riêng lẻ. Trong nền tảng nhiều tổ chức, chỉ kiểm tra role là chưa đủ; quyết định còn phụ thuộc tenant và tài nguyên cụ thể. Có thể mô hình hóa quyền hiệu lực như:

$$
Allowed(u,a,r)=Authenticated(u)\land Active(u)\land
TenantMatch(u,r)\land Capability(u,a)\land ResourceScope(u,r)
$$

Trong đó $u$ là người dùng, $a$ là hành động và $r$ là tài nguyên. Assignment trên kỳ thi là một dạng resource scope: người dùng có thể là manager ở kỳ thi A nhưng chỉ là proctor ở kỳ thi B.

Nguyên tắc đặc quyền tối thiểu yêu cầu chỉ cấp quyền cần thiết. Quản trị nền tảng không nên mặc nhiên xem evidence của mọi tổ chức. Quyền ngoại lệ cần có lý do, phạm vi, phê duyệt, thời hạn và audit log. Khi tài nguyên nằm ngoài phạm vi, trả `404` có thể hạn chế tiết lộ sự tồn tại tốt hơn trả chi tiết quyền bị thiếu.

## 2.14. Lưu trữ sự kiện và khả năng truy vết

Cơ sở dữ liệu quan hệ phù hợp với entity có quan hệ và cần truy vấn như tổ chức, người dùng, kỳ thi, assignment và trạng thái phiên mới nhất. JSON Lines phù hợp với chuỗi sự kiện append-only vì mỗi dòng là một JSON độc lập, có thể ghi tuần tự và đọc từng phần.

Mô hình lai cho phép:

- SQL phục vụ dashboard và kiểm soát quyền.
- JSONL lưu timeline chi tiết của tín hiệu, transition và sự kiện.
- Snapshot cung cấp bằng chứng hình ảnh ở thời điểm cần thiết.
- Báo cáo được tái tạo từ dữ liệu gốc thay vì chỉ lưu một kết luận tổng hợp.

Audit log khác với evidence. Evidence mô tả điều xảy ra trong phiên thi; audit log mô tả ai đã thao tác lên hệ thống hoặc truy cập dữ liệu. Hai loại cần tách biệt để hỗ trợ truy vết và trách nhiệm giải trình.

## 2.15. Các chỉ số đánh giá

Với bài toán nhị phân, confusion matrix gồm:

- **True Positive (TP):** vi phạm thật được phát hiện.
- **False Positive (FP):** hệ thống cảnh báo nhưng ground truth là bình thường.
- **False Negative (FN):** vi phạm thật không được phát hiện.
- **True Negative (TN):** trạng thái bình thường được nhận biết đúng.

Các chỉ số cơ bản:

$$
Precision=\frac{TP}{TP+FP}
$$

$$
Recall=\frac{TP}{TP+FN}
$$

$$
F1=2\cdot\frac{Precision\cdot Recall}{Precision+Recall}
$$

$$
Specificity=\frac{TN}{TN+FP},\qquad
FPR=\frac{FP}{TN+FP}
$$

Accuracy có thể gây hiểu nhầm khi dữ liệu mất cân bằng, vì hệ thống luôn dự đoán lớp phổ biến vẫn có accuracy cao. Precision, Recall, F1 và confusion matrix cần được báo cáo cùng nhau.

Đơn vị đánh giá cũng phải được công bố. Đánh giá theo frame coi mỗi frame là một mẫu; đánh giá theo event so khớp sự kiện với khoảng ground truth. Hai cách trả lời câu hỏi khác nhau và cho kết quả khác nhau. Độ trễ phát hiện của một true positive được tính bằng:

$$
Latency=t_{detected}-t_{ground\ truth\ start}
$$

Đối với ROC-AUC hoặc PR-AUC, cần có score liên tục ở nhiều ngưỡng hoặc một quá trình quét ngưỡng. Một confusion matrix tại một ngưỡng duy nhất không đủ để suy ra hai diện tích này.

## 2.16. Kết chương

Chương 2 đã trình bày nền tảng của các thành phần chính: phát hiện khuôn mặt bằng MTCNN, landmark MediaPipe, EAR, tỉ lệ mở miệng, YOLO, PnP, face embedding, liveness cơ bản, xử lý theo thời gian, weighted fusion và hysteresis. Chương cũng bổ sung các khái niệm về WebSocket, data contract, RBAC, cô lập tenant, lưu trữ sự kiện và chỉ số đánh giá để phản ánh đầy đủ hệ thống đã triển khai.

Chương 3 tiếp theo khảo sát các giải pháp liên quan và chuyển các vấn đề đã nhận diện thành yêu cầu chức năng, phi chức năng và tiêu chí nghiệm thu cụ thể.
