from flask import Flask, render_template, jsonify, request
from lotto_data import get_draws, fetch_all_draws, get_latest_draw_number, load_cache, get_fetch_status
from analysis import get_full_analysis, predict_numbers
import threading
import os

app = Flask(__name__)

# 백그라운드 데이터 수집
_data_ready = threading.Event()


def _bg_fetch():
    print('데이터 수집 시작...')
    draws = get_draws()
    print(f'총 {len(draws)}회차 데이터 로드 완료!')
    _data_ready.set()


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
