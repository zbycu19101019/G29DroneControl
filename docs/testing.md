# Testy V5 / Android 0.6

Automatyczne: python -m unittest discover -s tests -v. Zrealizowano 45 testów Windows. Sprawdzają m.in. mapowanie, kalibrację, podpisy/nonce/ACK, STOP, utratę wejścia, maskowanie kluczy, świeżość, zapis konfiguracji, symulator i geometrie 960×700 / 1180×820. Testy GUI wymagają sesji Windows z pulpitem.

Android: gradlew.bat -PwithDjiSdk=true :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug. Instrumentation com.example.g29dronecontrol.test/com.example.g29dronecontrol.BridgeInstrumentation wykonał 18 testów na wybranym Samsungu Android 16. Używa localhost, testowych tokenów, syntetycznych callbacków i renderu własnego View; nie żąda USB DJI, nie rejestruje SDK i nie wydaje komend lotu.

## Sprawdzenie użytkownika bez lotu

1. Zamknij V4. Uruchom G29CockpitV5.exe, sprawdź RAW A0 i paski przy rzeczywistym ruchu G29. Wynik wykrycia w self-test nie zastępuje testu ruchu.
2. Kalibruj osie według START-V5.md. Puszczone pedały mają dawać zero.
3. Demo pokazuje tylko model drona. Granica modelowanego pokoju nie ogranicza rzeczywistego lotu.
4. Telefon: V5 → Przygotuj połączenie → porównaj kod → ręcznie potwierdź na 0.6. Sam Intent nie łączy.
5. ACK oznacza mostek telefonu; kanały G29 nadal domyślnie wyłączone. Ich test wyłącznie na ziemi bez śmigieł.
6. STOP / Escape oraz STOP na telefonie mają zamykać sesję i wyzerować kanały, bez automatycznego wznowienia.
7. Odczyt DJI dopiero po naładowaniu drona, na ziemi bez śmigieł, po ręcznym zamknięciu DJI Fly i potwierdzeniu warunków w APK. Nie testuj ściany, lotu ani silników.
8. Brak świeżych danych ma być pokazany jako brak, nie zero. Nieznana bateria nie oznacza sprawnej baterii. Odczyt USB i rejestracja nie potwierdzają FlightController.
9. Podgląd wideo jest nieinteraktywny; nie pozwala na obsługę przycisków telefonu z Windows. Przejście do DJI Fly kończy pasywny odczyt SDK mostka.

Szczegółowe wyniki i otwarte ryzyka: ../AUDYT-V5.md. Żadnego testu tej wersji nie wykonywano w locie.
