import Foundation

struct KVCache {
    let maxPos: Int
    var k: [Float]   // N_LAYERS * N_KV_HEADS * maxPos * HEAD_DIM
    var v: [Float]
    var len: Int

    init(maxPos: Int) {
        let size = N_LAYERS * N_KV_HEADS * maxPos * HEAD_DIM
        self.k = [Float](repeating: 0, count: size)
        self.v = [Float](repeating: 0, count: size)
        self.maxPos = maxPos
        self.len = 0
    }

    @inline(__always)
    func idx(_ layer: Int, _ head: Int, _ pos: Int, _ d: Int) -> Int {
        return (((layer * N_KV_HEADS) + head) * maxPos + pos) * HEAD_DIM + d
    }
}

// Prefill si positions[0] == 0 et len==0 ; decode si positions[0] == len.
// Retourne les logits du dernier token traité.
func forward_with_cache(_ tokens: [Int], _ positions: [Int], _ cache: inout KVCache,
                        _ infos: [TensorInfo], _ base: Int, _ b: [UInt8]) -> [Float] {
    let N = tokens.count
    precondition(N == positions.count)
    precondition(N >= 1)
    precondition(positions[0] == cache.len, "positions[0]=\(positions[0]) != cache.len=\(cache.len)")
    let startLen = cache.len
    let invSqrtHD = Float(1.0 / (Double(HEAD_DIM)).squareRoot())
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

        // Store K_rope and V in cache at cachePos = startLen + t
        for t in 0..<N {
            let cachePos = startLen + t
            precondition(cachePos < cache.maxPos, "cache plein à \(cachePos)")
            for h_kv in 0..<N_KV_HEADS {
                let bk_h = h_kv * HEAD_DIM
                let k_rope = rope_f32(Array(K[t][bk_h..<(bk_h+HEAD_DIM)]), pos: positions[t], theta: THETA)
                for d in 0..<HEAD_DIM {
                    cache.k[cache.idx(layer, h_kv, cachePos, d)] = k_rope[d]
                    cache.v[cache.idx(layer, h_kv, cachePos, d)] = V[t][bk_h + d]
                }
            }
        }

        // Attention causale sur cache positions 0...cachePos
        var out_concat: [[Float]] = []
        for t in 0..<N {
            let cachePos = startLen + t
            var concat_t = [Float]()
            for h_q in 0..<N_Q_HEADS {
                let h_kv = h_q / (N_Q_HEADS / N_KV_HEADS)
                let bq_h = h_q * HEAD_DIM
                let q_rope = rope_f32(Array(Q[t][bq_h..<(bq_h+HEAD_DIM)]), pos: positions[t], theta: THETA)
                var sc = [Float](repeating: 0, count: cachePos + 1)
                for j in 0...cachePos {
                    var s: Float = 0
                    for d in 0..<HEAD_DIM {
                        s += q_rope[d] * cache.k[cache.idx(layer, h_kv, j, d)]
                    }
                    sc[j] = s * invSqrtHD
                }
                let sm = softmax_causal_f32(sc)
                var o = [Float](repeating: 0, count: HEAD_DIM)
                for j in 0...cachePos {
                    for d in 0..<HEAD_DIM {
                        o[d] += sm[j] * cache.v[cache.idx(layer, h_kv, j, d)]
                    }
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

    cache.len = startLen + N

    // output_norm + tête sur le dernier token uniquement
    let (b_on, _) = extraire_bytes(find_t(infos, "output_norm.weight"), base, b)
    let (b_oh, tc_oh) = extraire_bytes(find_t(infos, "output.weight"), base, b)
    let W_on = b_on.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
    let h_fn = rmsnorm_f32(h[N-1], W_on, EPS)
    return matvec_quantifie(b_oh, tc_oh, HIDDEN, VOCAB, h_fn)
}
