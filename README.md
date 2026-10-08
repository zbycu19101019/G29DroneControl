# G29 Operator V5 — Windows + Android 0.6

Gotowa aplikacja Windows do Logitech G29, lokalny symulator z atrapą drona, uwierzytelniony mostek Android i opcjonalne DJI Mobile SDK 4.18 tylko do odczytu. Jasny, spokojny interfejs zastępuje dawny styl terminala.

**Brak sterowania lotem DJI Mini 2 SE i realnej ochrony antykolizyjnej.** USB/ACK/rejestracja klucza nie oznaczają przyjęcia komend przez drona. Mapa, horyzont i granica pokoju są wyłącznie symulacją.

Aktualne prywatne artefakty lokalne: ../G29CockpitV5/G29CockpitV5.exe, G29Bridge.apk i ../G29CockpitV5-Windows.zip. Repozytorium zawiera źródła, nie prywatny klucz, APK/EXE, logi ani kalibrację użytkownika.

## Dokumentacja

- [Instrukcja V5 / Android 0.6](docs/START-V5.md)
- [Audyt bezpieczeństwa i wykonane testy](AUDYT-V5.md)
- [Podpisany protokół v2](docs/protocol.md)
- [Architektura](docs/architecture.md)
- [Budowa z klonu repozytorium](docs/github.md)
- [Testy](docs/testing.md)
- [Historyczna naprawa zgody USB 0.5](docs/USB-FIX-0.5.md)

## Co zmienia V5

Kanały telefonu domyślnie wyłączone, ręczna akceptacja kodu na Androidzie, losowy klucz HMAC-SHA256, nonce/sesja/sekwencje, neutralny handshake, watchdog 300 ms i STOP wymagający ręcznego wznowienia. Tryb ostrożny ogranicza amplitudę i tempo zmian kanałów testowych. Świeża niska bateria blokuje wyłącznie te kanały, nie hamuje drona. Przejście Androida w tło kończy odczyt DJI.

Stary V4 i Android ≤0.5 nie są zgodne z v2. Zamknij V4 przed uruchomieniem V5. W TELEFON / PILOT kliknij „Przygotuj połączenie”, porównaj kod i potwierdź na telefonie. Nie ma auto-connect przez Intent.

G29: zasilacz, USB, przełącznik PS4. Rzeczywisty odczyt RAW i paski działają z ukrytym SDL dzięki SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1. Pedały wymagają kalibracji. Demo i mapa nigdy nie uruchamiają silników.

Podgląd DJI Fly jest kopią ekranu tylko do odczytu, bez nagrywania, sterowania i schowka. Nie służy do wykrywania przeszkód.

## Ze źródeł

Python 3.12 / Windows:

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python cockpit.py
python -m unittest discover -s tests -v
~~~

Budowa Windows i Android:

~~~powershell
.\build_windows.ps1 -WithDjiSdk
~~~

Potrzebne JDK Android Studio, ANDROID_HOME i własny DJI_APP_KEY lub plik wskazany DJI_KEYS_FILE poza repozytorium. Bez przełącznika powstaje niezależny mostek bez SDK. SDK pobiera Gradle; build nie patchuje bibliotek producenta ani nie usuwa fly-safe-database. Prywatny APK osadza App Key — nie publikuj go na GitHub.

SDK 4.18 ma nadal znane ostrzeżenia bibliotek 16 KB i zależności TLS. APK jest buildem debug, EXE nie ma Authenticode. Nie deklarujemy produkcyjnej certyfikacji Android 16 ani bezpieczeństwa lotu.

Wykonano 45 testów Windows i 18 testów na telefonie SDK 0.6 bez odczytu DJI. Weryfikacja telemetrii drona pozostaje niewykonana; ostatni zrzut użytkownika potwierdza USB/REGISTERED, ale odrzucony start SDK, nie awarię kabla. Starsze V3/V4 i raporty zachowano jako historyczne wersje.
