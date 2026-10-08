#création des clée

import ecdsa


def generer_cles():
    #création de la paire de clés, retourne un dict avec les deux clés en hexa
    cle_privee = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1) #utilise courbe SECP256k1 avec ecdsa pour les clés

    cle_publique = cle_privee.get_verifying_key()

    return {
        "private_key": cle_privee.to_string().hex(),
        "public_key": cle_publique.to_string().hex() #retourne les clé en format héxadécimal
    }

#retourne les clés en format héxadécimal 
