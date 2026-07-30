#!/usr/bin/env python
"""
Script pour identifier et corriger le formatage des montants dans tous les templates
"""

import os
import re
import glob

def find_and_fix_amount_formatting():
    """Trouve et corrige le formatage des montants dans tous les templates"""
    
    print("💰 Correction du formatage des montants dans les templates...")
    print("=" * 60)
    
    # Répertoire des templates
    templates_dir = r"c:\Users\faral\Desktop\GS HADJA_KANFING_DIANÉ\templates"
    
    # Patterns à rechercher et corriger
    patterns_to_fix = [
        # Montants avec floatformat:0 sans intcomma
        (r'(\{\{\s*[^}]+\|floatformat:0)\s*\}\}(?!\|intcomma)', r'\1|intcomma }}'),
        
        # Montants directs sans formatage (ex: {{ montant }} GNF)
        (r'(\{\{\s*[^}]*montant[^}]*)\s*\}\}\s*(GNF)', r'\1|floatformat:0|intcomma }} \2'),
        
        # Autres patterns de montants
        (r'(\{\{\s*[^}]*total[^}]*)\s*\}\}\s*(GNF)(?![^{]*intcomma)', r'\1|floatformat:0|intcomma }} \2'),
        (r'(\{\{\s*[^}]*solde[^}]*)\s*\}\}\s*(GNF)(?![^{]*intcomma)', r'\1|floatformat:0|intcomma }} \2'),
        (r'(\{\{\s*[^}]*prix[^}]*)\s*\}\}\s*(GNF)(?![^{]*intcomma)', r'\1|floatformat:0|intcomma }} \2'),
    ]
    
    # Fichiers modifiés
    files_modified = []
    total_replacements = 0
    
    # Parcourir tous les fichiers HTML
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    original_content = content
                    file_replacements = 0
                    
                    # Appliquer chaque pattern
                    for pattern, replacement in patterns_to_fix:
                        matches = re.findall(pattern, content)
                        if matches:
                            content = re.sub(pattern, replacement, content)
                            file_replacements += len(matches)
                    
                    # Si des modifications ont été faites
                    if content != original_content:
                        # Ajouter {% load humanize %} si nécessaire
                        if '|intcomma' in content and '{% load humanize %}' not in content:
                            # Trouver la ligne après {% load static %} ou {% extends %}
                            lines = content.split('\n')
                            insert_line = 0
                            
                            for i, line in enumerate(lines):
                                if '{% load static %}' in line:
                                    insert_line = i + 1
                                    break
                                elif '{% extends' in line and insert_line == 0:
                                    insert_line = i + 1
                            
                            if insert_line > 0:
                                lines.insert(insert_line, '{% load humanize %}')
                                content = '\n'.join(lines)
                        
                        # Sauvegarder le fichier modifié
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        
                        files_modified.append(file_path)
                        total_replacements += file_replacements
                        
                        print(f"✅ {os.path.relpath(file_path, templates_dir)}: {file_replacements} correction(s)")
                
                except Exception as e:
                    print(f"❌ Erreur avec {file_path}: {e}")
    
    print(f"\n📊 Résumé:")
    print(f"   📁 Fichiers modifiés: {len(files_modified)}")
    print(f"   🔧 Total corrections: {total_replacements}")
    
    if files_modified:
        print(f"\n📋 Fichiers modifiés:")
        for file_path in files_modified:
            print(f"   - {os.path.relpath(file_path, templates_dir)}")
    
    print(f"\n✅ Formatage des montants terminé!")

