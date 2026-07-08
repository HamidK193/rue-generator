#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-Tests für rue_core (reine Logik, ohne GUI).

Ausführen aus dem Repo-Root:
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import rue_core as rc  # noqa: E402


class TestParsePnrs(unittest.TestCase):
    def test_einfache_liste(self):
        self.assertEqual(rc.parse_pnrs("1234567\n2345678"), ["1234567", "2345678"])

    def test_trennzeichen_gemischt(self):
        text = "111; 222,333\t444  555"
        self.assertEqual(rc.parse_pnrs(text), ["111", "222", "333", "444", "555"])

    def test_dedupe_erhaelt_reihenfolge(self):
        self.assertEqual(rc.parse_pnrs("3 1 3 2 1"), ["3", "1", "2"])

    def test_ohne_dedupe(self):
        self.assertEqual(rc.parse_pnrs("3 1 3", remove_dupes=False), ["3", "1", "3"])

    def test_leer(self):
        self.assertEqual(rc.parse_pnrs(""), [])
        self.assertEqual(rc.parse_pnrs("abc def"), [])


class TestParseVins(unittest.TestCase):
    VIN1 = "WVWZZZ1JZXW000001"
    VIN2 = "WAUZZZ8K9BA123456"

    def test_gueltige_vins(self):
        text = f"{self.VIN1}\n{self.VIN2}"
        self.assertEqual(rc.parse_vins(text), [self.VIN1, self.VIN2])

    def test_kleinschreibung_wird_normalisiert(self):
        self.assertEqual(rc.parse_vins(self.VIN1.lower()), [self.VIN1])

    def test_duplikate_behalten_und_entfernen(self):
        text = f"{self.VIN1} {self.VIN1}"
        self.assertEqual(rc.parse_vins(text, keep_dupes=True),
                         [self.VIN1, self.VIN1])
        self.assertEqual(rc.parse_vins(text, keep_dupes=False), [self.VIN1])

    def test_zu_kurz_wird_ignoriert(self):
        self.assertEqual(rc.parse_vins("WVWZZZ1JZXW00001"), [])  # 16 Zeichen


class TestZasmZeilen(unittest.TestCase):
    def test_zeile_hat_95_zeichen(self):
        line = rc.build_line_zasm("054020250001", "1234567", "ABCD1234", "202607081200")
        self.assertEqual(len(line), rc.LINE_LEN)

    def test_layout_positionen(self):
        aktion, pnr, stempel, ts = "054020250001", "1234567", "ABCD1234", "202607081200"
        line = rc.build_line_zasm(aktion, pnr, stempel, ts)
        self.assertTrue(line.startswith(f"{aktion} {rc.CONST1} {pnr:>7}"))
        # Rechter Block beginnt exakt an Spalte AFTER_PNR_COL
        self.assertEqual(line[rc.AFTER_PNR_COL:rc.AFTER_PNR_COL + 8], stempel)
        self.assertIn(f"{stempel} {rc.CONST2} {ts}", line)

    def test_kurze_pnr_wird_rechtsbuendig(self):
        line = rc.build_line_zasm("054020250001", "42", "ABCD1234", "202607081200")
        self.assertIn("PNR   P      42", line)
        self.assertEqual(len(line), rc.LINE_LEN)

    def test_kreuzprodukt_und_stempel_normalisierung(self):
        lines = rc.build_zasm_lines(
            ["A1", "A2", "A3"], ["111", "222"], "abcd1234", "202607081200"
        )
        self.assertEqual(len(lines), 6)  # 2 PNRs x 3 Aktionen
        self.assertIn("ABCD1234", lines[0])  # upper()
        for line in lines:
            self.assertEqual(len(line), rc.LINE_LEN)

    def test_dateiname(self):
        from datetime import datetime
        name = rc.zasm_dateiname("10053", "abcd1234", datetime(2026, 7, 8, 15, 30))
        self.assertEqual(name, "RÜ_08072026_10053_ABCD1234.txt")


