"""Execute reproducible software experiments on synthetic interval inputs.

The independent oracle counts integer-second cells using bit masks; it never calls
the interval module. These tests do not execute a detector, tracker or camera FSM.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import random
import sys

from interval_arithmetic import aggregate

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'computational_evaluation'
SEED = 20260919
N_PER_GROUP = 250
KEYS = ['presence_s', 'phone_s', 'unobserved_s', 'excess_s', 'effective_s', 'scheduled_s']
GROUPS = [
    ('mixed', 'Khoảng phân bố ngẫu nhiên'),
    ('overlap', 'Lịch và hiện diện trùng'),
    ('phone_overlap', 'Điện thoại chồng lấn'),
    ('outage', 'Gián đoạn trong và ngoài ca'),
    ('empty', 'Không có lịch'),
    ('unobserved', 'Mất quan sát toàn ca'),
    ('zero_allowance', 'Hạn mức bằng không'),
    ('no_deduction', 'Tắt điều chỉnh'),
]


def oracle(case):
    # Each bit represents exactly [t,t+1); all randomized endpoints are integers.
    origin = min([0] + [a for key in ['schedule', 'presence', 'phone', 'unobserved']
                       for a, _ in case.get(key, [])])

    def mask(intervals):
        value = 0
        for a, b in intervals:
            value |= ((1 << (b - a)) - 1) << (a - origin)
        return value

    scheduled = mask(case['schedule'])
    lost = scheduled & mask(case.get('unobserved', []))
    present = mask(case['presence']) & scheduled & ~lost
    phone = mask(case['phone']) & present
    p, h, u, s = (x.bit_count() for x in (present, phone, lost, scheduled))
    excess = max(0, h - case.get('allowance', 900))
    effective = p - excess if case.get('deduction_enabled', True) else p
    return dict(zip(KEYS, [p, h, u, excess, effective, s]))


def draw_case(rng, group):
    horizon = rng.choice([4, 6, 8]) * 3600
    middle = horizon // 2

    def intervals(n):
        return [sorted([rng.randint(-300, horizon + 300),
                        rng.randint(-300, horizon + 300)]) for _ in range(n)]

    case = dict(schedule=[[0, middle], [middle + 600, horizon]],
                presence=intervals(rng.randint(0, 8)),
                phone=intervals(rng.randint(0, 6)),
                unobserved=intervals(rng.randint(0, 3)),
                allowance=rng.choice([0, 300, 900, 1800, 2700]), deduction_enabled=True)
    if group == 'overlap':
        case['schedule'] += [[0, middle], [middle // 2, middle - 1]]
        case['presence'] += case['presence'][:2]
    elif group == 'phone_overlap':
        case['phone'] += [[100, 900], [500, 1200], [100, 900]]
    elif group == 'outage':
        case['unobserved'] = [[-300, 180], [60, 300], [horizon-60, horizon+300]]
    elif group == 'empty':
        case['schedule'] = []
    elif group == 'unobserved':
        case['unobserved'] = [[-300, horizon + 300]]
    elif group == 'zero_allowance':
        case['allowance'] = 0
    elif group == 'no_deduction':
        case['deduction_enabled'] = False
    return case


def compare(case, result):
    expected = oracle(case)
    actual = {key: result[key] for key in KEYS}
    assert actual == expected, (case, expected, actual)
    expected_coverage = ((expected['scheduled_s']-expected['unobserved_s']) /
                         expected['scheduled_s']) if expected['scheduled_s'] else None
    assert result['coverage'] == expected_coverage
    assert 0 <= result['phone_s'] <= result['presence_s'] <= result['observed_s']
    assert 0 <= result['effective_s'] <= result['presence_s']
    return expected


def run():
    rng = random.Random(SEED)
    records = []
    checks = Counter()
    for group, _ in GROUPS:
        for index in range(N_PER_GROUP):
            case = draw_case(rng, group)
            result = aggregate(case)
            expected = compare(case, result)
            checks['independent_oracle'] += 1
            for transformation in ['reorder', 'duplicate', 'translate', 'split']:
                changed = deepcopy(case)
                for key in ['schedule', 'presence', 'phone', 'unobserved']:
                    if transformation == 'reorder':
                        rng.shuffle(changed[key])
                    elif transformation == 'duplicate':
                        changed[key] *= 2
                    elif transformation == 'translate':
                        changed[key] = [[a+86400, b+86400] for a, b in changed[key]]
                    else:
                        changed[key] = [part for a, b in changed[key]
                                        for part in [[a, (a+b)//2], [(a+b)//2, b]]]
                transformed = aggregate(changed)
                assert {key: transformed[key] for key in KEYS} == expected
                assert transformed['coverage'] == result['coverage']
                checks[transformation] += 1
            higher = dict(case, allowance=case['allowance'] + 300)
            assert aggregate(higher)['effective_s'] >= result['effective_s']
            checks['allowance_monotonicity'] += 1
            records.append(dict(id=f'{group}-{index+1:03d}', group=group, input=case,
                                expected=expected, actual={k: result[k] for k in KEYS},
                                coverage=result['coverage'], status='PASS'))

    # Additional malformed inputs and a fractional-second case have explicit answers.
    base = dict(schedule=[[0, 10]], presence=[[0, 10]], phone=[])
    bad = [dict(base, presence=[[0, float('nan')]]),
           dict(base, presence=[[0, float('inf')]]),
           dict(base, presence=[[False, 1]]), dict(base, presence=[[0, 1, 2]]),
           dict(base, allowance=float('inf')), dict(base, allowance='900')]
    for case in bad:
        try:
            aggregate(case)
        except ValueError:
            checks['additional_invalid'] += 1
        else:
            raise AssertionError('Malformed input was not rejected')
    fraction = aggregate(dict(schedule=[[0, 2]], presence=[[0.25, 1.75]],
                              phone=[[0.5, 1.5]], allowance=0.75))
    assert [fraction[k] for k in KEYS[:5]] == [1.5, 1, 0, 0.25, 1.25]
    checks['fractional_seconds'] += 1
    OUT.mkdir(exist_ok=True)
    summary = dict(kind='EXECUTED_SOFTWARE_TESTS_ON_SYNTHETIC_INPUTS', seed=SEED,
                   randomized_cases=len(records), groups=[dict(id=g, label=l, n=N_PER_GROUP)
                                                          for g, l in GROUPS],
                   checks=dict(checks), status='PASS', records=records)
    data_path = OUT / 'evaluation.json'
    data_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    files = [Path(__file__), ROOT/'interval_arithmetic.py',
             ROOT/'data/interval_evaluation/evaluation.json', data_path]
    manifest = dict(executed_at_utc=datetime.now(timezone.utc).isoformat(),
                    python=sys.version.split()[0], platform=platform.platform(), seed=SEED,
                    hashes={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in files},
                    scope='Reference interval module only. No video, detector, tracker or production FSM.',
                    oracle='Independent integer-second bit masks; exact for integer endpoints only.')
    (OUT/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    tex = r'''% Generated by evaluate_interval_arithmetic.py after assertions pass.
\subsection{Thực nghiệm tính toán với bộ đối chiếu độc lập}
\label{sec:computational-experiment}
Để mở rộng phạm vi kiểm thử ngoài các đáp án cố định, chương trình thực thi bộ tổng hợp trên 2.000 trường hợp ngẫu nhiên có hạt giống 20260919. Tám nhóm có quy mô bằng nhau, mỗi nhóm 250 trường hợp. Lịch danh định dài 4, 6 hoặc 8 giờ và có khoảng nghỉ 10 phút ở giữa. Các đầu mút được sinh trên lưới một giây, có thể nằm ngoài lịch 300 giây để kiểm tra thao tác cắt khoảng. Các khoảng ngẫu nhiên phục vụ phát hiện lỗi số học, không được dùng như phân phối hành vi nhân viên.

Bộ tính cần kiểm tra dùng phép sắp xếp, hợp nhất, giao và hiệu các khoảng. Bộ đối chiếu được cài đặt riêng, biểu diễn mỗi giây $[t,t+1)$ bằng một bit, dùng phép toán bit và đếm số bit còn lại. Bộ đối chiếu không gọi các hàm hợp nhất hoặc giao của mô-đun cần kiểm tra. Hai cách biểu diễn phải cho cùng sáu đại lượng: thời lượng lịch, hiện diện, điện thoại, mất quan sát, phần vượt và thời gian hiệu lực. Độ bao phủ được đối chiếu riêng. Cách đếm ô giây là chính xác đối với các đầu mút nguyên của tập này, không phải phép xấp xỉ cho mốc thời gian tùy ý.

\begin{table}[H]
\centering\small
\caption{Kết quả đối chiếu bộ tính khoảng với biểu diễn bit độc lập}
\label{tab:computational-checks}
\begin{tabularx}{\textwidth}{Xrr}
\toprule
Nhóm đầu vào & Số trường hợp & Khớp đáp án\\
\midrule
'''
    for _, label in GROUPS:
        tex += f'{label} & {N_PER_GROUP} & {N_PER_GROUP}'+r'\\'+'\n'
    tex += r'''\midrule
Tổng & 2.000 & 2.000\\
\bottomrule
\end{tabularx}
\end{table}

Trong 2.000 trường hợp đã chạy, sai lệch giữa hai cách tính bằng không ở tất cả các đại lượng đối chiếu. Mỗi đầu vào còn được đảo thứ tự, nhân đôi bản ghi, dịch toàn bộ mốc thêm một ngày và chia mỗi khoảng thành hai đoạn liền kề. Cả bốn phép biến đổi đều giữ nguyên thời lượng và độ bao phủ, tương ứng 8.000 lượt kiểm tra. Việc tăng hạn mức thêm 300 giây cũng không làm giảm thời gian hiệu lực trong 2.000 lượt kiểm tra bổ sung. Các lượt biến đổi dùng lại đầu vào gốc, không được tính như những mẫu thực địa độc lập.

Sáu đầu vào phụ kiểm tra giá trị không hữu hạn, sai kiểu và sai số lượng đầu mút đều bị từ chối. Một trường hợp dùng mốc 0,25 và 1,75 giây cho thời lượng hiện diện 1,5 giây, điện thoại 1 giây, hạn mức 0,75 giây và hiệu lực 1,25 giây, khớp đáp án trực tiếp. Trường hợp này chỉ kiểm tra xử lý mốc lẻ, không mở rộng kết luận của bộ đối chiếu lưới một giây sang mọi số thực.

Kết quả cho thấy bộ tính tham chiếu bảo toàn các bất biến đã kiểm tra, đặc biệt là tính không phụ thuộc thứ tự và tính không cộng trùng. Kết quả không chứng minh máy trạng thái tạo đúng đầu vào, cũng không đánh giá độ chính xác của YOLOv8, ByteTrack hoặc FaceNet. Mã chạy, cấu hình sinh, từng đầu vào và kết quả được lưu trong \path{computational_evaluation/}. Tệp bản kê ghi phiên bản Python, hệ điều hành và mã SHA-256 của các tệp dùng trong lần chạy.

'''
    (ROOT/'generated'/'computational_results.tex').write_text(tex, encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'records'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
