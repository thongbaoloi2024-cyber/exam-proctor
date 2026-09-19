"""Reference interval arithmetic used by the thesis experiments, not a CCTV service.

All intervals are half-open. Inputs use one consistent unit (seconds in the report).
"""
import math
from numbers import Real


def finite_number(value):
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)


def merge(intervals):
    checked = []
    for interval in intervals:
        if not isinstance(interval, (list, tuple)) or len(interval) != 2:
            raise ValueError('An interval must contain two endpoints')
        a, b = interval
        if not finite_number(a) or not finite_number(b):
            raise ValueError('Endpoints must be finite numbers')
        if a > b:
            raise ValueError('Negative duration')
        if a != b:
            checked.append((a, b))
    result = []
    for a, b in sorted(checked):
        if result and a <= result[-1][1]:
            result[-1][1] = max(result[-1][1], b)
        else:
            result.append([a, b])
    return result


def intersect(left, right):
    left, right = merge(left), merge(right)
    return merge([[max(a, c), min(b, d)] for a, b in left for c, d in right
                  if max(a, c) < min(b, d)])


def subtract(left, right):
    result = merge(left)
    for c, d in merge(right):
        remaining = []
        for a, b in result:
            if d <= a or c >= b:
                remaining.append([a, b])
            else:
                if a < c:
                    remaining.append([a, c])
                if d < b:
                    remaining.append([d, b])
        result = remaining
    return result


def duration(intervals):
    return sum(b - a for a, b in intervals)


def aggregate(case):
    allowance = case.get('allowance', 900)
    if not finite_number(allowance) or allowance < 0:
        raise ValueError('Allowance must be a finite non-negative number')
    enabled = case.get('deduction_enabled', True)
    if not isinstance(enabled, bool):
        raise ValueError('Deduction flag must be boolean')
    schedule = merge(case['schedule'])
    unknown = intersect(schedule, case.get('unobserved', []))
    observed = subtract(schedule, unknown)
    presence = intersect(case['presence'], observed)
    phone = intersect(case['phone'], presence)
    p, h, u = map(duration, [presence, phone, unknown])
    excess = max(0, h - allowance)
    scheduled = duration(schedule)
    return dict(presence_s=p, phone_s=h, unobserved_s=u, excess_s=excess,
                effective_s=p - excess if enabled else p,
                scheduled_s=scheduled, observed_s=duration(observed),
                coverage=(scheduled - u) / scheduled if scheduled else None,
                valid_presence=presence, valid_phone=phone)
