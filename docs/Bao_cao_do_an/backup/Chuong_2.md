# Chương 2. Cơ sở lý thuyết

## 2.1. Tổng quan

Hệ thống giám sát thi trong đồ án là sự kết hợp của thị giác máy tính, xử lý tín hiệu theo thời gian và một nền tảng phần mềm thời gian thực. Dữ liệu đầu vào không được chuyển trực tiếp thành kết luận gian lận. Thay vào đó, ảnh webcam được biến đổi thành đặc trưng; đặc trưng được biến đổi thành các tín hiệu; tín hiệu được ổn định theo thời gian; cuối cùng nhiều trạng thái được kết hợp thành điểm rủi ro và bằng chứng để giám thị xem xét.

Chương này trình bày nền tảng cần thiết để hiểu các lựa chọn kỹ thuật đó. Các chi tiết về giải pháp do đồ án thiết kế được dành cho Chương 4, còn cách cài đặt cụ thể nằm ở Chương 5.

Trong chương này, thuật ngữ tiếng Việt được ưu tiên trong phần diễn giải; thuật ngữ hoặc chữ viết tắt tiếng Anh được giữ ở lần xuất hiện đầu để thuận tiện đối chiếu tài liệu kỹ thuật. Tên lớp, trường dữ liệu và định danh trong mã nguồn được giữ nguyên trong dấu mã nguồn.

## 2.2. Thị giác máy tính và xử lý video

Thị giác máy tính nghiên cứu phương pháp trích xuất thông tin có ý nghĩa từ ảnh hoặc video. Một ảnh màu có thể biểu diễn bằng tensor $I \in \mathbb{R}^{H\times W\times C}$, trong đó $H$, $W$ và $C$ lần lượt là chiều cao, chiều rộng và số kênh màu. Video là chuỗi các ảnh $I_t$ được lấy tại những thời điểm khác nhau.

Trong bài toán giám sát, mỗi khung hình chỉ là một quan sát có nhiễu. Điều kiện ánh sáng, nhòe chuyển động, tự động lấy nét và che khuất có thể làm đầu ra mô hình thay đổi dù hành vi thực tế không đổi. Vì vậy, cần phân biệt:

- **Đặc trưng tức thời:** khung bao, điểm mốc, độ tin cậy và lớp vật thể tại thời điểm $t$.
- **Tín hiệu:** đại lượng có ý nghĩa nghiệp vụ được suy ra từ đặc trưng, ví dụ có khuôn mặt, mắt nhắm hoặc góc yaw vượt ngưỡng.
- **Sự kiện:** bản ghi cho biết tín hiệu bất thường đã đủ mạnh hoặc kéo dài đủ lâu để cần giám thị chú ý.

Việc thay đổi kích thước khung hình giúp giới hạn chi phí tính toán nhưng phải giữ tỉ lệ ảnh để không làm biến dạng hình học khuôn mặt. Chuyển đổi BGR–RGB cũng cần được thực hiện đúng vì OpenCV và nhiều mô hình học sâu sử dụng thứ tự kênh khác nhau.

## 2.3. Phát hiện khuôn mặt bằng MTCNN

### 2.3.1. Bài toán phát hiện khuôn mặt

Phát hiện khuôn mặt (face detection) xác định số lượng và vị trí khuôn mặt trong ảnh. Đầu ra phổ biến là khung bao $b=(x_1,y_1,x_2,y_2)$, độ tin cậy $c$ và một số điểm mốc cơ bản. Khác với nhận dạng khuôn mặt, bước này không xác định người trong ảnh là ai.

Các phương pháp cổ điển như Viola–Jones sử dụng đặc trưng dạng Haar và bộ phân loại tầng [1]. Các phương pháp học sâu hiện đại học trực tiếp đặc trưng từ dữ liệu, xử lý tốt hơn biến thiên về tư thế và ánh sáng nhưng có chi phí tính toán lớn hơn.

### 2.3.2. Kiến trúc MTCNN

MTCNN sử dụng chuỗi ba mạng tích chập [2]:

1. **P-Net** tạo nhanh các vùng có khả năng chứa khuôn mặt ở nhiều tỉ lệ.
2. **R-Net** loại bỏ vùng sai và hiệu chỉnh khung bao.
3. **O-Net** tinh chỉnh lần cuối và dự đoán năm điểm mốc cơ bản.

