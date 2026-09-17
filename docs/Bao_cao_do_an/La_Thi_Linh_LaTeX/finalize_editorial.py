from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
path=ROOT/'Chuong6.tex'
t=path.read_text(encoding='utf-8')
start=t.index('\\subsection{Đánh giá phát hiện người -- số liệu mô phỏng}')
end=t.index('\\subsection{Đánh giá bảng điều khiển và luồng dữ liệu}',start)
t=t[:start]+'\\input{generated/synthetic_results}\n\n'+t[end:]
start=t.index('\\textbf{Lưu ý quan trọng:}')
end=t.index('\\subsection{Thiết kế bộ dữ liệu thực nghiệm}',start)
t=t[:start]+'''Phạm vi đánh giá trong bản thảo gồm hai phần: kiểm tra công thức và cách tổng hợp chỉ số bằng dữ liệu tổng hợp có thể tái tạo, cùng quy trình thực nghiệm trên video CCTV có nhãn tham chiếu. Phần dữ liệu tổng hợp được trình bày tại mục \\ref{sec:synthetic-origin}. Chưa có bộ video thực địa và kết quả chạy mô hình kèm theo để xác nhận chất lượng hệ thống trong môi trường triển khai.

Quy trình thực nghiệm cần bảo đảm ba nguyên tắc: tập hiệu chỉnh tham số tách biệt với tập kiểm tra, nhãn tham chiếu được xây dựng độc lập với dự đoán của mô hình, và kết quả bao gồm cả sai số thị giác lẫn sai số thời lượng.

'''+t[end:]
start=t.index('\\subsection{Phân tích độ tin cậy của số liệu mô phỏng}')
end=t.index('\\subsection{Kế hoạch thực nghiệm chính thức}',start)
t=t[:start]+'''\\subsection{Độ tin cậy của phép tính và phạm vi suy luận}
Các bảng tổng hợp đã được kiểm tra về mẫu số, tổng số mẫu và ràng buộc thời lượng. Sự nhất quán này xác nhận phép tính trên bộ dữ liệu đã khai báo, nhưng không xác nhận phân phối dữ liệu tương ứng với một môi trường thực tế. Đặc biệt, các mức nhiễu được lựa chọn trước nên không được dùng để chứng minh ưu thế của phương pháp đề xuất.

Đánh giá trên video cần kèm thông tin phần cứng, trọng số mô hình, phiên bản mã nguồn, cấu hình, vị trí camera và quy trình gán nhãn. Kết quả được lưu riêng với bộ dữ liệu tổng hợp để có thể truy nguyên từng bảng và biểu đồ.

'''+t[end:]
start=t.index('\\subsection{Kết luận chương}')
t=t[:start]+'''\\subsection{Kết luận chương}
Chương này xác định quy trình đánh giá từ chất lượng quan sát đến sai số thời lượng. Bộ dữ liệu tổng hợp công bố số đếm và bản ghi nguồn để kiểm tra lại Precision, Recall, F1, WPAR, MAE và MAPE. Kết quả tính toán cho thấy các bảng và biểu đồ nhất quán với dữ liệu nguồn trong phạm vi giả định đã nêu. Hiệu quả của bộ phát hiện, bộ theo dõi và máy trạng thái vẫn cần được kiểm chứng bằng thực nghiệm trên video có nhãn tham chiếu độc lập.
'''
t=t.replace('Ba chuỗi xử lý được so sánh:', 'Thực nghiệm trên video được thiết kế để so sánh ba chuỗi xử lý:')
t=t.replace('Nếu chỉ dùng được huấn luyện trước và không tinh chỉnh', 'Nếu chỉ dùng mô hình được huấn luyện trước và không tinh chỉnh')
t=t.replace('Khoảng tin cậy và biến thiên', 'Phương pháp ước lượng khoảng tin cậy và biến thiên')
t=t.replace('Trước khi thay số liệu mô phỏng, cần checklist:', 'Trước khi công bố kết quả thực nghiệm, cần kiểm tra các điều kiện sau:')
path.write_text(t,encoding='utf-8')

