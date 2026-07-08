# RÜ-Generator (ZASM & ViseV)

Windows-Desktop-Tool mit grafischer Oberfläche zum Erzeugen von Textdateien
für zwei Zielsysteme. Die Ausgabe landet standardmäßig im `Downloads`-Ordner.

Es gibt zwei Varianten, die parallel nutzbar sind:

| Variante | Dateien | UI |
|---|---|---|
| **Modern** (empfohlen) | `gui_rue_generator_modern.py` + `rue_core.py` + `projekte.json` | CustomTkinter, modernes Windows-Look & Feel |
| Klassisch | `gui_rue_generator_unified.py` | Tkinter/ttk |

## Funktion

Das Tool hat zwei Tabs:

### ZASM
- Eingabe: eine Liste von PNRs + Auswahl eines Projekts.
- Jede PNR wird mit allen im Projekt hinterlegten Aktionscodes kombiniert.
- Ausgabe: feste **95-Zeichen-Zeilen** im Format
  `<Aktion> PNR   P <PNR rechtsbündig>   <Stempel> NIO <Zeitstempel>`.
- Optionen: Duplikate entfernen, Zeitstempel live oder manuell (`YYYYMMDDhhmm`).

### ViseV
- Speziell für Projekt **7088**.
- Eingabe: 17-stellige VINs.
- Ausgabe pro VIN: `VIN-mitBindestrich<TAB>Aktion*` für alle Kampagnen-Aktionen.
- Optionaler Header `VIN<TAB>Campaign Description`.

## Projektdaten

**Moderne Version:** Die Projekte und ihre Aktionscodes liegen in
`projekte.json` (Block `zasm` je Projekt, Block `visev` für Projekt 7088).
Neue Codes einfach dort eintragen – Duplikate werden beim Laden automatisch
entfernt. Bei der EXE gilt: Eine `projekte.json` **neben der EXE** hat
Vorrang vor der eingebetteten Kopie, Datenpflege geht also ohne Neubau.

**Klassische Version:** Dictionary `PROJEKTE` in
`gui_rue_generator_unified.py`.

## Starten

Moderne Version:

```bat
start_rue_tool_modern.bat
```

oder direkt:

```bash
pip install -r requirements.txt
python gui_rue_generator_modern.py
```

Klassische Version (nur Tkinter, keine Zusatzpakete):

```bat
start_rue_tool.bat
```

Voraussetzung: Python 3.10+ mit Tkinter (bei Standard-Windows-Installationen
dabei); die moderne Version braucht zusätzlich `customtkinter`.

## Tests

Die Kernlogik (Parsing, Zeilenbau, Deduplizierung, Validierung) ist in
`rue_core.py` gekapselt und ohne GUI testbar:

```bash
python -m unittest discover -s tests -v
```

## Konfiguration

Beim ersten Start wird eine lokale `config.json` erzeugt (gemerktes Projekt,
Stempel, Fensterposition, Theme). Diese Datei ist **nicht** im Repo enthalten
(siehe `.gitignore`), weil sie den Stempel enthält. Als Vorlage dient
`config.example.json` – bei Bedarf kopieren und anpassen:

```bash
copy config.example.json config.json
```

## EXE bauen (moderne Version)

Einmalig auf dem Windows-Rechner (Python 3.10+):

```bash
pip install customtkinter pyinstaller
```

Dann im Repo-Verzeichnis:

```bash
pyinstaller gui_rue_generator_modern.spec
```

Das Ergebnis ist **eine einzige Datei ohne Konsolenfenster**:
`dist\RUE-Generator.exe`. Die Spec bündelt die CustomTkinter-Assets und
bettet `projekte.json` als Fallback mit ein; eine `projekte.json` neben der
EXE überschreibt die eingebettete Version.

## EXE bauen (klassische Version)

```bash
pyinstaller gui_rue_generator_unified.spec
```

## Bekannte offene Punkte (nur klassische Version)

Diese Punkte sind in der modernen Version behoben:

- `DEFAULT_PROJECT = "90079"` existiert nicht als Schlüssel in `PROJEKTE` –
  ohne vorhandene `config.json` bleibt die Vorschau zunächst leer.
- In einigen Projektlisten kommen einzelne Aktionscodes doppelt vor
  (doppelte Zeilen in der Ausgabe).
- Exportdateien werden mit `\r\r\n` statt `\r\n` als Zeilenende geschrieben.
