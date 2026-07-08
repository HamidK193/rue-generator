# Anleitung: CPR-Aktionen pflegen & Tool anpassen

Diese Anleitung beschreibt, wie du CPR-Aktionen (und ihre Aktionscodes)
ersetzt, änderst oder neu anlegst — und wo du einfache Anpassungen am Tool
selbst vornimmst.

## 1. CPR-Aktionen direkt im Tool pflegen (empfohlen)

Im Tool oben auf **„CPR-Aktionen"** umschalten. Dort gibt es:

| Aktion | So geht's |
|---|---|
| **Neu anlegen** | „+ Neue CPR-Aktion" → Name eingeben (z. B. `10060`) → Aktionscodes einfügen (einer je Zeile, auch Komma/Excel-Spalte funktioniert) → **Speichern** |
| **Bearbeiten** | Eintrag links anklicken → Codes im Textfeld ändern/ergänzen/entfernen → **Speichern** |
| **Ersetzen** | Eintrag anklicken → alle Codes markieren (Strg+A), löschen, neue Liste einfügen → **Speichern** |
| **Umbenennen** | Eintrag anklicken → Namen im Feld „Name" ändern → **Speichern** |
| **Löschen** | Eintrag anklicken → **Löschen** → Sicherheitsabfrage bestätigen |
| **ViseV-Kampagnen (7088)** | Eigener Eintrag „7088 (ViseV)" ganz unten in der Liste — nur Codes änderbar, nicht löschbar |

Hinweise:
- Aktionscodes müssen **genau 12 Ziffern** haben — anderes lehnt das Tool
  mit einer Meldung ab.
- **Duplikate werden automatisch entfernt**, die Reihenfolge bleibt erhalten.
- Jede Speicherung schreibt sofort in die `projekte.json` — es gibt keinen
  extra „Übernehmen"-Schritt.

## 2. Alternativ: projekte.json von Hand bearbeiten

Die Datei `projekte.json` liegt neben dem Skript bzw. neben der EXE und ist
normales JSON:

```json
{
  "zasm": {
    "10053": ["371020250047", "371020250064", "..."],
    "7088":  ["054000007089", "..."]
  },
  "visev": {
    "7088": ["054000007015", "..."]
  }
}
```

- **Neue CPR-Aktion:** unter `"zasm"` einen neuen Schlüssel mit Codeliste
  ergänzen (Komma zwischen den Einträgen nicht vergessen).
- **Codes ersetzen:** einfach die Liste des jeweiligen Schlüssels austauschen.
- **ViseV-Kampagnen:** unter `"visev" → "7088"`.
- Nach dem Speichern das Tool neu starten. Duplikate in den Listen sind
  unkritisch (werden beim Laden entfernt); ungültiges JSON meldet das Tool
  beim Start mit genauer Fehlermeldung.

**Bei der EXE gilt:** Eine `projekte.json` **neben der EXE** hat Vorrang vor
der einkompilierten Kopie. Datenpflege braucht also **keinen neuen
EXE-Build** — Datei anpassen (oder im Tool speichern), fertig.

## 3. Einfache Anpassungen am Tool

Alle Stellschrauben liegen oben in `rue_core.py`:

| Konstante | Bedeutung | Standard |
|---|---|---|
| `DEFAULT_PROJECT` | CPR-Aktion beim ersten Start (ohne config.json) | `"10053"` |
| `LINE_LEN` | feste ZASM-Zeilenlänge | `95` |
| `AFTER_PNR_COL` | Spalte, ab der Stempel/NIO/Zeitstempel beginnen | `70` |
| `CONST1` / `CONST2` | feste Textbausteine der ZASM-Zeile | `"PNR   P"` / `"NIO"` |
| `STEMPEL_LEN` | geforderte Stempellänge | `8` |
| `VISEV_PROJEKT` | fixe CPR-Aktion des ViseV-Bereichs | `"7088"` |

Optik (Farben, Schriften, Vorschau-Limit) steht oben in
`gui_rue_generator_modern.py` (Block „Farbpalette").

Nach Code-Änderungen die Tests laufen lassen:

```bash
python -m unittest discover -s tests -v
```

## 4. Gemerkte Einstellungen zurücksetzen

Das Tool merkt sich Stempel, CPR-Aktion, Schalter und Fensterposition in der
`config.json` (neben Skript/EXE). Zum Zurücksetzen die Datei einfach löschen —
sie wird beim nächsten Schließen neu erzeugt.

## 5. Neue EXE bauen (nur bei Code-Änderungen nötig)

```bash
pip install customtkinter pyinstaller
pyinstaller gui_rue_generator_modern.spec
```

Ergebnis: `dist\RUE-Generator.exe` (eine Datei, ohne Konsolenfenster).
