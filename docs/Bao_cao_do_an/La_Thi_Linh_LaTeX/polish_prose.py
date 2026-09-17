from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
protected=re.compile(r'(\\begin\{(?:Verbatim|verbatim|tikzpicture|equation|align)\}.*?\\end\{(?:Verbatim|verbatim|tikzpicture|equation|align)\}|\$[^$]*\$|\\(?:texttt|url|label|ref|cite|input)\{[^}]*\}|\\includegraphics(?:\[[^]]*\])?\{[^}]*\})',re.S)
phrases={
    'điện thoại máy trạng thái':'máy trạng thái điện thoại',
    'Điện thoại máy trạng thái':'Máy trạng thái điện thoại',
    'hiện diện máy trạng thái':'máy trạng thái hiện diện',
    'temporal máy trạng thái':'máy trạng thái theo thời gian',
    'temporal trạng thái':'trạng thái theo thời gian',
    'trạng thái parameters':'tham số trạng thái',
    'Điện thoại nhãn tham chiếu cũng là khoảng thời gian.':'Nhãn tham chiếu sử dụng điện thoại cũng được biểu diễn bằng các khoảng thời gian.',
    'mã quỹ đạo tạm thời':'mã quỹ đạo tạm thời',
    'Phone nhãn tham chiếu':'Nhãn tham chiếu điện thoại',
    'hiện diện candidate':'ứng viên hiện diện',
    'Điện thoại owner':'Người sử dụng điện thoại',
    'điện thoại owner':'người sử dụng điện thoại',
    'không phần vượt hạn mức':'không phát sinh phần vượt hạn mức',
    'Không phần vượt hạn mức':'Không phát sinh phần vượt hạn mức',
    'bằng chứng permission':'quyền truy cập bằng chứng',
    'báo cáo job':'tác vụ báo cáo','Báo cáo job':'Tác vụ báo cáo',
    'phiên ID':'mã phiên','sự kiện ID':'mã sự kiện',
    'Sự kiện ID':'Mã sự kiện','camera ID':'mã camera',
    'Camera ID':'Mã camera','organization ID':'mã tổ chức',
    'SQL current':'SQL lưu trạng thái hiện tại',
    'timestamp đồng hồ thời gian thực':'mốc thời gian thực',
    'Monotonic time':'Thời gian đơn điệu','monotonic time':'thời gian đơn điệu',
    'temporal processing':'xử lý theo thời gian','temporal confirmation':'xác nhận theo thời gian',
    'temporal validation':'xác thực theo thời gian',
    'frame boundary':'ranh giới khung hình','khung hình boundary':'ranh giới khung hình',
    'session boundary':'ranh giới phiên','phiên boundary':'ranh giới phiên',
    'quỹ đạo buffer':'bộ đệm quỹ đạo','bộ theo dõi buffer':'bộ đệm của bộ theo dõi',
    'ảnh chụp current-state':'bản chụp trạng thái hiện tại',
    'ảnh chụp trạng thái':'bản chụp trạng thái',
    'raw biometric/bằng chứng':'dữ liệu sinh trắc học gốc và bằng chứng',
    'raw embedding':'vector đặc trưng gốc','raw sinh trắc học':'dữ liệu sinh trắc học gốc',
    'FaceNet embedding':'vector đặc trưng FaceNet',
    'MTCNN crop':'cắt vùng mặt bằng MTCNN',
    'face data':'dữ liệu khuôn mặt','face reference':'mẫu khuôn mặt tham chiếu',
    'face enrollment':'đăng ký khuôn mặt','face detector':'bộ phát hiện khuôn mặt',
    'person ReID':'tái định danh người','người ReID':'tái định danh người',
    'appearance ReID':'tái định danh dựa trên ngoại hình',
    're-identification':'tái định danh',
    'interaction region':'vùng tương tác','Interaction region':'Vùng tương tác',
    'upper-body region':'vùng thân trên',
    'pose/hand-object interaction':'ước lượng tư thế và tương tác tay--vật thể',
    'Pose/hand-object interaction':'Ước lượng tư thế và tương tác tay--vật thể',
    'pose/hand interaction':'ước lượng tư thế và tương tác bàn tay',
    'hand-object interaction':'tương tác tay--vật thể',
    'edge inference':'suy luận tại thiết bị biên','edge processing':'xử lý tại thiết bị biên',
    'edge client':'ứng dụng tại thiết bị biên','camera client':'ứng dụng camera',
    'Camera client':'Ứng dụng camera','camera token':'mã xác thực camera',
    'Camera token':'Mã xác thực camera',
    'tenant isolation':'cô lập dữ liệu giữa các tổ chức',
    'Tenant isolation':'Cô lập dữ liệu giữa các tổ chức',
    'tenant filter':'bộ lọc tổ chức','Tenant filter':'Bộ lọc tổ chức',
    'Organization Admin':'quản trị viên tổ chức','System Admin':'quản trị viên hệ thống',
    'Supervisor':'người giám sát','Camera Client':'ứng dụng camera',
    'snapshot cursor':'con trỏ của bản chụp trạng thái',
    'bản tổng hợp coverage':'độ bao phủ của bản tổng hợp',
    'state delta':'phần thay đổi trạng thái','trạng thái delta':'phần thay đổi trạng thái',
    'current-state update':'cập nhật trạng thái hiện tại',
    'schema version':'phiên bản lược đồ','major version':'phiên bản chính',
    'major schema':'phiên bản chính của lược đồ','schema phiên bản':'lược đồ có phiên bản',
    'model format':'định dạng mô hình','input size':'kích thước đầu vào',
    'weight checksum':'mã kiểm tra trọng số','client version':'phiên bản ứng dụng phía camera',
    'ROI/danh tính error':'sai số liên kết vùng và danh tính',
    'duration MAE':'MAE thời lượng','phone-duration MAE':'MAE thời lượng điện thoại',
    'Quan sát phát hiện F1':'F1 phát hiện đối tượng',
    'Hiện diện F1':'F1 hiện diện','hiện diện F1':'F1 hiện diện',
    'Entry/exit error':'Sai số mốc vào và ra','entry/exit error':'sai số mốc vào và ra',
    'Entry/exit':'Mốc vào và ra','entry/exit':'mốc vào và ra',
    'entry error':'sai số mốc vào','exit error':'sai số mốc ra',
    'Phone-use F1':'F1 sử dụng điện thoại','phone-use F1':'F1 sử dụng điện thoại',
    'ngưỡng temporal':'ngưỡng thời gian','tham số temporal':'tham số thời gian',
    'sample record':'bản ghi mẫu','mẫu record':'bản ghi mẫu',
    'sample size':'cỡ mẫu','cỡ mẫu được ghi':'cỡ mẫu đã được ghi nhận',
    'mapping người sử dụng điện thoại':'ánh xạ điện thoại với người sử dụng',
    'false-present duration':'thời lượng hiện diện giả','false-absent duration':'thời lượng vắng mặt giả',
    'false-present/false-absent duration':'thời lượng hiện diện giả và vắng mặt giả',
    'phone-duration':'thời lượng điện thoại','session classification':'phân loại phiên',
    'trạng thái tracked/lost':'trạng thái đang theo dõi hoặc tạm mất dấu',
    'bị lost':'bị mất dấu','chuyển lost':'chuyển sang trạng thái mất dấu',
    'person+phone':'người và điện thoại','người+phone':'người và điện thoại',
    'Person và cell phone':'Người và điện thoại',
    'Cell điện thoại':'Điện thoại','Cell phone':'Điện thoại',
    'cell phone':'điện thoại',
    'Multi-object theo dõi':'Theo dõi đa đối tượng',
    'Phone Usage':'Sử dụng điện thoại','Điện thoại Usage':'Sử dụng điện thoại',
    'Workplace Context':'Ngữ cảnh khu vực làm việc',
    'Work-time Aggregation':'Tổng hợp thời gian làm việc',
    'Backend Platform':'Nền tảng dịch vụ','Perception':'Nhận thức',
    'Computer Vision':'Thị giác máy tính','computer vision':'thị giác máy tính',
    'Reporting':'Sinh báo cáo',
    'network jitter':'dao động độ trễ mạng','configuration mismatch':'sai khác cấu hình',
    'confidence cao':'độ tin cậy cao','confidence thấp':'độ tin cậy thấp',
    'quan sát phát hiện điểm liên kết thấp':'quan sát phát hiện có độ tin cậy thấp',
    'box điểm liên kết thấp':'hộp bao có độ tin cậy thấp',
    'hộp bao điểm liên kết thấp':'hộp bao có độ tin cậy thấp',
    'hộp bao điểm liên kết cao':'hộp bao có độ tin cậy cao',
    'camera góc mạnh':'camera có góc nhìn nghiêng lớn','góc camera mạnh':'góc nhìn camera nghiêng lớn',
    'privacy impact':'tác động đối với quyền riêng tư',
    'người gán nhãn bất đồng quá tolerance':'người gán nhãn bất đồng vượt dung sai',
    'hai người gán nhãn bất đồng quá tolerance':'hai người gán nhãn bất đồng vượt dung sai',
    'tập ``train``':'tập huấn luyện',
    '60\\% train/hiệu chỉnh, 20\\% xác thực, 20\\% test':'60\\% huấn luyện hoặc hiệu chỉnh, 20\\% xác thực và 20\\% kiểm tra',
}
terms={
    'timestamp':'mốc thời gian','timestamps':'các mốc thời gian',
    'polygon':'đa giác','Polygon':'Đa giác',
    'duration':'thời lượng','Duration':'Thời lượng',
    'association':'liên kết','Association':'Liên kết',
    'assignment':'phân công','Assignment':'Phân công',
    'embedding':'vector đặc trưng','embeddings':'các vector đặc trưng',
    'inference':'suy luận','Inference':'Suy luận',
    'queue':'hàng đợi','Queue':'Hàng đợi',
    'client':'ứng dụng phía máy khách','Client':'Ứng dụng phía máy khách',
    'server':'máy chủ','Server':'Máy chủ',
    'sequence':'số thứ tự','Sequence':'Số thứ tự',
    'schema':'lược đồ','Schema':'Lược đồ',
    'coverage':'độ bao phủ','Coverage':'Độ bao phủ',
    'context':'ngữ cảnh','Context':'Ngữ cảnh',
    'margin':'biên chênh lệch','version':'phiên bản',
    'bias':'sai lệch có hệ thống','anchor':'điểm neo',
    'area':'vùng','Area':'Vùng',
    'owner':'người sử dụng','Owner':'Người sử dụng',
    'geometry':'hình học','Geometry':'Hình học',
    'reconnect':'kết nối lại','retry':'gửi lại','Retry':'Gửi lại',
    'timeout':'thời gian chờ','Timeout':'Thời gian chờ',
    'unobserved':'không quan sát được',
    'active':'đang hoạt động','permission':'quyền truy cập',
    'permissions':'các quyền truy cập',
    'audit':'kiểm toán','Audit':'Kiểm toán',
    'log':'nhật ký','Log':'Nhật ký',
    'resource':'tài nguyên','Resource':'Tài nguyên',
    'module':'mô-đun','Module':'Mô-đun',
    'process':'tiến trình','thread':'luồng',
    'worker':'tiến trình xử lý nền','Worker':'Tiến trình xử lý nền',
    'resolution':'độ phân giải','resize':'đổi kích thước',
    'scale':'co giãn','crop':'cắt vùng ảnh','Crop':'Cắt vùng ảnh',
    'appearance':'ngoại hình','temporal':'theo thời gian',
    'train':'huấn luyện','test':'kiểm tra','Test':'Kiểm tra',
    'subset':'tập con','split':'phân hoạch','leakage':'rò rỉ dữ liệu',
    'metadata':'siêu dữ liệu','agreement':'mức đồng thuận',
    'Agreement':'Mức đồng thuận','tolerance':'dung sai',
    'deterministic':'có tính xác định','deterministically':'theo cách xác định',
    'normalize':'chuẩn hóa','merge':'hợp nhất','rebuild':'tái dựng',
    'recompute':'tính lại','reconcile':'đối soát','replay':'phát lại',
    'benchmark':'đo kiểm hiệu năng','Benchmark':'Đo kiểm hiệu năng',
    'containment':'mức bao chứa','outlier':'mẫu ngoại lệ',
    'baseline':'phương pháp cơ sở','proposed':'phương pháp đề xuất',
    'realtime':'thời gian thực','effective':'hiệu lực',
}

