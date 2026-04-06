import ecdsa
import json
from hashlib import sha256


mempool = [] #liste des transactions en attente de validation par les nodes

# ================================================
# GENERATIONS DE CLE ET D'ADRESSE
# ================================================

def generationkeys():
    private_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1) #génère une clé privée à l'aide de la courbe SECP256k1
    public_key = private_key.get_verifying_key() #génère la clé publique correspondante à partir de la clé privée
    
    return {
        "private_key": private_key.to_string().hex(), #retourne la clé privée sous forme de string hexadécimale
        "public_key": public_key.to_string().hex()
    }

def generation_addresse(public_key_hexa): #convertion de clé en adresse utilisable
    hashage = sha256(bytes.fromhex(public_key_hexa)).hexdigest() #Hashage de la clé publique pour générer l'adresse du wallet
    return hashage

def syntaxe(tx): 

    message = {
        "sender_address": tx["sender_address"],
        "sender_public_key": tx["sender_public_key"],
        "receiver_address": tx["receiver_address"],
        "amount": tx["amount"]


    }
    return json.dumps(message, sort_keys=True).encode() #convertit le message en JSON et encode en octets pour la signature

def signature(tx, private_key_hexa): #génère la signature d'une transaction à l'aide de la clé privée
    private_key = ecdsa.SigningKey.from_string(bytes.fromhex(private_key_hexa),curve=ecdsa.SECP256k1) #convertit la clé privée hexadécimale en objet de clé privée utilisable
    message = syntaxe(tx) #génère le message à signer à partir de la transaction
    signature = private_key.sign(message) #génère la signature du message à l'aide de la clé privée
    return signature.hex() #retourne la signature sous forme de string hexadécimale



# ================================================
# VERIFICATION DE LA TRANSACTION
# ================================================

def validation(tx):
    requirements = [ #liste des champs requis pour une transaction valide
        "sender_address",
        "sender_public_key",
        "receiver_address",
        "amount",
        "signature"
    ]

    for i in requirements: #verification des champs requis dans la transaction
        if i not in tx:
            return False, "Champs manquants"
    
    if not isinstance(tx["amount"], (int, float)) or tx["amount"] <= 0: #verification que le montant est un nombre positif
        return False, "Montant invalide"
    
    adresse_attendu = generation_addresse(tx["sender_public_key"]) #verification que l'adresse de l'expéditeur correspond à la clé publique fournie
    if adresse_attendu != tx["sender_address"]:
        return False, "Adresse de l'expéditeur ne correspond pas à la clé publique"
    
    try:
        public_key = ecdsa.VerifyingKey.from_string(bytes.fromhex(tx["sender_public_key"]), curve=ecdsa.SECP256k1) #convertit le string dans la clé publique en octets puis ces octets en un objet clé publique ecdsa
        message = syntaxe(tx) #génération du message à vérifier à partir de la transaction
        verification = public_key.verify(bytes.fromhex(tx["signature"]), message) #vérification que la signature correspond à la clé publique déclaré et le contenu de la transaction
        if not verification:
            return False, "Signature invalide"
        
    except ecdsa.BadSignatureError: #gestion de l'erreur de signature invalide
        return False, "Signature invalide"
    except Exception:
        return False, "Erreur"
    
    return True, "Transaction valide"