Ở mỗi tầng, phép loại bỏ cực đại không tối đa (Non-Maximum Suppression – NMS) loại các khung bao trùng lặp. Cấu trúc nhiều tầng giúp giảm số vùng cần xử lý ở tầng sau. Trong đồ án, khung bao MTCNN phục vụ tín hiệu hiện diện khuôn mặt và nhiều khuôn mặt. Một phiên bản MTCNN khác trong `facenet-pytorch` được dùng để cắt và căn chỉnh khuôn mặt trước khi tạo véc-tơ đặc trưng; cần phân biệt hai vai trò này.

MTCNN vẫn có thể bỏ sót khi khuôn mặt quá nhỏ, quay ở góc lớn, bị che khuất hoặc thiếu sáng. Vì vậy, “không phát hiện” trước hết là tình trạng thiếu quan sát của mô hình và chỉ trở thành tín hiệu bất thường sau khi được kiểm tra theo thời gian.

## 2.4. Landmark khuôn mặt với MediaPipe Face Landmarker

Điểm mốc khuôn mặt (facial landmark) là tập các điểm đặc trưng mô tả đường viền mắt, môi, mũi, cằm và bề mặt khuôn mặt. MediaPipe Face Mesh/Face Landmarker dự đoán 468 điểm bề mặt từ ảnh của một camera và có thể chạy gần thời gian thực [3], [11].

Tọa độ MediaPipe được chuẩn hóa theo kích thước ảnh. Với điểm mốc $p_i=(x_i,y_i)$ đã chuẩn hóa và khung hình có kích thước $(W,H)$, tọa độ điểm ảnh là:

$$
p_i^{\mathrm{pixel}}=(x_iW,\ y_iH)
$$

Phép quy đổi này cần thiết khi tính khoảng cách Euclid. Nếu sử dụng trực tiếp tọa độ chuẩn hóa trên ảnh không vuông, hai trục có tỉ lệ khác nhau và đại lượng hình học sẽ bị sai lệch. Đồ án sử dụng tọa độ điểm ảnh cho EAR, tỉ lệ mở miệng và PnP.

Không phải mọi tín hiệu đều cần điểm mốc chi tiết của nhiều khuôn mặt. Face Landmarker chỉ theo dõi khuôn mặt chính để phục vụ tín hiệu mắt, miệng và góc quay đầu; MTCNN chịu trách nhiệm đếm khuôn mặt. Cách phân tách này giảm chi phí và làm rõ trách nhiệm của từng mô hình.

## 2.5. Phát hiện trạng thái mắt bằng EAR

Tỉ lệ khung hình mắt (Eye Aspect Ratio – EAR) là đại lượng hình học được Soukupová và Čech đề xuất để biểu diễn độ mở mắt [4]. Với sáu điểm $P_1,...,P_6$ quanh một mắt:

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

YOLO là họ mô hình phát hiện vật thể một giai đoạn, dự đoán khung bao và lớp vật thể trong một lượt suy luận [7]. So với các phương pháp hai giai đoạn, YOLO thường phù hợp hơn với xử lý thời gian thực. Đồ án sử dụng YOLOv8n đã được huấn luyện trước trên COCO [8] thông qua thư viện Ultralytics [12].

Đầu ra của bộ phát hiện vật thể gồm lớp $k$, khung bao $b$ và độ tin cậy $c$. Chỉ những dự đoán có $c$ lớn hơn ngưỡng và thuộc lớp quan tâm mới được giữ lại. Mô hình hiện tại lọc hai lớp COCO là `cell phone` và `book`; lớp `laptop` không nằm trong danh sách được cấu hình chấp nhận.

YOLO có chi phí lớn hơn bước phát hiện điểm mốc. Một chiến lược phù hợp là chạy mô hình theo chu kỳ thay vì trên mọi khung hình, sau đó giữ kết quả gần nhất giữa hai lần suy luận. Tín hiệu vật thể còn phải duy trì đủ thời lượng để một dự đoán sai thoáng qua không trở thành sự kiện vi phạm.

Mô hình được huấn luyện trước chịu ảnh hưởng của miền dữ liệu huấn luyện. Điện thoại có kích thước nhỏ, bị che khuất, nằm ở rìa ảnh hoặc quay mặt lưng có thể bị bỏ sót. Tinh chỉnh mô hình có thể cải thiện kết quả trên một miền cụ thể nhưng đòi hỏi bộ dữ liệu, cách chia tập huấn luyện/xác thực/kiểm thử và tệp mô hình được quản lý rõ ràng.

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

