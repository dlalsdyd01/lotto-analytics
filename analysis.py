import numpy as np
import pandas as pd
from collections import Counter
import random


def build_dataframe(draws):
    """당첨 데이터를 DataFrame으로 변환"""
    rows = []
    for d in draws:
        row = {
            'draw_no': d['draw_no'],
            'date': d['date'],
            'n1': d['numbers'][0],
            'n2': d['numbers'][1],
            'n3': d['numbers'][2],
            'n4': d['numbers'][3],
            'n5': d['numbers'][4],
            'n6': d['numbers'][5],
            'bonus': d['bonus'],
        }
        rows.append(row)
    return pd.DataFrame(rows)


def get_all_numbers(draws):
    """모든 당첨번호를 1차원 리스트로 반환"""
    numbers = []
    for d in draws:
        numbers.extend(d['numbers'])
    return numbers


def frequency_analysis(draws):
    """번호별 출현 빈도 분석 (1~45)"""
    all_nums = get_all_numbers(draws)
    counter = Counter(all_nums)
    return {n: counter.get(n, 0) for n in range(1, 46)}


def recent_frequency(draws, n=50):
    """최근 N회차 번호별 출현 빈도"""
    recent = draws[-n:] if len(draws) >= n else draws
    all_nums = get_all_numbers(recent)
    counter = Counter(all_nums)
    return {num: counter.get(num, 0) for num in range(1, 46)}


def hot_cold_numbers(draws, n=50):
    """핫/콜드 번호 (최근 N회차 기준)"""
    freq = recent_frequency(draws, n)
    sorted_nums = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    hot = [{'number': num, 'count': cnt} for num, cnt in sorted_nums[:9]]
    cold = [{'number': num, 'count': cnt} for num, cnt in sorted_nums[-9:]]
    return hot, cold


def range_analysis(draws):
    """번호 구간별 출현 비율"""
    all_nums = get_all_numbers(draws)
    ranges = {
        '1-10': 0, '11-20': 0, '21-30': 0, '31-40': 0, '41-45': 0
    }
    for n in all_nums:
        if n <= 10:
            ranges['1-10'] += 1
        elif n <= 20:
            ranges['11-20'] += 1
        elif n <= 30:
            ranges['21-30'] += 1
        elif n <= 40:
            ranges['31-40'] += 1
        else:
            ranges['41-45'] += 1
    total = len(all_nums)
    return {k: round(v / total * 100, 1) for k, v in ranges.items()}


def odd_even_analysis(draws):
    """홀짝 비율 분석"""
    results = []
    for d in draws:
        odds = sum(1 for n in d['numbers'] if n % 2 == 1)
        evens = 6 - odds
        results.append({'draw_no': d['draw_no'], 'odd': odds, 'even': evens})

    # 평균 홀짝 비율
    avg_odd = np.mean([r['odd'] for r in results])
    avg_even = np.mean([r['even'] for r in results])

    # 홀짝 조합별 빈도
    combo_counter = Counter(f"{r['odd']}:{r['even']}" for r in results)
    combos = [{'combo': k, 'count': v} for k, v in
              sorted(combo_counter.items(), key=lambda x: x[1], reverse=True)]

    return {
        'avg_odd': round(avg_odd, 2),
        'avg_even': round(avg_even, 2),
        'combos': combos
    }


def consecutive_analysis(draws):
    """연속번호 패턴 분석"""
    has_consecutive = 0
    for d in draws:
        nums = sorted(d['numbers'])
        for i in range(len(nums) - 1):
            if nums[i + 1] - nums[i] == 1:
                has_consecutive += 1
                break
    total = len(draws)
    return {
        'consecutive_draws': has_consecutive,
        'total_draws': total,
        'percentage': round(has_consecutive / total * 100, 1) if total > 0 else 0
    }


def sum_analysis(draws):
    """당첨번호 합계 분석"""
    sums = [sum(d['numbers']) for d in draws]
    return {
        'avg': round(np.mean(sums), 1),
        'min': int(np.min(sums)),
        'max': int(np.max(sums)),
        'std': round(np.std(sums), 1),
    }


def predict_numbers(draws, num_sets=5):
    """
    가중 확률 기반 번호 예측
    - 전체 출현 빈도 (30%)
    - 최근 50회차 출현 빈도 (40%)
    - 구간 균형 보정 (20%)
    - 랜덤성 (10%)
    """
    total_freq = frequency_analysis(draws)
    recent_freq = recent_frequency(draws, 50)

    # 가중치 계산
    weights = {}
    for n in range(1, 46):
        w_total = total_freq[n] / max(total_freq.values()) if max(total_freq.values()) > 0 else 0
        w_recent = recent_freq[n] / max(recent_freq.values()) if max(recent_freq.values()) > 0 else 0
        w_range = 1.0  # 기본 구간 가중치
        w_random = random.random()

        weights[n] = (w_total * 0.3) + (w_recent * 0.4) + (w_range * 0.2) + (w_random * 0.1)

    predictions = []
    for _ in range(num_sets):
        # 가중치에 약간의 랜덤성 추가
        adjusted = {n: w + random.uniform(0, 0.15) for n, w in weights.items()}
        sorted_nums = sorted(adjusted.items(), key=lambda x: x[1], reverse=True)

        # 구간 균형을 고려하여 선택
        selected = []
        range_counts = {'1-10': 0, '11-20': 0, '21-30': 0, '31-40': 0, '41-45': 0}

        for num, _ in sorted_nums:
            if len(selected) >= 6:
                break
            r = get_range(num)
            max_per_range = 3 if r != '41-45' else 2
            if range_counts[r] < max_per_range:
                selected.append(num)
                range_counts[r] += 1

        predictions.append(sorted(selected[:6]))

    return predictions


def get_range(n):
    if n <= 10:
        return '1-10'
    elif n <= 20:
        return '11-20'
    elif n <= 30:
        return '21-30'
    elif n <= 40:
        return '31-40'
    else:
        return '41-45'


def get_full_analysis(draws):
    """전체 분석 결과 반환"""
    hot, cold = hot_cold_numbers(draws)
    return {
        'total_draws': len(draws),
        'latest_draw': draws[-1] if draws else None,
        'frequency': frequency_analysis(draws),
        'recent_frequency': recent_frequency(draws, 50),
        'hot_numbers': hot,
        'cold_numbers': cold,
        'range_analysis': range_analysis(draws),
        'odd_even': odd_even_analysis(draws),
        'consecutive': consecutive_analysis(draws),
        'sum_stats': sum_analysis(draws),
        'predictions': predict_numbers(draws),
    }
