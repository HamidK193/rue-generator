# RÜ-Generator (ZASM & ViseV)

Windows-Desktop-Tool mit moderner Oberfläche (Python + CustomTkinter) zum
Erzeugen von Textdateien für zwei Zielsysteme. Die Ausgabe landet
standardmäßig im `Downloads`-Ordner.

## Funktion

Das Tool hat drei Bereiche (Umschalter in der Kopfleiste):

### ZASM
- Eingabe: eine Liste von PNRs + Auswahl einer CPR-Aktion.
- Jede PNR wird mit allen hinterlegten Aktionscodes kombiniert.
- Ausgabe: feste **95-Zeichen-Zeilen** im Format
  `<Aktionscode> PNR   P <PNR rechtsbündig>   <Stempel> NIO <Zeitstempel>`.
- Optionen: Duplikate entfernen, Zeitstempel live oder manuell
  (`YYYYMMDDhhmm`, wird validiert).

### ViseV
- Fest für CPR-Aktion **7088**.
- Eingabe: 17-stellige VINs.
- Ausgabe pro VIN: `VIN-mitBindestrich<TAB>Aktion*` für alle
  Kampagnen-Aktionen; optionaler Header `VIN<TAB>Campaign Description`.

### CPR-Aktionen
- CPR-Aktionen und ihre Aktionscodes direkt im Tool **anlegen, bearbeiten,
  umbenennen und löschen** — ohne Code oder JSON anzufassen.
- Änderungen werden sofort in `projekte.json` gespeichert.
- Details: siehe **[ANLEITUNG.md](ANLEITUNG.md)**.

## Dateien

| Datei | Zweck |
|---|---|
| `gui_rue_generator_modern.py` | Oberfläche (CustomTkinter) |
| `rue_core.py` | Kernlogik (Parsing, Zeilenbau, Validierung, Dateien) |
| `projekte.json` | Alle CPR-Aktionen + ViseV-Kampagnen (im Tool pflegbar) |
| `ANLEITUNG.md` | Pflege- und Anpassungs-Anleitung |
| `tests/` | Unit-Tests der Kernlogik |
| `gui_rue_generator_modern.spec` | PyInstaller-Konfiguration für die EXE |

## Starten

```bat
start_rue_tool.bat
```

oder direkt:

```bash
pip install -r requirements.txt
python gui_rue_generator_modern.py
```

Voraussetzung: Python 3.10+ mit Tkinter (bei Standard-Windows-Installationen
dabei) und `customtkinter`.

## Konfiguration

Beim Schließen wird eine lokale `config.json` erzeugt (gemerkte CPR-Aktion,
Stempel, Schalter, Fensterposition). Diese Datei ist **nicht** im Repo
enthalten (siehe `.gitignore`), weil sie den Stempel enthält. Als Vorlage
dient `config.example.json`.

## Tests

```bash
python -m unittest discover -s tests -v
```

## EXE bauen

Einmalig (Python 3.10+ auf dem Windows-Rechner):

```bash
pip install customtkinter pyinstaller
```

Dann im Repo-Verzeichnis:

```bash
pyinstaller gui_rue_generator_modern.spec
```

Ergebnis: **`dist\RUE-Generator.exe`** — eine einzige Datei ohne
Konsolenfenster. Die `projekte.json` ist als Fallback eingebettet; eine
`projekte.json` **neben der EXE** hat Vorrang (wird auch vom
CPR-Aktionen-Bereich zum Speichern genutzt), Datenpflege braucht also keinen
neuen Build.
