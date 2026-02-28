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
    port = int(os.environ.get('PORT', 5000))
    print(f'http://localhost:{port} 에서 접속하세요.')
    print('데이터를 백그라운드에서 수집합니다... (최초 실행 시 1~2분 소요)')

    app.run(debug=False, host='0.0.0.0', port=port)
