"""
Module d'importation de notes depuis fichiers Excel/CSV
Supporte: Notes mensuelles, Compositions, Évaluations
"""
import pandas as pd
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.contrib import messages
from .models import NoteEleve, NoteMensuelle, CompositionNote, MatiereNote, Evaluation, ClasseNote
from eleves.models import Eleve


class ImportNotesError(Exception):
    """Erreur lors de l'importation"""
    pass


class ImportNotesValidator:
    """Validateur pour l'importation de notes"""
    
    def __init__(self, df, classe_id=None, matiere_id=None, evaluation_id=None, type_import='MENSUELLE'):
        self.df = df
        self.classe_id = classe_id
        self.matiere_id = matiere_id
        self.evaluation_id = evaluation_id
        self.type_import = type_import
        self.erreurs = []
        self.avertissements = []
    
    def valider(self):
        """Valide le fichier importé"""
        # Vérifier les colonnes requises (flexible avec la casse)
        colonnes_requises = self._get_colonnes_requises()
        colonnes_fichier = list(self.df.columns)
        
        # Fonction de normalisation plus robuste
        def normaliser_colonne(col):
            col = col.strip()
            # Gérer les accents
            col = col.replace('é', 'e').replace('è', 'e').replace('ê', 'e')
            col = col.replace('à', 'a').replace('â', 'a').replace('ä', 'a')
            col = col.replace('ö', 'o').replace('ô', 'o')
            col = col.replace('ù', 'u').replace('û', 'u')
            col = col.replace('ç', 'c')
            # Mettre en minuscules puis capitaliser chaque mot
            return ' '.join(word.capitalize() for word in col.lower().split())
        
        # Normaliser les colonnes pour la comparaison
        colonnes_fichier_normalisees = [normaliser_colonne(col) for col in colonnes_fichier]
        colonnes_requises_normalisees = [normaliser_colonne(col) for col in colonnes_requises]
        
        colonnes_manquantes = set(colonnes_requises_normalisees) - set(colonnes_fichier_normalisees)
        
        if colonnes_manquantes:
            # Créer un mapping des colonnes suggérées
            suggestions = {}
            for requise in colonnes_manquantes:
                for i, existante in enumerate(colonnes_fichier_normalisees):
                    if existante == requise:
                        suggestions[requise] = colonnes_fichier[i]
                        break
            
            message = f"Colonnes manquantes: {', '.join(colonnes_manquantes)}"
            if suggestions:
                message += f"\nColonnes suggérées: {', '.join([f'{k}→{v}' for k, v in suggestions.items()])}"
            else:
                message += f"\nColonnes attendues: {', '.join(colonnes_requises)}"
            
            raise ImportNotesError(message)
        
        # Créer un mapping des colonnes pour le traitement
        self.colonnes_mapping = {}
        for requise in colonnes_requises_normalisees:
            for i, existante in enumerate(colonnes_fichier_normalisees):
                if existante == requise:
                    self.colonnes_mapping[colonnes_requises[colonnes_requises_normalisees.index(requise)]] = colonnes_fichier[i]
                    break
        
        # Valider chaque ligne
        for index, row in self.df.iterrows():
            self._valider_ligne(index + 2, row)  # +2 car Excel commence à 1 et il y a l'en-tête
        
        return len(self.erreurs) == 0
    
    def _get_colonnes_requises(self):
        """Retourne les colonnes requises selon le type d'import"""
        colonnes_base = ['Matricule', 'Prénom', 'Nom']
        
        if self.type_import == 'MENSUELLE':
            return colonnes_base + ['Note', 'Absent']
        elif self.type_import == 'COMPOSITION':
            return colonnes_base + ['Note', 'Absent']
        elif self.type_import == 'EVALUATION':
            return colonnes_base + ['Note', 'Absent']
        
        return colonnes_base
    
    def _valider_ligne(self, numero_ligne, row):
        """Valide une ligne du fichier"""
        # Utiliser le mapping des colonnes si disponible
        matricule_col = getattr(self, 'colonnes_mapping', {}).get('Matricule', 'Matricule')
        absent_col = getattr(self, 'colonnes_mapping', {}).get('Absent', 'Absent')
        note_col = getattr(self, 'colonnes_mapping', {}).get('Note', 'Note')
        
        # Vérifier le matricule
        matricule = str(row.get(matricule_col, '')).strip()
        if not matricule or pd.isna(row.get(matricule_col, '')):
            self.erreurs.append(f"Ligne {numero_ligne}: Matricule manquant")
            return
        
        # Vérifier que l'élève existe
        try:
            eleve = Eleve.objects.get(matricule=matricule)
        except Eleve.DoesNotExist:
            self.erreurs.append(f"Ligne {numero_ligne}: Élève avec matricule '{matricule}' introuvable")
            return
        
        # Vérifier la note
        absent = str(row.get(absent_col, 'NON')).strip().upper() in ['OUI', 'O', 'YES', 'Y', '1', 'TRUE']
        
        if not absent:
            note = row.get(note_col)
            if pd.isna(note) or note == '':
                self.avertissements.append(f"Ligne {numero_ligne}: Note manquante pour {eleve}")
            else:
                try:
                    note_decimal = Decimal(str(note))
                    if note_decimal < 0 or note_decimal > 20:
                        self.erreurs.append(f"Ligne {numero_ligne}: Note invalide ({note}) - doit être entre 0 et 20")
                except (InvalidOperation, ValueError):
                    self.erreurs.append(f"Ligne {numero_ligne}: Format de note invalide ({note})")


