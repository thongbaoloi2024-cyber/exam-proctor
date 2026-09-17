"""One-off editorial revision. Backups preserve the user's pre-existing changes."""
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent
backup = ROOT / 'tmp' / 'editorial_backup_20260917'
backup.mkdir(parents=True, exist_ok=True)
for path in [*ROOT.glob('*.tex'), ROOT / 'README_UPDATE.md', ROOT / 'main.pdf']:
    if not (backup / path.name).exists():
        shutil.copy2(path, backup / path.name)

def replace(path, old, new):
    file = ROOT / path
    text = file.read_text(encoding='utf-8-sig')
    if old not in text:
        raise ValueError(f'Missing text in {path}: {old[:100]}')
    file.write_text(text.replace(old, new), encoding='utf-8')

replace('Chuong1.tex', 'Đồ án áp dụng phương pháp thiết kế hệ thống kết hợp thực nghiệm.',
        'Đồ án áp dụng phương pháp nghiên cứu tài liệu, phân tích yêu cầu và thiết kế hệ thống, kết hợp kiểm tra phép tính trên dữ liệu tổng hợp. Thực nghiệm trên video CCTV có nhãn tham chiếu được xác định là bước đánh giá tiếp theo.')
replace('Chuong1.tex', 'lưu chính xác mốc bắt đầu/kết thúc khoảng hiện diện', 'ước lượng mốc bắt đầu và kết thúc khoảng hiện diện')
replace('Chuong1.tex', 'thời điểm bắt đầu/kết thúc thật', 'thời điểm quan sát bắt đầu và kết thúc')
replace('Chuong1.tex', r'T_{phone}(e)=\sum_j |P_j\cap I_e\cap W|.',
        r'T_{phone}(e)=\left|\left(\bigcup_j P_j\right)\cap\left(\bigcup_k [s_k,e_k]\right)\cap W\right|.')
replace('Chuong1.tex', 'Cách tách bốn đại lượng ở trên', 'Các khoảng hiện diện phải được hợp nhất trước khi cộng để tránh tính trùng. Cách tách bốn đại lượng ở trên')
replace('Chuong2.tex', 'Báo cáo không diễn giải chi tiết nghĩa vụ pháp lý thay chuyên gia pháp lý, nhưng rút ra các nguyên tắc thiết kế kỹ thuật:',
        'Trong phạm vi kỹ thuật, đồ án xác định các nguyên tắc thiết kế gồm')
replace('Chuong2.tex', 'Tập interval cần được chuẩn hóa trước khi tổng hợp: sắp xếp theo thời gian, loại khoảng âm và hợp nhất các khoảng chồng lấn hoặc cách nhau dưới tolerance.',
        'Tập khoảng thời gian cần được chuẩn hóa trước khi tổng hợp bằng cách sắp xếp theo thời gian, từ chối khoảng có độ dài âm và hợp nhất các khoảng chồng lấn. Chỉ nối hai khoảng cách nhau dưới sai số kỹ thuật khi có bằng chứng chúng thuộc cùng một phiên liên tục. Không tự động nối các khoảng vắng mặt ngắn.')
replace('Chuong2.tex', r'\max(T_i,\epsilon)', 'T_i')
replace('Chuong2.tex', 'Với phiên có $T_i$ gần 0, MAPE không ổn định nên cần $\\epsilon$ hoặc loại trường hợp không có ground truth dương.',
        'MAPE chỉ được tính trên các mẫu có $T_i>0$, trong đó $N$ là số mẫu đáp ứng điều kiện này. Số mẫu có $T_i=0$ phải được báo cáo riêng và đánh giá bằng sai số tuyệt đối. Khi $T_i$ rất nhỏ, MAPE cần được diễn giải cùng MAE để tránh phóng đại mức sai lệch.')
replace('Chuong3.tex', 'Một thiết kế ngây thơ', 'Một phương án cơ sở')
replace('Chuong3.tex', 'tạo/dóng', 'mở và đóng')
replace('Chuong3.tex', 'ngưỡng mục tiêu cuối cùng chỉ được chốt sau thực nghiệm thật',
        'ngưỡng nghiệm thu phải được xác định trước khi đánh giá trên tập kiểm tra độc lập')
replace('Chuong4.tex', 'Session chỉ mở khi presence state là PRESENT hoặc GRACE trong giới hạn cho phép.',
        'Phiên điện thoại mới chỉ được mở khi trạng thái hiện diện là PRESENT. Phiên đã mở có thể được duy trì trong GRACE theo giới hạn cho phép, nhưng phải kết thúc không muộn hơn khoảng hiện diện tương ứng.')
