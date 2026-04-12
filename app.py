from flask import Flask, render_template, jsonify, request, Response
from lotto_data import get_draws, fetch_all_draws, get_latest_draw_number, load_cache, get_fetch_status
from analysis import get_full_analysis, predict_numbers, frequency_analysis, sum_analysis
from store_data import fetch_store_data, get_store_data, get_store_fetch_status
from collections import Counter
import threading
import os
import json

app = Flask(__name__)


@app.after_request
def add_cache_headers(response):
    if request.path.startswith('/static/'):
        response.cache_control.max_age = 86400
        response.cache_control.public = True
    return response

# 백그라운드 데이터 수집
_data_ready = threading.Event()


_store_ready = threading.Event()


def _bg_fetch():
    print('데이터 수집 시작...')
    draws = fetch_all_draws()
    print(f'총 {len(draws)}회차 데이터 로드 완료!')
    _data_ready.set()

    # 판매점 데이터도 백그라운드에서 수집
    print('판매점 데이터 수집 시작...')
    stores = fetch_store_data()
    print(f'판매점 {len(stores)}개 로드 완료!')
    _store_ready.set()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """데이터 수집 상태 반환"""
    status = get_fetch_status()
    cached = load_cache()
    return jsonify({
        'ready': _data_ready.is_set(),
        'cached_count': len(cached),
        'fetching': status['running'],
        'progress': status['progress'],
        'total': status['total'],
    })


@app.route('/api/data')
def api_data():
    """전체 당첨 데이터 + 분석 결과 반환"""
    if not _data_ready.is_set():
        # 데이터가 아직 준비되지 않은 경우 캐시된 것이라도 반환
        cached = load_cache()
        if len(cached) >= 10:
            analysis = get_full_analysis(cached)
            return jsonify({'draws': cached, 'analysis': analysis})
        return jsonify({'error': 'loading', 'message': '데이터를 수집하는 중입니다...'}), 202

    draws = get_draws()
    analysis = get_full_analysis(draws)
    return jsonify({'draws': draws, 'analysis': analysis})


@app.route('/api/draws')
def api_draws():
    """당첨번호 목록 (페이지네이션)"""
    draws = load_cache() if not _data_ready.is_set() else get_draws()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '', type=str)

    sorted_draws = sorted(draws, key=lambda x: x['draw_no'], reverse=True)

    if search:
        sorted_draws = [d for d in sorted_draws if str(d['draw_no']).startswith(search)]

    total = len(sorted_draws)
    start = (page - 1) * per_page
    end = start + per_page
    page_draws = sorted_draws[start:end]

    return jsonify({
        'draws': page_draws,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': max(1, (total + per_page - 1) // per_page)
    })


@app.route('/api/predict')
def api_predict():
    """새로운 예측 번호 생성"""
    draws = load_cache() if not _data_ready.is_set() else get_draws()
    if not draws:
        return jsonify({'error': '데이터가 없습니다.'}), 500
    predictions = predict_numbers(draws)
    next_draw = get_latest_draw_number() + 1
    return jsonify({
        'next_draw': next_draw,
        'predictions': predictions
    })


@app.route('/api/stores')
def api_stores():
    """1등 배출 판매점 데이터 반환"""
    stores = get_store_data()
    status = get_store_fetch_status()
    return jsonify({
        'ready': status['ready'],
        'count': status['count'],
        'stores': stores,
    })


@app.route('/draw/<int:draw_no>')
def draw_detail(draw_no):
    """회차별 상세 분석 페이지"""
    draws = load_cache() if not _data_ready.is_set() else get_draws()
    if not draws:
        return render_template('page.html', title='데이터 로딩 중', description='', content='<p>데이터를 수집하는 중입니다. 잠시 후 다시 시도해주세요.</p>')

    draw_map = {d['draw_no']: d for d in draws}
    draw = draw_map.get(draw_no)
    if not draw:
        return render_template('page.html', title='회차를 찾을 수 없습니다', description='', content=f'<p>제 {draw_no}회 데이터가 없습니다.</p>'), 404

    nums = draw['numbers']
    number_sum = sum(nums)
    odd_count = sum(1 for n in nums if n % 2 == 1)
    even_count = 6 - odd_count
    low_count = sum(1 for n in nums if n <= 23)
    high_count = 6 - low_count

    # 구간 분포
    range_dist = {'1-10': 0, '11-20': 0, '21-30': 0, '31-40': 0, '41-45': 0}
    for n in nums:
        if n <= 10: range_dist['1-10'] += 1
        elif n <= 20: range_dist['11-20'] += 1
        elif n <= 30: range_dist['21-30'] += 1
        elif n <= 40: range_dist['31-40'] += 1
        else: range_dist['41-45'] += 1

    # 연속번호
    sorted_nums = sorted(nums)
    consecutive_pairs = []
    for i in range(len(sorted_nums) - 1):
        if sorted_nums[i + 1] - sorted_nums[i] == 1:
            consecutive_pairs.append(f'{sorted_nums[i]}-{sorted_nums[i+1]}')

    # 끝수 분포
    last_digit_counter = Counter(n % 10 for n in nums)
    last_digits = ', '.join(f'{d}끝: {c}개' for d, c in sorted(last_digit_counter.items()))

    # 역대 빈도
    freq = frequency_analysis(draws)
    number_freq = {n: freq.get(n, 0) for n in sorted(nums + [draw['bonus']])}
    max_freq = max(number_freq.values()) if number_freq else 1

    # 합계 평균
    s_stats = sum_analysis(draws)
    avg_sum = s_stats['avg']
    abs_diff = abs(number_sum - avg_sum)

    # 당첨금 표시
    prize = draw.get('prize_1st', 0)
    if prize >= 100000000:
        prize_display = f'{prize // 100000000}억 {(prize % 100000000) // 10000:,}만원' if prize % 100000000 else f'{prize // 100000000}억원'
    elif prize > 0:
        prize_display = f'{prize:,}원'
    else:
        prize_display = '정보 없음'

    winners = draw.get('winners_1st', 0)
    per_person = prize // winners if winners > 0 and prize > 0 else 0
    if per_person >= 100000000:
        per_person_prize = f'약 {per_person // 100000000}억원'
    elif per_person > 0:
        per_person_prize = f'약 {per_person // 10000:,}만원'
    else:
        per_person_prize = '정보 없음'

    latest_no = draws[-1]['draw_no']
    next_draw = draw_no < latest_no

    return render_template('draw.html',
        draw=draw,
        number_sum=number_sum,
        odd_count=odd_count,
        even_count=even_count,
        low_count=low_count,
        high_count=high_count,
        range_dist=range_dist,
        has_consecutive=len(consecutive_pairs) > 0,
        consecutive_nums=', '.join(consecutive_pairs),
        last_digits=last_digits,
        number_freq=number_freq,
        max_freq=max_freq,
        avg_sum=avg_sum,
        abs_diff=abs_diff,
        prize_display=prize_display,
        winners_1st=winners,
        per_person_prize=per_person_prize,
        next_draw=next_draw,
    )


