from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
protected=re.compile(r'(\\begin\{(?:Verbatim|verbatim|tikzpicture|equation|align)\}.*?\\end\{(?:Verbatim|verbatim|tikzpicture|equation|align)\}|\$[^$]*\$|\\(?:texttt|url|label|ref|cite|input)\{[^}]*\}|\\includegraphics(?:\[[^]]*\])?\{[^}]*\})',re.S)
replacements={
 'hành vi sử dụng điện thoại F1':'F1 sử dụng điện thoại',
 'chỉ số quan sát phát hiện':'chỉ số phát hiện đối tượng',
 'chất lượng quan sát phát hiện':'chất lượng phát hiện đối tượng',
 'mô hình quan sát phát hiện':'mô hình phát hiện đối tượng',
 'đánh giá quan sát phát hiện':'đánh giá phát hiện đối tượng',
 'Object quan sát phát hiện':'Phát hiện đối tượng',
 'Multi-Object Theo dõi':'Theo dõi đa đối tượng',
 'tracking-by-detection':'theo dõi dựa trên phát hiện đối tượng',
 'phone--person':'người--điện thoại','người--track--nhân viên':'người--quỹ đạo--nhân viên',
 'detection--track--ROI--identity':'phát hiện--quỹ đạo--ROI--danh tính',
 'giảm lần đổi định danh':'giảm số lần đổi định danh',
 'không loại bỏ hoàn toàn lần đổi định danh':'không loại bỏ hoàn toàn hiện tượng đổi định danh',
 'vector đặc trưng FaceNet là':'Vector đặc trưng FaceNet là',
 'Re-identification':'Tái định danh',
 'class label':'nhãn lớp','class probability':'xác suất lớp',
 'Kalman filter':'bộ lọc Kalman','Hungarian algorithm':'thuật toán Hungarian',
 'phân công tối ưu':'phép gán tối ưu',
 'điểm liên kết cao nhất được giữ':'độ tin cậy cao nhất được giữ',
 'quan sát phát hiện điểm liên kết cao':'quan sát phát hiện có độ tin cậy cao',
 'quan sát phát hiện có điểm liên kết thấp':'quan sát phát hiện có độ tin cậy thấp',
 'quan sát phát hiện độ tin cậy cao':'quan sát phát hiện có độ tin cậy cao',
 'các quan sát phát hiện thấp hơn':'các quan sát có độ tin cậy thấp hơn',
 'Những hộp bao thấp':'Những hộp bao có độ tin cậy thấp',
 'background':'nền ảnh','rectangle':'hình chữ nhật',
 'bottom-center':'điểm giữa cạnh đáy hộp bao',
 'hộp bao overlap':'phần giao giữa các hộp bao',
 'video analytics':'phân tích video','Computer vision':'Thị giác máy tính',
 'Wrong-Person Liên kết Rate':'Wrong-Person Association Rate (WPAR)',
 'Điện thoại quan sát phát hiện đúng':'Điện thoại được phát hiện đúng',
 'UNKNOWN rate':'tỉ lệ UNKNOWN','false thời lượng':'thời lượng phân loại sai',
 'Sự kiện loss':'Tỉ lệ mất sự kiện','duplicate rate':'tỉ lệ trùng lặp',
 'false match':'xác minh nhầm','false absence segment':'đoạn vắng mặt giả',
 'Phone F1':'F1 sử dụng điện thoại','phone F1':'F1 sử dụng điện thoại',
 'Person cần ưu tiên recall':'Phát hiện người cần ưu tiên Recall',
 'Thời hạn lưu trữ chính sách':'Chính sách lưu trữ',
 'khoảng thời gian ID':'mã khoảng thời gian',
 'Phiên ID':'Mã phiên','candidate start':'mốc bắt đầu ứng viên',
 'candidate persons':'các quỹ đạo người ứng viên',
 'candidate đầu tiên':'ứng viên đầu tiên',
 'phiên start':'mốc bắt đầu phiên','last associated':'mốc liên kết cuối cùng',
 'start truy hồi mốc':'mốc bắt đầu được truy hồi',
 'end truy hồi mốc':'mốc kết thúc được truy hồi',
 'Score distance':'Điểm khoảng cách','center điện thoại':'tâm hộp bao điện thoại',
 'tất cả pair':'tất cả các cặp','phân công một-một':'phép gán một-một',
 'debug counter':'bộ đếm chẩn đoán',
 'chuyển trạng thái payload':'nội dung chuyển trạng thái',
 'Observation gồm':'Quan sát đầu vào gồm',
 'suy luận độ trễ':'độ trễ suy luận','ACK độ trễ':'độ trễ xác nhận ACK',
 'database độ trễ':'độ trễ cơ sở dữ liệu','báo cáo thời lượng':'thời lượng tạo báo cáo',
 'khung hình age':'tuổi khung hình','hàng đợi age':'thời gian lưu trong hàng đợi',
 'hàng đợi depth':'độ dài hàng đợi','đang hoạt động tracks':'số quỹ đạo đang hoạt động',
 'capture FPS':'FPS thu nhận','suy luận FPS':'FPS suy luận','processed FPS':'FPS xử lý',
 'sự kiện delivery':'truyền sự kiện','Sự kiện delivery':'Truyền sự kiện',
 'materializer lag':'độ trễ cập nhật dữ liệu dẫn xuất',
 'WebSocket consumer lag':'độ trễ nhận dữ liệu WebSocket',
 'bằng chứng storage':'kho bằng chứng','Active quỹ đạo':'Số quỹ đạo hoạt động',
 'offline hàng đợi':'hàng đợi ngoại tuyến','Offline hàng đợi':'Hàng đợi ngoại tuyến',
 'offline sự kiện hàng đợi':'hàng đợi sự kiện ngoại tuyến',
 'trạng thái ngưỡng':'ngưỡng trạng thái','danh tính ngưỡng':'ngưỡng xác minh danh tính',
 'liên kết biên chênh lệch':'biên chênh lệch liên kết',
 'Danh tính độ bao phủ':'Độ bao phủ xác minh danh tính',
 'hiện diện MAE':'MAE hiện diện','điện thoại MAE':'MAE điện thoại',
 'theo thời gian IoU':'IoU theo thời gian',
 'phương pháp phương pháp cơ sở/phương pháp đề xuất':'cấu hình cơ sở và đề xuất',
 'CSV các chỉ số':'tệp CSV chứa các chỉ số',
 'ROI boundary':'biên vùng ROI','điện thoại size':'kích thước điện thoại',
 'che khuất attribute':'thuộc tính che khuất','gắn attribute':'gắn thuộc tính',
 'UNKNOWN khoảng thời gian':'Khoảng thời gian UNKNOWN',
 'Không hành vi sử dụng điện thoại':'Không sử dụng điện thoại',
 'Wrong nhân viên khoảng thời gian':'Khoảng thời gian gán sai nhân viên',
 'Nearest điện thoại':'Liên kết điện thoại theo người gần nhất',
 'Khung hình-only':'Chỉ dùng khung hình',
 'False-absent sec':'Số giây vắng mặt giả',
 'Backdating giảm':'Truy hồi mốc giảm','Margin giảm':'Biên chênh lệch giảm',
 'miss ngắn':'bỏ sót ngắn','miss kéo dài':'bỏ sót kéo dài',
 'Thời lượng error':'Sai số thời lượng','median absolute error':'trung vị sai số tuyệt đối',
 'paired difference':'chênh lệch theo cặp',
 'Đo kiểm hiệu năng hiệu năng':'Đo kiểm hiệu năng',
 'P95 độ trễ':'độ trễ P95','khung hình drop':'số khung hình bị bỏ',
 'mô hình format':'định dạng mô hình','suy luận độ phân giải':'độ phân giải suy luận',
 'Stress kiểm tra':'Kiểm thử tải','Soak kiểm tra':'Kiểm thử độ ổn định',
 'request độ trễ':'độ trễ yêu cầu','sự kiện throughput':'thông lượng sự kiện',
 'WebSocket delivery':'thời gian truyền WebSocket',
 'Fault injection':'Đưa lỗi có chủ đích','fault injection':'đưa lỗi có chủ đích',
 'RTSP thời gian chờ':'hết thời gian chờ RTSP','duplicate sự kiện':'sự kiện trùng',
 'sự kiện count':'số sự kiện','unique mã sự kiện':'số mã sự kiện duy nhất',
 'số thứ tự gap':'khoảng thiếu số thứ tự','Camera sự kiện':'Sự kiện camera',
 'Gửi lại count':'Số lần gửi lại','Error mã chương trình':'Mã lỗi',
 'sự kiện error':'lỗi sự kiện','khoảng thời gian aggregation':'tổng hợp khoảng thời gian',
 'giữ nguyên timestamp':'giữ nguyên mốc thời gian',
 'CORS/HTTPS chính sách':'chính sách CORS và HTTPS',
 'sampling chính sách':'chính sách lấy mẫu','sampling khung hình':'lấy mẫu khung hình',
 'Capture luồng':'Luồng thu nhận','Suy luận tiến trình xử lý nền':'Tiến trình suy luận',
 'Dispatch tiến trình xử lý nền':'Tiến trình truyền dữ liệu',
 'configuration error':'lỗi cấu hình','data error':'lỗi dữ liệu',
 'raw dữ liệu':'dữ liệu gốc',
 'Model chứa':'Cấu hình mô hình chứa',
 'chính sách ngưỡng':'ngưỡng theo chính sách',
 'state transition':'chuyển trạng thái',
 'ảnh chụp chỉ tải':'ảnh bằng chứng chỉ tải',
 'máy chủ commit':'máy chủ hoàn tất giao dịch',
 'Buffer/đối soát':'Bộ đệm và đối soát',
 'Outage, kết nối lại':'Ghi gián đoạn và kết nối lại',
 'Rebuild trạng thái hiện tại':'Tái dựng trạng thái hiện tại',
 'không ép absent':'không kết luận vắng mặt',
 'absent chắc chắn':'vắng mặt chắc chắn',
 'Flag hậu kiểm':'Đánh dấu hậu kiểm',
 'có thể thay bằng trọng số':'có thể sử dụng trọng số',
}
words={
 'weight':'bộ trọng số','weights':'các bộ trọng số',
 'job':'tác vụ','jobs':'các tác vụ','restart':'khởi động lại',
 'offline':'mất kết nối','upload':'tải lên','portal':'cổng thông tin',
 'timeline':'dòng thời gian','Timeline':'Dòng thời gian',
 'taxonomy':'phân loại nguyên nhân','Taxonomy':'Phân loại nguyên nhân',
 'fragmentation':'mức phân mảnh','Fragmentation':'Mức phân mảnh',
 'percentile':'phân vị','Median':'Trung vị','median':'trung vị','mean':'trung bình',
 'vs.':'so với','max':'lớn nhất','min':'nhỏ nhất',
 'protocol':'quy trình đánh giá','oracle':'kết quả tham chiếu',
 'warm-up':'khởi động và chạy ổn định','decode':'giải mã',
 'preprocess':'tiền xử lý','postprocess':'hậu xử lý','network':'mạng',
 'capture':'thu nhận','dispatch':'truyền dữ liệu','transport':'truyền dữ liệu',
 'reset':'khởi tạo lại','revision':'bản sửa đổi','crash':'dừng đột ngột',
 'uncertain':'không chắc chắn','default':'giá trị mặc định',
 'role':'vai trò','instance':'đối tượng được gán nhãn',
 'observability':'khả năng quan sát','guard':'điều kiện bảo vệ',
 'centroid':'vector trung tâm','label':'nhãn','click':'nhấp chuột',
 'text/icon':'văn bản và biểu tượng','flag':'cờ trạng thái',
 'boolean':'giá trị logic','Boolean':'Giá trị logic',
}
ph=re.compile('|'.join(map(re.escape,sorted(replacements,key=len,reverse=True))))
wd=re.compile(r'(?<![\w\\-])('+'|'.join(map(re.escape,sorted(words,key=len,reverse=True)))+r')(?![\w-])')
for p in ROOT.glob('*.tex'):
    if p.name in {'main.tex','Bia.tex','TaiLieuThamKhao.tex','LoiCamDoan.tex','Glossary.tex','Abbreviations.tex'}:
        continue
    parts=protected.split(p.read_text(encoding='utf-8'))
    parts=[s if i%2 else wd.sub(lambda m:words[m.group()],ph.sub(lambda m:replacements[m.group()],s)) for i,s in enumerate(parts)]
    p.write_text(''.join(parts),encoding='utf-8')