replace('Chuong4.tex', 'FSM hiện diện gồm:',
        'Máy trạng thái hiện diện gồm bốn trạng thái nghiệp vụ dưới đây. Trạng thái bổ sung SUSPENDED được sử dụng khi nguồn quan sát bị gián đoạn và được mô tả tại mục về bất biến của máy trạng thái.')
replace('Chuong5.tex', '\\subsection{Công nghệ sử dụng}',
        '\\subsection{Phạm vi cài đặt và công nghệ lựa chọn}\nChương này trình bày phương án tổ chức cài đặt từ kiến trúc ở Chương 4. Cấu trúc thư mục, cấu hình và mã giả là đặc tả triển khai. Các nội dung này không thay thế bằng chứng chạy chương trình hoặc kết quả kiểm thử trên hệ thống hoàn chỉnh.\n')
replace('Chuong5.tex', '\\subsection{Cấu trúc kho mã nguồn sau khi tái cấu trúc}', '\\subsection{Cấu trúc kho mã nguồn đề xuất}')
replace('Chuong5.tex', 'Từ source nền, các gói proctoring được thay bằng các miền mới. Cấu trúc mục tiêu:',
        'Các gói chức năng được tổ chức theo miền nghiệp vụ nhân viên, camera, hiện diện và thời gian. Cấu trúc thư mục đề xuất như sau:')
replace('Chuong5.tex', 'Cấu trúc này giữ các thành phần hạ tầng đã ổn định như auth, authorization, WebSocket manager, reporting worker và Docker; đồng thời loại bỏ browser extension, head pose, eye/mouth signal và risk fusion vốn chỉ có ý nghĩa với đề tài giám sát thi cũ.',
        'Cấu trúc đề xuất cho phép tái sử dụng các thành phần xác thực, phân quyền, quản lý WebSocket, sinh báo cáo và đóng gói Docker. Các chức năng không thuộc bài toán hiện diện được đặt ngoài phạm vi triển khai.')
replace('Chuong5.tex', r'\texttt{backend/models.py} được thay các entity Exam/Candidate bằng Employee, Camera, WorkArea, WorkSchedule, MonitoringSession, PresenceInterval, PhoneUsageInterval và DailyWorkSummary.',
        r'Tệp \texttt{backend/models.py} cần định nghĩa các thực thể Employee, Camera, WorkArea, WorkSchedule, MonitoringSession, PresenceInterval, PhoneUsageInterval và DailyWorkSummary theo mô hình dữ liệu đã thiết kế.')
replace('Chuong5.tex', 'Schema cũ yêu cầu đủ bảy signal proctoring được thay bằng', 'Lược đồ thông điệp được thiết kế gồm')
replace('Chuong5.tex', '  person_conf: 0.35', '  person_conf: 0.10')
replace('Chuong5.tex', 'result = model(frame)\npersons = []', 'result = model(frame, conf=min(person_conf, phone_conf))[0]\npersons = []')
replace('Chuong5.tex', 'box.class', 'int(box.cls.item())')
replace('Chuong5.tex', 'box.conf >=', 'float(box.conf.item()) >=')
replace('Chuong5.tex', 'Policy nghiệp vụ như allowance không đặt chung',
        'Ngưỡng lọc người ở đầu ra bộ phát hiện không được lớn hơn ngưỡng liên kết thấp của ByteTrack, nếu không các hộp có độ tin cậy thấp sẽ bị loại trước bước ghép thứ hai. Các giá trị trong ví dụ chỉ là cấu hình khởi đầu, chưa được hiệu chỉnh trên video thực địa.\n\nPolicy nghiệp vụ như allowance không đặt chung')
replace('Chuong5.tex', 'có thể bỏ khỏi billing', 'có thể loại khỏi phần tổng hợp thời gian')
replace('Chuong5.tex', 'Vì thực tế mỗi frame thường ít phone, phương án tham lam có kiểm soát xung đột đủ đơn giản và dễ kiểm thử.',
        'Phương án tham lam có kiểm soát xung đột phù hợp để xây dựng nguyên mẫu. Chất lượng liên kết cần được so sánh với phương án gán tối ưu khi số đối tượng tăng.')
replace('Chuong5.tex', '$d_n$ được chuẩn hóa theo chiều cao person box', '$d_n$ được chuẩn hóa theo chiều cao person box và giới hạn trong $[0,1]$')

