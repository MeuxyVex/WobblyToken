#syncro des chaines avec le travail cumulé

#permet d'envoyer des requetes http
import requests

from blockchain import calculer_travail_chaine, valider_chaine


def synchroniser_chaine(chaine, transactions_en_attente, obtenir_pairs):
    #on garde la chaine valide qui a le plus de travail cumulé, pas forcément la plus longue
    #obtenir_pairs est la fonction qui récup les adresse des peers
    #met à jour la liste locale et la retourne, vide la mempool si la chaine change
    meilleure_chaine = None

    meilleur_travail = calculer_travail_chaine(chaine)

    #prend la liste de tout ses peers récupérée du registre et pour chaque peer on va lui demander sa blockchain
    for pair in obtenir_pairs():
        try:
            reponse = requests.get(f"{pair}/chain", timeout=3)

            #si le code de retour de la requete http n'est pas 200 "OK" on ignore le peer et on passe au suivant
            if reponse.status_code != 200:
                #le continue sert à passer a l'itération suivante de la boucle
                continue

            #récupère la réponse json sous forme de liste python
            chaine_pair = reponse.json()

            #la blockchain doit être une liste sinon on ignore
            if not isinstance(chaine_pair, list):
                continue

            #on verifie que la chaine est valide
            resultat_validation = valider_chaine(chaine_pair)

            if not resultat_validation[0]:
                #si la blockchain du peer n'est pas valide on affiche un message d'erreur dans le terminal du node
                print(f"Chaîne refusée depuis {pair} : {resultat_validation[1]}")
                continue

            travail_chaine = calculer_travail_chaine(chaine_pair)

            #si le travail est égal on garde la chaine déjà choisie
            if travail_chaine > meilleur_travail:
                meilleure_chaine = chaine_pair
                meilleur_travail = travail_chaine

        #gestion des erreurs de requetes http
        except requests.RequestException as erreur:
            print(f"Erreur de synchronisation avec {pair} : {erreur}")

        #si la réponse du peer n'est pas du json valide
        except ValueError:
            print(f"Réponse JSON invalide reçue depuis {pair}")

    # remplacement seulement après validation complète
    if meilleure_chaine is not None:
        #clear vide la même liste, extend y ajoute chaque bloc de la meilleure chaine
        #les autres fonctions gardent la même liste et voient donc le changement
        chaine.clear()

        chaine.extend(meilleure_chaine)


        # temporairement, vider la mempool après une synchro car on est peut être en retard
        # sur les transaction déjà validés
        #clear retire toutes les transactions de la liste existante
        transactions_en_attente.clear()

    return chaine
