#routes du node et démarrage du serveur

#utilisé pour lire les fichiers config docker
import os
#juste pour faire une pause à la fin du script
import time
from urllib.parse import quote

#permet d'envoyer des requetes http
import requests
#flask permet de crée un serveur au node.
from flask import Flask, jsonify, render_template, request

from blockchain import creer_bloc, valider_bloc
from consensus import synchroniser_chaine
from network import obtenir_donnees_reseau
#import des fonction utilisés de transaction
from transaction import (
    creer_transaction_utxo,
    calculer_identifiant_transaction,
    signer_depense_contrat,
    transactions_en_attente,
    valider_transaction_utxo,
)
#import des fonctions utilisés de utxos
from utxos import appliquer_transaction_aux_utxos, calculer_solde, reconstruire_utxos
#import des fonctions utilisés de wallet
from wallet import charger_ou_creer_portefeuille


#initialise le serveur web
application = Flask(__name__)


#recup dans le fichier .yml  le nom du node
NOM_NOEUD = os.getenv("NODE_NAME")
#recup dans le fichier .yml l'url du registre pour s'enregistrer et récupérer les autre nodes
URL_REGISTRE = os.getenv("REGISTRY_URL")
#recup dans le fichier .yml l'adresse de la peer pour communiquer avec elle et s'y synchroniser
ADRESSE_PAIR = os.getenv("PEER")
#recup dans le fichier .yml le chemin du wallet pour stocker les clés privées et publiques du node
CHEMIN_PORTEFEUILLE = os.getenv("WALLET_PATH", "/app/wallet/wallet.json")

#création du wallet du node pour stocker les clés privées et publiques du node
portefeuille_noeud = charger_ou_creer_portefeuille(CHEMIN_PORTEFEUILLE)
#récupération de l'adresse du node pour recevoir la récompense du minage
adresse_mineur = portefeuille_noeud["address"]


#init de la liste des block
chaine = []




#méthode GET : Lire, récupérér des donnée, etc...
#méthode POST : Créer une qql chose, envoyer des données, modifier une variable, etc...
#quand on va à l'adresse racine du serveur web du node affiche la page index.html
@application.route("/", endpoint="home")
def afficher_accueil():
    #affiche la page d'accueil
    #affiche la page index.html qui est dans le dossier templates du node
    return render_template(
        "index.html", node_name=NOM_NOEUD, peer=obtenir_pairs(), registry_url=URL_REGISTRE
    )


#mine un block quand on va sur /mine
@application.route("/mine", endpoint="mine")
def miner_bloc():
    #mine le block et l'envoie aux peers
    #on revérifie les transactions car une syncro peut avoir changé les utxos ou la hauteur

    utxos_temporaires = reconstruire_utxos(chaine)

    transactions_valides = []
    #copy crée une liste séparée mais garde les même transactions dedans
    for transaction in transactions_en_attente.copy():
        resultat_validation = valider_transaction_utxo(
            transaction, utxos_temporaires, hauteur_bloc=len(chaine)
        )
        valide = resultat_validation[0]
        if valide:
            transactions_valides.append(transaction)
            utxos_temporaires = appliquer_transaction_aux_utxos(transaction, utxos_temporaires)

    #création du block avec le nom du node + appel de creer_bloc pour le minage
    bloc = creer_bloc(
        f"Block de {NOM_NOEUD}", chaine, transactions_valides, adresse_mineur
    )
    resultat_validation = valider_bloc(bloc, chaine)
    valide = resultat_validation[0]
    message = resultat_validation[1]
    if not valide:
        return {"status": "Refusé", "message": message}, 409
    chaine.append(bloc)
    #on vide la mempool après avoir ajouté les transactions au block pour que les transactions soient prises en compte dans le block miné et pour que la mempool soit prête à recevoir de nouvelles transactions en attente de validation pour le prochain block à miner
    #clear vide la liste existante, les autre fonctions voient aussi le changement
    transactions_en_attente.clear()

    #pour chaque peer dans la liste des peers récupérée du registre
    for pair in obtenir_pairs():
        try:
            #envoie une requete http post à chaque peer pour lui envoyer le block miné et qu'il puisse l'ajouter à sa blockchain s'il est valide
            requests.post(f"{pair}/receive_block", json=bloc, timeout=3)
        except:

            #si l'envoie du block échoue on ignore l'erreur
            pass

    #retourne le block sinon rien
    return jsonify(bloc)


