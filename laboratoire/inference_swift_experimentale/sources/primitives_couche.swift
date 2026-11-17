import Foundation

func rmsnorm_f32(_ x: [Float], _ w: [Float], _ eps: Float) -> [Float] {
    precondition(x.count == w.count)
    var s: Float = 0
    for i in 0..<x.count { s += x[i] * x[i] }
    let ms = s / Float(x.count)
    let inv = 1.0 / (ms + eps).squareRoot()
    var y = [Float](repeating: 0, count: x.count)
    for i in 0..<x.count { y[i] = x[i] * inv * w[i] }
    return y
}

func rope_f32(_ x: [Float], pos: Int, theta: Double) -> [Float] {
    let half = x.count / 2
    var y = [Float](repeating: 0, count: x.count)
    for i in 0..<half {
        let inv = 1.0 / pow(theta, Double(i) / Double(half))
        let ang = Double(pos) * inv
        let c = Float(cos(ang))
        let s = Float(sin(ang))
        y[i]        = x[i] * c - x[i + half] * s
        y[i + half] = x[i] * s + x[i + half] * c
    }
    return y
}

// Softmax causal : -inf pour j > i (la position j ne peut influencer i que si j <= i)
func softmax_causal_f32(_ scores: [Float]) -> [Float] {
    var m: Float = -.infinity
    for v in scores { if v.isFinite && v > m { m = v } }
    var e = [Float](repeating: 0, count: scores.count)
    var s: Float = 0
    for i in 0..<scores.count {
        e[i] = scores[i].isFinite ? exp(scores[i] - m) : 0
        s += e[i]
    }
    for i in 0..<scores.count { e[i] /= s }
    return e
}

// silu(x) = x * sigmoid(x)
func silu_f32(_ x: [Float]) -> [Float] {
    var y = [Float](repeating: 0, count: x.count)
    for i in 0..<x.count {
        y[i] = x[i] / (1.0 + exp(-x[i]))
    }
    return y
}

// Produit terme à terme
func mul_elementwise(_ a: [Float], _ b: [Float]) -> [Float] {
    precondition(a.count == b.count)
    var y = [Float](repeating: 0, count: a.count)
    for i in 0..<a.count { y[i] = a[i] * b[i] }
    return y
}

// Addition (résiduelle)
func add_elementwise(_ a: [Float], _ b: [Float]) -> [Float] {
    precondition(a.count == b.count)
    var y = [Float](repeating: 0, count: a.count)
    for i in 0..<a.count { y[i] = a[i] + b[i] }
    return y
}