@app.route('/privacy')
def privacy():
    content = """
    <p style="color:var(--text-2);margin-bottom:8px;font-size:13px;">최종 수정일: 2026년 3월 1일</p>
    <h3 style="margin:20px 0 10px;font-size:17px;">1. 수집하는 개인정보</h3>
    <p>Lotto Lab은 서비스 이용 시 다음 정보를 자동으로 수집할 수 있습니다:</p>
    <ul><li>접속 IP 주소, 브라우저 종류, 접속 시간</li><li>Google Analytics를 통한 익명화된 이용 통계</li></ul>
    <p>Lotto Lab은 회원가입을 요구하지 않으며, 이름, 이메일 등 개인을 식별할 수 있는 정보를 직접 수집하지 않습니다.</p>

    <h3 style="margin:20px 0 10px;font-size:17px;">2. 개인정보 이용 목적</h3>
    <p>수집된 정보는 다음 목적으로만 사용됩니다:</p>
    <ul><li>서비스 이용 통계 분석 및 개선</li><li>서비스 안정성 확보</li></ul>

    <h3 style="margin:20px 0 10px;font-size:17px;">3. 개인정보 보관 기간</h3>
    <p>자동 수집된 로그 정보는 최대 1년간 보관 후 파기합니다.</p>

    <h3 style="margin:20px 0 10px;font-size:17px;">4. 제3자 제공</h3>
    <p>Lotto Lab은 이용자의 개인정보를 제3자에게 제공하지 않습니다. 단, 다음 서비스를 통해 익명화된 정보가 수집될 수 있습니다:</p>
    <ul>
        <li><strong>Google Analytics</strong> - 웹사이트 이용 통계 (Google 개인정보처리방침 적용)</li>
        <li><strong>Google AdSense</strong> - 맞춤형 광고 제공 (Google 광고 정책 적용)</li>
    </ul>

    <h3 style="margin:20px 0 10px;font-size:17px;">5. 쿠키 사용</h3>
    <p>본 사이트는 Google Analytics 및 Google AdSense를 위해 쿠키를 사용합니다. 브라우저 설정에서 쿠키를 거부할 수 있으나, 일부 서비스 이용이 제한될 수 있습니다.</p>

    <h3 style="margin:20px 0 10px;font-size:17px;">6. 이용자의 권리</h3>
    <p>이용자는 언제든지 쿠키 삭제, 광고 개인화 설정 변경 등을 통해 개인정보 수집을 제한할 수 있습니다.</p>

    <h3 style="margin:20px 0 10px;font-size:17px;">7. 문의</h3>
    <p>개인정보 관련 문의는 <a href="/contact">연락처 페이지</a>를 통해 주세요.</p>
    """
    return render_template('page.html', title='개인정보처리방침', description='Lotto Lab 개인정보처리방침', content=content)


@app.route('/terms')
def terms():
    content = """
    <p style="color:var(--text-2);margin-bottom:8px;font-size:13px;">최종 수정일: 2026년 3월 1일</p>
    <h3 style="margin:20px 0 10px;font-size:17px;">1. 서비스 소개</h3>
    <p>Lotto Lab은 과거 로또 당첨 데이터를 분석하여 통계적 인사이트를 제공하는 웹 서비스입니다. 본 서비스는 교육 및 통계 분석 목적으로 제공됩니다.</p>

    <h3 style="margin:20px 0 10px;font-size:17px;">2. 면책 조항</h3>
    <p><strong>로또는 완전한 무작위 추첨이며, 과거 데이터로 미래를 예측할 수 없습니다.</strong></p>
    <ul>
        <li>본 서비스에서 제공하는 분석 결과 및 예측 번호는 통계적 참고용입니다.</li>
        <li>당첨을 보장하지 않으며, 이를 근거로 한 구매에 대해 책임지지 않습니다.</li>
        <li>책임감 있는 구매를 권장합니다.</li>
    </ul>

    <h3 style="margin:20px 0 10px;font-size:17px;">3. 지적재산권</h3>
    <p>본 서비스의 디자인, 코드, 분석 알고리즘은 Lotto Lab에 귀속됩니다. 당첨번호 데이터의 저작권은 동행복권에 있습니다.</p>

    <h3 style="margin:20px 0 10px;font-size:17px;">4. 서비스 이용</h3>
    <ul>
        <li>본 서비스는 무료로 제공됩니다.</li>
        <li>서비스는 사전 고지 없이 변경되거나 중단될 수 있습니다.</li>
        <li>비정상적인 방법(자동화 도구 등)으로 서비스에 접근하는 것을 금지합니다.</li>
    </ul>

    <h3 style="margin:20px 0 10px;font-size:17px;">5. 광고</h3>
    <p>본 서비스는 Google AdSense를 통해 광고를 게재할 수 있습니다. 광고 내용은 Lotto Lab과 무관합니다.</p>

    <h3 style="margin:20px 0 10px;font-size:17px;">6. 약관 변경</h3>
    <p>본 약관은 사전 고지 후 변경될 수 있으며, 변경된 약관은 본 페이지에 게시됩니다.</p>
    """
    return render_template('page.html', title='이용약관', description='Lotto Lab 이용약관', content=content)


