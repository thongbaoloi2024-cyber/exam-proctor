"""Generate explicitly synthetic evaluation fixtures, tables and figures.

No video, detector, tracker or FSM is run by this script. Noise distributions
are uncalibrated scenario assumptions, not measured model performance.
"""
from pathlib import Path
import hashlib
import json
import random
import statistics
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'data' / 'synthetic_evaluation'
TEX = ROOT / 'generated'
IMG = ROOT / 'Images'
SEED = 20260917
rng = random.Random(SEED)
for folder in (OUT, TEX, IMG):
    folder.mkdir(parents=True, exist_ok=True)

def classify(tp, fp, fn, tn=None):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * tp / (2 * tp + fp + fn) if tp + fn else None
    result = dict(tp=tp, fp=fp, fn=fn, precision=p, recall=r, f1=f)
    if tn is not None:
        result.update(tn=tn, fpr=fp/(fp+tn) if fp+tn else None)
    return result

def percentile(values, q):
    values=sorted(values)
    index=(len(values)-1)*q
    lo=math.floor(index)
    hi=math.ceil(index)
    return values[lo]+(values[hi]-values[lo])*(index-lo)

def durations(reference, estimate):
    errors=[b-a for a,b in zip(reference,estimate)]
    absolute=[abs(x) for x in errors]
    positive=[(a,e) for a,e in zip(reference,absolute) if a>0]
    return dict(n=len(errors),mae_s=statistics.mean(absolute),
                median_ae_s=statistics.median(absolute),p95_ae_s=percentile(absolute,.95),
                max_ae_s=max(absolute),bias_s=statistics.mean(errors),
                mape_percent=statistics.mean(e/a*100 for a,e in positive),
                mape_n=len(positive))

person=[]
for condition,total,tp,fp in [
    ('Ít che khuất',3200,3063,91),
    ('Che khuất nhẹ',2800,2539,139),
    ('Che khuất vừa',2400,1987,184),
    ('Sát biên vùng',1600,1271,152),
]:
    person.append(dict(condition=condition,reference_objects=total,**classify(tp,fp,total-tp)))
person_total=classify(sum(x['tp'] for x in person),sum(x['fp'] for x in person),sum(x['fn'] for x in person))

# Counts share exactly the same reference support. They are not actual predictions.
presence=[]
for name,fn,fp in [('S1',810,430),('S2',1890,810),('S3',3510,1440)]:
    presence.append(dict(scenario=name,**classify(27000-fn,fp,fn,9000-fp)))

phone=[]
for label,tp,fp,fn,tn,assigned,wrong in [
    ('Một người',920,73,80,1927,80,1),
    ('Nhiều người',845,110,155,1890,110,4),
    ('Che khuất tay',728,132,272,1868,95,6),
    ('Gần hai người',760,148,240,1852,105,9),
    ('Chỉ đặt trên bàn',0,64,0,2936,0,0),
]:
    phone.append(dict(condition=label,**classify(tp,fp,fn,tn),
                      assigned_events=assigned,wrong_owner_events=wrong,
                      wpar=wrong/assigned if assigned else None))

sessions=[]
for i,ref in enumerate([34,49,76,123,188,247,326,418,507,633,746,858],1):
    error=round(rng.gauss(-2,6+ref*.035))
    est=max(0,ref+error)
    sessions.append(dict(session_id=f'SYN-P{i:02d}',reference_s=ref,
                         synthetic_estimate_s=est,error_s=est-ref))
phone_duration=durations([r['reference_s'] for r in sessions],[r['synthetic_estimate_s'] for r in sessions])

