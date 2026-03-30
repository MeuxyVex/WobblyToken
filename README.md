# WobblyToken
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="src/logo1.png">
  <img alt="Python cryptocurrency project">
</picture>

![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Web%20API-black?style=for-the-badge&logo=flask&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Blockchain](https://img.shields.io/badge/Blockchain-Simulation-purple?style=for-the-badge)
![Proof of Work](https://img.shields.io/badge/Proof%20of%20Work-Mining-orange?style=for-the-badge)


![Status](https://img.shields.io/badge/Status-In%20Development-yellow?style=for-the-badge)
![Last commit](https://img.shields.io/github/last-commit/MeuxyVex/WobblyToken?style=for-the-badge)



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