@app.route('/about')
def about():
    content = """
    <h3 style="margin:20px 0 10px;font-size:17px;">Lotto Lab이란?</h3>
    <p>Lotto Lab은 2002년 첫 회차부터 현재까지의 모든 로또 6/45 당첨 데이터를 수집, 분석하여 통계적 인사이트를 제공하는 서비스입니다.</p>

    <h3 style="margin:20px 0 10px;font-size:17px;">주요 기능</h3>
    <ul>
        <li><strong>당첨 확인</strong> - 내 번호가 최신 회차에 당첨되었는지 확인</li>
        <li><strong>역대 당첨번호</strong> - 2002년부터 현재까지 모든 당첨번호 조회</li>
        <li><strong>통계 분석</strong> - 번호 출현 빈도, 핫/콜드 번호, 홀짝 분석, 구간별 비율 등</li>
        <li><strong>번호 예측</strong> - 가중 확률 기반 AI 번호 생성 (참고용)</li>
        <li><strong>판매점 지도</strong> - 1등 배출 판매점 위치 확인</li>
        <li><strong>회차별 분석</strong> - 매 회차의 상세 통계 분석 페이지</li>
    </ul>

    <h3 style="margin:20px 0 10px;font-size:17px;">데이터 출처</h3>
    <p>당첨번호 데이터는 동행복권 공식 데이터를 기반으로 합니다.</p>

    <h3 style="margin:20px 0 10px;font-size:17px;">기술 스택</h3>
    <p>Python (Flask), Pandas, NumPy, Chart.js, Leaflet.js, OpenStreetMap</p>

    <div class="info-warn">
        <strong>주의사항:</strong> 로또는 완전한 무작위 추첨입니다. 본 서비스의 모든 분석과 예측은 통계적 참고용이며, 당첨을 보장하지 않습니다. 책임감 있는 구매를 권장합니다.
    </div>
    """
    return render_template('page.html', title='소개', description='Lotto Lab 소개 - 로또 데이터 분석 및 통계 서비스', content=content)


@app.route('/faq')
def faq():
    content = """
    <div class="faq-list">
        <div class="faq-item">
            <h3 style="margin:0 0 10px;font-size:17px;">Q. 로또 번호는 어떻게 추첨되나요?</h3>
            <p>로또 6/45는 1부터 45까지의 숫자 중 6개의 당첨번호와 1개의 보너스 번호를 추첨합니다. 매주 토요일 오후 8시 45분에 MBC에서 생방송으로 추첨이 진행되며, 완전한 무작위 방식으로 이루어집니다.</p>
        </div>

        <div class="faq-item">
            <h3 style="margin:0 0 10px;font-size:17px;">Q. 로또 당첨 확률은 얼마인가요?</h3>
            <p>각 등수별 당첨 확률은 다음과 같습니다:</p>
            <ul>
                <li><strong>1등</strong> (6개 일치): 1/8,145,060 (약 0.0000123%)</li>
                <li><strong>2등</strong> (5개 + 보너스): 1/1,357,510 (약 0.0000737%)</li>
                <li><strong>3등</strong> (5개 일치): 1/35,724 (약 0.0028%)</li>
                <li><strong>4등</strong> (4개 일치): 1/733 (약 0.14%)</li>
                <li><strong>5등</strong> (3개 일치): 1/45 (약 2.22%)</li>
            </ul>
        </div>

        <div class="faq-item">
            <h3 style="margin:0 0 10px;font-size:17px;">Q. 로또 당첨금에 세금이 붙나요?</h3>
            <p>네, 로또 당첨금에는 세금이 부과됩니다:</p>
            <ul>
                <li><strong>5만원 이하</strong> (5등): 비과세</li>
                <li><strong>5만원 초과 ~ 3억원 이하</strong>: 소득세 20% + 지방소득세 2% = <strong>22%</strong></li>
                <li><strong>3억원 초과</strong>: 소득세 30% + 지방소득세 3% = <strong>33%</strong></li>
            </ul>
            <p>예를 들어, 1등 당첨금이 20억원이라면 3억원까지는 22%, 나머지 17억원은 33%가 적용되어 실수령액은 약 12억 2,700만원입니다.</p>
        </div>

        <div class="faq-item">
            <h3 style="margin:0 0 10px;font-size:17px;">Q. 로또 당첨금은 어디서 수령하나요?</h3>
            <ul>
                <li><strong>5등 (5,000원)</strong>: 로또 판매점 어디서나 수령 가능</li>
                <li><strong>4등 (50,000원)</strong>: 로또 판매점 또는 농협 지점</li>
                <li><strong>3등</strong>: 농협 지점</li>
                <li><strong>1~2등</strong>: 농협은행 본점 (서울 중구)에서 수령</li>
            </ul>
            <p>당첨금 지급 기한은 지급 개시일로부터 1년입니다. 기한 내 수령하지 않으면 복권기금으로 귀속됩니다.</p>
        </div>

        <div class="faq-item">
            <h3 style="margin:0 0 10px;font-size:17px;">Q. 로또 구입 한도가 있나요?</h3>
            <p>1인당 1회 최대 <strong>5장 (5,000원)</strong>까지 구매 가능합니다. 온라인 구매(동행복권 사이트)의 경우 1주일 최대 <strong>10만원</strong>까지 구매 가능합니다. 미성년자(만 19세 미만)는 구매가 불가합니다.</p>
        </div>

        <div class="faq-item">
            <h3 style="margin:0 0 10px;font-size:17px;">Q. 이 사이트의 추천 번호를 사면 당첨되나요?</h3>
            <p><strong>아닙니다.</strong> 로또는 완전한 무작위 추첨이며, 과거 데이터로 미래를 예측할 수 없습니다. Lotto Lab에서 제공하는 모든 분석과 추천 번호는 통계적 참고용이며, 당첨을 보장하지 않습니다. 책임감 있는 구매를 권장합니다.</p>
        </div>

        <div class="faq-item">
            <h3 style="margin:0 0 10px;font-size:17px;">Q. Lotto Lab의 데이터는 어디서 가져오나요?</h3>
            <p>모든 당첨번호 데이터는 <strong>동행복권</strong> 공식 데이터를 기반으로 합니다. 2002년 12월 첫 회차부터 현재까지의 전체 데이터를 수집하여 분석에 활용하고 있습니다.</p>
        </div>

        <div class="faq-item">
            <h3 style="margin:0 0 10px;font-size:17px;">Q. 역대 로또 1등 최고 당첨금은 얼마인가요?</h3>
            <p>역대 1등 최고 당첨금은 <strong>약 407억원</strong> (2003년 제 55회)으로, 당시 1인이 수동으로 구매하여 당첨되었습니다. 세후 실수령액은 약 280억원이었습니다.</p>
        </div>
    </div>
    """
    faq_items = [
        {"@type": "Question", "name": "로또 번호는 어떻게 추첨되나요?", "acceptedAnswer": {"@type": "Answer", "text": "로또 6/45는 1부터 45까지의 숫자 중 6개의 당첨번호와 1개의 보너스 번호를 추첨합니다. 매주 토요일 오후 8시 45분에 생방송으로 추첨이 진행됩니다."}},
        {"@type": "Question", "name": "로또 당첨 확률은 얼마인가요?", "acceptedAnswer": {"@type": "Answer", "text": "1등 확률은 1/8,145,060, 2등 1/1,357,510, 3등 1/35,724, 4등 1/733, 5등 1/45입니다."}},
        {"@type": "Question", "name": "로또 당첨금에 세금이 붙나요?", "acceptedAnswer": {"@type": "Answer", "text": "5만원 이하는 비과세, 5만원 초과~3억원 이하는 22%, 3억원 초과는 33%가 적용됩니다."}},
        {"@type": "Question", "name": "로또 당첨금은 어디서 수령하나요?", "acceptedAnswer": {"@type": "Answer", "text": "5등은 판매점, 4등은 판매점/농협, 3등은 농협 지점, 1~2등은 농협은행 본점에서 수령합니다."}},
    ]
    return render_template('page.html', title='자주 묻는 질문 (FAQ)', description='로또 당첨 확률, 세금, 수령 방법 등 자주 묻는 질문과 답변', content=content, is_faq=True, faq_schema=json.dumps(faq_items, ensure_ascii=False))


