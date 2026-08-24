import ecdsa


def generate_keys():
    private_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    public_key = private_key.get_verifying_key()

    return {
        "private_key": private_key.to_string().hex(),
        "public_key": public_key.to_string().hex()
    }

