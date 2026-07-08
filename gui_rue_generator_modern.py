#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RÜ-Generator – ZASM & ViseV (CustomTkinter, helles Editor-Layout)

Drei Bereiche, umschaltbar in der Kopfleiste:
- ZASM:         PNRs × Aktionscodes -> feste 95-Zeichen-Zeilen
- ViseV:        VINs × Kampagnen-Aktionen (7088) -> 'VIN<TAB>Aktion*'
- CPR-Aktionen: Verwaltung der CPR-Aktionen und ihrer Aktionscodes direkt
                im Tool (anlegen / bearbeiten / löschen), gespeichert in
                projekte.json

Die gesamte Logik liegt in rue_core.py, die Daten in projekte.json.

Start:  python gui_rue_generator_modern.py
Bedarf: pip install customtkinter
"""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

import rue_core as core

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ---------- Farbpalette (Apple-artig, hell, mehrere Tonstufen) ----------
BG      = "#f5f5f7"   # App-Hintergrund (Apple-Hellgrau)
TOPBAR  = "#fbfbfd"   # Kopfleiste (fast weiß, eine Stufe heller)
PANEL   = "#ffffff"   # Karten
FIELD   = "#f2f2f7"   # Eingabefelder (iOS grouped background)
SEC_BG  = "#eceef2"   # sekundäre (getönte) Buttons
SEC_HOV = "#e2e4ea"
LINE    = "#e5e5ea"   # Hairline-Trenner
LINE_DK = "#d1d1d6"   # dunklere Trennlinie
INK     = "#1d1d1f"   # Primärtext (Apple)
MUT     = "#86868b"   # Sekundärtext (Apple)
SB_TXT  = "#6e6e73"   # Statusleistentext
ACC     = "#007aff"   # Systemblau
ACC_DK  = "#0066d6"
GREEN   = "#34c759"   # Systemgrün (Switches)
OK_TXT  = "#248a3d"
OK_BG   = "#e4f8ea"
WARN_TXT = "#c77700"
WARN_BG  = "#fff4e0"
SB_BG   = "#eef0f6"   # Statusleiste
SEL_BG  = "#e8f1fe"   # Auswahl in Listen (zartes Blau)
RED_TXT = "#d70015"   # destruktiv (getönt)
RED_BG  = "#fdeceb"
RED_HOV = "#f9dcda"

MONO = ("Consolas", 12)
MONO_SMALL = ("Consolas", 11)
PREVIEW_MAX_ZEILEN = 5000   # Anzeige-Limit; Export enthält immer alles

VISEV_EDIT_KEY = "7088 (ViseV)"   # Eintrag der ViseV-Liste im Verwaltungsbereich


class RueApp(ctk.CTk):
    """Hauptfenster: Kopfleiste + drei umschaltbare Bereiche."""

    def __init__(self, daten: core.ProjektDaten,
                 cfg: dict[str, object], cfg_warnung: str | None = None):
        super().__init__(fg_color=BG)
        self.daten = daten
        self.cfg = cfg

        self.title("RÜ-Generator – ZASM & ViseV")
        self.minsize(1000, 660)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(core.clamp_geometry(str(cfg.get("geometry", "")), sw, sh))

        # ---------- State (aus config.json) ----------
        self.cpr_var = tk.StringVar(
            value=core.resolve_project(cfg.get("project"), daten))
        self.stempel_var = tk.StringVar(value=str(cfg.get("stempel", "")))
        self.dedupe_var = tk.BooleanVar(value=bool(cfg.get("dedupe", True)))
        ts_mode = cfg.get("ts_mode")
        self.ts_mode_var = tk.StringVar(
            value=ts_mode if ts_mode in ("live", "manual") else "live")
        self.ts_manual_var = tk.StringVar(value=str(cfg.get("ts_manual", "")))
        self.visev_header_var = tk.BooleanVar(
            value=bool(cfg.get("visev_header", True)))
        self.visev_keep_dupes_var = tk.BooleanVar(
            value=bool(cfg.get("visev_keep_dupes", True)))

        self._edit_auswahl: str | None = None   # aktuell gewählter Eintrag im Verwaltungsbereich

        self._build_topbar()
        self._build_pages()
        self._switch_view("ZASM")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Live-Vorschau-Bindings (nach dem UI-Aufbau)
        self.cpr_var.trace_add("write", lambda *_: self.update_preview_zasm())
        self.dedupe_var.trace_add("write", lambda *_: self.update_preview_zasm())
        self.ts_manual_var.trace_add("write", lambda *_: self.update_preview_zasm())
        self.stempel_var.trace_add("write", lambda *_: self.update_preview_zasm())

        self.update_preview_zasm()
        self.update_preview_visev()

        if cfg_warnung:
            self.after(200, lambda: messagebox.showwarning(
                "Konfiguration", cfg_warnung, parent=self))

    # ==================================================================
    # Kopfleiste
    # ==================================================================
    def _build_topbar(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        bar = ctk.CTkFrame(self, fg_color=TOPBAR, corner_radius=0, height=54)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(3, weight=1)

        mark = ctk.CTkLabel(bar, text="RÜ", width=34, height=34,
                            fg_color=ACC, text_color="#ffffff",
                            corner_radius=10,
                            font=ctk.CTkFont(size=13, weight="bold"))
        mark.grid(row=0, column=0, padx=(16, 9), pady=10)
        ctk.CTkLabel(bar, text="RÜ-Generator", text_color=INK,
                     font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=1, padx=(0, 22))

        # iOS-artiger Segmentschalter: graue Wanne, weißes gewähltes Segment
        self.view_seg = ctk.CTkSegmentedButton(
            bar, values=["ZASM", "ViseV", "CPR-Aktionen"],
            command=self._switch_view, corner_radius=9, border_width=3,
            fg_color=FIELD, selected_color=PANEL, selected_hover_color=PANEL,
            unselected_color=FIELD, unselected_hover_color=SEC_HOV,
            text_color=INK, font=ctk.CTkFont(size=12, weight="bold"))
        self.view_seg.grid(row=0, column=2)

        # CPR-Aktion-Auswahl rechts (nur im ZASM-Bereich sichtbar)
        self.cpr_box = ctk.CTkFrame(bar, fg_color="transparent")
        self.cpr_box.grid(row=0, column=4, padx=14)
        ctk.CTkLabel(self.cpr_box, text="CPR-Aktion:",
                     text_color=MUT).pack(side="left", padx=(0, 8))
        self.cpr_combo = ctk.CTkComboBox(
            self.cpr_box, variable=self.cpr_var,
            values=self._cpr_namen(), state="readonly", width=170,
            corner_radius=9, fg_color=PANEL, border_color=LINE_DK,
            button_color=PANEL, button_hover_color=FIELD,
            dropdown_fg_color=PANEL, dropdown_hover_color=SEL_BG,
            dropdown_text_color=INK, text_color=INK)
        self.cpr_combo.pack(side="left")

        ctk.CTkFrame(self, fg_color=LINE, corner_radius=0, height=1).grid(
            row=0, column=0, sticky="sew")

    def _cpr_namen(self) -> list[str]:
        return sorted(self.daten.zasm.keys())

    def _build_pages(self) -> None:
        container = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        container.grid(row=1, column=0, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        self.page_zasm = ctk.CTkFrame(container, fg_color=BG, corner_radius=0)
        self.page_visev = ctk.CTkFrame(container, fg_color=BG, corner_radius=0)
        self.page_edit = ctk.CTkFrame(container, fg_color=BG, corner_radius=0)
        for p in (self.page_zasm, self.page_visev, self.page_edit):
            p.grid(row=0, column=0, sticky="nsew")

        self._build_zasm_page(self.page_zasm)
        self._build_visev_page(self.page_visev)
        self._build_edit_page(self.page_edit)

    def _switch_view(self, name: str) -> None:
        self.view_seg.set(name)
        if name == "ZASM":
            self.cpr_box.grid()
            self.page_zasm.lift()
        elif name == "ViseV":
            self.cpr_box.grid_remove()
            self.page_visev.lift()
        else:
            self.cpr_box.grid_remove()
            self._edit_refresh_liste()
            self.page_edit.lift()

    # ==================================================================
    # Gemeinsame Bausteine
    # ==================================================================
    def _linkes_panel(self, page: ctk.CTkFrame) -> ctk.CTkFrame:
        """Linkes Eingabepanel als schwebende weiße Karte."""
        panel = ctk.CTkFrame(page, fg_color=PANEL, corner_radius=16, width=330,
                             border_width=1, border_color=LINE)
        panel.grid(row=0, column=0, sticky="nsw", padx=(14, 4), pady=12)
        panel.grid_propagate(False)
        page.grid_columnconfigure(1, weight=1)
        page.grid_rowconfigure(0, weight=1)
        return panel

    @staticmethod
    def _panel_titel(panel: ctk.CTkFrame, text: str) -> None:
        ctk.CTkLabel(panel, text=text.upper(), text_color=MUT, anchor="w",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(
            fill="x", padx=16, pady=(16, 4))

    @staticmethod
    def _feld_label(master, text: str):
        ctk.CTkLabel(master, text=text, text_color=MUT, anchor="w",
                     font=ctk.CTkFont(size=12)).pack(fill="x", padx=16, pady=(10, 2))

    def _editorkopf(self, editor: ctk.CTkFrame):
        """Kopfzeile des Vorschau-Editors: Dateiname, Badges, Kopieren."""
        kopf = ctk.CTkFrame(editor, fg_color="transparent", height=44)
        kopf.pack(fill="x", padx=16, pady=(10, 6))
        fn = ctk.CTkLabel(kopf, text="", text_color=INK, font=MONO_SMALL, anchor="w")
        fn.pack(side="left")
        badge = ctk.CTkLabel(kopf, text="", corner_radius=10,
                             fg_color=OK_BG, text_color=OK_TXT,
                             font=ctk.CTkFont(size=11, weight="bold"),
                             padx=8, pady=2)
        badge.pack(side="left", padx=10)
        live = ctk.CTkLabel(kopf, text="LIVE-VORSCHAU", corner_radius=10,
                            fg_color="#e3edf9", text_color=ACC,
                            font=ctk.CTkFont(size=11, weight="bold"),
                            padx=8, pady=2)
        live.pack(side="left")
        return kopf, fn, badge

    def _statusleiste(self, editor: ctk.CTkFrame):
        sb = ctk.CTkFrame(editor, fg_color=SB_BG, corner_radius=12, height=34)
        sb.pack(fill="x", side="bottom", padx=16, pady=(0, 12))
        sb.pack_propagate(False)
        links = ctk.CTkLabel(sb, text="", text_color=SB_TXT, font=MONO_SMALL)
        links.pack(side="left", padx=14)
        rechts = ctk.CTkLabel(sb, text="", text_color=SB_TXT, font=MONO_SMALL)
        rechts.pack(side="right", padx=14)
        return links, rechts

    @staticmethod
    def _set_preview(box: ctk.CTkTextbox, lines: list[str]) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        if lines:
            text = "\n".join(lines[:PREVIEW_MAX_ZEILEN])
            if len(lines) > PREVIEW_MAX_ZEILEN:
                text += (f"\n… Vorschau auf {PREVIEW_MAX_ZEILEN} Zeilen gekürzt "
                         f"(Export enthält alle {len(lines)} Zeilen)")
            box.insert("1.0", text)
        box.configure(state="disabled")

    def _bind_textbox(self, box: ctk.CTkTextbox, callback) -> None:
        box.bind("<KeyRelease>", lambda e: callback())
        box.bind("<<Paste>>", lambda e: self.after(1, callback))
        box.bind("<<Cut>>", lambda e: self.after(1, callback))

    def _copy_lines(self, lines: list[str]) -> None:
        if not lines:
            messagebox.showinfo("Hinweis", "Vorschau ist leer.", parent=self)
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))

    def _export_lines(self, lines: list[str], dateiname: str) -> None:
        out_path = core.get_unique_path(
            os.path.join(core.downloads_dir(), dateiname))
        try:
            core.write_txt_crlf(out_path, lines)
        except OSError as e:
            messagebox.showerror("Fehler beim Speichern",
                                 f"{out_path}\n\n{e}", parent=self)
            return
        messagebox.showinfo("Fertig", f"TXT erstellt:\n{out_path}", parent=self)
        if os.name == "nt":
            try:
                subprocess.run(["explorer", "/select,", out_path], check=False)
            except OSError:
                pass

    def open_downloads(self) -> None:
        ordner = core.downloads_dir()
        if os.name == "nt":
            try:
                subprocess.run(["explorer", ordner], check=False)
                return
            except OSError:
                pass
        messagebox.showinfo("Ordner", ordner, parent=self)

    # ==================================================================
    # Bereich 1: ZASM
    # ==================================================================
    def _build_zasm_page(self, page: ctk.CTkFrame) -> None:
        panel = self._linkes_panel(page)

        self._panel_titel(panel, "Eingaben")

        self._feld_label(panel, f"Stempel ({core.STEMPEL_LEN} Zeichen)")
        ctk.CTkEntry(panel, textvariable=self.stempel_var, font=MONO, height=34,
                     corner_radius=9, border_width=0,
                     fg_color=FIELD, text_color=INK).pack(
            fill="x", padx=16)

        self._feld_label(panel, "Zeitstempel")
        self.ts_seg = ctk.CTkSegmentedButton(
            panel, values=["Live", "Manuell"],
            command=self._on_ts_seg, corner_radius=9, border_width=3,
            fg_color=FIELD, selected_color=PANEL, selected_hover_color=PANEL,
            unselected_color=FIELD, unselected_hover_color=SEC_HOV,
            text_color=INK)
        self.ts_seg.set("Manuell" if self.ts_mode_var.get() == "manual" else "Live")
        self.ts_seg.pack(fill="x", padx=16)
        self.ts_entry = ctk.CTkEntry(
            panel, textvariable=self.ts_manual_var, font=MONO, height=34,
            corner_radius=9, border_width=0, placeholder_text="YYYYMMDDhhmm",
            fg_color=FIELD, text_color=INK)
        self.ts_entry.pack(fill="x", padx=16, pady=(6, 0))

        self._feld_label(panel, "PNRs (Einfügen aus Excel)")
        self.txt_pnrs = ctk.CTkTextbox(panel, wrap="none", font=MONO,
                                       corner_radius=10, border_width=0,
                                       fg_color=FIELD, text_color=INK)
        self.txt_pnrs.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self._bind_textbox(self.txt_pnrs, self.update_preview_zasm)

        ctk.CTkSwitch(panel, text="Doppelte PNRs entfernen",
                      variable=self.dedupe_var,
                      progress_color=GREEN, text_color=INK).pack(
            anchor="w", padx=16, pady=(0, 12))

        ctk.CTkButton(panel, text="⬇  TXT generieren", height=40,
                      corner_radius=12, fg_color=ACC, hover_color=ACC_DK,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self.export_txt_zasm).pack(fill="x", padx=16)
        ctk.CTkButton(panel, text="Downloads öffnen", height=32,
                      corner_radius=10, fg_color=SEC_BG, hover_color=SEC_HOV,
                      text_color=ACC,
                      command=self.open_downloads).pack(fill="x", padx=16, pady=8)
        ctk.CTkButton(panel, text="Eingabe leeren", height=28,
                      corner_radius=10, fg_color=SEC_BG, hover_color=SEC_HOV,
                      text_color=INK,
                      command=self.clear_zasm).pack(fill="x", padx=16, pady=(0, 16))

        # Editor rechts
        editor = ctk.CTkFrame(page, fg_color=BG, corner_radius=0)
        editor.grid(row=0, column=1, sticky="nsew")
        _, self.fn_zasm, self.badge_zasm = self._editorkopf(editor)
        ctk.CTkButton(editor.winfo_children()[0], text="⧉ Kopieren", width=100,
                      corner_radius=10, fg_color=SEC_BG, hover_color=SEC_HOV,
                      text_color=ACC,
                      command=self.copy_preview_zasm).pack(side="right")
        self.sb_zasm_l, self.sb_zasm_r = self._statusleiste(editor)
        self.preview_zasm = ctk.CTkTextbox(
            editor, wrap="none", font=MONO, state="disabled",
            fg_color=PANEL, border_color=LINE, border_width=1,
            text_color=INK, corner_radius=12)
        self.preview_zasm.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    def _on_ts_seg(self, wert: str) -> None:
        self.ts_mode_var.set("manual" if wert == "Manuell" else "live")
        self.update_preview_zasm()

    def _zasm_ts(self) -> tuple[str, str | None]:
        if self.ts_mode_var.get() == "manual":
            fehler = core.validate_manual_ts(self.ts_manual_var.get())
            if fehler is None:
                return self.ts_manual_var.get().strip(), None
            return core.now_ts_compact(), "TS ungültig → Live"
        return core.now_ts_compact(), None

    def _zasm_lines(self) -> tuple[list[str], str | None]:
        aktionen = self.daten.zasm_aktionen(self.cpr_var.get())
        pnrs = core.parse_pnrs(self.txt_pnrs.get("1.0", "end"),
                               remove_dupes=self.dedupe_var.get())
        if not aktionen or not pnrs:
            return [], None
        ts, hinweis = self._zasm_ts()
        return core.build_zasm_lines(aktionen, pnrs,
                                     self.stempel_var.get(), ts), hinweis

    def update_preview_zasm(self) -> None:
        lines, hinweis = self._zasm_lines()
        self._set_preview(self.preview_zasm, lines)

        stempel = self.stempel_var.get().strip().upper() or "STEMPEL"
        self.fn_zasm.configure(
            text=core.zasm_dateiname(self.cpr_var.get(), stempel))

        n_pnrs = len(core.parse_pnrs(self.txt_pnrs.get("1.0", "end"),
                                     remove_dupes=self.dedupe_var.get()))
        n_akt = len(self.daten.zasm_aktionen(self.cpr_var.get()))
        if lines:
            ok = all(len(l) == core.LINE_LEN for l in lines)
            if ok:
                self.badge_zasm.configure(
                    text=f"✓ {len(lines)} Zeilen · alle {core.LINE_LEN} Zeichen",
                    fg_color=OK_BG, text_color=OK_TXT)
            else:
                self.badge_zasm.configure(
                    text=f"⚠ Zeilen mit Länge ≠ {core.LINE_LEN}",
                    fg_color=WARN_BG, text_color=WARN_TXT)
        else:
            self.badge_zasm.configure(text="– keine Eingabe –",
                                      fg_color=BG, text_color=MUT)
        links = f"PNRs: {n_pnrs}   Aktionen: {n_akt}   Zeilen: {len(lines)}"
        if hinweis:
            links += f"   ⚠ {hinweis}"
        self.sb_zasm_l.configure(text=links)
        self.sb_zasm_r.configure(
            text=f"Dedupe: {'AN' if self.dedupe_var.get() else 'AUS'}   "
                 f"TS: {'MANUELL' if self.ts_mode_var.get() == 'manual' else 'LIVE'}"
                 f"   → Downloads")

    def export_txt_zasm(self) -> None:
        fehler = core.validate_stempel(self.stempel_var.get())
        if fehler:
            messagebox.showwarning("Stempel", fehler, parent=self)
            return
        if self.ts_mode_var.get() == "manual":
            fehler = core.validate_manual_ts(self.ts_manual_var.get())
            if fehler:
                messagebox.showwarning("Zeitstempel", fehler, parent=self)
                return
        lines, _ = self._zasm_lines()
        if not lines:
            messagebox.showwarning("Hinweis",
                                   "Vorschau ist leer. Bitte PNRs eingeben.",
                                   parent=self)
            return
        self._export_lines(lines, core.zasm_dateiname(self.cpr_var.get(),
                                                      self.stempel_var.get()))

    def copy_preview_zasm(self) -> None:
        self._copy_lines(self._zasm_lines()[0])

    def clear_zasm(self) -> None:
        self.txt_pnrs.delete("1.0", "end")
        self.update_preview_zasm()

    # ==================================================================
    # Bereich 2: ViseV
    # ==================================================================
    def _build_visev_page(self, page: ctk.CTkFrame) -> None:
        panel = self._linkes_panel(page)

        self._panel_titel(panel, "Eingaben")
        self.visev_info = ctk.CTkLabel(
            panel,
            text=f"CPR-Aktion (fix): {core.VISEV_PROJEKT} · "
                 f"{len(self.daten.visev_aktionen())} Kampagnen-Aktionen",
            text_color=INK, anchor="w", font=ctk.CTkFont(size=12))
        self.visev_info.pack(fill="x", padx=16, pady=(4, 0))

        self._feld_label(panel, "VINs (Einfügen aus Excel)")
        self.txt_vins = ctk.CTkTextbox(panel, wrap="none", font=MONO,
                                       corner_radius=10, border_width=0,
                                       fg_color=FIELD, text_color=INK)
        self.txt_vins.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self._bind_textbox(self.txt_vins, self.update_preview_visev)

        ctk.CTkSwitch(panel, text="Header ausgeben",
                      variable=self.visev_header_var,
                      command=self.update_preview_visev,
                      progress_color=GREEN, text_color=INK).pack(
            anchor="w", padx=16, pady=(0, 6))
        ctk.CTkSwitch(panel, text="VIN-Duplikate beibehalten",
                      variable=self.visev_keep_dupes_var,
                      command=self.update_preview_visev,
                      progress_color=GREEN, text_color=INK).pack(
            anchor="w", padx=16, pady=(0, 12))

        ctk.CTkButton(panel, text="⬇  TXT generieren", height=40,
                      corner_radius=12, fg_color=ACC, hover_color=ACC_DK,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self.export_txt_visev).pack(fill="x", padx=16)
        ctk.CTkButton(panel, text="Downloads öffnen", height=32,
                      corner_radius=10, fg_color=SEC_BG, hover_color=SEC_HOV,
                      text_color=ACC,
                      command=self.open_downloads).pack(fill="x", padx=16, pady=8)
        ctk.CTkButton(panel, text="Eingabe leeren", height=28,
                      corner_radius=10, fg_color=SEC_BG, hover_color=SEC_HOV,
                      text_color=INK,
                      command=self.clear_visev).pack(fill="x", padx=16, pady=(0, 16))

        editor = ctk.CTkFrame(page, fg_color=BG, corner_radius=0)
        editor.grid(row=0, column=1, sticky="nsew")
        _, self.fn_visev, self.badge_visev = self._editorkopf(editor)
        ctk.CTkButton(editor.winfo_children()[0], text="⧉ Kopieren", width=100,
                      corner_radius=10, fg_color=SEC_BG, hover_color=SEC_HOV,
                      text_color=ACC,
                      command=self.copy_preview_visev).pack(side="right")
        self.sb_visev_l, self.sb_visev_r = self._statusleiste(editor)
        self.preview_visev = ctk.CTkTextbox(
            editor, wrap="none", font=MONO, state="disabled",
            fg_color=PANEL, border_color=LINE, border_width=1,
            text_color=INK, corner_radius=12)
        self.preview_visev.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    def _visev_lines(self) -> tuple[list[str], int]:
        vins = core.parse_vins(self.txt_vins.get("1.0", "end"),
                               keep_dupes=self.visev_keep_dupes_var.get())
        lines = core.build_visev_lines(
            vins, self.daten.visev_aktionen(),
            include_header=self.visev_header_var.get())
        return lines, len(vins)

    def update_preview_visev(self) -> None:
        lines, n_vins = self._visev_lines()
        self._set_preview(self.preview_visev, lines)
        self.fn_visev.configure(text=core.visev_dateiname())
        n_akt = len(self.daten.visev_aktionen())
        if n_vins:
            self.badge_visev.configure(text=f"✓ {n_vins} VINs · {len(lines)} Zeilen",
                                       fg_color=OK_BG, text_color=OK_TXT)
        else:
            self.badge_visev.configure(text="– keine VINs –",
                                       fg_color=BG, text_color=MUT)
        self.sb_visev_l.configure(
            text=f"VINs: {n_vins}   Aktionen: {n_akt}   Zeilen: {len(lines)}")
        self.sb_visev_r.configure(
            text=f"Header: {'AN' if self.visev_header_var.get() else 'AUS'}   "
                 f"Duplikate: "
                 f"{'BEHALTEN' if self.visev_keep_dupes_var.get() else 'ENTFERNEN'}"
                 f"   → Downloads")

    def export_txt_visev(self) -> None:
        lines, n_vins = self._visev_lines()
        if n_vins == 0:
            messagebox.showwarning("Hinweis",
                                   "Keine VINs erkannt. Bitte VINs einfügen.",
                                   parent=self)
            return
        self._export_lines(lines, core.visev_dateiname())

    def copy_preview_visev(self) -> None:
        self._copy_lines(self._visev_lines()[0])

    def clear_visev(self) -> None:
        self.txt_vins.delete("1.0", "end")
        self.update_preview_visev()

    # ==================================================================
    # Bereich 3: CPR-Aktionen verwalten
    # ==================================================================
    def _build_edit_page(self, page: ctk.CTkFrame) -> None:
        panel = self._linkes_panel(page)

        self._panel_titel(panel, "CPR-Aktionen")
        ctk.CTkButton(panel, text="+ Neue CPR-Aktion", height=34,
                      corner_radius=10, fg_color=ACC, hover_color=ACC_DK,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=self._edit_neu).pack(fill="x", padx=16, pady=(4, 8))
        self.edit_liste = ctk.CTkScrollableFrame(panel, fg_color=PANEL,
                                                 corner_radius=0)
        self.edit_liste.pack(fill="both", expand=True, padx=8, pady=(0, 12))

        # Rechte Seite: Editor-Karte
        rechts = ctk.CTkFrame(page, fg_color=BG, corner_radius=0)
        rechts.grid(row=0, column=1, sticky="nsew")
        karte = ctk.CTkFrame(rechts, fg_color=PANEL, corner_radius=16,
                             border_width=1, border_color=LINE)
        karte.pack(fill="both", expand=True, padx=16, pady=14)

        kopf = ctk.CTkFrame(karte, fg_color="transparent")
        kopf.pack(fill="x", padx=18, pady=(14, 4))
        self.edit_titel = ctk.CTkLabel(kopf, text="CPR-Aktion bearbeiten",
                                       text_color=INK,
                                       font=ctk.CTkFont(size=15, weight="bold"))
        self.edit_titel.pack(side="left")
        self.edit_status = ctk.CTkLabel(kopf, text="", text_color=OK_TXT,
                                        font=ctk.CTkFont(size=12, weight="bold"))
        self.edit_status.pack(side="right")

        zeile = ctk.CTkFrame(karte, fg_color="transparent")
        zeile.pack(fill="x", padx=18, pady=(6, 0))
        ctk.CTkLabel(zeile, text="Name:", text_color=MUT).pack(side="left")
        self.edit_name = ctk.CTkEntry(zeile, width=220, font=MONO, height=34,
                                      corner_radius=9, border_width=0,
                                      fg_color=FIELD, text_color=INK)
        self.edit_name.pack(side="left", padx=10)
        self.edit_anzahl = ctk.CTkLabel(zeile, text="", text_color=MUT)
        self.edit_anzahl.pack(side="left", padx=10)

        ctk.CTkLabel(karte, text="Aktionscodes (einer je Zeile, 12 Ziffern):",
                     text_color=MUT, anchor="w").pack(fill="x", padx=18, pady=(12, 2))
        self.edit_codes = ctk.CTkTextbox(karte, wrap="none", font=MONO,
                                         corner_radius=10, border_width=0,
                                         fg_color=FIELD, text_color=INK)
        self.edit_codes.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        self.edit_codes.bind("<KeyRelease>", lambda e: self._edit_zaehler())
        self.edit_codes.bind("<<Paste>>", lambda e: self.after(1, self._edit_zaehler))

        knopfzeile = ctk.CTkFrame(karte, fg_color="transparent")
        knopfzeile.pack(fill="x", padx=18, pady=(0, 14))
        self.edit_speichern_btn = ctk.CTkButton(
            knopfzeile, text="💾  Speichern", height=36, width=160,
            corner_radius=12, fg_color=ACC, hover_color=ACC_DK,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._edit_speichern)
        self.edit_speichern_btn.pack(side="left")
        self.edit_loeschen_btn = ctk.CTkButton(
            knopfzeile, text="🗑  Löschen", height=36, width=120,
            corner_radius=12, fg_color=RED_BG, hover_color=RED_HOV,
            text_color=RED_TXT, command=self._edit_loeschen)
        self.edit_loeschen_btn.pack(side="left", padx=10)
        ctk.CTkLabel(
            knopfzeile,
            text="Änderungen werden in projekte.json gespeichert.",
            text_color=MUT, font=ctk.CTkFont(size=11)).pack(side="right")

    def _edit_eintraege(self) -> list[str]:
        return self._cpr_namen() + [VISEV_EDIT_KEY]

    def _edit_refresh_liste(self) -> None:
        for w in self.edit_liste.winfo_children():
            w.destroy()
        for name in self._edit_eintraege():
            aktiv = (name == self._edit_auswahl)
            anz = (len(self.daten.visev_aktionen())
                   if name == VISEV_EDIT_KEY
                   else len(self.daten.zasm_aktionen(name)))
            ctk.CTkButton(
                self.edit_liste,
                text=f"{name}   ·   {anz} Codes",
                anchor="w", height=32, corner_radius=9,
                fg_color=SEL_BG if aktiv else "transparent",
                hover_color=SEL_BG if aktiv else FIELD,
                text_color=ACC if aktiv else INK,
                font=ctk.CTkFont(size=12,
                                 weight="bold" if aktiv else "normal"),
                command=lambda n=name: self._edit_auswaehlen(n)).pack(
                fill="x", pady=1)

    def _edit_auswaehlen(self, name: str) -> None:
        self._edit_auswahl = name
        self.edit_status.configure(text="")
        self.edit_name.configure(state="normal")
        self.edit_name.delete(0, "end")
        if name == VISEV_EDIT_KEY:
            self.edit_name.insert(0, name)
            self.edit_name.configure(state="disabled")
            codes = self.daten.visev_aktionen()
            self.edit_titel.configure(text="ViseV-Kampagnen (7088) bearbeiten")
            self.edit_loeschen_btn.configure(state="disabled")
        else:
            self.edit_name.insert(0, name)
            codes = self.daten.zasm_aktionen(name)
            self.edit_titel.configure(text=f"CPR-Aktion „{name}“ bearbeiten")
            self.edit_loeschen_btn.configure(state="normal")
        self.edit_codes.delete("1.0", "end")
        self.edit_codes.insert("1.0", "\n".join(codes))
        self._edit_zaehler()
        self._edit_refresh_liste()

    def _edit_neu(self) -> None:
        self._edit_auswahl = None
        self.edit_name.configure(state="normal")
        self.edit_name.delete(0, "end")
        self.edit_codes.delete("1.0", "end")
        self.edit_titel.configure(text="Neue CPR-Aktion anlegen")
        self.edit_status.configure(text="")
        self.edit_loeschen_btn.configure(state="disabled")
        self._edit_zaehler()
        self._edit_refresh_liste()
        self.edit_name.focus_set()

    def _edit_zaehler(self) -> None:
        codes = core.parse_aktionscodes(self.edit_codes.get("1.0", "end"))
        self.edit_anzahl.configure(text=f"{len(codes)} Aktionscodes")

    def _edit_speichern(self) -> None:
        codes = core.parse_aktionscodes(self.edit_codes.get("1.0", "end"))
        fehler = core.validate_aktionscodes(codes)
        if fehler:
            messagebox.showwarning("Aktionscodes", fehler, parent=self)
            return

        if self._edit_auswahl == VISEV_EDIT_KEY:
            self.daten.visev[core.VISEV_PROJEKT] = codes
        else:
            name = self.edit_name.get().strip()
            if not name:
                messagebox.showwarning("Name", "Bitte einen Namen für die "
                                               "CPR-Aktion eingeben.", parent=self)
                return
            if name == VISEV_EDIT_KEY:
                messagebox.showwarning("Name", "Dieser Name ist reserviert.",
                                       parent=self)
                return
            if (name != self._edit_auswahl and name in self.daten.zasm
                    and not messagebox.askyesno(
                        "Überschreiben?",
                        f"„{name}“ existiert bereits. Überschreiben?",
                        parent=self)):
                return
            if self._edit_auswahl and self._edit_auswahl != name:
                self.daten.zasm.pop(self._edit_auswahl, None)   # Umbenennen
            self.daten.zasm[name] = codes
            self._edit_auswahl = name

        fehler = core.speichere_projekte(self.daten)
        if fehler:
            messagebox.showerror("Speichern fehlgeschlagen", fehler, parent=self)
            return
        self.edit_status.configure(text="✓ Gespeichert (projekte.json)")
        self._nach_datenaenderung()

    def _edit_loeschen(self) -> None:
        name = self._edit_auswahl
        if not name or name == VISEV_EDIT_KEY:
            return
        if len(self.daten.zasm) <= 1:
            messagebox.showwarning("Löschen",
                                   "Die letzte CPR-Aktion kann nicht gelöscht "
                                   "werden.", parent=self)
            return
        if not messagebox.askyesno(
                "Löschen bestätigen",
                f"CPR-Aktion „{name}“ mit "
                f"{len(self.daten.zasm_aktionen(name))} Aktionscodes wirklich "
                f"löschen?", parent=self):
            return
        self.daten.zasm.pop(name, None)
        fehler = core.speichere_projekte(self.daten)
        if fehler:
            messagebox.showerror("Speichern fehlgeschlagen", fehler, parent=self)
            return
        self._edit_neu()
        self.edit_status.configure(text=f"✓ „{name}“ gelöscht")
        self._nach_datenaenderung()

    def _nach_datenaenderung(self) -> None:
        """Nach Anlegen/Ändern/Löschen: Auswahllisten und Vorschauen auffrischen."""
        namen = self._cpr_namen()
        self.cpr_combo.configure(values=namen)
        if self.cpr_var.get() not in namen:
            self.cpr_var.set(core.resolve_project(None, self.daten))
        self.visev_info.configure(
            text=f"CPR-Aktion (fix): {core.VISEV_PROJEKT} · "
                 f"{len(self.daten.visev_aktionen())} Kampagnen-Aktionen")
        self._edit_refresh_liste()
        self._edit_zaehler()
        self.update_preview_zasm()
        self.update_preview_visev()

    # ==================================================================
    # Persistenz / Schließen
    # ==================================================================
    def on_close(self) -> None:
        self.cfg.update({
            "project": self.cpr_var.get(),
            "dedupe": self.dedupe_var.get(),
            "ts_mode": self.ts_mode_var.get(),
            "ts_manual": self.ts_manual_var.get().strip(),
            "stempel": self.stempel_var.get().strip().upper(),
            "visev_header": self.visev_header_var.get(),
            "visev_keep_dupes": self.visev_keep_dupes_var.get(),
        })
        try:
            self.cfg["geometry"] = self.geometry()
        except tk.TclError:
            pass
        fehler = core.save_config(self.cfg)
        if fehler:
            messagebox.showwarning("Konfiguration", fehler, parent=self)
        self.destroy()


# ----------------------------------------------------------------------
# Start
# ----------------------------------------------------------------------
def _start_fehler(titel: str, text: str) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(titel, text)
    root.destroy()


def main() -> None:
    try:
        daten = core.lade_projekte()
    except core.ProjektDatenFehler as e:
        _start_fehler("Projektdaten", str(e))
        sys.exit(1)
    cfg, warnung = core.load_config()
    RueApp(daten, cfg, warnung).mainloop()


if __name__ == "__main__":
    main()