@app.route('/contact')
def contact():
    content = """
    <h3 style="margin:20px 0 10px;font-size:17px;">문의하기</h3>
    <p>Lotto Lab에 대한 문의, 건의, 오류 신고는 아래 방법으로 연락해주세요.</p>

    <div style="background:var(--bg);padding:20px;border-radius:var(--radius-sm);margin:20px 0;">
        <p style="margin-bottom:8px;"><strong>이메일</strong></p>
        <p style="color:var(--accent);font-size:16px;"><a href="mailto:kv0435029@naver.com" style="color:var(--accent);text-decoration:none;">kv0435029@naver.com</a></p>
    </div>

    <div style="background:var(--bg);padding:20px;border-radius:var(--radius-sm);margin:20px 0;">
        <p style="margin-bottom:8px;"><strong>GitHub</strong></p>
        <p><a href="https://github.com/dlalsdyd01/lotto-analytics" style="color:var(--accent);">github.com/dlalsdyd01/lotto-analytics</a></p>
    </div>

    <p style="color:var(--text-2);margin-top:16px;">문의 시 구체적인 내용을 포함해 주시면 빠른 답변이 가능합니다.</p>
    """
    return render_template('page.html', title='연락처', description='Lotto Lab 연락처 - 문의 및 건의', content=content)


@app.route('/guide')
def guide_index():
    content = """
    <p>로또 6/45를 처음 접하는 분부터 오랫동안 구매해 온 분까지, 로또에 대해 알아두면 좋은 정보를 주제별로 정리했습니다. 모든 내용은 동행복권 공식 자료와 통계 데이터를 바탕으로 작성되었습니다.</p>

    <h3 style="margin:24px 0 12px;font-size:17px;">콘텐츠 목록</h3>
    <ul>
        <li><a href="/guide/how-to-play"><strong>로또 구매 완벽 가이드</strong></a> — 구매 방법, 자동/수동/반자동 차이, 온라인 구매, 당첨금 수령 절차까지</li>
        <li><a href="/guide/statistics-meaning"><strong>로또 통계의 의미와 한계</strong></a> — 출현 빈도, 핫/콜드 번호의 실제 의미와 흔한 오해</li>
        <li><a href="/guide/winning-stories"><strong>역대 로또 기록 모음</strong></a> — 최고 당첨금, 최다 당첨 번호, 이월 회차 등 흥미로운 기록</li>
        <li><a href="/guide/responsible-play"><strong>책임 있는 복권 문화</strong></a> — 건강한 구매 습관과 도움받을 수 있는 기관</li>
        <li><a href="/probability"><strong>확률 교실</strong></a> — 로또 확률을 수학적으로 쉽게 설명</li>
        <li><a href="/tax-calculator"><strong>당첨금 세금 계산기</strong></a> — 실수령액을 즉시 계산</li>
        <li><a href="/faq"><strong>자주 묻는 질문</strong></a> — 구매, 수령, 세금 등 FAQ</li>
    </ul>

    <div class="info-warn" style="margin-top:24px;">
        로또는 완전한 무작위 추첨입니다. 본 사이트의 모든 분석과 예측은 통계적 참고용이며 당첨을 보장하지 않습니다.
    </div>
    """
    return render_template('page.html', title='로또 가이드', description='로또 6/45 구매 방법, 통계의 의미, 역대 기록, 책임 있는 복권 문화까지 - 로또에 대한 모든 것을 정리한 가이드', content=content)


