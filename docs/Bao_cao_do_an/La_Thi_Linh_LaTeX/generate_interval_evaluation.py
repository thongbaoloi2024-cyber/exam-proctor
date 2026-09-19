"""Deterministic interval fixtures, independent expected answers, and report assets.

This executes reference interval arithmetic, not a CCTV model or production FSM.
Run from any directory. No PDF is compiled or modified.
"""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'data' / 'interval_evaluation'
OUT.mkdir(parents=True, exist_ok=True)

from interval_arithmetic import aggregate, duration

# Expected tuples were derived by hand: presence, phone, unobserved, excess, effective.
cases=[
 dict(id='I01',label='Không sử dụng điện thoại',schedule=[[0,3600]],presence=[[0,3600]],phone=[],expected=[3600,0,0,0,3600]),
 dict(id='I02',label='Dưới hạn mức',schedule=[[0,3600]],presence=[[0,3600]],phone=[[100,940]],expected=[3600,840,0,0,3600]),
 dict(id='I03',label='Đúng hạn mức',schedule=[[0,3600]],presence=[[0,3600]],phone=[[100,1000]],expected=[3600,900,0,0,3600]),
 dict(id='I04',label='Vượt hạn mức 1 giây',schedule=[[0,3600]],presence=[[0,3600]],phone=[[100,1001]],expected=[3600,901,0,1,3599]),
 dict(id='I05',label='Khoảng chồng lấn và lặp',schedule=[[0,3600]],presence=[[0,2000],[1500,3600],[0,2000]],phone=[[100,700],[500,1200],[100,700]],expected=[3600,1100,0,200,3400]),
 dict(id='I06',label='Điện thoại ngoài hiện diện',schedule=[[0,3600]],presence=[[600,2400]],phone=[[0,900],[2300,3000]],expected=[1800,400,0,0,1800]),
 dict(id='I07',label='Ca có khoảng nghỉ',schedule=[[0,1800],[2400,4200]],presence=[[0,4200]],phone=[[1500,2700]],expected=[3600,600,0,0,3600]),
 dict(id='I08',label='Loại khoảng mất quan sát',schedule=[[0,3600]],presence=[[0,3600]],phone=[[900,2100]],unobserved=[[1200,1800]],expected=[3000,600,600,0,3000]),
 dict(id='I09',label='Mất quan sát chồng lấn',schedule=[[0,3600]],presence=[[0,3600]],phone=[],unobserved=[[-100,100],[50,300],[3500,4000]],expected=[3200,0,400,0,3200]),
 dict(id='I10',label='Ca qua nửa đêm',schedule=[[82800,90000]],presence=[[84600,88200]],phone=[[85800,87000]],expected=[3600,1200,0,300,3300]),
 dict(id='I11',label='Tắt điều chỉnh thời gian',schedule=[[0,3600]],presence=[[0,3600]],phone=[[0,1200]],deduction_enabled=False,expected=[3600,1200,0,300,3600]),
 dict(id='I12',label='Không có lịch làm việc',schedule=[],presence=[[0,3600]],phone=[[0,1200]],expected=[0,0,0,0,0]),
 dict(id='I13',label='Khoảng độ dài bằng không',schedule=[[0,3600]],presence=[[100,100],[200,400]],phone=[[200,200]],expected=[200,0,0,0,200]),
 dict(id='I14',label='Từ chối thời lượng âm',schedule=[[0,3600]],presence=[[400,200]],phone=[],expected_error='Negative duration'),
 dict(id='I15',label='Không có hiện diện',schedule=[[0,3600]],presence=[],phone=[[100,1000]],expected=[0,0,0,0,0]),
 dict(id='I16',label='Mất quan sát toàn ca',schedule=[[0,3600]],presence=[[0,3600]],phone=[[100,1000]],unobserved=[[-100,3700]],expected=[0,0,3600,0,0]),
 dict(id='I17',label='Các khoảng liền kề',schedule=[[0,3600]],presence=[[0,1800],[1800,3600]],phone=[[0,600],[600,1200]],expected=[3600,1200,0,300,3300]),
 dict(id='I18',label='Hạn mức bằng không',schedule=[[0,3600]],presence=[[0,3600]],phone=[[100,700]],allowance=0,expected=[3600,600,0,600,3000]),
 dict(id='I19',label='Hạn mức lớn hơn điện thoại',schedule=[[0,3600]],presence=[[0,3600]],phone=[[100,700]],allowance=7200,expected=[3600,600,0,0,3600]),
 dict(id='I20',label='Gián đoạn ngoài lịch',schedule=[[1000,2000]],presence=[[0,3000]],phone=[[800,1200]],unobserved=[[0,500],[2200,3000]],expected=[1000,200,0,0,1000]),
 dict(id='I21',label='Lịch trùng và chồng lấn',schedule=[[0,2400],[1800,3600],[0,2400]],presence=[[0,4000]],phone=[[0,1800]],expected=[3600,1800,0,900,2700]),
 dict(id='I22',label='Từ chối hạn mức âm',schedule=[[0,3600]],presence=[[0,3600]],phone=[],allowance=-1,expected_error='Allowance must be a finite non-negative number'),
 dict(id='I23',label='Từ chối hạn mức kiểu logic',schedule=[[0,3600]],presence=[[0,3600]],phone=[],allowance=True,expected_error='Allowance must be a finite non-negative number'),
 dict(id='I24',label='Từ chối cờ sai kiểu',schedule=[[0,3600]],presence=[[0,3600]],phone=[],deduction_enabled='false',expected_error='Deduction flag must be boolean'),
]
keys=['presence_s','phone_s','unobserved_s','excess_s','effective_s']
for case in cases:
    try:
        case['result']=aggregate(case)
    except ValueError as error:
        assert str(error)==case.get('expected_error'),case['id']
        case['status']='REJECTED_AS_EXPECTED'
    else:
        assert 'expected_error' not in case
        assert [case['result'][k] for k in keys]==case['expected'],case['id']
        case['status']='PASS'

