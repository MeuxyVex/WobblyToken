# =========================
# VARIABLES ET IMPORTS
# =========================


from flask import Flask, request, jsonify, render_template #flask permet de crée un serveur au node.
import requests #permet d'envoyer des requetes http
import os #utilisé pour lire les fichiers config docker
import time #juste pour faire une pause à la fin du script et pour calculer le temps de minage des blocks
import hashlib #permet de faire du hashage pour le minage des blocks
import json #permet de convertir les blocks en json pour le hashage et l'envoie entre les nodes
from wallet import walletcreation #import des fonctions utilisés de wallet
from transaction import validation_transaction_utxo, mempool, create_coinbase, validation_coinbase, creer_transaction_utxo #import des fonctions utilisés de transaction
from utxos import generateur_utxos, calculer_solde, appliquer_transaction_aux_utxos #import des fonctions utilisés de utxos
from network import dataweb
app = Flask(__name__) #initialise le serveur web

NODE_NAME = os.getenv("NODE_NAME") #recup dans le fichier .yml  le nom du node 
REGISTRY_URL = os.getenv("REGISTRY_URL") #recup dans le fichier .yml l'url du registre pour s'enregistrer et récupérer les autres nodes
PEER = os.getenv("PEER") #recup dans le fichier .yml l'adresse de la peer pour communiquer avec elle et s'y synchroniser

WALLET_PATH = os.getenv("WALLET_PATH", "/app/wallet/wallet.json") #recup dans le fichier .yml le chemin du wallet pour stocker les clés privées et publiques du node
nodewallet = walletcreation(WALLET_PATH) #création du wallet du node pour stocker les clés privées et publiques du node
miner_address = nodewallet["address"] #récupération de la clé publique du node pour l'utiliser dans les transactions 

blockchain = [] #init de la liste des block
temps = 10 #on veut que le block soit miner environ tte les 10 secondes pour éviter le ddosage du réseau, pour que les nodes aient le temps de se sycro et pour que les transactions aient le temps d'être ajoutées à la mempool et prises en compte dans les blocks minés
intervaldifficulty = 5 #interval de 5 blocks pour l'augmentation de la difficulté 
min_difficulty = 1 #difficulté minimale pour éviter d'avoir une difficulté de 0 ou négative
COIN = 100000000 #valeur d'un petit coin inspiré du satoshi de bitcoin il équivaut à 0.00000001 Wobblytoken pour éviter d'avoir des nombres à virgules et pour que les transactions soient plus faciles à gérer
BaseReward = 50 * COIN #basereward en petit wobblytoken pour éviter d'avoir des nombres à virgules et pour que les transactions soient plus faciles à gérer
IntervalReward = 10 # Interval de 10 blocks

# =========================
# DEFINITION FONCTIONS
# =========================

def hash_calcul(block):
    copie_block = block.copy() #copie du block pour ne pas modifier le block original
    copie_block.pop("hash", None) #on enlève la clé "hash" du block sinon on a un cercle vicieux pour calculer le hash du block
    copie_block.pop("time", None) #on enlève la clé "time" du block pour que le temps de minage ne soit pas pris en compte dans le hash du block on veut que il n'y ait que le nounce qui varie
    block_json = json.dumps(copie_block, sort_keys=True) #convertit le block en json pour le hashage en ordre alphabétique des clés pour que le hash soit toujours le même pour le même block
    return hashlib.sha256(block_json.encode()).hexdigest() #calcul du hash du block en utilisant la fonction sha256 de la bibliothèque hashlib et en encodant le json du block en octets -> hashlib celon la doc qu'avec des octets

def get_difficulty(chaine=None):
    if chaine is None:
        chaine = blockchain

    if len(chaine) == 0:
        return 4

    last_difficulty = chaine[-1]["difficulty"]

    if len(chaine) % intervaldifficulty != 0:
        return last_difficulty

    intervalle_des_blocs = chaine[-intervaldifficulty:]

    temps_calcule = 0

    for block in intervalle_des_blocs:
        temps_calcule += block["time"]

    temps_attendu = temps * intervaldifficulty
    ratio = temps_calcule / temps_attendu

    if ratio < 0.9:
        return last_difficulty + 1

    if ratio > 1.1:
        return max(min_difficulty, last_difficulty - 1)

    return last_difficulty


