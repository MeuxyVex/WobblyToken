#création et vérification des transaction

import json
import ecdsa
import hashlib
import secrets
from copy import deepcopy
from wallet import generer_adresse, valider_adresse
from smartcontract import NOMBRE_MAXIMAL_SIGNATAIRES, valider_contrat, verifier_contrat

#transactions en attente d'être ajoutées dans un block
transactions_en_attente = []


def calculer_identifiant_transaction(transaction):
    #on calcule le txid sans reprendre son ancienne valeur
    #copy copie le dict mais garde les mêmes objets imbriqués
    copie_transaction = transaction.copy()

    # retirer l'ancien txid s'il existe sinon None
    copie_transaction.pop("txid", None)

    # transformer la transaction en texte JSON
    transaction_json = json.dumps(copie_transaction, sort_keys=True) #trie les clés pour que le texte à hacher soit tjrs le même

    # calculer et retourner son hash
    empreinte_transaction = hashlib.sha256(transaction_json.encode()).hexdigest()

    #qui sera utilisé comme identifiant unique de la transaction
    return empreinte_transaction


def creer_coinbase(position, adresse_mineur, recompense):
    #création de la récompense du mineur
    transaction = {
        "type": "coinbase",
        "position": position,
        "inputs": [],

        # génère un id unique de 16 octets aléatoire pour la transaction qui sera utilisé pour éviter les doublons et pour lier la transaction à un block spécifique
        "random_nonce": secrets.token_hex(16),
        "outputs": [{"address": adresse_mineur, "amount": recompense}]
    }

    transaction["txid"] = calculer_identifiant_transaction(transaction)

    return transaction


def construire_message_signature(transaction):
    #on prépare le message qui sera signé, les preuve sont ajoutées après en v2
    #v2 pour les contrats, ancien format conservé pour les tx classiques
    #on exclut les preuve pour ajouter des signatures sans casser les précédentes
    if transaction.get("version") == 2:
        #en v2 on peut ajouter les preuves après, mais les entrées et sorties restent signées

        #copie le dict pour retirer le txid sans toucher à la tx originale
        message = transaction.copy()

        message.pop("txid", None)
        message["inputs"] = []
        for entree in transaction["inputs"]:
            entree_sans_preuve = {}
            for cle in entree:
                if cle not in ("proof", "signature"):
                    entree_sans_preuve[cle] = entree[cle]
            message["inputs"].append(entree_sans_preuve)

        return json.dumps(message, sort_keys=True).encode()

    entrees_sans_signature = []

    for entree in transaction["inputs"]:
        entree_sans_signature = {
            "txid": entree["txid"],
            "output_index": entree["output_index"],
            "public_key": entree["public_key"]
        }

        entrees_sans_signature.append(entree_sans_signature)

    message = {
        "type": transaction["type"],
        "inputs": entrees_sans_signature,
        "outputs": transaction["outputs"]
    }

    return json.dumps(message, sort_keys=True).encode()


def signer_transaction_utxo(transaction, cle_privee_hexa):
    #signature du message avec la clé privée du wallet
    #retourne la signature en hexa sans modifier la tx
    cle_privee = ecdsa.SigningKey.from_string(
        bytes.fromhex(cle_privee_hexa), curve=ecdsa.SECP256k1
    )

    message = construire_message_signature(transaction)

    signature = cle_privee.sign_deterministic(message, hashfunc=hashlib.sha256)
    #sign_deterministic pour que la signature soit toujours la même si même message et même clé privée

    return signature.hex()


