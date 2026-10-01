# LottoLab Android Mobile v1.1 자체 검증 보고서

## 검증 결론

- 모바일 추천 엔진 회귀 테스트: **PASS**
- Desktop v5.4 추천 엔진 parity: **PASS**
- Android 프로젝트 정적 감사: **PASS**
- 순수 Kotlin 모델 컴파일: **PASS**
- 실제 Android APK assemble/emulator: **아직 미실행** (현재 실행 환경에 Android SDK/Gradle 의존성 캐시가 없고 외부 바이너리 다운로드가 차단되어 있음)

## 추천 엔진 검증 결과

```text
MOBILE V1.1 VALIDATION PASS
Exact desktop parity: 6/6 cases
Additional top/pool parity: 8/8 histories
Recommendation benchmark (1000 draws): 0.117s
Quick research benchmark (25 draws): 0.124s
Recommendation ID: 1001-8DA09840DF
Research: 빠른 연구 보정 가중치를 적용합니다.
```

Desktop v5.4와 모바일 엔진을 서로 다른 synthetic history에 대해 비교했고, 검증 케이스에서 **상위 6개 번호 / 자동 후보 Pool / 최종 5게임이 모두 일치**하도록 모바일 포트폴리오 로직을 데스크톱 빔 탐색과 맞췄습니다.

## Android 정적 감사

```text
PASS - AGP 9.2.1 pinned
PASS - Kotlin 2.2.10 pinned
PASS - Chaquopy 17.0.0 pinned
PASS - Python 3.13 pinned
PASS - minSdk >=24
PASS - compileSdk 36
PASS - arm64 ABI
PASS - INTERNET permission
PASS - PyApplication
PASS - payload validation
PASS - latest from drawNo
PASS - confirmed ID DB
PASS - confirmed ID ViewModel
PASS - versionCode increment
ANDROID STATIC AUDIT PASS (14 checks)
```

## Kotlin 컴파일 검사

```text
no errors
KOTLIN MODELS COMPILE PASS
```

## 이번 감사에서 수정한 실제 문제

1. **최신 회차 갱신 안정화**: 외부 JSON의 특정 보조 키만 믿지 않고 `data[].drawNo`의 최대 회차를 직접 계산합니다.
2. **데이터 검증 강화**: 중복 회차, 번호 중복, 1~45 범위 오류, 보너스 번호 중복을 DB 저장 전에 차단합니다.
3. **추천 parity 강화**: 모바일 5게임 포트폴리오를 Desktop v5.4와 같은 빔 탐색 목적함수로 변경했습니다.
4. **확정 구매안 오인 방지**: 같은 회차에 기존 확정안이 있어도 현재 추천안 ID가 달라졌다면 '확정 완료'로 잘못 표시하지 않습니다.
5. **빠른 연구 최소 표본 보호**: 연구에 사용할 충분한 과거 데이터가 없으면 억지로 짧은 훈련 구간을 돌리지 않습니다.
6. **업데이트 설치 준비**: applicationId는 그대로 유지하고 versionCode를 2로 올려, 향후 같은 서명 APK는 새 앱을 계속 쌓기보다 업데이트 설치하는 흐름을 사용하도록 했습니다.

## 휴대폰 설치 요청 Gate

앞으로는 다음 조건을 충족하기 전에는 휴대폰에 APK를 반복 설치해달라고 요청하지 않습니다.

1. 엔진 회귀 테스트 PASS
2. Desktop parity PASS
3. Android 정적 감사 PASS
4. 실제 Gradle `assembleDebug` PASS
5. 가능하면 Emulator smoke test PASS

현재 1~3은 통과했습니다. 다음 기술 목표는 **실제 APK build gate**입니다.

## 자동 APK Build Gate 준비

프로젝트에 `.github/workflows/android-ci.yml`을 추가했습니다. GitHub 저장소에 올리면 휴대폰 설치 없이 CI에서 다음 순서로 검증하도록 구성되어 있습니다.

1. Python 3.13
2. JDK 17
3. Android SDK 36 / Build Tools 36.0.0
4. Gradle 9.4.1
5. 모바일 엔진 parity 검증
6. Android 정적 감사
7. `:app:assembleDebug`
8. 성공한 APK를 CI artifact로 업로드

따라서 다음부터는 **CI APK 빌드가 성공한 뒤에만** 실제 휴대폰 설치 후보로 올리는 흐름을 사용할 수 있습니다.
