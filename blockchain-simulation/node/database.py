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

    cursor.execute("INSERT INTO nodes (node_name, address) VALUES (?, ?)", (node_name, address)) 

    connection.commit()
    connection.close()
    #insère un nouveau noeud dans la table nodes crée au dessus avec les valeurs de node_name et address
    #clarification ici on a éviter de mettre avec un f string du type f"INSERT INTO nodes (node_name, address) VALUES ({node_name}, {address})" pour éviter les injections SQL
    # les ? sont des valeurs qui seront remplacés par les valeurs fournies juste après qui doivent être des string
    #https://docs.python.org/3/library/sqlite3.html#sqlite3-placeholders


# =========================
# RECUPERATION DES NODES
# =========================

def get_nodes():
    connection = sqlite3.connect(name) 
    cursor = connection.cursor()

    


