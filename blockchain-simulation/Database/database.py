#stockage des nodes dans la db sqlite

import sqlite3

CHEMIN_BASE_DONNEES = "data/blockchain.db"


def creer_base_donnees():
    #création de la db et de la table nodes si elles existent pas encore
    #crée automatiquement la base de données vide si elle n'existe pas et s'y connecte
    connexion = sqlite3.connect(CHEMIN_BASE_DONNEES)

    # crée le curseur pour exécuter les commande SQL et pour parcourir les lques de résultats
    curseur = connexion.cursor()


    #crée la table nodes si elle n'existe pas déjà avec les colonnes id, node_name et address qui id qui augmente automatiquement et node_name et address qui sont uniques et ne peuvent pas être null
    curseur.execute("CREATE TABLE IF NOT EXISTS nodes (id INTEGER PRIMARY KEY AUTOINCREMENT,node_name TEXT UNIQUE NOT NULL,address TEXT UNIQUE NOT NULL)")

    #enregistre les modifications dans la base de donné
    connexion.commit()

    #puis ferme connection à la base de données
    connexion.close()


def ajouter_noeud(nom_noeud, adresse):
    #ajoute le node à la db en ignorant les doublon
    #se reco a la db
    connexion = sqlite3.connect(CHEMIN_BASE_DONNEES)

    #recrée donc le curseur pour exectuer la commande sql
    curseur = connexion.cursor()


    #ajout du "OR IGNORE" pour éviter les erreurs quand on essaye d'insérer un noeud qui existe déjà dans la DB.
    #or IGNORE vérifie si il y a un doublon et si c'est le cas il ignore l'insertion.
    #insère un nouveau noeud dans la table nodes crée au dessus avec les valeurs de node_name et address
    #clarification ici on a éviter de mettre avec un f string du type f"INSERT INTO nodes (node_name, address) VALUES ({node_name}, {address})" pour éviter les injection SQL
    # les ? sont des valeurs qui seront remplacés par les valeurs fournies juste après qui doivent être des string
    #https://docs.python.org/3/library/sqlite3.html#sqlite3-placeholders
    curseur.execute(
        "INSERT OR IGNORE INTO nodes (node_name, address) VALUES (?, ?)",
        (nom_noeud, adresse)
    )

    connexion.commit()

    connexion.close()


def obtenir_noeuds():
    #récupère les nodes dans l'ordre de leur id
    connexion = sqlite3.connect(CHEMIN_BASE_DONNEES)

    #transforme les résultat de fetchall() en objets Row, des sortes de dictionnaire
    connexion.row_factory = sqlite3.Row
    curseur = connexion.cursor()

    #récupère tous les noeuds de la table nodes triés par id pour que le premier node ajouté soit le premier de la liste, etc..
    curseur.execute("SELECT * FROM nodes ORDER BY id")

    #on doit les retransformer en liste de dictionnaire car Flask ne travaille pas avec des objets Row mais avec des dictionnaires python
    #va nous servir avec la commande SQL SELECT, le fetchall() récupère les résultat de SELECT et les stocke sous forme de liste d'objets Row grace à la ligne connection.row_factory = sqlite3.Row.
    lignes = curseur.fetchall()
    #initalisation de la liste qui va stocker les noeuds en dictionnaire
    noeuds = []


    #pour toutes les ligne dans le fetchall():
    for ligne in lignes:
        #convertit la ligne de résultats d'un objet Row en dictionnaire
        noeud = dict(ligne)
        #ajout du dictionnaire de noeud à la liste nodes
        noeuds.append(noeud)

    #ferme la connexion à la base de données
    connexion.close()

    #retourne la grande liste de dictionnaire
    return noeuds
