use sha2::{Digest, Sha256};
use std::time::Instant;

const PREFIX: &[u8; 24] = b"WobblyToken-PoW-v2-data!";

fn digest(nonce: u32, difficulty: u32) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(PREFIX);
    hasher.update([difficulty as u8]);
    hasher.update(nonce.to_be_bytes());
    hasher.finalize().into()
}

fn is_valid(hash: &[u8; 32], difficulty: u32) -> bool {
    if difficulty == 0 {
        return true;
    }
    
    // Nombre d'octets complets à vérifier
    let full_bytes = (difficulty / 2) as usize;
    
    // Vérifier les octets complets
    if hash[..full_bytes].iter().any(|&byte| byte != 0) {
        return false;
    }
    
    // Vérifier le demi-octet restant si difficulté impaire
    if difficulty % 2 == 1 {
        if hash[full_bytes] >> 4 != 0 {
            return false;
        }
    }
    
    true
}

fn mine(difficulty: u32) -> (u32, [u8; 32]) {
    println!("=== WobblyToken PoW v2 - SHA-256 ===");
    println!("Payload: {}", String::from_utf8_lossy(PREFIX));
    println!("Difficulté: {} ({} bits)", difficulty, difficulty * 4);
    println!("Recherche du nonce...");
    
    let start = Instant::now();
    
    for nonce in 0..=u32::MAX {
        let hash = digest(nonce, difficulty);
        if is_valid(&hash, difficulty) {
            let elapsed = start.elapsed();
            
            println!("\n=== Résultat ===");
            println!("Nonce trouvé: {}", nonce);
            println!("Nonce (hex): 0x{:08x}", nonce);
            print!("Hash SHA-256: ");
            for byte in hash.iter() {
                print!("{:02x}", byte);
            }
            println!();
            println!("Premier mot: 0x{:08x}", u32::from_be_bytes([hash[0], hash[1], hash[2], hash[3]]));
            println!("Temps de recherche: {:.3} secondes", elapsed.as_secs_f64());
            println!("Performance: {:.2} hash/s", (nonce as u64 + 1) as f64 / elapsed.as_secs_f64());
            println!("Validité: ✓ Le hash commence par {} bits à zéro", difficulty * 4);
            
            return (nonce, hash);
        }
    }
    
    panic!("Aucun nonce trouvé dans l'espace u32");
}

fn main() {
    let difficulty = 6;
    let (nonce, hash) = mine(difficulty);
    

    assert!(is_valid(&hash, difficulty), "Le hash n'est pas valide!");
    
    print!("Hash complet: ");
    for byte in hash.iter() {
        print!("{:02x}", byte);
    }
    println!();
}