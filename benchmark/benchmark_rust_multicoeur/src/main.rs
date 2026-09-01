use sha2::{Digest, Sha256};
use rayon::prelude::*;
use std::time::Instant;
use std::sync::atomic::{AtomicU32, AtomicBool, Ordering};
use std::sync::Arc;

const PREFIX: &[u8; 24] = b"WobblyToken-PoW-v2-data!";
const BATCH_SIZE: u32 = 262_144; // 256K hashes par batch

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
    
    let bits = difficulty * 4;
    let first_word = u32::from_be_bytes([hash[0], hash[1], hash[2], hash[3]]);
    (first_word >> (32 - bits)) == 0
}

fn mine_parallel(difficulty: u32, num_threads: usize) -> (u32, [u8; 32], u64) {
    println!("=== WobblyToken PoW v2 - SHA-256 Multi-cœur ===");
    println!("Payload: {}", String::from_utf8_lossy(PREFIX));
    println!("Difficulté: {} ({} bits)", difficulty, difficulty * 4);
    println!("Threads CPU: {}", num_threads);
    println!("Taille du batch: {} hashes", BATCH_SIZE);
    println!("Recherche du nonce...");
    
    let start = Instant::now();
    let mut total_hashes: u64 = 0;
    let mut base = 0u32;
    
    loop {
        let end = base.saturating_add(BATCH_SIZE).min(u32::MAX);
        
        // Recherche parallèle dans le batch
        let found = (base..end)
            .into_par_iter()
            .filter(|&nonce| {
                let hash = digest(nonce, difficulty);
                is_valid(&hash, difficulty)
            })
            .min();
        
        total_hashes += (end - base) as u64;
        
        if let Some(nonce) = found {
            let hash = digest(nonce, difficulty);
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
            println!("Hashes calculés: {}", total_hashes);
            println!("Temps de recherche: {:.3} secondes", elapsed.as_secs_f64());
            println!("Performance: {:.2} hash/s", total_hashes as f64 / elapsed.as_secs_f64());
            println!("Performance par thread: {:.2} hash/s/thread", 
                     total_hashes as f64 / elapsed.as_secs_f64() / num_threads as f64);
            println!("Validité: ✓ Le hash commence par {} bits à zéro", difficulty * 4);
            
            return (nonce, hash, total_hashes);
        }
        
        if end == u32::MAX {
            break;
        }
        base = end;
    }
    
    panic!("Aucun nonce trouvé dans l'espace u32");
}

fn mine_parallel_early_exit(difficulty: u32, num_threads: usize) -> (u32, [u8; 32], u64) {
    println!("=== WobblyToken PoW v2 - SHA-256 Multi-cœur (early exit) ===");
    println!("Payload: {}", String::from_utf8_lossy(PREFIX));
    println!("Difficulté: {} ({} bits)", difficulty, difficulty * 4);
    println!("Threads CPU: {}", num_threads);
    println!("Recherche du nonce avec arrêt précoce...");
    
    let start = Instant::now();
    let found_nonce = Arc::new(AtomicU32::new(u32::MAX));
    let found_flag = Arc::new(AtomicBool::new(false));
    let total_hashes = Arc::new(AtomicU32::new(0));
    
    // Lancer plusieurs threads de minage
    let handles: Vec<_> = (0..num_threads)
        .map(|thread_id| {
            let found_nonce = Arc::clone(&found_nonce);
            let found_flag = Arc::clone(&found_flag);
            let total_hashes = Arc::clone(&total_hashes);
            
            std::thread::spawn(move || {
                let mut base = thread_id as u32;
                let step = num_threads as u32;
                
                while base < u32::MAX && !found_flag.load(Ordering::Relaxed) {
                    let hash = digest(base, difficulty);
                    total_hashes.fetch_add(1, Ordering::Relaxed);
                    
                    if is_valid(&hash, difficulty) {
                        // Premier thread à trouver le résultat
                        if !found_flag.swap(true, Ordering::Relaxed) {
                            found_nonce.store(base, Ordering::Relaxed);
                        }
                        break;
                    }
                    
                    base = base.saturating_add(step);
                }
            })
        })
        .collect();
    
    // Attendre tous les threads
    for handle in handles {
        handle.join().unwrap();
    }
    
    let nonce = found_nonce.load(Ordering::Relaxed);
    let hashes = total_hashes.load(Ordering::Relaxed);
    let elapsed = start.elapsed();
    
    if nonce == u32::MAX {
        panic!("Aucun nonce trouvé");
    }
    
    let hash = digest(nonce, difficulty);
    
    println!("\n=== Résultat ===");
    println!("Nonce trouvé: {}", nonce);
    println!("Nonce (hex): 0x{:08x}", nonce);
    print!("Hash SHA-256: ");
    for byte in hash.iter() {
        print!("{:02x}", byte);
    }
    println!();
    println!("Hashes calculés: {}", hashes);
    println!("Temps de recherche: {:.3} secondes", elapsed.as_secs_f64());
    println!("Performance: {:.2} hash/s", hashes as f64 / elapsed.as_secs_f64());
    
    (nonce, hash, hashes as u64)
}

