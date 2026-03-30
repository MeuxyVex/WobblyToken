
from flask import Flask, request, jsonify #flask permet de crée un serveur au node.
import requests #permet d'envoyer des requetes http
import os #utilisé pour lire les fichiers config docker
import time #juste pour faire une pause à la fin du script
import hashlib #permet de faire du hashage pour le minage des blocks
import json #permet de convertir les blocks en json pour le hashage et l'envoie entre les nodes
from wallet import validate_transaction, mempool

app = Flask(__name__) #initialise le serveur web

NODE_NAME = os.getenv("NODE_NAME") #recup dans le fichier .yml  le nom du node 
PEER = os.getenv("PEER") #recup l'adresse http de l'autre node

blockchain = [] #init de la liste des block
temps = 10 #on veut que le block soit miner environ tte les 10 secondes pour éviter le ddosage du réseau, pour que les nodes aient le temps de se sycro et pour que les transactions aient le temps d'être ajoutées à la mempool et prises en compte dans les blocks minés
interval = 5 #interval de 5 blocks pour l'augmentation de la difficulté 
min_difficulty = 1 #difficulté minimale pour éviter d'avoir une difficulté de 0 ou négative
BaseReward = 50 # récompense de base, la plus haute
Interval = 10 # Interval de 10 blocks

def get_difficulty():
        if len(blockchain) == 0:
            return 5 #si c'est le premier block on met une difficulté de 5
        
        last_difficulty = blockchain[-1]["difficulty"] #récupère la difficulté du dernier block ou 5 si c'est le premier block
        
        if len(blockchain) % interval != 0: #nombre total de block dans la blockchain modulo l'interval de 5 blocks pour savoir si on doit augmenter la difficulté ou pas
            return last_difficulty
        
        Intervaldesblock = blockchain[-interval:] #récupère les 5 derniers blocks pour calculer le temps de minage moyen blockchain[-5:] donne les 5 derniers éléments de la liste blockchain
        temps_calculé = sum(block["time"] for block in Intervaldesblock) #additionne le temps de minage de ces 5 blocks.
        temps_attendu = temps * interval
        ratio = temps_calculé / temps_attendu #calcul du ratio pour voir si le minage est trop difficile ou pas
        if ratio < 0.9:
            return last_difficulty + 1 #augemente la difficulté de 1 pour rendre le minage plus difficile si le temps de minage est trop court, on veut que le temps de minage soit proche de 10 secondes pour éviter le ddosage du réseau et pour que les nodes aient le temps de se sycro et pour que les transactions aient le temps d'être ajoutées à la mempool et prises en compte dans les blocks minés
        elif ratio > 1.1:
            return max(min_difficulty, last_difficulty - 1) #diminue la difficulté de 1 mais pas en dessous de la difficulté minimale pour éviter d'avoir une difficulté de 0 ou négative
        else:
            return last_difficulty #si le ratio est entre 0.9 et 1.1 on garde la même difficulté pour maintenir un temps de minage stable autour de 10 secondes

def get_block_reward(i):
    multiplier = i // Interval # i est le numéro du block qu'on divise par l'interval pour nous donner le coef de la récompense donc pour savoir a quel palier on est
    reward = BaseReward / (2 ** multiplier) # on divise la reward par 2 puissance le coef pour faire une récompense qui diminue de moitié tous les 10 blocks
    return max(1, reward) # limite à 1 la rewrad la plus basse on renvoit le plus grand de reward ou de 1 pour éviter d'avoir une récompense de 0 ou de 0.5 etc... 



