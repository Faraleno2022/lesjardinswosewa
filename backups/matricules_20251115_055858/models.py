from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from decimal import Decimal
import unicodedata

class Ecole(models.Model):
    """Modèle pour représenter une école"""
    ETAT_CHOICES = [
        ("BROUILLON", "Brouillon"),
        ("EN_ATTENTE", "En attente de validation"),
        ("VALIDE", "Validée"),
        ("REJETE", "Rejetée"),
    ]
    nom = models.CharField(max_length=200, verbose_name="Nom de l'école")
    adresse = models.TextField(verbose_name="Adresse")
    telephone = models.CharField(
        max_length=20, 
        validators=[RegexValidator(r'^\+224\d{8,9}$', 'Format: +224XXXXXXXXX')],
        verbose_name="Téléphone"
    )
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    directeur = models.CharField(max_length=100, verbose_name="Directeur")
    logo = models.ImageField(upload_to='ecoles/logos/', blank=True, null=True)
    # Préfixe explicite pour les matricules (ex: "AL-FUR/")
    code_prefixe = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Préfixe matricules",
        help_text="Préfixe d'école pour les matricules, ex: AL-FUR/ (laisser vide pour ne pas utiliser)"
    )
    # Informations officielles pour entête des bulletins
    ire = models.CharField(max_length=100, blank=True, null=True, verbose_name="IRE")
    dpe = models.CharField(max_length=100, blank=True, null=True, verbose_name="DPE")
    desee = models.CharField(max_length=100, blank=True, null=True, verbose_name="DESEE")
    date_creation = models.DateTimeField(auto_now_add=True)
    etat = models.CharField(max_length=20, choices=ETAT_CHOICES, default="BROUILLON", db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ecoles_creees')
    
    class Meta:
        verbose_name = "École"
        verbose_name_plural = "Écoles"
    
    def save(self, *args, **kwargs):
        # Normaliser le code_prefixe: supprimer doublons ('AL-FUR/AL-FUR/') et assurer un seul '/'
        try:
            if self.code_prefixe is not None:
                self.code_prefixe = _normalize_code_prefixe(self.code_prefixe)
        except Exception:
            pass
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.nom

class Classe(models.Model):
    """Modèle pour représenter une classe"""
    NIVEAUX_CHOICES = [
        ('GARDERIE', 'Garderie'),
        ('MATERNELLE', 'Maternelle'),
        ('PRIMAIRE_1', 'Primaire 1ère'),
        ('PRIMAIRE_2', 'Primaire 2ème'),
        ('PRIMAIRE_3', 'Primaire 3ème'),
        ('PRIMAIRE_4', 'Primaire 4ème'),
        ('PRIMAIRE_5', 'Primaire 5ème'),
        ('PRIMAIRE_6', 'Primaire 6ème'),
        ('COLLEGE_7', 'Collège 7ème'),
        ('COLLEGE_8', 'Collège 8ème'),
        ('COLLEGE_9', 'Collège 9ème'),
        ('COLLEGE_10', 'Collège 10ème'),
        ('LYCEE_11', 'Lycée 11ème'),
        ('LYCEE_12', 'Lycée 12ème'),
        ('TERMINALE', 'Terminale'),
    ]
    
    ecole = models.ForeignKey(Ecole, on_delete=models.CASCADE, related_name='classes')
    nom = models.CharField(max_length=100, verbose_name="Nom de la classe")
    niveau = models.CharField(max_length=20, choices=NIVEAUX_CHOICES, verbose_name="Niveau")
    code_matricule = models.CharField(
        max_length=12,
        blank=True,
        null=True,
        verbose_name="Code matricule",
        help_text="Préfixe utilisé pour les matricules (ex: PN3, CN7, L11SL)."
    )
    annee_scolaire = models.CharField(max_length=9, verbose_name="Année scolaire", help_text="Format: 2024-2025")
    capacite_max = models.PositiveIntegerField(default=30, verbose_name="Capacité maximale")
    
    class Meta:
        verbose_name = "Classe"
        verbose_name_plural = "Classes"
        unique_together = ['ecole', 'nom', 'annee_scolaire']
        indexes = [
            models.Index(fields=['ecole', 'niveau']),
            models.Index(fields=['ecole', 'annee_scolaire']),
            models.Index(fields=['ecole', 'code_matricule']),
        ]
    
    def __str__(self):
        return f"{self.nom} - {self.get_niveau_display()} ({self.annee_scolaire})"
    
    @property
    def nombre_eleves(self):
        return self.eleves.count()

# --- Helper: Resolve class code for matricule generation ---
def _code_classe_from_nom_ou_niveau(classe: "Classe") -> str:
    """Retourne le code matricule à partir du nom (prioritaire) ou du niveau de la classe.
    Mapping fourni par l'utilisateur. Si aucun mapping trouvé, retourne une chaîne vide.
    """
    # 1) Si le champ dédié est renseigné, on l'utilise en priorité
    code_direct = getattr(classe, 'code_matricule', None)
    if code_direct:
        return code_direct.strip()
    # Mapping par nom exact (insensible à la casse/espaces superflus)
    mapping_nom = {
        "garderie": "GA",
        "petite section": "MPS",
        "moyen section": "MMS",
        "moyenne section": "MMS",
        "ps": "MPS",
        "ms": "MMS",
        "gs": "MGS",
        "grande section": "MGS",
        "1ère année": "PN1",
        "2ème année": "PN2",
        "3ème année": "PN3",
        "4ème année": "PN4",
        "5ème année": "PN5",
        "6ème année": "PN6",
        "7ème année": "CN7",
        "8ème année": "CN8",
        "9ème année": "CN9",
        "10ème année": "CN10",
        "11ème série littéraire": "L11SL",
        "11ème série scientifique i": "L11SSI",
        "11ème série scientifique ii": "L11SSII",
        "12ème ss": "L12SS",
        "12ème sm": "L12SM",
        "12ème se": "L12SE",
        "terminale ss": "TSS",
        "terminale se": "TSE",
        "terminale sm": "TSM",
    }

    # Normalisation robuste: suppression accents/espaces multiples, lower
    def _normalize_nom(value: str) -> str:
        try:
            s = (value or "").strip().lower()
            s = unicodedata.normalize('NFD', s)
            s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')  # remove accents
            # Uniformiser espaces
            s = ' '.join(s.split())
            return s
        except Exception:
            return ""

# --- Helper: Normalize school prefix like 'AL-FUR/' and avoid duplicates 'AL-FUR/AL-FUR/' ---
def _normalize_code_prefixe(value: str) -> str:
    """Normalize a school code prefix:
    - Trim spaces
    - Split on '/'
    - Remove empty parts
    - Collapse immediate duplicate segments (e.g., ['AL-FUR','AL-FUR'] -> ['AL-FUR'])
    - Join back with one '/'
    - Ensure trailing '/'
    """
    try:
        s = (value or "").strip()
        if not s:
            return ""
        parts = [p.strip() for p in s.split('/') if p.strip()]
        # Collapse duplicates
        normalized_parts = []
        for p in parts:
            if not normalized_parts or normalized_parts[-1] != p:
                normalized_parts.append(p)
        if not normalized_parts:
            return ""
        return "/".join(normalized_parts).rstrip('/') + "/"
    except Exception:
        return ""

    nom_norm = _normalize_nom(getattr(classe, 'nom', ''))
    code = mapping_nom.get(nom_norm, "")
    if code:
        return code

    # Fallback basique sur niveau si le nom ne correspond pas
    niveau = getattr(classe, "niveau", "")
    fallback_niveau = {
        "GARDERIE": "GA",
        "PRIMAIRE_1": "PN1",
        "PRIMAIRE_2": "PN2",
        "PRIMAIRE_3": "PN3",
        "PRIMAIRE_4": "PN4",
        "PRIMAIRE_5": "PN5",
        "PRIMAIRE_6": "PN6",
        "COLLEGE_7": "CN7",
        "COLLEGE_8": "CN8",
        "COLLEGE_9": "CN9",
        "COLLEGE_10": "CN10",
        "LYCEE_11": "L11",
        "LYCEE_12": "L12",
        "TERMINALE": "T",
    }
    code_fb = fallback_niveau.get(niveau, "")
    if code_fb:
        return code_fb

    # Fallback avancé basé sur motifs (ex: 1ere/2eme annee, 11eme/12eme, terminale)
    nom_tokens = nom_norm
    # Détection des années 1-10 → PN/CN
    import re
    m = re.search(r"\b(1|2|3|4|5|6|7|8|9|10)\b", nom_tokens)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 6:
            return f"PN{n}"
        if 7 <= n <= 10:
            return f"CN{n}"

    # 11ème séries
    if '11' in nom_tokens:
        if 'litteraire' in nom_tokens:
            return 'L11SL'
        if 'scientifique' in nom_tokens:
            if 'ii' in nom_tokens or '2' in nom_tokens:
                return 'L11SSII'
            return 'L11SSI'
        return 'L11'

    # 12ème séries
    if '12' in nom_tokens:
        if 'ss' in nom_tokens:
            return 'L12SS'
        if 'sm' in nom_tokens:
            return 'L12SM'
        if 'se' in nom_tokens:
            return 'L12SE'
        return 'L12'

    # Terminale séries
    if 'terminale' in nom_tokens:
        if 'ss' in nom_tokens:
            return 'TSS'
        if 'se' in nom_tokens:
            return 'TSE'
        if 'sm' in nom_tokens:
            return 'TSM'
        return 'T'

    # Dernier recours: vide → le save() appliquera le fallback CL{id}
    return ""

class Responsable(models.Model):
    """Modèle pour représenter un responsable d'élève"""
    RELATION_CHOICES = [
        ('PERE', 'Père'),
        ('MERE', 'Mère'),
        ('TUTEUR', 'Tuteur'),
        ('TUTRICE', 'Tutrice'),
        ('GRAND_PERE', 'Grand-père'),
        ('GRAND_MERE', 'Grand-mère'),
        ('ONCLE', 'Oncle'),
        ('TANTE', 'Tante'),
        ('AUTRE', 'Autre'),
    ]
    
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    nom = models.CharField(max_length=100, verbose_name="Nom")
    relation = models.CharField(max_length=20, choices=RELATION_CHOICES, verbose_name="Relation")
    telephone = models.CharField(
        max_length=20, 
        validators=[RegexValidator(r'^\+224\d{8,9}$', 'Format: +224XXXXXXXXX')],
        verbose_name="Téléphone"
    )
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    adresse = models.TextField(verbose_name="Adresse")
    profession = models.CharField(max_length=100, blank=True, null=True, verbose_name="Profession")
    
    class Meta:
        verbose_name = "Responsable"
        verbose_name_plural = "Responsables"
    
    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.get_relation_display()})"

    @property
    def nom_complet(self) -> str:
        """Retourne le nom complet du responsable (Prénom Nom)."""
        return f"{self.prenom} {self.nom}"