def signer_depense_contrat(operation, portefeuille, utxos):
    #ajoute notre signature au brouillon sans encore l'envoyer aux autres nodes
    #retourne une copie signée, erreur si le node ne peut pas signer
    if not isinstance(operation, dict) or operation.get("type") != "standard":
        raise ValueError("Transaction standard attendue")

    if type(operation.get("version")) is not int or operation["version"] != 2:
        raise ValueError("La signature de contrat exige la version 2")
    if not isinstance(operation.get("inputs"), list) or not operation["inputs"]:
        raise ValueError("Au moins une entrée est requise")

    if not isinstance(operation.get("outputs"), list) or not operation["outputs"]:
        raise ValueError("Au moins une sortie est requise")

    def autorise_signature(condition, directe=False):
        #utilise le portefeuille reçu par la fonction qui l'entoure
        #verif si notre adresse fait partie des signataires du contrat
        #directe exclut la multisig pour repérer une signature individuelle
        if condition["type"] == "signature":
            return condition["address"] == portefeuille["address"]

        if condition["type"] == "multisig" and not directe:
            return portefeuille["address"] in condition["addresses"]
        if condition["type"] in ("and", "or"):
            for enfant in condition["conditions"]:
                if autorise_signature(enfant, directe):
                    return True

        return False

    #deepcopy copie aussi les liste et dicts imbriqués, le brouillon reste intact
    copie = deepcopy(operation)
    entrees_a_signer = []
    references = set()
    total_entrees = 0
    total_sorties = 0
    for entree in copie["inputs"]:
        if not isinstance(entree, dict) or not isinstance(entree.get("txid"), str):
            raise ValueError("Référence d'entrée invalide")
        indice = entree.get("output_index")
        if type(indice) is not int or indice < 0:
            raise ValueError("Indice de sortie invalide")
        reference = f'{entree["txid"]}:{indice}'
        if reference in references or reference not in utxos:
            raise ValueError("UTXO absent, déjà dépensé ou dupliqué")
        references.add(reference)
        sortie = utxos[reference]
        if "contract" not in sortie or "address" in sortie:
            raise ValueError("Cette signature est réservée aux UTXO à contrat")
        resultat_validation = valider_contrat(sortie["contract"])
        valide = resultat_validation[0]
        message = resultat_validation[1]
        if not valide:
            raise ValueError(message)
        if "proof" not in entree:
            entree["proof"] = {}
        preuve = entree["proof"]
        if not isinstance(preuve, dict):
            raise ValueError("La preuve doit être un objet JSON")
        signatures = preuve.get("signatures", [])
        if not isinstance(signatures, list):
            raise ValueError("Liste de signatures invalide")
        for element in signatures:
            if not isinstance(element, dict):
                raise ValueError("Liste de signatures invalide")
        if autorise_signature(sortie["contract"]["condition"]):
            entrees_a_signer.append((entree, autorise_signature(sortie["contract"]["condition"], directe=True)))
        total_entrees += sortie["amount"]

    for sortie in copie["outputs"]:
        if not isinstance(sortie, dict) or type(sortie.get("amount")) is not int or sortie["amount"] <= 0:
            raise ValueError("Montant de sortie invalide")
        if "address" in sortie and "contract" in sortie:
            raise ValueError("Choisir une adresse ou un contrat pour chaque sortie")
        if "address" not in sortie and "contract" not in sortie:
            raise ValueError("Choisir une adresse ou un contrat pour chaque sortie")
        if "contract" in sortie:
            resultat_validation = valider_contrat(sortie["contract"])
        else:
            resultat_validation = valider_adresse(sortie["address"])
        if len(resultat_validation) < 2:
            raise ValueError(f"not enough values to unpack (expected 2, got {len(resultat_validation)})")
        valide = resultat_validation[0]
        message = resultat_validation[1]
        if not valide:
            raise ValueError(message)
        total_sorties += sortie["amount"]
    if total_sorties > total_entrees:
        raise ValueError("Fonds insuffisants")
    if not entrees_a_signer:
        raise ValueError("Le portefeuille de ce nœud n'est pas un signataire de ces contrats")

    signature = signer_transaction_utxo(copie, portefeuille["private_key"])
    preuve_locale = {"public_key": portefeuille["public_key"], "signature": signature}
    for entree_a_signer in entrees_a_signer:
        entree = entree_a_signer[0]
        signature_directe = entree_a_signer[1]
        preuve = entree["proof"]
        #le cosignataire multisig ne doit pas écraser la signature directe d'une autre adresse

        if signature_directe:
            preuve.update(preuve_locale)
        #on garde les signatures des autres nodes et remplace seulement la notre
        signatures = []
        for element in preuve.get("signatures", []):
            if element.get("public_key") != portefeuille["public_key"]:
                signatures.append(element)
        #ajoute un dict séparé pour chaque entrée
        signatures.append(preuve_locale.copy())
        if len(signatures) > NOMBRE_MAXIMAL_SIGNATAIRES:
            raise ValueError(f"Le contrat accepte au maximum {NOMBRE_MAXIMAL_SIGNATAIRES} signatures")
        preuve["signatures"] = signatures
    #recalcul du txid après ajout des preuves
    copie["txid"] = calculer_identifiant_transaction(copie)
    return copie


