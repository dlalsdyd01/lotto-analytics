import requests
import json
import os
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lotto_cache.json')

# smok95 GitHub Pages API (동행복권 데이터 미러)
ALL_DATA_URL = 'https://smok95.github.io/lotto/results/all.json'
LATEST_URL = 'https://smok95.github.io/lotto/results/latest.json'

# 동행복권 공식 API (백업용)
DHLOTTERY_URL = 'https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={}'

FIRST_DRAW_DATE = datetime(2002, 12, 7)

# 데이터 수집 상태
fetch_status = {'running': False, 'progress': 0, 'total': 0}


def get_latest_draw_number():
    """현재 날짜 기준 최신 회차 번호 계산"""
    today = datetime.now()
    days_diff = (today - FIRST_DRAW_DATE).days
    return days_diff // 7 + 1


def _convert_smok95_format(item):
    """smok95 API 데이터를 앱 내부 형식으로 변환"""
    divisions = item.get('divisions', [])
    prize_1st = 0
    winners_1st = 0
    if divisions and len(divisions) > 0:
        first = divisions[0]
        prize_1st = first.get('prize', 0)
        winners_1st = first.get('winners', 0)

    date_str = item.get('date', '')
    if 'T' in date_str:
        date_str = date_str.split('T')[0]

    return {
        'draw_no': item['draw_no'],
        'date': date_str,
        'numbers': sorted(item['numbers']),
        'bonus': item['bonus_no'],
        'prize_1st': prize_1st,
        'winners_1st': winners_1st,
    }


def fetch_all_from_api():
    """smok95 API에서 전체 데이터를 한 번에 가져오기"""
    global fetch_status
    fetch_status = {'running': True, 'progress': 0, 'total': 1}
    try:
        resp = requests.get(ALL_DATA_URL, timeout=30)
        raw_data = resp.json()
        fetch_status = {'running': True, 'progress': 50, 'total': 100}

        converted = [_convert_smok95_format(item) for item in raw_data]
        # 회차 번호 기준 중복 제거
        seen = set()
        result = []
        for item in converted:
            if item['draw_no'] not in seen:
                seen.add(item['draw_no'])
                result.append(item)
        result.sort(key=lambda x: x['draw_no'])
        fetch_status = {'running': False, 'progress': 100, 'total': 100}
        return result
    except Exception as e:
        print(f'API 오류: {e}')
        fetch_status = {'running': False, 'progress': 0, 'total': 0}
        return []


def load_cache():
    """로컬 캐시 파일에서 데이터 로드"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data and len(data) > 0:
                    return data
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_cache(data):
    """데이터를 로컬 캐시 파일에 저장"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_all_draws():
    """모든 회차 데이터 수집 (캐시 활용)"""
    cached = load_cache()
    if cached and len(cached) > 1000:
        # 캐시가 충분하면 최신 데이터만 확인
        try:
            resp = requests.get(LATEST_URL, timeout=10)
            latest = _convert_smok95_format(resp.json())
            cached_nos = {d['draw_no'] for d in cached}
            if latest['draw_no'] not in cached_nos:
                cached.append(latest)
                cached.sort(key=lambda x: x['draw_no'])
                save_cache(cached)
        except Exception:
            pass
        return cached

    # 전체 데이터 새로 가져오기
    all_data = fetch_all_from_api()
    if all_data:
        save_cache(all_data)
    return all_data


def get_draws():
    """캐시된 데이터 반환 (없으면 전체 수집)"""
    cached = load_cache()
    if cached and len(cached) > 100:
        return cached
    return fetch_all_draws()


def get_fetch_status():
    return fetch_status