Độ chính xác của PnP phụ thuộc vào điểm mốc 2D, mô hình mặt 3D, tham số nội tại của camera và quy ước trục. Góc quay lớn hoặc hiện tượng che khuất có thể làm sai điểm mốc, kéo theo sai số ước lượng tư thế đầu. Do đó, hệ thống cần áp dụng ngưỡng thời lượng và không được coi một góc tức thời là kết luận.

## 2.9. Xác thực danh tính bằng face embedding

### 2.9.1. Biểu diễn véc-tơ đặc trưng

Xác minh khuôn mặt (face verification) trả lời câu hỏi hai ảnh có thuộc cùng một người hay không. FaceNet học ánh xạ $f(x)\in\mathbb{R}^d$ từ ảnh mặt sang véc-tơ đặc trưng bằng hàm mất mát bộ ba [5]. Với mẫu neo $a$, mẫu cùng người $p$ và mẫu khác người $n$:

$$
L=\max\left(0,\lVert f(a)-f(p)\rVert_2^2
-\lVert f(a)-f(n)\rVert_2^2+\alpha\right)
$$

Mục tiêu là đưa véc-tơ của cùng một người lại gần nhau và đẩy véc-tơ của người khác ra xa ít nhất một biên $\alpha$.

Đồ án sử dụng InceptionResnetV1 đã được huấn luyện trước trên VGGFace2 thông qua `facenet-pytorch` để tạo véc-tơ 512 chiều. Trong bước đăng ký, véc-tơ tham chiếu là trung bình của nhiều khung hình hợp lệ nhằm giảm ảnh hưởng của một quan sát riêng lẻ.

### 2.9.2. Cosine similarity và quyết định có biên

Độ tương tự cosine giữa hai vector $x$ và $y$ là:

$$
sim(x,y)=\frac{x\cdot y}{\lVert x\rVert_2\lVert y\rVert_2}
$$

Giá trị cao cho biết hai hướng véc-tơ gần nhau. Ngưỡng xác thực phụ thuộc vào mô hình và miền dữ liệu, do đó không có một giá trị phổ quát. Thiết kế nên có vùng cảnh báo và vùng không khớp thay vì một ngưỡng duy nhất. Đồ án còn yêu cầu nhiều kết quả không khớp liên tiếp và chỉ kiểm tra lại theo chu kỳ để tránh tạo véc-tơ đặc trưng trên mọi khung hình.

Nếu không tìm thấy khuôn mặt tại thời điểm kiểm tra lại, hệ thống không được đồng nhất tình huống này với “không đúng người”. Tín hiệu hiện diện khuôn mặt chịu trách nhiệm cho sự vắng mặt; tín hiệu danh tính chỉ đánh giá khi có véc-tơ hợp lệ để so sánh.

### 2.9.3. Liveness cơ bản

Xác minh khuôn mặt có thể bị đánh lừa bởi ảnh tĩnh nếu không kiểm tra sự hiện diện sống. Thử thách chớp mắt `mở → nhắm → mở` xác nhận một chuyển động đơn giản trước bước đăng ký. Giải pháp này có thể ngăn một số trường hợp sử dụng ảnh in hoặc ảnh trên màn hình, nhưng không chống được phát lại video, mặt nạ hoặc nội dung giả mạo tinh vi. Vì vậy, đây chỉ là kiểm tra sự hiện diện sống cơ bản, không phải cơ chế chống giả mạo hoàn chỉnh.

## 2.10. Xử lý tín hiệu theo thời gian

### 2.10.1. Debounce dựa trên thời lượng

Cơ chế chống dao động chỉ chấp nhận một điều kiện khi điều kiện đó duy trì đủ lâu. Nếu $q(t)\in\{0,1\}$ biểu diễn điều kiện thô và $D$ là thời lượng tối thiểu, tín hiệu chỉ vượt ngưỡng khi $q(t)=1$ liên tục trong khoảng $D$. Cách đo bằng giây ổn định hơn đếm số khung hình vì tốc độ khung hình có thể thay đổi theo thiết bị và tải xử lý.

### 2.10.2. Cửa sổ thời gian trượt

Với cửa sổ độ dài $W$, tỉ lệ bất thường của tín hiệu $i$ tại thời điểm $t$ là:

$$
r_i(t)=\frac{\sum_{\tau\in(t-W,t]}\mathbb{1}[q_i(\tau)=1]}
{\sum_{\tau\in(t-W,t]}\mathbb{1}[q_i(\tau)\text{ hợp lệ}]}
$$

Cửa sổ trượt giữ lại lịch sử gần nhất, loại bỏ ảnh hưởng lâu dài của sự kiện cũ và hỗ trợ các mẫu không liên tục như hoạt động miệng.

