import requests

def dataweb(NODE_NAME, REGISTRY_URL, blockchain, mempool, get_peers):
    data = {
        "current_node": NODE_NAME,
        "current_peers": get_peers(),
        "registry_url": REGISTRY_URL,
        "blockchain_length": len(blockchain),
        "mempool_size": len(mempool),
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
        nodes = requests.get(f"{REGISTRY_URL}/nodes", timeout=3).json()#demande a la db la liste des noeuds enregistrés
        data["nodes"] = nodes #enregistre la liste des noeuds dans data -> le dictionnaire qui va être envoyer a la page html

        relationnodes = [] #liste pour éviter les doublons dans les relations entre les noeuds

        for node in nodes: #pour chaque noeud dans la liste de tous les noeuds récupérés de la db
            try:
                peer_data = requests.get(f"{REGISTRY_URL}/peers/{node['node_name']}",timeout=3).json()
                #fais un requte sur chaque noeud pour récupérer ses peers

                for peer in peer_data["peers"]:
                    sortednodes = sorted([node["node_name"], peer["node_name"]]) #trie les noms des noeuds pour éviter les doublons dans les relations
                    relation = sortednodes[0] + " - " + sortednodes[1] #crée une relation entre les deux noeuds

                    if relation not in relationnodes: #si la relation n'est pas déjà dans la liste des relations
                        data["relations"].append({"source": node["node_name"], "target": peer["node_name"]}) #ajoute la relation entre les deux noeuds dans data
                        relationnodes.append(relation) #ajoute la relation à la liste des relations pour éviter les doublons
                        data["relations"].append({"from": node["node_name"], "to": peer["node_name"]}) #ajoute la relation dans les deux sens a la data

            except:
                pass


    
    except Exception as e:
        data["error"] = str(e) #retourne l'erreur dans data en string pour l'afficher dans la page html

    return data


