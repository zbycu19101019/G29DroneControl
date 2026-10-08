# Audyt bezpieczeństwa — G29 Operator V5 / Android 0.6

Data: 2026-10-08. Zakres: własny kod Windows/Python i Android/Kotlin/Java, protokół, uprawnienia, cykl życia, kalibracja, dane SDK, testy awarii, budowa oraz prywatna dystrybucja. To przegląd inżynierski i testy regresji, nie certyfikacja sterownika lotu, pełny pentest telefonu ani audyt zamkniętego firmware/SDK DJI.

## Najważniejszy wniosek

Pakiet nie steruje lotem Mini 2 SE i nie ma rzeczywistej ochrony antykolizyjnej. Mini 2 SE ma czujniki skierowane w dół, nie system wykrywania ścian. Nie wolno traktować ograniczenia symulatora, limitu kanałów, STOP ani podglądu kamery jako ochrony przed uderzeniem. Brak obsługiwanej integracji i czujników pozostaje ograniczeniem sprzętu/platformy, nie błędem poprawianym zmianą UI.

USB pilota i REGISTERED były potwierdzone wcześniej. Świeża telemetria i działanie na fizycznym Mini 2 SE nie zostały zweryfikowane w tym wydaniu. Obecne testy telefonu nie rejestrowały SDK, nie otwierały sesji odczytu DJI i nie wydawały komend lotu.

Najnowszy zrzut użytkownika dodatkowo pokazuje REGISTERED, USB GRANTED i RC-N1 permission:true, ale STOPPED / model UNKNOWN i odrzucony start SDK. Potwierdza to wykrycie/zgodę USB, nie przyczynę błędu SDK ani pełne połączenie radiowe. Komunikat po startConnectionToProduct()==false został poprawiony: bez bezpodstawnego zalecania zmiany kabla, z wyraźnym rozdzieleniem faktów i możliwych przyczyn. Nie zidentyfikowano jednoznacznej przyczyny i nie ukryto odmowy SDK jako sukcesu.

## Model zagrożeń

Chronimy przed przypadkowym/nieuprawnionym lokalnym procesem bez klucza sesji, starymi lub uszkodzonymi pakietami, błędną kalibracją, zanikiem wejścia/łącza oraz mylącym przedstawieniem niepełnych odczytów. Nie chronimy przed administratorem PC, zrootowanym telefonem, zaufanym hostem ADB, wykradzeniem klucza z pamięci/debuggera ani świadomie zatwierdzonym złośliwym klientem.

Mostek słucha wyłącznie na literalnym IPv4 127.0.0.1. Dostęp telefonu odbywa się przez autoryzowane ADB reverse, nie otwarty serwer LAN. HMAC uwierzytelnia dane; nie szyfruje ich. Transport bezprzewodowego ADB i jego autoryzacja pozostają oddzielną warstwą zaufania.

## Ustalenia i wdrożone zmiany

