# G29 Cockpit V4 / SDK read-only — wynik budowy

Wariant V4 zawiera rzeczywistą integrację DJI Mobile SDK 4.18. Nie jest adapterem poleceń lotu Mini 2 SE. Klucz użytkownika jest skonfigurowany w prywatnym pliku budowy i osadzony w APK; nie sprawdzano jeszcze jego rejestracji na telefonie. Na prośbę użytkownika wykonano wyłącznie budowę i testy lokalne. Nie instalowano nowego APK, nie zamykano DJI Fly i nie uruchamiano połączenia SDK z pilotem/dronem.

## Zaimplementowane

- Oddzielna konfiguracja Gradle `withDjiSdk=true`; bez niej mostek kompiluje się bez DJI. SDK i jego chronione biblioteki pozostają niezmodyfikowane.
- Instalacja oryginalnego runtime SDK w Application przed użyciem API.
- Rejestracja App Key przez prawdziwe `DJISDKManager.registerApp`. Rejestracja nie rozpoczyna połączenia USB jako efekt uboczny.
- Ręczna sesja odczytu produktu przez `startConnectionToProduct`, z potwierdzeniem testu naziemnego. Nie ma automatycznego uruchomienia SDK z intencji ADB używanej do mostka.
- Callbacki produktu, komponentów, FlightController i baterii. Oddzielne flagi RC/product/FlightController, model UNKNOWN zachowany bez podszywania się pod Mini 2/Mini SE.
- Świeżość odczytu lotu 1500 ms i baterii 3000 ms; po STOP/disconnect stare callbacki nie przywracają danych. Brak danych jest null, nie fikcyjnym zerem.
- Rozszerzenie ACK o rzeczywisty stan SDK i próbki callbacków. Kanały G29 nadal są tylko stanem mostka/symulatora. Żaden pakiet wejściowy nie wywołuje API lotu.
- Panel Windows TELEFON / PILOT → DANE DJI SDK, odrębny od symulowanego horyzontu/mapy. Windows wymaga ACK <300 ms oraz świeżości odczytu z uwzględnieniem wieku ACK.
- Jawne uprawnienia lokalizacji/stanu telefonu, ręczne przejęcie USB i osobny STOP odczytu na telefonie. Brak automatycznych zgód przez ADB.
- App Key poza źródłami i poza archiwum jako plik tekstowy; nie został wypisany w logu/testach. APK zawiera go zgodnie z modelem integracji DJI, dlatego pakiet należy traktować jako prywatny.

## Sprawdzone lokalnie

- 27 testów Windows: PASS. Dotychczasowe 21 oraz 6 dotyczących diagnostyki SDK: świeżość, brak ACK, NaN/fałszywe typy, źródło callbacków, stara bateria, brak metod sterowania lotem i zamknięcie panelu.
- Gotowy EXE V4: self-test zakończony kodem 0, pygame 2.6.1 / SDL 2.28.4 w dystrybucji, G29 wykryta, odtwarzacz scrcpy obecny. To nie nowy test fizycznego obracania kierownicą.
- DJI APK: assembleDebug + assembleDebugAndroidTest + lintDebug zakończone sukcesem. Test APK z 8 testami instrumentacyjnymi został skompilowany, ale NIE uruchomiony na telefonie w tej turze. Wcześniejsze 7 testów V3 na urządzeniu pozostaje wyłącznie wynikiem historycznym V3.
- Podpis APK: poprawny, scheme v2. ZIP APK bez uszkodzeń. Manifest ma właściwy applicationId, klasę startową runtime DJI i klucz identyczny z prywatnym plikiem budowy. Dołączone 34 biblioteki natywne, tylko ABI arm64-v8a.
- Kopia V3 oraz jej kalibracja pozostają zachowane; V4 jest w osobnym katalogu.

## Ważne ostrzeżenia lint SDK

Lint wariantu SDK: 0 błędów, 15 ostrzeżeń. Nie ukrywano ich ani nie wyłączano sprawdzeń.

1. Oryginalne biblioteki DJI SDK 4.18 nie mają pełnego wyrównania 16 KB. Mogą nie działać na telefonach wymagających takiego wyrównania. Nie przebudowywano ani nie patchowano zamkniętych bibliotek. Android 16/Samsung wymaga osobnego testu uruchomienia.
2. Transytywne `bcpkix-jdk15on:1.57` zawiera klasy zgłoszone przez lint jako TrustAllX509TrustManager. Nie sprawdzono, czy są używane w faktycznych połączeniach SDK. Samo przejście lint NIE oznacza audytu bezpieczeństwa sieci vendor SDK. Nie zmieniano samowolnie bibliotek kryptograficznych SDK.
3. Pozostałe: nowszy Gradle, brak ABI x86_64 (świadomy wariant Android arm64, nie ChromeOS), zasady backupu i nieprzetłumaczone teksty polskiego panelu diagnostycznego.

## Pozostaje do testu sprzętowego

Uruchomienie chronionego runtime na Androidzie 16; faktyczny wynik rejestracji App Key; zgody/USB i konkurencja z DJI Fly; wykryty model; rzeczywiste callbacki i ich zgodność z fizycznie przechylanym dronem; utrata połączenia produktu. Odbywa się to wyłącznie na ziemi bez śmigieł i bez uruchamiania silników.

Mini 2 SE jest oficjalnie oznaczony jako niewspierany. Klucz nie dodaje wsparcia. Nawet częściowe callbacki nie dowodzą, że Virtual Stick zadziała. V4 nie zawiera wywołań Virtual Stick, startu/lądowania, silników, RTH, zdjęć/nagrywania ani zmian limitów lotu. Nie wykonano reverse engineeringu ani żadnych losowych komend USB.

Źródła: [DJI zgodność modeli](https://repair.dji.com/help/content?customId=01700000763&lang=en&paperDocType=ARTICLE&re=US&spaceId=17), [oficjalny przykład SDK v4.18](https://github.com/dji-sdk/Mobile-SDK-Android), [integracja i rejestracja](https://developer.dji.com/mobile-sdk/documentation/application-development-workflow/workflow-integrate.html).
