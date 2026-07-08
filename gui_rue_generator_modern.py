#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RUE-Generator (moderne Version) – ZASM & ViseV

Moderne Oberfläche auf Basis von CustomTkinter. Funktional identisch zur
alten Tkinter-Version (gui_rue_generator_unified.py):

- ZASM-Tab: PNRs x Aktionscodes -> feste 95-Zeichen-Zeilen
- ViseV-Tab: VINs x Kampagnen-Aktionen (Projekt 7088) -> 'VIN<TAB>Aktion*'
- Zeitstempel live/manuell, Duplikat-Handling, Export nach ~/Downloads
  mit (2)-Nummerierung, Vorschau kopieren, Explorer öffnen,
  Persistenz über config.json

Die gesamte Logik (Parsing, Zeilenbau, Validierung, Dateien) liegt in
rue_core.py; die Projektdaten in projekte.json.

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

# ---------- Erscheinungsbild (ein fester, moderner Look) ----------
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

MONO = ("Consolas", 12)          # Monospace für Eingabe/Vorschau
PREVIEW_MAX_ZEILEN = 5000        # Anzeige-Limit der Vorschau (Export immer komplett)
PAD = 12


class RueApp(ctk.CTk):
    """Hauptfenster mit ZASM- und ViseV-Tab."""

    def __init__(self, daten: core.ProjektDaten,
                 cfg: dict[str, object], cfg_warnung: str | None = None):
        super().__init__()
        self.daten = daten
        self.cfg = cfg

        self.title("RUE-Generator – ZASM & ViseV")
        self.minsize(940, 680)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(core.clamp_geometry(str(cfg.get("geometry", "")), sw, sh))

        # ---------- State (aus config.json) ----------
        self.project_var = tk.StringVar(
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

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Live-Vorschau-Bindings
        self.project_var.trace_add("write", lambda *_: self.update_preview_zasm())
        self.dedupe_var.trace_add("write", lambda *_: self.update_preview_zasm())
        self.ts_mode_var.trace_add("write", lambda *_: self.update_preview_zasm())
        self.ts_manual_var.trace_add("write", lambda *_: self.update_preview_zasm())
        self.stempel_var.trace_add("write", lambda *_: self.update_preview_zasm())

        self.update_preview_zasm()
        self.update_preview_visev()

        if cfg_warnung:
            self.after(200, lambda: messagebox.showwarning(
                "Konfiguration", cfg_warnung, parent=self))

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        tabs = ctk.CTkTabview(self, anchor="nw")
        tabs.grid(row=0, column=0, sticky="nsew", padx=PAD, pady=(PAD // 2, PAD))
        self._build_zasm_tab(tabs.add("ZASM"))
        self._build_visev_tab(tabs.add("ViseV"))

    # ---------- ZASM-Tab ----------
    def _build_zasm_tab(self, tab: ctk.CTkFrame) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=2)   # PNR-Eingabe
        tab.grid_rowconfigure(5, weight=3)   # Vorschau

        # Kopfzeile: Projekt + Aktionen
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(4, 8))
        ctk.CTkLabel(top, text="Projekt:").pack(side="left")
        ctk.CTkComboBox(
            top, variable=self.project_var,
            values=sorted(self.daten.zasm.keys()),
            state="readonly", width=170,
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(top, text="TXT generieren",
                      command=self.export_txt_zasm).pack(side="right")
        ctk.CTkButton(top, text="Downloads öffnen", width=140,
                      fg_color="gray70", hover_color="gray60",
                      command=self.open_downloads).pack(side="right", padx=8)

        # Stempel + Zeitstempel
        opts = ctk.CTkFrame(tab)
        opts.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        opts.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(opts, text=f"Stempel ({core.STEMPEL_LEN} Zeichen):").grid(
            row=0, column=0, padx=(PAD, 8), pady=8, sticky="w")
        ctk.CTkEntry(opts, textvariable=self.stempel_var, width=160).grid(
            row=0, column=1, pady=8, sticky="w")
        ctk.CTkButton(opts, text="Alles löschen", width=120,
                      fg_color="gray70", hover_color="gray60",
                      command=self.clear_all_zasm).grid(
            row=0, column=2, padx=PAD, pady=8, sticky="e")

        ctk.CTkLabel(opts, text="Zeitstempel:").grid(
            row=1, column=0, padx=(PAD, 8), pady=(0, 8), sticky="w")
        ts_row = ctk.CTkFrame(opts, fg_color="transparent")
        ts_row.grid(row=1, column=1, columnspan=2, pady=(0, 8), sticky="w")
        ctk.CTkRadioButton(ts_row, text="Live", value="live",
                           variable=self.ts_mode_var).pack(side="left")
        ctk.CTkRadioButton(ts_row, text="Manuell (YYYYMMDDhhmm)", value="manual",
                           variable=self.ts_mode_var).pack(side="left", padx=(16, 8))
        ctk.CTkEntry(ts_row, textvariable=self.ts_manual_var, width=140,
                     placeholder_text="z. B. 202607081200").pack(side="left")

        # PNR-Eingabe
        ctk.CTkLabel(tab, text="PNRs (Excel-Bereich hier einfügen):").grid(
            row=2, column=0, sticky="w")
        self.txt_pnrs = ctk.CTkTextbox(tab, height=140, wrap="none", font=MONO)
        self.txt_pnrs.grid(row=3, column=0, sticky="nsew", pady=(4, 8))
        self._bind_textbox(self.txt_pnrs, self.update_preview_zasm)

        ctk.CTkCheckBox(tab, text="Doppelte PNRs entfernen",
                        variable=self.dedupe_var).grid(
            row=4, column=0, sticky="w", pady=(0, 8))

        # Vorschau
        self.preview_zasm = ctk.CTkTextbox(tab, wrap="none", font=MONO,
                                           state="disabled")
        self.preview_zasm.grid(row=5, column=0, sticky="nsew")

        status = ctk.CTkFrame(tab, fg_color="transparent")
        status.grid(row=6, column=0, sticky="ew", pady=(8, 0))
        self.status_zasm = ctk.CTkLabel(status, text="", anchor="w")
        self.status_zasm.pack(side="left")
        ctk.CTkButton(status, text="Vorschau kopieren", width=150,
                      fg_color="gray70", hover_color="gray60",
                      command=self.copy_preview_zasm).pack(side="right")

    # ---------- ViseV-Tab ----------
    def _build_visev_tab(self, tab: ctk.CTkFrame) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=2)   # VIN-Eingabe
        tab.grid_rowconfigure(4, weight=3)   # Vorschau

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(4, 8))
        ctk.CTkLabel(
            top,
            text=f"Projekt (fix): {core.VISEV_PROJEKT}  •  "
                 f"{len(self.daten.visev_aktionen())} Kampagnen-Aktionen",
        ).pack(side="left")
        ctk.CTkButton(top, text="TXT generieren",
                      command=self.export_txt_visev).pack(side="right")
        ctk.CTkButton(top, text="Downloads öffnen", width=140,
                      fg_color="gray70", hover_color="gray60",
                      command=self.open_downloads).pack(side="right", padx=8)

        ctk.CTkLabel(tab, text="VINs (Excel-Bereich hier einfügen):").grid(
            row=1, column=0, sticky="w")
        self.txt_vins = ctk.CTkTextbox(tab, height=140, wrap="none", font=MONO)
        self.txt_vins.grid(row=2, column=0, sticky="nsew", pady=(4, 8))
        self._bind_textbox(self.txt_vins, self.update_preview_visev)

        opts = ctk.CTkFrame(tab, fg_color="transparent")
        opts.grid(row=3, column=0, sticky="w", pady=(0, 8))
        ctk.CTkCheckBox(opts, text="Header ausgeben (VIN + Campaign Description)",
                        variable=self.visev_header_var,
                        command=self.update_preview_visev).pack(side="left")
        ctk.CTkCheckBox(opts, text="VIN-Duplikate beibehalten",
                        variable=self.visev_keep_dupes_var,
                        command=self.update_preview_visev).pack(
            side="left", padx=(24, 0))

        self.preview_visev = ctk.CTkTextbox(tab, wrap="none", font=MONO,
                                            state="disabled")
        self.preview_visev.grid(row=4, column=0, sticky="nsew")

        status = ctk.CTkFrame(tab, fg_color="transparent")
        status.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        self.status_visev = ctk.CTkLabel(status, text="", anchor="w")
        self.status_visev.pack(side="left")
        ctk.CTkButton(status, text="Vorschau kopieren", width=150,
                      fg_color="gray70", hover_color="gray60",
                      command=self.copy_preview_visev).pack(side="right")

    def _bind_textbox(self, box: ctk.CTkTextbox, callback) -> None:
        """Live-Update bei Tippen, Einfügen und Ausschneiden."""
        box.bind("<KeyRelease>", lambda e: callback())
        # after(1, callback): erst NACH dem Einfügen aktualisieren
        # (die alte Version rief den Callback hier versehentlich sofort auf)
        box.bind("<<Paste>>", lambda e: self.after(1, callback))
        box.bind("<<Cut>>", lambda e: self.after(1, callback))

    # ------------------------------------------------------------------
    # Gemeinsame Helfer
    # ------------------------------------------------------------------
    @staticmethod
    def _set_preview(box: ctk.CTkTextbox, lines: list[str]) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        if lines:
            shown = lines[:PREVIEW_MAX_ZEILEN]
            text = "\n".join(shown)
            if len(lines) > PREVIEW_MAX_ZEILEN:
                text += (f"\n… Vorschau auf {PREVIEW_MAX_ZEILEN} Zeilen gekürzt "
                         f"(Export enthält alle {len(lines)} Zeilen)")
            box.insert("1.0", text)
        box.configure(state="disabled")

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
        self._explorer_select(out_path)

    @staticmethod
    def _explorer_select(path: str) -> None:
        if os.name == "nt":
            try:
                subprocess.run(["explorer", "/select,", path], check=False)
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

    # ------------------------------------------------------------------
    # ZASM: Vorschau & Export
    # ------------------------------------------------------------------
    def _zasm_ts(self) -> tuple[str, str | None]:
        """(Zeitstempel, Hinweistext | None) – Hinweis bei ungültiger manueller Eingabe."""
        if self.ts_mode_var.get() == "manual":
            fehler = core.validate_manual_ts(self.ts_manual_var.get())
            if fehler is None:
                return self.ts_manual_var.get().strip(), None
            return core.now_ts_compact(), "manueller Zeitstempel ungültig – Vorschau nutzt Live-Zeit"
        return core.now_ts_compact(), None

    def _zasm_lines(self) -> tuple[list[str], str | None]:
        projekt = self.project_var.get()
        aktionen = self.daten.zasm_aktionen(projekt)
        pnrs = core.parse_pnrs(self.txt_pnrs.get("1.0", "end"),
                               remove_dupes=self.dedupe_var.get())
        if not aktionen or not pnrs:
            return [], None
        ts, hinweis = self._zasm_ts()
        stempel = self.stempel_var.get()
        return core.build_zasm_lines(aktionen, pnrs, stempel, ts), hinweis

    def update_preview_zasm(self) -> None:
        lines, hinweis = self._zasm_lines()
        self._set_preview(self.preview_zasm, lines)
        if lines:
            ok = all(len(l) == core.LINE_LEN for l in lines)
            text = (f"{len(lines)} Zeilen • "
                    + (f"alle {core.LINE_LEN} Zeichen ok" if ok
                       else f"⚠ Zeilen mit Länge ≠ {core.LINE_LEN}!"))
        else:
            text = "0 Zeilen"
        if hinweis:
            text += f" • ⚠ {hinweis}"
        self.status_zasm.configure(text=text)

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
            messagebox.showwarning("Hinweis", "Vorschau ist leer. Bitte PNRs eingeben.",
                                   parent=self)
            return
        self._export_lines(
            lines, core.zasm_dateiname(self.project_var.get(),
                                       self.stempel_var.get()))

    def copy_preview_zasm(self) -> None:
        self._copy_lines(self._zasm_lines()[0])

    def clear_all_zasm(self) -> None:
        self.txt_pnrs.delete("1.0", "end")
        self.update_preview_zasm()

    # ------------------------------------------------------------------
    # ViseV: Vorschau & Export
    # ------------------------------------------------------------------
    def _visev_lines(self) -> tuple[list[str], int]:
        """(Zeilen, Anzahl VINs)"""
        vins = core.parse_vins(self.txt_vins.get("1.0", "end"),
                               keep_dupes=self.visev_keep_dupes_var.get())
        lines = core.build_visev_lines(
            vins, self.daten.visev_aktionen(),
            include_header=self.visev_header_var.get())
        return lines, len(vins)

    def update_preview_visev(self) -> None:
        lines, n_vins = self._visev_lines()
        self._set_preview(self.preview_visev, lines)
        self.status_visev.configure(
            text=f"{n_vins} VINs • {len(lines)} Zeilen")

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

    # ------------------------------------------------------------------
    # Persistenz
    # ------------------------------------------------------------------
    def on_close(self) -> None:
        self.cfg.update({
            "project": self.project_var.get(),
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