@application.route("/receive_block", methods=["POST"], endpoint="receive_block")
def recevoir_bloc():
    #on valide le block reçu avant de l'ajouter
    bloc = request.get_json()

    if not bloc:
        return {"status": "Refusé", "message": "Aucun bloc reçu"}, 400

    resultat_validation = valider_bloc(bloc, chaine)

    if not resultat_validation[0]:
        return {"status": "Refusé", "message": resultat_validation[1]}, 400

    chaine.append(bloc)

    # retirer de la mempool les transactions confirmées
    identifiants_confirmes = set()

    for transaction in bloc["transactions"]:
        if transaction["type"] != "coinbase":
            identifiants_confirmes.add(transaction["txid"])

    transactions_restantes = []

    for transaction_en_attente in transactions_en_attente:
        if transaction_en_attente["txid"] not in identifiants_confirmes:
            transactions_restantes.append(transaction_en_attente)

    #clear vide la même liste puis extend ajoute les transaction restantes une par une
    transactions_en_attente.clear()

    transactions_en_attente.extend(transactions_restantes)

    return {"status": "Accepté", "message": "Bloc valide ajouté à la blockchain"}, 200


#quand on va à l'adresse /chain affiche toute la blockchain
@application.route("/chain", endpoint="get_chain")
def afficher_chaine():
    #retourne toute la chaine en json
    #convertit la liste blockchain en json
    return jsonify(chaine)


@application.route("/sync", endpoint="sync")
def synchroniser():
    #lance la syncro avec les autres nodes
    synchroniser_chaine(chaine, transactions_en_attente, obtenir_pairs) #sychroniser_chaine peut appeler obtenir_pairs()

    return jsonify(chaine)


@application.route("/network", endpoint="network")
def afficher_reseau():
    #données du réseau pour la page web
    return jsonify(
        obtenir_donnees_reseau(
            NOM_NOEUD, URL_REGISTRE, chaine, transactions_en_attente, obtenir_pairs
        )
    )




@application.route("/utxos", methods=["GET"])
def afficher_utxos():
    #retourne les utxos de la chaine locale
    utxos = reconstruire_utxos(chaine)

    return jsonify(utxos)


@application.route("/balance/<adresse>", methods=["GET"])
def afficher_solde(adresse):
    #solde confirmé de l'adresse en petites unités
    utxos = reconstruire_utxos(chaine)

    solde = calculer_solde(adresse, utxos)
    return jsonify({"address": adresse, "balance": solde})


@application.route("/wallet", methods=["GET"], endpoint="get_wallet")
def afficher_portefeuille():
    #on retourne seulement l'adresse et la clé publique, pas la clé privée
    return jsonify({
        "address": portefeuille_noeud["address"],
        "public_key": portefeuille_noeud["public_key"],
    })


#affiche les transaction en attente de validation dans la memepool
@application.route("/transaction", methods=["GET"], endpoint="get_transactions")
def afficher_transactions():
    #transactions encore en attente dans la mempool
    #convertit la memepool en json pour l'afficher
    return jsonify(transactions_en_attente)


def ajouter_transaction_en_attente(transaction, utxos):
    #vérifie la transaction et réserve ses utxos dans la mempool
    #retourne le résultat et un msg, aucun ajout si la tx est refusée
    if isinstance(transaction, dict):
        for transaction_en_attente in transactions_en_attente:
            if transaction_en_attente["txid"] == transaction.get("txid"):
                return False, "Transaction déjà présente dans la mempool"

    resultat_validation = valider_transaction_utxo(
        transaction, utxos, hauteur_bloc=len(chaine)
    )

    est_valide = resultat_validation[0]
    message = resultat_validation[1]

    if not est_valide:
        return False, message

    #évite de réserver le même utxo dans deux tx en attente
    entrees_reservees = set()

    for transaction_en_attente in transactions_en_attente:
        for entree_en_attente in transaction_en_attente["inputs"]:
            cle_reservee = f'{entree_en_attente["txid"]}:{entree_en_attente["output_index"]}'
            entrees_reservees.add(cle_reservee)

    for entree in transaction["inputs"]:
        cle_utxo = f'{entree["txid"]}:{entree["output_index"]}'

        if cle_utxo in entrees_reservees:
            return False, "UTXO déjà utilisé dans la mempool"

    transactions_en_attente.append(transaction)

    return True, "Transaction ajoutée à la mempool"


def propager_transaction(transaction, source=None):
    #envoie aux peers sauf celui qui nous a envoyé la transaction
    #retourne le nb de peers qui ont accepté la requete
    adresse_actuelle = f"http://{NOM_NOEUD}:5000"

    pairs_contactes = 0

    for pair in obtenir_pairs():
        if pair == source:
            continue

        try:
            reponse = requests.post(
                f"{pair}/receive_transaction",
                json={"transaction": transaction, "source": adresse_actuelle},
                timeout=3,
            )

            if reponse.status_code >= 200 and reponse.status_code < 300:
                pairs_contactes += 1
            else:
                print(f"Transaction refusée par {pair} : HTTP {reponse.status_code}")
        except requests.RequestException as erreur:
            print(f"Impossible de propager la transaction vers {pair} : {erreur}")

    return pairs_contactes


