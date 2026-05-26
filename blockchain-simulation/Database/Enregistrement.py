from flask import Flask, request, jsonify
from database import *

app = Flask(__name__)

# =========================
# Root
# =========================


@app.route("/")
def root():
    return jsonify({"message": "Ceci est la database d'enregistrement !"})



# =========================
# Enregistrement
# =========================

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json() #récupère les données envoyées dans la requete POST et les convertit en dictionnaire python
    if not data:
        return jsonify({"message": "Aucune donnée reçue"}), 400 #retourne un message d'erreur si aucune donnée n'est reçue dans la requete POST
    
    node_name = data.get("node_name") #récupère le nom du noeud à partir du dictionnaire de données
    if not node_name:
        return jsonify({"message": "Le champ 'node_name' est requis"}), 400 #retourne un message d'erreur si le champ node_name est manquant dans la requete POST   
    
    address = data.get("address") #récupère l'adresse du noeud à partir du dictionnaire de données

    if not address:
        return jsonify({"message": "Le champ 'address' est requis"}), 400 #retourne un message d'erreur si le champ address est manquant dans la requete POST
    
    add_node(node_name, address) #ajoute le noeud à la base de données en utilisant la fonction add_node définie dans database.py

    return jsonify({"message": f"{node_name} enregistré avec succès !", "node": {"name": node_name, "address": address}}), 201 #retourne un message de succès si le noeud est enregistré avec succès


# =========================
# Recupération db
# =========================


@app.route("/nodes", methods=["GET"])
def get_all_nodes():
    return jsonify(get_nodes())


# =========================
# Récupération peer
# =========================


@app.route("/peers/<node_name>", methods=["GET"])
def peers(node_name):
    nodes = get_nodes() #récupère tous les noeuds enregistrés dans la base de données
    if len(nodes) == 0:
        return {"status": "Erreur", "message": "Aucun node enregistré"}, 404

    position = None

    for i in range(len(nodes)): #trouve la position du noeud dans la liste de tous les noeuds
        if nodes[i]["node_name"] == node_name:
            position = i
            break
    
    if position is None: #si le noeud n'est pas trouvé dans la liste de tous les noeuds
        return {"status": "Erreur", "message": f"Node {node_name} non trouvé"}, 404
    
    if len(nodes) == 1: #si il n'y a qu'un seul noeud enregistré dans la base de données
        return jsonify ({
            "node": node_name,
            "peers": [],
            "précédent": None,
            "suivant": None,
            "message": "Aucun autre node enregistré"
        })
    
    précédent = nodes[position -1]
    suivant = nodes[(position + 1) % len(nodes)] #Fermeture de la boucle quand on est au bout de la liste on revient au node1

    peers = []

    if précédent["node_name"] != node_name:
        peers.append(précédent)

    if suivant["node_name"] != node_name and suivant != précédent: #évite d'ajouter 2x le même peer si il l'anneau ne contient que 2 noeuds
        peers.append(suivant)

    return jsonify ({
        "node": node_name,
        "peers": peers,
        "précédent": précédent,
        "suivant": suivant
    })

if __name__ == "__main__":
    create_db() #crée la base de données et la table nodes si elle n'existe pas déjà
    app.run(host="0.0.0", port=6000) #démarre le serveur Flask sur le port 6000 et accepte les connexions depuis l'extérieur du conteneur