def create_block(data): #création du block
    index = len(blockchain) #num du block

    if len(blockchain) > 0:
        dernier_bloc = blockchain[-1] #recupération dans la liste blockchain du dernier block
        prev_hash = dernier_bloc["hash"] #recup la valeur hash du dictionnaire du dernier block fait
    else:
        prev_hash = "0" #formation du tout premier block

    block = { #dictionnaire des data du block
        "index": index, #num du block
        "data": data, #data du block, dans notre cas le nom du node qui a miné le block
        "previous_hash": prev_hash,
        "nonce": 0,
        "hash": "", #valeurr du hash 
        "difficulty": get_difficulty(), #nombre de 0 que doit commencer le hash pour que le block soit valide
        "time": 0, #temps de minage du block
        "transactions": [],
        "reward": get_block_reward(index)
    }

    starttime = time.perf_counter()

    while block["hash"][0:block["difficulty"]] != "0" * block["difficulty"]: #avec la variable difficulty on peut faire varier la difficulté du minage du block en changeant le nombre de 0 que doit commencer le hash pour que le block soit valide
        blockjson = (json.dumps(block, sort_keys=True)) #convertit le block en json pour le hashage
        block["hash"] = (hashlib.sha256((blockjson).encode()).hexdigest()) #tant que les 4 premier caractères du hash ne sont pas 0000 on incrémente le nonce et on recalcule le hash 
        block["nonce"] += 1 #incrémetation du nonce pour faire varier le hash et trouver un hash qui commence par 0000
    endtime = time.perf_counter()
    block["time"] = endtime - starttime #calcul du temps de minage du block
    
    return block                  

@app.route("/mine") #mine un block quand on va sur /mine
def mine():
    block = create_block(f"Block de {NODE_NAME}") #création du block avec le nom du node + appel de la fonction create_block pour le minage du block
    blockchain.append(block)

    try:
        requests.post(f"{PEER}/receive_block", json=block) #envoie le block son format json http à l'autre node à l'adresse de la peer sur /receiveblock  
    except:
        pass

    return block #retourne le block sinon rien

@app.route("/receive_block", methods=["POST"]) 
def receive_block():
    block = request.json  # recup le block 

    if len(blockchain) == 0:
        blockchain.append(block)
        return {"status": "Accepté"} #si la blockchain est vide on accepte automatiquement le premier block

    dernier_bloc = blockchain[-1] #sinon on récupère le dernier block

    
    if block["previous_hash"] == dernier_bloc["hash"]:
        blockchain.append(block) #est-ce que le hash précédent annoncé par le nouveau block correspond bien au hash de MON dernier block ?
        return {"status": "Accepté"}
    else: #sinon on le refuse
        return {"status": "Refusé"} #retour en dictionnaire pour que ce soit plus lisible et retour parceque sa aide a debug

@app.route("/chain") #quand on va à l'adresse /chain affiche toute la blockchain 
def get_chain():
    return jsonify(blockchain) #convertit la liste blockchain en json
    
@app.route("/sync") #récupère la block chain de l'autre node 
def sync():
    try:
        peer_chain = requests.get(f"{PEER}/chain").json() #demande toute la blockchain à l'autre node
        global blockchain #la liste blockchain est en dehors des fonctions et donc  si global n'est pas utilisé la valeur serait celle tout en haut donc [], rien
        if len(peer_chain) > len(blockchain):
            blockchain = peer_chain #si la blockchain de l'autre node est plus longue que la notre on la remplace par la sienne pour être à jour
    except:
        pass

    return blockchain


@app.route("/transaction", methods=["GET"]) #affiche les transactions en attente de validation dans la memepool
def get_transactions():
    return jsonify(mempool) #convertit la memepool en json pour l'afficher


@app.route("/transaction", methods=["POST"]) #quand on envoie une requete http post à l'adresse /transaction on ajoute la transaction à la memepool
def add_transaction():
    tx = request.get_json()#recup la transaction envoyée par le client en json
    
    if not tx:
        return {"status": "Erreur", "message": "Aucune transaction reçue"}, 400 #si aucune transaction n'est reçue on retourne une erreur 400 "Bad Request"
    
    if not validate_transaction(tx):
        return {"status": "Erreur", "message": "Transaction invalide"}, 400 #si la transaction reçue n'est pas valide on retourne une erreur 400 "Bad Request"

    #sinon
    mempool.append(tx) #on ajoute la transaction à la mempool pour qu'elle soit prise en compte dans le prochain block miné
    return {"status": "Succès", "message": "Transaction ajoutée au mempool"}, 200 #retour de succès code http 200 "OK" pour indiquer que la transaction a été ajoutée à la mempool


if __name__ == "__main__":  #code executé quand on lance :
    time.sleep(3)  # attendre que l'autre node démarre 
    app.run(host="0.0.0.0", port=5000) #lance le serveur accesible depuis docker sur le port 5000
 