#quand on envoie une requete http post à l'adresse /transaction on ajoute la transaction à la memepool
@application.route("/transaction", methods=["POST"], endpoint="add_transaction")
def ajouter_transaction():
    #reçoit une transaction signée et la partage si elle est valide
    #recup la transaction envoyée par le client en json
    transaction = request.get_json(silent=True)

    if not transaction:
        #si aucune transaction n'est reçue on retourne une erreur 400 "Bad Request"
        return {"status": "Erreur", "message": "Aucune transaction reçue"}, 400

    utxos = reconstruire_utxos(chaine)

    resultat_ajout = ajouter_transaction_en_attente(transaction, utxos)
    succes = resultat_ajout[0]
    message = resultat_ajout[1]

    if not succes:
        return {"status": "Erreur", "message": message}, 400

    pairs_contactes = propager_transaction(transaction)

    return {
        "status": "Succès",
        "message": f"{message} et propagée à {pairs_contactes} pair(s)",
        "transaction": transaction,
        "pairs_contactes": pairs_contactes,
    }, 200


@application.route("/receive_transaction", methods=["POST"])
def recevoir_transaction():
    #si on a déjà cette transaction on ne la renvoie pas encore aux peers
    donnees = request.get_json(silent=True)

    if not isinstance(donnees, dict) or not isinstance(donnees.get("transaction"), dict):
        return {"status": "Erreur", "message": "Transaction manquante"}, 400

    transaction = donnees["transaction"]

    source = donnees.get("source")

    if source is not None and not isinstance(source, str):
        return {"status": "Erreur", "message": "Source invalide"}, 400

    utxos = reconstruire_utxos(chaine)

    resultat_ajout = ajouter_transaction_en_attente(transaction, utxos)
    succes = resultat_ajout[0]
    message = resultat_ajout[1]

    if not succes:
        if message == "Transaction déjà présente dans la mempool":
            return {"status": "Ignorée", "message": message}, 200

        return {"status": "Erreur", "message": message}, 400

    pairs_contactes = propager_transaction(transaction, source=source)
    return {
        "status": "Succès",
        "message": "Transaction reçue et propagée",
        "pairs_contactes": pairs_contactes,
    }, 200


@application.route("/send", methods=["POST"])
def envoyer_transaction():
    #prépare et signe l'envoi avec le wallet de ce node
    donnees = request.get_json(silent=True)

    if not isinstance(donnees, dict):
        return {"status": "Erreur", "message": "Données manquantes"}, 400

    adresse = donnees.get("address")

    montant = donnees.get("amount")
    contrat = donnees.get("contract")

    if "contract" in donnees and (contrat is None or "address" in donnees):
        return {"status": "Erreur", "message": "Choisir une adresse ou un contrat valide"}, 400

    if contrat is None and not isinstance(adresse, str):
        return {"status": "Erreur", "message": "Adresse destinataire invalide"}, 400

    utxos = reconstruire_utxos(chaine)
    utxos_reserves = set()

    for transaction_en_attente in transactions_en_attente:
        for entree_en_attente in transaction_en_attente["inputs"]:
            utxos_reserves.add(
                f'{entree_en_attente["txid"]}:{entree_en_attente["output_index"]}'
            )

    try:
        transaction = creer_transaction_utxo(
            portefeuille_noeud, adresse, montant, utxos, utxos_reserves, contrat=contrat
        )
    except (ValueError, KeyError, TypeError) as erreur:
        return {"status": "Erreur", "message": str(erreur)}, 400

    resultat_ajout = ajouter_transaction_en_attente(transaction, utxos)
    succes = resultat_ajout[0]
    message = resultat_ajout[1]

    if not succes:
        return {"status": "Erreur", "message": message}, 400

    pairs_contactes = propager_transaction(transaction)

    return {
        "status": "Succès",
        "message": f"{message} et propagée à {pairs_contactes} pair(s)",
        "transaction": transaction,
        "pairs_contactes": pairs_contactes,
    }, 200




