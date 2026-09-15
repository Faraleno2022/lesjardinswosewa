# Audit des calculs et corrections — 15 septembre 2026

Audit réalisé sur le projet Wosewa à partir du commit `81c713f`. Les corrections portent sur les règles déjà présentes dans l’application et sur leur cohérence entre calculs individuels, calculs collectifs et rapports.

## Anomalies reproduites et corrigées

| Domaine | Défaut reproduit | Correction |
| --- | --- | --- |
| Moyennes et classements | Un résultat mis en cache pour un élève ou une matière était réutilisé pour une autre sélection. | Les clés identifient les élèves, les matières, leur ordre et la version du calcul. |
| Barème du primaire | Une note de 10 avec un bonus de 2 donnait 12/10. | Le bonus respecte le plafond de la matière : 10 au primaire, 20 au secondaire. |
| Activation du bonus | Dans un lot de matières de plusieurs écoles, une école ayant activé le bonus pouvait l’activer pour les autres. | Seules les matières des écoles ayant activé le bonus sont retenues. |
| Absence semestrielle | Une composition explicitement absente était remplacée par les compositions trimestrielles. Avec 10 en cours et les compositions T1=16, T2=18, le résultat était 14,2 au lieu de 4. | Le repli trimestriel s’applique uniquement lorsqu’aucune composition semestrielle n’a été enregistrée. Une absence compte pour zéro. |
| Repli trimestriel | Une composition absente ou manquante pouvait sortir du dénominateur et augmenter la moyenne. | Les trimestres évalués dans la matière déterminent le dénominateur ; les absences et compositions manquantes valent zéro. |
| Sélection d’élèves | Une composition manquante était traitée différemment selon que le calcul portait sur un élève ou sur toute la classe. | La détection des compositions évaluées porte toujours sur la matière et l’année de la classe. |
| Libellés des périodes | « 1er Trimestre » et « TRIMESTRE_1 » pouvaient produire des moyennes différentes. | Les périodes sont normalisées avant les requêtes et les calculs. |
| Encaissements après baisse de tarif | Les rapports ne retenaient que la part affectée à l’échéancier ; le surplus encaissé disparaissait des recettes. | La ventilation conserve tout le montant réellement encaissé, y compris le surplus de scolarité. |
| Paiements annulés ou en attente | Les prestations hors scolarité pouvaient encore entrer dans la ventilation des encaissements. | Tous les paiements non validés sont exclus, quelle que soit leur catégorie. |
| Remises fixes | Une remise fixe de 10,50 pouvait rester fractionnaire alors que les remises sont calculées en GNF entiers. | Arrondi au GNF le plus proche, moitié supérieure, avec maintien du plafond du montant de base. |
| Répartition des heures | Les arrondis pouvaient produire une dernière durée négative ou affecter le reliquat à une classe sans heures prévues. | Répartition des centièmes selon les plus grands restes, sans durée négative ni perte du total. |
| Arrondis de paie | Un nombre fourni sous forme flottante pouvait être arrondi autrement que sa valeur décimale : 2,675 donnait 2,67. | Conversion par la représentation décimale avant l’arrondi ; 2,675 donne 2,68. |

## Principes vérifiés

### Scolarité et recettes

- Les recettes proviennent des paiements validés. Elles restent distinctes de la couverture du montant dû.
- La ventilation suit l’ordre admission, tranche 1, tranche 2, tranche 3.
- Les remises s’appliquent aux tranches concernées, jamais aux frais d’inscription ou de réinscription.
- Le solde restant est plafonné à zéro ; un surplus encaissé doit rester visible dans les recettes après une baisse de tarif.
- Le calcul est isolé par élève et année scolaire.
- La validation continue de refuser un nouveau paiement supérieur au solde autorisé. Le scénario de surplus testé provient d’une baisse du tarif après les encaissements.

### Notes

- Au primaire, les matières contribuent à poids égal et la composition est utilisée lorsqu’elle existe.
- Au secondaire, moyenne de période = 40 % de moyenne de cours + 60 % de composition lorsque les deux composantes existent.
- Une composition absente ou manquante compte pour zéro lorsque la matière a été évaluée.
- Le bonus de suivi nécessite l’activation par l’école et ne doit pas dépasser le barème.
- Les calculs individuels et collectifs doivent donner le même résultat pour les mêmes données.

### Salaires

- Le salaire horaire dépend des heures retenues et du taux horaire ; les pointages sont prioritaires selon le moteur existant.
- Le forfait est calculé au prorata de la date d’embauche.
- Salaire net = salaire de base + primes − déductions − avances.
- La ventilation conserve exactement le nombre d’heures total à la précision du modèle.
- Les arrondis utilisent les valeurs décimales et les états déjà validés restent protégés par les règles existantes.

## Validation

- Référence avant correction : **560 tests réussis**.
- Nouveaux tests de calcul : **18 tests réussis après correction**. Les scénarios avant correction avaient reproduit 27 échecs d’assertions, dont plusieurs variantes d’un même défaut. Un scénario supplémentaire a d’abord confirmé le refus normal d’un paiement dépassant le solde, puis a été reformulé pour tester une baisse de tarif.
- Suite complète après correction : **578 tests réussis** en 931.528 secondes.
- Migrations appliquées intégralement sur la base isolée ; **aucune migration supplémentaire à créer**.

Les tests utilisent une base SQLite en mémoire et un répertoire temporaire dédié. Les données réelles de l’établissement n’ont pas été modifiées. Cette validation automatisée ne constitue pas une vérification manuelle de tous les écrans ni du service déployé.

Traces locales : `logs/audit_initial_20260915.log`, `logs/audit_calculs_avant_20260915.log`, `logs/audit_calculs_apres_20260915.log`, `logs/audit_final_20260915.log`, `logs/audit_migrations_20260915.log`.

Tests ajoutés : `notes/tests_calculs_audit.py`, `salaires/tests_calculs_audit.py`, `paiements/tests/test_audit_calculs.py`.
