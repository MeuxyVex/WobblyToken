import json
import ecdsa
import hashlib
import secrets
from wallet import generation_addresse, adress_validation
mempool = []


def transaction_id(tx):
    # Faire une copie de la transaction
    transaction_copy = tx.copy()

    # Retirer l'ancien txid s'il existe sinon None
    transaction_copy.pop("txid", None)

    # Transformer la transaction en texte JSON
    transaction_json = json.dumps(transaction_copy, sort_keys=True)

    # Calculer et retourner son hash
    transaction_hash = hashlib.sha256(transaction_json.encode()).hexdigest()
    return transaction_hash #qui sera utilisé comme identifiant unique de la transaction

def create_coinbase(position, miner_address, reward):
    transaction = {
        "type": "coinbase",
        "position": position,
        "inputs": [],
        "random_nonce" : secrets.token_hex(16),  # Génère un identifiant unique de 16 octets aléatoire pour la transaction qui sera utilisé pour éviter les doublons et pour lier la transaction à un block spécifique
        "outputs": [{"address": miner_address, "amount": reward}]
    }

    transaction["txid"] = transaction_id(transaction)

    return transaction


def construction_message_pour_signature(tx):
    inputs_sans_signature = []

    for transaction_input in tx["inputs"]:
        input_sans_signature = {
            "txid": transaction_input["txid"],
            "output_index": transaction_input["output_index"],
            "public_key": transaction_input["public_key"]
        }

        inputs_sans_signature.append(input_sans_signature)

    message = {
        "type": tx["type"],
        "inputs": inputs_sans_signature,
        "outputs": tx["outputs"]
    }

    return json.dumps(message, sort_keys=True).encode()


def signer_transaction_utxo(tx, private_key_hexa):
    private_key = ecdsa.SigningKey.from_string(bytes.fromhex(private_key_hexa), curve=ecdsa.SECP256k1)

    message = construction_message_pour_signature(tx)

    signature = private_key.sign_deterministic(message, hashfunc=hashlib.sha256)

    return signature.hex()


def creer_transaction_utxo(wallet, adresse_destinataire, montant, utxos, utxos_exclus=None):
    """Construit et signe une transaction à partir des UTXO du wallet du nœud."""
    resultat_adresse = adress_validation(adresse_destinataire)

    if not resultat_adresse[0]:
        raise ValueError(resultat_adresse[1])

    if isinstance(montant, bool) or not isinstance(montant, int) or montant <= 0:
        raise ValueError("Montant invalide")

    utxos_exclus = utxos_exclus or set()
    inputs = []
    total_selectionne = 0

    for utxo_key, output in utxos.items():
        if utxo_key in utxos_exclus or output["address"] != wallet["address"]:
            continue

        previous_txid, output_index = utxo_key.rsplit(":", 1)
        inputs.append({
            "txid": previous_txid,
            "output_index": int(output_index),
            "public_key": wallet["public_key"],
            "signature": ""
        })
        total_selectionne += output["amount"]

        if total_selectionne >= montant:
            break

    if total_selectionne < montant:
        raise ValueError("Solde disponible insuffisant")

    outputs = [{"address": adresse_destinataire, "amount": montant}]
    monnaie = total_selectionne - montant

    if monnaie > 0:
        outputs.append({"address": wallet["address"], "amount": monnaie})

    transaction = {
        "type": "standard",
        "inputs": inputs,
        "outputs": outputs
    }

    signature = signer_transaction_utxo(transaction, wallet["private_key"])

    for transaction_input in transaction["inputs"]:
        transaction_input["signature"] = signature

    transaction["txid"] = transaction_id(transaction)
    return transaction

# =========================
# PARTIE VALIDATION DES TRANSACTIONS
# =========================

