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

def merge(intervals):
    result = []
    for a, b in sorted(intervals):
        if a > b:
            raise ValueError('Negative duration')
        if a == b:
            continue
        if result and a <= result[-1][1]:
            result[-1][1] = max(result[-1][1], b)
        else:
            result.append([a, b])
    return result

def intersect(left, right):
    return merge([[max(a,c),min(b,d)] for a,b in merge(left)
                  for c,d in merge(right) if max(a,c)<min(b,d)])

def subtract(left, right):
    result = merge(left)
    for c,d in merge(right):
        next_result=[]
        for a,b in result:
            if d<=a or c>=b:
                next_result.append([a,b])
            else:
                if a<c: next_result.append([a,c])
                if d<b: next_result.append([d,b])
        result=next_result
    return result

def duration(intervals):
    return sum(b-a for a,b in intervals)

def aggregate(case):
    schedule=merge(case['schedule'])
    unknown=intersect(schedule,case.get('unobserved',[]))
    observed=subtract(schedule,unknown)
    presence=intersect(case['presence'],observed)
    phone=intersect(case['phone'],presence)
    p,h,u=map(duration,[presence,phone,unknown])
    excess=max(0,h-case.get('allowance',900))
    effective=p-excess if case.get('deduction_enabled',True) else p
    return dict(presence_s=p,phone_s=h,unobserved_s=u,excess_s=excess,
                effective_s=effective,coverage=(1-u/duration(schedule)) if duration(schedule) else None,
                valid_presence=presence,valid_phone=phone)

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
              validation='13 exact expected results; 1 expected rejection',
              scope='Reference interval arithmetic only; no detector, tracker or production FSM executed.')
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

tex=r'''% Generated by generate_interval_evaluation.py; deterministic fixtures, not CCTV measurements.
\subsection{Kiểm tra tổng hợp khoảng thời gian bằng kịch bản xác định}
\label{sec:interval-evaluation}
Bộ dữ liệu bổ sung gồm 14 kịch bản có mốc bắt đầu, kết thúc và đáp án được xác định trước. Mục tiêu là kiểm tra phép hợp, giao, hiệu các tập khoảng và quy tắc hạn mức, bổ sung cho các số đếm và tổng thời lượng ở mục trước. Chương trình thực thi một bộ tính tham chiếu độc lập, chưa gọi bộ phát hiện, bộ theo dõi hoặc máy trạng thái của hệ thống triển khai. Vì vậy, kết quả đúng trên các kịch bản này chỉ xác nhận phép tính tham chiếu trong phạm vi đã xét.

Các khoảng được biểu diễn nửa kín $[s,e)$, đơn vị giây kể từ đầu ngày giả định. Mốc lớn hơn 86.400 biểu diễn ngày tiếp theo. Khoảng có độ dài bằng không được bỏ qua, khoảng có mốc kết thúc nhỏ hơn mốc bắt đầu bị từ chối. Các khoảng trùng và chồng lấn được hợp nhất trước khi tính thời lượng. Lịch làm việc hợp lệ được loại phần không quan sát được trước khi lấy giao với hiện diện và điện thoại.

\begin{table}[H]
\centering\small
\caption{Kết quả tính trên các kịch bản khoảng thời gian tổng hợp, đơn vị giây}
\label{tab:interval-checks}
\begin{tabularx}{\textwidth}{lXrrrr}
\toprule
Mã & Kịch bản & $T_{presence}$ & $T_{phone}$ & $T_{excess}$ & $T_{effective}$\\
\midrule
'''
for c in cases:
    vals=[str(c['result'][k]) for k in [keys[0],keys[1],keys[3],keys[4]]] if 'result' in c else ['--']*4
    tex+=' & '.join([c['id'],c['label']]+vals)+r'\\'+'\n'
