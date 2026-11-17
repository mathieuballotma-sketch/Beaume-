import Foundation

func u32(_ b: [UInt8], _ o: Int) -> UInt32 {
    return UInt32(b[o]) | (UInt32(b[o+1]) << 8) | (UInt32(b[o+2]) << 16) | (UInt32(b[o+3]) << 24)
}

func u64(_ b: [UInt8], _ o: Int) -> UInt64 {
    var v: UInt64 = 0
    for i in 0..<8 { v |= UInt64(b[o+i]) << (8 * i) }
    return v
}

func readString(_ b: [UInt8], _ o: inout Int) -> String {
    let len = Int(u64(b, o))
    o += 8
    let s = String(decoding: b[o..<(o + len)], as: UTF8.self)
    o += len
    return s
}

struct TensorInfo {
    let name: String
    let dims: [UInt64]
    let typeCode: UInt32
    let offset: UInt64
}

func typeName(_ c: UInt32) -> String {
    switch c {
    case 0:  return "F32"
    case 1:  return "F16"
    case 2:  return "Q4_0"
    case 3:  return "Q4_1"
    case 6:  return "Q5_0"
    case 7:  return "Q5_1"
    case 8:  return "Q8_0"
    case 9:  return "Q8_1"
    case 10: return "Q2_K"
    case 11: return "Q3_K"
    case 12: return "Q4_K"
    case 13: return "Q5_K"
    case 14: return "Q6_K"
    case 15: return "Q8_K"
    case 30: return "BF16"
    default: return "CODE_\(c)"
    }
}

func skipValue(_ b: [UInt8], _ o: inout Int, _ type: UInt32) {
    switch type {
    case 0, 1, 7: o += 1
    case 2, 3:    o += 2
    case 4, 5, 6: o += 4
    case 10, 11, 12: o += 8
    case 8:       _ = readString(b, &o)
    case 9:
        let elemType = u32(b, o); o += 4
        let n = Int(u64(b, o)); o += 8
        for _ in 0..<n { skipValue(b, &o, elemType) }
    default:
        fatalError("type de métadonnée inconnu: \(type)")
    }
}

func lire_gguf(_ path: String) throws -> (infos: [TensorInfo], base: Int, data: [UInt8]) {
    let data = try Data(contentsOf: URL(fileURLWithPath: path))
    let b = [UInt8](data)
    let nTensors = Int(u64(b, 8))
    let nKv = Int(u64(b, 16))
    var o = 24
    for _ in 0..<nKv {
        _ = readString(b, &o)
        let t = u32(b, o); o += 4
        skipValue(b, &o, t)
    }
    var infos: [TensorInfo] = []
    infos.reserveCapacity(nTensors)
    for _ in 0..<nTensors {
        let name = readString(b, &o)
        let nd = Int(u32(b, o)); o += 4
        var dims: [UInt64] = []
        for _ in 0..<nd { dims.append(u64(b, o)); o += 8 }
        let tc = u32(b, o); o += 4
        let off = u64(b, o); o += 8
        infos.append(TensorInfo(name: name, dims: dims, typeCode: tc, offset: off))
    }
    let base = ((o + 31) / 32) * 32
    return (infos, base, b)
}