def validation_transaction_utxo(transaction, utxos):
    # Vérifier la structure générale
    if not isinstance(transaction, dict):
        return False, "Transaction invalide"

    champs_requis = [
        "type",
        "inputs",
        "outputs",
        "txid"
    ]

    for champ in champs_requis:
        if champ not in transaction:
            return False, f"Champ manquant : {champ}"

    if transaction["type"] != "standard": #les transactions de type coinbase sont traitées séparément et ne nécessitent pas de validation des inputs et outputs
        return False, "Type de transaction invalide"

    if (not isinstance(transaction["inputs"], list) or len(transaction["inputs"]) == 0):
        return False, "La transaction doit avoir au moins un input"

    if (not isinstance(transaction["outputs"], list) or len(transaction["outputs"]) == 0):
        return False, "La transaction doit avoir au moins un output"

    total_inputs = 0
    total_outputs = 0
    inputs_utilises = set() #on crée un set pour stocker les UTXOs utilisés dans la transaction afin d'empêcher leur double utilisation car la propriété d'un set est de ne contenir que des éléments uniques, ce qui permet de vérifier facilement si un UTXO a déjà été utilisé dans la transaction.

    # Vérifier les inputs
    for transaction_input in transaction["inputs"]:
        champs_input = ["txid", "output_index", "public_key", "signature"]

        for champ in champs_input:
            if champ not in transaction_input:
                return False, f"Champ input manquant : {champ}"

        previous_txid = transaction_input["txid"]
        previous_output_index = transaction_input["output_index"]

        if not isinstance(previous_txid, str):
            return False, "txid d'input invalide"

        if (isinstance(previous_output_index, bool) or not isinstance(previous_output_index, int) or previous_output_index < 0):
            return False, "Index d'output invalide"

        utxo_key = (f"{previous_txid}:{previous_output_index}")

        # Empêcher deux utilisations du même UTXO
        if utxo_key in inputs_utilises:
            return False, "UTXO utilisé plusieurs fois"

        inputs_utilises.add(utxo_key)

        # Vérifier que l'UTXO existe encore
        if utxo_key not in utxos:
            return False, "UTXO inexistant ou déjà dépensé"

        utxo = utxos[utxo_key]

        # Vérifier que la clé publique possède l'UTXO
        try:
            expected_address = generation_addresse(transaction_input["public_key"]) 
        except (ValueError, TypeError):
            return False, "Clé publique invalide"

        if expected_address != utxo["address"]:
            return False, "La clé publique ne possède pas cet UTXO"

        # Vérifier la signature
        verification = verifier_signature_utxo(transaction, transaction_input)

        if not verification[0]:
            return False, verification[1]

        total_inputs += utxo["amount"]

    # Vérifier les nouveaux outputs
    for output in transaction["outputs"]:
        if "address" not in output or "amount" not in output:
            return False, "Output incomplet"

        resultat_adresse = adress_validation(output["address"])

        if not resultat_adresse[0]:
            return False, resultat_adresse[1]

        amount = output["amount"]

        if (isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0):
            return False, "Montant d'output invalide"

        total_outputs += amount

    # Empêcher la création de nouveaux fonds
    if total_outputs > total_inputs:
        return False, "Fonds insuffisants"

    # Vérifier l'identifiant de la transaction
    txid_attendu = transaction_id(transaction)

    if txid_attendu != transaction["txid"]:
        return False, "txid invalide"

    return True, "Transaction UTXO valide"

def verifier_signature_utxo(transaction, transaction_input):
    try:
        public_key = ecdsa.VerifyingKey.from_string(
            bytes.fromhex(transaction_input["public_key"]), curve=ecdsa.SECP256k1)

        signature = bytes.fromhex(transaction_input["signature"])

        message = construction_message_pour_signature(transaction)

        public_key.verify(signature, message, hashfunc=hashlib.sha256)

    except ecdsa.BadSignatureError: #erreur de signature invalide, la signature ne correspond pas à la clé publique et au message
        return False, "Signature invalide" 

    except (ValueError, TypeError, KeyError): #gestion des erreurs de conversion hexadécimale et de clé de dictionnaire manquante et de type incorrect
        return False, "Clé publique ou signature invalide"

    return True, "Signature valide"

def validation_coinbase(transaction, position_attendue, recompense_attendue):
    # Vérifier que la coinbase est un dictionnaire
    if not isinstance(transaction, dict):
        return False, "Coinbase invalide"

    champs_requis = [
        "type",
        "position",
        "random_nonce",
        "inputs",
        "outputs",
        "txid"
    ]

    # Vérifier la présence des champs
    for champ in champs_requis:
        if champ not in transaction:
            return False, f"Champ coinbase manquant : {champ}"

    # Vérifier le type
    if transaction["type"] != "coinbase":
        return False, "Type de coinbase invalide"

    # Vérifier la position du bloc
    if (isinstance(transaction["position"], bool) or not isinstance(transaction["position"], int) or transaction["position"] != position_attendue):
        return False, "Position de coinbase invalide"

    # Une coinbase ne dépense aucun UTXO
    if transaction["inputs"] != []:
        return False, "Une coinbase ne doit pas avoir d'input"

    # Une coinbase doit avoir exactement un output
    if (not isinstance(transaction["outputs"], list)or len(transaction["outputs"]) != 1):
        return False, "La coinbase doit avoir exactement un output"

    output = transaction["outputs"][0]

    if not isinstance(output, dict):
        return False, "Output coinbase invalide"

    if "address" not in output or "amount" not in output:
        return False, "Output coinbase incomplet"

    # Vérifier l'adresse du mineur
    resultat_adresse = adress_validation(output["address"])

    if not resultat_adresse[0]:
        return False, resultat_adresse[1]

    # Vérifier la récompense
    if (isinstance(output["amount"], bool) or not isinstance(output["amount"], int) or output["amount"] != recompense_attendue):
        return False, "Récompense coinbase invalide"

    # Vérifier le nonce aléatoire
    random_nonce = transaction["random_nonce"]

    if not isinstance(random_nonce, str):
        return False, "Nonce coinbase invalide"

    if len(random_nonce) != 32:
        return False, "Longueur du nonce coinbase invalide"

    try:
        bytes.fromhex(random_nonce)
    except ValueError:
        return False, "Format du nonce coinbase invalide"

    # Recalculer et vérifier le txid
    txid_attendu = transaction_id(transaction)

    if transaction["txid"] != txid_attendu:
        return False, "txid de coinbase invalide"

    return True, "Coinbase valide"