class TestVisevZeilen(unittest.TestCase):
    VIN = "WVWZZZ1JZXW000001"

    def test_vin_bindestrich(self):
        self.assertEqual(rc.format_vin(self.VIN), "WVWZZZ1JZX-W000001")

    def test_zeilenformat_mit_header(self):
        lines = rc.build_visev_lines([self.VIN], ["054000007015", "054000007042"],
                                     include_header=True)
        self.assertEqual(lines[0], "VIN\tCampaign Description")
        self.assertEqual(lines[1], "WVWZZZ1JZX-W000001\t054000007015*")
        self.assertEqual(lines[2], "WVWZZZ1JZX-W000001\t054000007042*")

    def test_ohne_header(self):
        lines = rc.build_visev_lines([self.VIN], ["X"], include_header=False)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].endswith("X*"))

    def test_keine_vins_nur_header(self):
        self.assertEqual(rc.build_visev_lines([], ["X"], include_header=True),
                         ["VIN\tCampaign Description"])


class TestValidierung(unittest.TestCase):
    def test_stempel_ok(self):
        self.assertIsNone(rc.validate_stempel("ABCD1234"))

    def test_stempel_leer_und_falsche_laenge(self):
        self.assertIsNotNone(rc.validate_stempel(""))
        self.assertIsNotNone(rc.validate_stempel("ABC"))
        self.assertIsNotNone(rc.validate_stempel("ABCD12345"))

    def test_stempel_verbotene_zeichen(self):
        self.assertIsNotNone(rc.validate_stempel("AB/D1234"))
        self.assertIsNotNone(rc.validate_stempel("AB:D1234"))

    def test_manueller_ts_ok(self):
        self.assertIsNone(rc.validate_manual_ts("202607081530"))

    def test_manueller_ts_fehler(self):
        self.assertIsNotNone(rc.validate_manual_ts(""))          # leer
        self.assertIsNotNone(rc.validate_manual_ts("2026070815"))  # zu kurz
        self.assertIsNotNone(rc.validate_manual_ts("202613081530"))  # Monat 13
        self.assertIsNotNone(rc.validate_manual_ts("20260708153x"))  # keine Ziffer


class TestDateien(unittest.TestCase):
    def test_unique_path_nummerierung(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.txt")
            self.assertEqual(rc.get_unique_path(p), p)
            Path(p).write_text("x")
            p2 = rc.get_unique_path(p)
            self.assertEqual(p2, os.path.join(d, "a (2).txt"))
            Path(p2).write_text("x")
            self.assertEqual(rc.get_unique_path(p), os.path.join(d, "a (3).txt"))

    def test_write_txt_crlf_bytes(self):
        """Regressionstest: alte Version schrieb \\r\\r\\n statt \\r\\n."""
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "out.txt")
            rc.write_txt_crlf(p, ["ZEILE1", "ZEILE2"])
            raw = Path(p).read_bytes()
            self.assertEqual(raw, b"ZEILE1\r\nZEILE2\r\n")
            self.assertNotIn(b"\r\r\n", raw)