### 2.10.3. Máy trạng thái hữu hạn

Máy trạng thái hữu hạn (Finite State Machine – FSM) biểu diễn hệ thống bằng tập trạng thái và điều kiện chuyển. Ba trạng thái `NORMAL`, `SUSPICIOUS`, `ALERT` cho phép phân biệt quan sát ban đầu với bằng chứng kéo dài. Máy trạng thái của mỗi tín hiệu hoạt động độc lập để nhiều hành vi có thể được ghi nhận đồng thời.

## 2.11. Kết hợp đa tín hiệu và hysteresis

### 2.11.1. Tổng hợp có trọng số

Sau khi ổn định từng tín hiệu, trạng thái có thể ánh xạ thành giá trị $s_i$ và kết hợp bằng tổng có trọng số:

$$
R(t)=\sum_{i=1}^{n}w_is_i(t)
$$

Trọng số $w_i$ biểu diễn mức đóng góp tương đối. Tổng hợp có trọng số có ưu điểm dễ giải thích, dễ cấu hình và không đòi hỏi tập huấn luyện lớn. Hạn chế của phương pháp là quan hệ tuyến tính không tự học được các tương tác phức tạp giữa các tín hiệu.

### 2.11.2. Hysteresis

Nếu chỉ dùng một ngưỡng $T$, nhiễu quanh $T$ làm trạng thái bật/tắt liên tục. Vùng trễ (hysteresis) sử dụng hai ngưỡng:

$$
state(t)=
\begin{cases}
ALERT,&state(t-1)=NORMAL\land R(t)\ge T_{enter}\\
NORMAL,&state(t-1)=ALERT\land R(t)\le T_{exit}\\
state(t-1),&\text{các trường hợp còn lại}
\end{cases}
$$

với $T_{exit}<T_{enter}$. Khoảng $(T_{exit},T_{enter})$ là vùng đệm giữ nguyên trạng thái cũ. Công thức trên minh họa quyết định hai trạng thái ở cấp phiên; máy trạng thái ba mức của từng tín hiệu sử dụng các điều kiện chuyển chi tiết hơn. Vùng trễ có thể được áp dụng ở cả cấp tín hiệu và cấp phiên.

### 2.11.3. Cạnh chuyển trạng thái và sự kiện

Một cảnh báo kéo dài không nên tạo một sự kiện ở mọi khung hình. Sự kiện được sinh tại cạnh chuyển vào trạng thái cảnh báo; thời lượng có thể suy ra từ bản ghi chuyển trạng thái trở về bình thường. Cách này giảm kích thước nhật ký và tránh hiển thị nhiều bản ghi cho cùng một hành vi.

## 2.12. Giao tiếp thời gian thực và hợp đồng dữ liệu

REST phù hợp với thao tác yêu cầu–phản hồi như đăng nhập, tạo kỳ thi và lấy danh sách phiên. WebSocket theo RFC 6455 [9] duy trì kênh song công để máy khách gửi nhịp kết nối và dữ liệu giám sát, còn máy chủ đẩy cập nhật đến bảng điều khiển mà không cần thăm dò liên tục.

Kênh thời gian thực không loại bỏ nhu cầu xác thực và kiểm tra dữ liệu. Một thông điệp từ máy khách cần:

- Có loại và lược đồ xác định.
- Giới hạn kích thước, tần suất và số phần tử.
- Phân biệt dấu thời gian do máy khách cung cấp với thời gian máy chủ tiếp nhận.
- Gắn với đúng loại token và đúng phiên.
- Có cơ chế nhịp kết nối, thời hạn chờ khi không hoạt động và trạng thái mất kết nối.

Hợp đồng dữ liệu giúp các thành phần thống nhất ý nghĩa của trường dữ liệu. `SignalResult`, `ViolationEvent` và sự kiện trình duyệt phải dùng giá trị liệt kê cố định, số hữu hạn và siêu dữ liệu có giới hạn. Máy chủ có thể tính lại hoặc đối chiếu giá trị dẫn xuất thay vì tin trực tiếp điểm do máy khách gửi.

## 2.13. Phân quyền và cô lập nhiều tổ chức

Kiểm soát truy cập dựa trên vai trò (Role-Based Access Control – RBAC) gán quyền cho vai trò thay vì từng người dùng riêng lẻ [10]. Trong nền tảng nhiều tổ chức, chỉ kiểm tra vai trò là chưa đủ; quyết định còn phụ thuộc vào tổ chức và tài nguyên cụ thể. Có thể mô hình hóa quyền hiệu lực như:

