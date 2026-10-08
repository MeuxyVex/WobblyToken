#minage et vérification des blocks de la chaine

#permet de faire du hashage pour le minage des blocks
import hashlib
#permet de convertir les block en json pour le hashage et l'envoie entre les nodes
import json
#pour calculer le temps de minage des blocks
import time

#import des fonctions utilisés de transaction
from transaction import creer_coinbase, valider_coinbase, valider_transaction_utxo
#import des fonction utilisés de utxos
from utxos import appliquer_transaction_aux_utxos, reconstruire_utxos



#on veut que le block soit miner environ tte les 10 secondes pour éviter le ddosage du réseau, pour que les nodes aient le temps de se sycro et pour que les transactions aient le temps d'être ajoutées à la mempool et prises en compte dans les blocks minés
TEMPS_CIBLE_BLOC = 10
#interval de 5 blocks pour l'augmentation de la difficulté
INTERVALLE_AJUSTEMENT_DIFFICULTE = 5
#difficulté minimale pour éviter d'avoir une difficulté de 0 ou négative
DIFFICULTE_MINIMALE = 1


#nombre de petites unités dans 1 Wobblytoken pour éviter les nombres à virgules
UNITES_PAR_WOBBLYTOKEN = 100000000
#basereward en petit wobblytoken pour éviter d'avoir des nombre à virgules et pour que les transactions soient plus faciles à gérer
RECOMPENSE_INITIALE = 50 * UNITES_PAR_WOBBLYTOKEN
# interval de 10 blocks
INTERVALLE_REDUCTION_RECOMPENSE = 10


def calculer_hash_bloc(bloc):
    #calcul du hash sans les champs hash et time du block
    #copy copie le dict pour retirer des champs sans modifier le bloc original
    #les liste et dicts à l'intérieur restent partagés
    copie_bloc = bloc.copy()

    #on enlève la clé "hash" du block sinon on a un cercle vicieux pour calculer le hash du block
    copie_bloc.pop("hash", None)
    #on enlève la clé "time" du block pour que le temps de minage ne soit pas pris en compte dans le hash du block on veut que il n'y ait que le nounce qui varie
    copie_bloc.pop("time", None)

    #convertit le block en json pour le hashage en ordre alphabétique des clés pour que le hash soit toujours le même pour le même block
    bloc_json = json.dumps(copie_bloc, sort_keys=True)
    #calcul du hash du block en utilisant la fonction sha256 de la bibliothèque hashlib et en encodant le json du block en octets -> hashlib celon la doc qu'avec des octets
    return hashlib.sha256(bloc_json.encode()).hexdigest()


def obtenir_difficulte(chaine):
    #nombre de 0 demandé au début du hash du prochain block
    if len(chaine) == 0:
        return 4

    derniere_difficulte = chaine[-1]["difficulty"]

    #recalcul tous les 5 blocs selon la config, sinon on garde la difficulté
    if len(chaine) % INTERVALLE_AJUSTEMENT_DIFFICULTE != 0:
        return derniere_difficulte

    #récup seulement les dernier blocs de l'intervalle
    blocs_intervalle = chaine[-INTERVALLE_AJUSTEMENT_DIFFICULTE:]

    duree_cumulee = 0

    for bloc in blocs_intervalle:
        duree_cumulee += bloc["time"]

    duree_attendue = TEMPS_CIBLE_BLOC * INTERVALLE_AJUSTEMENT_DIFFICULTE

    rapport_durees = duree_cumulee / duree_attendue

    #plus de 10% trop rapide donc on augmente la difficulté
    if rapport_durees < 0.9:
        return derniere_difficulte + 1

    #plus de 10% trop lent donc on baisse sans passer sous le min
    if rapport_durees > 1.1:
        return max(DIFFICULTE_MINIMALE, derniere_difficulte - 1)

    return derniere_difficulte


