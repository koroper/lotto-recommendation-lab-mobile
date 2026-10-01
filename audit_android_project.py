from pathlib import Path
import re
root=Path(__file__).resolve().parent
checks=[]
def ck(name,cond): checks.append((name,bool(cond)))
g=(root/'app/build.gradle.kts').read_text(encoding='utf-8'); top=(root/'build.gradle.kts').read_text(encoding='utf-8'); man=(root/'app/src/main/AndroidManifest.xml').read_text(encoding='utf-8'); repo=(root/'app/src/main/java/com/lotto/lab/data/LottoRepository.kt').read_text(encoding='utf-8'); db=(root/'app/src/main/java/com/lotto/lab/data/LottoDb.kt').read_text(encoding='utf-8'); vm=(root/'app/src/main/java/com/lotto/lab/MainViewModel.kt').read_text(encoding='utf-8')
ck('AGP 9.2.1 pinned','version "9.2.1"' in top); ck('Kotlin 2.2.10 pinned','version "2.2.10"' in top); ck('Chaquopy 17.0.0 pinned','version "17.0.0"' in top); ck('Python 3.13 pinned','version = "3.13"' in g); ck('minSdk >=24','minSdk = 26' in g); ck('compileSdk 36','compileSdk = 36' in g); ck('arm64 ABI','"arm64-v8a"' in g); ck('INTERNET permission','android.permission.INTERNET' in man); ck('PyApplication','com.chaquo.python.android.PyApplication' in man); ck('payload validation','validatePayload(payload)' in repo); ck('latest from drawNo','onlineLatest' in repo and 'getInt("drawNo")' in repo); ck('confirmed ID DB','confirmedRecommendationId' in db); ck('confirmed ID ViewModel','confirmedRecommendationId(rec.targetDraw) == rec.recommendationId' in vm); ck('versionCode increment','versionCode = 2' in g)
for n,p in checks: print(('PASS' if p else 'FAIL'),'-',n)
if not all(p for _,p in checks): raise SystemExit('static audit failed')
print(f'ANDROID STATIC AUDIT PASS ({len(checks)} checks)')
