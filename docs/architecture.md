# Architektura

PC odczytuje G29 przez pygame, mapuje wartości na abstrakcyjne kanały `yaw/pitch/roll/vertical` i wysyła JSON Lines przez TCP. Zalecana ścieżka USB to `adb reverse tcp:8765 tcp:8765`, ponieważ Android łączy się wtedy z `127.0.0.1:8765`.

Android odbiera pakiety, aktualizuje dashboard i `MockDroneControl`. Watchdog neutralizuje stan po 400 ms bez pakietu. `DisabledDjSdkDroneControl` jest celowo nieaktywne. Nie ma tu reverse engineeringu, wysyłania surowych komend do RC-N1 ani omijania zabezpieczeń DJI.