shifts=[]
levels={'S1':1.0,'S2':2.0,'S3':4.0}
for i in range(1,31):
    schedule=rng.choice([4,6,8])*3600
    unobserved=rng.choice([0,0,0,30,90,180])
    observed=schedule-unobserved
    presence_ref=round(observed*rng.uniform(.76,.96))
    # Explicit cases around the policy threshold and cases without use.
    phone_ref=[0,840,900,960][i-1] if i<=4 else rng.randint(0,2700)
    allowance=900
    excess_ref=max(0,phone_ref-allowance)
    effective_ref=presence_ref-excess_ref
    base_presence_error=rng.gauss(-35,65)
    base_phone_error=rng.gauss(-5,25)
    if i in (10,20,30):
        base_presence_error+=rng.choice([-1,1])*rng.uniform(180,330)
    estimates={}
    for level,scale in levels.items():
        pred_presence=min(observed,max(0,round(presence_ref+scale*base_presence_error)))
        pred_phone=min(pred_presence,max(0,round(phone_ref+scale*base_phone_error)))
        pred_excess=max(0,pred_phone-allowance)
        pred_effective=max(0,pred_presence-pred_excess)
        estimates[level]=dict(presence_s=pred_presence,phone_s=pred_phone,
                              excess_s=pred_excess,effective_s=pred_effective,
                              error_s=pred_effective-effective_ref)
    shifts.append(dict(shift_id=f'SYN-C{i:02d}',schedule_s=schedule,
                       unobserved_s=unobserved,coverage=observed/schedule,
                       reference_presence_s=presence_ref,reference_phone_s=phone_ref,
                       allowance_s=allowance,reference_excess_s=excess_ref,
                       reference_effective_s=effective_ref,estimates=estimates))
shift_metrics={level:durations([r['reference_effective_s'] for r in shifts],
                              [r['estimates'][level]['effective_s'] for r in shifts]) for level in levels}

data=dict(data_kind='SYNTHETIC_NOT_FIELD_EXPERIMENT',seed=SEED,
          provenance='Generated counts and time totals. No CCTV, model inference or algorithm execution.',
          person_counts=person,person_micro=person_total,presence_counts=presence,
          phone_counts=phone,phone_sessions=sessions,phone_duration_metrics=phone_duration,
          shifts=shifts,shift_metrics=shift_metrics)

# Validate mathematical invariants and the support used for every metric.
assert sum(x['reference_objects'] for x in person)==10000
for row in presence:
    assert row['tp']+row['fn']==27000
    assert row['fp']+row['tn']==9000
for row in phone:
    assert sum(row[k] for k in ('tp','fp','fn','tn'))==3000
    assert 0<=row['wrong_owner_events']<=row['assigned_events']
assert phone[-1]['f1'] is None and phone[-1]['recall'] is None
for row in shifts:
    assert 0<=row['reference_phone_s']<=row['reference_presence_s']<=row['schedule_s']-row['unobserved_s']
    assert row['reference_effective_s']==row['reference_presence_s']-max(0,row['reference_phone_s']-row['allowance_s'])
    for estimate in row['estimates'].values():
        assert 0<=estimate['phone_s']<=estimate['presence_s']<=row['schedule_s']-row['unobserved_s']
        assert estimate['effective_s']==estimate['presence_s']-max(0,estimate['phone_s']-row['allowance_s'])
        assert estimate['error_s']==estimate['effective_s']-row['reference_effective_s']

data_path=OUT/'evaluation.json'
data_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
manifest=dict(data_kind=data['data_kind'],seed=SEED,calibrated_to_field_data=False,
              generator='generate_synthetic_evaluation.py',
              generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              data_sha256=hashlib.sha256(data_path.read_bytes()).hexdigest(),
              counts=dict(person_reference_objects=10000,presence_seconds_per_scenario=36000,
                          phone_seconds_per_condition=3000,phone_sessions=12,shifts=30),
              assumptions=dict(schedule_hours=[4,6,8],presence_fraction_of_observed=[.76,.96],
                               allowance_s=900,phone_duration_s=[0,2700],
                               unobserved_s=[0,30,90,180],
                               base_presence_error_normal_s=dict(mean=-35,sd=65),
                               base_phone_error_normal_s=dict(mean=-5,sd=25),
                               outlier_shifts=[10,20,30],outlier_additive_magnitude_s=[180,330],
                               phone_session_error_normal_s='mean=-2, sd=6+0.035*reference_s',
                               error_multipliers=levels),
              independent_blocks=['person_counts','presence_counts','phone_counts','phone_sessions','shifts'],
              restrictions=['No empirical accuracy claim','No algorithm ranking','No measured latency',
                            'Do not join independent blocks as if they came from the same video'],
              quantile_method='linear interpolation at (n-1)*q',
              validation='PASS: count support, duration bounds, policy formulas, undefined metrics')
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def dec(v,d=3):
    return '--' if v is None else f'{v:.{d}f}'.replace('.',',')