def h(hour,minute=0): return hour*3600+minute*60
timeline=dict(id='TIMELINE',schedule=[[h(8),h(12)],[h(13),h(17,30)]],
              presence=[[h(8,5),h(12)],[h(13,5),h(17,15)]],
              phone=[[h(9,10),h(9,18)],[h(10,45),h(10,57)],[h(14,10),h(14,30)],[h(16,5),h(16,10)]],
              allowance=900)
timeline['result']=aggregate(timeline)
assert [timeline['result'][k] for k in keys]==[29100,2700,0,1800,27300]
# Display convention: consume allowance in chronological order, without claiming productivity.
remaining=timeline['allowance']; excess_intervals=[]
for a,b in timeline['result']['valid_phone']:
    free=min(remaining,b-a); remaining-=free
    if a+free<b: excess_intervals.append([a+free,b])
assert duration(excess_intervals)==timeline['result']['excess_s']
timeline['excess_intervals']=excess_intervals
sensitivity=[]
for minutes in [0,5,15,30,45]:
    c=dict(timeline,allowance=minutes*60)
    sensitivity.append(dict(allowance_min=minutes,**aggregate(c)))
data=dict(kind='DETERMINISTIC_SYNTHETIC_INTERVAL_FIXTURES',unit='second',
          interval_convention='half-open [start,end)',cases=cases,timeline=timeline,sensitivity=sensitivity)
path=OUT/'evaluation.json'
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
manifest=dict(generator=Path(__file__).name,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              data_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),cases=len(cases),
              validation='20 exact expected results; 4 expected rejections',
              module='interval_arithmetic.py',module_sha256=hashlib.sha256((ROOT/'interval_arithmetic.py').read_bytes()).hexdigest(),
              scope='Reference interval arithmetic only; no detector, tracker or production FSM executed.')
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


