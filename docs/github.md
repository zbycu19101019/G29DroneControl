# Repozytorium źródłowe

Projekt obejmuje kokpit Windows, odczyt G29, symulator, mostek Android/ADB oraz opcjonalną integrację DJI Mobile SDK 4.18 tylko do odczytu. DJI Mini 2 SE nie ma oficjalnego wsparcia SDK. W tym repozytorium nie ma działającego sterowania lotem tego modelu.

Repozytorium zawiera źródła i dokumentację. Nie zawiera osobistego App Key, APK z osadzonym kluczem, gotowych EXE, nagrań/logów, kalibracji użytkownika, bibliotek DJI ani paczki scrcpy. SDK pobiera Gradle przy budowie. Domyślny config.json jest przykładową konfiguracją, nie kalibracją konkretnego urządzenia.

## Windows

Python 3.12, Windows i Logitech G29:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python cockpit.py
python -m unittest discover -s tests -v
```

G29: zasilacz, USB i przełącznik PS4. Pedały wymagają kalibracji. Horyzont i mapa pokazują wyłącznie symulację. Testy GUI używają Tk; uruchamiaj je w sesji Windows z pulpitem.

## Android

Potrzebne JDK Android Studio i Android SDK zgodny z android/app/build.gradle.kts. JAVA_HOME i ANDROID_HOME wskazują Twoje lokalne instalacje; w repozytorium nie zapisano ścieżek użytkownika.

Niezależny mostek bez SDK, z katalogu android:

```powershell
.\gradlew.bat :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug
```

Wariant DJI: zarejestruj własną aplikację Android o package name com.example.g29dronecontrol. Skopiuj dji-private.properties.example poza repozytorium, wstaw własny App Key i wskaż ten plik zmienną DJI_KEYS_FILE. Następnie:

```powershell
.\gradlew.bat -PwithDjiSdk=true :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug
```

Alternatywnie użyj zmiennej DJI_APP_KEY. Nie wpisuj klucza do źródeł, commitów, zgłoszeń ani logów. Gotowy wariant APK osadza klucz, więc nie publikuj go bez świadomej decyzji o sposobie dystrybucji. Sama poprawna rejestracja klucza nie dodaje wsparcia Mini 2 SE.

Mostek używa `adb reverse tcp:8765 tcp:8765`; watchdog kanałów testowych wynosi 300 ms. Pełny format: protocol.md. Testy połączenia DJI wykonuj na ziemi bez śmigieł. Instrukcje: START-V4.md; zakres weryfikacji i ostrzeżenia SDK: ../AUDYT-V4.md.

## Budowa pakietu Windows

W katalogu projektu `./build_windows.ps1 -WithDjiSdk` buduje APK i EXE. Wymaga powyższych zmiennych i własnego klucza. Folder wynikowy powstaje obok repozytorium; nie jest automatycznie commitowany. Bez przełącznika budowany jest wariant Android bez SDK.

Podgląd telefonu wymaga oficjalnego scrcpy z [Genymobile](https://github.com/Genymobile/scrcpy), dostępnego przez PATH lub w folderze video/scrcpy-win64-v5.0 obok EXE. Własne adb.exe można wskazać w panelu aplikacji. Tryb podglądu wyłącza sterowanie telefonem, schowek i audio; to kopia ekranu, nie natywny strumień DJI.

Nie dołączono SDK binarnego ani nie nadano licencji open-source całemu projektowi. DJI SDK podlega [DJI EULA](https://developer.dji.com/policies/eula/); licencja przykładowego kodu DJI nie obejmuje automatycznie SDK. scrcpy i inne zależności zachowują własne licencje.
