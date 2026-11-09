# LikhKeDo for Android

**Download:** [LikhKeDo.apk](https://github.com/vanshikacs/LikhKeDo/raw/main/LikhKeDo.apk) (21 KB, Android 7.0 or newer).
On the phone, open the link and allow "Install unknown apps" for your browser when asked.

The app is the live site (https://likh-ke-do.vercel.app) in an Android WebView, plus the phone features the site needs:

| Feature | How |
|---|---|
| Listen mode | Asks for the microphone only when you tap Start (Android permission prompt) |
| Policy PDF upload | Opens the Android file picker |
| "Likh Ke Do" slip | The slip's Print button opens Android printing ("Save as PDF" works too) |
| Back button | Goes back inside the app |
| Other links | Open in the phone's browser; only the LikhKeDo site and API load inside the app |
| No internet | A retry page in English and Hindi |

No analytics, no extra permissions beyond internet and microphone, no AndroidX libraries.

## Build

```
bash android/build.sh
```

Uses only the Android SDK (build-tools 35.0.1, platform android-35) and a JDK 17+ (Android Studio's bundled JBR):
`aapt2 → javac → d8 → zipalign → apksigner`, no Gradle. The signing key is created on the first run in `~/.likhkedo/`
(outside the repo, never committed). Keep it: an update installs over an old version only with the same key.

Tested on the Android 15 emulator (Pixel 9 Pro XL): home, saved Hindi case, slip, print dialog, microphone prompt.