def creer_transaction_utxo(portefeuille, adresse_destinataire, montant, utxos, utxos_exclus=None, contrat=None):
    #prend les utxo disponibles du wallet et rend la monnaie si il en reste
    #montant en petites unités, contrat remplace l'adresse pour un dépôt
    #utxos exclus = fonds déjà réservés dans la mempool
    #retourne la tx signée sans la diffuser, erreur si fonds insuffisants
    if contrat is not None and adresse_destinataire is not None:
        raise ValueError("Choisir une adresse ou un contrat, pas les deux")

    if contrat is not None:
        resultat_adresse = valider_contrat(contrat)
    else:
        resultat_adresse = valider_adresse(adresse_destinataire)

    if not resultat_adresse[0]:
        raise ValueError(resultat_adresse[1])

    if isinstance(montant, bool) or not isinstance(montant, int) or montant <= 0: #refuse les bouléen car True peut être converti en 1 et False en 0
        raise ValueError("Montant invalide")

    #or garde les exclusions, sinon crée un ensemble vide si elles sont vides ou à none
    utxos_exclus = utxos_exclus or set()

    entrees = []
    total_selectionne = 0

    for reference_utxo in utxos:
        sortie = utxos[reference_utxo]
        #ignore les fonds réservés, sous contrat ou appartenant à un autre wallet
        if reference_utxo in utxos_exclus or "contract" in sortie or sortie.get("address") != portefeuille["address"]:
            continue

        parties_reference = reference_utxo.rsplit(":", 1) #rsplit sépare txid:index en deux parties "abc123:2" devient ["abc123", "2"]
        if len(parties_reference) < 2:
            raise ValueError(f"not enough values to unpack (expected 2, got {len(parties_reference)})")
        identifiant_precedent = parties_reference[0]
        indice_sortie = parties_reference[1]
        entrees.append({
            "txid": identifiant_precedent,
            "output_index": int(indice_sortie),
            "public_key": portefeuille["public_key"],
            "signature": ""
        })
        total_selectionne += sortie["amount"]

        if total_selectionne >= montant:
            break

    if total_selectionne < montant:
        raise ValueError("Solde disponible insuffisant")

    if contrat is not None:
        sorties = [{"contract": contrat, "amount": montant}]
    else:
        sorties = [{"address": adresse_destinataire, "amount": montant}]
    monnaie = total_selectionne - montant

    if monnaie > 0:
        #le reste revient au wallet dans une nouvelle sortie
        sorties.append({"address": portefeuille["address"], "amount": monnaie})

    transaction = {
        "type": "standard",
        "inputs": entrees,
        "outputs": sorties
    }
    if contrat is not None:
        transaction["version"] = 2

    signature = signer_transaction_utxo(transaction, portefeuille["private_key"])

    for entree in transaction["inputs"]: #la signature est la même pour toutes les entrés du wallet, on peut la réutiliser
        entree["signature"] = signature

    transaction["txid"] = calculer_identifiant_transaction(transaction)
    return transaction