@app.route('/guide/how-to-play')
def guide_how_to_play():
    content = """
    <p style="color:var(--text-2);margin-bottom:8px;font-size:13px;">읽는 시간: 약 6분</p>
    <p>로또 6/45는 대한민국에서 2002년 12월부터 판매된 복권으로, 1부터 45까지의 숫자 중 6개를 맞히면 1등에 당첨되는 방식입니다. 이 글에서는 로또를 처음 구매하는 분도 이해할 수 있도록 구매 방법과 절차를 자세히 설명합니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">1. 로또 게임 방식</h3>
    <p>1부터 45까지의 숫자 중 6개를 선택하고, 매주 토요일 오후 8시 45분에 추첨되는 6개의 당첨번호와 비교합니다. 또한 1개의 보너스 번호가 함께 추첨되어 2등 당첨 여부에 사용됩니다.</p>
    <ul>
        <li><strong>1등:</strong> 선택한 6개가 모두 당첨번호와 일치</li>
        <li><strong>2등:</strong> 5개 일치 + 보너스 번호 일치</li>
        <li><strong>3등:</strong> 5개 일치</li>
        <li><strong>4등:</strong> 4개 일치</li>
        <li><strong>5등:</strong> 3개 일치</li>
    </ul>

    <h3 style="margin:24px 0 10px;font-size:17px;">2. 구매 방법 세 가지</h3>
    <p>판매점에서 로또 용지에 직접 번호를 칠하거나, 점원에게 말하면 됩니다. 방식은 세 가지가 있습니다.</p>
    <ul>
        <li><strong>자동</strong> — 컴퓨터가 무작위로 6개 번호를 선택. 가장 간편하며 통계적으로 수동과 당첨 확률 차이가 없습니다.</li>
        <li><strong>수동</strong> — 본인이 6개 번호를 직접 기입. 생일, 기념일, 좋아하는 숫자를 넣고 싶을 때 사용합니다.</li>
        <li><strong>반자동</strong> — 일부 번호만 직접 기입하고 나머지는 자동. 특정 숫자는 넣고 싶지만 전부 고르기 어려울 때 유용합니다.</li>
    </ul>
    <p>한 장(1게임)은 1,000원이며, 한 용지에 최대 5게임까지 기입할 수 있습니다. 1인당 1회 최대 5게임(5,000원)이 구매 한도입니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">3. 온라인 구매</h3>
    <p>동행복권 공식 사이트(dhlottery.co.kr)에서 본인 인증 후 예치금을 충전해 구매할 수 있습니다. 온라인 구매는 주당 10만 원 한도가 있으며, 미성년자(만 19세 미만)는 구매할 수 없습니다. 공식 앱 이외의 사이트에서 구매를 유도하는 경우 사기일 수 있으니 반드시 공식 경로를 이용하세요.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">4. 추첨 시간과 방송</h3>
    <p>매주 토요일 오후 8시 45분 MBC에서 생방송으로 추첨이 이루어집니다. 추첨기는 물리적으로 공을 섞어 꺼내는 방식으로, 완전한 무작위성을 보장합니다. 추첨 결과는 동행복권 사이트와 <a href="/">Lotto Lab</a>에서 바로 확인할 수 있습니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">5. 당첨금 수령 방법</h3>
    <ul>
        <li><strong>5등 (5,000원)</strong> — 로또 판매점 어디서나 즉시 수령 가능합니다.</li>
        <li><strong>4등 (약 50,000원)</strong> — 판매점 또는 농협 지점에서 수령합니다.</li>
        <li><strong>3등 (약 150만 원)</strong> — 농협 지점에서 신분증 지참 후 수령합니다.</li>
        <li><strong>1·2등</strong> — 서울 중구 NH농협은행 본점에서만 수령 가능합니다. 신분증과 당첨 복권 원본을 지참해야 하며, 당첨 세금이 원천징수됩니다.</li>
    </ul>
    <p>당첨금 지급 기한은 <strong>지급 개시일로부터 1년</strong>입니다. 이 기간 내 수령하지 않으면 복권기금으로 귀속되어 공익사업에 사용됩니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">6. 구매 시 유의사항</h3>
    <ul>
        <li>구매 후 복권 용지를 분실하지 않도록 주의하세요. 원본이 없으면 당첨금을 받을 수 없습니다.</li>
        <li>QR 코드가 훼손되지 않도록 복권을 잘 보관해야 합니다.</li>
        <li>자신의 번호를 기록해두면 분실 시에도 당첨 여부를 확인할 수 있습니다.</li>
        <li>로또는 오락이며, 생활에 지장을 주지 않는 범위에서 구매하세요.</li>
    </ul>

    <div class="info-warn" style="margin-top:24px;">
        로또는 완전한 무작위 추첨이며, 과거 당첨번호와 미래 당첨은 통계적으로 독립입니다. 구매는 본인의 판단과 책임 하에 이루어져야 합니다.
    </div>

    <p style="margin-top:24px;"><a href="/guide">← 가이드 목록으로 돌아가기</a></p>
    """
    return render_template('page.html', title='로또 구매 완벽 가이드', description='로또 6/45 구매 방법, 자동·수동·반자동 차이, 온라인 구매, 당첨금 수령 절차까지 초보자를 위한 완벽 가이드', content=content)


