struct Params {
    base_nonce: u32,
    difficulty: u32,
    count: u32,
    _padding: u32,
}

@group(0) @binding(0) var<uniform> params: Params;
// result[0] = indicateur trouvé ; result[1] = plus petit nonce valide du lot.
@group(0) @binding(1) var<storage, read_write> result: array<atomic<u32>, 2>;

// Variable privée plutôt que `const` : Naga/wgpu n'autorise pas
// l'indexation dynamique d'un tableau constant avec K[i].
var<private> K: array<u32, 64> = array<u32, 64>(
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u,
    0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
    0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
    0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
    0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
    0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
    0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
    0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
    0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
    0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u,
    0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u,
    0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
    0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
    0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u
);

fn rotr(x: u32, n: u32) -> u32 {
    return (x >> n) | (x << (32u - n));
}

fn sha256_first_word(nonce: u32, difficulty: u32) -> u32 {
    var w: array<u32, 64>;

    // "WobblyToken-PoW-v2-data!" (24 octets), puis difficulté (1 octet),
    // nonce big-endian (4 octets), 0x80 et longueur 29*8 = 232 bits.
    w[0] = 0x576f6262u; w[1] = 0x6c79546fu;
    w[2] = 0x6b656e2du; w[3] = 0x506f572du;
    w[4] = 0x76322d64u; w[5] = 0x61746121u;
    w[6] = (difficulty << 24u) | (nonce >> 8u);
    w[7] = (nonce << 24u) | 0x00800000u;
    for (var i = 8u; i < 15u; i = i + 1u) { w[i] = 0u; }
    w[15] = 232u;

    for (var i = 16u; i < 64u; i = i + 1u) {
        let s0 = rotr(w[i - 15u], 7u) ^ rotr(w[i - 15u], 18u) ^ (w[i - 15u] >> 3u);
        let s1 = rotr(w[i - 2u], 17u) ^ rotr(w[i - 2u], 19u) ^ (w[i - 2u] >> 10u);
        w[i] = w[i - 16u] + s0 + w[i - 7u] + s1;
    }

    var a = 0x6a09e667u; var b = 0xbb67ae85u;
    var c = 0x3c6ef372u; var d = 0xa54ff53au;
    var e = 0x510e527fu; var f = 0x9b05688cu;
    var g = 0x1f83d9abu; var h = 0x5be0cd19u;

    for (var i = 0u; i < 64u; i = i + 1u) {
        let s1 = rotr(e, 6u) ^ rotr(e, 11u) ^ rotr(e, 25u);
        let ch = (e & f) ^ ((~e) & g);
        let temp1 = h + s1 + ch + K[i] + w[i];
        let s0 = rotr(a, 2u) ^ rotr(a, 13u) ^ rotr(a, 22u);
        let maj = (a & b) ^ (a & c) ^ (b & c);
        let temp2 = s0 + maj;
        h = g; g = f; f = e; e = d + temp1;
        d = c; c = b; b = a; a = temp1 + temp2;
    }
    return a + 0x6a09e667u;
}

@compute @workgroup_size(256)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    if (id.x >= params.count) { return; }
    let nonce = params.base_nonce + id.x;
    let first_word = sha256_first_word(nonce, params.difficulty);
    let bits = params.difficulty * 4u;
    let valid = bits == 0u || (first_word >> (32u - bits)) == 0u;
    if (valid) {
        atomicMin(&result[1], nonce);
        atomicStore(&result[0], 1u);
    }
}