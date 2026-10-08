# G29 Cockpit V4 / DJI SDK — tylko odczyt

Ta wersja zawiera aplikację Windows oraz APK z rzeczywistym, niezmodyfikowanym DJI Mobile SDK 4.18 i Twoim App Key. Nie wysyła poleceń lotu. Mini 2 SE nie ma oficjalnego wsparcia SDK; to test rzeczywistych możliwości połączenia i odczytu, nie obietnica kompatybilności.

Aktualizacja Android 0.5: aplikacja uzyskuje zgodę USB w Androidzie przed rozpoczęciem sesji SDK. Szczegóły i komunikaty: [USB-FIX-0.5.md](USB-FIX-0.5.md). Nie zmieniono targetSdk 34 ani zabezpieczeń systemu lub SDK.

## Teraz: uruchomienie Windows

Rozpakuj cały ZIP do osobnego katalogu i uruchom G29CockpitV4.exe. Zachowaj obok config.json, G29Bridge.apk oraz folder video. Nie trzeba instalować Pythona ani Android Studio. Twoja wcześniejsza kalibracja została skopiowana, nie nadpisana w V3. G29: zasilanie i USB, przełącznik PS4.

TELEFON / PILOT → DANE DJI SDK otwiera osobny panel diagnostyczny. Panel nie zastępuje symulatora: główny horyzont i mapa pozostają wyraźnie symulowane. Bez świeżych callbacków SDK nie ma telemetrii i nie ma zmyślonych wartości zastępczych.

Pierwotna budowa V4 nie obejmowała testu telefonu. W późniejszym teście użytkownik uzyskał `REGISTERED`, ale połączenie produktu nie powstało. Log SDK wykazał niedozwolony mutable implicit PendingIntent podczas żądania zgody USB. Wariant 0.5 usuwa tę ścieżkę z naszego rozpoczęcia odczytu, pobierając zgodę wcześniej przez API Androida. DJI Fly pozostaje niezmienione.

## Później: naziemny test odczytu

1. Włącz drona na ziemi, zdejmij śmigła. Nie uruchamiaj silników. Pilot pozostaje podłączony do telefonu.
2. PC i telefon: ta sama zaufana sieć Wi-Fi, ADB autoryzowane. TELEFON / PILOT → ODŚWIEŻ TELEFONY → wybierz telefon w stanie device.
3. ZAINSTALUJ APK aktualizuje nasz mostek do wariantu DJI; nie modyfikuje DJI Fly. To ten sam pakiet Android, nie dwie równoległe instalacje.
4. POŁĄCZ MOSTEK uruchamia wyłącznie kanał PC ↔ telefon. ACK OK nie oznacza sterowania dronem.
5. Na telefonie kliknij REJESTRUJ DJI SDK. Telefon potrzebuje internetu. SDK wymaga zgód na lokalizację i stan telefonu; aplikacja prosi o nie jawnie. REGISTERED oznacza potwierdzenie rejestracji przez SDK, nie wsparcie drona.
6. Zamknij DJI Fly, żeby nie konkurował o USB pilota. Kliknij ODCZYT DJI / BEZ KOMEND LOTU, potwierdź przygotowanie stanowiska i zaakceptuj zgodę USB w oknie Androida (jeżeli nie została już przyznana). Podczas oczekiwania `connection` to `WAITING_USB_PERMISSION`. SDK rozpocznie sesję dopiero po rzeczywistej zgodzie. Jeśli Android poprosi o aplikację obsługującą akcesorium DJI, wybierz G29 DJI / READ ONLY. Po odłączeniu/podłączeniu kabla okno wyboru może pojawić się ponownie. Nie wybieraj stałej aplikacji, jeśli chcesz łatwo wracać do DJI Fly.
7. Obserwuj registration, model, productConnected, rcConnected, flightControllerConnected i telemetryFresh w telefonie oraz DANE DJI SDK na PC. UNKNOWN_AIRCRAFT, false lub null są prawdziwymi wynikami, nie błędami ukrywanymi przez symulator. Wartości SDK wymagają późniejszego potwierdzenia zgodności z fizycznym dronem.
8. ZATRZYMAJ ODCZYT DJI kończy sesję SDK. STOP MOSTKA kończy kanał PC i odczyt SDK. STOP w Windows kończy kanał PC; sam odczyt diagnostyczny SDK może działać dalej, więc zakończ go również na telefonie. Do powrotu do DJI Fly zamknij nasz wariant DJI i w razie potrzeby podłącz kabel pilota ponownie.

Podgląd video kopiuje cały ekran telefonu. Podczas używania DJI SDK pokazuje ekran naszej aplikacji; DJI Fly i test SDK nie są równoległymi źródłami obrazu. Nie ma jeszcze natywnego dekodera wideo SDK w tym wariancie.

## Ograniczenia i prywatność

Telemetria lotu jest uznawana za świeżą maksymalnie 1500 ms od callbacku SDK, bateria 3000 ms. Windows dodatkowo wymaga ACK młodszego niż 300 ms. Stare dane są ukrywane. Jest to diagnostyka, nie certyfikowany failsafe lotu. Żadne pakiety G29 nie są przekazywane do FlightController.

Wariant SDK jest dla Android arm64-v8a. Na Samsungu/Androidzie 16 potwierdzono uruchomienie aplikacji i rejestrację App Key. Nie potwierdzono połączenia produktu, callbacków telemetrii ani pełnej zgodności SDK z tym telefonem i dronem. Nie zmodyfikowano SDK, firmware, geofencingu, limitów ani RTH. Nie wykonano reverse engineeringu ani losowych komend USB.

Lint wykrywa również stare biblioteki natywne SDK bez pełnego wyrównania 16 KB i ostrzeżenie o klasach TrustAllX509TrustManager w zależności vendor SDK. Szczegóły i zakres testów: AUDYT-V4.md. Udana budowa nie oznacza pełnej zgodności runtime ani audytu bezpieczeństwa SDK DJI.

App Key jest poza kodem źródłowym, ale zgodnie z modelem DJI znajduje się w gotowym APK. ZIP i APK traktuj jako swój prywatny pakiet; nie publikuj ich z osobistym kluczem. Sam klucz nie zapewnia obsługi Mini 2 SE.

## Budowa ze źródeł

Ustaw JAVA_HOME na JDK Android Studio oraz ANDROID_HOME na Android SDK. Klucz podaj przez DJI_APP_KEY albo DJI_KEYS_FILE (plik properties z polem djiAppKey). Nie dodawaj klucza do repozytorium.

W katalogu projektu: `./build_windows.ps1 -WithDjiSdk`. Sam Android: w katalogu android `./gradlew.bat -PwithDjiSdk=true :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug`. Bez flagi withDjiSdk powstaje niezależny mostek testowy bez SDK.

Oficjalne źródła: [DJI SDK 4.18 / przykład integracji](https://github.com/dji-sdk/Mobile-SDK-Android), [rejestracja aplikacji](https://developer.dji.com/mobile-sdk/documentation/application-development-workflow/workflow-integrate.html), [zgodność produktów](https://repair.dji.com/help/content?customId=01700000763&lang=en&paperDocType=ARTICLE&re=US&spaceId=17).