def table(caption,label,headers,rows,spec):
    return '\n'.join([r'\begin{table}[H]',r'\centering',r'\small',
        r'\caption{'+caption+'}',r'\label{'+label+'}',r'\begin{tabular}{'+spec+'}',
        r'\toprule',' & '.join(headers)+r'\\',r'\midrule',
        *[' & '.join(map(str,row))+r'\\' for row in rows],r'\bottomrule',r'\end{tabular}',r'\end{table}',''])

def figure(name,caption,label):
    return '\n'.join([r'\begin{figure}[H]',r'\centering',
        r'\includegraphics[width=0.88\textwidth]{Images/'+name+'}',r'\caption{'+caption+'}',
        r'\label{'+label+'}',r'\end{figure}',''])

text=r'''% Generated from data/synthetic_evaluation/evaluation.json. Do not edit numbers manually.
\subsection{Nguồn gốc và cấu trúc dữ liệu tổng hợp}
\label{sec:synthetic-origin}
Bộ dữ liệu trong phần này được tạo bằng chương trình với hạt giống ngẫu nhiên cố định 20260917. Dữ liệu gồm số đếm phân loại và các bản ghi thời lượng, không phải video đã chạy qua mô hình thị giác máy tính. Các tham số được chọn để bao phủ ca làm có độ dài khác nhau, trường hợp dưới và trên hạn mức điện thoại, khoảng mất quan sát và một số sai số lớn. Đây là các giả định thiết kế chưa được hiệu chỉnh theo dữ liệu thực địa.

Chương trình đã thực hiện việc sinh dữ liệu, kiểm tra ràng buộc và tính các chỉ số. Kết quả dưới đây vì vậy là \textbf{kết quả tính toán trên dữ liệu tổng hợp}, không phải kết quả thực nghiệm CCTV. Các mã SYN-P và SYN-C chỉ nhận diện bản ghi tổng hợp, không đại diện người tham gia thực tế.

Năm khối dữ liệu độc lập gồm số đếm phát hiện người, số đếm hiện diện, số đếm sử dụng điện thoại, 12 phiên điện thoại và 30 ca. Không ghép các khối này thành một tập quan sát chung hoặc suy ra quan hệ nhân quả giữa chúng. Ba mức S1, S2 và S3 biểu diễn mức nhiễu tăng dần, không đại diện ba thuật toán đã được chạy.

\begin{table}[H]
\centering
\caption{Các giả định của bộ dữ liệu tổng hợp}
\label{tab:synthetic-assumptions}
\begin{tabularx}{\textwidth}{p{4.4cm}X}
\toprule
Thành phần & Quy tắc tạo dữ liệu\\
\midrule
Thời lượng ca & 4, 6 hoặc 8 giờ\\
Mất quan sát & 0, 30, 90 hoặc 180 giây, lưu riêng với vắng mặt\\
Hiện diện tham chiếu & 76--96\% thời gian có quan sát\\
Điện thoại trong ca & 0--2700 giây, có mẫu tại ngưỡng hạn mức\\
Hạn mức điện thoại & 900 giây mỗi ca, dùng để kiểm tra công thức\\
Nhiễu thời lượng hiện diện & Phân phối chuẩn với trung bình $-35$ giây, độ lệch chuẩn 65 giây\\
Nhiễu thời lượng điện thoại & Phân phối chuẩn với trung bình $-5$ giây, độ lệch chuẩn 25 giây\\
Trường hợp sai số lớn & Ca 10, 20 và 30 thêm sai lệch có độ lớn 180--330 giây\\
Mức nhiễu S1/S2/S3 & Nhân cùng sai lệch cơ sở lần lượt với 1, 2 và 4\\
\bottomrule
\end{tabularx}
\end{table}

Thời lượng được làm tròn đến giây và giới hạn trong miền hợp lệ. Thời gian điện thoại không vượt thời gian hiện diện, thời gian hiện diện không vượt thời gian có quan sát. Các ràng buộc này bảo đảm tính nhất quán số học, nhưng không xác nhận rằng phân phối nhiễu phản ánh một camera hoặc một mô hình cụ thể.

\subsection{Kiểm tra chỉ số phát hiện người bằng số đếm tổng hợp}
Đơn vị tham chiếu là một đối tượng người tại một thời điểm quan sát, không phải một khung hình. Bảng sử dụng 10.000 đối tượng tham chiếu. TP, FP và FN là số đếm được khai báo trong bộ tổng hợp để kiểm tra công thức Precision, Recall và F1. Tổng hợp được tính từ tổng số đếm, không lấy trung bình các tỉ lệ theo số khung hình.
'''
rows=[[r['condition'],r['tp'],r['fp'],r['fn'],dec(r['precision']),dec(r['recall']),dec(r['f1'])] for r in person]
rows.append(['Tổng',person_total['tp'],person_total['fp'],person_total['fn'],dec(person_total['precision']),dec(person_total['recall']),dec(person_total['f1'])])
text+=table('Chỉ số phát hiện người từ số đếm tổng hợp','tab:syn-person',['Điều kiện','TP','FP','FN','P','R','F1'],rows,'lrrrrrr')
text+=r'''Số bỏ sót tăng theo nhóm che khuất là một giả định của bộ dữ liệu. Bảng này minh họa cách báo cáo kết quả theo điều kiện, không chứng minh bộ phát hiện đạt các giá trị tương ứng ngoài thực tế. Khi đánh giá trên video, cần bổ sung ngưỡng IoU, ngưỡng độ tin cậy và quy tắc ghép một-một giữa hộp dự đoán với nhãn tham chiếu.

\subsection{Kiểm tra chỉ số hiện diện trên cùng tập tham chiếu}
Mỗi kịch bản có 36.000 mẫu người--giây, trong đó 27.000 mẫu hiện diện và 9.000 mẫu vắng mặt. Khoảng mất quan sát không nằm trong tập phân loại này. Vì mỗi mẫu có độ dài một giây, FN chính là số giây vắng mặt giả và FP chính là số giây hiện diện giả.
'''
text+=table('Chỉ số hiện diện trên ba kịch bản nhiễu tổng hợp','tab:syn-presence',
            ['Mức','TP','FP (s)','FN (s)','TN','P','R','F1'],
            [[r['scenario'],r['tp'],r['fp'],r['fn'],r['tn'],dec(r['precision']),dec(r['recall']),dec(r['f1'])] for r in presence],'lrrrrrrr')
