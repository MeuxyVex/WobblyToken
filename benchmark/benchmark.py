import hashlib

PREFIX = b"WobblyToken-PoW-v2-data!"

def digest(nonce, difficulty):
   
    
    message = PREFIX + bytes([difficulty]) + nonce.to_bytes(4, byteorder='big')
    return hashlib.sha256(message).digest()

def is_valid(hash_bytes, difficulty):

    if difficulty == 0:
        return True
    
    # Nombre d'octets complets à vérifier
    full_bytes = difficulty // 2
    
    # Vérifier les octets complets
    for i in range(full_bytes):
        if hash_bytes[i] != 0:
            return False
    
    # Vérifier le demi-octet restant si difficulté impaire
    if difficulty % 2 == 1:
        if hash_bytes[full_bytes] >> 4 != 0:
            return False
    
    return True

def mine(difficulty = 6, max_nonce = 0xFFFFFFFF):

    for nonce in range(max_nonce + 1):
        hash_bytes = digest(nonce, difficulty)
        if is_valid(hash_bytes, difficulty):
            return nonce, hash_bytes
    
    raise ValueError("Aucun nonce trouvé dans l'espace de recherche")

def main():
    difficulty = 6
    print("=== WobblyToken PoW v2 - SHA-256 ===")
    print(f"Payload: {PREFIX.decode('utf-8')}")
    print(f"Difficulté: {difficulty} ({difficulty * 4} bits)")
    print(f"Recherche du nonce...")
    
    nonce, hash_bytes = mine(difficulty)
    
    print(f"\n=== Résultat ===")
    print(f"Nonce trouvé: {nonce}")
    print(f"Nonce (hex): 0x{nonce:08x}")
    print(f"Hash SHA-256: {hash_bytes.hex()}")
    print(f"Premier mot: 0x{int.from_bytes(hash_bytes[:4], 'big'):08x}")
    
    # Vérification
    assert is_valid(hash_bytes, difficulty), "Le hash n'est pas valide!"
    print(f"Validité: ✓ Le hash commence par {difficulty * 4} bits à zéro")

if __name__ == "__main__":
    main()