@app.route('/guide/statistics-meaning')
def guide_statistics_meaning():
    content = """
    <p style="color:var(--text-2);margin-bottom:8px;font-size:13px;">읽는 시간: 약 7분</p>
    <p>로또 분석 사이트를 방문하면 "핫 넘버", "콜드 넘버", "출현 빈도" 같은 용어를 흔히 볼 수 있습니다. 이런 통계들이 정확히 무엇을 의미하고, 어떤 한계가 있는지 살펴봅니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">출현 빈도(Frequency)란?</h3>
    <p>지금까지 추첨된 전체 회차 동안 각 번호(1~45)가 당첨번호로 몇 번 나왔는지 센 값입니다. 2002년부터 현재까지 1,100회 이상 추첨되었으므로, 각 번호가 나온 기대 횟수는 약 <code>1,100 × 6 ÷ 45 ≈ 147회</code>입니다. 실제 데이터를 보면 이 평균 주변에서 일정 범위 내로 분포합니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">"핫 넘버"와 "콜드 넘버"</h3>
    <p>최근 N회차(보통 20~50회) 동안 자주 나온 번호를 "핫 넘버", 드물게 나온 번호를 "콜드 넘버"라고 부릅니다. 이 개념은 두 가지 정반대 해석이 있습니다.</p>
    <ul>
        <li><strong>도박사의 오류(Gambler's Fallacy)</strong> — "최근 안 나온 번호가 곧 나올 것이다"라는 생각. 각 추첨은 독립 사건이므로 이는 틀린 추론입니다.</li>
        <li><strong>뜨거운 손 오류(Hot-hand Fallacy)</strong> — "최근 자주 나온 번호가 계속 나올 것이다"라는 생각. 로또 추첨은 이전 결과에 의존하지 않으므로 이 또한 틀린 추론입니다.</li>
    </ul>
    <p>두 해석 모두 수학적으로는 근거가 없습니다. 그럼에도 사람들은 패턴을 찾으려는 본능 때문에 의미를 부여하곤 합니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">홀짝 비율·고저 비율</h3>
    <p>6개 번호의 홀짝 비율이나 1~22(저)과 23~45(고) 분포도 자주 언급됩니다. 통계적으로 3:3, 2:4, 4:2 조합이 가장 자주 나오는데, 이는 단순히 조합 수가 많기 때문입니다. 6:0(전부 홀수)이 드문 것은 "규칙"이 아니라 <em>경우의 수</em>가 적기 때문입니다.</p>
    <p>즉 "3:3 비율로 고르는 게 유리하다"는 말은 틀렸습니다. 확률이 높은 것이 아니라 그런 조합 자체가 많아서 많이 당첨되는 것이며, 당첨 확률은 모든 조합이 동일합니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">연속번호·동일 끝수</h3>
    <p>연속된 두 숫자(예: 14-15)가 포함된 조합이나, 끝자리가 같은 숫자 여러 개(예: 5, 15, 35)가 포함된 조합도 자주 관찰됩니다. 이 역시 경우의 수가 충분히 많기 때문이며, 특정 패턴이 "당첨되기 쉬운" 것은 아닙니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">번호 합계(Sum)</h3>
    <p>6개 번호의 합계는 이론상 21(1+2+3+4+5+6)부터 255(40+41+42+43+44+45)까지이며, 평균은 138입니다. 실제 당첨 번호 합계도 대부분 100~180 구간에 몰려 있는데, 이는 중간 값 근처의 조합이 훨씬 많기 때문입니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">통계가 유용한 영역</h3>
    <p>그렇다면 통계는 쓸모가 없을까요? 그렇지 않습니다. 통계는 다음 영역에서 의미가 있습니다.</p>
    <ul>
        <li><strong>추첨의 무작위성 검증</strong> — 관측값이 이론값에서 크게 벗어나는지 확인하여 추첨이 공정한지 판단할 수 있습니다.</li>
        <li><strong>기댓값 계산</strong> — 1등 당첨금 × 당첨 확률 = 기댓값. 로또의 기댓값은 항상 구매 가격보다 낮으며, 이는 장기적으로 손실이 발생함을 의미합니다.</li>
        <li><strong>재미와 참고</strong> — 통계는 "어떤 번호를 고를지" 결정하는 데 도움이 되지는 않지만, 과거 데이터를 살펴보는 재미와 학습 목적으로 유용합니다.</li>
    </ul>

    <h3 style="margin:24px 0 10px;font-size:17px;">결론</h3>
    <p>로또는 완전한 무작위 추첨이며, 어떤 번호를 고르든 1등 당첨 확률은 <strong>8,145,060분의 1</strong>로 동일합니다. 본 사이트(<a href="/">Lotto Lab</a>)의 통계 분석은 흥미로운 데이터 시각화이자 학습 자료로 제공되며, 당첨을 돕는 도구가 아닙니다. 통계의 한계를 이해하고 현명하게 활용하세요.</p>

    <div class="info-warn" style="margin-top:24px;">
        어떤 "예측 알고리즘"도 로또 당첨 확률을 높일 수 없습니다. 이를 주장하는 유료 서비스에 주의하세요.
    </div>

    <p style="margin-top:24px;"><a href="/guide">← 가이드 목록으로 돌아가기</a></p>
    """
    return render_template('page.html', title='로또 통계의 의미와 한계', description='핫 넘버, 콜드 넘버, 출현 빈도 등 로또 통계가 실제로 무엇을 의미하는지와 그 한계를 수학적 관점에서 설명', content=content)


@app.route('/guide/winning-stories')
def guide_winning_stories():
    content = """
    <p style="color:var(--text-2);margin-bottom:8px;font-size:13px;">읽는 시간: 약 5분</p>
    <p>한국 로또 6/45는 2002년 12월 첫 추첨 이후 수많은 기록을 남겨 왔습니다. 이 글에서는 흥미로운 역대 기록과 사례를 정리합니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">역대 최고 당첨금</h3>
    <p>로또 역사상 1인 최고 당첨금은 <strong>2003년 4월 제19회 추첨의 약 407억 원</strong>입니다. 당시는 5회차 연속 이월되어 누적금액이 폭등한 회차였습니다. 이 당첨자는 수동으로 구매했으며, 세후 실수령액은 약 280억 원이었습니다.</p>
    <p>이후 로또 제도가 개편되어 1등 당첨금 이월 횟수와 1인 구매 한도가 제한되었습니다. 현재는 1회당 최대 5장(5,000원)까지만 구매 가능하며, 이월은 2회로 제한되어 있습니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">1등 당첨자 수의 변동</h3>
    <p>한 회차의 1등 당첨자 수는 보통 5~15명 정도이지만, 때로 극단적인 수치가 나오기도 합니다.</p>
    <ul>
        <li><strong>최다 1등</strong> — 한 회차에 1등이 60명 이상 쏟아진 경우도 있었습니다. 이런 경우 1인당 당첨금은 상대적으로 적습니다.</li>
        <li><strong>최소 1등</strong> — 1등이 1명만 나와 전체 당첨금을 독차지한 회차도 있습니다.</li>
        <li><strong>1등 없음(이월)</strong> — 1등이 나오지 않아 다음 회차로 당첨금이 이월되는 경우도 드물게 발생합니다.</li>
    </ul>

    <h3 style="margin:24px 0 10px;font-size:17px;">자주 나온 번호·드물게 나온 번호</h3>
    <p>장기간 누적 데이터를 보면 번호별 출현 빈도는 평균(약 147회)을 중심으로 분포합니다. 특정 번호가 평균보다 10~20회 많거나 적게 나오는 경우가 있지만, 이는 통계적 요동 범위 내에서 흔히 관찰되는 현상입니다. 역대 최다/최소 출현 번호는 <a href="/">Lotto Lab 메인</a>의 빈도 분석에서 실시간으로 확인할 수 있습니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">같은 번호가 연속 회차에 나올 확률</h3>
    <p>어떤 번호가 두 회차 연속으로 당첨번호에 포함될 확률은 <code>6/45 × 6/45 ≈ 1.78%</code>입니다. 놀랍게도 이런 "연속 출현"은 거의 매주 발생합니다. 이는 우연이 아니라 확률적으로 당연한 결과입니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">같은 6개 조합이 다시 나올 확률</h3>
    <p>어떤 6개 조합이 정확히 같은 순서로 다시 당첨될 확률은 <code>1/8,145,060</code>입니다. 매주 한 번씩 추첨해도 같은 조합이 나오기까지 통계적으로 약 15만 년이 필요합니다. 2002년 이후 지금까지 완전히 같은 조합이 두 번 나온 사례는 없습니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">유명 판매점 "명당"이란?</h3>
    <p>1등 당첨 복권을 여러 번 배출한 판매점을 흔히 "명당"이라고 부릅니다. 그러나 이는 단순히 <strong>해당 판매점의 판매량이 많기 때문</strong>인 경우가 대부분입니다. 판매량이 많으면 당첨자 배출 빈도도 자연스럽게 높아집니다.</p>
    <p>즉, 어느 판매점에서 사든 번호 하나당 당첨 확률은 같습니다. 명당이라는 개념은 심리적 요소일 뿐, 확률을 바꾸지는 않습니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">복권기금의 사용처</h3>
    <p>로또 판매액의 약 42%는 복권기금으로 적립되어 저소득층 주거 안정, 문화예술 진흥, 장학사업, 국가유공자 지원 등 공익사업에 사용됩니다. 당첨되지 않더라도 복권 구매는 사회 기여의 한 형태이기도 합니다.</p>

    <div class="info-warn" style="margin-top:24px;">
        흥미로운 기록들을 소개했지만, 로또 당첨은 극히 낮은 확률의 이벤트입니다. 과거 기록을 근거로 한 번호 선택은 당첨 확률을 높이지 않습니다.
    </div>

    <p style="margin-top:24px;"><a href="/guide">← 가이드 목록으로 돌아가기</a></p>
    """
    return render_template('page.html', title='역대 로또 기록 모음', description='역대 최고 당첨금 407억 원, 최다·최소 당첨자 수, 명당 판매점의 진실 등 로또 6/45의 흥미로운 기록들', content=content)


