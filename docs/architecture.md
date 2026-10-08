# Architektura V5 / 0.6

Windows odczytuje G29 przez pygame/SDL z obsługą zdarzeń w tle, kalibruje i mapuje wartości na kanały yaw/pitch/roll/vertical. Domyślnie ogranicza amplitudę i tempo zmian. Horyzont, atrapa i trasa to lokalny FlightModel — nie telemetria DJI i nie realna ochrona pomieszczenia.

JsonLineServer na IPv4 localhost wysyła podpisane HMAC ramki protokołu v2 przez autoryzowane ADB reverse. Android przyjmuje tylko ręcznie zatwierdzoną sesję z właściwym kluczem, nonce i rosnącą sekwencją; pierwszy pakiet jest neutralny. ACK opisuje stan aplikacji telefonu, nie drona. Watchdog obu stron ma próg programowy 300 ms.

NetworkClient aktualizuje wyłącznie BridgeState. Nie ma połączenia kanałów z API lotu. Oryginalny DJI SDK 4.18 jest opcjonalny i służy ręcznie uruchamianej rejestracji oraz pasywnym callbackom produktu/FlightController/baterii. Uprawnienie USB uzyskiwane jest przed connectReadOnly. Mini 2 SE nie jest oficjalnie wspierany; callbacki nie stanowią uprawnienia lotu. Lifecycle/STOP mogą zakończyć odczyt.

Telemetria ma osobne bramki świeżości i panel. Nie jest łączona z modelowanym pokojem ani udawana w mapie. Wideo jest oddzielnym, nieinteraktywnym podglądem ekranu DJI Fly przez scrcpy. Brak analizy obrazu, rozpoznawania ścian, surowych komend pilota, modyfikacji firmware i obchodzenia zabezpieczeń DJI.

Szczegóły: protocol.md, START-V5.md i ../AUDYT-V5.md.
