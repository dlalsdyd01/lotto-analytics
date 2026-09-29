from flask import Flask, render_template, jsonify, request, Response
from datetime import date, timedelta
from lotto_data import get_draws, start_auto_refresh
from predictor import predict, hot_cold
import os

SITE_URL = 'https://lottoanalytics.co.kr'

# 애드센스 — 대시보드에서 만든 디스플레이 광고 단위의 data-ad-slot 번호를 넣으면 해당 위치에 광고가 표시됨
AD_CLIENT = 'ca-pub-3398247421662455'
AD_SLOTS = {
    'after_result': '',   # 예측번호 카드 아래
    'bottom': '',         # 페이지 하단 (푸터 위)
}

app = Flask(__name__)


@app.context_processor
def inject_ads():
    return {'ad_client': AD_CLIENT, 'ad_slots': AD_SLOTS}


@app.after_request
def add_cache_headers(response):
    if request.path.startswith('/static/'):
        response.cache_control.max_age = 86400
        response.cache_control.public = True
    return response


@app.template_filter('won')
def format_won(amount):
    """2592525282 → '25억 9,252만원'"""
    eok, man = amount // 100_000_000, (amount % 100_000_000) // 10_000
    if eok:
        return f'{eok:,}억 {man:,}만원' if man else f'{eok:,}억원'
    return f'{man:,}만원' if man else f'{amount:,}원'


def _next_draw(draws):
    latest = draws[-1]
    return {
        'draw_no': latest['draw_no'] + 1,
        'date': (date.fromisoformat(latest['date']) + timedelta(days=7)).isoformat(),
    }


def _parse_numbers(value):
    try:
        nums = {int(x) for x in value.split(',') if x.strip()}
    except ValueError:
        return set()
    return {n for n in nums if 1 <= n <= 45}


@app.route('/')
def index():
    draws = get_draws()
    if not draws:
        return render_template('page.html', title='데이터 준비 중',
                               content='<p>당첨번호 데이터를 불러오는 중입니다. 잠시 후 새로고침해 주세요.</p>'), 503
    return render_template('index.html',
                           latest=draws[-1],
                           next_draw=_next_draw(draws),
                           total_draws=len(draws),
                           stats=hot_cold(draws))


@app.route('/api/predict')
def api_predict():
    draws = get_draws()
    if not draws:
        return jsonify({'error': '데이터를 불러오는 중입니다.'}), 503

    strategy = request.args.get('strategy', 'balanced')
    sets = min(max(request.args.get('sets', 5, type=int), 1), 10)
    fixed = _parse_numbers(request.args.get('fixed', ''))
    excluded = _parse_numbers(request.args.get('exclude', ''))
    try:
        result = predict(draws, strategy, sets, fixed, excluded)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    result['next_draw'] = _next_draw(draws)
    return jsonify(result)


PRIVACY = """
<p class="muted">최종 수정일: 2026년 9월 29일</p>
<h3>1. 수집하는 개인정보</h3>
<p>Lotto Lab은 회원가입이 없으며 이름, 이메일 등 개인을 식별할 수 있는 정보를 직접 수집하지 않습니다. 서비스 이용 과정에서 접속 IP, 브라우저 종류, 접속 시간 등이 자동으로 수집될 수 있습니다.</p>
<h3>2. 이용 목적</h3>
<p>자동 수집된 정보는 서비스 이용 통계 분석 및 안정성 확보에만 사용됩니다.</p>
<h3>3. 제3자 서비스</h3>
<ul>
  <li><strong>Google Analytics</strong> — 익명화된 이용 통계 (Google 개인정보처리방침 적용)</li>
  <li><strong>Google AdSense</strong> — 광고 제공 (Google 광고 정책 적용)</li>
</ul>
<h3>4. 쿠키</h3>
<p>위 서비스를 위해 쿠키가 사용됩니다. 브라우저 설정에서 쿠키를 거부할 수 있습니다.</p>
<h3>5. 보관 기간</h3>
<p>자동 수집된 로그 정보는 최대 1년간 보관 후 파기합니다.</p>
<h3>6. 문의</h3>
<p><a href="/contact">연락처 페이지</a>를 이용해 주세요.</p>
"""

TERMS = """
<p class="muted">최종 수정일: 2026년 9월 29일</p>
<h3>1. 서비스 소개</h3>
<p>Lotto Lab은 역대 로또 6/45 당첨 데이터를 바탕으로 번호 조합을 생성해 주는 무료 서비스입니다.</p>
<h3>2. 면책 조항</h3>
<p><strong>로또는 완전한 무작위 추첨이며, 과거 데이터로 미래 당첨번호를 예측할 수 없습니다.</strong> 본 서비스가 제공하는 번호는 참고용이며 당첨을 보장하지 않습니다. 이를 근거로 한 구매에 대해 책임지지 않습니다.</p>
<h3>3. 서비스 변경</h3>
<p>서비스는 사전 고지 없이 변경되거나 중단될 수 있습니다.</p>
<h3>4. 광고</h3>
<p>본 서비스는 Google AdSense 광고를 게재할 수 있으며, 광고 내용은 Lotto Lab과 무관합니다.</p>
<h3>5. 기타</h3>
<p>만 19세 미만은 복권을 구매할 수 없습니다. 도박 문제 상담은 한국도박문제예방치유원(국번 없이 1336)에서 받을 수 있습니다.</p>
"""

CONTACT = """
<p>문의, 건의, 오류 신고는 아래로 연락해 주세요.</p>
<p><strong>이메일</strong> — <a href="mailto:kv0435029@naver.com">kv0435029@naver.com</a></p>
<p><strong>GitHub</strong> — <a href="https://github.com/dlalsdyd01/lotto-analytics">github.com/dlalsdyd01/lotto-analytics</a></p>
"""

PAGES = {
    'privacy': ('개인정보처리방침', PRIVACY),
    'terms': ('이용약관', TERMS),
    'contact': ('연락처', CONTACT),
}


@app.route('/<any(privacy, terms, contact):slug>')
def static_page(slug):
    title, content = PAGES[slug]
    return render_template('page.html', title=title, content=content)


@app.route('/sitemap.xml')
def sitemap():
    paths = ['/', '/privacy', '/terms', '/contact']
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for p in paths:
        freq, prio = ('weekly', '1.0') if p == '/' else ('yearly', '0.3')
        xml += f'  <url><loc>{SITE_URL}{p}</loc><changefreq>{freq}</changefreq><priority>{prio}</priority></url>\n'
    xml += '</urlset>'
    return Response(xml, mimetype='application/xml')


@app.route('/ads.txt')
def ads_txt():
    return Response('google.com, pub-3398247421662455, DIRECT, f08c47fec0942fa0\n', mimetype='text/plain')


@app.route('/robots.txt')
def robots():
    return Response(f'User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: {SITE_URL}/sitemap.xml\n',
                    mimetype='text/plain')


start_auto_refresh()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f'http://localhost:{port} 에서 접속하세요.')
    app.run(debug=False, host='0.0.0.0', port=port)
