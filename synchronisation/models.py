import hashlib
import secrets
import uuid

from django.contrib.auth.hashers import check_password
from django.db import models
from django.utils import timezone

from eleves.models import Ecole
from .mixins import SyncTrackedModel


class SyncDevice(models.Model):
    ecole = models.ForeignKey(Ecole, on_delete=models.CASCADE, related_name='sync_devices')
    nom = models.CharField(max_length=120)
    device_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    token_hash = models.CharField(max_length=255)
    actif = models.BooleanField(default=True, db_index=True)
    derniere_connexion = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Appareil de synchronisation'
        verbose_name_plural = 'Appareils de synchronisation'
        indexes = [
            models.Index(fields=['ecole', 'actif']),
            models.Index(fields=['derniere_connexion']),
        ]

    # Prefixe des empreintes rapides. Les jetons de synchronisation sont des
    # secrets aleatoires de 256 bits, pas des mots de passe choisis par un
    # humain : une empreinte SHA-256 les protege aussi bien qu'un PBKDF2, sans
    # son cout. Ce cout n'etait pas neutre : chaque appel de synchronisation
    # verifie le jeton, et une cadence de quelques secondes aurait consomme le
    # processeur du serveur en pur hachage.
    FAST_HASH_PREFIX = 'sha256$'

    @classmethod
    def _empreinte_rapide(cls, token):
        return cls.FAST_HASH_PREFIX + hashlib.sha256(token.encode('utf-8')).hexdigest()

    def definir_token(self, token):
        self.token_hash = self._empreinte_rapide(token)

    def verifier_token(self, token):
        if not token:
            return False
        stocke = self.token_hash or ''
        if stocke.startswith(self.FAST_HASH_PREFIX):
            return secrets.compare_digest(stocke, self._empreinte_rapide(token))
        # Appareil enregistre par une version anterieure : on verifie avec
        # l'ancien format, puis on convertit pour que la lenteur ne se
        # reproduise pas au prochain appel.
        if not check_password(token, stocke):
            return False
        self.token_hash = self._empreinte_rapide(token)
        self.save(update_fields=['token_hash', 'date_modification'])
        return True

    def marquer_connexion(self):
        self.derniere_connexion = timezone.now()
        self.save(update_fields=['derniere_connexion', 'date_modification'])

    def __str__(self):
        return f'{self.nom} - {self.ecole}'


class SyncChange(models.Model):
    OPERATION_CREATE = 'CREATE'
    OPERATION_UPDATE = 'UPDATE'
    OPERATION_DELETE = 'DELETE'
    OPERATION_CHOICES = [
        (OPERATION_CREATE, 'Creation'),
        (OPERATION_UPDATE, 'Modification'),
        (OPERATION_DELETE, 'Suppression'),
    ]

    STATUT_PENDING = 'PENDING'
    STATUT_APPLIED = 'APPLIED'
    STATUT_FAILED = 'FAILED'
    STATUT_ABANDONED = 'ABANDONED'
    STATUT_CHOICES = [
        (STATUT_PENDING, 'En attente'),
        (STATUT_APPLIED, 'Applique'),
        (STATUT_FAILED, 'Echec (sera rejoue)'),
        (STATUT_ABANDONED, 'Abandonne apres trop de tentatives'),
    ]

    ecole = models.ForeignKey(Ecole, on_delete=models.CASCADE, related_name='sync_changes')
    device = models.ForeignKey(SyncDevice, on_delete=models.SET_NULL, null=True, blank=True, related_name='changes')
    model_label = models.CharField(max_length=120)
    object_uuid = models.UUIDField(null=True, blank=True, db_index=True)
    operation = models.CharField(max_length=10, choices=OPERATION_CHOICES)
    payload = models.JSONField(default=dict, blank=True)
    statut = models.CharField(max_length=12, choices=STATUT_CHOICES, default=STATUT_PENDING, db_index=True)
    erreur = models.TextField(blank=True)
    # Nombre d'echecs. Un echec est souvent temporaire (l'objet lie n'est pas
    # encore arrive) : le changement est rejoue aux cycles suivants, jusqu'a
    # une limite, au lieu d'etre perdu ou renvoye indefiniment.
    tentatives = models.PositiveSmallIntegerField(default=0)
    # Identifiant du changement sur le poste emetteur. Permet de reconnaitre un
    # renvoi (accuse de reception perdu, refus temporaire) et de mettre a jour
    # la ligne existante au lieu d'en empiler une nouvelle a chaque cycle.
    client_change_id = models.PositiveIntegerField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True, db_index=True)
    date_application = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Changement synchronise'
        verbose_name_plural = 'Changements synchronises'
        indexes = [
            models.Index(fields=['ecole', 'statut', 'date_creation']),
            models.Index(fields=['model_label', 'object_uuid']),
            models.Index(fields=['device', 'client_change_id']),
        ]

    def __str__(self):
        return f'{self.operation} {self.model_label} ({self.statut})'