def calculer_recompense_bloc(index_bloc):
    #calcul de la récompense suivant le numéro du block
    #on divise le numéro du block par l'interval pour savoir a quel palier de récompense on est
    nombre_reductions = index_bloc // INTERVALLE_REDUCTION_RECOMPENSE

    # on divise la reward par 2 puissance le coef pour faire une récompense qui diminue de moitié tous les 10 blocks
    recompense = RECOMPENSE_INITIALE // (2 ** nombre_reductions)
    # limite à 1 la rewrad la plus basse on renvoit le plus grand de reward ou de 1 pour éviter d'avoir une récompense de 0 ou de 0.5 etc...
    return max(1, recompense)


#création du block
def creer_bloc(donnees, chaine, transactions_en_attente, adresse_mineur):
    #création et minage du block, il sera ajouté à la chaine dans app.py
    #num du block
    index_bloc = len(chaine)

    if len(chaine) > 0:
        #recupération dans la liste blockchain du dernier block
        dernier_bloc = chaine[-1]
        #recup la valeur hash du dictionnaire du dernier block fait
        hash_precedent = dernier_bloc["hash"]
    else:
        #formation du tout premier block
        hash_precedent = "0"

    recompense = calculer_recompense_bloc(index_bloc)

    coinbase = creer_coinbase(
        position=index_bloc, adresse_mineur=adresse_mineur, recompense=recompense
    )


    #dictionnaire des data du block
    bloc = {
        #num du block
        "index": index_bloc,
        #data du block, dans notre cas le nom du node qui a miné le block
        "data": donnees,
        "previous_hash": hash_precedent,
        "nonce": 0,
        #valeurr du hash
        "hash": "",
        #nombre de 0 que doit commencer le hash pour que le block soit valide
        "difficulty": obtenir_difficulte(chaine),
        #temps de minage du block
        "time": 0,
        #on ajoute les transactions en attente de validation dans la mempool au block pour qu'elles soient prises en compte dans le minage du block et pour que les transactions soient validées et ajoutées à la blockchain
        #copy sépare la liste de la mempool mais pas les dict des transactions
        "transactions": [coinbase] + transactions_en_attente.copy(),
    }

    #démarrage chronomètre
    debut_minage = time.perf_counter()

    while True:
        #calcul du hash du block avec la fonction calculer_hash_bloc
        hash_bloc = calculer_hash_bloc(bloc)
        #vérifie si le hash du block commence par le nombre de 0 requis par la difficulté du block pour être valide
        if hash_bloc.startswith("0" * bloc["difficulty"]):
            #si le hash est valide on l'ajoute au block
            bloc["hash"] = hash_bloc
            #on sort de la boucle while pour arrêter le minage du block
            break
        #sinon on incrémente le nonce pour changer le hash du block et essayer à nouveau de trouver un hash valide
        bloc["nonce"] += 1

    #fin chronomètre
    fin_minage = time.perf_counter()

    #calcul du temps de minage du block
    bloc["time"] = fin_minage - debut_minage
    return bloc


