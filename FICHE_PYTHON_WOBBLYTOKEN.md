# Fiche Python pour lire WobblyToken
## 0
Ce programme est à but éducatif il n'a pas pour but de prendre le role d'une vraie cryptomonnaie. Il est donc naturel que le code soit volontairement moins optimiser pour prioriser la lisibilité.

## 1. Niveau de départ et objectif

Cette fiche vise un élève de 2e année de gymnase qui connaît déjà :

- les variables et les types simples (`int`, `str`, `bool`) ;
- les conditions `if`, `elif`, `else` ;
- les boucles `for` et `while` ;
- les listes ;
- les fonctions simples.



WobblyToken ajoute plusieurs notions qui ne sont pas toujours maîtrisées à ce niveau : dictionnaires imbriqués, ensembles (`set`), tuples, exceptions, modules, API Flask et cryptographie appliquée.

L'objectif est de comprendre le projet et comment il a été écrit

## 2. Comment lire le projet

Ordre de lecture :

1. `wallet/keys.py` : création des clés ;
2. `wallet/address.py` : création et validation d'une adresse ;
3. `wallet/storage.py` : stockage du portefeuille ;
4. `transaction.py` : construction, signature et validation des transactions ;
5. `utxos.py` : reconstruction des UTXO et calcul des soldes ;
6. `app.py` : blocs, blockchain, endpoints et communication entre nœuds ;
7. `network.py` : informations affichées sur le réseau.


## 3. Les structures de données

### La liste : une suite ordonnée et modifiable

```python
mempool = []
mempool.append(transaction)
```

Une liste :

- conserve l'ordre ;
- accepte les doublons ;
- est modifiable ;
- utilise des indices commençant à `0`.

```python
transactions[0]   # première transaction
transactions[-1]  # dernière transaction
transactions[-5:] # au maximum les cinq dernières
```

Dans WobblyToken, une blockchain est une liste de blocs, un bloc contient une liste de transactions et une transaction contient des listes d'inputs et d'outputs.

### Le dictionnaire : associer une clé à une valeur

```python
output = {
    "address": "wbl_abc123",
    "amount": 5_000_000_000
}

adresse = output["address"]
```

Un dictionnaire est adapté lorsqu'une donnée possède plusieurs champs nommés.

Méthodes importantes :

```python
transaction.get("type")       # valeur ou None si la clé manque
transaction.get("type", "?") # valeur ou "?" si la clé manque
transaction.pop("txid", None) # retire txid ; ne plante pas s'il manque
utxos.items()                  # couples clé-valeur
utxos.values()                 # valeurs uniquement
```

`transaction["type"]` provoque une `KeyError` si la clé manque. `transaction.get("type")` retourne `None`.

### Le tuple : un groupe ordonné et non modifiable

```python
resultat = (True, "Transaction valide")
valide = resultat[0]
message = resultat[1]
```

Un tuple ressemble à une liste, mais il ne peut pas être modifié. Il peut servir de clé de dictionnaire :

```python
cle_utxo = (txid, output_index)
utxos[cle_utxo] = output
```

WobblyToken utilise actuellement une chaîne équivalente :

```python
cle_utxo = f"{txid}:{output_index}"
```

Ce n'est pas un tuple : le résultat est une seule chaîne, par exemple `"abc123:0"`.

### Le set : un ensemble sans doublon

```python
inputs_utilises = set()
inputs_utilises.add("abc123:0")
```

Un `set` :

- ne contient jamais deux fois la même valeur ;
- n'est pas conçu pour conserver un ordre ;
- permet de vérifier efficacement si une valeur est déjà présente.

```python
if utxo_key in inputs_utilises:
    return False, "UTXO utilisé plusieurs fois"

inputs_utilises.add(utxo_key)
```

Ici, le `set` empêche une transaction de dépenser deux fois le même UTXO.

Une liste pourrait aussi enregistrer les clés, mais elle accepterait les doublons et sa recherche deviendrait plus lente lorsque sa taille augmente.

## 4. Affectation, références et copies

```python
copie = transaction
```

Cette instruction ne crée pas réellement une nouvelle transaction. Les deux variables désignent le même dictionnaire.

```python
copie = transaction.copy()
```

Cette instruction crée un nouveau dictionnaire de premier niveau. C'est une **copie superficielle** : les listes et dictionnaires placés à l'intérieur restent partagés.

Dans `transaction_id`, la copie superficielle suffit, car le code retire seulement la clé `txid` du niveau principal :

```python
transaction_copy = transaction.copy()
transaction_copy.pop("txid", None)
```

Le dictionnaire original reste intact.

## 5. Boucles imbriquées et décomposition

```python
for block in blockchain:
    for transaction in block["transactions"]:
        for output in transaction["outputs"]:
            print(output)
```

La première boucle choisit un bloc. Pour ce bloc, la deuxième parcourt ses transactions. Pour chaque transaction, la troisième parcourt ses outputs.

Dans cette boucle :