text+=figure('synthetic_presence_f1.png','F1 hiện diện tính từ số đếm tổng hợp','fig:synthetic-presence')
text+=r'''Ba hàng có cùng mẫu dương và mẫu âm, nên thay đổi Recall có thể đối chiếu trực tiếp với FN. Chênh lệch F1 xuất phát từ mức nhiễu đã đặt, không phải bằng chứng về mức cải thiện của ByteTrack hoặc máy trạng thái. Việc so sánh các thuật toán phải được thực hiện trên cùng video theo quy trình ở phần phương pháp so sánh.

\subsection{Kiểm tra chỉ số sử dụng và liên kết điện thoại}
Mỗi điều kiện có 3.000 mẫu người--giây. Bốn điều kiện đầu có 1.000 mẫu sử dụng và 2.000 mẫu không sử dụng. Điều kiện chỉ đặt điện thoại trên bàn có toàn bộ 3.000 mẫu âm, do đó Recall và F1 không được báo cáo. Tỉ lệ dương tính giả được tính theo $FPR=FP/(FP+TN)$.
'''
text+=table('Phân loại sử dụng điện thoại từ số đếm tổng hợp','tab:syn-phone',
            ['Điều kiện','TP','FP','FN','P','R','F1','FPR'],
            [[r['condition'],r['tp'],r['fp'],r['fn'],dec(r['precision']),dec(r['recall']),dec(r['f1']),dec(r['fpr'])] for r in phone],'lrrrrrrr')
