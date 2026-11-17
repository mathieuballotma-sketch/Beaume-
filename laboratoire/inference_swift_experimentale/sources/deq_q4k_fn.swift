import Foundation

func sm(_ j: Int, _ s: [UInt8]) -> (Int, Int) {
    if j < 4 { return (Int(s[j] & 63), Int(s[j+4] & 63)) }
    let sc = Int((s[j+4] & 0xF) | ((s[j-4] >> 6) << 4))
    let mn = Int((s[j+4] >> 4) | ((s[j] >> 6) << 4))
    return (sc, mn)
}

func deq_bloc(_ b: [UInt8], _ out: inout [Float], _ base: Int) {
    let d    = Float(Float16(bitPattern: UInt16(b[0]) | (UInt16(b[1]) << 8)))
    let dmin = Float(Float16(bitPattern: UInt16(b[2]) | (UInt16(b[3]) << 8)))
    let s = Array(b[4..<16])
    let q = Array(b[16..<144])
    for jb in 0..<4 {
        let (sc1, m1) = sm(jb*2,   s)
        let (sc2, m2) = sm(jb*2+1, s)
        let d1 = d  * Float(sc1)
        let d2 = d  * Float(sc2)
        let n1 = dmin * Float(m1)
        let n2 = dmin * Float(m2)
        for l in 0..<32 {
            let lo = Float(q[jb*32 + l] & 0xF)
            let hi = Float(q[jb*32 + l] >>  4)
            out[base + jb*64 + l     ] = d1*lo - n1
            out[base + jb*64 + 32 + l] = d2*hi - n2
        }
    }
}