fn benchmark_throughput(difficulty: u32, num_threads: usize, hash_count: u32) {
    println!("\n=== Benchmark de performance ===");
    println!("Calcul de {} hashes...", hash_count);
    
    let start = Instant::now();
    
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(num_threads)
        .build()
        .unwrap();
    
    let hits: u64 = pool.install(|| {
        (0..hash_count)
            .into_par_iter()
            .map(|nonce| {
                let hash = digest(nonce, difficulty);
                is_valid(&hash, difficulty) as u64
            })
            .sum()
    });
    
    let elapsed = start.elapsed();
    
    println!("Hashes calculés: {}", hash_count);
    println!("Hits: {}", hits);
    println!("Temps: {:.3} secondes", elapsed.as_secs_f64());
    println!("Performance: {:.2} hash/s", hash_count as f64 / elapsed.as_secs_f64());
    println!("Performance par thread: {:.2} hash/s/thread", 
             hash_count as f64 / elapsed.as_secs_f64() / num_threads as f64);
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    
    let difficulty: u32 = args.get(1)
        .and_then(|v| v.parse().ok())
        .unwrap_or(6);
    
    let num_threads: usize = args.get(2)
        .and_then(|v| v.parse().ok())
        .unwrap_or_else(num_cpus::get);
    
    let mode: String = args.get(3)
        .cloned()
        .unwrap_or_else(|| "batch".to_string());
    
    println!("=== WobblyToken PoW v2 - Multi-cœur ===");
    println!("CPU: {} cœurs disponibles", num_cpus::get());
    println!("Threads utilisés: {}", num_threads);
    
    match mode.as_str() {
        "batch" => {
            let (nonce, hash, hashes) = mine_parallel(difficulty, num_threads);
            
            // Vérification finale
            assert!(is_valid(&hash, difficulty), "Le hash n'est pas valide!");
            println!("\n✓ Vérification finale réussie");
        }
        "early" => {
            let (nonce, hash, hashes) = mine_parallel_early_exit(difficulty, num_threads);
            
            // Vérification finale
            assert!(is_valid(&hash, difficulty), "Le hash n'est pas valide!");
            println!("\n✓ Vérification finale réussie");
        }
        "benchmark" => {
            let hash_count = args.get(4)
                .and_then(|v| v.parse().ok())
                .unwrap_or(1_000_000);
            
            benchmark_throughput(difficulty, num_threads, hash_count);
        }
        _ => {
            eprintln!("Modes disponibles: batch, early, benchmark");
            eprintln!("Usage: {} [difficulté] [threads] [mode] [hash_count]", args[0]);
            std::process::exit(1);
        }
    }
}