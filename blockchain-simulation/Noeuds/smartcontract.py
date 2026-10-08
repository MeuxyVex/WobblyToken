#conditions pour pouvoir dépenser les utxo sous contrat

import hashlib

import ecdsa


VERSION_CONTRAT = 1
#limites pour éviter un contrat trop lourd à verif
PROFONDEUR_MAXIMALE = 8
NOMBRE_MAXIMAL_CONDITIONS = 128
NOMBRE_MAXIMAL_SIGNATAIRES = 16
TAILLE_MAXIMALE_SECRET = 4096  #taille max du secret en octets une fois encodé en utf-8


def _est_entier(valeur):
    #on refuse les booléens même si python les compte comme des int
    return isinstance(valeur, int) and not isinstance(valeur, bool)


def _est_hexadecimal(valeur, longueur, autoriser_majuscules=False):
    #vérifie la longueur et les caractères du texte hexa
    if not isinstance(valeur, str) or len(valeur) != longueur:
        return False

    caracteres_autorises = "0123456789abcdef"

    if autoriser_majuscules:
        caracteres_autorises += "ABCDEF"

    for caractere in valeur:
        if caractere not in caracteres_autorises:
            return False

    return True


def _est_adresse(adresse):
    #vérifie le format des adresse wbl_
    if not isinstance(adresse, str) or not adresse.startswith("wbl_"):
        return False

    return _est_hexadecimal(adresse[4:], 64)


def _valider_structure(condition, profondeur, compteur):
    #vérifie toutes les branches du contrat, même celles du OU non utilisées
    #profondeur = nb de niveaux imbriqués
    #liste avec un seul nombre pour partager le compteur entre les appel
    #compteur[0] augmente à chaque condition, même dans une autre branche
    compteur[0] += 1

    if profondeur > PROFONDEUR_MAXIMALE or compteur[0] > NOMBRE_MAXIMAL_CONDITIONS:
        return False, "Contrat trop complexe"
    if not isinstance(condition, dict):
        return False, "Condition invalide : dictionnaire attendu"

    type_condition = condition.get("type")

    if type_condition == "signature":
        #verif les noms des champs, aucun champ en plus ou manquant
        if set(condition) != {"type", "address"} or not _est_adresse(condition["address"]):
            return False, "Adresse de signature invalide"
    elif type_condition == "after_block":
        if set(condition) != {"type", "height"}:
            return False, "Condition de hauteur invalide"
        if not _est_entier(condition["height"]) or condition["height"] < 0:
            return False, "Hauteur minimale invalide"
    elif type_condition == "hashlock":
        if set(condition) != {"type", "hash"}:
            return False, "Condition de secret invalide"
        empreinte = condition["hash"]
        if not _est_hexadecimal(empreinte, 64):
            return False, "Empreinte SHA-256 invalide"
    elif type_condition == "multisig":
        if set(condition) != {"type", "required", "addresses"}:
            return False, "Condition multisignature invalide"
        adresses = condition["addresses"]
        seuil = condition["required"]
        if not isinstance(adresses, list) or not (len(adresses) >= 1 and len(adresses) <= NOMBRE_MAXIMAL_SIGNATAIRES):
            return False, "Liste des signataires invalide"
        for adresse in adresses:
            if not _est_adresse(adresse):
                return False, "Adresse de signataire invalide"
        #set retire les doublons, si la taille change une adresse était répétée
        if len(set(adresses)) != len(adresses):
            return False, "Signataires dupliqués dans le contrat"
        if not _est_entier(seuil) or not (seuil >= 1 and seuil <= len(adresses)):
            return False, "Nombre de signatures requises invalide"
    elif type_condition in ("and", "or"):
        if set(condition) != {"type", "conditions"}:
            return False, "Condition composée invalide"
        enfants = condition["conditions"]
        if not isinstance(enfants, list) or not (len(enfants) >= 1 and len(enfants) <= NOMBRE_MAXIMAL_CONDITIONS):
            return False, "Liste de sous-conditions invalide"
        for enfant in enfants:
            #rappelle la même fonction pour verif la sous-condition un niveau plus bas
            resultat_validation = _valider_structure(enfant, profondeur + 1, compteur)
            valide = resultat_validation[0]
            message = resultat_validation[1]
            if not valide:
                return False, message
    else:
        return False, "Type de condition inconnu"

    return True, "Structure valide"


