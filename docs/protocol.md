# Protokół v2 — Windows V5 / Android 0.6

To kanał diagnostyczny PC ↔ telefon, nie protokół DJI i nie potwierdzenie poleceń przyjętych przez drona. Serwer PC nasłuchuje wyłącznie na IPv4 127.0.0.1; Android łączy się z 127.0.0.1 przez autoryzowany adb reverse. Brak kompatybilności/fallbacku do v1.

## Zatwierdzenie i koperta

Windows tworzy losowy klucz 32 B (64 małe znaki hex) dla instancji mostka. ADB Intent przekazuje wyłącznie propozycję token/port. Telefon wymaga porównania kodu: pierwsze 8 uppercase hex SHA256 surowego klucza, oraz ręcznego potwierdzenia. connect=true nie uruchamia połączenia, SDK ani odczytu.

Każda linia LF ma kopertę JSON z dokładnie version:2, payload (tekst wewnętrznego JSON) oraz mac (64 małe znaki hex HMAC-SHA256 UTF-8 payload). Podpis sprawdzany przed parsowaniem danych, constant-time. HMAC to uwierzytelnienie, NIE szyfrowanie. Klucz nie jest zapisywany w config. Zaufany administrator/debugger/host ADB pozostaje poza tą granicą ochrony.

Telefon wysyła podpisane hello z version:2, type:hello i losowym clientNonce (32 hex). PC przypisuje nową sessionId (32 hex). Następne pakiety i ACK muszą odpowiadać obu wartościom. Drugie połączenie nie zastępuje już przyjętego klienta.

## Pakiety testowe i odpowiedzi

PC: version:2, type:control, sessionId, clientNonce, rosnąca całkowita seq, timestampMs (informacyjny, nie zegar bezpieczeństwa), inputConnected i emergency (boolean), heartbeat:true, output z yaw/pitch/roll/vertical jako skończone liczby [-1,1]. Pierwszy pakiet musi być nieaktywny z zerami. Nieaktywny/emergency pakiet z niezerowym kanałem jest odrzucany. Aktywne kanały są tylko stanem testowym i nie wywołują API DJI.

Android ACK: version:2, type:ack, ta sama sessionId/clientNonce/seq, state:NEUTRAL lub RECEIVING, mode:MOCK_ONLY lub DJI_SDK_READ_ONLY, flightControl:false, aircraftTelemetry, dji oraz usb. ACK nie nadawał i nie nadaje uprawnienia lotu. PC odrzuca nieznany protokół/podpis/sesję/nonce lub flightControl inne niż false. Tylko oczekiwany ACK odświeża watchdog; duplikaty go nie przedłużają.

## Błędy i świeżość

Limity: 8192 B ramki odbiorczej telefonu i wysyłanej przez PC; 32768 B bufora ACK na PC; payload podpisu do 16000 B; kolejka oczekujących ACK do 64. Watchdog pakietów i ACK: 300 ms zegara monotonicznego. RTT to czas obiegu PC→telefon→PC, nie opóźnienie radiowe drona. Nie jest to system czasu rzeczywistego.

Nieprawidłowy podpis, zły nonce/sesja, stara sekwencja, EOF, timeout i STOP zerują testowy stan telefonu oraz zamykają sesję. Zdalny emergency STOP zatrzymuje również pasywny odczyt SDK. Sam błąd TCP/watchdog zamyka kanał testowy; nie udaje polecenia hamowania/lądowania. Ponowne połączenie telefonu tylko po ręcznym potwierdzeniu; utrata sesji Windows odznacza kanały G29.

dji: registration, connection, model, productConnected, rcConnected, flightControllerConnected, telemetryFresh/telemetryAgeMs, batteryFresh/batteryAgeMs, telemetry/battery lub null, validation/error i usbPermission. Świeżość telemetrii ≤1500 ms wymaga READ_ONLY + produktu + FC; bateria ≤3000 ms wymaga READ_ONLY + produktu. Windows dolicza wiek ACK. Wszystkie częściowe callbacki są niezweryfikowane sprzętowo dla Mini 2 SE.

Eksport lotu: pitch/roll/yaw, altitudeM, velocityXMps/velocityYMps/velocityZMps, satellites, flightMode, flying, motorsOn. GPS latitude/longitude usunięto ze względów prywatności. Bateria: percent, temperatureC. Świeża bateria ≤20% zatrzymuje kanały testowe, nie silniki. Źródłowe flagi officialMini2SeSupport:false i flightControl:false obowiązują zawsze.

Przejście MainActivity w tło zatrzymuje odczyt SDK i oczekującą zgodę USB. Usługa mostka testowego jest foreground, non-exported, START_NOT_STICKY i ma powiadomienie STOP. Samo uruchomienie Activity / dołączenie USB niczego nie rejestruje ani nie łączy z DJI.
