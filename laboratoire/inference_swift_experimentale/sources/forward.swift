import Foundation

let HIDDEN = 3584
let FFN = 18944
let N_Q_HEADS = 28
let N_KV_HEADS = 4
let HEAD_DIM = 128
let KV_DIM = 512
let N_LAYERS = 28
let VOCAB = 152064
let EPS: Float = 1e-6
let THETA: Double = 1e6

// Extrait les bytes d'un tenseur selon son typeCode (Q4_K=12, Q6_K=14, F32=0).
func extraire_bytes(_ t: TensorInfo, _ base: Int, _ b: [UInt8]) -> ([UInt8], UInt32) {
    let tc = t.typeCode
    let n = total_elements(t)
    let abs = base + Int(t.offset)
    let taille: Int
    switch tc {
    case 0:  taille = n * 4
    case 12: taille = (n/256) * 144
    case 14: taille = (n/256) * 210
    default: fatalError("type non supporté (\(tc)) pour \(t.name)")
    }
    return (Array(b[abs..<(abs+taille)]), tc)
}

func matvec_quantifie(_ bytes: [UInt8], _ tc: UInt32, _ in_: Int, _ out: Int, _ x: [Float]) -> [Float] {
    switch tc {
    case 12: return matvec_q4k_blocs(bytes: bytes, in_: in_, out: out, x: x)
    case 14: return matvec_q6k_blocs(bytes: bytes, in_: in_, out: out, x: x)
    default: fatalError("type non supporté pour matvec: \(tc)")
    }
}

// Embedding des tokens (lecture directe des blocs Q4_K de token_embd).
func embedding_tokens(_ tokens: [Int], _ infos: [TensorInfo], _ base: Int, _ b: [UInt8]) -> [[Float]] {
    let t_emb = find_t(infos, "token_embd.weight")
    let (bytes, _) = extraire_bytes(t_emb, base, b)
    var out: [[Float]] = []
    for v in tokens {
        let debut = v * 14 * 144
        var vec = [Float](repeating: 0, count: HIDDEN)
        for i in 0..<14 {
            let blk = Array(bytes[(debut + i*144)..<(debut + i*144 + 144)])
            deq_bloc(blk, &vec, i*256)
        }
        out.append(vec)
    }
    return out
}