tex=r'''% Generated by generate_interval_evaluation.py. Inputs are synthetic test fixtures.
\subsection{Kiểm thử bộ tổng hợp trên các kịch bản xác định}
\label{sec:interval-evaluation}
Thí nghiệm thực thi mô-đun \texttt{interval\_arithmetic.py} trên 24 kịch bản đầu vào tổng hợp. Hai mươi kịch bản hợp lệ có đáp án xác định trước bằng phép tính trực tiếp. Bốn kịch bản không hợp lệ kiểm tra khả năng từ chối dữ liệu sai. Các tình huống được lựa chọn từ quy tắc nghiệp vụ ở Chương 3, gồm ca qua nửa đêm, giờ nghỉ, khoảng trùng, gián đoạn quan sát và cấu hình hạn mức. Đây là kiểm thử phần mềm của bộ tính tham chiếu, chưa bao gồm bộ nhận biết hình ảnh hoặc dịch vụ triển khai.

Các khoảng có dạng nửa kín $[s,e)$, đơn vị giây. Mốc lớn hơn 86.400 thuộc ngày kế tiếp. Đầu mút phải là số hữu hạn, hạn mức không âm và cờ điều chỉnh có kiểu logic. Khoảng độ dài bằng không được bỏ qua. Khoảng trùng, chồng lấn hoặc liền kề được hợp nhất trước khi tính. Bảng~\ref{tab:interval-checks} trình bày kết quả thực thi, ký hiệu gạch ngang ứng với đầu vào bị từ chối. Dữ liệu và đáp án đầy đủ nằm trong Phụ lục F.

\begingroup
\small
\setlength{\tabcolsep}{4pt}
\begin{longtable}{p{0.65cm}p{4.2cm}rrrr}
\caption{Kết quả thực thi trên 24 kịch bản xác định, đơn vị giây}\label{tab:interval-checks}\\
\toprule
Mã & Kịch bản & $T_{presence}$ & $T_{phone}$ & $T_{excess}$ & $T_{effective}$\\
\midrule\endfirsthead
\toprule
Mã & Kịch bản & $T_{presence}$ & $T_{phone}$ & $T_{excess}$ & $T_{effective}$\\
\midrule\endhead
\bottomrule\endfoot
'''
for c in cases:
    vals=[str(c['result'][k]) for k in [keys[0],keys[1],keys[3],keys[4]]] if 'result' in c else ['--']*4
    tex+=' & '.join([c['id'],c['label']]+vals)+r'\\'+'\n'
