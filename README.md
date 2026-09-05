# Panel-HMI-AS45TFT0703

Prosty program w Pythonie do obsługi urządzeń grzewczych.

## Dostępne funkcje

- dodawanie urządzeń grzewczych,
- włączanie i wyłączanie urządzeń,
- ustawianie temperatury docelowej,
- zapisywanie konfiguracji do pliku JSON.

## Uruchamianie

```bash
python heating_program.py list
python heating_program.py add "Kocioł" piec --current-temperature 19.5 --target-temperature 21
python heating_program.py on "Kocioł"
python heating_program.py set-temperature "Kocioł" 22.5
```

Domyślnie dane są zapisywane do pliku `heating_devices.json` w katalogu projektu.

## Testy

```bash
python -m unittest discover -s tests
```
