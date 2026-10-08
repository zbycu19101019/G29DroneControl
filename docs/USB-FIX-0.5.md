# G29 Bridge 0.5 — zgoda USB

Pakiet: `com.example.g29dronecontrol`, versionCode 5, versionName `0.5-usb-permission-fix`. Jest to aktualizacja tej samej aplikacji, nie druga instalacja. Zachowuje dane i ustawienia przy instalacji `adb install -r` z tym samym podpisem. Gotowa APK z osobistym App Key jest prywatnym artefaktem i nie trafia do GitHub.

## Co naprawiono

W poprzednim teście SDK było zarejestrowane, ale nie rozpoczęło połączenia produktu. W logu `DJIUsbAccessoryReceiver` Android blokował mutable PendingIntent bez wskazanego pakietu/komponentu. Ogólny tekst „SDK odrzuciło połączenie produktu” generowała nasza aplikacja, nie dron.

Wariant 0.5 przed `startConnectionToProduct`:

1. Wyszukuje pilota DJI `com.dji.logiclink` w Android USB Accessory. Nie otwiera USB i nie wysyła komend.
2. Sprawdza zgodę Androida. Jeśli jej brak, prosi użytkownika przez `UsbManager.requestPermission`, używając niezmiennego PendingIntent ograniczonego do naszego pakietu i osobnego identyfikatora każdej próby. Odbiornik na Androidzie 13+ jest nieeksportowany.
3. Po odpowiedzi ponownie sprawdza faktyczne `hasPermission`, zamiast ufać danym broadcastu. Rejestracja SDK sama nie żąda zgody USB ani nie rozpoczyna połączenia produktu.
4. SDK startuje w wątku roboczym dopiero po zgodzie i powtórnym sprawdzeniu obecności pilota. STOP unieważnia próbę, usuwa odbiornik i timer, anuluje PendingIntent. Spóźniona odpowiedź ani zadanie w kolejce nie wznawiają zatrzymanej sesji.

Limit oczekiwania na zgodę: 30 s. Odmowa, odłączenie, błąd lub upływ czasu wymagają ponownego świadomego kliknięcia ODCZYT. Kabel ponownie podłączony nie wznawia samodzielnie zatrzymanej próby. Brak callbacków oznacza brak telemetrii, nie zastępcze zera.

SDK DJI 4.18 pozostaje niezmodyfikowane. targetSdk nadal 34. Nie dodano unsafe PendingIntent flags, wyjątków bezpieczeństwa Androida, przechwytywania wejścia telefonu, zmian firmware ani komend lotu.

## Test użytkownika

1. Dron na ziemi, bez śmigieł; nie uruchamiaj silników. Zamknij DJI Fly. Pilot pozostaje połączony z telefonem.
2. Otwórz **G29 DJI / READ ONLY**. Nagłówek powinien zawierać `USB FIX 0.5`.
3. REJESTRUJ DJI SDK; poczekaj na `REGISTERED`. Następnie ODCZYT DJI i potwierdzenie stanowiska.
4. Jeżeli Android pokaże zgodę dostępu do pilota przez USB, zaakceptuj ją ręcznie.
5. Odczytaj `usbPermission`, `connection`, `model`, `productConnected`, `flightControllerConnected`, `telemetryFresh` i `error`.

`usbPermission: GRANTED` potwierdza tylko zgodę USB. `READ_ONLY` oznacza uruchomioną sesję diagnostyczną SDK, nie potwierdzone połączenie drona. Połączenie i próbki muszą wynikać z osobnych flag i callbacków.

| usbPermission | Znaczenie |
| --- | --- |
| WAITING | Trwa oczekiwanie na okno zgody Androida |
| GRANTED | Android potwierdził zgodę; to nie dowód wsparcia drona |
| NO_ACCESSORY / UNSUPPORTED_ACCESSORY | Brak właściwego pilota w USB Accessory |
| DENIED | Zgoda nie została przyznana |
| DETACHED / REVOKED | Pilot odłączono lub dostęp został utracony |
| TIMEOUT | Brak odpowiedzi przez 30 s |
| CANCELLED | Próbę zatrzymano przez STOP |
| ERROR | Android nie zrealizował żądania/sprawdzenia |

Jeżeli po `GRANTED` SDK nadal nie zacznie połączenia, zamknij DJI Fly, przepnij kabel pilot–telefon, w razie pytania wybierz G29 i ponów odczyt. Nie oznaczamy wtedy fikcyjnego sukcesu.

Mini 2 SE nie ma oficjalnego wsparcia SDK. Naprawa zgody USB nie dodaje obsługi tego modelu ani sterowania lotem. Test samego okna zgody, odmowy, STOP podczas oczekiwania i połączenia produktu wymaga ręcznej próby użytkownika.

## Weryfikacja 2026-10-08

- Budowa SDK 0.5: assembleDebug, assembleDebugAndroidTest i lintDebug — PASS, 0 błędów lint, 16 ostrzeżeń. 15 jest znanych z poprzedniego wariantu (m.in. biblioteki vendor SDK); dodatkowe UseKtx to sugestia użycia rozszerzenia `toUri` zamiast `Uri.parse`, nie problem bezpieczeństwa.
- Budowa niezależnego wariantu bez SDK: assembleDebug, assembleDebugAndroidTest i lintDebug — PASS. Nie instalowano go zamiast wariantu SDK.
- Windows: 27 testów — PASS. Nie przebudowywano EXE, bo poprawka dotyczy Androida. APK obok EXE została zaktualizowana; kalibracji nie zmieniono.
- Samsung SM-S938B / Android 16: SDK APK 0.5 zainstalowana jako aktualizacja, 10 testów instrumentacyjnych — PASS. Testy obejmują utworzenie nowego immutable, package-scoped PendingIntent na prawdziwym systemie, dopuszczony model USB, mapowanie stanów zgody, świeżość telemetrii i dotychczasowe zabezpieczenia mostka. Nie żądają dostępu USB ani nie uruchamiają rejestracji/odczytu SDK lub poleceń lotu.
- Pomocnicza aplikacja testowa została po testach odinstalowana. Właściwa aplikacja pozostaje zainstalowana; jej dane nie były usuwane.
- Podpis v2 jest poprawny i zgodny z poprzednią APK. Sprawdzono klucz względem prywatnego pliku bez wypisywania jego wartości, ABI arm64, oryginalne 34 biblioteki natywne i integralność ZIP APK.

SHA-256 gotowej SDK APK: `87f477b4bb0b0233c9e44dfbd4e63d5e354565405dfa4534434558e79f72657f` (57 247 930 bajtów).

Te wyniki potwierdzają budowę, instalację i testy programowe, nie udaną obsługę okna zgody z pilotem ani telemetrię Mini 2 SE. Fizyczny test zgody USB, odmowy, STOP w trakcie oczekiwania i połączenia SDK pozostaje do wykonania ręcznie. Nie zgłaszamy wyniku sprzętowego jako PASS bez tego testu.

Źródła: [USB Accessory i zgoda Androida](https://developer.android.com/develop/connectivity/usb/accessory), [restrykcje PendingIntent Android 14](https://developer.android.com/about/versions/14/behavior-changes-14#safer-intents), [DJI startConnectionToProduct](https://developer.dji.com/api-reference/android-api/Components/SDKManager/DJISDKManager.html).