| Ustalenie w poprzednim kodzie | Wdrożona zmiana | Weryfikacja |
| --- | --- | --- |
| Lokalny TCP nie uwierzytelniał każdego pakietu | Protokół v2, losowy 256-bitowy klucz, HMAC-SHA256 dokładnego UTF-8, porównanie podpisu constant-time | Zły klucz, zmieniony podpis, Unicode Python→Android, odrzucenie v1 |
| Zewnętrzny Intent mógł inicjować połączenie bez potwierdzenia | Intent tylko proponuje sesję; porównanie publicznego kodu i zgoda użytkownika na telefonie | Test connect=true nie uruchamia mostka |
| Brak wyraźnego powiązania z każdym połączeniem | Losowy nonce telefonu, losowa sesja PC, rosnąca sekwencja; pierwszy pakiet neutralny | Stary nonce/sekwencja/sesja i pierwszy aktywny pakiet odrzucone |
| Kolejny klient mógł zastąpić sesję | Drugi socket jest zamykany, aktywna sesja nie jest zastępowana | Test dwóch klientów |
| STOP po stronie PC nie był trwałym STOP po stronie Androida | Podpisany STOP zamyka kanał i zatrzymuje odczyt SDK; ręczne wznowienie | STOP lokalny/zdalny, późniejszy pakiet nie reaktywuje kanałów |
| Rozłączenie mogło zostawić optycznie „włączone” kanały | Utrata sesji odznacza przełącznik; błąd/EOF/watchdog zeruje stan; żadnego reconnectu Androida | Testy utraty wejścia i ACK |
| Niepełne/nieaktualne callbacki mogły wprowadzać w błąd | Warunki READ_ONLY + połączony produkt + świeżość; FC dla telemetrii; brak danych jako null; nigdy flightControl=true | Testy świeżości i braku FC/produktu |
| Kalibracja akceptowała niektóre błędne typy/zakresy | Ścisłe typy, skończone liczby, prawidłowy środek i zakresy, rozdzielenie osi, bezpieczne pedały | Testy bool/NaN/Inf/odwrócenia/niepełnej kalibracji |
| Zapis ustawień i zamykanie GUI miały słabe punkty | Unikalny plik tymczasowy, fsync i atomowa zamiana; anulowanie timerów zamykanych paneli | Test zachowania pliku po błędzie i GUI |
| Niepotrzebna precyzyjna lokalizacja w transmisji | Usunięto latitude/longitude z własnego eksportu callbacków | Przegląd eksportu; SDK nadal może wymagać zgody lokalizacyjnej |

Zachowano wcześniejszą naprawę USB: wyłącznie pilot DJI, pakietowy immutable PendingIntent z unikalnym nonce, nieeksportowany receiver, timeout i anulowanie STOP. Nie zmieniono firmware, fly-safe-database, geofencingu, RTH ani innych zabezpieczeń DJI.

## Dodatkowe mechanizmy ostrożności

- Kanały G29 do telefonu domyślnie wyłączone; ich włączenie wymaga świadomego potwierdzenia testu na ziemi bez śmigieł.
- Domyślny limit znormalizowanego kanału 0,35 i ograniczenie zmian 1,2 jednostki/s. Brak interpretacji jako rzeczywista prędkość.
- Przerwa pętli Windows ≥300 ms zatrzymuje aktywny odczyt/mostek/demo; watchdog telefonu sprawdzany również podczas odbioru po wznowieniu urządzenia. To zegary programowe, nie gwarancja czasu rzeczywistego.
- Świeża bateria ≤20% blokuje kanały testowe; ≤30% ostrzega. Nieznany/stary odczyt jest jawnie oznaczony.
- STOP stale dostępny w dolnej części Androida i na pasku Windows; Escape w Windows. STOP nie jest poleceniem awaryjnego wyłączenia silników ani hamowania.
- Odczyt DJI wymaga trzech potwierdzeń. Przejście Activity w tło kończy odczyt i oczekującą zgodę USB.
- Podgląd telefonu jest tylko do odczytu, bez nagrywania, sterowania, schowka i audio.
- Granica wirtualnego pokoju zatrzymuje jedynie model symulacyjny. Nie ma detekcji ścian, geofencingu pokoju ani komputerowej analizy wideo.

## Pozostałe ograniczenia / otwarte ryzyka

