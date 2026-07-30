from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os


def document_upload_path(instance, filename):
    """Génère le chemin d'upload pour les documents"""
    return f'chatbot/documents/{instance.matiere}/{filename}'


class Matiere(models.Model):
    """Matières disponibles pour les documents"""
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icone = models.CharField(max_length=50, default='📚')
    ordre = models.IntegerField(default=0)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = 'Matière'
        verbose_name_plural = 'Matières'
    
    def __str__(self):
        return f"{self.icone} {self.nom}"


class DocumentCours(models.Model):
    """Documents de cours uploadés pour le chatbot"""
    NIVEAU_CHOICES = [
        ('6EME', '6ème'),
        ('5EME', '5ème'),
        ('4EME', '4ème'),
        ('3EME', '3ème'),
        ('2NDE', '2nde'),
        ('1ERE', '1ère'),
        ('TLE', 'Terminale'),
        ('TOUS', 'Tous niveaux'),
    ]
    
    titre = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name='documents')
    niveau = models.CharField(max_length=10, choices=NIVEAU_CHOICES, default='TOUS')
    fichier = models.FileField(upload_to=document_upload_path)
    contenu_extrait = models.TextField(blank=True, help_text="Contenu textuel extrait du document")
    
    # Métadonnées
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='documents_uploades')
    date_upload = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    actif = models.BooleanField(default=True)
    nombre_consultations = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-date_upload']
        verbose_name = 'Document de cours'
        verbose_name_plural = 'Documents de cours'
    
    def __str__(self):
        return f"{self.titre} - {self.matiere.nom} ({self.get_niveau_display()})"
    
    @property
    def extension(self):
        """Retourne l'extension du fichier"""
        if self.fichier:
            return os.path.splitext(self.fichier.name)[1].lower()
        return ''
    
    @property
    def taille_fichier(self):
        """Retourne la taille du fichier en format lisible"""
        if self.fichier:
            try:
                size = self.fichier.size
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size < 1024:
                        return f"{size:.1f} {unit}"
                    size /= 1024
            except:
                pass
        return "N/A"


class ConversationChat(models.Model):
    """Historique des conversations avec le chatbot"""
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations_chat', null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True, help_text="ID de session pour utilisateurs non connectés")
    matiere = models.ForeignKey(Matiere, on_delete=models.SET_NULL, null=True, blank=True)
    date_debut = models.DateTimeField(auto_now_add=True)
    date_derniere_activite = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-date_derniere_activite']
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'
    
    def __str__(self):
        user_str = self.utilisateur.username if self.utilisateur else f"Session {self.session_id[:8]}"
        return f"Conversation de {user_str} - {self.date_debut.strftime('%d/%m/%Y %H:%M')}"


class MessageChat(models.Model):
    """Messages individuels dans une conversation"""
    TYPE_CHOICES = [
        ('USER', 'Utilisateur'),
        ('BOT', 'Chatbot'),
        ('SYSTEM', 'Système'),
    ]
    
    conversation = models.ForeignKey(ConversationChat, on_delete=models.CASCADE, related_name='messages')
    type_message = models.CharField(max_length=10, choices=TYPE_CHOICES)
    contenu = models.TextField()
    documents_references = models.ManyToManyField(DocumentCours, blank=True, related_name='messages_references')
    date_envoi = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['date_envoi']
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
    
    def __str__(self):
        return f"{self.get_type_message_display()}: {self.contenu[:50]}..."


class RecherchePopulaire(models.Model):
    """Stocke les recherches populaires pour suggestions"""
    question = models.CharField(max_length=500)
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, null=True, blank=True)
    nombre_recherches = models.IntegerField(default=1)
    derniere_recherche = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-nombre_recherches']
        verbose_name = 'Recherche populaire'
        verbose_name_plural = 'Recherches populaires'
    
    def __str__(self):
        return f"{self.question} ({self.nombre_recherches} fois)"