def get_block_reward(i):
    multiplier = i // IntervalReward # i est la variable qui prendra le numéro du block qu'on divise par l'interval pour nous donner le coef de la récompense donc pour savoir a quel palier on est
    reward = BaseReward // (2 ** multiplier) # on divise la reward par 2 puissance le coef pour faire une récompense qui diminue de moitié tous les 10 blocks
    return max(1, reward) # limite à 1 la rewrad la plus basse on renvoit le plus grand de reward ou de 1 pour éviter d'avoir une récompense de 0 ou de 0.5 etc... 



# =========================
# FONCTION PRINCIPAL ET BOUCLE PRINCIPAL
# =========================

def create_block(data): #création du block
    index = len(blockchain) #num du block

    if len(blockchain) > 0:
        dernier_bloc = blockchain[-1] #recupération dans la liste blockchain du dernier block
        prev_hash = dernier_bloc["hash"] #recup la valeur hash du dictionnaire du dernier block fait
    else:
        prev_hash = "0" #formation du tout premier block

    reward = get_block_reward(index)
    coinbase = create_coinbase(position=index, miner_address=miner_address, reward=reward)

    block = { #dictionnaire des data du block
        "index": index, #num du block
        "data": data, #data du block, dans notre cas le nom du node qui a miné le block
        "previous_hash": prev_hash,
        "nonce": 0,
        "hash": "", #valeurr du hash 
        "difficulty": get_difficulty(), #nombre de 0 que doit commencer le hash pour que le block soit valide
        "time": 0, #temps de minage du block
        "transactions": [coinbase] + mempool.copy(), #on ajoute les transactions en attente de validation dans la mempool au block pour qu'elles soient prises en compte dans le minage du block et pour que les transactions soient validées et ajoutées à la blockchain
    }

    starttime = time.perf_counter() #démarrage compteur

    while True:
        hash1 = hash_calcul(block) #calcul du hash du block avec la fonction hash_calcul
        if hash1.startswith("0" * block["difficulty"]): #vérifie si le hash du block commence par le nombre de 0 requis par la difficulté du block pour être valide
            block["hash"] = hash1 #si le hash est valide on l'ajoute au block
            break #on sort de la boucle while pour arrêter le minage du block
        block["nonce"] += 1 #sinon on incrémente le nonce pour changer le hash du block et essayer à nouveau de trouver un hash valide
    

    endtime = time.perf_counter() #fin compteur
    block["time"] = endtime - starttime #calcul du temps de minage du block
    return block                  



def validation_bloc(block, chaine_reference=None):
    if chaine_reference is None:
        chaine_reference = blockchain

    if not isinstance(block, dict):
        return False, "Bloc invalide"

    champs_requis = [
        "index",
        "data",
        "previous_hash",
        "nonce",
        "hash",
        "difficulty",
        "time",
        "transactions"
    ]

    for champ in champs_requis:
        if champ not in block:
            return False, f"Champ de bloc manquant : {champ}"

    # Vérifier la position du bloc
    index_attendu = len(chaine_reference)

    if (
        isinstance(block["index"], bool) or not isinstance(block["index"], int) or block["index"] != index_attendu):
        return False, "Index du bloc invalide"

    # Vérifier le lien avec le bloc précédent
    if len(chaine_reference) == 0:
        previous_hash_attendu = "0"
    else:
        previous_hash_attendu = chaine_reference[-1]["hash"]

    if block["previous_hash"] != previous_hash_attendu:
        return False, "Hash précédent invalide"

    # Vérifier la difficulté
    difficulte_attendue = get_difficulty(chaine_reference)

    if (isinstance(block["difficulty"], bool) or not isinstance(block["difficulty"], int) or block["difficulty"] != difficulte_attendue):
        return False, "Difficulté invalide"

    # Vérifier le nonce de minage
    if (isinstance(block["nonce"], bool) or not isinstance(block["nonce"], int) or block["nonce"] < 0):
        return False, "Nonce du bloc invalide"

    # Recalculer le hash
    hash_attendu = hash_calcul(block)

    if block["hash"] != hash_attendu:
        return False, "Hash du bloc invalide"

    # Vérifier la Proof of Work
    if not block["hash"].startswith("0" * block["difficulty"]):
        return False, "Proof of Work invalide"

    # Vérifier la liste des transactions
    transactions = block["transactions"]

    if (not isinstance(transactions, list) or len(transactions) == 0):
        return False, "Le bloc doit contenir des transactions"

    coinbase = transactions[0]

    resultat_coinbase = validation_coinbase(coinbase, position_attendue=block["index"], recompense_attendue=get_block_reward(block["index"]))

    if not resultat_coinbase[0]:
        return False, resultat_coinbase[1]

    # Reconstruire les UTXO précédant le nouveau bloc
    utxos_temporaires = generateur_utxos(chaine_reference)

    # Valider les transactions normales dans l'ordre
    transaction_index = 1

    while transaction_index < len(transactions):
        transaction = transactions[transaction_index]

        # Interdire une deuxième coinbase
        if transaction.get("type") == "coinbase":
            return False, "Plusieurs coinbases dans le bloc"

        resultat_transaction = validation_transaction_utxo(transaction, utxos_temporaires)

        if not resultat_transaction[0]:
            return False, resultat_transaction[1]

        try:
            utxos_temporaires = (appliquer_transaction_aux_utxos(transaction, utxos_temporaires))
        except ValueError as erreur:
            return False, str(erreur)

        transaction_index += 1

    # Ajouter la coinbase seulement après les transactions normales.
    # Elle ne peut donc pas être dépensée dans le même bloc.
    utxos_temporaires = appliquer_transaction_aux_utxos(coinbase, utxos_temporaires)

    return True, "Bloc valide"



