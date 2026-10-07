# Protokół V1 / kokpit V4

TCP na 127.0.0.1 po stronie PC, klient Android 127.0.0.1 przez `adb reverse tcp:8765 tcp:8765`. Każda linia UTF-8 kończy się LF i zawiera jeden obiekt JSON. Android ogranicza ramkę do 8192 bajtów. To kanał PC ↔ telefon, nie protokół DJI i nie potwierdzenie poleceń przyjętych przez drona.

Pakiet PC zawiera `version:1`, `type:"control"`, `sessionId` (32 małe znaki hex), `seq` (rosnąca liczba całkowita), `timestampMs`, `inputConnected` (boolean), `emergency` (boolean), `heartbeat:true` i `output` z czterema wymaganymi skończonymi liczbami `yaw`, `pitch`, `roll`, `vertical` w zakresie [-1,1]. Telefon uznaje wejście za aktywne tylko przy inputConnected=true i emergency=false. Kanały są wyłącznie stanem testowym; NIE wywołują API lotu.

Android potwierdza pakiet `version:1`, `type:"ack"`, ta sama `sessionId` i `seq`, `state:"NEUTRAL"` lub `"RECEIVING"`, `mode:"MOCK_ONLY"` albo `"DJI_SDK_READ_ONLY"`, `flightControl:false`, `aircraftTelemetry` (świeży callback lotu), `usb` (deskryptory) oraz opcjonalne `dji`.

`dji` zawiera registration, connection, model, productConnected, rcConnected, flightControllerConnected, telemetryFresh, telemetryAgeMs, batteryFresh, batteryAgeMs, telemetry, battery, validation i error. Bez aktualnych callbacków telemetry/battery są null. Rejestracja REGISTERED nie oznacza wsparcia Mini 2 SE. Znaczniki `officialMini2SeSupport:false`, `flightControl:false` i validation obowiązują również wtedy, gdy SDK zwraca częściowe dane. Callbacki są do sprawdzenia na fizycznym dronie.

Telemetria: kąty pitch/roll/yaw w stopniach, wysokość altitudeM w metrach, prędkości velocityXMps/velocityYMps/velocityZMps w m/s w układzie SDK, liczba satellites, flightMode, flying i motorsOn. GPS latitude/longitude pojawia się tylko przy poprawnym zakresie i co najmniej czterech satelitach; nadal wymaga weryfikacji. SDK nie jest przemapowywane na symulowaną mapę/horyzont. Bateria: percent i temperatureC. Brak pola oznacza brak odczytu, a nie zero.

Watchdog wejścia i ACK: 300 ms, zegar monotoniczny obu urządzeń niezależnie. EOF, błąd ramki, stara sekwencja, STOP i timeout zerują kanały mostka. PC przed pierwszym ACK wysyła zera i odrzuca spóźnione ACK. RTT mierzy obieg PC → Android → PC, nie pojedyncze opóźnienie ani stan radiowego łącza DJI.

Telemetria SDK jest świeża do 1500 ms od callbacku, bateria do 3000 ms. Windows dodatkowo sprawdza świeżość ACK i dodaje wiek ACK do wieku odczytu. STOP PC kończy kanał sterowania testowego, lecz pasywny odczyt SDK może działać dalej; oddzielny STOP odczytu na Androidzie kończy sesję DJI. W tym wariancie nie jest potrzebna neutralizacja prawdziwego drona, ponieważ aplikacja nigdy nie przejmuje sterowania lotem.
