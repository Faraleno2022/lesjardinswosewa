"""
Numerotation des recus, resistante au travail sur plusieurs postes.

Le numero etait tire du plus grand numero present dans la base **locale**.
Chaque poste ayant sa propre base, deux caisses qui encaissent en meme temps
produisaient le meme numero. A la synchronisation, le paiement arrivant
heurtait la contrainte d'unicite, echouait cinq fois, puis etait abandonne :
le paiement disparaissait purement et simplement du poste destinataire, sans
que personne ne le remarque.

La reponse est d'inserer dans le numero un code propre au poste emetteur. Deux
postes ne peuvent alors plus produire la meme valeur, et le numero reste celui
d'origine partout ou le paiement voyage — ce qui compte pour une piece
comptable deja imprimee.
"""
import hashlib
import re

from django.conf import settings

# REC2026-A3F7-0001 : annee, code du poste, sequence. Tient dans les 20
# caracteres de la colonne.
LONGUEUR_CODE_POSTE = 4
MOTIF_NUMERO = re.compile(r'^REC(\d{4})(?:-([0-9A-F]{4})-)?(\d{4})$')


def code_du_poste():
    """
    Code court identifiant ce poste, ou None s'il travaille seul.

    Il derive de l'identifiant d'appareil de synchronisation : deux postes
    relies au meme serveur en ont forcement un different, et il ne change
    jamais pour un poste donne — un code qui bougerait recreerait le probleme
    qu'il resout, en repartant a la sequence 1 sur des numeros deja pris.

    Un poste sans synchronisation ne partage sa base avec personne : aucune
    collision n'est possible, et lui ajouter un code allongerait ses numeros
    sans rien apporter.
    """
    identifiant = (getattr(settings, 'MYSCHOOL_SYNC_DEVICE_ID', '') or '').strip()
    if not identifiant:
        return None
    empreinte = hashlib.sha256(identifiant.encode('utf-8')).hexdigest()
    return empreinte[:LONGUEUR_CODE_POSTE].upper()


def prefixe_courant(annee):
    """Debut commun a tous les numeros emis par ce poste cette annee."""
    code = code_du_poste()
    return f'REC{annee}-{code}-' if code else f'REC{annee}'


def sequence_de(numero):
    """
    Numero d'ordre contenu dans un numero de recu, ou None.

    Les deux formats coexistent : les paiements anterieurs gardent leur
    numero, il n'est pas question de les renumeroter.
    """
    trouve = MOTIF_NUMERO.match((numero or '').strip().upper())
    if not trouve:
        return None
    try:
        return int(trouve.group(3))
    except (TypeError, ValueError):
        return None


def prochain_numero(modele, annee, decalage=0):
    """
    Prochain numero libre pour ce poste et cette annee.

    La recherche se limite aux numeros portant le meme prefixe : ceux des
    autres postes ne doivent pas faire avancer la sequence locale, sinon deux
    postes se pousseraient mutuellement vers le haut a chaque synchronisation.
    """
    prefixe = prefixe_courant(annee)
    sequences = [
        sequence_de(valeur)
        for valeur in modele.objects
        .filter(numero_recu__startswith=prefixe)
        .values_list('numero_recu', flat=True)
    ]
    connues = [s for s in sequences if s is not None]
    suivante = (max(connues) if connues else 0) + 1 + decalage
    return f'{prefixe}{suivante:04d}'