ph=re.compile('|'.join(map(re.escape,sorted(phrases,key=len,reverse=True))))
words=re.compile(r'(?<![\w\\-])('+'|'.join(map(re.escape,sorted(terms,key=len,reverse=True)))+r')(?![\w-])')

def polish(s):
    s=ph.sub(lambda m:phrases[m.group()],s)
    return words.sub(lambda m:terms[m.group()],s)

for p in ROOT.glob('*.tex'):
    if p.name in {'main.tex','Bia.tex','TaiLieuThamKhao.tex','LoiCamDoan.tex','Glossary.tex','Abbreviations.tex'}:
        continue
    parts=protected.split(p.read_text(encoding='utf-8'))
    t=''.join(s if i%2 else polish(s) for i,s in enumerate(parts))
    t=t.replace('\\textit{điện thoại}','\\textit{cell phone}')
    # Heading capitalization after replacing technical phrases.
    t=re.sub(r'(\\(?:subsection|subsubsection)\{)([^}])',lambda m:m[1]+m[2].upper(),t)
    p.write_text(t,encoding='utf-8')

# Rewrite passages whose argument needs more than terminology replacement.
def paragraph(file, starts, new):
    p=ROOT/file
    t=p.read_text(encoding='utf-8')
    start=t.index(starts)
    end=t.find('\n\n',start)
    if end<0: end=len(t)
    p.write_text(t[:start]+new+t[end:],encoding='utf-8')