def valider_contrat(contrat):
    #vérifie la forme du contrat avant le dépôt, pas encore les preuve
    #contrat = version + condition à respecter
    #retourne le résultat de la verif et un msg
    if not isinstance(contrat, dict) or set(contrat) != {"version", "condition"}:
        return False, "Format de contrat invalide"

    if not _est_entier(contrat["version"]) or contrat["version"] != VERSION_CONTRAT:
        return False, "Version de contrat non prise en charge"
    return _valider_structure(contrat["condition"], 1, [0])


def _adresse_signature_valide(preuve, contexte):
    #récupère l'adresse du signataire si sa signature est valide
    #preuve = clé publique + signature du message
    #retourne aucune adresse si la verif échoue
    if not isinstance(preuve, dict):
        return None

    cle_hexa = preuve.get("public_key")
    signature_hexa = preuve.get("signature")
    message = contexte.get("message")

    if not isinstance(message, bytes) or not message:
        return None
    #ici les clés publiques sont brutes et la signature contient r puis s
    if not _est_hexadecimal(cle_hexa, 128, autoriser_majuscules=True):
        return None
    if not _est_hexadecimal(signature_hexa, 128, autoriser_majuscules=True):
        return None
    try:
        cle_octets = bytes.fromhex(cle_hexa)
        cle_publique = ecdsa.VerifyingKey.from_string(cle_octets, curve=ecdsa.SECP256k1)
        cle_publique.verify(bytes.fromhex(signature_hexa), message, hashfunc=hashlib.sha256)
    except (ValueError, TypeError, ecdsa.BadSignatureError, ecdsa.MalformedPointError):
        return None
    return "wbl_" + hashlib.sha256(cle_octets).hexdigest()


def _evaluer_condition(condition, preuve, contexte):
    #test la condition une fois sa structure vérifiée
    #preuve = secret ou signatures fournis pour dépenser
    #contexte = hauteur du bloc et message fournis par le node
    #retourne si la condition est remplie
    type_condition = condition["type"]

    if type_condition == "signature":
        return _adresse_signature_valide(preuve, contexte) == condition["address"]

    if type_condition == "after_block":
        #hauteur du node et pas une hauteur choisie par celui qui dépense
        hauteur = contexte.get("block_height")
        return _est_entier(hauteur) and hauteur >= 0 and hauteur >= condition["height"]

    if type_condition == "hashlock":
        secret = preuve.get("secret")
        if not isinstance(secret, str) or len(secret) > TAILLE_MAXIMALE_SECRET: #vérifie la taille du secret avant encodage
            return False
        try:
            secret_octets = secret.encode("utf-8")
        except UnicodeEncodeError:
            return False
        if len(secret_octets) > TAILLE_MAXIMALE_SECRET: #vérifie la taille du secret une fois encodé en octets
            return False
        empreinte = hashlib.sha256(secret_octets).hexdigest()
        #le hash attendu est déjà public dans le contrat
        return empreinte == condition["hash"]

    if type_condition == "multisig":
        signatures = preuve.get("signatures")
        if not isinstance(signatures, list) or len(signatures) > NOMBRE_MAXIMAL_SIGNATAIRES:
            return False
        signataires_valides = set()
        for signature in signatures:
            adresse = _adresse_signature_valide(signature, contexte)
            if adresse in condition["addresses"]:
                #mettre 2x la même signature ne compte pas comme deux signataires
                signataires_valides.add(adresse)
        return len(signataires_valides) >= condition["required"]

    #et = toutes les condition, ou = au moins une
    #les sous-conditions utilisent la même preuve
    if type_condition == "and":
        for enfant in condition["conditions"]:
            if not _evaluer_condition(enfant, preuve, contexte):
                return False
        return True

    for enfant in condition["conditions"]:
        if _evaluer_condition(enfant, preuve, contexte):
            return True

    return False


def verifier_condition(condition, preuve, contexte):
    #vérifie la condition avec les preuves et le contexte donné par le node
    #retourne le résultat de la verif et un msg
    resultat_validation = _valider_structure(condition, 1, [0])

    valide = resultat_validation[0]
    message = resultat_validation[1]
    if not valide:
        return False, message

    if not isinstance(preuve, dict) or not isinstance(contexte, dict):
        return False, "Preuve ou contexte invalide"
    if not _evaluer_condition(condition, preuve, contexte):
        return False, "Conditions de dépense non satisfaites"
    return True, "Conditions de dépense satisfaites"


def verifier_contrat(contrat, preuve, contexte):
    #vérifie la version du contrat puis ses conditions de dépense
    #ne dépense rien ici, retourne juste le résultat et un msg
    resultat_validation = valider_contrat(contrat)

    valide = resultat_validation[0]
    message = resultat_validation[1]
    if not valide:
        return False, message

    return verifier_condition(contrat["condition"], preuve, contexte)