p=ROOT/'PhuLuc.tex'
t=p.read_text(encoding='utf-8')+'\n\\input{generated/synthetic_appendix}\n'
t=t.replace('Thay toàn bộ bảng/hình có chữ ``mô phỏng'' nếu đã có kết quả thật.',
            'Chỉ thay bảng và hình tổng hợp bằng kết quả đo khi có dữ liệu nguồn và chương trình tái lập tương ứng. Giữ rõ nguồn gốc nếu trình bày cả hai loại kết quả.')
p.write_text(t,encoding='utf-8')

protected=re.compile(r'(\\begin\{(?:Verbatim|verbatim|tikzpicture|equation|align)\}.*?\\end\{(?:Verbatim|verbatim|tikzpicture|equation|align)\}|\$[^$]*\$|\\(?:texttt|url|label|ref|cite|input)\{[^}]*\}|\\includegraphics(?:\[[^]]*\])?\{[^}]*\})',re.S)
terms={
    'phone--person association':'liên kết người--điện thoại',
    'Phone--person association':'Liên kết người--điện thoại',
    'Phone association':'Liên kết điện thoại',
    'phone association':'liên kết điện thoại',
    'phone-use':'hành vi sử dụng điện thoại',
    'Phone-use':'Hành vi sử dụng điện thoại',
    'person box':'hộp bao người','phone box':'hộp bao điện thoại',
    'bounding box':'hộp bao','Bounding box':'Hộp bao',
    'track ID':'mã quỹ đạo','Track ID':'Mã quỹ đạo',
    'employee ID':'mã nhân viên','Employee ID':'Mã nhân viên',
    'ID switch':'lần đổi định danh','ID Switch':'Lần đổi định danh',
    'identity switch':'lần đổi định danh',
    'identity state':'trạng thái danh tính','identity support':'hỗ trợ xác minh danh tính',
    'identity mismatch':'danh tính không khớp','Identity mismatch':'Danh tính không khớp',
    'ROI matching':'liên kết vùng ROI','ROI association':'liên kết vùng ROI',
    'ROI score':'điểm liên kết vùng ROI','ROI consistency':'tính nhất quán với vùng ROI',
    'false positive':'dương tính giả','False positive':'Dương tính giả',
    'false absence':'vắng mặt giả','false presence':'hiện diện giả',
    'camera outage':'gián đoạn camera','Camera outage':'Gián đoạn camera',
    'work area':'khu vực làm việc','Work area':'Khu vực làm việc',
    'phone owner':'người sử dụng điện thoại',
    'owner association':'liên kết người sử dụng','owner label':'nhãn người sử dụng',
    'phone used/allowed/excess':'thời gian điện thoại, hạn mức và phần vượt mức',
    'effective time':'thời gian hiệu lực','gross time':'tổng thời gian hiện diện',
    'phone state':'trạng thái điện thoại','presence state':'trạng thái hiện diện',
    'Phone state':'Trạng thái điện thoại','Phone evaluation':'Đánh giá điện thoại',
    'phone excess':'thời gian điện thoại vượt hạn mức',
    'phone allowance':'hạn mức điện thoại','allowance/deduction':'hạn mức và quy tắc điều chỉnh',
    'timestamp monotonic':'mốc thời gian đơn điệu',
    'monotonic timestamp':'mốc thời gian đơn điệu',
    'monotonic clock':'đồng hồ đơn điệu','Monotonic clock':'Đồng hồ đơn điệu',
    'wall-clock':'đồng hồ thời gian thực',
    'unit test':'kiểm thử đơn vị','Unit test':'Kiểm thử đơn vị',
    'integration test':'kiểm thử tích hợp','Integration test':'Kiểm thử tích hợp',
    'Security test':'Kiểm thử bảo mật','test set':'tập kiểm tra','Test set':'Tập kiểm tra',
    'tập test':'tập kiểm tra','tập train':'tập huấn luyện','tập validation':'tập xác thực',
    'test split':'phân hoạch kiểm tra','test subset':'tập con kiểm tra',
    'cấu hình threshold':'cấu hình ngưỡng','config threshold':'cấu hình ngưỡng',
    'config version':'phiên bản cấu hình','configuration version':'phiên bản cấu hình',
    'feature flag':'cờ bật hoặc tắt chức năng','operating point':'điểm vận hành',
    'sampling rate':'tần suất lấy mẫu','sample size':'cỡ mẫu','frame drop':'bỏ khung hình',
    'được huấn luyện trước và không fine-tune':'được huấn luyện trước và không tinh chỉnh',
    'nguồn sự thật duy nhất':'nguồn dữ liệu chính duy nhất',
    'source of truth':'nguồn dữ liệu chính',
    'phần source':'phần mã nguồn','commit code':'mã phiên bản chương trình',
    'commit source':'mã phiên bản chương trình','commit mã nguồn':'mã phiên bản chương trình',
    'dataset description':'mô tả bộ dữ liệu',
    'presence classification':'phân loại hiện diện','session classification':'phân loại phiên',
    'time evaluation':'đánh giá thời lượng','Tracking metric':'Chỉ số theo dõi',
    'confidence aggregate':'độ tin cậy tổng hợp','confidence detector':'ngưỡng tin cậy của bộ phát hiện',
    'tune':'hiệu chỉnh','tuning':'hiệu chỉnh','validation':'xác thực',
    'detection':'quan sát phát hiện','Detection':'Quan sát phát hiện',
    'detections':'các quan sát phát hiện',
    'tracking':'theo dõi','Tracking':'Theo dõi',
    'identity':'danh tính','Identity':'Danh tính',
    'person':'người','phone':'điện thoại','Phone':'Điện thoại',
    'employee':'nhân viên','Employee':'Nhân viên',
    'intervals':'các khoảng thời gian','interval':'khoảng thời gian','Interval':'Khoảng thời gian',
    'state':'trạng thái','State':'Trạng thái',
    'transition':'chuyển trạng thái','transitions':'các chuyển trạng thái',
    'event':'sự kiện','Event':'Sự kiện',
    'session':'phiên','Session':'Phiên',
    'policy':'chính sách','Policy':'Chính sách',
    'schedule':'lịch làm việc','Schedule':'Lịch làm việc',
    'summary':'bản tổng hợp','Summary':'Bản tổng hợp',
    'allowance':'hạn mức','excess':'phần vượt hạn mức','deduction':'điều chỉnh thời gian',
    'presence':'hiện diện','Presence':'Hiện diện',
    'model':'mô hình','Model':'Mô hình',
    'dataset':'bộ dữ liệu','Dataset':'Bộ dữ liệu',
    'metric':'chỉ số','Metric':'Chỉ số','metrics':'các chỉ số',
    'latency':'độ trễ','Latency':'Độ trễ',
    'retention':'thời hạn lưu trữ','Retention':'Thời hạn lưu trữ',
    'evidence':'bằng chứng','Evidence':'Bằng chứng',
    'snapshot':'ảnh chụp','Snapshot':'Ảnh chụp',
    'review':'hậu kiểm','Review':'Hậu kiểm',
    'score':'điểm liên kết','confidence':'độ tin cậy',
    'box':'hộp bao','track':'quỹ đạo','Track':'Quỹ đạo',
    'annotation':'gán nhãn','Annotation':'Gán nhãn',
    'annotator':'người gán nhãn','occlusion':'che khuất','Occlusion':'Che khuất',
    'outlier':'mẫu ngoại lệ','outage':'gián đoạn quan sát',
    'artifact':'tệp kết quả','artifacts':'các tệp kết quả',
    'trade-off':'sự đánh đổi','config':'cấu hình','Config':'Cấu hình',
    'report':'báo cáo','Report':'Báo cáo',
    'code':'mã chương trình','UI':'giao diện','realtime':'thời gian thực',
}
pattern=re.compile(r'(?<![\w\\-])('+'|'.join(map(re.escape,sorted(terms,key=len,reverse=True)))+r')(?![\w-])')
for p in ROOT.glob('*.tex'):
    if p.name in {'main.tex','Bia.tex','TaiLieuThamKhao.tex','LoiCamDoan.tex','Glossary.tex','Abbreviations.tex'}:
        continue
    parts=protected.split(p.read_text(encoding='utf-8'))
    parts=[s if i%2 else pattern.sub(lambda m:terms[m.group()],s) for i,s in enumerate(parts)]
    p.write_text(''.join(parts),encoding='utf-8')