class ImportNotesProcessor:
    """Processeur pour importer les notes"""
    
    def __init__(self, df, classe_id, matiere_id, periode, annee_scolaire, type_import='MENSUELLE', user=None, evaluation_id=None, colonnes_mapping=None):
        self.df = df
        self.classe_id = classe_id
        self.matiere_id = matiere_id
        self.periode = periode
        self.annee_scolaire = annee_scolaire
        self.type_import = type_import
        self.user = user
        self.evaluation_id = evaluation_id
        self.colonnes_mapping = colonnes_mapping or {}
        self.stats = {
            'total': 0,
            'importees': 0,
            'modifiees': 0,
            'absents': 0,
            'erreurs': 0
        }
    
    def importer(self):
        """Importe les notes depuis le DataFrame"""
        try:
            matiere = MatiereNote.objects.get(id=self.matiere_id)
        except MatiereNote.DoesNotExist:
            raise ImportNotesError("Matière introuvable")
        
        if self.type_import == 'MENSUELLE':
            return self._importer_notes_mensuelles(matiere)
        elif self.type_import == 'COMPOSITION':
            return self._importer_notes_composition(matiere)
        elif self.type_import == 'EVALUATION':
            return self._importer_notes_evaluation(matiere)
        
        raise ImportNotesError(f"Type d'import non supporté: {self.type_import}")

    def _invalider_cache_import(self, matiere, periode=None):
        """Invalide les caches apres un import en bloc.

        Les bulk_create/bulk_update ne declenchent pas les signaux Django.
        """
        try:
            from .utils_rangs import invalider_cache_rangs
            invalider_cache_rangs(matiere.classe, periode or self.periode)
        except Exception as e:
            print(f"Erreur invalidation cache apres import: {e}")
    
    def _importer_notes_mensuelles(self, matiere):
        """Importe des notes mensuelles - VERSION OPTIMISÉE"""
        # ⚡ OPTIMISATION: Charger tous les élèves en mémoire (1 seule requête)
        eleves_dict = {e.matricule: e for e in Eleve.objects.all()}
        
        # ⚡ OPTIMISATION: Charger les notes existantes (1 seule requête)
        notes_existantes = {}
        for note in NoteMensuelle.objects.filter(
            matiere=matiere,
            mois=self.periode,
            annee_scolaire=self.annee_scolaire
        ).select_related('eleve'):
            notes_existantes[note.eleve.matricule] = note
        
        notes_a_creer = []
        notes_a_modifier = []
        
        with transaction.atomic():
            for index, row in self.df.iterrows():
                self.stats['total'] += 1
                
                try:
                    # Utiliser le mapping des colonnes
                    matricule_col = self.colonnes_mapping.get('Matricule', 'Matricule')
                    absent_col = self.colonnes_mapping.get('Absent', 'Absent')
                    note_col = self.colonnes_mapping.get('Note', 'Note')
                    
                    matricule = str(row[matricule_col]).strip()
                    eleve = eleves_dict.get(matricule)
                    
                    if not eleve:
                        self.stats['erreurs'] += 1
                        print(f"Erreur ligne {index + 2}: Élève {matricule} introuvable")
                        continue
                    
                    absent = str(row.get(absent_col, 'NON')).strip().upper() in ['OUI', 'O', 'YES', 'Y', '1', 'TRUE']
                    note_value = None if absent else row.get(note_col)
                    
                    note_decimal = Decimal(str(note_value)) if note_value is not None and not pd.isna(note_value) else Decimal('0')
                    
                    # Vérifier si la note existe déjà
                    if matricule in notes_existantes:
                        # Modifier
                        note = notes_existantes[matricule]
                        note.note = note_decimal
                        note.absent = absent
                        note.cree_par = self.user
                        notes_a_modifier.append(note)
                        self.stats['modifiees'] += 1
                    else:
                        # Créer
                        notes_a_creer.append(NoteMensuelle(
                            eleve=eleve,
                            matiere=matiere,
                            mois=self.periode,
                            annee_scolaire=self.annee_scolaire,
                            note=note_decimal,
                            absent=absent,
                            cree_par=self.user
                        ))
                        self.stats['importees'] += 1
                    
                    if absent:
                        self.stats['absents'] += 1
                
                except Exception as e:
                    self.stats['erreurs'] += 1
                    print(f"Erreur ligne {index + 2}: {e}")
            
            # ⚡ BULK OPERATIONS (1 seule requête pour toutes les créations)
            if notes_a_creer:
                NoteMensuelle.objects.bulk_create(notes_a_creer, batch_size=500)
            
            # ⚡ BULK UPDATE (1 seule requête pour toutes les modifications)
            if notes_a_modifier:
                NoteMensuelle.objects.bulk_update(
                    notes_a_modifier, 
                    ['note', 'absent', 'cree_par'],
                    batch_size=500
                )
        
        if notes_a_creer or notes_a_modifier:
            self._invalider_cache_import(matiere)

        return self.stats
    
    def _importer_notes_composition(self, matiere):
        """Importe des notes de composition - VERSION OPTIMISÉE"""
        # ⚡ OPTIMISATION: Charger tous les élèves en mémoire (1 seule requête)
        eleves_dict = {e.matricule: e for e in Eleve.objects.all()}
        
        # ⚡ OPTIMISATION: Charger les notes existantes (1 seule requête)
        notes_existantes = {}
        for note in CompositionNote.objects.filter(
            matiere=matiere,
            periode=self.periode,
            annee_scolaire=self.annee_scolaire
        ).select_related('eleve'):
            notes_existantes[note.eleve.matricule] = note
        
        notes_a_creer = []
        notes_a_modifier = []
        
        with transaction.atomic():
            for index, row in self.df.iterrows():
                self.stats['total'] += 1
                
                try:
                    matricule = str(row['Matricule']).strip()
                    eleve = eleves_dict.get(matricule)
                    
                    if not eleve:
                        self.stats['erreurs'] += 1
                        print(f"Erreur ligne {index + 2}: Élève {matricule} introuvable")
                        continue
                    
                    absent = str(row.get('Absent', 'NON')).strip().upper() in ['OUI', 'O', 'YES', 'Y', '1', 'TRUE']
                    note_value = None if absent else row.get('Note')
                    
                    note_decimal = Decimal(str(note_value)) if note_value is not None and not pd.isna(note_value) else Decimal('0')
                    
                    # Vérifier si la note existe déjà
                    if matricule in notes_existantes:
                        # Modifier
                        note = notes_existantes[matricule]
                        note.note = note_decimal
                        note.absent = absent
                        note.cree_par = self.user
                        notes_a_modifier.append(note)
                        self.stats['modifiees'] += 1
                    else:
                        # Créer
                        notes_a_creer.append(CompositionNote(
                            eleve=eleve,
                            matiere=matiere,
                            periode=self.periode,
                            annee_scolaire=self.annee_scolaire,
                            note=note_decimal,
                            absent=absent,
                            cree_par=self.user
                        ))
                        self.stats['importees'] += 1
                    
                    if absent:
                        self.stats['absents'] += 1
                
                except Exception as e:
                    self.stats['erreurs'] += 1
                    print(f"Erreur ligne {index + 2}: {e}")
            
            # ⚡ BULK OPERATIONS (1 seule requête pour toutes les créations)
            if notes_a_creer:
                CompositionNote.objects.bulk_create(notes_a_creer, batch_size=500)
            
            # ⚡ BULK UPDATE (1 seule requête pour toutes les modifications)
            if notes_a_modifier:
                CompositionNote.objects.bulk_update(
                    notes_a_modifier, 
                    ['note', 'absent', 'cree_par'],
                    batch_size=500
                )
        
        if notes_a_creer or notes_a_modifier:
            self._invalider_cache_import(matiere)

        return self.stats
    
    def _importer_notes_evaluation(self, matiere):
        """Importe des notes d'évaluation - VERSION OPTIMISÉE"""
        try:
            evaluation = Evaluation.objects.get(id=self.evaluation_id)
        except Evaluation.DoesNotExist:
            raise ImportNotesError("Évaluation introuvable")
        
        # ⚡ OPTIMISATION: Charger tous les élèves en mémoire (1 seule requête)
        eleves_dict = {e.matricule: e for e in Eleve.objects.all()}
        
        # ⚡ OPTIMISATION: Charger les notes existantes (1 seule requête)
        notes_existantes = {}
        for note in NoteEleve.objects.filter(
            evaluation=evaluation
        ).select_related('eleve'):
            notes_existantes[note.eleve.matricule] = note
        
        notes_a_creer = []
        notes_a_modifier = []
        
        with transaction.atomic():
            for index, row in self.df.iterrows():
                self.stats['total'] += 1
                
                try:
                    matricule = str(row['Matricule']).strip()
                    eleve = eleves_dict.get(matricule)
                    
                    if not eleve:
                        self.stats['erreurs'] += 1
                        print(f"Erreur ligne {index + 2}: Élève {matricule} introuvable")
                        continue
                    
                    absent = str(row.get('Absent', 'NON')).strip().upper() in ['OUI', 'O', 'YES', 'Y', '1', 'TRUE']
                    note_value = None if absent else row.get('Note')
                    
                    note_decimal = Decimal(str(note_value)) if note_value is not None and not pd.isna(note_value) else None
                    
                    # Vérifier si la note existe déjà
                    if matricule in notes_existantes:
                        # Modifier
                        note = notes_existantes[matricule]
                        note.note = note_decimal
                        note.absent = absent
                        note.cree_par = self.user
                        notes_a_modifier.append(note)
                        self.stats['modifiees'] += 1
                    else:
                        # Créer
                        notes_a_creer.append(NoteEleve(
                            evaluation=evaluation,
                            eleve=eleve,
                            note=note_decimal,
                            absent=absent,
                            cree_par=self.user
                        ))
                        self.stats['importees'] += 1
                    
                    if absent:
                        self.stats['absents'] += 1
                
                except Exception as e:
                    self.stats['erreurs'] += 1
                    print(f"Erreur ligne {index + 2}: {e}")
            
            # ⚡ BULK OPERATIONS (1 seule requête pour toutes les créations)
            if notes_a_creer:
                NoteEleve.objects.bulk_create(notes_a_creer, batch_size=500)
            
            # ⚡ BULK UPDATE (1 seule requête pour toutes les modifications)
            if notes_a_modifier:
                NoteEleve.objects.bulk_update(
                    notes_a_modifier, 
                    ['note', 'absent', 'cree_par'],
                    batch_size=500
                )
            
            # 🔄 SYNCHRONISATION: Copier vers NoteMensuelle pour les périodes mensuelles
            # (bulk_create/bulk_update ne déclenchent pas les signaux Django)
            self._sync_notes_to_mensuelle(evaluation, notes_a_creer + notes_a_modifier)
        
        if notes_a_creer or notes_a_modifier:
            self._invalider_cache_import(matiere, evaluation.periode)

        return self.stats
    
    def _sync_notes_to_mensuelle(self, evaluation, notes_eleve_list):
        """
        Synchronise les NoteEleve vers NoteMensuelle après un bulk import.
        Nécessaire car bulk_create/bulk_update ne déclenchent pas les signaux.
        """
        periodes_mensuelles = ['OCTOBRE', 'NOVEMBRE', 'DECEMBRE', 'JANVIER', 
                               'FEVRIER', 'MARS', 'AVRIL', 'MAI', 'JUIN']
        
        if evaluation.periode not in periodes_mensuelles:
            return  # Pas de sync pour les trimestres/semestres
        
        matiere = evaluation.matiere
        classe_note = matiere.classe
        
        notes_mensuelle_a_creer = []
        notes_mensuelle_existantes = {}
        
        # Charger les NoteMensuelle existantes
        for nm in NoteMensuelle.objects.filter(
            matiere=matiere,
            mois=evaluation.periode,
            annee_scolaire=classe_note.annee_scolaire
        ):
            notes_mensuelle_existantes[nm.eleve_id] = nm
        
        for ne in notes_eleve_list:
            if ne.note is None and not ne.absent:
                continue
            
            note_value = ne.note if ne.note is not None else Decimal('0')
            
            if ne.eleve_id in notes_mensuelle_existantes:
                # Mettre à jour
                nm = notes_mensuelle_existantes[ne.eleve_id]
                nm.note = note_value
                nm.absent = ne.absent
                nm.cree_par = ne.cree_par
            else:
                # Créer
                notes_mensuelle_a_creer.append(NoteMensuelle(
                    eleve=ne.eleve,
                    matiere=matiere,
                    mois=evaluation.periode,
                    annee_scolaire=classe_note.annee_scolaire,
                    note=note_value,
                    absent=ne.absent,
                    cree_par=ne.cree_par
                ))
        
        # Bulk operations
        if notes_mensuelle_a_creer:
            NoteMensuelle.objects.bulk_create(notes_mensuelle_a_creer, batch_size=500)
        
        if notes_mensuelle_existantes:
            NoteMensuelle.objects.bulk_update(
                list(notes_mensuelle_existantes.values()),
                ['note', 'absent', 'cree_par'],
                batch_size=500
            )

        if notes_mensuelle_a_creer or notes_mensuelle_existantes:
            self._invalider_cache_import(matiere, evaluation.periode)


