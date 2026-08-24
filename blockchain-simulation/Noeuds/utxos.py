
def generateur_utxos(blockchain): #la fonction reçoit chaque block de la blockchain

    utxos = {}

    for block in blockchain:
        for transaction in block["transactions"]: #elle regarde les transactions de chaque block (mempool liste des transactions et coinbase la récompense du mineur)
            for transaction_input in transaction["inputs"]: #elle regarde les inputs de chaque transaction pour supprimer les utxos dépensés
                previous_txid = transaction_input["txid"] #prend l'identifiant de la transaction précédente qui a été dépensée
                previous_output_index = transaction_input["output_index"] #prend l'index de l'output de la transaction précédente qui a été dépensée

                utxo_key = f"{previous_txid}:{previous_output_index}" #construit la clé de l'utxo à supprimer en combinant l'identifiant de la transaction précédente et l'index de l'output dépensé
                utxos.pop(utxo_key, None) #supprime l'utxo dépensé de la liste des utxos disponibles, si il existe sinon ne fait rien

            # Ajouter les nouveaux outputs
            txid = transaction["txid"] 
            output_index = 0

            for output in transaction["outputs"]: #on parcourt maintenant les outputs de la transaction pour ajouter les nouveaux utxos disponibles
                utxo_key = f"{txid}:{output_index}" #on construit la clé de l'utxo à ajouter en combinant l'identifiant de la transaction et l'index de l'output
                utxos[utxo_key] = output #on assigne l'output à la clé de l'utxo dans le dictionnaire des utxos disponibles

                output_index += 1

    return utxos



def calculer_solde(address, utxos):
    solde = 0
    #parcourt tout les utxos et regarde si l'adresse de l'utxo correspond à l'adresse du wallet du node, si c'est le cas on ajoute le montant de l'utxo au solde du wallet du node
    for utxo in utxos.values(): #.values() permet de récupérer les valeurs du dictionnaire utxos, qui sont les outputs des transactions
        if utxo["address"] == address: 
            solde += utxo["amount"] 

    return solde


def appliquer_transaction_aux_utxos(transaction, utxos):
    # Travailler sur une copie pour ne pas modifier
    # l'état officiel avant la validation complète du bloc
    nouveaux_utxos = utxos.copy()

    # Supprimer les UTXO consommés
    for transaction_input in transaction["inputs"]:
        previous_txid = transaction_input["txid"]
        previous_output_index = transaction_input["output_index"]

        utxo_key = (f"{previous_txid}:{previous_output_index}")

        if utxo_key not in nouveaux_utxos:
            raise ValueError("Impossible d'appliquer un input inexistant")

        nouveaux_utxos.pop(utxo_key)

    # Ajouter les nouveaux outputs
    txid = transaction["txid"]
    output_index = 0

    for output in transaction["outputs"]:
        utxo_key = f"{txid}:{output_index}"

        nouveaux_utxos[utxo_key] = output.copy()

        output_index += 1

    return nouveaux_utxos