def paragraph(file,starts,new):
    p=ROOT/file
    t=p.read_text(encoding='utf-8')
    a=t.index(starts)
    b=t.find('\n\n',a)
    if b<0:b=len(t)
    p.write_text(t[:a]+new+t[b:],encoding='utf-8')

paragraph('Chuong2.tex','YOLOv8 do Ultralytics phát hành năm 2023.',
          'YOLOv8 do Ultralytics phát hành năm 2023, gồm các biến thể phục vụ phát hiện đối tượng, phân đoạn ảnh, ước lượng tư thế, phát hiện hộp bao định hướng và phân loại ảnh. Các bộ trọng số phát hiện tiêu chuẩn được huấn luyện trên COCO với 80 lớp \\cite{ultralyticsv8}. Báo cáo sử dụng tài liệu phần mềm Ultralytics làm nguồn mô tả YOLOv8 vì nhóm phát triển chưa công bố bài báo học thuật riêng cho phiên bản này.')
paragraph('Chuong4.tex','Hệ thống được thiết kế theo hướng phân tách',
          'Hệ thống phân tách xử lý thị giác tại thiết bị biên và quản trị dữ liệu tại máy chủ. Ứng dụng camera thu nhận luồng CCTV, phát hiện và theo dõi đối tượng, liên kết vùng, hỗ trợ xác minh danh tính và cập nhật máy trạng thái. Máy chủ chỉ nhận dữ liệu trạng thái có cấu trúc, sự kiện và ảnh bằng chứng cần thiết. Cách tổ chức này giảm băng thông so với truyền video liên tục và cho phép ghi nhận sự kiện cục bộ khi mạng gián đoạn.')
