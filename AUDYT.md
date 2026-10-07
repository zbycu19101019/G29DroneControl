# Audyt G29 Cockpit V3 — 7 października 2026

To raport historyczny zachowanej dystrybucji V3. Aktualny moduł SDK tylko do odczytu i stan jego weryfikacji opisano w `AUDYT-V4.md`. V4 nie jest nadal sterownikiem lotu Mini 2 SE.

## Wynik

Gotowe: aplikacja Windows, odczyt G29, symulowany dron/HUD, panel ADB, rzeczywisty mostek Android z ACK, diagnostyka USB RC-N1 oraz osobne okno podglądu ekranu DJI Fly. Nie jest to sterownik lotu Mini 2 SE. W pakiecie nie ma działającego adaptera poleceń ani telemetrii z tego drona.

DJI jednoznacznie oznacza Mini 2 SE jako model bez SDK. Mini 2 i Mini SE to inne pozycje, nie zastępują Mini 2 SE. [Oficjalna zgodność DJI](https://repair.dji.com/help/content?customId=01700000763&lang=en&paperDocType=ARTICLE&re=US&spaceId=17).

## Znalezione problemy i poprawki

| Ważność | Problem | Stan V3 |
| --- | --- | --- |
| Wysoka | Android po EOF nie gwarantował wyzerowania i mógł zastosować opóźniony callback UI po STOP | Jeden blok synchronizacji; atomowy stan; STOP/EOF/błąd zerują; UI tylko odczytuje stan |
| Wysoka | Watchdog był uruchamiany ponownie przy kolejnych połączeniach, miał próg 400 ms i używał czasu ściennego | Jeden watchdog na klienta; 300 ms; zegar monotoniczny; zamknięcie gniazda; sprzątanie executorów |
| Wysoka | Brak kanału w JSON stawał się zerem, brak kontroli zakresów i kolejności | Wersja, sesja, sekwencja, wymagane pola, skończone wartości ±1; błędny pakiet kończy sesję |
| Wysoka | PC nie otrzymywał ACK, a status TCP sugerował działające łącze | Dwukierunkowy ACK, RTT, neutralne polecenia przed pierwszym ACK i przy jego utracie |
| Wysoka | Odwrócony pedał po kalibracji zmieniał spoczynek w pełne wciśnięcie | Kierunek określają zmierzone końce pedału; puszczony pedał zawsze 0 |
| Średnia | Odczyt ukrytego SDL nie reagował na G29 | Zachowano potwierdzoną wcześniej poprawkę SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1 |
| Średnia | Kalibracja mogła być użyta dla innego modelu urządzenia, jedna oś dla wielu kanałów | Powiązanie z GUID SDL; blokada powielonych przypisań; -1 wyłącza kanał; zmiana mapowania neutralizuje mostek |
| Średnia | Po odłączeniu G29 mogło dojść do automatycznego wznowienia komend | Zamknięcie mostka i zatrzask STOP; wznowienie wymaga kliknięcia POŁĄCZ G29 |
| Średnia | USB wykrywało wyłącznie tryb Host | Także UsbManager.accessoryList; nie otwiera portów, nie pyta o dostęp do DJI, nie odbiera danych Fly |
| Średnia | APK nie kompilował się: brak typów w Simulator i kolizje setterów Mock | Naprawiono; zbudowane APK; Gradle wrapper i zgodna lokalna konfiguracja AGP/Kotlin |
| Średnia | Dolny panel łącza znikał na mniejszym ekranie | Responsywne kolumny, przewijany panel, status łącza przeniesiony nad strojenie |
| Niska | Nieskończony log i znikająca siatka przy dalszym locie | Ograniczony log i siatka podążająca za kamerą; grafika czterech wirników + wektor prędkości |
| Średnia | Build Windows mógł zgłosić sukces mimo błędu i nadpisać kalibrację | Kontrola kodów zakończenia i zachowanie istniejącego dist/config.json |

## Testy

- Windows: 21 testów automatycznych przeszło. Obejmują mapowanie, pedały, NaN, profile, symulator, duplikaty osi, ACK fragmentowany/stary/spóźniony, EOF, STOP, sterowanie Tk i tryb podglądu bez kontroli/nagrywania.
- Gotowy EXE wykonano z --self-test: kod zakończenia 0, pygame/SDL obecne w dystrybucji, G29 wykryta, odtwarzacz obecny, flightControl=false. Nie wymaga zainstalowanego Pythona. ADB także jest dołączone w pakiecie video.
- Android: 7 testów instrumentacyjnych przeszło na fizycznym Samsung SM-S938B. Sprawdzają format, neutralizację wejścia, ACK, EOF, watchdog, powtórzenie sekwencji, STOP oraz limit długości ramki.
- APK: assembleDebug i lintDebug zakończone sukcesem. Lint ma ostrzeżenia dotyczące wersji narzędzi/target API i zasad backupu; nie jest to certyfikacja aplikacji lotniczej.
- Test PC → ADB Wi-Fi → Android: 304 pakiety wysłane, 303 ACK odebrane w 8 sekund; mediana RTT 31 ms, maksimum 47 ms. Ostatni pakiet był jeszcze w drodze przy zamknięciu próbki; nie jest to pomiar utraty pakietów radiowych drona.
- ACK telefonu pokazał akcesorium manufacturer=DJI, model=com.dji.logiclink, description=DJI RC-N1. permission=false dla mostka jest oczekiwane: dostęp do pilota pozostaje przy DJI Fly.
- Podgląd telefonu: uruchomiono scrcpy 5.0 na tym samym urządzeniu Android 16, dekoder Direct3D11/D3D11VA. Sześci sekundowy test zakończył się kodem 0; otrzymano klatki 592×1280 i licznik osiągnął 29 fps. Obraz ekranu telefonu nie dowodzi dostępności natywnego strumienia kamery przez SDK ani radiowego połączenia z dronem.
- Ponownego testu zakresów fizycznie obracanej G29 w tej turze nie wykonywano; wcześniejszy test potwierdził zakres około -1..+1 z ukrytym SDL. Bieżące testy GUI sprawdzają zmianę osi na kontrolowanych danych.

Watchdog 300 ms jest progiem programowym, nie gwarancją czasu rzeczywistego Windows/Android. Spóźnione ACK są odrzucane. Nie stanowi on failsafe samego statku powietrznego i nie wydaje polecenia RTH/lądowania.

## Obraz z DJI Fly

Dołączono oficjalny scrcpy 5.0 dla Windows x64. Rozmiar maksymalny 1280, limit 30 fps, bitrate 4 Mbps. Parametry --no-control, --no-clipboard-autosync i --no-audio wyłączają sterowanie, synchronizację schowka i dźwięk. Nie ma automatycznego nagrywania. Widać cały ekran telefonu, więc inne aplikacje/powiadomienia też mogą się pojawić; do podglądu zostaw DJI Fly na pierwszym planie.

[Oficjalna dokumentacja podglądu](https://github.com/Genymobile/scrcpy/blob/master/doc/video.md), [tryb tylko do odczytu](https://github.com/Genymobile/scrcpy/blob/master/doc/control.md).

## Co pozostaje niegotowe

- Brak sterowania lotem i telemetrii Mini 2 SE. Samo USB/ADB/ACK nie rozwiązuje braku SDK.
- Wariant oficjalnego DJI SDK jest nadal szkieletem do modelu wspieranego przez SDK, bez klucza/dependency/komend. Nie przedstawiam go jako gotowego sterownika.
- Wariant MAVLink jest osobnym przykładem, nie protokołem RC-N1 i nie został certyfikowany ani sprawdzony w locie.
- Starsze launchery i pliki legacy są zachowane, ale nie należą do audytowanej ścieżki V3. Używaj dist/G29CockpitV3.exe.
- Przed jakimkolwiek przyszłym adapterem lotu wymagane są osobne: autoryzacja sterowania, przejęcie/powrót do pilota, telemetria, ograniczenia lotu i testy naziemne. Obecny mostek jest wyłącznie diagnostyczny/bench.
- Wi-Fi i harmonogram systemu nie dają deterministycznego czasu reakcji. Podgląd ma dodatkowe opóźnienie względem telefonu; nie jest samodzielnym systemem bezpiecznego pilotażu.