def valider_transaction_utxo(transaction, utxos, hauteur_bloc=None):
    #vérification des entrée et sorties avant d'accepter la transaction
    #hauteur donnée par le node pour les conditions de bloc
    #retourne le résultat et un msg sans modifier les utxos
    # vérifier la structure générale
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

    #les transaction de type coinbase sont traitées séparément et ne nécessitent pas de validation des inputs et outputs
    if transaction["type"] != "standard":
        return False, "Type de transaction invalide"

    version = transaction.get("version", 1) #si pas de version alors on dit que c'est la v1 pour les tx classiques, sinon on prend la version donnée

    if isinstance(version, bool) or not isinstance(version, int) or version not in (1, 2):
        return False, "Version de transaction invalide"

    if (not isinstance(transaction["inputs"], list) or len(transaction["inputs"]) == 0):
        return False, "La transaction doit avoir au moins un input"

    if (not isinstance(transaction["outputs"], list) or len(transaction["outputs"]) == 0):
        return False, "La transaction doit avoir au moins un output"

    total_entrees = 0

    total_sorties = 0
    #on crée un set pour stocker les UTXOs utilisés dans la transaction afin d'empêcher leur double utilisation car la propriété d'un set est de ne contenir que des éléments uniques, ce qui permet de vérifier facilement si un UTXO a déjà été utilisé dans la transaction.
    utxos_utilises = set()

    # vérifier les inputs
    for entree in transaction["inputs"]:
        if not isinstance(entree, dict):
            return False, "Input invalide"
        champs_entree = ["txid", "output_index"]

        for champ in champs_entree:
            if champ not in entree:
                return False, f"Champ input manquant : {champ}"

        identifiant_precedent = entree["txid"]
        indice_sortie_precedente = entree["output_index"]

        if not isinstance(identifiant_precedent, str):
            return False, "txid d'input invalide"

        if (
            isinstance(indice_sortie_precedente, bool)
            or not isinstance(indice_sortie_precedente, int)
            or indice_sortie_precedente < 0
        ):
            return False, "Index d'output invalide"

        reference_utxo = f"{identifiant_precedent}:{indice_sortie_precedente}"


        # empêcher deux utilisation du même UTXO
        if reference_utxo in utxos_utilises:
            return False, "UTXO utilisé plusieurs fois"

        utxos_utilises.add(reference_utxo)

        # vérifier que l'UTXO existe encore
        if reference_utxo not in utxos:
            return False, "UTXO inexistant ou déjà dépensé"

        utxo = utxos[reference_utxo]

        if "contract" in utxo:
            if version != 2:
                return False, "Une dépense de contrat exige une transaction de version 2"
            if "address" in utxo:
                return False, "UTXO ambigu : adresse et contrat"
            try:
                message_signe = construire_message_signature(transaction)
            except (KeyError, TypeError, ValueError, AttributeError):
                return False, "Message de transaction invalide"
            #le node fournit la hauteur et reconstruit le message à verif
            contexte = {"block_height": hauteur_bloc, "message": message_signe}
            resultat_validation = verifier_contrat(utxo["contract"], entree.get("proof"), contexte)
            valide = resultat_validation[0]
            message = resultat_validation[1]
            if not valide:
                return False, message
            total_entrees += utxo["amount"]
            continue

        for champ in ("public_key", "signature"):
            if champ not in entree:
                return False, f"Champ input manquant : {champ}"


        # vérifier que la clé publique possède l'UTXO
        try:
            adresse_attendue = generer_adresse(entree["public_key"])
        except (ValueError, TypeError):
            return False, "Clé publique invalide"

        if adresse_attendue != utxo["address"]:
            return False, "La clé publique ne possède pas cet UTXO"

        # vérifier la signature
        verification = verifier_signature_utxo(transaction, entree)

        if not verification[0]:
            return False, verification[1]

        total_entrees += utxo["amount"]

    # vérifier les nouveaux outputs
    for sortie in transaction["outputs"]:
        if not isinstance(sortie, dict):
            return False, "Output invalide"
        if "amount" not in sortie:
            return False, "Output incomplet"
        if "address" in sortie and "contract" in sortie:
            return False, "Un output doit avoir une adresse ou un contrat, exclusivement"
        if "address" not in sortie and "contract" not in sortie:
            return False, "Un output doit avoir une adresse ou un contrat, exclusivement"
        if "contract" in sortie:
            if version != 2:
                return False, "Un contrat exige une transaction de version 2"
            resultat_adresse = valider_contrat(sortie["contract"])
        else:
            resultat_adresse = valider_adresse(sortie["address"])

        if not resultat_adresse[0]:
            return False, resultat_adresse[1]

        montant = sortie["amount"]

        if (isinstance(montant, bool) or not isinstance(montant, int) or montant <= 0):
            return False, "Montant d'output invalide"

        total_sorties += montant


    # empêcher la création de nouveaux fonds
    if total_sorties > total_entrees:
        return False, "Fonds insuffisants"

    # vérifier l'identifiant de la transaction
    identifiant_attendu = calculer_identifiant_transaction(transaction)

    if identifiant_attendu != transaction["txid"]:
        return False, "txid invalide"

    return True, "Transaction UTXO valide"