class GrilleTarifaire(models.Model):
    """Modèle pour les grilles tarifaires par école et niveau"""
    ecole = models.ForeignKey(Ecole, on_delete=models.CASCADE, related_name='grilles_tarifaires')
    niveau = models.CharField(max_length=20, choices=Classe.NIVEAUX_CHOICES, verbose_name="Niveau")
    annee_scolaire = models.CharField(max_length=9, verbose_name="Année scolaire")
    
    # Frais d'inscription
    frais_inscription = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="Frais d'inscription (GNF)"
    )
    # Frais de réinscription (peut être différent)
    frais_reinscription = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="Frais de réinscription (GNF)"
    )
    
    # Frais de scolarité par tranches
    tranche_1 = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="1ère tranche (GNF)"
    )
    tranche_2 = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="2ème tranche (GNF)"
    )
    tranche_3 = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="3ème tranche (GNF)"
    )
    
    # Périodes de paiement
    periode_1 = models.CharField(max_length=50, default="À l'inscription", verbose_name="Période 1")
    periode_2 = models.CharField(max_length=50, default="Début janvier", verbose_name="Période 2")
    periode_3 = models.CharField(max_length=50, default="Début mars", verbose_name="Période 3")
    # Échéances par défaut (optionnelles) pour initialiser les échéanciers des élèves
    # Si non renseignées, la logique applicative utilisera des valeurs par défaut (15/01, 15/03, 15/05)
    date_echeance_inscription_defaut = models.DateField(
        null=True, blank=True, verbose_name="Échéance inscription (défaut)"
    )
    date_echeance_tranche_1_defaut = models.DateField(
        null=True, blank=True, verbose_name="Échéance Tranche 1 (défaut)"
    )
    date_echeance_tranche_2_defaut = models.DateField(
        null=True, blank=True, verbose_name="Échéance Tranche 2 (défaut)"
    )
    date_echeance_tranche_3_defaut = models.DateField(
        null=True, blank=True, verbose_name="Échéance Tranche 3 (défaut)"
    )
    
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Grille tarifaire"
        verbose_name_plural = "Grilles tarifaires"
        unique_together = ['ecole', 'niveau', 'annee_scolaire']
    
    def __str__(self):
        return f"{self.ecole.nom} - {self.get_niveau_display()} ({self.annee_scolaire})"
    
    @property
    def total_scolarite(self):
        return self.tranche_1 + self.tranche_2 + self.tranche_3
    
    @property
    def total_avec_inscription(self):
        return self.frais_inscription + self.total_scolarite

