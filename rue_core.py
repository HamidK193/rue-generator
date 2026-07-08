#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rue_core – Kernlogik des RUE-Generators (ohne GUI).

Enthält alles, was sich ohne Oberfläche testen lässt:
- Laden der Projektdaten aus projekte.json (mit automatischer Deduplizierung)
- Parsing von PNRs und VINs
- Zeilenbau für ZASM (95-Zeichen-Zeilen) und ViseV (VIN<TAB>Aktion*)
- Validierung (Stempel, manueller Zeitstempel)
- Dateinamen, eindeutige Pfade, CRLF-Schreiben
- Laden/Speichern der config.json
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Konfigurierbare Konstanten
# ---------------------------------------------------------------------------

APP_TITLE = "RUE-Generator – ZASM & ViseV"

# ZASM-Zeilenlayout (wie Referenzsystem)
AFTER_PNR_COL = 70          # Spalte, ab der der rechte Block beginnt
LINE_LEN = 95               # feste Gesamtzeilenlänge
CONST1 = "PNR   P"          # fester Text nach dem Aktionscode (7 Zeichen)
CONST2 = "NIO"              # fester Text vor dem Zeitstempel

STEMPEL_LEN = 8             # geforderte Stempellänge
VISEV_PROJEKT = "7088"      # fixes Projekt des ViseV-Tabs

# Standardprojekt, wenn keine (gültige) config.json existiert.
# Muss ein existierender Schlüssel in projekte.json -> "zasm" sein.
DEFAULT_PROJECT = "10053"

PROJEKTE_DATEINAME = "projekte.json"
CONFIG_DATEINAME = "config.json"

# In Windows-Dateinamen verbotene Zeichen
_INVALID_FILENAME_CHARS = set('<>:"/\\|?*')

VIN_RE = re.compile(r"[A-HJ-NPR-Z0-9]{17}")  # klassische VIN-Regel (ohne I, O, Q)
_TS_RE = re.compile(r"\d{12}")               # YYYYMMDDhhmm


# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------

