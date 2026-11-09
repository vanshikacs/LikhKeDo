#!/usr/bin/env bash
# Build LikhKeDo.apk with the Android SDK command-line tools only (no Gradle, no AndroidX).
# Needs: Android SDK (build-tools 35.0.1, platforms/android-35) and a JDK 17+ (Android Studio's bundled JBR works).
# The signing key lives OUTSIDE the repo in ~/.likhkedo/ and is created on the first run. Keep it: Android only
# installs an update over an existing install if it is signed with the same key.
set -euo pipefail
cd "$(dirname "$0")"

SDK="${ANDROID_HOME:-${LOCALAPPDATA:-$HOME}/Android/Sdk}"
BT="$SDK/build-tools/35.0.1"
JAR="$SDK/platforms/android-35/android.jar"
JAVA_HOME="${JAVA_HOME:-/c/Program Files/Android/Android Studio/jbr}"
export JAVA_HOME PATH="$JAVA_HOME/bin:$PATH"
VERSION_CODE="${VERSION_CODE:-1}"
VERSION_NAME="${VERSION_NAME:-1.0}"

KEYDIR="$HOME/.likhkedo"
KS="$KEYDIR/release.jks"
PASSFILE="$KEYDIR/release.pass"
if [ ! -f "$KS" ]; then
  mkdir -p "$KEYDIR"
  python -c "import secrets; print(secrets.token_urlsafe(24))" > "$PASSFILE"
  PASS="$(cat "$PASSFILE")"
  keytool -genkeypair -keystore "$KS" -alias likhkedo -keyalg RSA -keysize 3072 -validity 10000 \
    -storepass "$PASS" -keypass "$PASS" -dname "CN=LikhKeDo, O=LikhKeDo, C=IN" >/dev/null 2>&1
  echo "created signing key in $KEYDIR (back it up; never commit it)"
fi

rm -rf build && mkdir -p build/gen build/classes build/dex
"$BT/aapt2" compile --dir res -o build/res.zip
"$BT/aapt2" link -o build/base.apk -I "$JAR" --manifest AndroidManifest.xml --java build/gen \
  --min-sdk-version 24 --target-sdk-version 35 --version-code "$VERSION_CODE" --version-name "$VERSION_NAME" \
  build/res.zip
javac -nowarn -source 11 -target 11 -classpath "$JAR" -d build/classes \
  $(find src build/gen -name '*.java') 2>&1 | grep -v "bootstrap classpath\|^1 warning\|source value 11\|target value 11\|To suppress warnings" || true
"$BT/d8.bat" --release --min-api 24 --lib "$JAR" --output build/dex $(find build/classes -name '*.class')
python - <<'EOF'
import shutil, zipfile
shutil.copy("build/base.apk", "build/unsigned.apk")
with zipfile.ZipFile("build/unsigned.apk", "a", zipfile.ZIP_DEFLATED) as z:
    z.write("build/dex/classes.dex", "classes.dex")
EOF
"$BT/zipalign" -p -f 4 build/unsigned.apk build/aligned.apk
W() { command -v cygpath >/dev/null && cygpath -w "$1" || echo "$1"; }
"$BT/apksigner.bat" sign --ks "$(W "$KS")" --ks-key-alias likhkedo --ks-pass "file:$(W "$PASSFILE")" \
  --out ../LikhKeDo.apk build/aligned.apk
"$BT/apksigner.bat" verify --print-certs ../LikhKeDo.apk | grep -i "digest: \|verified" || "$BT/apksigner.bat" verify -v ../LikhKeDo.apk
ls -l ../LikhKeDo.apk