@app.route('/guide/responsible-play')
def guide_responsible_play():
    content = """
    <p style="color:var(--text-2);margin-bottom:8px;font-size:13px;">읽는 시간: 약 4분</p>
    <p>로또는 대부분의 구매자에게 가벼운 오락이지만, 과도한 구매는 재정적·심리적 문제를 일으킬 수 있습니다. 건강한 복권 문화를 위해 알아두어야 할 원칙을 소개합니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">1. 오락 비용으로만 구매하기</h3>
    <p>로또는 투자가 아니라 오락입니다. 영화 관람이나 외식처럼 "써도 괜찮은 돈"의 범위에서만 구매하세요. 생활비, 비상금, 대출금을 로또에 쓰는 것은 매우 위험합니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">2. 주간 한도 정하기</h3>
    <p>매주 사용할 금액을 미리 정해두세요. 예를 들어 "매주 5,000원까지만"처럼 고정된 한도를 두는 것이 좋습니다. 당첨되지 않아 분할 수를 늘리거나, 이월 회차라고 갑자기 많이 사는 행동은 <strong>추격 매수(chasing losses)</strong>로 이어져 위험합니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">3. 기댓값 이해하기</h3>
    <p>로또의 기댓값은 구매 가격보다 항상 낮습니다. 판매액의 약 50%가 당첨금으로 환원되므로, 장기적으로 구매액의 절반 정도를 잃게 됩니다. 즉 로또는 "재미를 사는 것"이지 "돈을 버는 수단"이 아닙니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">4. 확률적 사고 유지하기</h3>
    <ul>
        <li>1등 당첨 확률은 <strong>8,145,060분의 1</strong>입니다. 이는 낙뢰에 맞을 확률보다도 훨씬 낮습니다.</li>
        <li>같은 번호를 매주 사도 확률은 변하지 않습니다.</li>
        <li>"이번엔 느낌이 온다"는 감각은 심리적 착각입니다.</li>
    </ul>

    <h3 style="margin:24px 0 10px;font-size:17px;">5. 도박 문제 자가진단</h3>
    <p>다음 중 해당 항목이 2개 이상이면 전문 상담을 고려해 보세요.</p>
    <ul>
        <li>로또나 다른 복권 구매에 점점 더 많은 돈을 쓰게 된다.</li>
        <li>당첨되지 못한 돈을 만회하려고 다시 산다.</li>
        <li>로또를 줄이거나 끊으려 했지만 실패한 경험이 있다.</li>
        <li>로또 구매를 가족이나 주변 사람에게 숨긴다.</li>
        <li>로또 때문에 재정적 어려움이나 관계 문제가 생긴 적이 있다.</li>
    </ul>

    <h3 style="margin:24px 0 10px;font-size:17px;">6. 도움받을 수 있는 곳</h3>
    <ul>
        <li><strong>한국도박문제예방치유원</strong> — 전국 상담전화 <strong>1336</strong> (24시간, 무료, 익명 상담)</li>
        <li><strong>한국도박문제예방치유원 홈페이지</strong> — kcgp.or.kr (자가진단 및 상담 신청)</li>
        <li><strong>정신건강상담</strong> — 국번 없이 <strong>1577-0199</strong></li>
    </ul>
    <p>도박 문제는 개인의 의지 부족이 아니라 치료가 필요한 질환으로 인정되고 있습니다. 조기에 도움을 받으면 충분히 회복할 수 있습니다.</p>

    <h3 style="margin:24px 0 10px;font-size:17px;">7. 미성년자 구매 금지</h3>
    <p>대한민국에서는 만 19세 미만의 복권 구매가 법적으로 금지되어 있습니다. 미성년자 대리 구매는 판매점과 구매자 모두에게 법적 책임이 있습니다.</p>

    <div class="info-warn" style="margin-top:24px;">
        Lotto Lab은 건강하고 책임 있는 복권 문화를 지지합니다. 본 사이트는 통계 분석 및 교육 목적으로 제공되며, 구매를 권유하지 않습니다.
    </div>

    <p style="margin-top:24px;"><a href="/guide">← 가이드 목록으로 돌아가기</a></p>
    """
    return render_template('page.html', title='책임 있는 복권 문화', description='건강한 로또 구매 습관, 도박 문제 자가진단, 상담 기관 연락처까지 - 책임 있는 복권 구매를 위한 가이드', content=content)