```python
for utxo_key, output in utxos.items():
```

`utxos.items()` produit des couples `(clé, valeur)`. Python place la première partie dans `utxo_key` et la seconde dans `output`. Cela s'appelle la **décomposition** ou *unpacking*.

Version détaillée équivalente :

```python
for element in utxos.items():
    utxo_key = element[0]
    output = element[1]
```

### `continue` et `break`

```python
for peer in get_peers():
    if peer == source:
        continue
    envoyer(peer)
```

`continue` abandonne seulement l'itération actuelle et passe au pair suivant.

```python
if total_selectionne >= montant:
    break
```

`break` arrête complètement la boucle la plus proche.

## 6. Fonctions, paramètres et `None`

```python
def get_difficulty(chaine=None):
    if chaine is None:
        chaine = blockchain
```

Le paramètre est facultatif :

- `get_difficulty(ma_chaine)` utilise `ma_chaine` ;
- `get_difficulty()` reçoit `None`, puis utilise la blockchain globale.

`None` signifie « absence de valeur ». Ce n'est ni `0`, ni `False`, ni une chaîne vide.

### Retourner plusieurs informations

```python
return False, "Montant invalide"
```

Python retourne ici un tuple :

```python
resultat = validation_transaction_utxo(tx, utxos)
valide = resultat[0]   # bool
message = resultat[1] # str
```

On peut aussi le décomposer :

```python
valide, message = validation_transaction_utxo(tx, utxos)
```

## 7. Types et validation

```python
if not isinstance(transaction, dict):
    return False, "Transaction invalide"
```

`isinstance(valeur, type_attendu)` vérifie le type d'une valeur.

```python
if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
    return False, "Montant invalide"
```

Pourquoi vérifier `bool` séparément ? En Python, `bool` est une sous-classe de `int` :

```python
isinstance(True, int)  # True
```

Sans le premier test, `True` pourrait être accepté comme le montant `1`.

Les montants utilisent des entiers :

```python
COIN = 100_000_000
reward = 50 * COIN
```

Les `_` servent seulement à faciliter la lecture. `100_000_000` et `100000000` ont exactement la même valeur.

L'utilisation d'unités entières évite les imprécisions des nombres à virgule flottante.

## 8. Chaînes, f-strings et tranches

```python
utxo_key = f"{previous_txid}:{previous_output_index}"
```

Une f-string insère la valeur des expressions entre accolades dans une chaîne.

```python
chaine[-1]                 # dernier élément
chaine[-intervaldifficulty:] # derniers éléments de l'intervalle
```

Une tranche `liste[début:fin]` va du début inclus jusqu'à la fin exclue. Une borne négative compte depuis la fin.

```python
previous_txid, output_index = utxo_key.rsplit(":", 1)
```

`rsplit(":", 1)` coupe la chaîne une seule fois en partant de la droite. Le résultat contient deux chaînes qui sont ensuite décomposées dans deux variables.

## 9. Erreurs et exceptions

### Trois familles d'erreurs

- **Erreur de syntaxe** : Python ne peut pas lire le programme.
- **Erreur d'exécution** : le programme démarre, puis une opération échoue.
- **Erreur de logique ou de sémantique** : le programme fonctionne, mais donne un mauvais résultat.

### Exceptions fréquentes dans WobblyToken

- `ValueError` : la bonne sorte de donnée contient une valeur inutilisable, par exemple un faux nombre hexadécimal ;
- `TypeError` : une opération reçoit un mauvais type ;
- `KeyError` : une clé demandée n'existe pas dans un dictionnaire ;
- `requests.RequestException` : une communication HTTP échoue ;
- `ecdsa.BadSignatureError` : une signature cryptographique ne correspond pas.

```python
try:
    bytes.fromhex(public_key_hexa)
except ValueError:
    return False, "Clé publique invalide"
```

Le bloc `try` tente l'opération. `except` décrit quoi faire si l'exception prévue se produit.

```python
raise ValueError("Solde disponible insuffisant")
```

`raise` déclenche volontairement une exception. La fonction appelante doit la traiter ou laisser le programme s'arrêter.

Évite si possible `except:` sans type : il masque aussi des erreurs de programmation inattendues.

## 10. Modules et imports

```python
import hashlib
from wallet import walletcreation
```

- `import hashlib` importe le module ; on écrit ensuite `hashlib.sha256(...)`.
- `from wallet import walletcreation` importe directement un nom ; on écrit `walletcreation(...)`.

Fichiers importants :

- `hashlib` : fonctions de hachage ;
- `secrets` : nombres aléatoires adaptés à la sécurité ;
- `ecdsa` : signatures à clé publique ;
- `json` : conversion entre dictionnaires Python et texte JSON ;
- `requests` : requêtes HTTP vers d'autres nœuds ;
- `flask` : serveur HTTP du nœud ;
- `os` : fichiers, permissions et variables d'environnement.

## 11. JSON, HTTP et Flask

JSON représente les données échangées entre le navigateur, le registre et les nœuds :

