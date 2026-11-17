import Foundation

func deq_q6k(_ b: [UInt8], _ out: inout [Float], _ base: Int) {
    let d = Float(Float16(bitPattern: UInt16(b[208]) | (UInt16(b[209]) << 8)))
    for n in [0, 128] {
        let ql_off = n / 2
        let qh_off = n / 4
        let sc_off = n / 16
        for l in 0..<32 {
            let is_ = l / 16
            let qh_v = Int(b[128 + qh_off + l])
            let q1 = (Int(b[ql_off + l] & 0xF) | ((qh_v & 3) << 4)) - 32
            let q2 = (Int(b[ql_off + l + 32] & 0xF) | (((qh_v >> 2) & 3) << 4)) - 32
            let q3 = (Int(b[ql_off + l] >> 4) | (((qh_v >> 4) & 3) << 4)) - 32
            let q4 = (Int(b[ql_off + l + 32] >> 4) | (((qh_v >> 6) & 3) << 4)) - 32
            let s0 = Float(Int8(bitPattern: b[192 + sc_off + is_ + 0]))
            let s2 = Float(Int8(bitPattern: b[192 + sc_off + is_ + 2]))
            let s4 = Float(Int8(bitPattern: b[192 + sc_off + is_ + 4]))
            let s6 = Float(Int8(bitPattern: b[192 + sc_off + is_ + 6]))
            out[base + n + l +  0] = d * s0 * Float(q1)
            out[base + n + l + 32] = d * s2 * Float(q2)
            out[base + n + l + 64] = d * s4 * Float(q3)
            out[base + n + l + 96] = d * s6 * Float(q4)
        }
    }
}

