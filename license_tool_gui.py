#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MySchoolGN - Outil de Gestion des Licences (Développeur)
=========================================================
Auteur  : GS Hadja Kanfing Dian
Usage   : Réservé au développeur — génère les fichiers .lic pour les clients

Fonctions :
  - Générer une licence pour une machine client
  - Voir toutes les licences émises
  - Copier l'ID machine du client
"""

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Ajouter le dossier du script au path
BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

import license_manager as lm

# ─── Couleurs ─────────────────────────────────────────────────────────────────
BG       = "#1a2744"
BG2      = "#f4f6fb"
ACCENT   = "#f5a623"
WHITE    = "#ffffff"
BLUE     = "#2563eb"
GREEN    = "#16a34a"
RED      = "#dc2626"
GRAY     = "#6b7280"
DARK     = "#111827"
CARD     = "#ffffff"
BORDER   = "#e5e7eb"

FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_H2    = ("Segoe UI", 12, "bold")
FONT_BODY  = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_MONO  = ("Consolas", 10)

# ─── Fichier journal des licences émises ──────────────────────────────────────
LICENSES_LOG = BASE / "licenses_emises.json"

def load_licenses_log() -> list:
    if LICENSES_LOG.exists():
        try:
            return json.loads(LICENSES_LOG.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_license_to_log(entry: dict):
    records = load_licenses_log()
    records.append(entry)
    LICENSES_LOG.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


# ─── Application principale ───────────────────────────────────────────────────
class LicenseToolApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MySchoolGN — Gestionnaire de Licences  |  GS Hadja Kanfing Dian")
        self.configure(bg=BG)
        self.resizable(True, True)

        w, h = 860, 650
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.minsize(800, 580)

        ico = BASE / "myschool.ico"
        if ico.exists():
            try: self.iconbitmap(str(ico))
            except Exception: pass

        self._build()
        self._refresh_log()

    # ── Construction UI ───────────────────────────────────────────────────────
    def _build(self):
        # ── En-tête
        hdr = tk.Frame(self, bg=BG, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="MySchoolGN", font=("Segoe UI", 20, "bold"),
                 fg=WHITE, bg=BG).pack(side="left", padx=20)
        tk.Label(hdr, text="Gestionnaire de Licences", font=("Segoe UI", 11),
                 fg="#94a3b8", bg=BG).pack(side="left", padx=4)
        tk.Label(hdr, text="GS Hadja Kanfing Dian", font=("Segoe UI", 10, "italic"),
                 fg=ACCENT, bg=BG).pack(side="right", padx=20)

        tk.Frame(self, bg=ACCENT, height=3).pack(fill="x")

        # ── Corps principal (2 panneaux)
        main = tk.Frame(self, bg=BG2)
        main.pack(fill="both", expand=True)

        # Panneau gauche — Génération
        left = tk.Frame(main, bg=CARD, bd=0, relief="flat", width=380)
        left.pack(side="left", fill="y", padx=(16, 8), pady=16)
        left.pack_propagate(False)
        self._build_form(left)

        # Panneau droit — Historique
        right = tk.Frame(main, bg=CARD, bd=0, relief="flat")
        right.pack(side="left", fill="both", expand=True, padx=(0, 16), pady=16)
        self._build_log(right)

    def _section(self, parent, title):
        tk.Label(parent, text=title, font=FONT_H2, fg=DARK, bg=CARD,
                 anchor="w").pack(fill="x", padx=16, pady=(16, 4))
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=16, pady=(0, 10))

    def _field(self, parent, label, var=None, placeholder="", width=30, combo=None):
        f = tk.Frame(parent, bg=CARD)
        f.pack(fill="x", padx=16, pady=4)
        tk.Label(f, text=label, font=FONT_SMALL, fg=GRAY, bg=CARD, anchor="w",
                 width=18).pack(side="left")
        if combo:
            cb = ttk.Combobox(f, textvariable=var, values=combo, state="readonly",
                               font=FONT_BODY, width=width-2)
            cb.pack(side="left", fill="x", expand=True)
            return cb
        else:
            e = tk.Entry(f, textvariable=var, font=FONT_BODY, width=width,
                         bg="#f9fafb", relief="solid", bd=1)
            e.pack(side="left", fill="x", expand=True, ipady=4)
            if placeholder and var:
                var.set(placeholder)
                def on_focus_in(ev, v=var, p=placeholder):
                    if v.get() == p: v.set("")
                def on_focus_out(ev, v=var, p=placeholder):
                    if not v.get(): v.set(p)
                e.bind("<FocusIn>", on_focus_in)
                e.bind("<FocusOut>", on_focus_out)
            return e

    # ── Formulaire de génération ──────────────────────────────────────────────
    def _build_form(self, parent):
        self._section(parent, "Générer une Licence")

        self.v_mid      = tk.StringVar()
        self.v_school   = tk.StringVar()
        self.v_days     = tk.StringVar(value="365")
        self.v_edition  = tk.StringVar(value="Standard")
        self.v_contact  = tk.StringVar()

        self._field(parent, "ID Machine *", self.v_mid,       "Coller l'ID du client")
        self._field(parent, "Nom de l'école *", self.v_school,"Ex: Ecole Al-Nour")
        self._field(parent, "Contact / Tél.", self.v_contact, "Ex: +224 6XX XXX XXX")
        self._field(parent, "Durée (jours) *", self.v_days)
        self._field(parent, "Édition", self.v_edition, combo=[
            "Standard", "Premium", "Entreprise"
        ])

        # Bouton Générer
        tk.Button(
            parent, text="⚡  Générer la Licence",
            font=("Segoe UI", 11, "bold"),
            bg=ACCENT, fg=DARK,
            activebackground="#e09010",
            relief="flat", cursor="hand2",
            padx=10, pady=10,
            command=self._generate
        ).pack(fill="x", padx=16, pady=(16, 4))

        # Bouton Copier ID machine courant
        tk.Button(
            parent, text="📋  Copier mon ID Machine",
            font=FONT_SMALL,
            bg="#e0e7ef", fg=DARK,
            activebackground="#c8d4e0",
            relief="flat", cursor="hand2",
            padx=6, pady=6,
            command=self._copy_my_id
        ).pack(fill="x", padx=16, pady=2)

        # Résultat
        self._section(parent, "Résultat")
        self.result_text = tk.Text(parent, height=7, font=FONT_MONO,
                                    bg="#f0f4ff", fg=DARK, relief="solid", bd=1,
                                    wrap="word", state="disabled")
        self.result_text.pack(fill="x", padx=16, pady=(0, 4))

        tk.Button(
            parent, text="💾  Enregistrer le fichier .lic",
            font=FONT_SMALL,
            bg=GREEN, fg=WHITE,
            activebackground="#15803d",
            relief="flat", cursor="hand2",
            padx=6, pady=6,
            command=self._save_lic
        ).pack(fill="x", padx=16, pady=(0, 16))

        self._last_lic_data = None
        self._last_filename = None

    # ── Historique ────────────────────────────────────────────────────────────
    def _build_log(self, parent):
        self._section(parent, "Licences Émises")

        # Tableau
        cols = ("École", "Édition", "Durée", "Émise le", "Expire le", "Machine (court)")
        tree_frame = tk.Frame(parent, bg=CARD)
        tree_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        style = ttk.Style()
        style.configure("License.Treeview", rowheight=26, font=FONT_SMALL,
                         background=CARD, fieldbackground=CARD)
        style.configure("License.Treeview.Heading", font=("Segoe UI", 9, "bold"),
                         background=BG, foreground=WHITE)
        style.map("License.Treeview", background=[("selected", "#dbeafe")])

        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  style="License.Treeview", selectmode="browse")
        widths = [160, 90, 70, 90, 90, 130]
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        # Barre du bas
        bot = tk.Frame(parent, bg=CARD)
        bot.pack(fill="x", padx=16, pady=(0, 16))
        self.lbl_total = tk.Label(bot, text="0 licences émises",
                                   font=FONT_SMALL, fg=GRAY, bg=CARD)
        self.lbl_total.pack(side="left")
        tk.Button(bot, text="🔄 Actualiser", font=FONT_SMALL,
                   bg="#e0e7ef", fg=DARK, relief="flat", cursor="hand2",
                   padx=8, pady=4, command=self._refresh_log).pack(side="right")
        tk.Button(bot, text="🗑 Effacer journal", font=FONT_SMALL,
                   bg="#fee2e2", fg=RED, relief="flat", cursor="hand2",
                   padx=8, pady=4, command=self._clear_log).pack(side="right", padx=6)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _generate(self):
        mid     = self.v_mid.get().strip()
        school  = self.v_school.get().strip()
        contact = self.v_contact.get().strip()
        edition = self.v_edition.get()

        try:
            days = int(self.v_days.get().strip())
            if days <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Erreur", "La durée doit être un nombre de jours positif.")
            return

        placeholders = {"Coller l'ID du client", "Ex: Ecole Al-Nour", "Ex: +224 6XX XXX XXX"}
        if not mid or mid in placeholders:
            messagebox.showerror("Erreur", "Veuillez saisir l'ID Machine du client.")
            return
        if mid != "*" and len(mid) < 8:
            messagebox.showerror("Erreur", "L'ID Machine doit faire au moins 8 caractères, ou être * pour une licence distribuable.")
            return
        if not school or school in placeholders:
            messagebox.showerror("Erreur", "Veuillez saisir le nom de l'école.")
            return

        # Générer
        lic_data = lm.generate_activation_file(mid, days, school, edition)
        now = datetime.now()
        exp = now + timedelta(days=days)

        self._last_lic_data = lic_data
        mid_label = "DISTRIBUTABLE" if mid == "*" else mid[:8]
        self._last_filename = f"license_{mid_label}_{school[:10].replace(' ','_')}.lic"

        # Afficher
        result_lines = [
            f"✓ Licence générée avec succès",
            f"",
            f"École    : {school}",
            f"Édition  : {edition}",
            f"Durée    : {days} jours",
            f"Émise le : {now.strftime('%d/%m/%Y')}",
            f"Expire   : {exp.strftime('%d/%m/%Y')}",
            f"Machine  : {'toutes les machines' if mid == '*' else mid[:16] + '...'}",
            f"Fichier  : {self._last_filename}",
        ]
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("end", "\n".join(result_lines))
        self.result_text.configure(state="disabled")

        # Enregistrer dans le journal
        save_license_to_log({
            "school": school,
            "edition": edition,
            "days": days,
            "contact": contact,
            "issued": now.strftime("%Y-%m-%d"),
            "expires": exp.strftime("%Y-%m-%d"),
            "machine_short": "DISTRIBUTABLE" if mid == "*" else mid[:16],
            "filename": self._last_filename,
        })
        self._refresh_log()

    def _save_lic(self):
        if not self._last_lic_data:
            messagebox.showwarning("Attention", "Générez d'abord une licence.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".lic",
            filetypes=[("Fichier licence", "*.lic"), ("JSON", "*.json")],
            initialfile=self._last_filename or "license.lic",
            title="Enregistrer la licence"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._last_lic_data, f, indent=2)
            messagebox.showinfo("Succès",
                f"Fichier enregistré :\n{path}\n\nEnvoyez-le au client par email ou WhatsApp.")

    def _copy_my_id(self):
        mid = lm.get_machine_id()
        self.clipboard_clear()
        self.clipboard_append(mid)
        messagebox.showinfo("Copié",
            f"Votre ID Machine a été copié :\n\n{mid}\n\n"
            "(Ce PC — développeur GS Hadja Kanfing Dian)")

    def _refresh_log(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        records = load_licenses_log()
        for r in reversed(records):  # plus récent en premier
            self.tree.insert("", "end", values=(
                r.get("school", ""),
                r.get("edition", ""),
                f"{r.get('days', '')}j",
                r.get("issued", ""),
                r.get("expires", ""),
                r.get("machine_short", "")[:16] + "...",
            ))
        n = len(records)
        self.lbl_total.configure(text=f"{n} licence{'s' if n > 1 else ''} émise{'s' if n > 1 else ''}")

    def _clear_log(self):
        if messagebox.askyesno("Confirmer", "Effacer tout le journal des licences ?"):
            LICENSES_LOG.write_text("[]", encoding="utf-8")
            self._refresh_log()


# ─── Point d'entrée ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = LicenseToolApp()
    app.mainloop()