tex+=r'''\end{longtable}
\endgroup

Hai mươi kịch bản hợp lệ khớp cả năm đại lượng: hiện diện, điện thoại, không quan sát được, phần vượt hạn mức và thời gian hiệu lực. I14, I22, I23 và I24 bị từ chối đúng điều kiện. Kết quả này xác nhận các đáp án kiểm thử đã xét, không phải tỉ lệ nhận biết người hoặc điện thoại.

I05 và I21 cho thấy việc nhập lặp các khoảng không làm tăng thời lượng. I07 loại phần điện thoại nằm trong giờ nghỉ. I08 và I09 loại lần lượt 600 và 400 giây mất quan sát, cho độ bao phủ 83,33\% và 88,89\%. I12 không có lịch nên độ bao phủ không xác định, còn I16 có lịch nhưng mất quan sát toàn ca nên độ bao phủ bằng không. Hai trường hợp này cần được hiển thị khác nhau.

I11 giữ nguyên hiện diện khi tắt điều chỉnh, dù vẫn ghi phần vượt. I18 kiểm tra hạn mức bằng không. I22--I24 bổ sung kiểm tra cấu hình nhằm tránh một giá trị âm hoặc chuỗi ký tự làm thay đổi phép tính ngoài dự kiến.

\subsection{Ảnh hưởng của chính sách hạn mức}
\label{sec:policy-sensitivity}
Dòng thời gian ở Hình~\ref{fig:timeline-ui} dùng lịch 08:00--12:00 và 13:00--17:30, tổng 510 phút. Hiện diện gồm 08:05--12:00 và 13:05--17:15, tổng 485 phút. Bốn phiên điện thoại dài 8, 12, 20 và 5 phút, tổng 45 phút. Vì không có gián đoạn nguồn, độ bao phủ quan sát bằng 100\%, trong khi tỉ lệ hiện diện trên lịch là $485/510\approx95{,}10\%$. Độ bao phủ phản ánh khả năng quan sát, không đồng nghĩa với tỉ lệ hiện diện.

\begin{table}[H]
\centering
\caption{Kết quả thay đổi hạn mức trên cùng đầu vào tổng hợp, đơn vị phút}
\label{tab:allowance-sensitivity}
\begin{tabular}{rrrr}
\toprule
Hạn mức & Điện thoại & Phần vượt & Thời gian hiệu lực\\
\midrule
'''
for c in sensitivity:
    tex+=' & '.join(str(c[k]//60) if k!='allowance_min' else str(c[k]) for k in ['allowance_min','phone_s','excess_s','effective_s'])+r'\\'+'\n'
tex+=r'''\bottomrule
\end{tabular}
\end{table}

Hạn mức 15 phút cho phần vượt 30 phút và thời gian hiệu lực 455 phút. Khi hạn mức tăng đến 45 phút, thời gian hiệu lực đạt 485 phút và không tăng thêm. Đây là tác động của chính sách trên cùng quan sát đầu vào, không phải mức cải thiện của thuật toán nhận biết. Phần vượt trên hình được phân bổ theo thứ tự thời gian để giải thích tổng lượng khấu trừ.

Tệp \path{data/interval_evaluation/evaluation.json} lưu đầu vào, đáp án và kết quả. Bản kê đi kèm ghi mã SHA-256 của dữ liệu, chương trình sinh và mô-đun tính toán. Các kết quả được tái tạo bằng lệnh \texttt{python generate\_interval\_evaluation.py}.

'''
(ROOT/'generated'/'interval_results.tex').write_text(tex,encoding='utf-8')
appendix=r'''\clearpage
\section*{PHỤ LỤC F -- DỮ LIỆU KIỂM THỬ KHOẢNG THỜI GIAN}
\phantomsection\addcontentsline{toc}{section}{\numberline{}PHỤ LỤC F -- DỮ LIỆU KIỂM THỬ KHOẢNG THỜI GIAN}
Các đầu vào dưới đây được tạo cho kiểm thử bộ tính thời gian. Ký hiệu $S$, $P$, $H$, $U$ lần lượt là lịch, hiện diện, điện thoại và mất quan sát. Đơn vị là giây, các khoảng có dạng $[s,e)$. Mỗi kịch bản mặc định có hạn mức 900 giây và bật điều chỉnh. Đáp án là bộ năm giá trị theo thứ tự: hiện diện, điện thoại, mất quan sát, phần vượt và thời gian hiệu lực. Các giá trị kỳ vọng được khai báo riêng với kết quả do chương trình tính.

'''
def interval_tex(values):
    return '$'+(', '.join(f'[{a},{b})' for a,b in values) or r'\varnothing')+'$'
for c in cases:
    appendix+=r'\noindent\textbf{'+c['id']+' -- '+c['label']+r'.} '+'\n'
    for key,symbol in [('schedule','S'),('presence','P'),('phone','H'),('unobserved','U')]:
        appendix+=f'{symbol}: {interval_tex(c.get(key,[]))}. '+ '\n'
    allowance=str(c.get('allowance',900))
    enabled=str(c.get('deduction_enabled',True))
    appendix+=f'Hạn mức: {allowance}. Cờ điều chỉnh: \\texttt{{{enabled}}}. '
    if 'expected' in c:
        appendix+='Đáp án: $('+', '.join(map(str,c['expected']))+')$.\n\n'
    else:
        appendix+='Kỳ vọng: từ chối đầu vào.\n\n'
(ROOT/'generated'/'interval_appendix.tex').write_text('\n'.join(line.rstrip() for line in appendix.splitlines())+'\n',encoding='utf-8')

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(figsize=(10,4.5))
for y,intervals,color,hatch in [(3,timeline['result']['valid_presence'],'#31688e',None),
                              (2,timeline['result']['valid_phone'],'#35a18a','//'),
                              (1,excess_intervals,'#ce7850','xx')]:
    ax.broken_barh([(a/3600,(b-a)/3600) for a,b in intervals],(y-.23,.46),facecolors=color,edgecolors='#263746',hatch=hatch)
ax.axvspan(12,13,color='#e9edef',zorder=0)
ax.set_xlim(8,17.5);ax.set_ylim(.4,3.7)
ax.set_yticks([3,2,1],['Hiện diện\n485 phút','Điện thoại\n45 phút','Phần vượt\n30 phút'])
ax.set_xticks(range(8,18),[f'{x:02d}:00' for x in range(8,18)])
ax.set_xlabel('Giờ trong ngày giả định');ax.grid(axis='x',alpha=.2)
ax.set_title('Kịch bản kiểm thử: hiện diện và sử dụng điện thoại',fontsize=12,pad=15)
fig.text(.55,.015,'Vùng xám: giờ nghỉ. Phần vượt được phân bổ theo thứ tự thời gian.',ha='center',fontsize=10)
fig.tight_layout(rect=(0,.06,1,1))
for ext in ['png','svg','pdf']:
    target=ROOT/'Images'/f'sim_timeline.{ext}'
    pending=target.with_name(target.stem+'.writing'+target.suffix)
    fig.savefig(pending,dpi=220,bbox_inches='tight')
    if ext=='svg':
        pending.write_text('\n'.join(line.rstrip() for line in pending.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    pending.replace(target)
plt.close(fig)
print(json.dumps(manifest,ensure_ascii=False,indent=2))
