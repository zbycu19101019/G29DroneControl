# Testy bezpieczeństwa

1. Uruchom `G29CockpitV3.exe`. Status powinien pokazać `G29 ONLINE / 4 OSIE`.
2. Obróć kierownicą. `RAW A0` powinno zmieniać się między wartościami ujemnymi i dodatnimi. Na testowanej kierownicy potwierdzono zakres około `-1.0..+1.0` przy ukrytym oknie SDL i ustawieniu `SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1`.
3. Sprawdź, czy zmieniają się paski `STEERING` i `YAW`. Jeśli porusza się inna oś, przypisz jej numer w panelu mapowania.
4. Uruchom kalibrację: 1,5 sekundy neutralnie, następnie przez 10 sekund pełny zakres każdej osi. Sprawdź zapis `config.json`.
5. Kliknij `DEMO LOT`. Atrapa drona powinna wznieść się, polecieć do przodu, skręcić i opadać; mapa pokazuje ślad. `RESET SYMULACJI` zeruje pozycję.
6. `STOP` powinien zerować polecenia i zamknąć TCP. Po STOP program nie podłącza automatycznie G29.
7. `TELEFON / PILOT` → autoryzowany telefon → `POŁĄCZ MOSTEK`. `ACK OK` i RTT potwierdzają odbiór w telefonie. Diagnostyka USB pokazuje `DJI RC-N1` jako akcesorium bez przejmowania DJI Fly.
8. Ten pakiet nie wysyła komend do DJI Mini 2 SE; wartości HUD są tylko symulacją.
9. Otwórz DJI Fly na telefonie i `OBRAZ DJI FLY` w Windows. Sprawdź aktualizację obrazu. Nie klikaj poleceń startu; podgląd PC jest tylko do odczytu.
10. Testy automatyczne Windows: `python -m unittest discover -s tests -v`. Testy instrumentacyjne Android w `android/app/src/androidTest` działają na localhost, bez otwierania USB DJI. Zbuduj i uruchom właściwy test runner na wybranym telefonie. Wyniki rzeczywistego testu opisano w `AUDYT.md`.