def base_dir() -> Path:
    """Verzeichnis der EXE (PyInstaller) bzw. dieses Skripts."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_projekte_json() -> Path:
    """
    Sucht projekte.json:
    1. neben der EXE / dem Skript (damit die Daten ohne Neubau pflegbar sind),
    2. als Fallback im PyInstaller-Bundle (sys._MEIPASS).
    """
    extern = base_dir() / PROJEKTE_DATEINAME
    if extern.exists():
        return extern
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        gebuendelt = Path(meipass) / PROJEKTE_DATEINAME
        if gebuendelt.exists():
            return gebuendelt
    return extern  # existiert nicht -> Fehler beim Laden mit klarer Meldung


def config_path() -> Path:
    return base_dir() / CONFIG_DATEINAME


def downloads_dir() -> str:
    return os.path.join(os.path.expanduser("~"), "Downloads")


# ---------------------------------------------------------------------------
# Projektdaten
# ---------------------------------------------------------------------------

class ProjektDatenFehler(Exception):
    """Projektdaten fehlen oder sind ungültig."""


@dataclass(frozen=True)
class ProjektDaten:
    """Aktionscodes je Projekt, getrennt nach Zielsystem."""
    zasm: dict[str, list[str]] = field(default_factory=dict)
    visev: dict[str, list[str]] = field(default_factory=dict)

    def zasm_aktionen(self, projekt: str) -> list[str]:
        return self.zasm.get(projekt, [])

    def visev_aktionen(self, projekt: str = VISEV_PROJEKT) -> list[str]:
        return self.visev.get(projekt, [])


def dedupe_keep_order(seq: list[str]) -> list[str]:
    """Entfernt Duplikate, behält die ursprüngliche Reihenfolge."""
    return list(dict.fromkeys(seq))


def lade_projekte(pfad: str | Path | None = None) -> ProjektDaten:
    """
    Lädt projekte.json und dedupliziert alle Aktionslisten.
    Wirft ProjektDatenFehler mit verständlicher Meldung bei Problemen.
    """
    p = Path(pfad) if pfad is not None else find_projekte_json()
    if not p.exists():
        raise ProjektDatenFehler(
            f"Projektdaten nicht gefunden:\n{p}\n\n"
            f"Die Datei '{PROJEKTE_DATEINAME}' muss neben der EXE bzw. dem Skript liegen."
        )
    try:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise ProjektDatenFehler(
            f"'{p.name}' ist kein gültiges JSON:\n{e}"
        ) from e

    zasm = raw.get("zasm")
    if not isinstance(zasm, dict) or not zasm:
        raise ProjektDatenFehler(
            f"'{p.name}' enthält keinen gültigen 'zasm'-Block mit Projekten."
        )
    visev = raw.get("visev") or {}

    def _liste(projekt: str, wert: object) -> list[str]:
        if (not isinstance(wert, list)
                or not all(isinstance(a, str) and a.strip() for a in wert)):
            raise ProjektDatenFehler(
                f"Projekt '{projekt}' in '{p.name}' hat keine gültige Aktionsliste."
            )
        return dedupe_keep_order([a.strip() for a in wert])

    return ProjektDaten(
        zasm={k: _liste(k, v) for k, v in zasm.items()},
        visev={k: _liste(k, v) for k, v in visev.items()},
    )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_pnrs(text: str, remove_dupes: bool = True) -> list[str]:
    """Extrahiert Ziffernfolgen (PNRs); optional Duplikate entfernen (Reihenfolge bleibt)."""
    tokens = re.split(r"[^A-Z0-9]+", text.upper())
    digits = [re.sub(r"\D+", "", t) for t in tokens if t]
    digits = [d for d in digits if d]
    if remove_dupes:
        digits = dedupe_keep_order(digits)
    return digits


def parse_vins(text: str, keep_dupes: bool = True) -> list[str]:
    """Extrahiert 17-stellige VINs (ohne I, O, Q). Duplikate je nach Flag."""
    vins = VIN_RE.findall(text.upper())
    if keep_dupes:
        return vins
    return dedupe_keep_order(vins)


# ---------------------------------------------------------------------------
# Validierung
# ---------------------------------------------------------------------------

def validate_stempel(stempel: str) -> str | None:
    """
    Prüft den Stempel. Rückgabe: None wenn ok, sonst deutsche Fehlermeldung.
    Anforderungen: genau STEMPEL_LEN Zeichen, keine in Dateinamen verbotenen Zeichen.
    """
    s = stempel.strip()
    if not s:
        return f"Bitte Stempel eingeben ({STEMPEL_LEN} Zeichen)."
    if len(s) != STEMPEL_LEN:
        return (f"Der Stempel muss genau {STEMPEL_LEN} Zeichen haben "
                f"(aktuell {len(s)}).")
    verboten = sorted(set(s) & _INVALID_FILENAME_CHARS)
    if verboten:
        return ("Der Stempel enthält Zeichen, die in Dateinamen nicht erlaubt sind: "
                + " ".join(verboten))
    return None


def validate_manual_ts(ts: str) -> str | None:
    """
    Prüft einen manuellen Zeitstempel 'YYYYMMDDhhmm'.
    Rückgabe: None wenn ok, sonst deutsche Fehlermeldung.
    """
    s = ts.strip()
    if not _TS_RE.fullmatch(s):
        return "Manueller Zeitstempel muss 12 Ziffern haben (Format YYYYMMDDhhmm)."
    try:
        datetime.strptime(s, "%Y%m%d%H%M")
    except ValueError:
        return f"'{s}' ist kein gültiges Datum (Format YYYYMMDDhhmm)."
    return None


def now_ts_compact() -> str:
    return datetime.now().strftime("%Y%m%d%H%M")


# ---------------------------------------------------------------------------
# ZASM-Zeilenbau
# ---------------------------------------------------------------------------

def build_line_zasm(aktion: str, pnr: str, stempel: str, ts: str) -> str:
    """Baut eine feste 95-Zeichen-Zeile für ZASM."""
    left = f"{aktion} {CONST1} {pnr:>7}"
    spaces_needed = AFTER_PNR_COL - len(left)
    if spaces_needed < 0:
        left = left[:AFTER_PNR_COL]
        spaces_needed = 0
    left += " " * spaces_needed
    line = f"{left}{stempel} {CONST2} {ts}"
    if len(line) > LINE_LEN:
        line = line[:LINE_LEN]
    elif len(line) < LINE_LEN:
        line += " " * (LINE_LEN - len(line))
    return line


def build_zasm_lines(aktionen: list[str], pnrs: list[str],
                     stempel: str, ts: str) -> list[str]:
    """Kreuzprodukt: für jede PNR alle Aktionen des Projekts."""
    stempel_fix = stempel.strip().upper().ljust(STEMPEL_LEN)[:STEMPEL_LEN]
    return [build_line_zasm(a, p, stempel_fix, ts) for p in pnrs for a in aktionen]


def zasm_dateiname(projekt: str, stempel: str, wann: datetime | None = None) -> str:
    """z.B. 'RÜ_08072026_10053_ABCD1234.txt'"""
    d = (wann or datetime.now()).strftime("%d%m%Y")
    return f"RÜ_{d}_{projekt}_{stempel.strip().upper()}.txt"


# ---------------------------------------------------------------------------
# ViseV-Zeilenbau
# ---------------------------------------------------------------------------

VISEV_HEADER = "VIN\tCampaign Description"


def format_vin(vin: str) -> str:
    """17-stellige VIN mit Bindestrich nach Position 10, sonst unverändert."""
    if len(vin) == 17:
        return f"{vin[:10]}-{vin[10:]}"
    return vin


def build_visev_lines(vins: list[str], aktionen: list[str],
                      include_header: bool) -> list[str]:
    """Pro VIN eine Zeile je Aktion: '<VIN-mit-Bindestrich>\\t<AKTION>*'."""
    lines: list[str] = []
    if include_header:
        lines.append(VISEV_HEADER)
    for vin in vins:
        vin_fmt = format_vin(vin)
        lines.extend(f"{vin_fmt}\t{aktion}*" for aktion in aktionen)
    return lines


def visev_dateiname(wann: datetime | None = None) -> str:
    """z.B. 'ViseV_20260708-1530_7088_ALL.txt'"""
    d = (wann or datetime.now()).strftime("%Y%m%d-%H%M")
    return f"ViseV_{d}_{VISEV_PROJEKT}_ALL.txt"


# ---------------------------------------------------------------------------
# Dateien schreiben
# ---------------------------------------------------------------------------

def get_unique_path(path: str) -> str:
    """Hängt ' (2)', ' (3)', ... an, bis der Dateiname frei ist (wie Windows)."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 2
    while True:
        candidate = f"{base} ({counter}){ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def write_txt_crlf(path: str, lines: list[str]) -> None:
    """
    Schreibt Zeilen mit echten Windows-Zeilenenden (CRLF).

    Hinweis: newline="" verhindert, dass Python '\\n' nochmals übersetzt –
    die alte Version erzeugte dadurch fälschlich '\\r\\r\\n'.
    """
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(lines) + "\r\n")


# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict[str, object] = {
    "project": DEFAULT_PROJECT,
    "dedupe": True,
    "ts_mode": "live",        # "live" | "manual"
    "ts_manual": "",          # 'YYYYMMDDhhmm'
    "stempel": "",
    "geometry": "1020x760+120+80",
    "visev_header": True,
    "visev_keep_dupes": True,
}


def load_config(pfad: str | Path | None = None) -> tuple[dict[str, object], str | None]:
    """
    Lädt die config.json. Rückgabe: (Konfiguration, Warnungstext | None).
    Bei fehlender Datei: Defaults ohne Warnung. Bei kaputter Datei: Defaults + Warnung.
    """
    p = Path(pfad) if pfad is not None else config_path()
    if not p.exists():
        return dict(DEFAULT_CONFIG), None
    try:
        with open(p, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict):
            raise ValueError("Inhalt ist kein JSON-Objekt")
    except (OSError, ValueError) as e:
        return dict(DEFAULT_CONFIG), (
            f"config.json konnte nicht gelesen werden ({e}). "
            f"Es werden Standardwerte verwendet."
        )
    out = dict(DEFAULT_CONFIG)
    out.update(cfg)
    return out, None


def save_config(cfg: dict[str, object],
                pfad: str | Path | None = None) -> str | None:
    """Speichert die config.json. Rückgabe: None wenn ok, sonst Fehlermeldung."""
    p = Path(pfad) if pfad is not None else config_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return None
    except OSError as e:
        return (f"Einstellungen konnten nicht gespeichert werden:\n{p}\n{e}")


def resolve_project(cfg_project: object, daten: ProjektDaten) -> str:
    """
    Liefert ein garantiert existierendes Projekt:
    Config-Wert -> DEFAULT_PROJECT -> erster Schlüssel.
    """
    if isinstance(cfg_project, str) and cfg_project in daten.zasm:
        return cfg_project
    if DEFAULT_PROJECT in daten.zasm:
        return DEFAULT_PROJECT
    return next(iter(daten.zasm))