# Rewrite conclusions around the current thesis, rather than its editing history.
p = ROOT / 'Chuong7.tex'
t = p.read_text(encoding='utf-8')
start = t.index('Đồ án đã chuyển bài toán')
end = t.index('\\subsection{Kết quả chính', start)
t = t[:start] + '''Đồ án nghiên cứu bài toán chuyển video từ một camera CCTV cố định thành các khoảng hiện diện của nhiều nhân viên trong khu vực làm việc. Giải pháp kết hợp phát hiện đối tượng, theo dõi đa đối tượng, liên kết vùng và xác minh danh tính nhằm xây dựng dữ liệu thời gian có thể giải thích và truy vết.

Kiến trúc đề xuất sử dụng YOLOv8 để phát hiện người và điện thoại, ByteTrack để duy trì quỹ đạo, vùng quan tâm đa giác để mô tả vị trí làm việc và FaceNet để hỗ trợ xác minh danh tính. Hai máy trạng thái xử lý hiện diện và sử dụng điện thoại. Bộ tổng hợp giữ riêng thời gian hiện diện, thời gian điện thoại, hạn mức, phần vượt hạn mức và thời gian hiệu lực. Các thành phần quản trị, truyền dữ liệu và báo cáo được tổ chức quanh các thực thể nhân viên, camera và khu vực làm việc.

''' + t[end:]
start=t.index('Chương 6 đã xây dựng')
end=t.index('\\subsection{Hạn chế',start)
t=t[:start]+'''Chương 6 xác định quy trình đánh giá phát hiện, theo dõi, hiện diện, liên kết điện thoại và sai số thời lượng. Bộ dữ liệu tổng hợp kèm báo cáo cho phép tính lại các chỉ số từ số đếm và bản ghi thời gian. Các bảng, biểu đồ được sinh từ cùng một nguồn dữ liệu nhằm kiểm tra tính nhất quán của phép tính và cách trình bày.

Các kết quả tính toán này chỉ mô tả bộ dữ liệu tổng hợp. Chưa có cơ sở để suy ra độ chính xác, tốc độ xử lý hoặc thứ hạng thuật toán trên camera thực địa. Việc kiểm chứng giả thuyết về hiệu quả của giải pháp cần dựa trên video có nhãn tham chiếu độc lập, cấu hình đã khóa và kết quả chạy có thể tái lập.

'''+t[end:]
t=t.replace('Khác với hệ thống cũ chọn khuôn mặt chính, thiết kế mới coi', 'Thiết kế coi')
t=t.replace('Đề tài mới hình thành một bài toán rõ ràng hơn ở cấp hệ thống:', 'Đóng góp của đồ án ở cấp hệ thống là')
t=t.replace('Presence không phải productivity.', 'Sự hiện diện không đồng nghĩa với năng suất lao động.')
t=t.replace('Hạn chế lớn nhất của bản cập nhật là số liệu đánh giá chưa phải dữ liệu thực. Mọi kết luận định lượng phải chờ thực nghiệm thật. Các số mô phỏng chỉ phục vụ thiết kế và kiểm tra biểu mẫu báo cáo.',
            'Hạn chế chính là chưa có kết quả đo trên bộ video thực địa có nhãn tham chiếu. Dữ liệu tổng hợp hỗ trợ kiểm tra công thức và phân tích độ nhạy theo giả định, nhưng chưa thể dùng để xác nhận chất lượng mô hình hoặc mức sai số khi triển khai.')
p.write_text(t,encoding='utf-8')

replace('TomTat.tex', 'Hệ thống hoàn chỉnh gồm', 'Kiến trúc hệ thống gồm')
replace('TomTat.tex', 'bao gồm các chỉ số phát hiện, theo dõi, phân loại hiện diện, phát hiện sử dụng điện thoại và sai số ước lượng thời gian',
        'bao gồm số đếm phân loại, các mẫu thời lượng điện thoại và thời gian theo ca. Chỉ số được tính từ dữ liệu tổng hợp kèm theo, trong khi đánh giá theo dõi và hiệu năng được trình bày dưới dạng quy trình thực nghiệm')

# Protect code, mathematical notation and LaTeX references while editing prose.
protected = re.compile(
    r'(\\begin\{(?:Verbatim|verbatim|tikzpicture)\}.*?\\end\{(?:Verbatim|verbatim|tikzpicture)\}'
    r'|\\begin\{(?:equation|align)\}.*?\\end\{(?:equation|align)\}'
    r'|\$[^$]*\$|\\(?:texttt|url|label|ref|cite|input)\{[^}]*\}'
    r'|\\includegraphics(?:\[[^]]*\])?\{[^}]*\})', re.S)
