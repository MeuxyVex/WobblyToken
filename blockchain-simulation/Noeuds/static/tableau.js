/* page du node, la clé privée reste sur le serveur */
"use strict";

const UNITE = 100000000n;
const etat = {
  portefeuille: {}, reseau: {}, chaine: [], utxos: {}, attente: [], solde: 0,
  occupe: false, actualise: false, actualisationDemandee: false, pageBlocs: 0, journal: [], objets: [],
  derniereReponse: null, configurationInitialisee: false
};
const element = identifiant => document.getElementById(identifiant);
const echapper = valeur => String(valeur ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
const abreger = (valeur, debut = 12, fin = 7) => {
  const texte = String(valeur ?? "");
  return texte.length > debut + fin + 1 ? texte.slice(0, debut) + "…" + texte.slice(-fin) : texte;
};
const json = valeur => JSON.stringify(valeur, null, 2);
const titres = {accueil: "Vue d’ensemble", paiements: "Transactions", contrats: "Contrats", explorateur: "Blocs & UTXO", reseau: "Réseau", outils: "Console API"};

const routes = [
  {nom: "GET / · Page du nœud", chemin: "/", description: "Lire la page HTML du nœud."},
  {nom: "GET /wallet · Identité publique", chemin: "/wallet", description: "Adresse et clé publique, sans clé privée."},
  {nom: "GET /balance · Solde d’une adresse", chemin: "/balance/", parametre: true, description: "Solde classique confirmé, en unités minimales."},
  {nom: "GET /utxos · Sorties non dépensées", chemin: "/utxos", description: "Tous les UTXO, y compris ceux sous contrat."},
  {nom: "GET /chain · Chaîne complète", chemin: "/chain", description: "Tous les blocs et leurs transactions."},
  {nom: "GET /transaction · Transactions en attente", chemin: "/transaction", description: "Transactions acceptées en attente d’un bloc."},
  {nom: "GET /network · Vue du réseau", chemin: "/network", description: "État local, nœuds et relations du registre."},
  {nom: "GET /mine · Miner un bloc", chemin: "/mine", description: "Action : mine un bloc, l’ajoute localement et le transmet aux pairs."},
  {nom: "GET /sync · Synchroniser", chemin: "/sync", description: "Action : adopte une chaîne valide de travail supérieur si elle existe."},
  {nom: "POST /send · Créer un paiement ou un dépôt", chemin: "/send", methode: "POST", exemple: {address: "wbl_…", amount: 100000000}, description: "Le nœud signe et diffuse. Remplacez address par contract pour un dépôt. Montants en unités minimales."},
  {nom: "POST /transaction · Soumettre une transaction", chemin: "/transaction", methode: "POST", exemple: {type: "standard", version: 2, inputs: [], outputs: [], txid: ""}, description: "Valide puis diffuse une transaction finalisée."},
  {nom: "POST /receive_transaction · Relayer une transaction", chemin: "/receive_transaction", methode: "POST", enveloppe: true, exemple: {transaction: {}, source: "http://node2:5000"}, description: "Reçoit une transaction provenant d’un autre nœud. Le champ source est facultatif."},
  {nom: "POST /receive_block · Recevoir un bloc", chemin: "/receive_block", methode: "POST", exemple: {index: 0, data: "", previous_hash: "0", nonce: 0, hash: "", difficulty: 4, time: 0, transactions: []}, description: "Importer un vrai bloc miné. Un exemple non miné sera refusé."},
  {nom: "POST /contracts/sign · Signer un brouillon", chemin: "/contracts/sign", methode: "POST", enveloppe: true, exemple: {transaction: {}}, description: "Ajoute la signature du portefeuille local. Ne diffuse rien."},
  {nom: "POST /contracts/check · Vérifier un brouillon", chemin: "/contracts/check", methode: "POST", enveloppe: true, exemple: {transaction: {}}, description: "Calcule le txid et vérifie les conditions pour le prochain bloc. Ne diffuse rien."},
  {nom: "GET /registry · Accueil du registre", chemin: "/registry", description: "Accès au registre depuis le nœud."},
  {nom: "GET /registry/nodes · Tous les nœuds", chemin: "/registry/nodes", description: "Relais vers GET /nodes du registre."},
  {nom: "GET /registry/peers · Voisins d’un nœud", chemin: "/registry/peers/", parametre: true, description: "Relais vers GET /peers/<nom> du registre."},
  {nom: "POST /registry/register · Inscrire un nœud", chemin: "/registry/register", methode: "POST", exemple: {node_name: "node4", address: "http://node4:5000"}, description: "Relais vers POST /register. Inscrit un serveur existant sans le démarrer."}
];

function notifier(message, erreur = false) {
  const cible = element("notification");
  cible.textContent = message;
  cible.className = "notification visible" + (erreur ? " erreur" : "");
  clearTimeout(notifier.delai);
  notifier.delai = setTimeout(() => cible.className = "notification", 6500);
}
function resultat(identifiant, texte, valide = true) {
  element(identifiant).textContent = texte;
  element(identifiant).className = "resultat " + (valide ? "succes" : "erreur");
}
function changerVue() {
  const nom = location.hash.slice(1) || "accueil";
  const vue = Object.hasOwn(titres, nom) ? nom : "accueil";
  document.querySelectorAll("[data-page]").forEach(page => page.hidden = page.dataset.page !== vue);
  document.querySelectorAll("[data-vue]").forEach(lien => {
    lien.classList.toggle("actif", lien.dataset.vue === vue);
    if (lien.dataset.vue === vue) lien.setAttribute("aria-current", "page");
    else lien.removeAttribute("aria-current");
  });
  element("titre-vue").textContent = titres[vue];
}
function ouvrirOnglet(nom) {
  element("panneau-depot").hidden = nom !== "depot";
  element("panneau-retrait").hidden = nom !== "retrait";
  document.querySelectorAll("[data-contrat-onglet]").forEach(bouton => {
    const actif = bouton.dataset.contratOnglet === nom;
    bouton.classList.toggle("actif", actif);
    bouton.setAttribute("aria-pressed", String(actif));
  });
}
function enregistrerReponse(chemin, methode, statut, donnees) {
  etat.derniereReponse = donnees;
  element("statut-api").textContent = methode + " " + chemin + " · HTTP " + statut;
  element("reponse-api").textContent = typeof donnees === "string" ? donnees : json(donnees);
  etat.journal.unshift({heure: new Date().toLocaleTimeString("fr-FR"), chemin, methode, statut});
  etat.journal = etat.journal.slice(0, 25);
  element("journal").innerHTML = etat.journal.map(ligne =>
    '<div class="ligne-journal"><time>' + echapper(ligne.heure) + '</time><span>' + echapper(ligne.methode + " " + ligne.chemin) +
    '</span><span class="statut-http ' + (ligne.statut >= 400 || !ligne.statut ? "echec" : "") + '">' +
    (ligne.statut || "Réseau") + "</span></div>").join("");
}
async function api(chemin, donnees, journaliser = true) {
  const methode = donnees === undefined ? "GET" : "POST";
  let reponse;
  try {
    reponse = await fetch(chemin, {
      method: methode, cache: "no-store",
      ...(donnees === undefined ? {} : {headers: {"Content-Type": "application/json"}, body: JSON.stringify(donnees)})
    });
  } catch {
    if (journaliser) enregistrerReponse(chemin, methode, 0, {message: "Le nœud est injoignable."});
    throw new Error("Le nœud est injoignable. Vérifiez qu’il est démarré.");
  }
  const texte = await reponse.text();
  let contenu = texte;
  if ((reponse.headers.get("content-type") || "").includes("application/json")) {
    try { contenu = JSON.parse(texte); } catch { contenu = {message: "Réponse JSON invalide du serveur."}; }
  }
  if (journaliser) enregistrerReponse(chemin, methode, reponse.status, contenu);
  if (!reponse.ok) throw new Error(contenu?.message || "Le serveur a répondu HTTP " + reponse.status);
  return contenu;
}
async function action(travail, sortie) {
  if (etat.occupe) { notifier("Une action est déjà en cours."); return; }
  etat.occupe = true;
  const boutons = [...document.querySelectorAll("button")].filter(bouton => !bouton.disabled);
  boutons.forEach(bouton => bouton.disabled = true);
  document.body.setAttribute("aria-busy", "true");
  try { await travail(); }
  catch (erreur) {
    notifier(erreur.message, true);
    if (sortie) resultat(sortie, erreur.message, false);
  } finally {
    etat.occupe = false;
    boutons.forEach(bouton => bouton.disabled = false);
    document.body.removeAttribute("aria-busy");
    await actualiser();
  }
}
function analyserJson(texte) {
  try {
    const valeur = JSON.parse(texte);
    if (valeur === null || typeof valeur !== "object") throw new Error();
    return valeur;
  } catch { throw new Error("JSON invalide : vérifiez les guillemets, les virgules et les accolades."); }
}
function entier(texte, minimum = 0) {
  const valeur = String(texte).trim();
  if (!valeur || [...valeur].some(caractere => !"0123456789".includes(caractere))) throw new Error("Un nombre entier positif est attendu.");
  const nombre = Number(valeur);
  if (!Number.isSafeInteger(nombre) || nombre < minimum) throw new Error("Nombre entier hors limites.");
  return nombre;
}
function lireMontant(texte) {
  const valeur = String(texte).trim().replace(",", ".");
  const parties = valeur.split(".");
  if (parties.length > 2 || !parties[0] || [...parties[0]].some(c => !"0123456789".includes(c))) throw new Error("Saisissez un montant positif en WBL.");
  const decimales = parties[1] ?? "";
  if ((parties.length === 2 && !decimales) || decimales.length > 8 || [...decimales].some(c => !"0123456789".includes(c))) throw new Error("Le montant accepte au maximum 8 décimales.");
  const unites = BigInt(parties[0]) * UNITE + BigInt(decimales.padEnd(8, "0"));
  if (unites <= 0n || unites > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error("Montant nul ou trop grand pour cette interface.");
  return Number(unites);
}
function montantSaisie(unites) {
  if (!Number.isSafeInteger(unites)) return "";
  const valeur = BigInt(unites);
  let decimales = String(valeur % UNITE).padStart(8, "0");
  while (decimales.endsWith("0")) decimales = decimales.slice(0, -1);
  return String(valeur / UNITE) + (decimales ? "." + decimales : "");
}
function wbl(unites) {
  const texte = montantSaisie(unites);
  if (!texte) return "Hors plage d’affichage";
  const [entierTexte, decimales] = texte.split(".");
  return BigInt(entierTexte).toLocaleString("fr-FR") + (decimales ? "," + decimales : "");
}
function disponible() {
  const reserves = new Set();
  for (const operation of etat.attente) for (const entree of operation.inputs || []) reserves.add(entree.txid + ":" + entree.output_index);
  let total = 0;
  for (const [reference, sortie] of Object.entries(etat.utxos))
    if (!sortie.contract && sortie.address === etat.portefeuille.address && !reserves.has(reference)) total += sortie.amount;
  return total;
}
function preuveCondition(condition) {
  if (!condition) return "Condition inconnue";
  if (condition.type === "signature") return "Signature · " + abreger(condition.address, 8, 5);
  if (condition.type === "after_block") return "À partir du bloc " + condition.height;
  if (condition.type === "hashlock") return "Secret SHA-256";
  if (condition.type === "multisig") return condition.required + " signatures sur " + (condition.addresses || []).length;
  if (condition.type === "and" || condition.type === "or") return "(" + (condition.conditions || []).map(preuveCondition).join(condition.type === "and" ? " ET " : " OU ") + ")";
  return "Condition inconnue";
}
function inspecter(titre, donnees) {
  element("titre-inspecteur").textContent = titre;
  element("contenu-inspecteur").textContent = typeof donnees === "string" ? donnees : json(donnees);
  element("inspecteur").showModal();
}
function boutonDetails(titre, objet) {
  const index = etat.objets.push({titre, objet}) - 1;
  return '<button class="bouton discret petit" data-inspecter="' + index + '">Détails ↗</button>';
}
function blocHtml(bloc) {
  return '<div class="ligne-bloc"><span class="numero-bloc">#' + echapper(bloc.index) + '</span><div class="info-bloc"><strong>' +
    echapper(bloc.data) + '</strong><code title="' + echapper(bloc.hash) + '">' + echapper(abreger(bloc.hash, 18, 10)) +
    '</code><div class="meta"><span>' + (bloc.transactions || []).length + ' transaction(s)</span><span>Difficulté ' + echapper(bloc.difficulty) +
    '</span></div></div><span class="valeur">' + echapper(wbl(bloc.transactions?.[0]?.outputs?.[0]?.amount || 0)) +
    ' WBL</span>' + boutonDetails("Bloc #" + bloc.index, bloc) + "</div>";
}
function rendreBlocs() {
  const recherche = element("recherche-bloc").value.trim().toLowerCase();
  const blocs = [...etat.chaine].reverse().filter(bloc => [bloc.index, bloc.hash, bloc.data].some(valeur => String(valeur).toLowerCase().includes(recherche)));
  const pages = Math.max(1, Math.ceil(blocs.length / 10));
  etat.pageBlocs = Math.min(etat.pageBlocs, pages - 1);
  element("blocs-recents").innerHTML = etat.chaine.length ? [...etat.chaine].reverse().slice(0, 4).map(blocHtml).join("") :
    '<div class="vide"><strong>Tout commence par un bloc.</strong>Minez votre premier bloc pour recevoir des WBL.</div>';
  element("tous-blocs").innerHTML = blocs.length ? blocs.slice(etat.pageBlocs * 10, etat.pageBlocs * 10 + 10).map(blocHtml).join("") : '<p class="vide">Aucun bloc à afficher.</p>';
  element("page-blocs").textContent = "Page " + (etat.pageBlocs + 1) + " / " + pages;
  element("blocs-precedents").disabled = etat.pageBlocs === 0 || etat.occupe;
  element("blocs-suivants").disabled = etat.pageBlocs === pages - 1 || etat.occupe;
}
function rendreUtxos() {
  const recherche = element("recherche-utxo").value.trim().toLowerCase();
  const filtre = element("filtre-utxo").value;
  const entrees = Object.entries(etat.utxos).filter(([ref, sortie]) =>
    (ref.toLowerCase().includes(recherche) || (sortie.address || "").toLowerCase().includes(recherche)) &&
    (filtre !== "miens" || (!sortie.contract && sortie.address === etat.portefeuille.address)) &&
    (filtre !== "contrats" || sortie.contract));
  element("total-utxos").textContent = Object.keys(etat.utxos).length + " UTXO";
  element("table-utxos").innerHTML = entrees.length ? entrees.map(([ref, sortie]) =>
    '<tr><td><code title="' + echapper(ref) + '">' + echapper(abreger(ref, 14, 8)) + '</code></td><td>' +
    (sortie.contract ? '<span class="badge jaune">Contrat</span><small>' + echapper(preuveCondition(sortie.contract.condition)) + '</small>' :
    '<code title="' + echapper(sortie.address) + '">' + echapper(abreger(sortie.address)) + '</code>' + (sortie.address === etat.portefeuille.address ? '<small>Votre portefeuille</small>' : '')) +
    '</td><td class="valeur">' + echapper(wbl(sortie.amount)) + ' WBL</td><td>' + boutonDetails("UTXO " + ref, {reference: ref, ...sortie}) +
    (sortie.contract ? '<button class="bouton secondaire petit" data-depenser="' + echapper(ref) + '">Dépenser</button>' : '') + '</td></tr>').join("") :
    '<tr><td colspan="4" class="vide">Aucun UTXO ne correspond à ce filtre.</td></tr>';
  const selection = element("utxo-contrat").value;
  const contrats = Object.entries(etat.utxos).filter(([, sortie]) => sortie.contract);
  element("utxo-contrat").innerHTML = '<option value="">Sélectionnez un contrat confirmé…</option>' +
    contrats.map(([ref, sortie]) => '<option value="' + echapper(ref) + '">' + echapper(abreger(ref) + " · " + wbl(sortie.amount) + " WBL · " + preuveCondition(sortie.contract.condition)) + '</option>').join("");
  element("utxo-contrat").value = contrats.some(([ref]) => ref === selection) ? selection : "";
  afficherContratSelectionne();
}
function rendreAttente() {
  element("liste-attente").innerHTML = etat.attente.length ? etat.attente.map(operation =>
    '<div class="ligne-transaction"><span class="icone-stat jaune-clair">↗</span><div class="info-bloc"><strong>Transaction ' +
    echapper(abreger(operation.txid)) + '</strong><div class="meta"><span>' + operation.inputs.length + ' entrée(s)</span><span>' +
    operation.outputs.length + ' sortie(s)</span><span>Version ' + (operation.version || 1) + '</span></div></div>' +
    boutonDetails("Transaction en attente", operation) + '</div>').join("") : '<p class="vide">Aucune transaction en attente. Vos prochains envois apparaîtront ici.</p>';
}
function adresseNoeud(nom) {
  const texte = String(nom);
  if (texte === document.body.dataset.noeud) return location.origin + "/";
  //ports des trois nodes dans le docker-compose
  if (!["node1", "node2", "node3"].includes(texte)) return null;
  const suffixe = texte.slice(4);
  if (!suffixe || [...suffixe].some(c => !"0123456789".includes(c))) return null;
  const port = 5000 + Number(suffixe);
  if (!Number.isSafeInteger(port) || port > 65535) return null;
  const url = new URL(location.href);
  url.port = String(port); url.pathname = "/"; url.hash = ""; url.search = "";
  return url.href;
}
function rendreReseau() {
  const noeuds = Array.isArray(etat.reseau.nodes) ? etat.reseau.nodes : [];
  element("noeuds").innerHTML = noeuds.length ? noeuds.map(noeud => {
    const actuel = noeud.node_name === etat.reseau.current_node;
    const adresse = adresseNoeud(noeud.node_name);
    return '<article class="carte noeud ' + (actuel ? 'actuel' : '') + '"><div class="entre"><span class="icone-stat">◎</span>' +
      (actuel ? '<span class="badge">Ce nœud</span>' : '<span class="badge jaune">Inscrit</span>') + '</div><h3>' +
      echapper(noeud.node_name) + '</h3><code>' + echapper(noeud.address) + '</code>' +
      (adresse ? '<a class="lien" href="' + echapper(adresse) + '">' + (actuel ? 'Ouvrir ce nœud' : 'Ouvrir le tableau de bord') + ' ↗</a>' : '<small class="texte-doux">Adresse publique à ouvrir manuellement</small>') +
      '<p class="aide">Inscription au registre, sans garantie de disponibilité.</p></article>';
  }).join("") : '<p class="vide">Aucun nœud retourné par le registre.</p>';
  const uniques = new Set();
  const relations = [];
  for (const lien of etat.reseau.relations || []) {
    const source = lien.source || lien.from, cible = lien.target || lien.to;
    const cle = [source, cible].sort().join(":");
    if (!source || !cible || uniques.has(cle)) continue;
    uniques.add(cle); relations.push('<span class="relation">' + echapper(source) + ' <span class="point">↔</span> ' + echapper(cible) + '</span>');
  }
  element("relations").innerHTML = relations.join("") || '<span class="texte-doux">Aucune relation connue.</span>';
  element("etat-registre").textContent = etat.reseau.error ? "Registre indisponible : " + etat.reseau.error : "Registre : " + (etat.reseau.registry_url || "non configuré");
}
function rendre() {
  etat.objets = [];
  const contrats = Object.values(etat.utxos).filter(sortie => sortie.contract);
  element("solde").textContent = wbl(etat.solde);
  element("solde-unites").textContent = "· " + Number(etat.solde).toLocaleString("fr-FR") + " unités";
  element("disponible").textContent = element("disponible-formulaire").textContent = wbl(disponible()) + " WBL";
  element("adresse-portefeuille").textContent = etat.portefeuille.address || "Indisponible";
  element("cle-publique").textContent = etat.portefeuille.public_key || "Indisponible";
  element("nombre-blocs").textContent = etat.chaine.length;
  element("hauteur").textContent = etat.chaine.length ? "Dernier index : " + (etat.chaine.length - 1) : "Aucun bloc";
  element("nombre-attente").textContent = element("badge-attente").textContent = etat.attente.length;
  element("nombre-contrats").textContent = contrats.length;
  element("montant-contrats").textContent = wbl(contrats.reduce((somme, sortie) => somme + sortie.amount, 0)) + " WBL · toute la chaîne";
  element("nombre-noeuds").textContent = (etat.reseau.nodes || []).length;
  element("nombre-pairs").textContent = (etat.reseau.current_peers || []).length + " pair(s) direct(s)";
  element("difficulte").textContent = etat.chaine.at(-1)?.difficulty ?? "—";
  let travail = 0n;
  for (const bloc of etat.chaine) if (Number.isInteger(bloc.difficulty) && bloc.difficulty >= 0 && bloc.difficulty <= 64) travail += 16n ** BigInt(bloc.difficulty);
  element("travail").textContent = travail.toLocaleString("fr-FR");
  element("aide-hauteur").textContent = "Le prochain bloc aura l’index " + etat.chaine.length + ". La condition est satisfaite dès l’index indiqué.";
  if (!etat.configurationInitialisee && etat.portefeuille.address) {
    for (const identifiant of ["signataire", "adresse-retrait", "adresse-solde"]) element(identifiant).value = etat.portefeuille.address;
    element("nom-pairs").value = document.body.dataset.noeud;
    exempleComposition();
    etat.configurationInitialisee = true;
  }
  rendreBlocs(); rendreUtxos(); rendreAttente(); rendreReseau();
}
async function actualiser() {
  if (etat.actualise) { etat.actualisationDemandee = true; return; }
  if (etat.occupe) return;
  etat.actualise = true;
  try {
    const [portefeuille, chaine, utxos, attente, reseau] = await Promise.all([
      api("/wallet", undefined, false), api("/chain", undefined, false), api("/utxos", undefined, false),
      api("/transaction", undefined, false), api("/network", undefined, false).catch(erreur => ({nodes: [], error: erreur.message}))
    ]);
    const solde = await api("/balance/" + encodeURIComponent(portefeuille.address), undefined, false);
    etat.portefeuille = portefeuille; etat.chaine = chaine; etat.utxos = utxos; etat.attente = attente; etat.reseau = reseau; etat.solde = solde.balance;
    rendre();
    element("connexion").className = "connexion en-ligne";
    element("connexion").lastElementChild.textContent = document.body.dataset.noeud + " · connecté";
    element("derniere-actualisation").textContent = "Actualisé à " + new Date().toLocaleTimeString("fr-FR");
    element("erreur-globale").hidden = true;
  } catch (erreur) {
    element("connexion").className = "connexion hors-ligne";
    element("connexion").lastElementChild.textContent = "Connexion interrompue";
    element("erreur-globale").textContent = erreur.message + " Les dernières données affichées peuvent être anciennes.";
    element("erreur-globale").hidden = false;
  } finally {
    etat.actualise = false;
    //si une action vient de finir on recharge encore les données
    if (etat.actualisationDemandee) {
      etat.actualisationDemandee = false;
      await actualiser();
    }
  }
}
async function miner() {
  await action(async () => {
    notifier("Minage en cours… La durée dépend de la difficulté.");
    const bloc = await api("/mine");
    notifier("Bloc #" + bloc.index + " miné. " + bloc.transactions.length + " transaction(s) confirmée(s).");
  });
}
async function synchroniser() {
  await action(async () => {
    notifier("Recherche de la chaîne valide au travail le plus élevé…");
    const chaine = await api("/sync");
    notifier("Synchronisation terminée : " + chaine.length + " bloc(s) locaux.");
  });
}
async function copier(texte) {
  if (!texte) { notifier("Aucune donnée à copier.", true); return; }
  try { await navigator.clipboard.writeText(texte); notifier("Copié dans le presse-papiers."); }
  catch { inspecter("Copiez ce contenu", texte); }
}
function exporter(nom, contenu) {
  const adresse = URL.createObjectURL(new Blob([json(contenu)], {type: "application/json"}));
  const lien = document.createElement("a"); lien.href = adresse; lien.download = nom;
  document.body.append(lien); lien.click(); lien.remove();
  setTimeout(() => URL.revokeObjectURL(adresse), 1000);
}
function lireContrat() {
  const type = element("type-contrat").value;
  let condition;
  if (type === "signature") {
    const adresse = element("signataire").value.trim();
    if (!adresse) throw new Error("Indiquez l’adresse du signataire.");
    condition = {type, address: adresse};
  } else if (type === "after_block") condition = {type, height: entier(element("hauteur-contrat").value)};
  else if (type === "hashlock") {
    const empreinte = element("empreinte-secret").value.trim();
    if (empreinte.length !== 64 || [...empreinte].some(c => !"0123456789abcdef".includes(c))) throw new Error("L’empreinte SHA-256 doit contenir 64 caractères hexadécimaux minuscules.");
    condition = {type, hash: empreinte};
  } else if (type === "multisig") {
    const adresses = element("signataires").value.split("\n").map(adresse => adresse.trim()).filter(Boolean);
    const seuil = entier(element("seuil-signatures").value, 1);
    if (adresses.length > 16 || adresses.length < seuil || new Set(adresses).size !== adresses.length) throw new Error("Indiquez de 1 à 16 adresses distinctes, en nombre suffisant pour le seuil.");
    condition = {type, required: seuil, addresses: adresses};
  } else {
    const conditions = analyserJson(element("sous-conditions").value);
    if (!Array.isArray(conditions) || !conditions.length) throw new Error("Une liste JSON non vide de conditions est attendue.");
    condition = {type, conditions};
  }
  return {version: 1, condition};
}
function changerTypeContrat() {
  const type = element("type-contrat").value;
  for (const [nom, visible] of Object.entries({signature: type === "signature", hauteur: type === "after_block", secret: type === "hashlock", multisig: type === "multisig", composition: type === "and" || type === "or"}))
    element("champ-" + nom).hidden = !visible;
  const messages = {
    signature: "Seules les signatures de l’adresse indiquée autoriseront une dépense.",
    after_block: "Une hauteur seule autorise toute personne à dépenser les fonds après ce bloc. Ajoutez une signature avec ET pour désigner un propriétaire.",
    hashlock: "Quiconque connaît le secret peut dépenser ces fonds. Combinez cette règle avec une signature pour réserver la dépense.",
    multisig: "Il faut des signatures d’adresses distinctes. Chaque personne signe la même transaction de retrait.",
    and: "Toutes les sous-conditions doivent être satisfaites par les preuves de la même entrée.",
    or: "Une seule branche suffit. Vérifiez qu’aucune branche n’autorise une dépense trop large."
  };
  element("note-contrat").textContent = messages[type];
  element("apercu-contrat").textContent = "Prévisualisez cette condition avant de déposer.";
}
function exempleComposition() {
  element("sous-conditions").value = json([
    {type: "signature", address: etat.portefeuille.address || "wbl_…"},
    {type: "after_block", height: etat.chaine.length + 3}
  ]);
}
function afficherContratSelectionne() {
  const sortie = etat.utxos[element("utxo-contrat").value];
  element("details-contrat").textContent = sortie ? wbl(sortie.amount) + " WBL\n" + json(sortie.contract) : "Sélectionnez un UTXO à contrat confirmé.";
}
function lireBrouillon() {
  const operation = analyserJson(element("brouillon").value);
  if (Array.isArray(operation) || operation.version !== 2 || operation.type !== "standard" || !Array.isArray(operation.inputs) || !Array.isArray(operation.outputs)) throw new Error("Le brouillon doit être une transaction standard de version 2 avec inputs et outputs.");
  return operation;
}
function resumerBrouillon() {
  try {
    const operation = lireBrouillon();
    element("resume-retrait").textContent = operation.inputs.length + " entrée(s) → " + operation.outputs.map(sortie => wbl(sortie.amount) + " WBL vers " + (sortie.contract ? "un contrat" : abreger(sortie.address))).join(" · ");
  } catch { element("resume-retrait").textContent = "Préparez ou importez un brouillon valide."; }
}
function placerBrouillon(operation) {
  element("brouillon").value = json(operation); resumerBrouillon();
}
async function verifierBrouillon(signer = false) {
  const operation = lireBrouillon();
  const reponse = await api(signer ? "/contracts/sign" : "/contracts/check", {transaction: operation});
  placerBrouillon(reponse.transaction);
  resultat("resultat-retrait", (signer ? "Signature locale ajoutée. " : "") +
    (reponse.valid ? "Les conditions sont satisfaites pour le prochain bloc." : "Dépense non autorisée pour le moment : " + reponse.message), reponse.valid);
  return reponse;
}
function changerRouteApi() {
  const route = routes[Number(element("route-api").value)];
  element("description-api").textContent = route.description;
  element("champ-parametre-api").hidden = !route.parametre;
  element("parametre-api").required = Boolean(route.parametre);
  element("champ-corps-api").hidden = route.methode !== "POST";
  element("corps-api").value = route.exemple ? json(route.exemple) : "";
  element("importer-dernier").hidden = !["/transaction", "/receive_transaction", "/contracts/sign", "/contracts/check"].includes(route.chemin);
  if (route.parametre) element("parametre-api").value = route.chemin === "/balance/" ? etat.portefeuille.address || "" : document.body.dataset.noeud;
}

/* les boutons lancent les actions, actualiser ne mine pas et n'envoie rien */
element("actualiser").addEventListener("click", () => actualiser());
element("miner").addEventListener("click", miner);
element("synchroniser").addEventListener("click", synchroniser);
element("copier-adresse").addEventListener("click", () => copier(etat.portefeuille.address));
element("copier-cle").addEventListener("click", () => copier(etat.portefeuille.public_key));
element("fermer-inspecteur").addEventListener("click", () => element("inspecteur").close());
element("copier-inspecteur").addEventListener("click", () => copier(element("contenu-inspecteur").textContent));
element("inspecteur").addEventListener("click", evenement => { if (evenement.target === element("inspecteur")) element("inspecteur").close(); });
document.addEventListener("click", evenement => {
  const details = evenement.target.closest("[data-inspecter]");
  if (details) { const objet = etat.objets[Number(details.dataset.inspecter)]; if (objet) inspecter(objet.titre, objet.objet); }
  const depense = evenement.target.closest("[data-depenser]");
  if (depense) { location.hash = "contrats"; ouvrirOnglet("retrait"); element("utxo-contrat").value = depense.dataset.depenser; afficherContratSelectionne(); }
  const onglet = evenement.target.closest("[data-contrat-onglet]");
  if (onglet) ouvrirOnglet(onglet.dataset.contratOnglet);
  const bouton = evenement.target.closest("[data-action]");
  if (bouton?.dataset.action === "miner") miner();
  if (bouton?.dataset.action === "synchroniser") synchroniser();
});
element("montant-max").addEventListener("click", () => element("montant").value = montantSaisie(disponible()));
element("form-paiement").addEventListener("submit", evenement => {
  evenement.preventDefault();
  action(async () => {
    const montant = lireMontant(element("montant").value);
    if (montant > disponible()) throw new Error("Le montant dépasse les fonds classiques disponibles.");
    const reponse = await api("/send", {address: element("destinataire").value.trim(), amount: montant});
    resultat("resultat-paiement", reponse.message + "\nMine un bloc pour confirmer le paiement.");
    notifier("Paiement ajouté aux transactions en attente.");
  }, "resultat-paiement");
});
element("form-solde").addEventListener("submit", evenement => {
  evenement.preventDefault();
  action(async () => {
    const reponse = await api("/balance/" + encodeURIComponent(element("adresse-solde").value.trim()));
    resultat("solde-consulte", wbl(reponse.balance) + " WBL confirmés · " + reponse.balance.toLocaleString("fr-FR") + " unités.");
  }, "solde-consulte");
});
element("type-contrat").addEventListener("change", changerTypeContrat);
element("mon-adresse-contrat").addEventListener("click", () => element("signataire").value = etat.portefeuille.address || "");
element("mon-adresse-retrait").addEventListener("click", () => element("adresse-retrait").value = etat.portefeuille.address || "");
element("exemple-composition").addEventListener("click", exempleComposition);
element("previsualiser-contrat").addEventListener("click", () => {
  try { element("apercu-contrat").textContent = json(lireContrat()); }
  catch (erreur) { notifier(erreur.message, true); }
});
element("calculer-empreinte").addEventListener("click", async () => {
  try {
    if (!globalThis.crypto?.subtle) throw new Error("Le calcul local SHA-256 nécessite localhost ou HTTPS. Vous pouvez aussi coller une empreinte déjà calculée.");
    const octets = new TextEncoder().encode(element("secret-depot").value);
    if (octets.length > 4096) throw new Error("Le secret dépasse 4096 octets.");
    const empreinte = await crypto.subtle.digest("SHA-256", octets);
    element("empreinte-secret").value = [...new Uint8Array(empreinte)].map(octet => octet.toString(16).padStart(2, "0")).join("");
    notifier("Empreinte calculée localement.");
  } catch (erreur) { notifier(erreur.message, true); }
});
element("form-depot").addEventListener("submit", evenement => {
  evenement.preventDefault();
  action(async () => {
    const contrat = lireContrat();
    const montant = lireMontant(element("montant-depot").value);
    if (montant > disponible()) throw new Error("Le montant dépasse les fonds classiques disponibles.");
    element("apercu-contrat").textContent = json(contrat);
    const reponse = await api("/send", {contract: contrat, amount: montant});
    resultat("resultat-depot", "Dépôt en attente. Minez un bloc, puis ouvrez « Dépenser un contrat ».\nRéférence : " + reponse.transaction.txid + ":0");
    notifier("Dépôt créé. Il reste à le confirmer par minage.");
  }, "resultat-depot");
});
element("utxo-contrat").addEventListener("change", afficherContratSelectionne);
element("preparer-retrait").addEventListener("click", () => {
  try {
    const reference = element("utxo-contrat").value;
    const sortie = etat.utxos[reference];
    if (!sortie?.contract) throw new Error("Sélectionnez un UTXO à contrat.");
    if (!Number.isSafeInteger(sortie.amount)) throw new Error("Montant trop grand pour une édition fiable dans cette interface.");
    const adresse = element("adresse-retrait").value.trim();
    if (!adresse) throw new Error("Indiquez le destinataire des fonds.");
    const separation = reference.lastIndexOf(":");
    const preuve = {secret: element("secret-retrait").value};
    placerBrouillon({version: 2, type: "standard",
      inputs: [{txid: reference.slice(0, separation), output_index: Number(reference.slice(separation + 1)), proof: preuve}],
      outputs: [{address: adresse, amount: sortie.amount}]
    });
    resultat("resultat-retrait", "Brouillon préparé. Vérifiez le destinataire, puis signez si le contrat l’exige.");
  } catch (erreur) { notifier(erreur.message, true); }
});
element("brouillon").addEventListener("input", () => {
  resumerBrouillon();
  resultat("resultat-retrait", "Brouillon modifié : une nouvelle vérification est nécessaire.", false);
});
element("importer-brouillon").addEventListener("change", async evenement => {
  try {
    const fichier = evenement.target.files[0];
    if (!fichier) return;
    if (fichier.size > 1000000) throw new Error("Le brouillon dépasse 1 Mo.");
    const contenu = analyserJson(await fichier.text());
    placerBrouillon(contenu.transaction || contenu);
    lireBrouillon();
    resultat("resultat-retrait", "Brouillon importé. Vérifiez les sorties avant d’ajouter votre signature.");
  } catch (erreur) { notifier(erreur.message, true); }
  finally { evenement.target.value = ""; }
});
element("signer-retrait").addEventListener("click", () => action(() => verifierBrouillon(true), "resultat-retrait"));
element("verifier-retrait").addEventListener("click", () => action(() => verifierBrouillon(false), "resultat-retrait"));
element("envoyer-retrait").addEventListener("click", () => action(async () => {
  const reponse = await verifierBrouillon(false);
  if (!reponse.valid) throw new Error("Dépense refusée : " + reponse.message);
  const soumission = await api("/transaction", reponse.transaction);
  resultat("resultat-retrait", soumission.message + "\nLa dépense attend maintenant un bloc.");
  notifier("Dépense de contrat soumise.");
}, "resultat-retrait"));
element("exporter-brouillon").addEventListener("click", () => {
  try { exporter("wobblytoken-brouillon.json", lireBrouillon()); }
  catch (erreur) { notifier(erreur.message, true); }
});
element("exporter-chaine").addEventListener("click", () => exporter("wobblytoken-chaine.json", etat.chaine));
element("recherche-utxo").addEventListener("input", rendreUtxos);
element("filtre-utxo").addEventListener("change", rendreUtxos);
element("recherche-bloc").addEventListener("input", () => { etat.pageBlocs = 0; rendreBlocs(); });
element("blocs-precedents").addEventListener("click", () => { etat.pageBlocs = Math.max(0, etat.pageBlocs - 1); rendreBlocs(); });
element("blocs-suivants").addEventListener("click", () => { etat.pageBlocs += 1; rendreBlocs(); });
element("form-pairs").addEventListener("submit", evenement => {
  evenement.preventDefault();
  action(async () => {
    element("resultat-pairs").textContent = json(await api("/registry/peers/" + encodeURIComponent(element("nom-pairs").value.trim())));
  });
});
element("form-inscription").addEventListener("submit", evenement => {
  evenement.preventDefault();
  action(async () => {
    const reponse = await api("/registry/register", {node_name: element("nom-inscription").value.trim(), address: element("adresse-inscription").value.trim()});
    resultat("resultat-inscription", reponse.message);
  }, "resultat-inscription");
});
element("route-api").innerHTML = routes.map((route, index) => '<option value="' + index + '">' + echapper(route.nom) + '</option>').join("");
element("route-api").addEventListener("change", changerRouteApi);
element("form-api").addEventListener("submit", evenement => {
  evenement.preventDefault();
  action(async () => {
    const route = routes[Number(element("route-api").value)];
    const chemin = route.chemin + (route.parametre ? encodeURIComponent(element("parametre-api").value.trim()) : "");
    await api(chemin, route.methode === "POST" ? analyserJson(element("corps-api").value) : undefined);
    notifier("Requête exécutée. La réponse complète est affichée.");
  });
});
element("importer-dernier").addEventListener("click", () => {
  try {
    const route = routes[Number(element("route-api").value)];
    const operation = lireBrouillon();
    element("corps-api").value = json(route.enveloppe ? {transaction: operation} : operation);
  } catch (erreur) { notifier(erreur.message, true); }
});
element("copier-reponse").addEventListener("click", () => copier(element("reponse-api").textContent));
element("vider-journal").addEventListener("click", () => { etat.journal = []; element("journal").innerHTML = '<p class="vide">Le journal de session est vide.</p>'; });
window.addEventListener("hashchange", changerVue);
changerVue(); changerTypeContrat(); changerRouteApi(); actualiser();
setInterval(() => { if (element("automatique").checked) actualiser(); }, 8000);