@application.route("/contracts/sign", methods=["POST"])
def signer_contrat():
    #on signe ici mais la diffusion se fait séparément
    #retourne la tx signée et le résultat de sa verif
    #la tx peut encore manquer d'autres signatures
    donnees = request.get_json(silent=True)

    if not isinstance(donnees, dict) or not isinstance(donnees.get("transaction"), dict):
        return {"status": "Erreur", "message": "Transaction manquante"}, 400
    utxos = reconstruire_utxos(chaine)

    try:
        operation = signer_depense_contrat(donnees["transaction"], portefeuille_noeud, utxos)
    except (ValueError, TypeError, KeyError, AttributeError) as erreur:
        return {"status": "Erreur", "message": str(erreur)}, 400
    resultat_validation = valider_transaction_utxo(operation, utxos, hauteur_bloc=len(chaine))
    valide = resultat_validation[0]
    message = resultat_validation[1]
    return {"transaction": operation, "valid": valide, "message": message}, 200


@application.route("/contracts/check", methods=["POST"])
def verifier_depense_contrat():
    #recalcule le txid et vérifie le brouillon sans le diffuser
    #verif pour le prochain bloc, sans réserver les utxos
    donnees = request.get_json(silent=True)

    if not isinstance(donnees, dict) or not isinstance(donnees.get("transaction"), dict):
        return {"status": "Erreur", "message": "Transaction manquante"}, 400
    operation = donnees["transaction"]

    if type(operation.get("version")) is not int or operation["version"] != 2:
        return {"status": "Erreur", "message": "Transaction de version 2 attendue"}, 400
    operation["txid"] = calculer_identifiant_transaction(operation)
    resultat_validation = valider_transaction_utxo(
        operation, reconstruire_utxos(chaine), hauteur_bloc=len(chaine)
    )
    valide = resultat_validation[0]
    message = resultat_validation[1]
    return {"transaction": operation, "valid": valide, "message": message}, 200


@application.route("/registry", defaults={"chemin": ""}, methods=["GET"])
@application.route("/registry/<path:chemin>", methods=["GET", "POST"])
def consulter_registre(chemin):
    #la page passe par le node pour contacter les routes du registre
    lecture = chemin in ("", "nodes") or (
        chemin.startswith("peers/") and len(chemin.split("/")) == 2
        and chemin[6:] not in ("", ".", "..")
    )

    if not ((request.method == "GET" and lecture) or (request.method == "POST" and chemin == "register")):
        return {"message": "Route du registre non autorisée"}, 404
    if not URL_REGISTRE:
        return {"message": "Adresse du registre non configurée"}, 503

    try:
        if request.method == "POST":
            donnees = request.get_json(silent=True)
            if not isinstance(donnees, dict):
                return {"message": "Objet JSON attendu"}, 400
            reponse = requests.post(f"{URL_REGISTRE}/register", json=donnees, timeout=3)
        else:
            #le nom du node doit rester un seul morceau de l'url
            if chemin.startswith("peers/"):
                suffixe = "peers/" + quote(chemin[6:], safe="")
            else:
                suffixe = chemin
            reponse = requests.get(f"{URL_REGISTRE}/{suffixe}", timeout=3)
        return jsonify(reponse.json()), reponse.status_code
    except (requests.RequestException, ValueError):
        return {"message": "Le registre est indisponible ou sa réponse est invalide"}, 502




def enregistrer_noeud():
    #enregistrement du node dans le registre
    try:
        #envoie une requete http post au registre pour s'enregistrer dans la base de données du registre avec le nom du node et son adresse
        requests.post(
            f"{URL_REGISTRE}/register",
            json={"node_name": NOM_NOEUD, "address": f"http://{NOM_NOEUD}:5000"},
            timeout=3,
        )
    except:
        #si l'enregistrement échoue on retourne False
        return False

    #si l'enregistrement réussit on retourne True
    return True


def obtenir_pairs():
    #récupère les peer dans le registre, liste vide si la requete échoue
    try:
        #envoie une requete http get au registre pour récupérer les voisins de ce node
        reponse_registre = requests.get(
            f"{URL_REGISTRE}/peers/{NOM_NOEUD}", timeout=3
        ).json()

        pairs = []

        #pour chaque noeud dans la liste de tous les noeuds récupérés du registre
        for pair in reponse_registre["peers"]:
            #on ajoute l'adresse du noeud à la liste des peer pour pouvoir communiquer avec lui
            pairs.append(pair["address"])

        #retourne la liste des peers pour que le node puisse communiquer avec eux et s'y synchroniser
        return pairs

    except Exception as erreur:
        print(f"Erreur lors de la récupération des peers : {erreur}")

        #si la récupération échoue on retourne une liste vide
        return []


#code executé quand on lance :
if __name__ == "__main__":

    # attendre que l'autre node démarre
    time.sleep(3)
    enregistrer_noeud()
    #lance le serveur accesible depuis docker sur le port 5000
    application.run(host="0.0.0.0", port=5000)
