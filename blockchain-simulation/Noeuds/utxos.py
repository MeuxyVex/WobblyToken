#gestion des sortie pas encore dépensées


#la fonction reçoit chaque block de la blockchain
def reconstruire_utxos(chaine):
    #on reparcourt la chaine pour retrouver les utxos pas encore dépensés
    utxos = {}

    for bloc in chaine:
        #elle regarde les transactions de chaque block (mempool liste des transactions et coinbase la récompense du mineur)
        for transaction in bloc["transactions"]:

            #elle regarde les input de chaque transaction pour supprimer les utxos dépensés
            for entree in transaction["inputs"]:
                #prend l'identifiant de la transaction précédente qui a été dépensée
                identifiant_precedent = entree["txid"]

                #prend l'index de l'output de la transaction précédente qui a été dépensée
                indice_sortie_precedente = entree["output_index"]

                #construit la clé de l'utxo à supprimer en combinant l'identifiant de la transaction précédente et l'index de l'output dépensé
                reference_utxo = f"{identifiant_precedent}:{indice_sortie_precedente}"
                #supprime l'utxo dépensé de la liste des utxos disponibles, si il existe sinon ne fait rien
                utxos.pop(reference_utxo, None)

            # ajouter les nouveaux outputs
            identifiant_transaction = transaction["txid"]

            indice_sortie = 0

            #on parcourt maintenant les outputs de la transaction pour ajouter les nouveaux utxos disponibles
            for sortie in transaction["outputs"]:
                #on construit la clé de l'utxo à ajouter en combinant l'identifiant de la transaction et l'index de l'output
                reference_utxo = f"{identifiant_transaction}:{indice_sortie}"
                #on assigne l'output à la clé de l'utxo dans le dictionnaire des utxo disponibles
                utxos[reference_utxo] = sortie

                indice_sortie += 1

    return utxos


def calculer_solde(adresse, utxos):
    #additionne les fonds de cette adresse, sans les fonds sous contrat
    solde = 0

    #parcourt tout les utxos et regarde si l'adresse de l'utxo correspond à l'adresse du wallet du node, si c'est le cas on ajoute le montant de l'utxo au solde du wallet du node
    #.values() permet de récupérer les valeur du dictionnaire utxos, qui sont les outputs des transactions
    for utxo in utxos.values():
        if "contract" not in utxo and utxo.get("address") == adresse:
            solde += utxo["amount"]

    return solde


def appliquer_transaction_aux_utxos(transaction, utxos):
    #travaille sur une copie pour ne pas changer les utxos avant la validation
    # travailler sur une copie pour ne pas modifier
    # l'état officiel avant la validation complète du bloc
    #copy sépare le dict, supprimer une clé ici ne la supprime pas dans l'original
    #les sorties déjà présentes restent les mêmes objets
    nouveaux_utxos = utxos.copy()

    # supprimer les UTXO consommés
    for entree in transaction["inputs"]:
        identifiant_precedent = entree["txid"]

        indice_sortie_precedente = entree["output_index"]

        reference_utxo = f"{identifiant_precedent}:{indice_sortie_precedente}"

        if reference_utxo not in nouveaux_utxos:
            raise ValueError("Impossible d'appliquer un input inexistant")

        nouveaux_utxos.pop(reference_utxo)

    # ajouter les nouveaux outputs
    identifiant_transaction = transaction["txid"]

    indice_sortie = 0

    for sortie in transaction["outputs"]:
        reference_utxo = f"{identifiant_transaction}:{indice_sortie}"

        #copie les champ de la sortie, un contrat imbriqué reste partagé
        nouveaux_utxos[reference_utxo] = sortie.copy()

        indice_sortie += 1

    return nouveaux_utxos