paragraph('Chuong4.tex','Kiến trúc gồm các miền chính:',
          'Kiến trúc gồm các mô-đun nhận thức, theo dõi, ngữ cảnh khu vực làm việc, hiện diện, sử dụng điện thoại, tổng hợp thời gian, dịch vụ máy chủ và báo cáo. Mỗi mô-đun có hợp đồng đầu vào và đầu ra để hỗ trợ kiểm thử độc lập.')
paragraph('Chuong6.tex','Nếu có đủ video, chia theo phiên quay',
          'Dữ liệu cần được chia theo phiên quay để hạn chế rò rỉ thông tin giữa các tập. Có thể dành 60\\% số phiên cho huấn luyện hoặc hiệu chỉnh, 20\\% cho xác thực và 20\\% cho kiểm tra khi quy mô thu thập cho phép. Nếu không tinh chỉnh trọng số mô hình, phần huấn luyện được sử dụng để xây dựng và khảo sát cấu hình. Tập kiểm tra phải được giữ độc lập và chỉ được sử dụng sau khi khóa cấu hình.')
paragraph('Chuong7.tex','Thay vì cộng số khung hình, hệ thống dùng',
          'Thời lượng được tính từ các mốc thời gian và khoảng hiện diện thay vì số khung hình. Khoảng đệm hạn chế ảnh hưởng của lỗi bỏ sót ngắn. Khi xác nhận trạng thái, đầu và cuối khoảng được truy hồi về mốc bắt đầu ứng viên và mốc quan sát tin cậy cuối cùng. Cách tổ chức này giảm sai lệch do thời gian chờ xác nhận và giữ ý nghĩa tham số khi tốc độ xử lý thay đổi.')
