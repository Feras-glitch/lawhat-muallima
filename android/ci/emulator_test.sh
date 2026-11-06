#!/bin/bash
# يُشغَّل داخل android-emulator-runner: تثبيت بناء الاختبار، ثم فحص الواجهة داخل التطبيق ولقطات الشاشة
set -e
NAME="$1"
APK=android/app/build/outputs/apk/release/app-release.apk
adb wait-for-device
adb shell settings put global window_animation_scale 0
adb shell settings put global transition_animation_scale 0
adb shell settings put global animator_duration_scale 0
adb install -r "$APK"
mkdir -p shots
python3 android/ci/webview_check.py app.lawhat.muallima.preview app.lawhat.muallima.MainActivity "shots/$NAME"