@app.route('/my-numbers')
def my_numbers():
    return render_template('my_numbers.html')


@app.route('/numbers')
def numbers_index():
    draws = load_cache() if not _data_ready.is_set() else get_draws()
    total_draws = len(draws) if draws else 0
    freq = frequency_analysis(draws) if draws else {n: 0 for n in range(1, 46)}
    numbers = []
    for n in range(1, 46):
        c = freq.get(n, 0)
        rate = round(c / total_draws * 100, 1) if total_draws else 0
        numbers.append({'num': n, 'count': c, 'rate': rate})
    return render_template('numbers_index.html', numbers=numbers, total_draws=total_draws)


@app.route('/number/<int:number>')
def number_detail(number):
    if number < 1 or number > 45:
        return render_template('page.html', title='잘못된 번호', description='', content='<p>1~45 사이의 번호만 조회할 수 있습니다.</p>'), 404

    draws = load_cache() if not _data_ready.is_set() else get_draws()
    if not draws:
        return render_template('page.html', title='데이터 로딩 중', description='', content='<p>데이터를 수집하는 중입니다.</p>')

    total_draws = len(draws)
    total_count = sum(1 for d in draws if number in d['numbers'])
    bonus_count = sum(1 for d in draws if d.get('bonus') == number)
    recent = draws[-50:] if total_draws >= 50 else draws
    recent_count = sum(1 for d in recent if number in d['numbers'])

    expected = round(total_draws * 6 / 45)
    deviation = total_count - expected
    appearance_rate = round(total_count / total_draws * 100, 1) if total_draws else 0

    # 최근 출현 10회
    recent_appearances = [
        {'draw_no': d['draw_no'], 'date': d.get('date', '')}
        for d in sorted(draws, key=lambda x: x['draw_no'], reverse=True)
        if number in d['numbers']
    ][:10]

    # 동반 번호 Top 10
    partner_counter = Counter()
    for d in draws:
        if number in d['numbers']:
            for n in d['numbers']:
                if n != number:
                    partner_counter[n] += 1
    partners = [{'num': n, 'count': c} for n, c in partner_counter.most_common(10)]

    return render_template('number.html',
        number=number,
        total_draws=total_draws,
        total_count=total_count,
        recent_count=recent_count,
        bonus_count=bonus_count,
        expected_count=expected,
        deviation=deviation,
        appearance_rate=appearance_rate,
        recent_appearances=recent_appearances,
        partners=partners,
    )


@app.route('/probability')
def probability():
    return render_template('probability.html')


@app.route('/tax-calculator')
def tax_calculator():
    return render_template('tax_calculator.html')


@app.route('/sitemap.xml')
def sitemap():
    """SEO용 사이트맵"""
    draws = load_cache() if not _data_ready.is_set() else get_draws()
    latest_no = draws[-1]['draw_no'] if draws else 1

    urls = []
    # 메인 페이지
    urls.append({'loc': 'https://lottoanalytics.co.kr/', 'priority': '1.0', 'changefreq': 'weekly'})
    # 법적 페이지
    # 콘텐츠 페이지
    urls.append({'loc': 'https://lottoanalytics.co.kr/probability', 'priority': '0.7', 'changefreq': 'monthly'})
    urls.append({'loc': 'https://lottoanalytics.co.kr/tax-calculator', 'priority': '0.7', 'changefreq': 'monthly'})
    # 가이드 (고품질 콘텐츠)
    urls.append({'loc': 'https://lottoanalytics.co.kr/my-numbers', 'priority': '0.8', 'changefreq': 'weekly'})
    urls.append({'loc': 'https://lottoanalytics.co.kr/numbers', 'priority': '0.8', 'changefreq': 'weekly'})
    for n in range(1, 46):
        urls.append({'loc': f'https://lottoanalytics.co.kr/number/{n}', 'priority': '0.7', 'changefreq': 'weekly'})
    urls.append({'loc': 'https://lottoanalytics.co.kr/guide', 'priority': '0.8', 'changefreq': 'monthly'})
    for slug in ['how-to-play', 'statistics-meaning', 'winning-stories', 'responsible-play']:
        urls.append({'loc': f'https://lottoanalytics.co.kr/guide/{slug}', 'priority': '0.8', 'changefreq': 'monthly'})
    # 법적 페이지
    for page in ['faq', 'privacy', 'terms', 'about', 'contact']:
        urls.append({'loc': f'https://lottoanalytics.co.kr/{page}', 'priority': '0.3', 'changefreq': 'monthly'})
    # 회차별 페이지 (전체)
    for no in range(latest_no, 0, -1):
        urls.append({'loc': f'https://lottoanalytics.co.kr/draw/{no}', 'priority': '0.6', 'changefreq': 'never' if no < latest_no else 'weekly'})

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u in urls:
        xml += f'  <url>\n    <loc>{u["loc"]}</loc>\n    <changefreq>{u["changefreq"]}</changefreq>\n    <priority>{u["priority"]}</priority>\n  </url>\n'
    xml += '</urlset>'

    return Response(xml, mimetype='application/xml')


@app.route('/ads.txt')
def ads_txt():
    return Response('google.com, pub-3398247421662455, DIRECT, f08c47fec0942fa0\n', mimetype='text/plain')


@app.route('/robots.txt')
def robots():
    txt = """User-agent: *
Allow: /
Disallow: /api/

Sitemap: https://lottoanalytics.co.kr/sitemap.xml
"""
    return Response(txt, mimetype='text/plain')


@app.route('/api/refresh')
def api_refresh():
    """데이터 새로고침"""
    draws = fetch_all_draws()
    _data_ready.set()
    return jsonify({'total': len(draws), 'latest': draws[-1]['draw_no'] if draws else 0})


# 앱 시작 시 백그라운드 데이터 수집
t = threading.Thread(target=_bg_fetch, daemon=True)
t.start()

if __name__ == '__main__':
    print('로또 분석 웹앱을 시작합니다...')
    port = int(os.environ.get('PORT', 5001))
    print(f'http://localhost:{port} 에서 접속하세요.')
    print('데이터를 백그라운드에서 수집합니다... (최초 실행 시 1~2분 소요)')

    app.run(debug=False, host='0.0.0.0', port=port)