paragraph('Chuong7.tex','Auth, cô lập dữ liệu',
          'Thiết kế nền tảng kết hợp xác thực, phân quyền theo tổ chức, vé kết nối WebSocket, nhật ký kiểm toán, kiểm soát truy cập bằng chứng và tác vụ báo cáo. Dữ liệu sinh trắc học và hình ảnh được tách khỏi dữ liệu thời lượng phục vụ bảng điều khiển. Thời hạn lưu trữ và quyền truy cập được xác định theo từng nhóm dữ liệu \\cite{vnprivacy}.')
paragraph('Chuong7.tex','Vùng tương tác + trạng thái theo thời gian',
          'Quan hệ không gian và điều kiện thời gian chỉ cung cấp dấu hiệu gián tiếp về hành vi sử dụng điện thoại. Điện thoại đặt gần người hoặc được chuyển giữa hai người vẫn có thể gây nhầm lẫn. Ước lượng tư thế và tương tác tay--vật thể là hướng mở rộng cần được đánh giá bằng dữ liệu phù hợp.')

p=ROOT/'Chuong6.tex'
t=p.read_text(encoding='utf-8')
start=t.index('\\begin{enumerate}',t.index('\\subsection{Phương pháp so sánh}'))
end=t.index('\\input{generated/synthetic_results}',start)
t=t[:start]+r'''\begin{enumerate}
\item \textbf{Phương pháp cơ sở A -- Khung hình và ROI}: áp dụng YOLO độc lập trên từng khung hình, xác định hiện diện khi có điểm neo người trong vùng.
\item \textbf{Phương pháp cơ sở B -- YOLO, ByteTrack và ROI}: bổ sung theo dõi đối tượng nhưng chưa dùng máy trạng thái theo thời gian hoặc xác minh danh tính.
\item \textbf{Phương pháp đề xuất}: bổ sung xác minh danh tính, máy trạng thái hiện diện, liên kết điện thoại và máy trạng thái sử dụng điện thoại.
\end{enumerate}
Các phương pháp cần chạy trên cùng video và cùng cấu hình bộ phát hiện để phân tích đóng góp của theo dõi và xử lý theo thời gian. Bộ số liệu tổng hợp ở phần tiếp theo chỉ kiểm tra cách tính chỉ số, không phải kết quả chạy ba phương pháp này.

'''+t[end:]
p.write_text(t,encoding='utf-8')