1. **Brak realnej ochrony lotu — zasadnicze ograniczenie.** Nie ma obsługiwanej integracji sterowania Mini 2 SE. App Key, USB i ACK nie nadają uprawnienia ani potwierdzenia przyjęcia komendy przez drona.
2. **Natywne DJI SDK 4.18 / pamięć 16 KB.** Lint zgłasza brak wyrównania bibliotek. Nie można wiarygodnie naprawić ELF przez zmianę motywu/manifestu lub samo zipalign. Bibliotek nie patchowano; aktualizacja producenta pozostaje potrzebna. Wcześniejszy odczyt telefonu wykazał strony 4096 B, co nie certyfikuje działania na urządzeniach 16 KB.
3. **Zależności zamkniętego SDK.** Lint znajduje TrustAllX509TrustManager w zależności bcpkix 1.57. Nie wykazano osiągalności tych implementacji w używanej ścieżce; nie twierdzimy, że potwierdzono exploit. Nie zamieniono arbitralnie kryptografii wewnątrz SDK.
4. **Build deweloperski.** Prywatny APK jest debuggable, podpisany dotychczasowym certyfikatem debug; EXE nie ma Authenticode. Produkcyjne podpisywanie, własność kluczy i pełna dystrybucja to osobny etap. Nie usunięto ostrzeżeń Androida przez ukrywanie ich manifestem.
5. **Klucze i prywatność.** Klucz HMAC nie trafia do konfiguracji/logów i jest maskowany przy błędzie uruchomienia ADB. Jest jednak przekazywany przez zaufane ADB/Intent i obecny w pamięci. Osobisty DJI App Key musi być osadzony w prywatnym APK; źródła go nie zawierają. Vendor SDK może wykonywać własne połączenia sieciowe i przechowywać dane diagnostyczne. allowBackup=false nie zastępuje pełnego audytu transferów OEM.
6. **Warunki rzeczywiste.** Nie testowano tej wersji w locie, zachowania baterii na dronie, interferencji radiowej ani odległości od ściany. Zawsze trzymaj możliwość ręcznego sterowania standardowym pilotem. Testy tej aplikacji wyłącznie na ziemi bez śmigieł.

## Wykonane sprawdzenia

- Windows: **45 testów — PASS**. Mapowanie/pedały, NaN/Inf, kalibracja, bezpieczny zapis, podpisy, nonce/sesje/sekwencje, RTT/ACK/EOF, drugi klient, STOP, brak API lotu, świeżość SDK, limit/slew, 10 000 kroków symulacji, geometria GUI 960×700 i 1180×820, maskowanie klucza ADB.
- Android SDK 0.6 na Samsung SM-S938B / Android 16: **18 testów — PASS**. Protokół, podpisy, złe nonce, pierwszy pakiet neutralny, STOP, watchdog, EOF, limity ramki, świeżość, zgoda USB bez faktycznego jej żądania, Intent bez auto-connect, własny render UI oraz komunikat odróżniający odrzucenie SDK od problemu kabla.
- Gradle assembleDebug / assembleDebugAndroidTest / lintDebug: **PASS**, zarówno wariant SDK, jak i wariant bez SDK.
- Lint wariantu SDK: **0 błędów, 13 ostrzeżeń**, w tym znane SDK/ABI, TLS, backup oraz sugestie KTX. Nie wyciszono ostrzeżeń bezpieczeństwa.
- Prywatny APK: poprawny podpis, zachowany certyfikat aktualizacji, zgodność package/private App Key, 34 oryginalne biblioteki arm64 i integralność ZIP.
- Android 0.6 zainstalowany przez install -r. Brak automatycznej rejestracji SDK / odczytu / startu drona.
- Końcowy EXE i ZIP podlegają dodatkowo sprawdzeniu dystrybucji opisanym w WERYFIKACJA-V5.json obok aplikacji. Wynik wykrycia G29 to pojedynczy odczyt, nie ponowny test fizycznego zakresu ruchu.

## Źródła pierwotne

- [DJI Mini 2 SE — brak obstacle avoidance](https://www.dji.com/support/product/mini-2-se)
- [DJI — lista wsparcia SDK](https://repair.dji.com/help/content?customId=01700000763&lang=en&paperDocType=ARTICLE&re=US&spaceId=17)
- [Android — bezpieczeństwo aplikacji](https://developer.android.com/privacy-and-security/security-tips)
- [Android — exported components](https://developer.android.com/privacy-and-security/risks/android-exported)
- [Android — zgodność stron 16 KB](https://developer.android.com/guide/practices/page-sizes)
- [Python HMAC — compare_digest](https://docs.python.org/3/library/hmac.html)