# Specific editorial refinements after terminology normalization.
refinements={
    'Chuong1.tex':[
        ('SORT đã chứng minh một chuỗi xử lý theo dõi trực tuyến có thể đạt tốc độ cao bằng Kalman filter và Hungarian assignment \\cite{sort}, Deep SORT',
         'SORT kết hợp bộ lọc Kalman và thuật toán gán Hungarian để theo dõi trực tuyến \\cite{sort}. Deep SORT'),
        ('\\cite{deepsort}, ByteTrack','\\cite{deepsort}. ByteTrack'),
        ('khung hình có cell phone thì nhân viên đang dùng điện thoại','phát hiện điện thoại trong khung hình đồng nghĩa với việc nhân viên đang sử dụng điện thoại'),
        ('chỉ phần vượt hạn mức mới tham gia phép điều chỉnh','trong đó chỉ phần vượt hạn mức mới tham gia phép điều chỉnh'),
    ],
    'Chuong2.tex':[
        ('Lớp \\textit{cell điện thoại}', 'Lớp \\textit{cell phone}'),
        ('Trạng thái danh tính', 'Trạng thái danh tính'),
        ('Ngưỡng không nên lấy cố định từ một nghiên cứu khác','Ngưỡng xác minh cần được hiệu chỉnh cho dữ liệu mục tiêu và không nên áp dụng trực tiếp từ một nghiên cứu khác'),
    ],
    'Chuong6.tex':[
        ('Một cấu hình tốt không nhất thiết có chỉ số tốt nhất tuyệt đối trên xác thực. Nên ưu tiên vùng plateau:',
         'Việc lựa chọn cấu hình cần xem xét cả độ ổn định trên tập xác thực. Có thể ưu tiên vùng tham số mà'),
        ('giá trị số thập phân','giá trị số thập phân'),
    ],
}
for name,pairs in refinements.items():
    p=ROOT/name
    t=p.read_text(encoding='utf-8')
    for old,new in pairs:
        t=t.replace(old,new)
    p.write_text(t,encoding='utf-8')

for p in ROOT.glob('*.tex'):
    if p.name in {'main.tex','Bia.tex','TaiLieuThamKhao.tex','LoiCamDoan.tex'}:
        continue
    t=p.read_text(encoding='utf-8').replace('cell điện thoại','cell phone')
    t=t.replace('\\textit{người}', '\\textit{person}')
    p.write_text(t,encoding='utf-8')

p=ROOT/'TaiLieuThamKhao.tex'
t=p.read_text(encoding='utf-8').replace('https://vbpl.moj.gov.vn/bocongan/Pages/vbpq-thuoctinh.aspx?ItemID=179252',
                                     'https://congbao.chinhphu.vn/van-ban/luat-so-91-2025-qh15-45578.htm')
t=t.replace('Cơ sở dữ liệu quốc gia về văn bản pháp luật. Available:', 'Công báo điện tử Chính phủ. Available:')
p.write_text(t,encoding='utf-8')
print('Quantitative sections replaced and terminology refined.')
