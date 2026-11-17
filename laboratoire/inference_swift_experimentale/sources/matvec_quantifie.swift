import Foundation

// Matvec Q4_K à la volée : ne stocke JAMAIS la matrice déquantifiée.
// Bloc Q4_K = 144 octets = 256 poids. W_gguf est row-major [out, in],
// donc chaque ligne (out) contient in/256 blocs consécutifs de 256 poids.
// Accumulation Kahan pour reproduire matvec_kahan (comparaison bit-exact).
func matvec_q4k_blocs(bytes: [UInt8], in_: Int, out: Int, x: [Float]) -> [Float] {
    precondition(bytes.count == out * (in_ / 256) * 144)
    precondition(x.count == in_)
    let nblk_par_ligne = in_ / 256
    var y = [Float](repeating: 0, count: out)
    var bloc = [Float](repeating: 0, count: 256)
    for i in 0..<out {
        var s: Float = 0
        var comp: Float = 0
        for b in 0..<nblk_par_ligne {
            let start = (i * nblk_par_ligne + b) * 144
            let bbuf = Array(bytes[start..<(start + 144)])
            deq_bloc(bbuf, &bloc, 0)
            let xbase = b * 256
            for j in 0..<256 {
                let prod = bloc[j] * x[xbase + j]
                let t = s + prod
                if abs(s) >= abs(prod) { comp += (s - t) + prod }
                else                   { comp += (prod - t) + s }
                s = t
            }
        }
        y[i] = s + comp
    }
    return y
}

// Matvec Q6_K à la volée : ne stocke JAMAIS la matrice déquantifiée.
// Bloc Q6_K = 210 octets = 256 poids. Même structure que Q4_K.
func matvec_q6k_blocs(bytes: [UInt8], in_: Int, out: Int, x: [Float]) -> [Float] {
    precondition(bytes.count == out * (in_ / 256) * 210)
    precondition(x.count == in_)
    let nblk_par_ligne = in_ / 256
    var y = [Float](repeating: 0, count: out)
    var bloc = [Float](repeating: 0, count: 256)
    for i in 0..<out {
        var s: Float = 0
        var comp: Float = 0
        for b in 0..<nblk_par_ligne {
            let start = (i * nblk_par_ligne + b) * 210
            let bbuf = Array(bytes[start..<(start + 210)])
            deq_q6k(bbuf, &bloc, 0)
            let xbase = b * 256
            for j in 0..<256 {
                let prod = bloc[j] * x[xbase + j]
                let t = s + prod
                if abs(s) >= abs(prod) { comp += (s - t) + prod }
                else                   { comp += (prod - t) + s }
                s = t
            }
        }
        y[i] = s + comp
    }
    return y
}