def validation_blockchain(chaine_candidate):
    if not isinstance(chaine_candidate, list):
        return False, "La blockchain doit être une liste"

    if len(chaine_candidate) == 0:
        return False, "La blockchain reçue est vide"

    chaine_validee = []
    position = 0

    for block in chaine_candidate:
        resultat_validation = validation_bloc(block, chaine_reference=chaine_validee)

        if not resultat_validation[0]:
            return False, (f"Bloc {position} invalide : {resultat_validation[1]}")

        chaine_validee.append(block)
        position += 1

    return True, "Blockchain valide"

# =========================
# PARTIE FLASK
# =========================

#Méthode GET : Lire, récupérér des données, etc...
#Méthode POST : Créer une qql chose, envoyer des données, modifier une variable, etc...

# =========================
# PARTIE MINAGE ET BLOCKCHAIN
# =========================

@app.route("/") #quand on va à l'adresse racine du serveur web du node affiche la page index.html
def home():
    return render_template("index.html", node_name = NODE_NAME, peer = get_peers(), registry_url = REGISTRY_URL) #affiche la page index.html qui est dans le dossier templates du node


@app.route("/mine") #mine un block quand on va sur /mine
def mine():
    block = create_block(f"Block de {NODE_NAME}") #création du block avec le nom du node + appel de la fonction create_block pour le minage du block
    blockchain.append(block)

    mempool.clear() #on vide la mempool après avoir ajouté les transactions au block pour que les transactions soient prises en compte dans le block miné et pour que la mempool soit prête à recevoir de nouvelles transactions en attente de validation pour le prochain block à miner

    for i in get_peers(): #pour chaque peer dans la liste des peers récupérée du registre
        try:
            requests.post(f"{i}/receive_block", json=block, timeout=3) #envoie une requete http post à chaque peer pour lui envoyer le block miné et qu'il puisse l'ajouter à sa blockchain s'il est valide
        except:
            pass #si l'envoie du block échoue on ignore l'erreur

    return jsonify(block) #retourne le block sinon rien

@app.route("/receive_block", methods=["POST"])
def receive_block():
    block = request.get_json(silent=True)

    if not block:
        return {"status": "Refusé", "message": "Aucun bloc reçu"}, 400

    resultat_validation = validation_bloc(block)

    if not resultat_validation[0]:
        return {"status": "Refusé", "message": resultat_validation[1]}, 400

    blockchain.append(block)

    # Retirer de la mempool les transactions confirmées
    txids_confirmes = set()

    for transaction in block["transactions"]:
        if transaction["type"] != "coinbase":
            txids_confirmes.add(transaction["txid"])

    transactions_restantes = []

    for pending_transaction in mempool:
        if pending_transaction["txid"] not in txids_confirmes:
            transactions_restantes.append(pending_transaction)

    mempool.clear()
    mempool.extend(transactions_restantes)

    return {"status": "Accepté", "message": "Bloc valide ajouté à la blockchain"}, 200

@app.route("/chain") #quand on va à l'adresse /chain affiche toute la blockchain 
def get_chain():
    return jsonify(blockchain) #convertit la liste blockchain en json
    
@app.route("/sync")