def lire_fichier_import(file_path_or_obj):
    """Lit un fichier Excel ou CSV et retourne un DataFrame"""
    try:
        # Essayer Excel
        if hasattr(file_path_or_obj, 'name') and file_path_or_obj.name.endswith('.csv'):
            df = pd.read_csv(file_path_or_obj)
        else:
            df = pd.read_excel(file_path_or_obj)
        
        # Nettoyer les noms de colonnes
        df.columns = df.columns.str.strip()
        
        return df
    except Exception as e:
        raise ImportNotesError(f"Erreur lors de la lecture du fichier: {e}")


def generer_template_excel(classe_id, matiere_id, type_import='MENSUELLE'):
    """Génère un fichier template Excel pour l'importation avec la liste des élèves pré-remplie"""
    try:
        classe = ClasseNote.objects.get(id=classe_id)
        matiere = MatiereNote.objects.get(id=matiere_id)
        
        # Récupérer les élèves de la classe
        from eleves.models import Classe as ClasseEleve
        
        # Trouver la classe d'élèves correspondante
        # Essayer plusieurs méthodes de correspondance en priorisant l'école
        classe_eleve = None
        ecole = classe.ecole  # L'école de la ClasseNote
        
        # Méthode 1: Correspondance exacte avec année scolaire ET école
        if ecole:
            classe_eleve = ClasseEleve.objects.filter(
                nom__iexact=classe.nom,
                annee_scolaire=classe.annee_scolaire,
                ecole=ecole
            ).first()
        
        # Méthode 2: Correspondance exacte avec année scolaire (sans école)
        if not classe_eleve:
            classe_eleve = ClasseEleve.objects.filter(
                nom__iexact=classe.nom,
                annee_scolaire=classe.annee_scolaire
            ).first()
        
        # Méthode 3: Correspondance exacte du nom avec école
        if not classe_eleve and ecole:
            classe_eleve = ClasseEleve.objects.filter(
                nom__iexact=classe.nom,
                ecole=ecole
            ).first()
        
        # Méthode 4: Correspondance exacte sans année scolaire ni école
        if not classe_eleve:
            classe_eleve = ClasseEleve.objects.filter(
                nom__iexact=classe.nom
            ).first()
        
        # Méthode 5: Correspondance avec normalisation (ignorer casse et accents)
        if not classe_eleve:
            # Normaliser le nom: enlever accents, mettre en minuscules
            nom_normalise = classe.nom.lower().replace('è', 'e').replace('é', 'e').replace('ê', 'e').replace('à', 'a')
            # Filtrer par école si disponible
            if ecole:
                toutes_classes = ClasseEleve.objects.filter(ecole=ecole)
            else:
                toutes_classes = ClasseEleve.objects.all()
            
            for c in toutes_classes:
                nom_c_normalise = c.nom.lower().replace('è', 'e').replace('é', 'e').replace('ê', 'e').replace('à', 'a')
                if nom_normalise == nom_c_normalise:
                    classe_eleve = c
                    break
        
        # Méthode 6: Correspondance partielle (contient premier mot)
        if not classe_eleve:
            premier_mot = classe.nom.split()[0] if classe.nom.split() else classe.nom
            if ecole:
                classe_eleve = ClasseEleve.objects.filter(
                    nom__icontains=premier_mot,
                    ecole=ecole
                ).first()
            if not classe_eleve:
                classe_eleve = ClasseEleve.objects.filter(
                    nom__icontains=premier_mot
                ).first()
        
        # Méthode 7: Chercher par nom simplifié (sans ÈME/ème/ANNÉE)
        if not classe_eleve:
            nom_simple = classe.nom.replace('ÈME', '').replace('ème', '').replace('ANNÉE', '').replace('Année', '').strip()
            if nom_simple:
                if ecole:
                    classe_eleve = ClasseEleve.objects.filter(
                        nom__icontains=nom_simple,
                        ecole=ecole
                    ).first()
                if not classe_eleve:
                    classe_eleve = ClasseEleve.objects.filter(
                        nom__icontains=nom_simple
                    ).first()
        
        # Méthode 8: Chercher dans toutes les classes (dernière chance)
        if not classe_eleve:
            # Récupérer toutes les classes et chercher la meilleure correspondance
            if ecole:
                toutes_classes = ClasseEleve.objects.filter(ecole=ecole)
            else:
                toutes_classes = ClasseEleve.objects.all()
            
            for c in toutes_classes:
                if classe.nom.lower() in c.nom.lower() or c.nom.lower() in classe.nom.lower():
                    classe_eleve = c
                    break
        
        # Récupérer les élèves triés par ordre alphabétique (prénom puis nom)
        eleves = []
        if classe_eleve:
            eleves = list(Eleve.objects.filter(classe=classe_eleve, statut='ACTIF').order_by('prenom', 'nom'))
        
        if eleves:
            # Créer le template avec les élèves
            data = {
                'Matricule': [e.matricule for e in eleves],
                'Prénom': [e.prenom for e in eleves],
                'Nom': [e.nom for e in eleves],
                'Note': ['' for _ in eleves],
                'Absent': ['NON' for _ in eleves]
            }
        else:
            # Si pas d'élèves trouvés, créer un template avec message d'erreur
            msg_classe = f'Classe: {classe.nom}'
            if classe_eleve:
                msg_erreur = f'Aucun élève ACTIF dans la classe "{classe_eleve.nom}"'
            else:
                msg_erreur = f'Classe élèves non trouvée pour "{classe.nom}"'
            
            data = {
                'Matricule': [msg_erreur],
                'Prénom': ['Vérifiez que les élèves sont bien affectés'],
                'Nom': ['et ont le statut ACTIF'],
                'Note': [''],
                'Absent': ['NON']
            }
        
        df = pd.DataFrame(data)
        
        return df
    
    except ClasseNote.DoesNotExist:
        raise ImportNotesError(f"Classe non trouvée (ID: {classe_id})")
    except MatiereNote.DoesNotExist:
        raise ImportNotesError(f"Matière non trouvée (ID: {matiere_id})")
    except Exception as e:
        raise ImportNotesError(f"Erreur lors de la génération du template: {e}")
