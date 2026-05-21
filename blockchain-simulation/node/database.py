import sqlite3
name = "blockchain.db"


# =========================
# CREATION DATABASE
# =========================

def create_db():

    connection = sqlite3.connect(name) #crée automatiquement la base de données vide si elle n'existe pas et s'y connecte
    cursor = connection.cursor() # crée le curseur pour exécuter les commandes SQL et pour parcourir les lques de résultats

    cursor.execute("CREATE TABLE IF NOT EXISTS nodes (id INTEGER PRIMARY KEY AUTOINCREMENT,node_name TEXT UNIQUE NOT NULL,address TEXT UNIQUE NOT NULL)")
    #crée la table nodes si elle n'existe pas déjà avec les colonnes id, node_name et address qui id qui augmente automatiquement et node_name et address qui sont uniques et ne peuvent pas être null
    
    connection.commit() #enregistre les modifications dans la base de donné
    connection.close() #puis ferme connection à la base de données


# =========================
# ENREGISTREMENT DES NODES
# =========================

def add_node(node_name, address):
    connection = sqlite3.connect(name) #se reco a la db
    cursor = connection.cursor() #recrée donc le curseur pour exectuer la commande sql

    cursor.execute("INSERT OR IGNORE INTO nodes (node_name, address) VALUES (?, ?)", (node_name, address)) 
    #Ajout du "OR IGNORE" pour éviter les erreurs quand on essaye d'insérer un noeud qui existe déjà dans la DB.
    #OR IGNORE vérifie si il y a un doublon et si c'est le cas il ignore l'insertion.

    connection.commit()
    connection.close()
    #insère un nouveau noeud dans la table nodes crée au dessus avec les valeurs de node_name et address
    #clarification ici on a éviter de mettre avec un f string du type f"INSERT INTO nodes (node_name, address) VALUES ({node_name}, {address})" pour éviter les injections SQL
    # les ? sont des valeurs qui seront remplacés par les valeurs fournies juste après qui doivent être des string
    #https://docs.python.org/3/library/sqlite3.html#sqlite3-placeholders


# =========================
# RECUPERATION DES DONNEES
# =========================

def get_nodes():
    connection = sqlite3.connect(name) 

    connection.row_factory = sqlite3.Row #transforme les résultats de fetchall() en objets row des sortes de dictionnaire ou quand on
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM nodes ORDER BY id") #récupère tous les noeuds de la table nodes triés par id
    #on doit les retransformer en liste de dictionnaire car Flask ne travaille pas avec des objets Row mais avec des dictionnaires python


    rows = cursor.fetchall() #va nous servir avec la commande SQL SELECT, le fetchall() récupère les résultats de SELECT et les stocke sous forme de liste d'objets Row grace à la ligne connection.row_factory = sqlite3.Row.
    nodes = [] #initalisation de la liste qui va stocker les noeuds en dictionnaire


    for i in rows: #pour toutes les lignes dans le fetchall():
        node = dict(i) #convertit la ligne de résultats d'un objet Row en dictionnaire
        nodes.append(node) #ajout du dictionnaire de noeud à la liste nodes

    connection.close() #ferme la connexion à la base de données

    return nodes #retourne la grande liste de dictionnaire

    


