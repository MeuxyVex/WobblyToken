from hashlib import sha256
prefix = "wbl_"

def generation_addresse(public_key_hexa): #convertion de clé en adresse utilisable
    try:
        hashage = bytes.fromhex(public_key_hexa)
    except ValueError:
        raise ValueError("Clé publique invalide : doit être un hash hexadécimal")
    
    return prefix + sha256(hashage).hexdigest() #Hashage de la clé publique pour générer l'adresse du wallet


def adress_validation(adress):
    if not isinstance(adress, str):
        return False, "Adresse invalide : doit être une chaîne de caractères"
    
    if not adress.startswith(prefix):
        return False, "Adresse invalide : doit commencer par 'wbl_'"

    hash_part = adress[len(prefix):]

    if len(hash_part) != 64:
        return False, "Adresse invalide : longueur incorrecte"
    
    try:
        bytes.fromhex(hash_part)
    except ValueError:
        return False, "Adresse invalide : doit être un hash hexadécimal"
    
    return True, "Adresse valide"