def sync():
    global blockchain

    for peer in get_peers(): #prend la liste de tout ses peers récupérée du registre et pour chaque peer on va lui demander sa blockchain
        try:
            response = requests.get(f"{peer}/chain", timeout=3)

            if response.status_code != 200: #si le code de retour de la requete http n'est pas 200 "OK" on ignore le peer et on passe au suivant
                continue #le continue sert à passer a l'itération suivante de la boucle

            peer_chain = response.json() #convertit en json

            if not isinstance(peer_chain, list): #la blockchain doit être une liste sinon on ignore
                continue

            if len(peer_chain) <= len(blockchain): #la blockchain doit être plus longue que la notre sinon on ignore
                continue

            resultat_validation = validation_blockchain(peer_chain) #on verifie que la chaine est valide

            if not resultat_validation[0]:
                print(f"Chaîne refusée depuis {peer} : {resultat_validation[1]}") 
                #si la blockchain du peer n'est pas valide on affiche un message d'erreur dans le terminal du node
                continue

            # Remplacement seulement après validation complète
            blockchain = peer_chain

            # Temporairement, vider la mempool après une synchronisation car on est peut être en retard 
            # sur les transactions déjà validés
            mempool.clear()

        except requests.RequestException as erreur: #gestion des erreurs flask
            print(f"Erreur de synchronisation avec {peer} : {erreur}")

        except ValueError: #erreur de type réponse par exemple un string au lieu d'un json
            print(f"Réponse JSON invalide reçue depuis {peer}")
    return jsonify(blockchain)

# =========================
# PARTIE NETWORK
# =========================

@app.route("/network")
def network():
    return jsonify(dataweb(NODE_NAME,REGISTRY_URL,blockchain,mempool,get_peers))



# =========================
# PARTIE TRANSACTIONS
# =========================

@app.route("/utxos", methods=["GET"])
def afficher_utxos():
    utxos = generateur_utxos(blockchain)

    return jsonify(utxos)

@app.route("/balance/<address>", methods=["GET"])
def afficher_solde(address):
    utxos = generateur_utxos(blockchain)
    solde = calculer_solde(address, utxos)

    return jsonify({"address": address, "balance": solde})

@app.route("/wallet", methods=["GET"])
def get_wallet():
    return jsonify({"address": nodewallet["address"], "public_key": nodewallet["public_key"]})

@app.route("/transaction", methods=["GET"]) #affiche les transactions en attente de validation dans la memepool
def get_transactions():
    return jsonify(mempool) #convertit la memepool en json pour l'afficher


def ajouter_transaction_mempool(tx, utxos):
    if isinstance(tx, dict):
        for pending_transaction in mempool:
            if pending_transaction["txid"] == tx.get("txid"):
                return False, "Transaction déjà présente dans la mempool"

    resultat_validation = validation_transaction_utxo(tx, utxos)
    valeurbool = resultat_validation[0]
    message = resultat_validation[1]

    if not valeurbool:
        return False, message

    inputs_mempool = set()

    for pending_transaction in mempool:
        for pending_input in pending_transaction["inputs"]:
            pending_key = f'{pending_input["txid"]}:{pending_input["output_index"]}'
            inputs_mempool.add(pending_key)

    for transaction_input in tx["inputs"]:
        utxo_key = f'{transaction_input["txid"]}:{transaction_input["output_index"]}'

        if utxo_key in inputs_mempool:
            return False, "UTXO déjà utilisé dans la mempool"

    mempool.append(tx)
    return True, "Transaction ajoutée à la mempool"


def propager_transaction(tx, source=None):
    adresse_actuelle = f"http://{NODE_NAME}:5000"
    pairs_contactes = 0

    for peer in get_peers():
        if peer == source:
            continue

        try:
            response = requests.post(
                f"{peer}/receive_transaction",
                json={"transaction": tx, "source": adresse_actuelle},
                timeout=3
            )

            if 200 <= response.status_code < 300:
                pairs_contactes += 1
            else:
                print(f"Transaction refusée par {peer} : HTTP {response.status_code}")
        except requests.RequestException as erreur:
            print(f"Impossible de propager la transaction vers {peer} : {erreur}")

    return pairs_contactes


