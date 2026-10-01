# 로또 추천 연구소 — Android Mobile v1.1 Audited

## 개발/설치 원칙

매 수정마다 휴대폰에 APK를 설치하지 않습니다. 먼저 PC/자동 검증에서 엔진 회귀, Desktop 추천 parity, 데이터 오류 방어, Android 정적 감사를 통과시키고, **실제 APK 빌드까지 확인된 묶음 버전만 휴대폰 설치 후보**로 올립니다.

`PRECHECK_NO_PHONE.bat`는 휴대폰 없이 엔진/프로젝트 검사를 다시 수행하는 용도입니다.

## 목표

서버비 없이 **Android 휴대폰 하나에서** 다음을 처리하는 독립 앱입니다.

- 최신 로또 당첨 데이터 업데이트
- 이번 주 추천 1~10게임
- 최우선 번호 / 실전 반복축
- 추천 점수 / 조합 순위
- 구매용 큰 화면
- 구매안 확정
- 실제 추천 기록
- 모바일 빠른 Walk-forward 연구
- 연구가 홀드아웃을 통과할 때만 가중치 반영

당첨 데이터 업데이트에만 인터넷을 사용합니다.
추천 계산과 기록은 휴대폰 내부에서 처리합니다.

---

## 구조

```text
Android UI (Kotlin / Jetpack Compose)
        ↓
Chaquopy 17
        ↓
mobile_engine.py (Python 3.13)
        ↓
Android SQLite
```

기존 데스크톱 연구소의 핵심 아이디어를 모바일용 순수 Python 엔진으로 옮겼습니다.
모바일 엔진은 pandas/numpy 없이 Python 표준 라이브러리만 사용하므로 APK 이식이 단순합니다.

---

## 현재 Mobile v1 기능

### 추천
- 6개 모델
  - 장기 빈도
  - 최근 추세
  - 미출현 간격
  - 동반 출현
  - 균형 혼합
  - 역추세
- 자동 후보 Pool
- 후보 조합 전수 계산
- 표준 / 집중 / 분산 포트폴리오
- 최우선 번호 / 실전 반복축
- 내부 추천 확신도

### 연구
모바일 첫 버전에서는 빠른 연구를 사용합니다.

- 최근 40회 Walk-forward
- 6개 모델 성적 비교
- 연구 가중치 생성
- 마지막 25% 홀드아웃 검증
- 통과할 때만 다음 추천에 반영

데스크톱의 무거운 진화형 + Monte Carlo 연구는 후속 모바일 버전에서
백그라운드 작업으로 추가하는 방향입니다.

### 기록
`SQLite`에 확정 구매안을 보관합니다.
새 회차 데이터가 업데이트되면 과거 확정 추천의 최고 일치 개수를 자동 계산합니다.

---

# APK 만드는 방법

## 방법 A — Android Studio 권장

1. Android Studio 설치
2. 이 폴더를 Android Studio에서 `Open`
3. SDK Manager에서 **Android SDK Platform 36** 설치
4. Gradle Sync
5. `Build > Build APK(s)`
6. 생성 파일:
   `app/build/outputs/apk/debug/app-debug.apk`

현재 Chaquopy 17은 Android Gradle Plugin 7.3~9.2.x를 지원하고,
Python 3.13도 지원합니다.
이 프로젝트는 AGP 9.2.1 + Python 3.13으로 고정했습니다.

## 방법 B — Windows 자동 빌드

Android Studio와 SDK 36이 설치되어 있다면:

`BUILD_DEBUG_APK.bat`

를 실행하세요.

스크립트가:
- Android SDK 확인
- Python 3.13 확인
- Gradle 9.4.1 다운로드
- APK 빌드

까지 진행합니다.

---

# 휴대폰 설치

Debug APK를 휴대폰으로 옮긴 뒤 설치하면 됩니다.

Android에서 처음 설치할 때는 브라우저/파일관리자의
`알 수 없는 앱 설치 허용`이 필요할 수 있습니다.

Google Play 등록은 필요 없습니다.

---

# 데이터

앱은 공개된 역대 로또 데이터 스냅샷을 사용합니다.

`https://raw.githubusercontent.com/JunKwon91/lotto-data/main/data/lotto-history.json`

첫 실행에는 인터넷 연결이 필요합니다.
이후 업데이트가 실패해도 휴대폰 DB에 저장된 기존 데이터로 추천할 수 있습니다.

---

# 다음 모바일 버전 후보

- 번호 고정 / 제외 UI
- 정밀 진화형 연구
- Monte Carlo 백그라운드 실행
- 연구 진행률 / 중단 / 재개
- 추첨일 알림
- 결과 발표 후 자동 사후분석
- 데이터 백업/복원
- 정식 Release APK 서명

---

# Google AI Studio 구현 체계

이 저장소는 Google AI Studio Build mode의 Native Android 프로젝트로 가져와 브라우저 Android Emulator에서 먼저 검증하는 운영을 권장합니다.

1. `ZERO_COST_POLICY.md` 확인
2. `docs/AI_STUDIO_MASTER_HANDOFF_PROMPT.md` 전체 전달
3. 첫 세션에서는 기능 추가 없이 Build + Emulator Audit만 수행
4. 검증 결과를 다시 ChatGPT에 전달해 다음 작업 프롬프트 작성
5. 안정 후보가 될 때까지 실제 휴대폰 APK 설치는 보류

기존 사용자의 다른 GitHub 저장소와는 완전히 분리해서 운영합니다.
