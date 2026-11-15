// matrice_v2.swift — incrément 2 du laboratoire Beaume.
// Même cœur CPU/Metal que matrice.swift, non modifié ici.
// Ajoute : tailles non multiples de threadExecutionWidth, référence indépendante
// en Double pour les cas générés, cas invalide m>1024. Pas de benchmark.
// La migration fastMathEnabled -> mathMode est reportée à l'incrément suivant.
import Foundation
import Metal

enum ErreurCalcul: Error, CustomStringConvertible {
    case entree(String)
    case metal(String)
    var description: String {
        switch self {
        case .entree(let m): return "Entrée invalide : \(m)"
        case .metal(let m):  return "Metal indisponible ou en échec : \(m)"
        }
    }
}

struct Produit {
    let m: Int, k: Int, n: Int
    let a: [Float], b: [Float]

    func verifier() throws {
        guard m > 0, k > 0, n > 0, m <= 1024, k <= 1024, n <= 1024 else {
            throw ErreurCalcul.entree("dimensions hors de 1...1024")
        }
        guard a.count == m * k, b.count == k * n else {
            throw ErreurCalcul.entree("taille des matrices incompatible")
        }
        guard a.allSatisfy({ $0.isFinite }), b.allSatisfy({ $0.isFinite }) else {
            throw ErreurCalcul.entree("les valeurs doivent être finies")
        }
    }
}

func multiplierCPU(_ p: Produit) throws -> [Float] {
    try p.verifier()
    var c = [Float](repeating: 0, count: p.m * p.n)
    for i in 0..<p.m {
        for j in 0..<p.n {
            var somme: Float = 0
            for l in 0..<p.k { somme += p.a[i * p.k + l] * p.b[l * p.n + j] }
            c[i * p.n + j] = somme
        }
    }
    return c
}

let shader = """
#include <metal_stdlib>
using namespace metal;
kernel void produit_matrice(device const float *a [[buffer(0)]],
                            device const float *b [[buffer(1)]],
                            device float *c [[buffer(2)]],
                            constant uint &m [[buffer(3)]],
                            constant uint &k [[buffer(4)]],
                            constant uint &n [[buffer(5)]],
                            uint2 position [[thread_position_in_grid]]) {
    uint j = position.x, i = position.y;
    if (i >= m || j >= n) return;
    float somme = 0.0f;
    for (uint l = 0; l < k; ++l) somme += a[i * k + l] * b[l * n + j];
    c[i * n + j] = somme;
}
"""

func multiplierMetal(_ p: Produit) throws -> [Float] {
    try p.verifier()
    guard let device = MTLCreateSystemDefaultDevice() else {
        throw ErreurCalcul.metal("aucun GPU accessible dans cet environnement")
    }
    let options = MTLCompileOptions()
    options.mathMode = .safe
    options.mathFloatingPointFunctions = .precise  // équivalent sémantique à fastMathEnabled = false
    let library: MTLLibrary
    do { library = try device.makeLibrary(source: shader, options: options) }
    catch { throw ErreurCalcul.metal("compilation du kernel : \(error)") }
    guard let fonction = library.makeFunction(name: "produit_matrice") else {
        throw ErreurCalcul.metal("kernel introuvable")
    }
    let pipeline: MTLComputePipelineState
    do { pipeline = try device.makeComputePipelineState(function: fonction) }
    catch { throw ErreurCalcul.metal("création du pipeline : \(error)") }
    let taille = MemoryLayout<Float>.stride
    guard let bufferA = p.a.withUnsafeBytes({ raw in
        device.makeBuffer(bytes: raw.baseAddress!, length: raw.count, options: .storageModeShared)
    }), let bufferB = p.b.withUnsafeBytes({ raw in
        device.makeBuffer(bytes: raw.baseAddress!, length: raw.count, options: .storageModeShared)
    }), let bufferC = device.makeBuffer(length: p.m * p.n * taille, options: .storageModeShared),
          let queue = device.makeCommandQueue(),
          let commande = queue.makeCommandBuffer(),
          let encodeur = commande.makeComputeCommandEncoder() else {
        throw ErreurCalcul.metal("création des tampons ou commandes impossible")
    }
    var m = UInt32(p.m), k = UInt32(p.k), n = UInt32(p.n)
    encodeur.setComputePipelineState(pipeline)
    encodeur.setBuffer(bufferA, offset: 0, index: 0)
    encodeur.setBuffer(bufferB, offset: 0, index: 1)
    encodeur.setBuffer(bufferC, offset: 0, index: 2)
    encodeur.setBytes(&m, length: MemoryLayout<UInt32>.stride, index: 3)
    encodeur.setBytes(&k, length: MemoryLayout<UInt32>.stride, index: 4)
    encodeur.setBytes(&n, length: MemoryLayout<UInt32>.stride, index: 5)
    let largeur = min(p.n, pipeline.threadExecutionWidth)
    let hauteur = min(p.m, max(1, pipeline.maxTotalThreadsPerThreadgroup / largeur))
    encodeur.dispatchThreads(MTLSize(width: p.n, height: p.m, depth: 1),
                            threadsPerThreadgroup: MTLSize(width: largeur, height: hauteur, depth: 1))
    encodeur.endEncoding()
    commande.commit()
    commande.waitUntilCompleted()
    guard commande.status == .completed else {
        throw ErreurCalcul.metal("exécution GPU : \(String(describing: commande.error))")
    }
    let pointeur = bufferC.contents().bindMemory(to: Float.self, capacity: p.m * p.n)
    return Array(UnsafeBufferPointer(start: pointeur, count: p.m * p.n))
}