```json
{
  "address": "wbl_abc123",
  "amount": 5000000000
}
```

Un objet JSON devient généralement un dictionnaire Python. Un tableau JSON devient une liste Python.

```python
@app.route("/send", methods=["POST"])
def envoyer_transaction():
    donnees = request.get_json(silent=True)
```

`@app.route(...)` est un **décorateur**. Il indique à Flask d'appeler cette fonction lorsqu'une requête correspondante arrive.

- `GET` demande une information ;
- `POST` envoie une nouvelle information ;
- `200` signifie que la requête a réussi ;
- `400` signifie que les données envoyées sont invalides.

```python
return jsonify(mempool)
```

`jsonify` transforme les données Python en réponse JSON.

### Client et serveur

Dans WobblyToken, chaque nœud joue les deux rôles :

- serveur lorsqu'il reçoit `/receive_block` ou `/receive_transaction` ;
- client lorsqu'il utilise `requests.post(...)` pour contacter un autre nœud.

## 12. Texte, octets, hachage et signature

Les fonctions cryptographiques travaillent avec des octets, pas directement avec du texte :

```python
message = json.dumps(transaction, sort_keys=True).encode()
```

Étapes :

1. le dictionnaire devient un texte JSON ;
2. `sort_keys=True` impose le même ordre aux clés ;
3. `.encode()` transforme le texte en octets.

```python
hashlib.sha256(message).hexdigest()
```

- `sha256` calcule une empreinte ;
- `hexdigest()` la représente avec les caractères `0-9` et `a-f`.

Un hash n'est pas un chiffrement : il n'est pas prévu pour retrouver le message initial.

Une signature fonctionne ainsi :

1. la clé privée signe le message ;
2. la clé publique vérifie la signature ;
3. modifier un input ou un output rend la signature invalide.

La clé privée ne doit jamais être envoyée avec une transaction.

## 13. Fichiers et portefeuille

```python
with open(path, "r") as fichier:
    wallet = json.load(fichier)
```

`with` garantit que le fichier sera fermé, même si une erreur se produit.

```python
os.chmod(path, 0o600)
```

Sous Linux, `0o600` donne au propriétaire le droit de lire et écrire le fichier, sans droit pour les autres utilisateurs.

```python
WALLET_PATH = os.getenv("WALLET_PATH", "/app/wallet/wallet.json")
```

`os.getenv` lit une variable d'environnement. Si elle n'existe pas, la deuxième valeur est utilisée.

## 14. Comprendre le modèle UTXO

Un UTXO est une sortie de transaction qui n'a pas encore été dépensée.

```text
Transaction A, output 0 : 30 WBL pour Alice
Transaction B, output 1 : 20 WBL pour Alice

Solde d'Alice = 30 + 20 = 50 WBL
```

Pour envoyer 40 WBL à Bob :

```text
Inputs :
  A:0 = 30 WBL
  B:1 = 20 WBL

Outputs :
  40 WBL pour Bob
  10 WBL de monnaie pour Alice
```

Les clés `"A:0"` et `"B:1"` identifient exactement les outputs dépensés.

### Reconstruction des UTXO

L'algorithme parcourt la blockchain dans l'ordre :

1. chaque input retire un ancien UTXO ;
2. chaque output crée un nouvel UTXO ;
3. ce qui reste à la fin est encore dépensable.

Le solde n'est donc pas stocké directement : il est calculé en additionnant les UTXO appartenant à une adresse.

## 15. Lire une validation de transaction pas à pas

Dans `validation_transaction_utxo`, suis cet ordre :

1. vérifier que la transaction est un dictionnaire ;
2. vérifier les champs obligatoires ;
3. vérifier qu'il existe au moins un input et un output ;
4. créer un `set` pour détecter un UTXO utilisé deux fois ;
5. vérifier que chaque UTXO existe ;
6. vérifier que la clé publique possède cet UTXO ;
7. vérifier la signature ;
8. additionner les montants d'entrée ;
9. valider les adresses et montants de sortie ;
10. vérifier que les sorties ne dépassent pas les entrées ;
11. recalculer et comparer le `txid`.

Cette fonction est longue parce qu'elle ne répond pas à une seule question. Elle construit une chaîne de preuves : structure valide, propriété valide, signature valide et conservation des fonds.

## 16. Comprendre la propagation entre nœuds

```python
for peer in get_peers():
    if peer == source:
        continue
    requests.post(f"{peer}/receive_transaction", json=message)
```

Chaque nœud :

1. reçoit une transaction ;
2. la valide localement ;
3. l'ajoute à sa mempool si elle est nouvelle ;
4. la transmet à ses autres pairs.

Le `txid` sert à reconnaître une transaction déjà reçue. Sans cette vérification, les nœuds pourraient se la renvoyer indéfiniment.

Une transaction peut cependant être valide sur un nœud et refusée sur un autre si leurs blockchains ne contiennent pas les mêmes UTXO. La synchronisation de la chaîne reste donc indispensable.

