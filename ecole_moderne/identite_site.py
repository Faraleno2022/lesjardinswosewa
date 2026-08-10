"""Identité publique du site, déduite du domaine qui sert la requête.

Le même déploiement répond sur plusieurs domaines (myschoolgn.space pour le
logiciel, lesjardinswosewa.com pour l'école). Les métadonnées partagées —
titre, description, Open Graph, Twitter Card, données structurées — doivent
donc suivre le domaine servi, comme le font déjà robots.txt et sitemap.xml.

Un lien de lesjardinswosewa.com partagé sur WhatsApp, Facebook ou LinkedIn
doit annoncer l'école, jamais le logiciel qui l'héberge.
"""

DOMAINE_ECOLE = 'lesjardinswosewa'


IDENTITE_ECOLE = {
    'est_ecole': True,
    'nom': "Les Jardins Wosewa",
    'titre': "Les Jardins Wosewa — Groupe Scolaire Privé à Conakry et Siguiri",
    'description': (
        "Groupe scolaire privé à Conakry (Kipé T2, Ratoma) et à Siguiri : "
        "crèche, maternelle, primaire, collège et lycée, programme "
        "franco-guinéen."
    ),
    'description_partage': (
        "Institution privée d'enseignement général à Conakry et Siguiri : "
        "maternelle, primaire, collège et lycée, programme franco-guinéen."
    ),
    # Coordonnées publiées par l'école sur ses propres pages (accueil, campus).
    'email_contact': "lesjardinswosewa.gui23@gmail.com",
    'telephone': "+224622751518",
    'telephone_affiche': "+224 622 75 15 18",
    'schema_type': "School",
}

IDENTITE_LOGICIEL = {
    'est_ecole': False,
    'nom': "Myschool",
    # Valeur historique de ce déploiement : elle n'est pas modifiée ici pour
    # ne pas changer l'affichage du domaine du logiciel sans arbitrage.
    'titre': "G.S HKD",
    'description': (
        "Myschool — système de gestion scolaire moderne : élèves, paiements, "
        "salaires, transport, notes et statistiques pour les établissements "
        "en Guinée."
    ),
    'description_partage': (
        "Gestion scolaire moderne — automatisation des inscriptions, "
        "paiements, notes et bulletins."
    ),
    'email_contact': "contact@myschoolgn.space",
    'telephone': "+224622613559",
    'telephone_affiche': "+224 622613559",
    'schema_type': "SoftwareApplication",
}


def identite_pour_hote(host):
    """Retourne l'identité publique correspondant à un nom d'hôte."""
    if DOMAINE_ECOLE in (host or '').lower():
        return IDENTITE_ECOLE
    return IDENTITE_LOGICIEL


def identite_site(request):
    """Context processor : expose ``site`` dans tous les gabarits."""
    try:
        host = request.get_host()
    except Exception:
        host = ''
    return {'site': identite_pour_hote(host)}