def valider_bloc(bloc, chaine_reference):
    #vérifie le block par rapport à la chaine reçue en paramètre
    #retourne le résultat et un msg sans ajouter le bloc
    if not isinstance(bloc, dict):
        return False, "Bloc invalide"

    champs_requis = [
        "index", "data", "previous_hash", "nonce", "hash", "difficulty", "time",
        "transactions",
    ]

    for champ in champs_requis:
        if champ not in bloc:
            return False, f"Champ de bloc manquant : {champ}"

    # vérifier la position du bloc
    index_attendu = len(chaine_reference)

    if (
        isinstance(bloc["index"], bool)
        or not isinstance(bloc["index"], int)
        or bloc["index"] != index_attendu
    ):
        return False, "Index du bloc invalide"

    # vérifier le lien avec le bloc précédent
    if len(chaine_reference) == 0:
        hash_precedent_attendu = "0"
    else:
        hash_precedent_attendu = chaine_reference[-1]["hash"]

    if bloc["previous_hash"] != hash_precedent_attendu:
        return False, "Hash précédent invalide"

    # vérifier la difficulté
    difficulte_attendue = obtenir_difficulte(chaine_reference)

    if (
        isinstance(bloc["difficulty"], bool)
        or not isinstance(bloc["difficulty"], int)
        or bloc["difficulty"] != difficulte_attendue
    ):
        return False, "Difficulté invalide"

    # vérifier le nonce de minage
    if (
        isinstance(bloc["nonce"], bool)
        or not isinstance(bloc["nonce"], int)
        or bloc["nonce"] < 0
    ):
        return False, "Nonce du bloc invalide"

    # recalculer le hash
    hash_attendu = calculer_hash_bloc(bloc)

    if bloc["hash"] != hash_attendu:
        return False, "Hash du bloc invalide"

    # vérifier la Proof of Work
    if not bloc["hash"].startswith("0" * bloc["difficulty"]):
        return False, "Proof of Work invalide"

    # vérifier la liste des transactions
    transactions = bloc["transactions"]

    if not isinstance(transactions, list) or len(transactions) == 0:
        return False, "Le bloc doit contenir des transactions"

    coinbase = transactions[0]

    resultat_coinbase = valider_coinbase(
        coinbase,
        position_attendue=bloc["index"],
        recompense_attendue=calculer_recompense_bloc(bloc["index"]),
    )

    if not resultat_coinbase[0]:
        return False, resultat_coinbase[1]

    # reconstruire les UTXO précédant le nouveau bloc
    utxos_temporaires = reconstruire_utxos(chaine_reference)

    # valider les transactions normales dans l'ordre
    index_transaction = 1 #commence à 1 car le 0 est la coinbase qui a déjà été validée

    #chaque transaction reprend les utxo laissés par celle d'avant
    while index_transaction < len(transactions):
        transaction = transactions[index_transaction]

        # interdire une deuxième coinbase
        if isinstance(transaction, dict) and transaction.get("type") == "coinbase":
            return False, "Plusieurs coinbases dans le bloc"

        resultat_transaction = valider_transaction_utxo(
            transaction, utxos_temporaires, hauteur_bloc=bloc["index"]
        )

        if not resultat_transaction[0]:
            return False, resultat_transaction[1]

        try:
            utxos_temporaires = appliquer_transaction_aux_utxos(
                transaction, utxos_temporaires
            )
        except ValueError as erreur:
            return False, str(erreur)

        index_transaction += 1


    # ajouter la coinbase seulement après les transactions normales.
    # elle ne peut donc pas être dépensée dans le même bloc.
    utxos_temporaires = appliquer_transaction_aux_utxos(coinbase, utxos_temporaires)
    return True, "Bloc valide"


def valider_chaine(chaine_candidate):
    #vérifie les blocks un par un dans l'ordre
    #retourne le résultat et le msg du premier bloc refusé si il y en a un
    if not isinstance(chaine_candidate, list):
        return False, "La blockchain doit être une liste"

    if len(chaine_candidate) == 0:
        return False, "La blockchain reçue est vide"

    chaine_validee = []

    position = 0

    for bloc in chaine_candidate:
        resultat_validation = valider_bloc(bloc, chaine_reference=chaine_validee)

        if not resultat_validation[0]:
            return False, f"Bloc {position} invalide : {resultat_validation[1]}"

        chaine_validee.append(bloc)

        position += 1

    return True, "Blockchain valide"


def calculer_travail_chaine(chaine):
    #additionne le travail des block, la chaine doit déjà être validée
    #un zéro hexa en plus rend le hash env 16x plus rare
    #travail estimé, pas le nb réel d'essais du mineur
    travail_total = 0

    for bloc in chaine:
        travail_total += 16 ** bloc["difficulty"]

    return travail_total