text+=r'''WPAR sử dụng đơn vị sự kiện đã được gán người, khác với đơn vị người--giây của bảng phân loại. Các số đếm sự kiện bên dưới là một khối giả định riêng, không được dùng thay mẫu số của Precision hoặc Recall. Trường hợp không có sự kiện được gán có WPAR không xác định, ký hiệu bằng dấu gạch ngang.
'''
text+=table('Sai gán người trên các sự kiện điện thoại tổng hợp','tab:syn-owner',
            ['Điều kiện','Đã gán','Gán sai','WPAR'],
            [[r['condition'],r['assigned_events'],r['wrong_owner_events'],dec(r['wpar'])] for r in phone],'lrrr')
text+=r'''\subsection{Sai số thời lượng của 12 phiên điện thoại tổng hợp}
Thời lượng tham chiếu của 12 phiên được khai báo trong dữ liệu nguồn. Sai lệch được lấy từ phân phối chuẩn có trung bình $-2$ giây và độ lệch chuẩn $6+0{,}035T$ giây, với $T$ là thời lượng tham chiếu. Các giả định này tạo cả sai số tăng và giảm thời lượng, chưa mô tả sai số đo được của mô hình.
'''
text+=table('Toàn bộ 12 phiên điện thoại tổng hợp, đơn vị giây','tab:syn-phone-duration',
            ['Mã phiên','Tham chiếu','Ước lượng tổng hợp','Sai số có dấu'],
            [[r['session_id'],r['reference_s'],r['synthetic_estimate_s'],f"{r['error_s']:+d}"] for r in sessions],'lrrr')
text+=f"MAE tính trên toàn bộ 12 phiên là {dec(phone_duration['mae_s'],2)} giây/phiên, trung vị sai số tuyệt đối là {dec(phone_duration['median_ae_s'],2)} giây và sai số tuyệt đối lớn nhất là {dec(phone_duration['max_ae_s'],0)} giây. Các giá trị này có thể tính lại trực tiếp từ bảng, không suy ra từ một tập mẫu chưa công bố.\n\n"
text+=r'''\subsection{Sai số thời gian hiệu lực trên 30 ca tổng hợp}
Mỗi ca có thời lượng hiện diện và điện thoại tham chiếu. Sau khi bổ sung nhiễu, chương trình tính lại phần vượt hạn mức và thời gian hiệu lực cho từng mức S1, S2, S3 bằng cùng công thức ở Chương 1. Sai số được tính trên thời gian hiệu lực của cùng một ca. Khoảng mất quan sát được báo riêng, không tự động cộng vào hiện diện hoặc diễn giải là vắng mặt.
'''
text+=table('Sai số thời gian hiệu lực trên 30 ca tổng hợp','tab:syn-worktime',
            ['Mức','MAE (s/ca)',r'MAPE (\%)','Trung vị (s)','P95 (s)','Max (s)'],
            [[level,dec(m['mae_s'],2),dec(m['mape_percent'],2),dec(m['median_ae_s'],2),dec(m['p95_ae_s'],2),dec(m['max_ae_s'],0)] for level,m in shift_metrics.items()],'lrrrrr')
