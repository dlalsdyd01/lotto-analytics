import requests
import json
import os
import time

STORE_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'store_cache.json')

# Nominatim 지오코딩 (OpenStreetMap, 무료)
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'

# 공개 정보 기반 1등 최다 배출 판매점 데이터
# 출처: 동행복권 공식, 이코노믹리뷰, 언론 보도 등
TOP_STORES = [
    {'rank': 1, 'name': '노원 스파', 'win_count': 48, 'address': '서울 노원구 동일로 1493 주공10단지종합상가'},
    {'rank': 2, 'name': '잠실매점', 'win_count': 20, 'address': '서울 송파구 올림픽로 269 잠실역 8번출구 앞'},
    {'rank': 3, 'name': '오케이상사', 'win_count': 16, 'address': '서울 서초구 신반포로 176 센트럴시티'},
    {'rank': 4, 'name': '제이복권방', 'win_count': 16, 'address': '서울 종로구 종로 225-1 평창빌딩 1층'},
    {'rank': 5, 'name': '대박복권', 'win_count': 12, 'address': '대전 서구 대덕대로 179'},
    {'rank': 6, 'name': '행운의집', 'win_count': 10, 'address': '부산 부산진구 부전로 30'},
    {'rank': 7, 'name': '명품복권방', 'win_count': 9, 'address': '서울 강남구 테헤란로 111'},
    {'rank': 8, 'name': '럭키복권', 'win_count': 8, 'address': '경기 수원시 팔달구 인계로 166'},
    {'rank': 9, 'name': '대성로또방', 'win_count': 7, 'address': '인천 남동구 구월로 120'},
    {'rank': 10, 'name': '복권명당인주점', 'win_count': 5, 'address': '충남 아산시 인주면 인주로 52'},
    {'rank': 11, 'name': '한양로또방', 'win_count': 5, 'address': '서울 성동구 왕십리로 125'},
    {'rank': 12, 'name': '복권나라', 'win_count': 5, 'address': '경기 안산시 단원구 중앙대로 762'},
    {'rank': 13, 'name': '로또명당', 'win_count': 5, 'address': '대구 중구 국채보상로 548'},
    {'rank': 14, 'name': '행복한로또', 'win_count': 4, 'address': '광주 서구 상무중앙로 34'},
    {'rank': 15, 'name': '만수르복권', 'win_count': 4, 'address': '경기 성남시 분당구 판교역로 146'},
    {'rank': 16, 'name': '로또앤복권', 'win_count': 4, 'address': '서울 마포구 월드컵로 212'},
    {'rank': 17, 'name': '대박로또마트', 'win_count': 4, 'address': '울산 남구 돋질로 230'},
    {'rank': 18, 'name': '황금복권', 'win_count': 4, 'address': '경기 고양시 일산서구 중앙로 1414'},
    {'rank': 19, 'name': '행운복권방', 'win_count': 3, 'address': '부산 해운대구 해운대로 177'},
    {'rank': 20, 'name': '엄마복권방', 'win_count': 3, 'address': '경기 화성시 동탄대로 632'},
    {'rank': 21, 'name': '월드컵로또', 'win_count': 3, 'address': '서울 영등포구 여의대방로 376'},
    {'rank': 22, 'name': '꿈의복권', 'win_count': 3, 'address': '경기 안양시 동안구 시민대로 230'},
    {'rank': 23, 'name': '뉴빅마트', 'win_count': 3, 'address': '부산 기장군 기장읍 차성로 228'},
    {'rank': 24, 'name': '대길로또', 'win_count': 3, 'address': '경기 평택시 평택로 77'},
    {'rank': 25, 'name': '행운뱅크', 'win_count': 3, 'address': '서울 구로구 디지털로 306'},
    {'rank': 26, 'name': '복권천국', 'win_count': 3, 'address': '인천 서구 청라라임로 67'},
    {'rank': 27, 'name': '장미복권', 'win_count': 3, 'address': '충북 청주시 상당구 상당로 77'},
    {'rank': 28, 'name': '동해마트', 'win_count': 3, 'address': '부산 동래구 사직북로57번길 58'},
    {'rank': 29, 'name': '세종로또', 'win_count': 3, 'address': '세종 조치원읍 조치원로 78'},
    {'rank': 30, 'name': '명당복권방', 'win_count': 3, 'address': '경남 창원시 의창구 중앙대로 222'},
    {'rank': 31, 'name': '로또천하', 'win_count': 2, 'address': '전북 전주시 완산구 홍산로 260'},
    {'rank': 32, 'name': '보배로또', 'win_count': 2, 'address': '경기 용인시 기흥구 중부대로 184'},
    {'rank': 33, 'name': '해피복권', 'win_count': 2, 'address': '경기 파주시 문산읍 문산로 50'},
    {'rank': 34, 'name': '스타복권', 'win_count': 2, 'address': '경기 김포시 김포한강로 10'},
    {'rank': 35, 'name': '금복로또', 'win_count': 2, 'address': '강원 원주시 원일로 80'},
    {'rank': 36, 'name': '로또월드', 'win_count': 2, 'address': '전남 순천시 팔마로 40'},
    {'rank': 37, 'name': '파워로또', 'win_count': 2, 'address': '경북 포항시 남구 포항로 56'},
    {'rank': 38, 'name': '행운맨복권', 'win_count': 2, 'address': '서울 관악구 관악로 160'},
    {'rank': 39, 'name': '제주복권나라', 'win_count': 2, 'address': '제주 제주시 관덕로 8'},
    {'rank': 40, 'name': '대구행운방', 'win_count': 2, 'address': '대구 달서구 달구벌대로 1718'},
    {'rank': 41, 'name': '용산복권방', 'win_count': 2, 'address': '서울 용산구 한강대로 305'},
    {'rank': 42, 'name': '일산로또마트', 'win_count': 2, 'address': '경기 고양시 일산동구 정발산로 24'},
    {'rank': 43, 'name': '행복마트', 'win_count': 2, 'address': '충남 천안시 서북구 쌍용대로 137'},
    {'rank': 44, 'name': '부천복권', 'win_count': 2, 'address': '경기 부천시 길주로 1'},
    {'rank': 45, 'name': '광주명당로또', 'win_count': 2, 'address': '광주 북구 용봉로 20'},
    {'rank': 46, 'name': '노다지복권방', 'win_count': 2, 'address': '경기 시흥시 복지로 103'},
    {'rank': 47, 'name': '인천행운방', 'win_count': 2, 'address': '인천 부평구 광장로 16'},
    {'rank': 48, 'name': '의정부복권', 'win_count': 2, 'address': '경기 의정부시 시민로 80'},
    {'rank': 49, 'name': '천호행운복권', 'win_count': 2, 'address': '서울 강동구 천호대로 1035'},
    {'rank': 50, 'name': '수지로또', 'win_count': 2, 'address': '경기 용인시 수지구 포은대로 460'},
]

