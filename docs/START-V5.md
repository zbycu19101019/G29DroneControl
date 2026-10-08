# G29 Operator V5 / Android 0.6 — instrukcja

To rzeczywista aplikacja Windows do G29, symulator i mostek diagnostyczny Android z opcjonalnym DJI SDK 4.18 tylko do odczytu. Nie jest sterownikiem lotu Mini 2 SE. Nie wykrywa przeszkód i nie gwarantuje uniknięcia ściany.

## Uruchomienie Windows

1. Zamknij poprzedni G29CockpitV4: obie wersje używają domyślnie portu 8765. V5 nie zabija poprzedniego procesu.
2. Rozpakuj cały pakiet do osobnego katalogu. Pozostaw G29CockpitV5.exe, config.json, G29Bridge.apk i video razem. Python nie jest potrzebny.
3. Podłącz zasilacz i USB G29, przełącznik PS4. Uruchom G29CockpitV5.exe. RAW i paski osi pokazują rzeczywisty odczyt kierownicy; mapa i horyzont są wyłącznie symulacją.
4. W razie innego numeru osi wybierz właściwe przypisanie. Kalibracja: 1,5 s kierownica prosto / pedały puszczone, następnie pełny zakres kierownicy i każdego pedału w czasie 10 s. Niepełna kalibracja pedału pozostawia jego wyjście zerowe.
5. Tryb ostrożny jest domyślnie włączony: maksymalnie 35% znormalizowanego kanału i narastanie 1,2 jednostki/s. To NIE jest ograniczenie rzeczywistej prędkości w m/s ani hamowanie drona.
6. STOP / Escape zeruje wyjścia testowe, zamyka sesję i blokuje automatyczne wznowienie G29. Ponownie kliknij POŁĄCZ G29. STOP nie wyłącza silników.

## Telefon — wymagane obie nowe wersje

Android 0.6 jest już zainstalowany na testowanym telefonie. Aktualizacja nie odinstalowuje aplikacji ani nie kasuje jej danych. Po każdej nowej sesji Windows wymagane jest ręczne potwierdzenie telefonu.

1. Otwórz TELEFON / PILOT, wybierz autoryzowany telefon. Gdy pilot zajmuje USB telefonu, użyj wcześniej sparowanego bezprzewodowego ADB w zaufanej sieci.
2. W razie potrzeby kliknij „1. Zainstaluj APK 0.6”.
3. Kliknij „2. Przygotuj połączenie”. Windows otworzy lokalny port i przygotuje adb reverse. Na telefonie pojawi się propozycja sesji, nie automatyczne połączenie.
4. Porównaj 8-znakowy kod w panelu Windows i na telefonie. Kliknij „Potwierdź komputer i połącz”, a potem potwierdź zgodność kodu. Jeśli kody są różne, anuluj.
5. ACK OK oznacza uwierzytelnioną odpowiedź aplikacji telefonu, NIE odpowiedź drona.
6. Kanały G29 do telefonu są domyślnie wyłączone. Ich osobny przełącznik w Windows wymaga potwierdzenia testu na ziemi bez śmigieł. To nadal kanały testowe, nie komendy DJI.
7. Błąd podpisu, niezgodna sesja, stara sekwencja, EOF lub brak pakietów/ACK przez 300 ms zamyka połączenie i zeruje kanały. Sesję należy potwierdzić ponownie; utrata sesji odznacza przełącznik kanałów.
8. Klucz sesji nie jest zapisywany w ustawieniach. Zamknięcie Windows / nowy mostek wymaga nowej propozycji. Nie ma zgodności wstecznej z protokołem V4.

Jeśli widzisz brak nowej sesji, kliknij ponownie „Przygotuj połączenie” w V5. Jeśli port zajęty, zamknij poprzednią aplikację. Nie uruchamiaj dwóch kokpitów jednocześnie.

## Odczyt DJI później, na ziemi

Dron musi być naładowany, na ziemi ze zdjętymi śmigłami. Nie uruchamiaj silników. DJI Fly zamknij ręcznie, aby nie rywalizowało o pilota USB.

Rejestrację DJI SDK i odczyt uruchamiasz wyłącznie ręcznie na telefonie. Odczyt wymaga potwierdzenia trzech warunków. Uprawnienie USB jest uzyskiwane przed uruchomieniem połączenia SDK; STOP anuluje oczekiwanie. Przejście aplikacji w tło zatrzymuje pasywny odczyt DJI i oczekującą zgodę USB, ale zatwierdzony mostek testowy może działać jako usługa z powiadomieniem STOP.

REGISTERED potwierdza rejestrację klucza. USB GRANTED potwierdza dostęp do pilota. Żaden z tych stanów nie potwierdza połączenia z kontrolerem lotu. Świeże callbacki SDK są pokazane oddzielnie, nadal bez potwierdzenia zgodności z Mini 2 SE. W tej aktualizacji nie wykonano ponownego odczytu sprzętu — dron był rozładowany.

Brak/stare dane nie są zastępowane zerową „telemetrią”. Bateria ma limit świeżości 3 s, telemetria 1,5 s; Windows dolicza wiek ACK. Świeży odczyt baterii ≤20% blokuje kanały testowe; ≤30% ostrzega. To progi doradcze aplikacji, nie progi procedur DJI ani komendy lądowania. Brak odczytu baterii nie oznacza naładowanej baterii.

## Wideo i symulator

„OBRAZ DJI FLY” to osobne okno kopii ekranu telefonu, tylko do odczytu: bez kliknięć, schowka, audio i nagrywania. Nie ma analizy przeszkód ani automatycznego unikania kolizji. Otworzenie DJI Fly zatrzymuje pasywny odczyt SDK tej aplikacji.

Atrapa drona, horyzont, trasa i ograniczenie wirtualnego pokoju dotyczą wyłącznie symulatora. Pokój ±11,25 m i wysokość do 5 m nie są pomiarem pomieszczenia ani realną strefą lotu. Nie wypróbuj ich ochrony przez lot w stronę ściany.

## Znane ograniczenia

Mini 2 SE nie ma oficjalnego wsparcia tego SDK ani systemu unikania przeszkód. W paczce nie ma adaptera komend lotu. Oryginalne biblioteki DJI 4.18 nadal mają ostrzeżenia zgodności z pamięcią 16 KB. Nie ukryto ostrzeżenia Androida ani nie patchowano bibliotek. APK jest prywatnym buildem testowym podpisanym kluczem debug, a EXE nie ma podpisu Authenticode. Nie publikuj APK z osadzonym osobistym DJI App Key.

Raport: AUDYT-V5.md. Historyczna poprawka USB: USB-FIX-0.5.md.