text+=r'''P95 sử dụng nội suy tuyến tính tại vị trí $(N-1)\times0{,}95$ trong dãy sai số tuyệt đối đã sắp tăng dần. MAPE chỉ tính trên thời lượng tham chiếu dương. Trong bộ này, cả 30 ca đều đáp ứng điều kiện. Các mức nhiễu sử dụng chung sai lệch cơ sở, vì vậy không được xem là các lần thử độc lập để kiểm định ưu thế thuật toán.
'''
text+=figure('synthetic_time_mae.png','MAE thời gian hiệu lực theo mức nhiễu tổng hợp','fig:synthetic-mae')
text+=figure('synthetic_shift_errors.png','Sai số có dấu của 30 ca tổng hợp ở mức S1','fig:synthetic-errors')
text+=r'''Phụ lục E công bố đủ 30 ca ở mức S1. Tệp dữ liệu nguồn lưu cả ba mức nhiễu cùng thời gian điện thoại trước và sau nhiễu. Mẫu không sử dụng điện thoại, mẫu đúng hạn mức và mẫu vừa vượt hạn mức giúp kiểm tra tính liên tục của phép điều chỉnh thời gian. Tuy nhiên, đây là kiểm tra số học trên tổng thời lượng, chưa kiểm chứng thuật toán xử lý khoảng thời gian hoặc chất lượng nhận biết hành vi.

\subsection{Phạm vi chưa có kết quả đo}
Các chỉ số IDF1, HOTA và số lần đổi định danh yêu cầu quỹ đạo dự đoán cùng nhãn theo thời gian. Do bộ dữ liệu tổng hợp hiện tại không có quỹ đạo, chương này không gán giá trị số cho các chỉ số theo dõi. Tương tự, ảnh hưởng của khoảng đệm và sai số mốc vào/ra chỉ có thể đo khi chạy máy trạng thái trên chuỗi quan sát có thời điểm cụ thể.

Hiệu năng phải được đo trên thiết bị xác định với phiên bản mô hình, thư viện và cấu hình đầu vào được lưu lại. Không thể suy ra tốc độ CCTV từ số đếm phân loại hoặc thời lượng tổng hợp. Với một chuỗi xử lý tuần tự, tổng thời gian trung bình bằng tổng trung bình của các thành phần, nhưng phân vị P95 của tổng không bằng tổng các phân vị P95. Độ trễ đầu-cuối còn bao gồm giải mã video, hàng đợi, truyền dữ liệu và hiển thị. Quy trình đo các thành phần này được trình bày ở phần đánh giá hiệu năng.

\subsection{Tái lập và giới hạn diễn giải}
Tệp \texttt{data/synthetic\_evaluation/evaluation.json} lưu toàn bộ số đếm, thời lượng và chỉ số. Tệp \texttt{manifest.json} ghi hạt giống, giả định, số mẫu và mã SHA-256 của dữ liệu cùng chương trình sinh. Chạy \texttt{python generate\_synthetic\_evaluation.py} tại thư mục báo cáo để tạo lại dữ liệu, bảng LaTeX và biểu đồ.

Bộ dữ liệu đáp ứng các ràng buộc số học đã khai báo và hỗ trợ kiểm tra cách tính chỉ số. Để đánh giá mức sát với thực tế, cần ước lượng lại phân phối sai số từ video có nhãn tham chiếu và kiểm tra trên tập độc lập. Khi chưa có dữ liệu đó, không thể xác định các mức S1, S2 hoặc S3 tương ứng với chất lượng của hệ thống ngoài thực địa.

'''
(TEX/'synthetic_results.tex').write_text(text,encoding='utf-8')

