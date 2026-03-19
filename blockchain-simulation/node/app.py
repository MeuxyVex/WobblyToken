from flask import Flask, request, jsonify #flask permet de crée un serveur au node.
import requests #permet d'envoyer des requetes http
import os #utilisé pour lire les fichiers config docker
import time #juste pour faire une pause à la fin du script
import hashlib #permet de faire du hashage pour le minage des blocks
import json #permet de convertir les blocks en json pour le hashage et l'envoie entre les nodes
app = Flask(__name__) #initialise le serveur web

NODE_NAME = os.getenv("NODE_NAME") #recup dans le fichier .yml  le nom du node 
PEER = os.getenv("PEER") #recup l'adresse http de l'autre node

blockchain = [] #init de la liste des block

def create_block(data): #création du block
    index = len(blockchain) #num du block
    if len(blockchain) > 0:
        dernier_bloc = blockchain[-1] #recupération dans la liste blockchain du dernier block
        prev_hash = dernier_bloc["hash"] #recup la valeur hash du dictionnaire du dernier block fai
    else:
        prev_hash = "0" #formation du tout premier block

    block = { #dictionnaire des data du block
        "index": index,
        "data": data, #data va reprendre le nom du node pour différencier les blocks minés par les différents nodes
        "previous_hash": prev_hash,
        "nonce": 0,
        "hash": "123456789abcdef", #valeur de hash temporaire pour le minage du block
        "time": 0
    }
    starttime = time.perf_counter()
    while block["hash"][0:5] != "00000":
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

if __name__ == "__main__":  #code executé quand on lance :
    time.sleep(3)  # attendre que l'autre node démarre 
    app.run(host="0.0.0.0", port=5000) #lance le serveur accesible depuis docker sur le port 5000
 
