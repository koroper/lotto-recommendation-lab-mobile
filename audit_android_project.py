from pathlib import Path

root = Path(__file__).resolve().parent
checks = []

def ck(name, cond):
    checks.append((name, bool(cond)))

app_gradle = (root / 'app/build.gradle.kts').read_text(encoding='utf-8')
root_gradle = (root / 'build.gradle.kts').read_text(encoding='utf-8')
properties = (root / 'gradle.properties').read_text(encoding='utf-8')
manifest = (root / 'app/src/main/AndroidManifest.xml').read_text(encoding='utf-8')
repo = (root / 'app/src/main/java/com/lotto/lab/data/LottoRepository.kt').read_text(encoding='utf-8')
db = (root / 'app/src/main/java/com/lotto/lab/data/LottoDb.kt').read_text(encoding='utf-8')
vm = (root / 'app/src/main/java/com/lotto/lab/MainViewModel.kt').read_text(encoding='utf-8')

ck('AGP 9.2.1 pinned', 'version "9.2.1"' in root_gradle)
ck('AGP built-in Kotlin used', 'org.jetbrains.kotlin.android' not in root_gradle and 'org.jetbrains.kotlin.android' not in app_gradle)
ck('Built-in Kotlin not disabled', 'android.builtInKotlin=false' not in properties)
ck('Compose compiler 2.2.10 pinned', 'org.jetbrains.kotlin.plugin.compose") version "2.2.10"' in root_gradle)
ck('Chaquopy 17.0.0 pinned', 'version "17.0.0"' in root_gradle)
ck('Python 3.13 pinned', 'version = "3.13"' in app_gradle)
ck('Legacy android.kotlinOptions removed', 'kotlinOptions' not in app_gradle)
ck('minSdk >=24', 'minSdk = 26' in app_gradle)
ck('compileSdk 37', 'compileSdk = 37' in app_gradle)
ck('targetSdk remains 36', 'targetSdk = 36' in app_gradle)
ck('arm64 ABI', '"arm64-v8a"' in app_gradle)
ck('INTERNET permission', 'android.permission.INTERNET' in manifest)
ck('PyApplication', 'com.chaquo.python.android.PyApplication' in manifest)
ck('payload validation', 'validatePayload(payload)' in repo)
ck('latest from drawNo', 'onlineLatest' in repo and 'getInt("drawNo")' in repo)
ck('confirmed ID DB', 'confirmedRecommendationId' in db)
ck('confirmed ID ViewModel', 'confirmedRecommendationId(rec.targetDraw) == rec.recommendationId' in vm)
ck('versionCode increment', 'versionCode = 2' in app_gradle)

for name, passed in checks:
    print(('PASS' if passed else 'FAIL'), '-', name)
if not all(passed for _, passed in checks):
    raise SystemExit('static audit failed')
print(f'ANDROID STATIC AUDIT PASS ({len(checks)} checks)')
