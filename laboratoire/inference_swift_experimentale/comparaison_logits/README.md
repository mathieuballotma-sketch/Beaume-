# Comparaison des logits : aide bienvenue

Sur un Mac M4, six positions ont donné le même argmax, mais l'écart absolu
maximal était de **1,669172**. L'origine de cet écart est inconnue ; l'accord
sur les argmax ne valide pas l'ensemble des logits.

## Données de l'essai historique

- Modèle : fichier GGUF local correspondant au modèle Ollama `qwen2.5:7b-instruct` ;
  SHA-256 `2bada8a7450677000f678be90653b85d364de7db25eb5ea54136ada5f3933730`.
  Les poids ne sont pas inclus ; obtenir le fichier dans le respect de sa licence.
- Entrée initiale : `Bonjour` ; séquence complète des IDs imposée aux deux
  systèmes : `[81581, 11, 4759, 35631, 6185, 7789]`, positions 0 à 5.
  Pas de sampling lors de la comparaison.
- Référence Swift archivée : `reference_swift_f32.bin`, SHA-256
  `ae7aa626c287fd2dac5fc3aae9bfe7c4882b76c8c5e0624e431e47d346f41664` ;
  6 × 152064 flottants IEEE 754 32 bits little-endian.
- `llama-cpp-python` 0.3.37, `n_ctx=32`, `n_batch=8`, `logits_all=True`,
  `n_gpu_layers=0` ; CPU, Swift avec accumulation Kahan.

## Rejouer la comparaison externe

Dans un environnement isolé avec Python, NumPy et `llama-cpp-python==0.3.37`
installés, depuis ce répertoire :

```sh
python comparer.py /chemin/vers/modele.gguf
```

Le script contrôle les deux empreintes, la forme, les valeurs finies, puis
affiche pour chaque position les argmax et les écarts absolus maximal et moyen.
Noter la machine, les versions, les options de compilation et le backend :
ils peuvent influer sur les résultats. La sortie Swift est une archive : le
dépôt ne permet pas encore de la régénérer de bout en bout. Il faut aussi
obtenir séparément le fichier GGUF exact ; un modèle portant le même nom ne
garantit pas la même empreinte.

Rejoué le 17 novembre 2026 sur le Mac de l'essai : mêmes six argmax et
écart maximal de 1,669172. Dans un environnement restreint, l'initialisation
Metal de la bibliothèque a échoué même avec `n_gpu_layers=0` ; l'exécution
hors de cet environnement a réussi. La disponibilité du backend est donc
une condition de reproduction, et `n_gpu_layers=0` ne supprime pas forcément
son initialisation.

## Hypothèses et travail recherché

Une piste est la quantification éventuelle des activations en Q8 dans les
kernels Q4_K/Q6_K de llama.cpp, tandis que le prototype Swift déquantifie les
poids en flottants. **Cela dépend du build et n'est pas établi pour le run.**
Comparer d'abord les produits matrice-vecteur sur les mêmes tenseurs et les
mêmes entrées à une référence en flottants utilisant les mêmes poids
déquantifiés ; comparer ensuite le chemin Q8, les sorties intermédiaires par
couche et les logits. Examiner aussi l'ordre d'accumulation, RoPE et GQA.
Ne conclure ni à un bug ni à une simple conséquence de la quantification sans
résultat discriminant. Les exemples et données de test doivent être fictifs.

Un contrôle partiel historique a été rejoué le 17 novembre 2026 : sur le
tenseur Q6_K `blk.0.ffn_down.weight`, pour un vecteur de test, le produit
par blocs Swift et un produit Swift sur poids préalablement déquantifiés en
Float32 donnent 18 944 résultats bit-identiques. Ils partagent cependant des
composants, et ce test ne compare ni les activations de ces six positions ni
les logits à une référence flottante indépendante. Il ne départage donc pas
les causes de l'écart avec llama.cpp ; c'est le travail à réaliser ci-dessus.
