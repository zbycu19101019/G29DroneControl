# Trzy warianty docelowe

## 1. Oficjalny DJI SDK

`dji-official-android/` zawiera adapter `DroneControl` i miejsce na oficjalny moduł DJI SDK. Adapter sprawdza model i odrzuca modele nieobsługiwane. Nie wolno podmieniać go reverse-engineeringiem protokołu.

## 2. MAVLink

`mavlink-python/` to sterownik dla własnego/autoryzowanego autopilota MAVLink. Domyślnie działa w dry-run. Tryb live wymaga jawnego `--live`, pozytywnej telemetrii i potwierdzenia użytkownika.

## 3. Mini 2 SE — laboratorium/symulator

`mini2se-lab/` odbiera te same pakiety G29, uruchamia model dynamiki, watchdog i dashboard Tkinter. Nie wysyła żadnych danych do DJI Fly, RC-N1 ani drona.
