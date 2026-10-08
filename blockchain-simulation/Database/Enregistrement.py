#registre des nodes et récupération de leurs voisins

from flask import Flask, request, jsonify

from database import creer_base_donnees, ajouter_noeud, obtenir_noeuds

application = Flask(__name__)


# root
@application.route("/", endpoint="root")
def afficher_accueil():
    #retourne le msg d'accueil du registre en json
    return jsonify({"message": "Ceci est la database d'enregistrement !"})


# enregistrement
@application.route("/register", methods=["POST"], endpoint="register")
def enregistrer_noeud():
    #enregistrement du node dans le registre
    #récupère les donnée envoyées dans la requete POST et les convertit en dictionnaire python
    donnees = request.get_json()

    if not donnees:
        #retourne un message d'erreur si aucune donnée n'est reçue dans la requete POST
        return jsonify({"message": "Aucune donnée reçue"}), 400

    #récupère le nom du noeud à partir du dictionnaire de données
    nom_noeud = donnees.get("node_name")

    if not nom_noeud:
        #retourne un message d'erreur si le champ node_name est manquant dans la requete POST
        return jsonify({"message": "Le champ 'node_name' est requis"}), 400

    #récupère l'adresse du noeud à partir du dictionnaire de données
    adresse = donnees.get("address")
    if not adresse:
        #retourne un message d'erreur si le champ address est manquant dans la requete POST
        return jsonify({"message": "Le champ 'address' est requis"}), 400

    #ajoute le noeud à la base avec ajouter_noeud définie dans database.py
    ajouter_noeud(nom_noeud, adresse)

    #retourne un message de succès si le noeud est enregistré avec succès
    return jsonify({
        "message": f"{nom_noeud} enregistré avec succès !",
        "node": {"name": nom_noeud, "address": adresse}
    }), 201


# recupération db
@application.route("/nodes", methods=["GET"], endpoint="get_all_nodes")
def lister_noeuds():
    #retourne la liste des nodes enregistrés
    return jsonify(obtenir_noeuds())


# récupération peer
@application.route("/peers/<nom_noeud>", methods=["GET"], endpoint="peers")
def obtenir_pairs_noeud(nom_noeud):
    #cherche les voisins du node dans l'anneau
    #récupère tous les noeud enregistrés dans la base de données
    noeuds = obtenir_noeuds()

    if len(noeuds) == 0:
        return {"status": "Erreur", "message": "Aucun node enregistré"}, 404

    position = None

    #trouve la position du noeud dans la liste de tous les noeuds
    for index_noeud in range(len(noeuds)):
        if noeuds[index_noeud]["node_name"] == nom_noeud:
            position = index_noeud
            break

    #si le noeud n'est pas trouvé dans la liste de tous les noeuds
    if position is None:
        return {"status": "Erreur", "message": f"Node {nom_noeud} non trouvé"}, 404

    #si il n'y a qu'un seul noeud enregistré dans la base de données
    if len(noeuds) == 1:
        return jsonify({
            "node": nom_noeud,
            "peers": [],
            "précédent": None,
            "suivant": None,
            "message": "Aucun autre node enregistré"
        })


    #si position vaut 0, l'indice -1 récup le dernier node
    noeud_precedent = noeuds[position - 1]

    #fermeture de la boucle quand on est au bout de la liste on revient au node1
    noeud_suivant = noeuds[(position + 1) % len(noeuds)]
    pairs = []

    if noeud_precedent["node_name"] != nom_noeud:
        pairs.append(noeud_precedent)


    #évite d'ajouter 2x le même peer si il l'anneau ne contient que 2 noeuds
    if noeud_suivant["node_name"] != nom_noeud and noeud_suivant != noeud_precedent:
        pairs.append(noeud_suivant)

    return jsonify({
        "node": nom_noeud,
        "peers": pairs,
        "précédent": noeud_precedent,
        "suivant": noeud_suivant
    })


if __name__ == "__main__":
    #crée la base de données et la table nodes si elle n'existe pas déjà
    creer_base_donnees()

    #démarre le serveur Flask sur le port 6000 et accepte les connexion depuis l'extérieur du conteneur
    application.run(host="0.0.0.0", port=6000)