class TestProjektDaten(unittest.TestCase):
    def test_lade_repo_projekte(self):
        daten = rc.lade_projekte(REPO_ROOT / "projekte.json")
        self.assertEqual(len(daten.zasm), 29)
        # Erwartete Anzahlen nach Deduplizierung (aus alter Datei verifiziert)
        self.assertEqual(len(daten.zasm["7042"]), 62)
        self.assertEqual(len(daten.zasm["7088"]), 71)
        self.assertEqual(len(daten.zasm["90082"]), 81)
        self.assertEqual(len(daten.zasm["10053"]), 44)
        self.assertEqual(len(daten.visev_aktionen()), 67)
        # keine Duplikate in irgendeiner Liste
        for name, akt in {**daten.zasm, **daten.visev}.items():
            self.assertEqual(len(akt), len(set(akt)), f"Duplikate in {name}")

    def test_default_project_existiert(self):
        daten = rc.lade_projekte(REPO_ROOT / "projekte.json")
        self.assertIn(rc.DEFAULT_PROJECT, daten.zasm)

    def test_dedupe_beim_laden(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "projekte.json"
            p.write_text(json.dumps({"zasm": {"X": ["1", "2", "1"]}}), encoding="utf-8")
            daten = rc.lade_projekte(p)
            self.assertEqual(daten.zasm["X"], ["1", "2"])

    def test_fehlende_datei(self):
        with self.assertRaises(rc.ProjektDatenFehler):
            rc.lade_projekte("/nicht/vorhanden/projekte.json")

    def test_kaputtes_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "projekte.json"
            p.write_text("{kaputt", encoding="utf-8")
            with self.assertRaises(rc.ProjektDatenFehler):
                rc.lade_projekte(p)

    def test_resolve_project(self):
        daten = rc.ProjektDaten(zasm={"10053": ["A"], "7042": ["B"]})
        self.assertEqual(rc.resolve_project("7042", daten), "7042")
        self.assertEqual(rc.resolve_project("gibtsnicht", daten), "10053")
        daten2 = rc.ProjektDaten(zasm={"7042": ["B"]})
        self.assertEqual(rc.resolve_project("gibtsnicht", daten2), "7042")


class TestClampGeometry(unittest.TestCase):
    def test_gueltige_geometrie_bleibt(self):
        self.assertEqual(rc.clamp_geometry("980x720+120+80", 1920, 1080),
                         "980x720+120+80")

    def test_offscreen_wird_zurueckgeholt(self):
        self.assertEqual(rc.clamp_geometry("980x720+5000+80", 1920, 1080),
                         "980x720+940+80")

    def test_negative_position(self):
        self.assertEqual(rc.clamp_geometry("980x720-50-50", 1920, 1080),
                         "980x720+0+0")

    def test_unsinnige_eingabe_faellt_auf_default(self):
        self.assertEqual(rc.clamp_geometry("kaputt", 1920, 1080),
                         "1020x760+120+80")

    def test_zu_gross_wird_begrenzt(self):
        self.assertEqual(rc.clamp_geometry("4000x3000+0+0", 1920, 1080),
                         "1920x1080+0+0")


class TestConfig(unittest.TestCase):
    def test_fehlende_config_liefert_defaults(self):
        cfg, warn = rc.load_config("/nicht/vorhanden/config.json")
        self.assertIsNone(warn)
        self.assertEqual(cfg["project"], rc.DEFAULT_PROJECT)

    def test_kaputte_config_warnt(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            p.write_text("{kaputt", encoding="utf-8")
            cfg, warn = rc.load_config(p)
            self.assertIsNotNone(warn)
            self.assertEqual(cfg["project"], rc.DEFAULT_PROJECT)

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            cfg = dict(rc.DEFAULT_CONFIG)
            cfg["stempel"] = "ABCD1234"
            self.assertIsNone(rc.save_config(cfg, p))
            geladen, warn = rc.load_config(p)
            self.assertIsNone(warn)
            self.assertEqual(geladen["stempel"], "ABCD1234")

    def test_unbekannte_keys_bleiben_erhalten(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            p.write_text(json.dumps({"theme": "light"}), encoding="utf-8")
            cfg, _ = rc.load_config(p)
            self.assertEqual(cfg["theme"], "light")


class TestParitaetMitAlterVersion(unittest.TestCase):
    """Stellt sicher, dass die neue Logik dieselben Zeilen baut wie die alte Datei."""

    @classmethod
    def setUpClass(cls):
        import ast
        src = (REPO_ROOT / "gui_rue_generator_unified.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "PROJEKTE":
                        cls.alte_projekte = ast.literal_eval(node.value)
                    if isinstance(t, ast.Name) and t.id == "VISEV_ACTIONS_7088":
                        cls.alte_visev = ast.literal_eval(node.value)

    def test_zasm_codes_identisch_nach_dedupe(self):
        daten = rc.lade_projekte(REPO_ROOT / "projekte.json")
        for name, alt in self.alte_projekte.items():
            erwartet = list(dict.fromkeys(alt["AKTIONEN"]))
            self.assertEqual(daten.zasm[name], erwartet, f"Abweichung in {name}")

    def test_visev_codes_identisch(self):
        daten = rc.lade_projekte(REPO_ROOT / "projekte.json")
        self.assertEqual(daten.visev_aktionen(),
                         list(dict.fromkeys(self.alte_visev)))

    def test_zasm_zeile_identisch_zur_alten_formel(self):
        """Alte Formel nachgebaut: Ergebnis muss Zeichen für Zeichen gleich sein."""
        aktion, pnr, stempel, ts = "054020250001", "1234567", "ABCD1234", "202607081200"
        left = f"{aktion} PNR   P {pnr:>7}"
        left += " " * (70 - len(left))
        alt = left + f"{stempel} NIO {ts}"
        alt += " " * (95 - len(alt))
        self.assertEqual(rc.build_line_zasm(aktion, pnr, stempel, ts), alt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
