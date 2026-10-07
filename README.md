# G29 Operator Cockpit V4 — Windows + Android / DJI SDK tylko odczyt

Repozytorium zawiera źródła, nie prywatny pakiet APK/EXE z kluczem. **Stan projektu: kokpit + symulator + mostek + diagnostyka SDK; brak sterowania lotem Mini 2 SE.** Instrukcja dla świeżego klonu: [docs/github.md](docs/github.md). Gotowe prywatne paczki wymienione poniżej są lokalnymi artefaktami, nie plikami tego repozytorium.

Aktualny gotowy wariant: `../G29CockpitV4/G29CockpitV4.exe` oraz prywatny pakiet `../G29CockpitV4-Windows.zip`. Wariant Android zawiera rzeczywiste, niezmodyfikowane DJI Mobile SDK 4.18, rejestrację App Key, ręczne połączenie produktu i callbacki FlightController/baterii. Telemetria SDK jest odrębna od symulatora. Sterowanie lotem jest wyłączone: Mini 2 SE nadal nie ma oficjalnego wsparcia.

Instrukcja V4: `docs/START-V4.md`. Bez `-PwithDjiSdk=true` buduje się dotychczasowy niezależny mostek bez SDK. Klucz podaje się prywatnie przez DJI_APP_KEY lub DJI_KEYS_FILE, nie znajduje się w źródłach. Rejestracja i zgodność z telefonem/drone pozostają do późniejszego testu sprzętowego; na życzenie użytkownika SDK nie uruchamiano na telefonie podczas budowy.

## Zachowany pakiet V3

`dist/G29CockpitV3.exe` jest aplikacją Windows dla Logitech G29. Odczytuje osie, pokazuje HUD i atrapę drona na mapie, łączy się z rzeczywistym mostkiem Android i wykrywa pilota RC-N1 w trybie USB Accessory. Podgląd DJI Fly działa w osobnym oknie tylko do odczytu. Mapa/HUD nadal są symulacją, nie telemetrią drona.

Gotowy pakiet Windows zawiera EXE, `G29Bridge.apk` i folder `video`; pozostaw je razem. Raport: `AUDYT.md`, instrukcja: `dist/START-V3.md`. Mini 2 SE nie jest obsługiwany przez oficjalny SDK i nie jest sterowany przez ten pakiet.

## Szybki start

1. Podłącz zasilacz kierownicy i USB. Ustaw przełącznik G29 w trybie PS4 dla Windows.
2. Uruchom `dist/G29CockpitV3.exe`. `config.json` powinien leżeć obok pliku EXE.
3. Obróć kierownicą. W sekcji `RAW` zmieniać się powinna oś `A0`, a pasek `STEERING` i komenda `YAW` powinny reagować.
4. Kliknij `KALIBRACJA`: przez pierwsze 1,5 s trzymaj koło prosto i nie naciskaj pedałów; przez następne 10 s obróć koło do obu końców i wciśnij po kolei każdy pedał do końca. Aplikacja zapisze zmierzone zakresy.
5. Użyj `DEMO LOT`, żeby obejrzeć działanie mapy bez poruszania kierownicą. `RESET SYMULACJI` zeruje położenie i trasę.

Jeśli oś poruszająca się przy obrocie nie jest przypisana do `STEERING`, wybierz jej numer w sekcji `URZĄDZENIE / PRZYPISANIE OSI` i wykonaj kalibrację ponownie. Ustawienia czułości i profil można zapisać przyciskiem `ZAPISZ`.

## Android

W kokpicie kliknij `TELEFON / PILOT`. Odśwież listę, wybierz autoryzowany telefon, zainstaluj APK (jeśli nieobecny) i kliknij `POŁĄCZ MOSTEK`. Aplikacja sama ustawia `adb reverse` i uruchamia mostek. Panel obsługuje też parowanie kodem i łączenie przez ADB Wi-Fi. Pilot zajmuje port USB telefonu, więc Wi-Fi pozwala używać pilota równocześnie z mostkiem.

`ACK OK` potwierdza odbiór pakietów przez mostek, nie przez drona. RTT jest czasem obiegu, nie jednokierunkowym opóźnieniem. Przed ACK wysyłane są zera; brak/spóźnienie ACK 300 ms zamyka sesję. Android również zeruje stan po błędzie, EOF, STOP i braku pakietów 300 ms. `TX` mierzy wysłane pakiety. `STOP` lub Escape blokuje G29 i zamyka mostek do świadomego ponownego połączenia.

`OBRAZ DJI FLY` uruchamia dołączony odtwarzacz scrcpy z wyłączonym sterowaniem, schowkiem i audio. Otwórz DJI Fly i widok kamery na telefonie. To kopia ekranu telefonu z nakładkami, nie natywny strumień kamery drona. Wideo nie jest nagrywane i nie zastępuje bezpośredniej obserwacji podczas lotu.

Kokpit oraz symulator nie wysyłają komend lotu do DJI Mini 2 SE. Wartości na HUD są symulacją poleceń, nie telemetrią z drona.

## Uruchomienie ze źródeł

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python cockpit.py
```

## Budowanie EXE V4

```powershell
.\build_windows.ps1 -WithDjiSdk
```

Android: ustaw `ANDROID_HOME` i JDK Android Studio, w katalogu `android` uruchom `gradlew.bat :app:assembleDebug :app:lintDebug`. Gotowe APK to `app/build/outputs/apk/debug/app-debug.apk`. Budowa Windows nie pobiera odtwarzacza; zachowaj dostarczony folder video oraz jego licencję.

Testy: `python -m unittest discover -s tests -v`. Test dystrybucji V4: `../G29CockpitV4/G29CockpitV4.exe --self-test` zapisuje `self-test.json` obok EXE i kończy program. Nie wydaje komend lotu.

Przy pierwszym starcie aplikacja wyszukuje G29 automatycznie. Wykorzystuje `SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1`, bo SDL działa za oknem Tkinter; bez tego ustawienia kierownica może zgłaszać stałe zera.
