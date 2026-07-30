#!/usr/bin/env python
"""
MySchoolGN — Générateur de Licences (Outil Distributeur)
==========================================================
Auteur  : GS Hadja Kanfing Dian
Version : 1.0.0

Outil réservé au distributeur pour générer des fichiers de licence
(.lic) à envoyer aux clients après paiement.

Usage :
    python generate_license_gui.py
    ou double-cliquer sur GenerateurLicences.exe
"""
import os
import sys
import json

# Ajouter le dossier courant au path pour trouver license_manager
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from license_manager import (
        generate_activation_file,
        get_machine_id,
        get_machine_id_short,
    )
except ImportError:
    messagebox.showerror(
        "Erreur",
        "license_manager.py est introuvable.\n"
        "Placez generate_license_gui.py dans le même dossier que license_manager.py."
    )
    sys.exit(1)


# ─── Couleurs & styles ────────────────────────────────────────────────────────
BG      = '#ecf0f1'
HDR_BG  = '#1a3a5c'
HDR_FG  = 'white'
ACCENT  = '#27ae60'
BLUE    = '#2980b9'
ORANGE  = '#e67e22'
GREY    = '#7f8c8d'
RED     = '#c0392b'
LABEL_FG = '#2c3e50'
ENTRY_BG = '#ffffff'
ENTRY_RO = '#eaf2ff'


