import Foundation

// Vérifications de portée volontairement limitée, sans fichier de modèle.
func proche(_ valeur: Float, _ attendu: Float, tolerance: Float = 0.00001) -> Bool {
    return valeur.isFinite && abs(valeur - attendu) <= tolerance
}

let probabilites = softmax_causal_f32([1000, 1001, 1002])
guard probabilites.count == 3,
      proche(probabilites.reduce(0, +), 1),
      proche(probabilites[0], 0.09003057),
      proche(probabilites[1], 0.24472847),
      proche(probabilites[2], 0.66524096) else {
    fputs("Échec : softmax\n", stderr)
    exit(1)
}

let somme = add_elementwise([1, -2], [3, 4])
guard somme == [4, 2], mul_elementwise([2, -3], [4, 5]) == [8, -15] else {
    fputs("Échec : opérations élémentaires\n", stderr)
    exit(1)
}

let rotation = rope_f32([1, 2, 3, 4], pos: 0, theta: 1_000_000)
guard rotation == [1, 2, 3, 4] else {
    fputs("Échec : RoPE en position zéro\n", stderr)
    exit(1)
}
print("OK : softmax, opérations élémentaires et RoPE sur cas synthétiques")
