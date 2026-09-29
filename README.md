# Lotto Lab — 로또 번호 예측

**https://lottoanalytics.co.kr/**

역대 로또 6/45 당첨 데이터를 바탕으로 이번 주 예측번호를 생성하는 Flask 웹앱입니다.

## 기능

- **3D 추첨기** — 공이 계속 섞이다가 추첨하기를 누르면 A세트 번호가 하나씩 나옴 (WebGL 미지원 시 2D)
- **예측번호 1세트** — 전체 빈도 30% + 최근 50회 빈도 45% + 미출현 기간 25% 가중치. 회차별로 브라우저(localStorage)에 저장되어 같은 회차 동안 같은 번호 유지
- **조합 필터** — 합계 100~175, 홀짝·저고 2:4~4:2, 3연속 번호 없음, 역대 1등 조합과 중복 없음
- **최신 회차 당첨번호**, 최근 핫/콜드 번호 표시
- 새 회차 자동 수집 (30분 간격, KST 토요일 21시 이후 반영)

## 구조

```
app.py          라우트 (/, /api/predict, 약관 페이지, sitemap/robots/ads.txt)
predictor.py    예측 엔진
lotto_data.py   당첨번호 수집 및 캐시 (lotto_cache.json)
templates/      base.html, index.html, page.html
static/         style.css, 이미지
```

## API

`GET /api/predict?strategy=balanced&sets=5&fixed=7,13&exclude=1,2`

- `strategy`: `balanced` | `hot` | `cold` | `random`
- `sets`: 1~10
- `fixed`, `exclude`: 쉼표로 구분한 번호

## 실행

```bash
pip install -r requirements.txt
python app.py   # http://localhost:5001
```

## 데이터 출처

- [smok95 GitHub Pages API](https://smok95.github.io/lotto/results/all.json) (동행복권 데이터 미러)
- 동행복권 공식 API (최신 회차 보충)

## 면책 조항

로또는 완전한 무작위 추첨이며, 과거 데이터로 미래 당첨번호를 예측할 수 없습니다. 제공되는 번호는 참고용이며 당첨을 보장하지 않습니다.
