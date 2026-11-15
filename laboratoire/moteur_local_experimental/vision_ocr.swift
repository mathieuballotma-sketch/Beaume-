import Foundation
import Vision
import AppKit

let path = CommandLine.arguments[1]
guard let image = NSImage(contentsOfFile: path),
      let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("ERREUR_IMAGE")
    exit(1)
}
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.usesLanguageCorrection = true
req.recognitionLanguages = ["fr-FR", "en-US"]
let handler = VNImageRequestHandler(cgImage: cg, options: [:])
let t0 = Date()
do { try handler.perform([req]) } catch {
    print("ERREUR_VISION: \(error)")
    exit(1)
}
let dt = Int(Date().timeIntervalSince(t0) * 1000)
guard let results = req.results else { exit(0) }
var texts: [String] = []
print("===")
for obs in results {
    if let top = obs.topCandidates(1).first {
        texts.append(top.string)
        let b = obs.boundingBox
        let conf = String(format: "%.3f", top.confidence)
        let bx = String(format: "%.3f,%.3f,%.3f,%.3f", b.origin.x, b.origin.y, b.size.width, b.size.height)
        print("LINE|\(conf)|\(bx)|\(top.string)")
    }
}
print("---")
print("TIME_MS|\(dt)")
print("LINES|\(results.count)")
print("FULL_TEXT_START")
print(texts.joined(separator: " "))
print("FULL_TEXT_END")