paragraph('Chuong5.tex','Với mỗi điện thoại, hàm tạo',
          'Với mỗi hộp bao điện thoại, thuật toán xây dựng danh sách quỹ đạo người ứng viên trong vùng tương tác. Điểm liên kết kết hợp khoảng cách tâm chuẩn hóa, mức bao chứa và tính nhất quán với vùng ROI. Các cặp được xét theo điểm giảm dần, đồng thời kiểm tra xung đột để mỗi điện thoại chỉ gắn với một người. Khi nhiều ứng viên có điểm gần nhau, kết quả được giữ ở trạng thái chưa xác định. Phương án tham lam này cần được so sánh với phép gán tối ưu khi số đối tượng tăng.')
paragraph('Chuong5.tex','API tương tự hiện diện.',
          'Giao diện cập nhật có cấu trúc tương tự máy trạng thái hiện diện. Khi xác nhận USING, mốc bắt đầu phiên được truy hồi về thời điểm xuất hiện ứng viên. Khi hết khoảng đệm GRACE, mốc kết thúc được truy hồi về lần liên kết tin cậy cuối cùng. Phiên ngắn hơn \\texttt{min\\_session\\_seconds} có thể được loại khỏi phần tổng hợp theo chính sách nhưng vẫn được ghi vào bộ đếm chẩn đoán.')