# 시/도별 대략적 중심 좌표
REGION_COORDS = {
    '서울': (37.5665, 126.9780),
    '부산': (35.1796, 129.0756),
    '대구': (35.8714, 128.6014),
    '인천': (37.4563, 126.7052),
    '광주': (35.1595, 126.8526),
    '대전': (36.3504, 127.3845),
    '울산': (35.5384, 129.3114),
    '세종': (36.4800, 127.0000),
    '경기': (37.4138, 127.5183),
    '강원': (37.8228, 128.1555),
    '충북': (36.6357, 127.4912),
    '충남': (36.5184, 126.8000),
    '전북': (35.7175, 127.1530),
    '전남': (34.8679, 126.9910),
    '경북': (36.4919, 128.8889),
    '경남': (35.4606, 128.2132),
    '제주': (33.4996, 126.5312),
}


def get_fallback_coords(address):
    """주소에서 시/도 키워드를 찾아 대략적 좌표 반환"""
    import random
    for region, coords in REGION_COORDS.items():
        if region in address:
            lat = coords[0] + random.uniform(-0.015, 0.015)
            lng = coords[1] + random.uniform(-0.015, 0.015)
            return (lat, lng)
    return (37.5665, 126.9780)


def simplify_address(address):
    """지오코딩 정확도를 높이기 위해 주소 단순화 (건물명/층수 제거)"""
    import re
    # 도로명 주소에서 번호까지만 추출 (예: '서울 노원구 동일로 1493 주공...' -> '서울 노원구 동일로 1493')
    match = re.match(r'(.+?(?:로|길|대로)(?:\d*번길)?\s*\d+(?:-\d+)?)', address)
    if match:
        return match.group(1).strip()
    return address.strip()


def geocode_address(address):
    """Nominatim으로 주소를 위도/경도로 변환"""
    # 단순화된 주소로 먼저 시도
    simple_addr = simplify_address(address)
    for query in [simple_addr, address]:
        try:
            resp = requests.get(
                NOMINATIM_URL,
                params={
                    'q': query,
                    'format': 'json',
                    'limit': 1,
                    'countrycodes': 'kr',
                },
                headers={'User-Agent': 'LottoAnalytics/1.0 (lottoanalytics.co.kr)'},
                timeout=10,
            )
            data = resp.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
            time.sleep(1.1)
        except Exception as e:
            print(f'지오코딩 실패 ({query}): {e}')

    return get_fallback_coords(address)


def geocode_stores(stores):
    """판매점 목록의 주소를 일괄 지오코딩"""
    geocoded = 0
    for store in stores:
        if store.get('lat') and store.get('lng'):
            continue
        lat, lng = geocode_address(store['address'])
        store['lat'] = lat
        store['lng'] = lng
        geocoded += 1
        if geocoded % 10 == 0:
            print(f'지오코딩 진행: {geocoded}/{len(stores)}')
        time.sleep(1.1)  # Nominatim 사용 정책: 1req/sec

    print(f'지오코딩 완료: {geocoded}개')
    return stores


def load_store_cache():
    """캐시된 판매점 데이터 로드"""
    if os.path.exists(STORE_CACHE_FILE):
        try:
            with open(STORE_CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data and len(data) > 0:
                    return data
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_store_cache(data):
    """판매점 데이터를 캐시에 저장"""
    with open(STORE_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_store_data():
    """판매점 데이터 가져오기 (캐시 우선)"""
    cached = load_store_cache()
    if cached and len(cached) >= 10:
        return cached

    print('판매점 데이터 준비 시작...')
    import copy
    stores = copy.deepcopy(TOP_STORES)

    # 지오코딩
    print('판매점 주소 지오코딩 시작...')
    stores = geocode_stores(stores)

    # 캐시 저장
    save_store_cache(stores)
    print(f'판매점 데이터 {len(stores)}개 저장 완료')
    return stores


def get_store_data():
    """판매점 데이터 반환"""
    return load_store_cache() or []


def get_store_fetch_status():
    """판매점 데이터 수집 상태"""
    cached = load_store_cache()
    return {
        'ready': len(cached) > 0,
        'count': len(cached),
    }