def verifier_signature_utxo(transaction, entree):
    #retourne le résultat de la verif et un msg
    #vérifie que la signature correspond au message et à la clé publique
    try:
        cle_publique = ecdsa.VerifyingKey.from_string(
            bytes.fromhex(entree["public_key"]), curve=ecdsa.SECP256k1
        )

        signature = bytes.fromhex(entree["signature"])

        message = construire_message_signature(transaction)

        cle_publique.verify(signature, message, hashfunc=hashlib.sha256)

    #erreur de signature invalide, la signature ne correspond pas à la clé publique et au message
    except ecdsa.BadSignatureError:
        return False, "Signature invalide"

    #gestion des erreurs de conversion hexadécimale et de clé de dictionnaire manquante et de type incorrect
    except (ValueError, TypeError, KeyError, AttributeError, ecdsa.MalformedPointError):
        return False, "Clé publique ou signature invalide"

    return True, "Signature valide"


def valider_coinbase(transaction, position_attendue, recompense_attendue):
    #compare la position et le montant aux valeurs attendues pour ce bloc
    #retourne le résultat de la verif et un msg
    #vérification de la récompense pour ce numéro de block
    # vérifier que la coinbase est un dictionnaire
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

    # vérifier la présence des champ
    for champ in champs_requis:
        if champ not in transaction:
            return False, f"Champ coinbase manquant : {champ}"

    # vérifier le type
    if transaction["type"] != "coinbase":
        return False, "Type de coinbase invalide"

    # vérifier la position du bloc
    if (
        isinstance(transaction["position"], bool)
        or not isinstance(transaction["position"], int)
        or transaction["position"] != position_attendue
    ):
        return False, "Position de coinbase invalide"

    # une coinbase ne dépense aucun UTXO
    if transaction["inputs"] != []:
        return False, "Une coinbase ne doit pas avoir d'input"

    # une coinbase doit avoir exactement un output
    if (not isinstance(transaction["outputs"], list) or len(transaction["outputs"]) != 1):
        return False, "La coinbase doit avoir exactement un output"

    sortie = transaction["outputs"][0]

    if not isinstance(sortie, dict):
        return False, "Output coinbase invalide"

    if "address" not in sortie or "amount" not in sortie:
        return False, "Output coinbase incomplet"

    if "contract" in sortie:
        return False, "La coinbase doit utiliser une adresse classique"

    # vérifier l'adresse du mineur
    resultat_adresse = valider_adresse(sortie["address"])

    if not resultat_adresse[0]:
        return False, resultat_adresse[1]

    # vérifier la récompense
    if (
        isinstance(sortie["amount"], bool)
        or not isinstance(sortie["amount"], int)
        or sortie["amount"] != recompense_attendue
    ):
        return False, "Récompense coinbase invalide"

    # vérifier le nonce aléatoire
    nonce_aleatoire = transaction["random_nonce"]

    if not isinstance(nonce_aleatoire, str):
        return False, "Nonce coinbase invalide"

    if len(nonce_aleatoire) != 32:
        return False, "Longueur du nonce coinbase invalide"

    try:
        bytes.fromhex(nonce_aleatoire)
    except ValueError:
        return False, "Format du nonce coinbase invalide"

    # recalculer et vérifier le txid
    identifiant_attendu = calculer_identifiant_transaction(transaction)

    if transaction["txid"] != identifiant_attendu:
        return False, "txid de coinbase invalide"

    return True, "Coinbase valide"