func comparer(_ obtenu: [Float], _ attendu: [Float], tolerance: Float, etiquette: String) throws {
    guard obtenu.count == attendu.count else {
        throw ErreurCalcul.entree("\(etiquette) : taille de sortie incorrecte")
    }
    for (index, valeurs) in zip(obtenu, attendu).enumerated() {
        let (x, y) = valeurs
        guard x.isFinite, abs(x - y) <= tolerance * max(1, abs(y)) else {
            throw ErreurCalcul.entree("\(etiquette) : écart à l'indice \(index) : \(x) au lieu de \(y)")
        }
    }
}

// Générateur déterministe LCG. Les valeurs restent dans [-1, 1).
// L'attendu est accumulé en Double, séparément de multiplierCPU : on compare
// à une référence indépendante, on ne recopie pas l'implémentation testée.
func generer(_ m: Int, _ k: Int, _ n: Int, seed: UInt64) -> (Produit, [Float]) {
    var s = seed
    func suivant() -> Float {
        s = s &* 6364136223846793005 &+ 1442695040888963407
        let x = UInt32(truncatingIfNeeded: s >> 33)
        return Float(x) / Float(UInt32.max) * 2 - 1
    }
    let a = (0..<(m * k)).map { _ in suivant() }
    let b = (0..<(k * n)).map { _ in suivant() }
    var attendu = [Float](repeating: 0, count: m * n)
    for i in 0..<m {
        for j in 0..<n {
            var d: Double = 0
            for l in 0..<k { d += Double(a[i * k + l]) * Double(b[l * n + j]) }
            attendu[i * n + j] = Float(d)
        }
    }
    return (Produit(m: m, k: k, n: n, a: a, b: b), attendu)
}

let manuels: [(String, Produit, [Float])] = [
    ("rectangulaire", Produit(m: 2, k: 3, n: 2,
       a: [1, 2, 3, 4, 5, 6], b: [7, 8, 9, 10, 11, 12]), [58, 64, 139, 154]),
    ("scalaire", Produit(m: 1, k: 1, n: 1, a: [-2], b: [3]), [-6]),
    ("identité", Produit(m: 2, k: 2, n: 2, a: [1, 0, 0, 1], b: [2, -3, 0.5, 4]), [2, -3, 0.5, 4]),
    ("annulation", Produit(m: 1, k: 3, n: 1, a: [2, -2, 4], b: [3, 3, 0]), [0]),
]

let generes: [(String, Int, Int, Int, UInt64)] = [
    ("3x5·5x7",         3,   5,   7, 1),
    ("17x13·13x19",    17,  13,  19, 2),
    ("33x17·17x9",     33,  17,   9, 3),
    ("128x128·128x128", 128, 128, 128, 4),
]

let arguments = CommandLine.arguments.dropFirst()
guard arguments.count == 1, let mode = arguments.first, ["--cpu", "--metal"].contains(mode) else {
    fputs("Usage : matrice_v2 --cpu | --metal\n", stderr)
    exit(2)
}
do {
    for (nom, produit, attendu) in manuels {
        try comparer(try multiplierCPU(produit), attendu, tolerance: 1e-4, etiquette: "CPU/\(nom)")
        if mode == "--metal" {
            try comparer(try multiplierMetal(produit), attendu, tolerance: 1e-4, etiquette: "GPU/\(nom)")
        }
        print("OK \(mode) : \(nom)")
    }
    for (nom, m, k, n, seed) in generes {
        let (produit, attendu) = generer(m, k, n, seed: seed)
        try comparer(try multiplierCPU(produit), attendu, tolerance: 1e-3, etiquette: "CPU/\(nom)")
        if mode == "--metal" {
            try comparer(try multiplierMetal(produit), attendu, tolerance: 1e-3, etiquette: "GPU/\(nom)")
        }
        print("OK \(mode) : \(nom)")
    }
    let invalides: [(String, Produit)] = [
        ("dimensions incohérentes", Produit(m: 2, k: 2, n: 2, a: [1], b: [1])),
        ("dimension nulle",          Produit(m: 0, k: 1, n: 1, a: [], b: [1])),
        ("valeur NaN",               Produit(m: 1, k: 1, n: 1, a: [.nan], b: [1])),
        ("valeur infinie",           Produit(m: 1, k: 1, n: 1, a: [.infinity], b: [1])),
        ("m=2048 hors borne",        Produit(m: 2048, k: 1, n: 1, a: [1], b: [1])),
    ]
    for (nom, produit) in invalides {
        var refuseCPU = false
        do { _ = try multiplierCPU(produit) } catch ErreurCalcul.entree { refuseCPU = true }
        guard refuseCPU else { throw ErreurCalcul.entree("CPU : \(nom) accepté") }
        if mode == "--metal" {
            var refuseGPU = false
            do { _ = try multiplierMetal(produit) } catch ErreurCalcul.entree { refuseGPU = true }
            guard refuseGPU else { throw ErreurCalcul.entree("Metal : \(nom) accepté") }
        }
        print("OK \(mode) : \(nom) refusé")
    }
    print("Résultats contrôlés sur données fictives ; aucun benchmark.")
} catch {
    fputs("ÉCHEC \(mode) : \(error)\n", stderr)
    exit(1)
}