appendix=r'''\clearpage
\section*{PHỤ LỤC E -- DỮ LIỆU THỜI LƯỢNG TỔNG HỢP}
\phantomsection\addcontentsline{toc}{section}{\numberline{}PHỤ LỤC E -- DỮ LIỆU THỜI LƯỢNG TỔNG HỢP}
Bảng dưới đây công bố 30 ca tổng hợp ở mức S1. Các cột đều có đơn vị giây. Cột $U$ là thời gian không quan sát được, $P$ là hiện diện tham chiếu, $H$ là điện thoại tham chiếu, $E$ là thời gian hiệu lực tham chiếu và $\widehat{E}$ là thời gian hiệu lực sau khi thêm nhiễu. Mỗi ca dùng hạn mức điện thoại 900 giây. Cột sai số bằng $\widehat{E}-E$. Các bản ghi không đại diện nhân viên hoặc ca làm việc thực tế.

\begingroup
\small
\setlength{\tabcolsep}{4pt}
\begin{longtable}{lrrrrrrr}
\caption{Toàn bộ 30 ca tổng hợp ở mức nhiễu S1}\label{tab:synthetic-all-shifts}\\
\toprule
Mã ca & Ca & $U$ & $P$ & $H$ & $E$ & $\widehat{E}$ & Sai số\\
\midrule\endfirsthead
\toprule
Mã ca & Ca & $U$ & $P$ & $H$ & $E$ & $\widehat{E}$ & Sai số\\
\midrule\endhead
\bottomrule\endfoot
'''
for r in shifts:
    appendix+=' & '.join(map(str,[r['shift_id'],r['schedule_s'],r['unobserved_s'],r['reference_presence_s'],r['reference_phone_s'],r['reference_effective_s'],r['estimates']['S1']['effective_s'],f"{r['estimates']['S1']['error_s']:+d}"]))+r'\\'+'\n'
appendix+=r'\end{longtable}'+'\n'+r'\endgroup'+'\n'
(TEX/'synthetic_appendix.tex').write_text(appendix,encoding='utf-8')

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
def save(fig,name):
    fig.tight_layout()
    fig.savefig(IMG/name,dpi=180,bbox_inches='tight')
    plt.close(fig)

fig,ax=plt.subplots(figsize=(8,3.8))
values=[r['f1'] for r in presence]
bars=ax.bar(list(levels),values,color=['#386b8c','#738fa2','#aab7bf'],width=.55)
ax.set_ylim(0,1.08)
ax.set_ylabel('F1 hiện diện')
ax.set_xlabel('Mức nhiễu tổng hợp')
ax.set_title('Kết quả tính toán trên dữ liệu tổng hợp')
ax.bar_label(bars,labels=[dec(x) for x in values],padding=4)
save(fig,'synthetic_presence_f1.png')

fig,ax=plt.subplots(figsize=(8,3.8))
values=[r['mae_s'] for r in shift_metrics.values()]
bars=ax.bar(list(levels),values,color=['#386b8c','#738fa2','#aab7bf'],width=.55)
ax.set_ylim(0,max(values)*1.2)
ax.set_ylabel('MAE (giây/ca)')
ax.set_xlabel('Mức nhiễu tổng hợp')
ax.set_title('30 ca tổng hợp, không phải kết quả chạy mô hình')
ax.bar_label(bars,labels=[dec(x,2) for x in values],padding=4)
save(fig,'synthetic_time_mae.png')

fig,ax=plt.subplots(figsize=(8,3.8))
errors=[r['estimates']['S1']['error_s'] for r in shifts]
ax.bar(range(1,31),errors,color=['#a86148' if x<0 else '#386b8c' for x in errors])
ax.axhline(0,color='black',linewidth=.7)
ax.set_xticks([1,5,10,15,20,25,30])
ax.set_xlabel('Chỉ số ca tổng hợp')
ax.set_ylabel('Sai số có dấu (giây)')
ax.set_title('Biến thiên sai số được tạo ở mức nhiễu S1')
save(fig,'synthetic_shift_errors.png')

print(json.dumps(dict(validation='PASS',phone_duration=phone_duration,shift_metrics=shift_metrics,
                      data_sha256=manifest['data_sha256']),ensure_ascii=False,indent=2))
