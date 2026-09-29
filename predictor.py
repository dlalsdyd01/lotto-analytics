import random
from collections import Counter

NUMBERS = range(1, 46)

STRATEGIES = {
    'balanced': '종합 통계 — 전체 빈도, 최근 50회 빈도, 미출현 기간을 함께 반영',
    'hot': '핫 번호 — 최근 30회에 자주 나온 번호 위주',
    'cold': '콜드 번호 — 오래 나오지 않은 번호 위주',
    'random': '완전 랜덤 — 통계 없이 무작위 (조합 필터만 적용)',
}

# 역대 당첨 조합 분포 기준 필터 범위
SUM_RANGE = (100, 175)
ODD_RANGE = (2, 4)
LOW_RANGE = (2, 4)  # 1~22 저번호 개수


def _normalize(values):
    lo, hi = min(values.values()), max(values.values())
    span = hi - lo or 1
    return {n: (v - lo) / span for n, v in values.items()}


def _frequency(draws):
    counter = Counter(n for d in draws for n in d['numbers'])
    return {n: counter.get(n, 0) for n in NUMBERS}


def _gaps(draws):
    """번호별 마지막 출현 이후 지난 회차 수"""
    gaps = {n: len(draws) for n in NUMBERS}
    for i, d in enumerate(reversed(draws)):
        for n in d['numbers']:
            if gaps[n] == len(draws):
                gaps[n] = i
    return gaps


def number_weights(draws, strategy):
    """전략별 번호 가중치 (0.05 이상으로 보정해 모든 번호가 뽑힐 여지를 남김)"""
    if strategy == 'random':
        return {n: 1.0 for n in NUMBERS}

    total = _normalize(_frequency(draws))
    recent50 = _normalize(_frequency(draws[-50:]))
    recent30 = _normalize(_frequency(draws[-30:]))
    gap = _normalize(_gaps(draws))

    if strategy == 'hot':
        raw = {n: 0.75 * recent30[n] + 0.25 * total[n] for n in NUMBERS}
    elif strategy == 'cold':
        raw = {n: 0.7 * gap[n] + 0.3 * (1 - recent50[n]) for n in NUMBERS}
    else:
        raw = {n: 0.3 * total[n] + 0.45 * recent50[n] + 0.25 * gap[n] for n in NUMBERS}
    return {n: 0.05 + w for n, w in raw.items()}


def _weighted_sample(pool, weights, k):
    pool = list(pool)
    picked = []
    for _ in range(k):
        n = random.choices(pool, weights=[weights[p] for p in pool])[0]
        picked.append(n)
        pool.remove(n)
    return picked


def _passes_filters(nums):
    s = sum(nums)
    odd = sum(n % 2 for n in nums)
    low = sum(n <= 22 for n in nums)
    if not (SUM_RANGE[0] <= s <= SUM_RANGE[1]):
        return False
    if not (ODD_RANGE[0] <= odd <= ODD_RANGE[1]):
        return False
    if not (LOW_RANGE[0] <= low <= LOW_RANGE[1]):
        return False
    # 3개 이상 연속번호 제외
    return not any(nums[i] + 1 == nums[i + 1] and nums[i + 1] + 1 == nums[i + 2] for i in range(4))


def describe(nums):
    odd = sum(n % 2 for n in nums)
    low = sum(n <= 22 for n in nums)
    return {
        'numbers': nums,
        'sum': sum(nums),
        'odd_even': f'{odd}:{6 - odd}',
        'low_high': f'{low}:{6 - low}',
    }


def predict(draws, strategy='balanced', sets=5, fixed=(), excluded=()):
    """
    예측 번호 생성.
    fixed 번호는 모든 세트에 포함, excluded 번호는 제외.
    조합 필터를 통과하지 못하면 재시도하고, 끝내 실패하면 필터 없이 생성.
    """
    if strategy not in STRATEGIES:
        strategy = 'balanced'
    fixed = sorted(set(fixed))
    excluded = set(excluded) - set(fixed)
    pool = [n for n in NUMBERS if n not in excluded and n not in fixed]
    need = 6 - len(fixed)
    if need < 1:
        raise ValueError('고정수는 최대 5개까지 선택할 수 있습니다.')
    if len(pool) < need:
        raise ValueError('제외수가 너무 많아 조합을 만들 수 없습니다.')

    weights = number_weights(draws, strategy)
    past = {tuple(sorted(d['numbers'])) for d in draws}
    results, seen = [], set()

    for _ in range(sets):
        combo = None
        for attempt in range(3000):
            nums = tuple(sorted(fixed + _weighted_sample(pool, weights, need)))
            if nums in seen or nums in past:
                continue
            if attempt < 2500 and not _passes_filters(nums):
                continue
            combo = nums
            break
        if combo is None:
            break
        seen.add(combo)
        results.append(describe(list(combo)))

    return {'strategy': strategy, 'strategy_desc': STRATEGIES[strategy], 'sets': results}


def hot_cold(draws, window=30, k=6):
    freq = _frequency(draws[-window:])
    ranked = sorted(NUMBERS, key=lambda n: (-freq[n], n))
    gaps = _gaps(draws)
    cold = sorted(NUMBERS, key=lambda n: (-gaps[n], n))[:k]
    return {
        'hot': [{'number': n, 'count': freq[n]} for n in ranked[:k]],
        'cold': [{'number': n, 'gap': gaps[n]} for n in cold],
        'window': window,
    }
