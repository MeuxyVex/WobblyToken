
mempool = [] #liste des transactions en attente de validation par les nodes

def validate_transaction(tx):
    return (
        "sender" in tx and #tx est un dictionnaire qui doit contenir les clés "sender", "receiver" et "amount" pour être valide
        "receiver" in tx and
        "amount" in tx and
        isinstance(tx["amount"], (int, float)) and #dans tx "amout" doit être un nombre entier ou à virgule
        tx["amount"] > 0 #et plus grand que 0 logique.
    )   
    

