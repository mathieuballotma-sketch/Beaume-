#!/usr/bin/env python3
"""Compare les logits Swift archivés à llama-cpp-python sur une entrée fixe."""
import argparse
import hashlib
from pathlib import Path

import llama_cpp
import numpy as np

EXPECTED = "2bada8a7450677000f678be90653b85d364de7db25eb5ea54136ada5f3933730"
REFERENCE = "ae7aa626c287fd2dac5fc3aae9bfe7c4882b76c8c5e0624e431e47d346f41664"
TOKENS = [81581, 11, 4759, 35631, 6185, 7789]


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gguf", type=Path)
    args = parser.parse_args()
    ref = Path(__file__).with_name("reference_swift_f32.bin")
    if sha256(args.gguf) != EXPECTED or sha256(ref) != REFERENCE:
        raise SystemExit("Empreinte du GGUF ou de la référence incorrecte.")
    if llama_cpp.__version__ != "0.3.37":
        raise SystemExit("Utiliser llama-cpp-python 0.3.37 pour ce protocole.")
    a = np.fromfile(ref, dtype="<f4").reshape(6, 152064)
    llm = llama_cpp.Llama(model_path=str(args.gguf), n_ctx=32, n_batch=8,
                          n_gpu_layers=0, logits_all=True, verbose=False)
    llm.eval(TOKENS)
    b = np.asarray(llm.scores[:6], dtype=np.float32)
    if b.shape != a.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise SystemExit("Forme incorrecte ou valeurs non finies.")
    for i in range(6):
        delta = np.abs(a[i] - b[i])
        print(f"position={i} argmax_swift={a[i].argmax()} argmax_llama={b[i].argmax()} "
              f"max_abs={delta.max():.6f} mean_abs={delta.mean():.6f}")


if __name__ == "__main__":
    main()
