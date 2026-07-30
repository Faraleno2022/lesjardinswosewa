#!/usr/bin/env python
"""Diagnostic des notes pour l'école Espoir d'Afrique"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from notes.models import ClasseNote, MatiereNote, NoteMensuelle, CompositionNote
from eleves.models import Eleve, Classe as ClasseEleve

print("=" * 80)
print("DIAGNOSTIC - ÉCOLE ESPOIR D'AFRIQUE")
print("=" * 80)

# 1. Vérifier les ClasseNote
print("\n=== 1. CLASSES DANS LE SYSTÈME NOTES (ClasseNote) ===")
classes_notes = ClasseNote.objects.filter(ecole__nom__icontains='espoir')
if classes_notes.exists():
    for c in classes_notes:
        print(f"  ID:{c.id} | {c.nom} | Ecole: {c.ecole} | Actif: {c.actif}")
else:
    print("  ❌ AUCUNE ClasseNote trouvée pour cette école!")

# 2. Vérifier les ClasseEleve
print("\n=== 2. CLASSES DANS LE SYSTÈME ÉLÈVES (ClasseEleve) ===")
classes_eleves = ClasseEleve.objects.filter(ecole__nom__icontains='espoir')
if classes_eleves.exists():
    for c in classes_eleves:
        eleves_count = Eleve.objects.filter(classe=c, statut='ACTIF').count()
        print(f"  ID:{c.id} | {c.nom} | Ecole: {c.ecole} | Élèves: {eleves_count}")
else:
    print("  ❌ AUCUNE ClasseEleve trouvée pour cette école!")

# 3. Vérifier les matières
print("\n=== 3. MATIÈRES PAR CLASSE ===")
for cn in classes_notes:
    matieres = MatiereNote.objects.filter(classe=cn, actif=True)
    print(f"  {cn.nom}: {matieres.count()} matières actives")
    for m in matieres[:5]:
        print(f"    - {m.nom} (ID: {m.id})")
    if matieres.count() > 5:
        print(f"    ... et {matieres.count() - 5} autres")

# 4. Vérifier les élèves
print("\n=== 4. ÉLÈVES AVEC MATRICULE ESP ===")
eleves = Eleve.objects.filter(matricule__startswith='ESP', statut='ACTIF')
for e in eleves[:10]:
    print(f"  {e.matricule}: {e.prenom} {e.nom} | Classe: {e.classe}")

# 5. Vérifier les notes
print("\n=== 5. NOTES SAISIES ===")
for e in eleves[:10]:
    notes_mensuelles = NoteMensuelle.objects.filter(eleve=e)
    notes_compo = CompositionNote.objects.filter(eleve=e)
    print(f"  {e.matricule}: {notes_mensuelles.count()} notes mensuelles, {notes_compo.count()} compositions")
    
    if notes_mensuelles.exists():
        for n in notes_mensuelles[:3]:
            print(f"    - {n.matiere.nom} ({n.periode}): {n.note}")

# 6. Vérifier la correspondance des classes
print("\n=== 6. CORRESPONDANCE CLASSES ===")
for cn in classes_notes:
    ce = ClasseEleve.objects.filter(
        nom=cn.nom,
        annee_scolaire=cn.annee_scolaire,
        ecole=cn.ecole
    ).first()
    
    if ce:
        print(f"  ✅ {cn.nom}: ClasseNote ID:{cn.id} <-> ClasseEleve ID:{ce.id}")
    else:
        print(f"  ❌ {cn.nom}: PAS DE CORRESPONDANCE!")
        # Chercher des correspondances partielles
        ce_similaires = ClasseEleve.objects.filter(ecole=cn.ecole)
        if ce_similaires.exists():
            print(f"     Classes disponibles dans cette école:")
            for ces in ce_similaires:
                print(f"       - '{ces.nom}' (ID: {ces.id})")

print("\n" + "=" * 80)
print("FIN DU DIAGNOSTIC")
print("=" * 80)