class Eleve(models.Model):
    """Modèle principal pour représenter un élève"""
    SEXE_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]
    
    STATUT_CHOICES = [
        ('ACTIF', 'Actif'),
        ('SUSPENDU', 'Suspendu'),
        ('EXCLU', 'Exclu'),
        ('TRANSFERE', 'Transféré'),
        ('DIPLOME', 'Diplômé'),
    ]
    
    # Informations personnelles
    matricule = models.CharField(max_length=20, unique=True, verbose_name="Matricule")
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    nom = models.CharField(max_length=100, verbose_name="Nom")
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES, verbose_name="Sexe")
    date_naissance = models.DateField(verbose_name="Date de naissance", blank=True, null=True)
    lieu_naissance = models.CharField(max_length=100, verbose_name="Lieu de naissance")
    photo = models.ImageField(upload_to='eleves/photos/', blank=True, null=True, verbose_name="Photo")
    
    # Scolarité
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name='eleves')
    date_inscription = models.DateField(verbose_name="Date d'inscription")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='ACTIF', verbose_name="Statut", db_index=True)
    
    # Responsables
    responsable_principal = models.ForeignKey(
        Responsable, on_delete=models.CASCADE, 
        related_name='eleves_principal', verbose_name="Responsable principal"
    )
    responsable_secondaire = models.ForeignKey(
        Responsable, on_delete=models.SET_NULL, 
        related_name='eleves_secondaire', blank=True, null=True,
        verbose_name="Responsable secondaire"
    )
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Élève"
        verbose_name_plural = "Élèves"
        ordering = ['nom', 'prenom']
        indexes = [
            models.Index(fields=['classe', 'statut']),
            models.Index(fields=['nom', 'prenom']),
            models.Index(fields=['date_inscription']),
        ]
    
    def __str__(self):
        return f"{self.matricule} - {self.prenom} {self.nom}"
    
    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}"
    
    @property
    def age(self):
        from datetime import date
        if not self.date_naissance:
            return None
        today = date.today()
        return today.year - self.date_naissance.year - ((today.month, today.day) < (self.date_naissance.month, self.date_naissance.day))

    def _reaffecter_matricules_ancienne_classe(self, ancienne_classe, ancien_matricule):
        """Désactivée pour éviter les conflits UNIQUE"""
        pass
    def save(self, *args, **kwargs):
        """Génère automatiquement le matricule au format CODE-### si absent.
        - CODE déterminé par la classe via `_code_classe_from_nom_ou_niveau`
        - ### est une séquence à 3 chiffres, incrémentée par classe (et donc par école)
        - Si des matricules existants de la classe contiennent un préfixe d'école (ex: "AL-FUR/PN4-001"),
          ce préfixe est détecté et conservé pour les nouveaux matricules de la même classe.
        - Si la classe change, le matricule est automatiquement régénéré avec le code de la nouvelle classe.
        - NOUVEAU: Réaffectation intelligente des matricules de l'ancienne classe pour combler le "trou".
        """
        # Détecter un changement de classe pour régénérer le matricule
        regenerer_matricule = False
        ancienne_classe = None
        ancien_matricule = None
        changement_classe_info = None
        reaffecter_ancienne_classe = False
        
        if self.pk:  # Si l'élève existe déjà
            try:
                old_instance = Eleve.objects.get(pk=self.pk)
                if old_instance.classe_id != self.classe_id:
                    # Changement de classe détecté
                    regenerer_matricule = True
                    ancienne_classe = old_instance.classe
                    ancien_matricule = self.matricule
                    reaffecter_ancienne_classe = True
                    # Stocker les infos pour créer l'historique après la sauvegarde
                    changement_classe_info = {
                        'ancienne_classe': old_instance.classe.nom,
                        'nouvelle_classe': self.classe.nom,
                        'ancien_matricule': ancien_matricule,
                        'utilisateur': getattr(self, '_current_user', None)
                    }
            except Eleve.DoesNotExist:
                pass
        
        # Ne générer le matricule automatiquement que si :
        # 1. Il n'y a pas de matricule ou on doit le régénérer (changement de classe)
        # 2. ET qu'on n'a pas demandé de skip la génération (saisie manuelle)
        if (not self.matricule or regenerer_matricule) and getattr(self, 'classe_id', None) and not getattr(self, '_skip_matricule_generation', False):
            code = _code_classe_from_nom_ou_niveau(self.classe)
            # Fallback de sécurité pour éviter un matricule vide si le code n'est pas résolu
            if not code:
                try:
                    cls_id = getattr(self.classe, 'id', None) or 'X'
                except Exception:
                    cls_id = 'X'
                code = f"CL{cls_id}"
            if code:
                import re
                # 1) Déterminer s'il existe un préfixe d'école pour cette classe
                #    On inspecte les matricules existants de la même classe uniquement (reset par classe)
                classe_qs = Eleve.objects.filter(classe=self.classe)
                prefix_ecole = ""  # ex: "AL-FUR/" si présent

                # 1.a) Utiliser en priorité le préfixe explicite de l'école s'il est fourni
                ec_prefix = getattr(self.classe.ecole, 'code_prefixe', None) or ""
                ec_prefix = _normalize_code_prefixe(ec_prefix)
                if ec_prefix:
                    prefix_ecole = ec_prefix
                # Chercher un exemple existant correspondant au motif optionnel prefix + code-###
                exemple = (
                    classe_qs
                    .filter(matricule__contains=f"{code}-")
                    .order_by('-id')
                    .first()
                )
                if not prefix_ecole and exemple:
                    m_pref = re.match(rf"^(.*?/)?{re.escape(code)}-\d+$", exemple.matricule)
                    if m_pref and m_pref.group(1):
                        prefix_ecole = m_pref.group(1)  # conserve le '/'
                # Sinon, essayer d'inférer un préfixe d'école depuis d'autres classes de la même école
                if not prefix_ecole:
                    autre = (
                        Eleve.objects
                        .filter(classe__ecole=self.classe.ecole)
                        .order_by('-id')
                        .first()
                    )
                    if autre:
                        m_ec = re.match(r"^(.*?/)[A-Z0-9]+-\d+$", autre.matricule)
                        if m_ec:
                            prefix_ecole = m_ec.group(1)

                # 2) Calculer le prochain numéro dans la classe, quel que soit le préfixe
                motif = rf"^(?:.*/)?{re.escape(code)}-(\d+)$"
                next_num = 1
                # Parcourir les matricules de la classe contenant le code, triés récents d'abord
                for e in classe_qs.filter(matricule__contains=f"{code}-").order_by('-id'):
                    m = re.match(motif, e.matricule)
                    if m:
                        try:
                            next_num = int(m.group(1)) + 1
                            break
                        except Exception:
                            continue

                # 3) Générer un candidat avec ou sans préfixe école détecté, en évitant les collisions
                for _ in range(10):
                    candidat = f"{prefix_ecole}{code}-{next_num:03d}"
                    if not Eleve.objects.filter(matricule=candidat).exists():
                        self.matricule = candidat
                        break
                    next_num += 1

        # Si changement de classe, libérer temporairement le matricule avant réaffectation
        # pour éviter les conflits UNIQUE
        matricule_final = None
        if reaffecter_ancienne_classe and ancienne_classe:
            matricule_final = self.matricule
            # Attribuer un matricule temporaire unique pour libérer l'ancien
            import uuid
            self.matricule = f"TEMP-{uuid.uuid4().hex[:8]}"
        
        super().save(*args, **kwargs)
        
        # Réaffectation intelligente des matricules de l'ancienne classe
        if reaffecter_ancienne_classe and ancienne_classe:
            #self._reaffecter_matricules_ancienne_classe(ancienne_classe, ancien_matricule)
            # Restaurer le matricule final de l'élève transféré
            if matricule_final:
                self.matricule = matricule_final
                super().save(update_fields=['matricule'])
        
        # Créer l'historique du changement de classe après la sauvegarde
        if changement_classe_info:
            HistoriqueEleve.objects.create(
                eleve=self,
                action='CHANGEMENT_CLASSE',
                description=f"Changement de classe: {changement_classe_info['ancienne_classe']} → {changement_classe_info['nouvelle_classe']}. Ancien matricule: {changement_classe_info['ancien_matricule']}, Nouveau matricule: {self.matricule}",
                utilisateur=changement_classe_info['utilisateur']
            )

class HistoriqueEleve(models.Model):
    """Modèle pour l'historique des modifications d'un élève"""
    ACTION_CHOICES = [
        ('CREATION', 'Création'),
        ('MODIFICATION', 'Modification'),
        ('CHANGEMENT_CLASSE', 'Changement de classe'),
        ('CHANGEMENT_STATUT', 'Changement de statut'),
        ('SUSPENSION', 'Suspension'),
        ('EXCLUSION', 'Exclusion'),
        ('TRANSFERT', 'Transfert'),
    ]
    
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name='historique')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Action")
    description = models.TextField(verbose_name="Description")
    date_action = models.DateTimeField(auto_now_add=True, verbose_name="Date de l'action")
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Historique élève"
        verbose_name_plural = "Historiques élèves"
        ordering = ['-date_action']
    
    def __str__(self):
        return f"{self.eleve.nom_complet} - {self.get_action_display()} ({self.date_action.strftime('%d/%m/%Y')})"