paragraph('Chuong6.tex','Trung vị và phân vị hữu ích bên cạnh trung bình.',
          'Ngoài giá trị trung bình, cần báo cáo trung vị và các phân vị của sai số tuyệt đối. Một số ca có sai số lớn có thể làm tăng MAE đáng kể, trong khi trung vị phản ánh rõ hơn mức sai số của ca điển hình. Các chỉ số nên gồm MAE, trung vị sai số tuyệt đối, P90, P95 và giá trị lớn nhất, kèm phân tích các mẫu ngoại lệ.')
paragraph('Chuong6.tex','Đo kiểm hiệu năng cần',
          'Đo kiểm hiệu năng cần khởi động mô hình và chạy ổn định trước khi ghi nhận thời gian. Các thành phần được đo riêng gồm giải mã, tiền xử lý, suy luận, hậu xử lý, theo dõi, xử lý ngữ cảnh và truyền dữ liệu. Báo cáo cần nêu trung vị, độ trễ P95, FPS hiệu dụng và tỉ lệ khung hình bị bỏ trong cùng một cửa sổ đo.')
paragraph('Chuong6.tex','Phần cứng, driver, thư viện',
          'Thông tin phần cứng, trình điều khiển, phiên bản thư viện, định dạng mô hình, kích thước đầu vào, kích thước lô và độ chính xác số học phải được lưu cùng kết quả. Khi so sánh CPU và GPU, các cấu hình phải xử lý cùng chuỗi video. Nếu có lấy mẫu khung hình, FPS thu nhận và FPS xử lý được báo cáo riêng.')
paragraph('Chuong6.tex','Sau mỗi kiểm tra, so sánh',
          'Sau mỗi phép thử, cần đối chiếu số sự kiện, số mã duy nhất, khoảng thiếu số thứ tự, các khoảng thời gian và bản tổng hợp với kết quả tham chiếu. Phép thử chỉ được xác nhận đạt khi hệ thống phục hồi trong thời gian quy định và dữ liệu cuối cùng nhất quán. Thông báo phục hồi trong nhật ký chưa đủ để xác nhận tính đúng đắn.')
paragraph('Chuong6.tex','Chỉ số cho biết mức độ',
          'Chỉ số định lượng phản ánh mức sai lệch nhưng chưa giải thích đầy đủ nguyên nhân. Sau khi chạy thử, cần xem lại các mẫu nhận biết ổn định, vắng mặt giả kéo dài, gán sai danh tính hoặc người sử dụng điện thoại và sai số thời lượng lớn. Mỗi mẫu cần có dòng thời gian về độ tin cậy phát hiện, mã quỹ đạo, vùng liên kết, trạng thái danh tính và chuyển trạng thái để đối chiếu.')

# Restore English terminology only where explicitly introduced as such.
p=ROOT/'Chuong2.tex'
t=p.read_text(encoding='utf-8').replace('Wrong-Person Association Rate (WPAR):','tỉ lệ gán sai người (Wrong-Person Association Rate, WPAR):')
p.write_text(t,encoding='utf-8')
print('Final sentence-level corrections applied.')