def manual_fixes():
    """Corrections manuelles spécifiques"""
    
    print("\n🔧 Application de corrections manuelles spécifiques...")
    
    # Corrections spécifiques pour certains templates
    specific_fixes = [
        {
            'file': r'templates\paiements\tableau_bord.html',
            'fixes': [
                ('{{ stats.nombre_paiements_mois }}', '{{ stats.nombre_paiements_mois|intcomma }}'),
                ('{{ stats.eleves_en_retard }}', '{{ stats.eleves_en_retard|intcomma }}'),
                ('{{ stats.paiements_en_attente }}', '{{ stats.paiements_en_attente|intcomma }}'),
                ('{{ paiement.montant|floatformat:0 }}', '{{ paiement.montant|floatformat:0|intcomma }}'),
                ('{{ echeancier.solde_restant|floatformat:0 }}', '{{ echeancier.solde_restant|floatformat:0|intcomma }}'),
            ]
        },
        {
            'file': r'templates\paiements\liste_paiements.html',
            'fixes': [
                ('{{ stats.total_paiements }}', '{{ stats.total_paiements|intcomma }}'),
                ('{{ stats.montant_total|floatformat:0 }}', '{{ stats.montant_total|floatformat:0|intcomma }}'),
                ('{{ stats.en_attente }}', '{{ stats.en_attente|intcomma }}'),
                ('{{ stats.ce_mois }}', '{{ stats.ce_mois|intcomma }}'),
                ('{{ paiement.montant|floatformat:0 }}', '{{ paiement.montant|floatformat:0|intcomma }}'),
            ]
        },
        {
            'file': r'templates\paiements\echeancier_eleve.html',
            'fixes': [
                ('{{ echeancier.total_du|floatformat:0 }}', '{{ echeancier.total_du|floatformat:0|intcomma }}'),
                ('{{ echeancier.total_paye|floatformat:0 }}', '{{ echeancier.total_paye|floatformat:0|intcomma }}'),
                ('{{ echeancier.solde_restant|floatformat:0 }}', '{{ echeancier.solde_restant|floatformat:0|intcomma }}'),
                ('{{ echeancier.frais_inscription_du|floatformat:0 }}', '{{ echeancier.frais_inscription_du|floatformat:0|intcomma }}'),
                ('{{ echeancier.frais_inscription_paye|floatformat:0 }}', '{{ echeancier.frais_inscription_paye|floatformat:0|intcomma }}'),
                ('{{ echeancier.tranche_1_due|floatformat:0 }}', '{{ echeancier.tranche_1_due|floatformat:0|intcomma }}'),
                ('{{ echeancier.tranche_1_payee|floatformat:0 }}', '{{ echeancier.tranche_1_payee|floatformat:0|intcomma }}'),
                ('{{ echeancier.tranche_2_due|floatformat:0 }}', '{{ echeancier.tranche_2_due|floatformat:0|intcomma }}'),
                ('{{ echeancier.tranche_2_payee|floatformat:0 }}', '{{ echeancier.tranche_2_payee|floatformat:0|intcomma }}'),
                ('{{ echeancier.tranche_3_due|floatformat:0 }}', '{{ echeancier.tranche_3_due|floatformat:0|intcomma }}'),
                ('{{ echeancier.tranche_3_payee|floatformat:0 }}', '{{ echeancier.tranche_3_payee|floatformat:0|intcomma }}'),
                ('{{ paiement.montant|floatformat:0 }}', '{{ paiement.montant|floatformat:0|intcomma }}'),
            ]
        }
    ]
    
    base_dir = r"c:\Users\faral\Desktop\GS HADJA_KANFING_DIANÉ"
    
    for template_info in specific_fixes:
        file_path = os.path.join(base_dir, template_info['file'])
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                fixes_applied = 0
                
                for old_text, new_text in template_info['fixes']:
                    if old_text in content and new_text not in content:
                        content = content.replace(old_text, new_text)
                        fixes_applied += 1
                
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    print(f"✅ {template_info['file']}: {fixes_applied} correction(s) appliquée(s)")
                else:
                    print(f"ℹ️  {template_info['file']}: Déjà à jour")
            
            except Exception as e:
                print(f"❌ Erreur avec {file_path}: {e}")
        else:
            print(f"⚠️  Fichier non trouvé: {file_path}")

if __name__ == '__main__':
    find_and_fix_amount_formatting()
    manual_fixes()
