import Foundation

func bytesToUnicode() -> [UInt8: Character] {
    var bs: [Int] = []
    for b in 0x21...0x7E { bs.append(b) }
    for b in 0xA1...0xAC { bs.append(b) }
    for b in 0xAE...0xFF { bs.append(b) }
    var cs = bs
    var n = 0
    for b in 0..<256 {
        if !bs.contains(b) {
            bs.append(b)
            cs.append(256 + n)
            n += 1
        }
    }
    var map = [UInt8: Character]()
    for i in 0..<bs.count {
        if let scalar = Unicode.Scalar(cs[i]) {
            map[UInt8(bs[i])] = Character(scalar)
        }
    }
    return map
}

struct Tokenizer {
    let toks: [String]
    let vocab: [String: Int32]
    let bpeRanks: [String: Int]      // clé "a b"
    let specialTokens: [String: Int32]
    let b2u: [UInt8: Character]
    let u2b: [Character: UInt8]
    let regex: NSRegularExpression

    init?(vocab: [String], merges: [String], types: [UInt8]) {
        self.toks = vocab
        var v = [String: Int32]()
        v.reserveCapacity(vocab.count)
        for (i, t) in vocab.enumerated() { v[t] = Int32(i) }
        self.vocab = v
        var ranks = [String: Int]()
        ranks.reserveCapacity(merges.count)
        for (i, m) in merges.enumerated() {
            // format "a b" → clé "a b" (concaténation avec espace conservée)
            ranks[m] = i
        }
        self.bpeRanks = ranks
        var specials = [String: Int32]()
        for (i, t) in vocab.enumerated() where types[i] == 3 || types[i] == 4 {
            specials[t] = Int32(i)
        }
        self.specialTokens = specials
        let b2u = bytesToUnicode()
        self.b2u = b2u
        var u = [Character: UInt8]()
        for (b, c) in b2u { u[c] = b }
        self.u2b = u
        let pat = #"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"#
        guard let re = try? NSRegularExpression(pattern: pat) else { return nil }
        self.regex = re
    }
}

extension Tokenizer {
    // BPE canonique : trouvre la paire de rang minimal, fusionne TOUTES ses
    // occurrences, recommence. Retourne la liste de symboles fusionnés.
    func bpe(_ token: [String]) -> [String] {
        var word = token
        if word.count <= 1 { return word }
        while true {
            var bestRank = Int.max
            var bestPair: String? = nil
            for i in 0..<(word.count - 1) {
                let key = word[i] + " " + word[i+1]
                if let r = bpeRanks[key], r < bestRank {
                    bestRank = r
                    bestPair = key
                }
            }
            guard let pairKey = bestPair else { break }
            let parts = pairKey.split(separator: " ", maxSplits: 1).map(String.init)
            guard parts.count == 2 else { break }
            let first = parts[0], second = parts[1]
            var newWord = [String]()
            var i = 0
            while i < word.count {
                if i < word.count - 1, word[i] == first, word[i+1] == second {
                    newWord.append(first + second)
                    i += 2
                } else {
                    newWord.append(word[i])
                    i += 1
                }
            }
            word = newWord
            if word.count == 1 { break }
        }
        return word
    }
}

extension Tokenizer {
    // Encode un texte sans tokens spéciaux : pré-tokenisation d'abord,
    // byte-encodage de CHAQUE prétoken, puis BPE.
    func encodeRegular(_ text: String) -> [Int32] {
        var ids = [Int32]()
        let ns = text as NSString
        let matches = regex.matches(in: text, options: [], range: NSRange(location: 0, length: ns.length))
        for m in matches {
            let pretok = ns.substring(with: m.range)
            // Byte-encode ce prétoken
            var bchars: [String] = []
            for byte in pretok.utf8 {
                if let c = b2u[byte] {
                    bchars.append(String(c))
                }
            }
            // BPE sur les chars individuels
            let tokens = bpe(bchars)
            for t in tokens {
                if let id = vocab[t] { ids.append(id) }
            }
        }
        return ids
    }

    func encode(_ text: String) -> [Int32] {
        if specialTokens.isEmpty { return encodeRegular(text) }
        // Découpe en segments spéciaux et non-spéciaux
        var segments: [(Bool, String)] = []  // (is_special, content)
        var pos = text.startIndex
        while pos < text.endIndex {
            // Chercher le plus long special token qui commence à pos
            var bestSp: String? = nil
            for sp in specialTokens.keys {
                if text[pos...].hasPrefix(sp) {
                    if bestSp == nil || sp.count > bestSp!.count {
                        bestSp = sp
                    }
                }
            }
            if let sp = bestSp {
                segments.append((true, sp))
                pos = text.index(pos, offsetBy: sp.count)
            } else {
                // Chercher la prochaine occurrence d'un special token
                var nextPos = text.endIndex
                for sp in specialTokens.keys {
                    if let r = text.range(of: sp, range: pos..<text.endIndex) {
                        if r.lowerBound < nextPos { nextPos = r.lowerBound }
                    }
                }
                if nextPos > pos {
                    segments.append((false, String(text[pos..<nextPos])))
                }
                pos = nextPos
            }
        }
        var ids = [Int32]()
        for (isSp, content) in segments {
            if isSp {
                if let id = specialTokens[content] { ids.append(id) }
            } else {
                ids.append(contentsOf: encodeRegular(content))
            }
        }
        return ids
    }

    func decode(_ ids: [Int32]) -> String {
        var bchars: [Character] = []
        for id in ids {
            let tok = toks[Int(id)]
            for c in tok { bchars.append(c) }
        }
        // Character -> byte
        var bytes = [UInt8]()
        for c in bchars {
            if let b = u2b[c] { bytes.append(b) }
        }
        return String(decoding: bytes, as: UTF8.self)
    }
}