// Forward complet, N tokens, sans cache KV. Recalcule tout à chaque appel.
func forward(_ tokens: [Int], _ positions: [Int], _ infos: [TensorInfo], _ base: Int, _ b: [UInt8]) -> [[Float]] {
    precondition(tokens.count == positions.count)
    let N = tokens.count
    var h = embedding_tokens(tokens, infos, base, b)

    for layer in 0..<N_LAYERS {
        let prefix = "blk.\(layer)."
        let (b_an, _) = extraire_bytes(find_t(infos, prefix+"attn_norm.weight"), base, b)
        let (b_q,  tc_q)  = extraire_bytes(find_t(infos, prefix+"attn_q.weight"), base, b)
        let (b_k,  tc_k)  = extraire_bytes(find_t(infos, prefix+"attn_k.weight"), base, b)
        let (b_v,  tc_v)  = extraire_bytes(find_t(infos, prefix+"attn_v.weight"), base, b)
        let (b_bq, _) = extraire_bytes(find_t(infos, prefix+"attn_q.bias"), base, b)
        let (b_bk, _) = extraire_bytes(find_t(infos, prefix+"attn_k.bias"), base, b)
        let (b_bv, _) = extraire_bytes(find_t(infos, prefix+"attn_v.bias"), base, b)
        let (b_o,  tc_o)  = extraire_bytes(find_t(infos, prefix+"attn_output.weight"), base, b)
        let (b_fn, _) = extraire_bytes(find_t(infos, prefix+"ffn_norm.weight"), base, b)
        let (b_g,  tc_g)  = extraire_bytes(find_t(infos, prefix+"ffn_gate.weight"), base, b)
        let (b_u,  tc_u)  = extraire_bytes(find_t(infos, prefix+"ffn_up.weight"), base, b)
        let (b_d,  tc_d)  = extraire_bytes(find_t(infos, prefix+"ffn_down.weight"), base, b)

        let W_an = b_an.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
        let bq   = b_bq.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
        let bk   = b_bk.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
        let bv   = b_bv.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
        let W_fn = b_fn.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }

        var h_norm: [[Float]] = []
        for t in 0..<N { h_norm.append(rmsnorm_f32(h[t], W_an, EPS)) }
        var Q: [[Float]] = [], K: [[Float]] = [], V: [[Float]] = []
        for t in 0..<N {
            var q = matvec_quantifie(b_q, tc_q, HIDDEN, HIDDEN, h_norm[t])
            var k = matvec_quantifie(b_k, tc_k, HIDDEN, KV_DIM, h_norm[t])
            var v = matvec_quantifie(b_v, tc_v, HIDDEN, KV_DIM, h_norm[t])
            for i in 0..<HIDDEN { q[i] += bq[i] }
            for i in 0..<KV_DIM { k[i] += bk[i]; v[i] += bv[i] }
            Q.append(q); K.append(k); V.append(v)
        }
        let invSqrtHD = Float(1.0 / (Double(HEAD_DIM)).squareRoot())
        var out_concat: [[Float]] = []
        for t in 0..<N {
            var concat_t = [Float]()
            for h_q in 0..<N_Q_HEADS {
                let h_kv = h_q / (N_Q_HEADS / N_KV_HEADS)
                let bq_h = h_q * HEAD_DIM
                let bk_h = h_kv * HEAD_DIM
                let q_rope = rope_f32(Array(Q[t][bq_h..<(bq_h+HEAD_DIM)]), pos: positions[t], theta: THETA)
                var sc = [Float](repeating: 0, count: N)
                for j in 0..<N {
                    if j > t { sc[j] = -.infinity }
                    else {
                        let k_rope = rope_f32(Array(K[j][bk_h..<(bk_h+HEAD_DIM)]), pos: positions[j], theta: THETA)
                        var s: Float = 0
                        for d in 0..<HEAD_DIM { s += q_rope[d] * k_rope[d] }
                        sc[j] = s * invSqrtHD
                    }
                }
                let sm = softmax_causal_f32(sc)
                var o = [Float](repeating: 0, count: HEAD_DIM)
                for j in 0..<N {
                    for d in 0..<HEAD_DIM { o[d] += sm[j] * V[j][bk_h + d] }
                }
                concat_t.append(contentsOf: o)
            }
            out_concat.append(concat_t)
        }
        var attn_proj: [[Float]] = []
        for t in 0..<N { attn_proj.append(matvec_quantifie(b_o, tc_o, HIDDEN, HIDDEN, out_concat[t])) }
        var h_post: [[Float]] = []
        for t in 0..<N { h_post.append(add_elementwise(h[t], attn_proj[t])) }

        var h2: [[Float]] = []
        for t in 0..<N { h2.append(rmsnorm_f32(h_post[t], W_fn, EPS)) }
        var gate: [[Float]] = [], up: [[Float]] = []
        for t in 0..<N {
            gate.append(matvec_quantifie(b_g, tc_g, HIDDEN, FFN, h2[t]))
            up.append(matvec_quantifie(b_u, tc_u, HIDDEN, FFN, h2[t]))
        }
        var ffn_h: [[Float]] = []
        for t in 0..<N {
            let sg = silu_f32(gate[t])
            ffn_h.append(mul_elementwise(sg, up[t]))
        }
        var ffn_out: [[Float]] = []
        for t in 0..<N { ffn_out.append(matvec_quantifie(b_d, tc_d, FFN, HIDDEN, ffn_h[t])) }
        var h_new: [[Float]] = []
        for t in 0..<N { h_new.append(add_elementwise(h_post[t], ffn_out[t])) }
        h = h_new
    }

    // output_norm + tête
    let (b_on, _) = extraire_bytes(find_t(infos, "output_norm.weight"), base, b)
    let (b_oh, tc_oh) = extraire_bytes(find_t(infos, "output.weight"), base, b)
    let W_on = b_on.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
    var logits: [[Float]] = []
    for t in 0..<N {
        let h_fn = rmsnorm_f32(h[t], W_on, EPS)
        logits.append(matvec_quantifie(b_oh, tc_oh, HIDDEN, VOCAB, h_fn))
    }
    return logits
}