phrases = {
    'source nền': 'mã nguồn nền', 'Source nền': 'Mã nguồn nền',
    'source mới': 'mã nguồn triển khai', 'source': 'mã nguồn',
    'bản cập nhật': 'bản thảo', 'project': 'đồ án',
    'detection miss': 'lỗi bỏ sót phát hiện', 'Detection miss': 'Lỗi bỏ sót phát hiện',
    'person detection': 'phát hiện người', 'phone detection': 'phát hiện điện thoại',
    'face verification': 'xác minh khuôn mặt', 'Face verification': 'Xác minh khuôn mặt',
    'identity verification': 'xác minh danh tính', 'face recognition': 'nhận dạng khuôn mặt',
    'face embedding': 'vector đặc trưng khuôn mặt', 'Face embedding': 'Vector đặc trưng khuôn mặt',
    'phone session': 'phiên sử dụng điện thoại', 'presence interval': 'khoảng hiện diện',
    'presence intervals': 'các khoảng hiện diện', 'phone intervals': 'các khoảng sử dụng điện thoại',
    'phone interval': 'khoảng sử dụng điện thoại', 'phone usage': 'thời gian sử dụng điện thoại',
    'gross presence': 'tổng thời gian hiện diện', 'effective work time': 'thời gian làm việc hiệu lực',
    'state machine': 'máy trạng thái', 'State machine': 'Máy trạng thái',
    'grace period': 'khoảng đệm', 'Grace period': 'Khoảng đệm',
    'ground truth': 'nhãn tham chiếu', 'Ground truth': 'Nhãn tham chiếu',
    'input/output': 'đầu vào và đầu ra', 'input, output': 'đầu vào, đầu ra',
    'frame-level': 'ở cấp khung hình', 'frame index': 'chỉ số khung hình',
    'model weight': 'trọng số mô hình', 'model version': 'phiên bản mô hình',
    'model checksum': 'mã kiểm tra trọng số mô hình',
    'weight fine-tune': 'trọng số được tinh chỉnh',
    'fine-tune': 'tinh chỉnh', 'pretrained': 'được huấn luyện trước',
    'raw event': 'sự kiện gốc', 'Raw event': 'Sự kiện gốc',
    'current state': 'trạng thái hiện tại', 'Current state': 'Trạng thái hiện tại',
    'policy version': 'phiên bản chính sách', 'Policy version': 'Phiên bản chính sách',
    'event store': 'kho sự kiện', 'event log': 'nhật ký sự kiện',
    'audit log': 'nhật ký kiểm toán', 'audit trail': 'lịch sử kiểm toán',
    'backdating': 'truy hồi mốc thời gian', 'backdate': 'truy hồi mốc',
    'hard-code': 'gán cố định trong mã nguồn', 'hot-swap': 'thay thế ngay khi đang chạy',
    'bit-for-bit đúng': 'chính xác đến đơn vị lưu trữ',
    'trade-off': 'sự đánh đổi', 'trade-offs': 'các sự đánh đổi',
    'Pseudo-code:': 'Mã giả minh họa:',
    'frame': 'khung hình', 'Frame': 'Khung hình',
    'detector': 'bộ phát hiện', 'Detector': 'Bộ phát hiện',
    'tracker': 'bộ theo dõi', 'Tracker': 'Bộ theo dõi',
    'pipeline': 'chuỗi xử lý', 'Pipeline': 'Chuỗi xử lý',
    'threshold': 'ngưỡng', 'thresholds': 'các ngưỡng',
    'dashboard': 'bảng điều khiển', 'Dashboard': 'Bảng điều khiển',
}
ordered=sorted(phrases,key=len,reverse=True)
pattern=re.compile(r'(?<![\w\\])('+'|'.join(map(re.escape,ordered))+r')(?![\w])')

def prose(s):
    s=s.replace('&#x20;', ' ').replace('&nbsp;', ' ')
    s=pattern.sub(lambda m:phrases[m.group()],s)
    # Coordinate clauses with commas. Split very long paragraphs at former semicolons later.
    s=s.replace(';', ',')
    return s

for path in ROOT.glob('*.tex'):
    if path.name in {'main.tex','Bia.tex','TaiLieuThamKhao.tex','LoiCamDoan.tex'}:
        continue
    parts=protected.split(path.read_text(encoding='utf-8-sig'))
    path.write_text(''.join(p if i%2 else prose(p) for i,p in enumerate(parts)),encoding='utf-8')

replace('PhuLuc.tex', r'ABSENT/\allowbreak CANDIDATE/\allowbreak PRESENT/\allowbreak GRACE',
        r'ABSENT/\allowbreak CANDIDATE/\allowbreak PRESENT/\allowbreak GRACE/\allowbreak SUSPENDED')
print('Editorial revision applied. Original files preserved in', backup)
