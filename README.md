# WobblyToken
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="src/logo.ppg">
  <img alt="Python cryptocurrency project">
</picture>

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.1.0-brightgreen)](CHANGELOG.md)
![Repo size](https://img.shields.io/github/repo-size/MeuxyVex/WobblyToken?style=for-the-badge)
![Last commit](https://img.shields.io/github/last-commit/MeuxyVex/WobblyToken?style=for-the-badge)
![Issues](https://img.shields.io/github/issues/MeuxyVex/WobblyToken?style=for-the-badge)
![Stars](https://img.shields.io/github/stars/MeuxyVex/WobblyToken?style=for-the-badge)


## État actuel

Mini-blockchain avec 2 nœuds qui communiquent, minent et mettent à jour une blockchain.

## Fonctionnalités

- `/mine` : crée un nouveau bloc
- `/receive_block` : reçoit un bloc depuis l’autre nœud
- `/chain` : affiche la blockchain
- `/sync` : synchronise la blockchain avec l’autre nœud
- `/transaction` : Affiche le mempool avec méthode GET et envoie des transactions avec POST 

## Urls

http://localhost:5001/....
http://localhost:5002/....

Remplace les .... avec une des routes si dessus

## Utilisation

```bash
git clone https://github.com/MeuxyVex/WobblyToken
cd WobblyToken/blockchain-simulation
docker compose up --build

```

## Transactions

```bash
curl -X POST http://localhost:5001/transaction \
-H "Content-Type: application/json" \
-d "{\"sender\":\"Alice\",\"receiver\":\"Bob\",\"amount\":10}"
```
