#génération et vérification adresses WobblyToken

from hashlib import sha256

PREFIXE_ADRESSE = "wbl_"


#convertion de clé en adresse utilisable
def generer_adresse(cle_publique_hexa):
    #génération adresse depuis clé publique
    try:
        cle_publique_octets = bytes.fromhex(cle_publique_hexa) #convertit le texte hexa en octets
    except ValueError:
        raise ValueError("Clé publique invalide : doit être un hash hexadécimal")

    #hashage de la clé publique pour générer l'adresse du wallet
    return PREFIXE_ADRESSE + sha256(cle_publique_octets).hexdigest()


def valider_adresse(adresse):
    #verif du préfixe et des 64 caractères hexa
    
    if not isinstance(adresse, str):
        return False, "adresse invalide" #adresse invalide si pas  une chaîne de caractères

    if not adresse.startswith(PREFIXE_ADRESSE):
        return False, "adresse invalide" #adresse invalide si pas préfixe "wbl_"

    empreinte_hexa = adresse[len(PREFIXE_ADRESSE):] #retire le préfixe pour le calcul du has

    if len(empreinte_hexa) != 64:
        return False, "adresse invalide" #adresse invalide si longueur incorrecte
    #64 car sha256 produit un hash de 256 bits en octets sa fait 32 et vu que 2 caractère hexa = 1 octets on attend 64 caractères hexa

    #refuse les espaces et les caractères hors hexa minuscule
    for caractere in empreinte_hexa:
        if caractere not in "0123456789abcdef":
            return False, "adresse invalide"

    try:
        bytes.fromhex(empreinte_hexa) #verif si le texte hexa se convertit en octets
    except ValueError:
        return False, "adresse invalide" #adresse invalide si pas être un hash hexadécimal

    return True, "adresse valide" #adresse valide
