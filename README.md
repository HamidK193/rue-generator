# RÜ-Generator (ZASM & ViseV)

Windows-Desktop-Tool mit grafischer Oberfläche (Python + Tkinter) zum Erzeugen
von Textdateien für zwei Zielsysteme. Die Ausgabe landet standardmäßig im
`Downloads`-Ordner.

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

Die Projekte und ihre Aktionscodes sind im Dictionary `PROJEKTE` in
`gui_rue_generator_unified.py` hinterlegt.

## Starten

```bat
start_rue_tool.bat
```

oder direkt:

```bash
python gui_rue_generator_unified.py
```

Voraussetzung: Python 3 mit Tkinter (bei Standard-Windows-Installationen dabei).

## Konfiguration

Beim ersten Start wird eine lokale `config.json` erzeugt (gemerktes Projekt,
Stempel, Fensterposition, Theme). Diese Datei ist **nicht** im Repo enthalten
(siehe `.gitignore`), weil sie den Stempel enthält. Als Vorlage dient
`config.example.json` – bei Bedarf kopieren und anpassen:

```bash
copy config.example.json config.json
```

## EXE bauen (optional)

Mit PyInstaller und der mitgelieferten Spec-Datei:

```bash
pyinstaller gui_rue_generator_unified.spec
```

Das Ergebnis liegt danach unter `dist/`.

## Bekannte offene Punkte

- `DEFAULT_PROJECT = "90079"` existiert nicht als Schlüssel in `PROJEKTE`
  (nur `90079_2.13` etc.) – ohne vorhandene `config.json` bleibt die Vorschau
  zunächst leer.
- In einigen Projektlisten kommen einzelne Aktionscodes doppelt vor.
