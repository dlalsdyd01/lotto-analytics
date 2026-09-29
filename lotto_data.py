import requests
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lotto_cache.json')

# smok95 GitHub Pages API (동행복권 데이터 미러)
ALL_DATA_URL = 'https://smok95.github.io/lotto/results/all.json'

# 동행복권 공식 API (백업용)
DHLOTTERY_URL = 'https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={}'

KST = timezone(timedelta(hours=9))
FIRST_DRAW_DATE = datetime(2002, 12, 7, tzinfo=KST)
# 추첨은 토요일 20:45 — 21시 이후를 해당 회차 발표 시점으로 간주
DRAW_OFFSET = timedelta(hours=21)

_lock = threading.Lock()
_draws = []


def get_latest_draw_number():
    """현재 시각(KST) 기준 이미 추첨이 끝난 최신 회차 번호"""
    elapsed = datetime.now(KST) - FIRST_DRAW_DATE - DRAW_OFFSET
    return elapsed.days // 7 + 1


def _convert_smok95_format(item):
    divisions = item.get('divisions') or [{}]
    date_str = item.get('date', '').split('T')[0]
    return {
        'draw_no': item['draw_no'],
        'date': date_str,
        'numbers': sorted(item['numbers']),
        'bonus': item['bonus_no'],
        'prize_1st': divisions[0].get('prize', 0),
        'winners_1st': divisions[0].get('winners', 0),
    }


def _fetch_all_from_mirror():
    try:
        resp = requests.get(ALL_DATA_URL, timeout=30)
        unique = {d['draw_no']: d for d in map(_convert_smok95_format, resp.json())}
        return sorted(unique.values(), key=lambda x: x['draw_no'])
    except Exception as e:
        print(f'API 오류: {e}')
        return []


def _fetch_draw_from_dhlottery(draw_no):
    try:
        data = requests.get(DHLOTTERY_URL.format(draw_no), timeout=10).json()
        if data.get('returnValue') != 'success':
            return None
        return {
            'draw_no': data['drwNo'],
            'date': data['drwNoDate'],
            'numbers': sorted(data[f'drwtNo{i}'] for i in range(1, 7)),
            'bonus': data['bnusNo'],
            'prize_1st': data.get('firstWinamnt', 0),
            'winners_1st': data.get('firstPrzwnerCo', 0),
        }
    except Exception as e:
        print(f'동행복권 API 오류 (회차 {draw_no}): {e}')
        return None


def load_cache():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f) or []
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_cache(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def refresh_draws():
    """캐시에 없는 최신 회차를 수집해 메모리/캐시를 갱신"""
    global _draws
    with _lock:
        draws = _draws or load_cache()
        expected = get_latest_draw_number()
        cached_max = draws[-1]['draw_no'] if draws else 0
        missing = range(cached_max + 1, expected + 1)

        if draws and 0 < len(missing) <= 3:
            added = [d for d in map(_fetch_draw_from_dhlottery, missing) if d]
            draws = draws + added
            if len(added) == len(missing):
                missing = []

        if not draws or missing:
            fetched = _fetch_all_from_mirror()
            if fetched and fetched[-1]['draw_no'] >= (draws[-1]['draw_no'] if draws else 0):
                draws = fetched

        if draws and draws is not _draws:
            draws.sort(key=lambda x: x['draw_no'])
            if not _draws or draws[-1]['draw_no'] != _draws[-1]['draw_no']:
                save_cache(draws)
            _draws = draws
        return _draws


def get_draws():
    """메모리 데이터 반환 (백그라운드 갱신 전이면 캐시 파일)"""
    return _draws or load_cache()


def _auto_refresh_loop():
    """30분마다 새 회차 확인"""
    while True:
        try:
            refresh_draws()
        except Exception as e:
            print(f'[자동갱신] 오류: {e}')
        time.sleep(1800)


def start_auto_refresh():
    threading.Thread(target=_auto_refresh_loop, daemon=True).start()