@app.route("/transaction", methods=["POST"]) #quand on envoie une requete http post à l'adresse /transaction on ajoute la transaction à la memepool
def add_transaction():
    tx = request.get_json(silent=True)#recup la transaction envoyée par le client en json
    
    if not tx:
        return {"status": "Erreur", "message": "Aucune transaction reçue"}, 400 #si aucune transaction n'est reçue on retourne une erreur 400 "Bad Request"
    
    utxos = generateur_utxos(blockchain)
    succes, message = ajouter_transaction_mempool(tx, utxos)

    if not succes:
        return {"status": "Erreur", "message": message}, 400

    pairs_contactes = propager_transaction(tx)

    return {
        "status": "Succès",
        "message": f"{message} et propagée à {pairs_contactes} pair(s)",
        "transaction": tx,
        "pairs_contactes": pairs_contactes
    }, 200


@app.route("/receive_transaction", methods=["POST"])
def recevoir_transaction():
    donnees = request.get_json(silent=True)

    if not isinstance(donnees, dict) or not isinstance(donnees.get("transaction"), dict):
        return {"status": "Erreur", "message": "Transaction manquante"}, 400

    tx = donnees["transaction"]
    source = donnees.get("source")

    if source is not None and not isinstance(source, str):
        return {"status": "Erreur", "message": "Source invalide"}, 400

    utxos = generateur_utxos(blockchain)
    succes, message = ajouter_transaction_mempool(tx, utxos)

    if not succes:
        if message == "Transaction déjà présente dans la mempool":
            return {"status": "Ignorée", "message": message}, 200

        return {"status": "Erreur", "message": message}, 400

    pairs_contactes = propager_transaction(tx, source=source)
    return {"status": "Succès", "message": "Transaction reçue et propagée", "pairs_contactes": pairs_contactes}, 200


@app.route("/send", methods=["POST"])
def envoyer_transaction():
    donnees = request.get_json(silent=True)

    if not isinstance(donnees, dict):
        return {"status": "Erreur", "message": "Données manquantes"}, 400

    adresse = donnees.get("address")
    montant = donnees.get("amount")

    if not isinstance(adresse, str):
        return {"status": "Erreur", "message": "Adresse destinataire invalide"}, 400

    utxos = generateur_utxos(blockchain)
    utxos_reserves = set()

    for pending_transaction in mempool:
        for pending_input in pending_transaction["inputs"]:
            utxos_reserves.add(f'{pending_input["txid"]}:{pending_input["output_index"]}')

    try:
        tx = creer_transaction_utxo(nodewallet, adresse, montant, utxos, utxos_reserves)
    except (ValueError, KeyError, TypeError) as erreur:
        return {"status": "Erreur", "message": str(erreur)}, 400

    succes, message = ajouter_transaction_mempool(tx, utxos)

    if not succes:
        return {"status": "Erreur", "message": message}, 400

    pairs_contactes = propager_transaction(tx)

    return {
        "status": "Succès",
        "message": f"{message} et propagée à {pairs_contactes} pair(s)",
        "transaction": tx,
        "pairs_contactes": pairs_contactes
    }, 200


def enregistrement():
    try:
        requests.post(f"{REGISTRY_URL}/register", json={"node_name": NODE_NAME, "address": f"http://{NODE_NAME}:5000"}, timeout=3)
        #envoie une requete http post au registre pour s'enregistrer dans la base de données du registre avec le nom du node et son adresse
    except:
        return False #si l'enregistrement échoue on retourne False pour pouvoir réessayer plus tard dans la boucle principale
    return True #si l'enregistrement réussit on retourne True

def get_peers():
    try:
        retour = requests.get(f"{REGISTRY_URL}/peers/{NODE_NAME}", timeout=3).json() #envoie une requete http get au registre pour récupérer la liste de tous les noeuds enregistrés dans la base de données du registre
        
        peers =[]

        for i in retour["peers"]: #pour chaque noeud dans la liste de tous les noeuds récupérés du registre
            peers.append(i["address"]) #on ajoute l'adresse du noeud à la liste des peers pour pouvoir communiquer avec lui
        return peers #retourne la liste des peers pour que le node puisse communiquer avec eux et s'y synchroniser
        
    except Exception as e :
        print(f"Erreur lors de la récupération des peers : {e}")
        return [] #si la récupération échoue on retourne une liste vide
    

if __name__ == "__main__":  #code executé quand on lance :
    time.sleep(3)  # attendre que l'autre node démarre 
    enregistrement()
    app.run(host="0.0.0.0", port=5000) #lance le serveur accesible depuis docker sur le port 5000
 
