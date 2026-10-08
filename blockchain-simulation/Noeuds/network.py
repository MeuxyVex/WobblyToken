#infos du réseau pour la page html

import requests


def obtenir_donnees_reseau(
    nom_noeud, url_registre, chaine, transactions_en_attente, obtenir_pairs
):
    #récupération des infos du réseau pour les afficher dans la page html
    donnees = {
        "current_node": nom_noeud,
        "current_peers": obtenir_pairs(),
        "registry_url": url_registre,
        "blockchain_length": len(chaine),
        "mempool_size": len(transactions_en_attente),
        "nodes": [],
        "relations": [],
        "database": {
            "container": "registry",
            "engine": "SQLite",
            "file": "/app/data/blockchain.db",
            "volume": "registry-data"
        }
    }

    try:
        #demande a la db la liste des noeud enregistrés
        noeuds = requests.get(f"{url_registre}/nodes", timeout=3).json()

        #enregistre la liste des noeuds dans data -> le dictionnaire qui va être envoyer a la page html
        donnees["nodes"] = noeuds
        #liste pour éviter les doublons dans les relations entre les noeuds
        relations_recensees = []

        #pour chaque noeud dans la liste de tous les noeud récupérés de la db
        for noeud in noeuds:
            try:
                #fais une requete au registre pour récupérer les peers de chaque noeud
                donnees_pairs = requests.get(
                    f"{url_registre}/peers/{noeud['node_name']}", timeout=3
                ).json()

                for pair in donnees_pairs["peers"]:

                    #trie les noms des noeuds pour éviter les doublons dans les relations
                    noms_tries = sorted([noeud["node_name"], pair["node_name"]])

                    #crée une relation entre les deux noeud
                    relation = noms_tries[0] + " - " + noms_tries[1]

                    #si la relation n'est pas déjà dans la liste des relations
                    if relation not in relations_recensees:

                        #ajoute la relation entre les deux noeuds dans data
                        donnees["relations"].append({
                            "source": noeud["node_name"],
                            "target": pair["node_name"]
                        })
                        #ajoute la relation à la liste des relation pour éviter les doublons
                        relations_recensees.append(relation)
                        #ajoute la même relation avec les clés from et to pour la page html
                        donnees["relations"].append({
                            "from": noeud["node_name"],
                            "to": pair["node_name"]
                        })

            except:
                #si un peer pose problème on continue avec les autres
                pass

    except Exception as erreur:
        #retourne l'erreur dans data en string pour l'afficher dans la page html
        donnees["error"] = str(erreur)

    return donnees
