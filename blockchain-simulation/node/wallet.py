
mempool = [] #liste des transactions en attente de validation par les nodes

def validate_transaction(tx):
    return (
        "sender" in tx and
        "receiver" in tx and
        "amount" in tx and
        isinstance(tx["amount"], (int, float)) and
        tx["amount"] > 0
    )   
    