tex+=r'''\bottomrule
\end{tabularx}
\end{table}

Mười ba kịch bản hợp lệ khớp toàn bộ các đại lượng với đáp án đã xác định trước, còn I14 bị từ chối đúng quy tắc. Đây là mức bao phủ kịch bản, không phải tỉ lệ chính xác của mô hình thị giác. I05 cho thấy bản ghi lặp không làm tăng thời lượng. I07 loại phần điện thoại nằm trong giờ nghỉ. I08 và I09 loại lần lượt 600 và 400 giây mất quan sát, cho độ bao phủ tương ứng 83,33\% và 88,89\%. I11 vẫn ghi nhận phần vượt hạn mức nhưng không trừ khi chính sách điều chỉnh bị tắt. I12 có độ bao phủ không xác định vì tổng lịch bằng không, không tự gán bằng 100\%.

\subsection{Phân tích tác động của hạn mức trên cùng dòng thời gian}
Dòng thời gian minh họa tại Hình~\ref{fig:timeline-ui} có hai khoảng hiện diện: 08:05--12:00 và 13:05--17:15, tổng 485 phút. Bốn phiên điện thoại dài 8, 12, 20 và 5 phút, tổng 45 phút. Với hạn mức 15 phút, phần vượt là 30 phút và thời gian hiệu lực là 455 phút. Trên hình, phần vượt được tô theo thứ tự thời gian để giải thích phép trừ. Đây là quy ước hiển thị, không phải nhãn về năng suất từng đoạn.

\begin{table}[H]
\centering
\caption{Ảnh hưởng của hạn mức trên cùng dữ liệu tổng hợp, đơn vị phút}
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

Khi hạn mức tăng từ 0 đến tổng thời gian điện thoại, thời gian hiệu lực tăng cùng lượng, sau đó giữ ở mức hiện diện. Thay đổi này xuất phát hoàn toàn từ chính sách, không thể diễn giải thành cải thiện độ chính xác mô hình. Phân tích giúp phân biệt sai số quan sát với tác động của quy định áp dụng sau quan sát.

Tệp \texttt{data/interval\_evaluation/evaluation.json} công bố toàn bộ khoảng đầu vào, đáp án, kết quả và dữ liệu của hình minh họa. Có thể tái tạo bằng \texttt{python generate\_interval\_evaluation.py}. Bản kê đi kèm lưu mã SHA-256 của chương trình và dữ liệu. Các kịch bản không bao phủ chất lượng liên kết danh tính, điều kiện chuyển trạng thái, độ trễ hay tính đúng đắn của dịch vụ triển khai.

'''
(ROOT/'generated'/'interval_results.tex').write_text(tex,encoding='utf-8')
appendix=r'''\clearpage
\section*{PHỤ LỤC F -- KỊCH BẢN KHOẢNG THỜI GIAN TỔNG HỢP}
\phantomsection\addcontentsline{toc}{section}{\numberline{}PHỤ LỤC F -- KỊCH BẢN KHOẢNG THỜI GIAN TỔNG HỢP}
Các mốc dưới đây có đơn vị giây. Mỗi kịch bản mặc định có hạn mức 900 giây và bật điều chỉnh. I11 tắt điều chỉnh. Ký hiệu $S$, $P$, $H$, $U$ lần lượt là lịch làm việc, hiện diện đầu vào, điện thoại đầu vào và khoảng không quan sát được. Tập rỗng ký hiệu $\varnothing$.

'''
def interval_tex(values):
    return '$'+(', '.join(f'[{a},{b})' for a,b in values) or r'\varnothing')+'$'
for c in cases:
    appendix+=r'\noindent\textbf{'+c['id']+' -- '+c['label']+r'.} '+'\n'
    for key,symbol in [('schedule','S'),('presence','P'),('phone','H'),('unobserved','U')]:
        appendix+=f'{symbol}: {interval_tex(c.get(key,[]))}. '+ '\n'
    appendix+='\n'
(ROOT/'generated'/'interval_appendix.tex').write_text(appendix,encoding='utf-8')

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
ax.set_title('Dữ liệu tổng hợp | Hạn mức 15 phút | Thời gian hiệu lực 455 phút',fontsize=12,pad=15)
fig.text(.55,.015,'Vùng xám: giờ nghỉ. Phần vượt được phân bổ theo thứ tự thời gian.',ha='center',fontsize=10)
fig.tight_layout(rect=(0,.06,1,1))
for ext in ['png','svg']:
    fig.savefig(ROOT/'Images'/f'sim_timeline.{ext}',dpi=220,bbox_inches='tight')
plt.close(fig)
print(json.dumps(manifest,ensure_ascii=False,indent=2))
