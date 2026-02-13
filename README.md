# 🎰 로또 번호 분석 웹앱

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**실시간 로또 당첨번호 분석 및 AI 기반 예측 서비스**

과거 모든 로또 당첨 데이터를 분석하여 통계적 인사이트를 제공하고, 가중 확률 기반 번호 예측 기능을 제공하는 웹 애플리케이션입니다.

---
**https://lottoanalytics.co.kr/**
---

---

## ✨ 주요 기능

### 📊 데이터 분석
- **전체 회차 데이터** - 2002년 첫 회차부터 현재까지 모든 당첨번호 수집
- **번호별 출현 빈도** - 1~45번 각 번호의 역대 출현 횟수 통계
- **핫/콜드 번호** - 최근 50회차 기준 가장 자주/드물게 나온 번호
- **구간 분석** - 1-10, 11-20, 21-30, 31-40, 41-45 구간별 출현 비율
- **홀짝 비율** - 홀수/짝수 조합 패턴 분석
- **연속번호 분석** - 연속된 번호 출현 빈도 (예: 12, 13)
- **합계 통계** - 당첨번호 6개 합계의 평균, 최소, 최대, 표준편차

### 🎯 AI 예측
- **가중 확률 기반 예측** - 다중 요소를 고려한 번호 생성
  - 전체 출현 빈도 (30%)
  - 최근 50회차 빈도 (40%)
  - 구간 균형 보정 (20%)
  - 랜덤성 (10%)
- **5세트 자동 생성** - 한 번에 5개의 예측 번호 조합 제공
- **구간 균형 최적화** - 특정 구간에 편중되지 않도록 자동 조정

### 🔄 실시간 업데이트
- **자동 캐싱** - 최신 데이터를 로컬에 저장하여 빠른 응답
- **백그라운드 수집** - 서버 시작 시 자동으로 최신 데이터 수집
- **새로고침 API** - 필요 시 수동으로 최신 데이터 갱신 가능

---

## 🛠️ 기술 스택

### Backend
- **Flask 3.0+** - 경량 웹 프레임워크
- **Pandas & NumPy** - 데이터 분석 및 통계 처리
- **Requests** - 외부 API 통신

### Data Source
- [smok95 GitHub Pages API](https://smok95.github.io/lotto/results/all.json) - 동행복권 데이터 미러
- 동행복권 공식 API (백업용)

### Deployment
- **Render** - 무료 호스팅 (Free Tier)
- **Gunicorn** - WSGI HTTP 서버

---

## 🚀 로컬 설치 및 실행

### 1. 저장소 클론
```bash
git clone https://github.com/yourusername/lotto-analytics.git
cd lotto-analytics
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 애플리케이션 실행
```bash
python app.py
```

브라우저에서 `http://localhost:5000` 접속

> ⏱️ 최초 실행 시 전체 데이터 수집에 1~2분 소요됩니다.

---


### 통계적 근거
- 로또는 완전 무작위지만, 과거 데이터의 통계적 패턴을 참고
- 극단적 편중을 피하고 균형잡힌 번호 조합 생성
- 매 예측마다 랜덤성을 추가하여 다양한 조합 생성


## ⚠️ 면책 조항

이 애플리케이션은 **교육 및 통계 분석 목적**으로 제작되었습니다.

- 로또는 완전한 무작위 추첨이며, 과거 데이터로 미래를 예측할 수 없습니다.
- 제공되는 예측 번호는 통계적 참고용일 뿐, 당첨을 보장하지 않습니다.
- 책임감 있는 구매를 권장합니다.

---
## 👨‍💻 개발자

Made with ❤️ by [MinyongLee]

[![GitHub](https://img.shields.io/badge/GitHub-Profile-black?logo=github)](https://github.com/yourusername)
[![Email](https://img.shields.io/badge/Email-Contact-red?logo=gmail)](mailto:your.email@example.com)

---
