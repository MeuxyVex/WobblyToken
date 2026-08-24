import json
import os

from .address import generation_addresse
from .keys import generate_keys


def walletcreation(path):
    if os.path.exists(path):
        with open(path, "r") as fichier:
            return json.load(fichier)

    directory = os.path.dirname(path)

    if directory:
        os.makedirs(directory, exist_ok=True)

    keys = generate_keys()
    address = generation_addresse(keys["public_key"])

    wallet = {
        "private_key": keys["private_key"],
        "public_key": keys["public_key"],
        "address": address
    }

    with open(path, "w", encoding="utf-8") as fichier:
        json.dump(wallet, fichier, indent=2)

    os.chmod(path, 0o600)

    return wallet