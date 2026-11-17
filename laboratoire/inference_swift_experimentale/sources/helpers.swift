import Foundation

func find_t(_ infos: [TensorInfo], _ name: String) -> TensorInfo {
    for t in infos where t.name == name { return t }
    fatalError("tenseur \(name) introuvable")
}

func total_elements(_ t: TensorInfo) -> Int {
    var p = 1
    for d in t.dims { p *= Int(d) }
    return p
}

func deq_q4k_tensor(_ t: TensorInfo, _ base: Int, _ b: [UInt8]) -> [Float] {
    let abs = base + Int(t.offset)
    let nblk = total_elements(t) / 256
    var out = [Float](repeating: 0, count: nblk * 256)
    for i in 0..<nblk {
        let start = abs + i*144
        let blk = Array(b[start..<(start + 144)])
        deq_bloc(blk, &out, i*256)
    }
    return out
}

func deq_q6k_tensor(_ t: TensorInfo, _ base: Int, _ b: [UInt8]) -> [Float] {
    let abs = base + Int(t.offset)
    let nblk = total_elements(t) / 256
    var out = [Float](repeating: 0, count: nblk * 256)
    for i in 0..<nblk {
        let start = abs + i*210
        let blk = Array(b[start..<(start + 210)])
        deq_q6k(blk, &out, i*256)
    }
    return out
}

func matvec_kahan(_ W: [Float], _ r: Int, _ c: Int, _ x: [Float]) -> [Float] {
    precondition(W.count == r * c)
    precondition(x.count == c)
    var y = [Float](repeating: 0, count: r)
    for i in 0..<r {
        var s: Float = 0
        var comp: Float = 0
        let base = i * c
        for j in 0..<c {
            let prod = W[base + j] * x[j]
            let t = s + prod
            if abs(s) >= abs(prod) { comp += (s - t) + prod }
            else                   { comp += (prod - t) + s }
            s = t
        }
        y[i] = s + comp
    }
    return y
}

func generer_x(_ n: Int) -> [Float] {
    var x = [Float](repeating: 0, count: n)
    for i in 0..<n { x[i] = Float(sin(Double(i) * 0.001)) * 0.5 }
    return x
}

func comparer_bitpattern(_ a: [Float], _ b: [Float]) -> (exacts: Int, maxAbs: Float) {
    precondition(a.count == b.count)
    var exacts = 0
    var maxAbs: Float = 0
    for i in 0..<a.count {
        if a[i].bitPattern == b[i].bitPattern { exacts += 1 }
        maxAbs = max(maxAbs, abs(a[i] - b[i]))
    }
    return (exacts, maxAbs)
}

func load_f32(_ t: TensorInfo, _ base: Int, _ b: [UInt8]) -> [Float] {
    let abs = base + Int(t.offset)
    let n = total_elements(t)
    let data = Data(b[abs..<(abs + n*4)])
    return data.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
}