paragraph('TomTat.tex','Để minh họa cấu trúc đánh giá',
          'Báo cáo kèm bộ dữ liệu tổng hợp gồm số đếm phân loại, 12 phiên điện thoại và 30 ca có các mức nhiễu khác nhau. Chương trình sinh dữ liệu tính lại các chỉ số và tạo bảng, biểu đồ từ cùng một nguồn. Kết quả hỗ trợ kiểm tra công thức, tính nhất quán số học và cách trình bày đánh giá. Bộ dữ liệu chưa được hiệu chỉnh theo quan sát thực địa, do đó không được sử dụng để xác nhận độ chính xác hoặc hiệu năng triển khai. Quy trình thực nghiệm trên video có nhãn tham chiếu được trình bày để kiểm chứng giải pháp ở bước tiếp theo.')
paragraph('MoDau.tex','Báo cáo trình bày từ cơ sở lý thuyết',
          'Báo cáo trình bày cơ sở lý thuyết, khảo sát yêu cầu, thiết kế hệ thống, phương án cài đặt và quy trình đánh giá. Chương 6 sử dụng dữ liệu tổng hợp có thể tái tạo để kiểm tra phép tính chỉ số và các ràng buộc thời lượng. Kết quả tính toán được phân biệt với thực nghiệm trên camera, vốn cần video có nhãn tham chiếu độc lập và thông tin cấu hình đầy đủ.')
print('Prose polished.')