$$
Allowed(u,a,r)=Authenticated(u)\land Active(u)\land
TenantMatch(u,r)\land Capability(u,a)\land ResourceScope(u,r)
$$

Trong đó $u$ là người dùng, $a$ là hành động và $r$ là tài nguyên. Nhiệm vụ được giao trên kỳ thi là một dạng phạm vi tài nguyên: người dùng có thể có vai trò quản lý ở kỳ thi A nhưng chỉ có vai trò giám thị ở kỳ thi B.

Nguyên tắc đặc quyền tối thiểu yêu cầu chỉ cấp các quyền cần thiết. Quản trị viên nền tảng không nên mặc nhiên được xem bằng chứng của mọi tổ chức. Quyền ngoại lệ cần có lý do, phạm vi, phê duyệt, thời hạn và nhật ký kiểm toán. Khi tài nguyên nằm ngoài phạm vi, phản hồi `404` có thể hạn chế tiết lộ sự tồn tại của tài nguyên tốt hơn việc trả chi tiết về quyền còn thiếu.

## 2.14. Lưu trữ sự kiện và khả năng truy vết

Cơ sở dữ liệu quan hệ phù hợp với những thực thể có quan hệ và cần truy vấn như tổ chức, người dùng, kỳ thi, nhiệm vụ được giao và trạng thái phiên mới nhất. JSON Lines phù hợp với chuỗi sự kiện chỉ ghi nối tiếp vì mỗi dòng là một đối tượng JSON độc lập, có thể ghi tuần tự và đọc từng phần.

Mô hình lai cho phép:

- SQL phục vụ bảng điều khiển và kiểm soát quyền.
- JSONL lưu diễn biến chi tiết của tín hiệu, chuyển trạng thái và sự kiện.
- Ảnh chụp cung cấp bằng chứng hình ảnh tại thời điểm cần thiết.
- Báo cáo được tái tạo từ dữ liệu gốc thay vì chỉ lưu một kết luận tổng hợp.

Nhật ký kiểm toán khác với bằng chứng phiên thi. Bằng chứng mô tả điều xảy ra trong phiên; nhật ký kiểm toán mô tả ai đã thao tác trên hệ thống hoặc truy cập dữ liệu. Hai loại dữ liệu cần được tách biệt để hỗ trợ truy vết và trách nhiệm giải trình.

## 2.15. Các chỉ số đánh giá

Với bài toán nhị phân, confusion matrix gồm:

- **True Positive (TP):** vi phạm thật được phát hiện.
- **False Positive (FP):** hệ thống cảnh báo nhưng nhãn tham chiếu là bình thường.
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

Accuracy có thể gây hiểu nhầm khi dữ liệu mất cân bằng vì một hệ thống luôn dự đoán lớp phổ biến vẫn có thể đạt Accuracy cao. Do đó, cần báo cáo đồng thời Precision, Recall, F1 và ma trận nhầm lẫn.

Đơn vị đánh giá cũng phải được công bố. Đánh giá theo khung hình coi mỗi khung hình là một mẫu; đánh giá theo sự kiện so khớp sự kiện với khoảng thời gian có nhãn tham chiếu. Hai cách đánh giá trả lời những câu hỏi khác nhau và cho kết quả khác nhau. Độ trễ phát hiện của một trường hợp dương tính đúng được tính bằng:

$$
Latency=t_{detected}-t_{ground\ truth\ start}
$$

Đối với ROC-AUC hoặc PR-AUC, cần có score liên tục ở nhiều ngưỡng hoặc một quá trình quét ngưỡng. Một confusion matrix tại một ngưỡng duy nhất không đủ để suy ra hai diện tích này.

## 2.16. Kết chương

Chương 2 đã trình bày nền tảng của các thành phần chính: phát hiện khuôn mặt bằng MTCNN, điểm mốc MediaPipe, EAR, tỉ lệ mở miệng, YOLO, PnP, véc-tơ đặc trưng khuôn mặt, kiểm tra sự hiện diện sống cơ bản, xử lý theo thời gian, tổng hợp có trọng số và vùng trễ. Chương cũng trình bày WebSocket, hợp đồng dữ liệu, RBAC, cô lập dữ liệu giữa các tổ chức, lưu trữ sự kiện và các chỉ số đánh giá để phản ánh đầy đủ nền tảng lý thuyết của hệ thống.

Chương 3 tiếp theo khảo sát các giải pháp liên quan và chuyển các vấn đề đã nhận diện thành yêu cầu chức năng, phi chức năng và tiêu chí nghiệm thu cụ thể.
