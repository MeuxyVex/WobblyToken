#chargement et sauvegarde du portefeuille local du noeud.

import json
import os #bibliothèque pour la gestion des fichier et des chemins

from .address import generer_adresse
from .keys import generer_cles


def charger_ou_creer_portefeuille(chemin):
    #charge le wallet existant sinon crée les clés et sauvegarde le fichier
    #retourne un dict avec les clés et l'adresse du wallet
    

    if os.path.exists(chemin): #charge le fichier si éxiste, utile si le noeud est redémarré
        with open(chemin, "r") as fichier:
            return json.load(fichier)

    dossier = os.path.dirname(chemin)

    if dossier: #crée le dossier si il n'existe pas, souvent si le noeud est lancé pour la première fois
        os.makedirs(dossier, exist_ok=True)

    cles = generer_cles()

    adresse = generer_adresse(cles["public_key"])

    portefeuille = {
        "private_key": cles["private_key"],
        "public_key": cles["public_key"],
        "address": adresse
    }

    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump(portefeuille, fichier, indent=2)

    # le fichier contient la clé privée : seul son propriétaire peut le lire et l'écrire.
    os.chmod(chemin, 0o600) #le chiffre est en octal et il permet de dire avec le chiffre 6 (4 + 2) que le propriétaire peut écrire et lire le fichier
    #et avec les deux autres zéros que les autres ne peuvent rien faire (ils ne pourront pas la lire ni l'écrire)
    #plus d'info : https://fr.wikipedia.org/wiki/Chmod
    return portefeuille