class LicenseGeneratorApp:
    """Fenêtre principale du générateur de licences."""

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("MySchoolGN — Générateur de Licences")
        root.resizable(False, False)
        root.configure(bg=BG)

        W, H = 580, 620
        root.geometry(f"{W}x{H}")
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")

        self._build_ui()

    # ─── Construction de l'interface ─────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._build_body()
        self._build_footer()

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=HDR_BG, height=80)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)

        tk.Label(hdr, text="MySchoolGN",
                 font=('Arial', 22, 'bold'), bg=HDR_BG, fg=HDR_FG).place(
            relx=0.5, rely=0.32, anchor='center')
        tk.Label(hdr,
                 text="Générateur de Licences — Réservé au Distributeur",
                 font=('Arial', 9, 'italic'), bg=HDR_BG, fg='#aed6f1').place(
            relx=0.5, rely=0.70, anchor='center')

    def _build_body(self):
        body = tk.Frame(self.root, bg=BG, padx=26, pady=20)
        body.pack(fill='both', expand=True)

        # ── Section informations client ──
        client_frm = tk.LabelFrame(
            body, text="  Informations du client  ",
            bg=BG, font=('Arial', 9, 'bold'), fg=HDR_BG,
            padx=14, pady=12, relief='groove')
        client_frm.pack(fill='x', pady=(0, 14))

        # ID Machine
        tk.Label(client_frm, text="ID Machine du client :",
                 font=('Arial', 9, 'bold'), bg=BG, fg=LABEL_FG).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 3))
        self.mid_var = tk.StringVar()
        tk.Entry(client_frm, textvariable=self.mid_var,
                 font=('Courier', 10), width=44,
                 relief='flat', bd=1, bg=ENTRY_BG, fg=HDR_BG).grid(
            row=1, column=0, columnspan=2, sticky='ew',
            ipady=5, pady=(0, 12))

        # Nom de l'école
        tk.Label(client_frm, text="Nom de l'école :",
                 font=('Arial', 9, 'bold'), bg=BG, fg=LABEL_FG).grid(
            row=2, column=0, columnspan=2, sticky='w', pady=(0, 3))
        self.school_var = tk.StringVar()
        tk.Entry(client_frm, textvariable=self.school_var,
                 font=('Arial', 10), width=44,
                 relief='flat', bd=1, bg=ENTRY_BG).grid(
            row=3, column=0, columnspan=2, sticky='ew',
            ipady=5, pady=(0, 12))

        # Édition + Durée (côte à côte)
        left = tk.Frame(client_frm, bg=BG)
        left.grid(row=4, column=0, sticky='w')
        right = tk.Frame(client_frm, bg=BG)
        right.grid(row=4, column=1, sticky='w', padx=(20, 0))

        tk.Label(left, text="Édition :",
                 font=('Arial', 9, 'bold'), bg=BG, fg=LABEL_FG).pack(anchor='w')
        self.edition_var = tk.StringVar(value='Standard')
        ttk.Combobox(left, textvariable=self.edition_var,
                     values=['Standard', 'Pro', 'Enterprise'],
                     state='readonly', width=16,
                     font=('Arial', 10)).pack(anchor='w', pady=(4, 0))

        tk.Label(right, text="Durée (jours) :",
                 font=('Arial', 9, 'bold'), bg=BG, fg=LABEL_FG).pack(anchor='w')
        days_row = tk.Frame(right, bg=BG)
        days_row.pack(anchor='w', pady=(4, 0))
        self.days_var = tk.StringVar(value='365')
        tk.Entry(days_row, textvariable=self.days_var,
                 font=('Arial', 10), width=7,
                 relief='flat', bd=1, bg=ENTRY_BG).pack(side='left', ipady=4)
        tk.Label(days_row, text=" jours  (365 = 1 an)",
                 font=('Arial', 8), bg=BG, fg='#888').pack(side='left')

        client_frm.columnconfigure(0, weight=1)
        client_frm.columnconfigure(1, weight=1)

        # ── Section fichier de sortie ──
        out_frm = tk.LabelFrame(
            body, text="  Fichier de licence à générer  ",
            bg=BG, font=('Arial', 9, 'bold'), fg=HDR_BG,
            padx=14, pady=10, relief='groove')
        out_frm.pack(fill='x', pady=(0, 14))

        self.out_var = tk.StringVar(value="")
        out_row = tk.Frame(out_frm, bg=BG)
        out_row.pack(fill='x')
        tk.Entry(out_row, textvariable=self.out_var,
                 font=('Arial', 9), state='readonly',
                 readonlybackground='#f9f9f9',
                 relief='flat', bd=1).pack(
            side='left', fill='x', expand=True, ipady=5)

        def _browse_out():
            mid_value = self.mid_var.get().strip()
            mid_short = 'DISTRIBUTABLE' if mid_value == '*' else (mid_value[:8] or 'client')
            default_name = f"licence_{mid_short}.lic"
            p = filedialog.asksaveasfilename(
                title="Enregistrer le fichier de licence",
                initialfile=default_name,
                defaultextension=".lic",
                filetypes=[("Fichier licence", "*.lic"),
                           ("Tous les fichiers", "*.*")])
            if p:
                self.out_var.set(p)

        tk.Button(out_row, text="  Choisir…  ", command=_browse_out,
                  font=('Arial', 9), bg=GREY, fg='white',
                  relief='flat', padx=6, pady=5, cursor='hand2').pack(
            side='left', padx=(6, 0))
        tk.Label(out_frm,
                 text="Laissez vide pour enregistrer dans le dossier courant "
                      "(licence_<ID>.lic).",
                 font=('Arial', 8), bg=BG, fg='#888').pack(
            anchor='w', pady=(5, 0))

        # ── Résultat ──
        self.result_var = tk.StringVar(value="")
        self.result_lbl = tk.Label(body, textvariable=self.result_var,
                                   font=('Arial', 9), bg=BG, fg=ACCENT,
                                   wraplength=520, justify='left')
        self.result_lbl.pack(anchor='w', pady=(0, 10))

        # ── Bouton Générer ──
        tk.Button(body,
                  text="      Générer le fichier de licence      ",
                  command=self._generate,
                  font=('Arial', 12, 'bold'), bg=ACCENT, fg='white',
                  relief='flat', padx=14, pady=10,
                  cursor='hand2').pack(anchor='center')

    def _build_footer(self):
        footer = tk.Frame(self.root, bg='#d5d8dc', height=36)
        footer.pack(fill='x', side='bottom')
        footer.pack_propagate(False)
        try:
            my_mid = get_machine_id()
            short = my_mid[:8] + "…  (complet : " + my_mid + ")"
        except Exception:
            short = "N/A"
        tk.Label(footer,
                 text=f"Machine distributeur : {short}",
                 font=('Arial', 7), bg='#d5d8dc', fg='#555').place(
            relx=0.5, rely=0.5, anchor='center')

    # ─── Génération ──────────────────────────────────────────────────────────
    def _generate(self):
        mid    = self.mid_var.get().strip()
        school = self.school_var.get().strip()
        edition = self.edition_var.get().strip() or 'Standard'
        days_str = self.days_var.get().strip()
        out_path = self.out_var.get().strip()

        # Validation des champs
        if not mid:
            messagebox.showwarning(
                "Champ manquant",
                "Veuillez saisir l'identifiant machine du client.")
            return
        if mid != '*' and len(mid) < 8:
            messagebox.showwarning(
                "Identifiant invalide",
                "L'identifiant machine doit faire au moins 8 caractères.\n"
                "Utilisez * uniquement pour une licence distribuable.\n"
                "Demandez-le au client via son application MySchoolGN.")
            return
        if not school:
            messagebox.showwarning(
                "Champ manquant",
                "Veuillez saisir le nom de l'école.")
            return
        try:
            days = int(days_str)
            if not (1 <= days <= 3650):
                raise ValueError()
        except ValueError:
            messagebox.showwarning(
                "Durée invalide",
                "La durée doit être un nombre entier entre 1 et 3650 jours.")
            return

        # Génération du fichier de licence
        try:
            lic_data = generate_activation_file(mid, days, school, edition)
        except Exception as exc:
            messagebox.showerror("Erreur de génération",
                                 f"Impossible de générer la licence :\n{exc}")
            return

        # Chemin de sortie par défaut
        if not out_path:
            mid_short = 'DISTRIBUTABLE' if mid == '*' else mid[:8]
            out_path = os.path.join(BASE, f"licence_{mid_short}.lic")
            self.out_var.set(out_path)

        # Écriture du fichier
        try:
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(lic_data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            messagebox.showerror("Erreur d'écriture",
                                 f"Impossible d'écrire le fichier :\n{exc}")
            return

        # Afficher le succès
        from datetime import datetime, timedelta
        exp_date = (datetime.utcnow() + timedelta(days=days)).strftime('%d/%m/%Y')
        filename = os.path.basename(out_path)
        self.result_var.set(
            f"Licence générée : {filename}\n"
            f"   École : {school}  |  Édition : {edition}  "
            f"|  Expire le : {exp_date}")
        self.result_lbl.config(fg=ACCENT)

        messagebox.showinfo(
            "Licence générée avec succès",
            f"Le fichier de licence a été créé !\n\n"
            f"Fichier  : {filename}\n"
            f"École    : {school}\n"
            f"Édition  : {edition}\n"
            f"Durée    : {days} jour(s)\n"
            f"Expire   : {exp_date}\n\n"
            f"Envoyez ce fichier au client par email ou clé USB.\n"
            f"Le client l'importera dans MySchoolGN pour activer sa licence.")


# ─── Point d'entrée ───────────────────────────────────────────────────────────
def main():
    root = tk.Tk()
    LicenseGeneratorApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
