# ShopperGPT × Carrefour Traiteur — Documentation

Ce document décrit les deux interfaces exposées par le module Magento `Carrefour_ShopperGPT` pour le partenaire ShopperGPT (Redpill) :

1. **Exports JSONL** (batch journalier) — catalogue, prix par magasin, référentiel magasins
2. **API REST Cart** (temps réel) — lecture / modification du panier d'un utilisateur via son `session_id`

> 📋 **Statut : DRAFT V1 — sans authentification.**
> Objectif de ce document : faire valider par l'équipe IA les requêtes / réponses / format JSON et identifier ce qui manque côté contrat avant d'ajouter la couche sécurité.

---

# Partie 1 — Exports JSONL

## Vue d'ensemble

3 fichiers JSONL générés en batch :

| Fichier | Contenu |
|---|---|
| `products.jsonl` | Catalogue (catégories + attributs EAV) |
| `products_prices.jsonl` | Matrice (produit, magasin, prix) + disponibilité |
| `stores.jsonl` | Référentiel magasins (adresses, concepts, livraison) |

Format : **JSONL** (1 objet JSON par ligne). Le CSV n'a pas été retenu car il ne peut pas représenter les structures imbriquées (catégories, composition, ean_vente/plu par type de magasin, etc.). Avantage opérationnel : on peut écrire ligne par ligne pendant l'export, sans attendre que tout le traitement soit fini — côté partenaire, même chose en lecture.

## Commandes pour générer les exports

```bash
# 1. Catalogue produits
php -r \
  'require "app/Mage.php"; Mage::app(); Mage::getModel("carrefour_cron/export_products")->export();'

# 2. Prix par produit × magasin (avec disponibilité incluse)
php -r \
  'require "app/Mage.php"; Mage::app(); Mage::getModel("carrefour_cron/export_productsPrices")->export();'

# 3. Référentiel magasins
php -r \
  'require "app/Mage.php"; Mage::app(); Mage::getModel("carrefour_cron/export_stores")->export();'
```

Tous les fichiers sont écrits dans `var/export/`.

---

## 1. `products.jsonl` — Catalogue produits

1 ligne par produit. **Exemple complet (63 champs)** sur le produit PID 100 (`"Buffet Gourmand pour 10"`). Les contenus HTML longs sont tronqués (`...`) pour la lisibilité, mais sont bien présents dans l'export.

L'ordre des clés dans le JSON réel n'est pas garanti. Les regroupements ci-dessous sont uniquement pour faciliter la lecture.

```jsonc
{
  // === Identité produit ===
  "product_id": 100,                                  // ID Magento
  "sku": "2016021572",                                // Référence produit
  "type_id": "simple",                                // simple / configurable / plateau / bundle
  "name": "Buffet Gourmand pour 10",
  "status": "Activé",                                 // "Activé" / "Désactivé"
  "visibility": "Catalogue, Recherche",               // "Non visible individuellement" / "Catalogue" / "Chercher" / "Catalogue, Recherche"
  "cdbase": "5570218",                                // Code base interne
  "tax_class_id": "TVA 5,5%",                         // Classe de TVA
  "url_key": "buffet-gourmand-pour-10",               // Slug URL
  "url_path": "buffet-gourmand-pour-10.html",         // URL frontend complète

  // === Rayon / restrictions ===
  "carrefour_suppliers_department": "Charcuterie",    // Département / rayon
  "carrefour_store_restriction": ["Hyper", "Super"],  // Types de magasins autorisés

  // === Catégories assignées (relation) ===
  "categories": [
    {"category_id": 325,  "category_name": "Buffets & cocktails dinatoires"},
    {"category_id": 341,  "category_name": "Diner de gala"},
    {"category_id": 345,  "category_name": "Déjeuner de fête"},
    {"category_id": 350,  "category_name": "Pour le cocktail"},
    {"category_id": 360,  "category_name": "Naissance / Baptême"},
    {"category_id": 383,  "category_name": "A table !"},
    {"category_id": 469,  "category_name": "Apéritif de fête"},
    {"category_id": 470,  "category_name": "Déjeuner de fête"},
    {"category_id": 847,  "category_name": "Traiteur pour 10 personnes"},
    {"category_id": 862,  "category_name": "Buffet froid"},
    {"category_id": 865,  "category_name": "Buffet froid mariage"},
    {"category_id": 866,  "category_name": "Buffet mariage"},
    {"category_id": 888,  "category_name": "Wraps"},
    {"category_id": 985,  "category_name": "Plats"},
    {"category_id": 1002, "category_name": "Buffets & Cocktails & Plateaux"},
    {"category_id": 1032, "category_name": "Cocktail Dînatoire & Buffet Gourmand"}
  ],

  // === Conditionnement / poids ===
  "weight": "0.0000",                                 // Poids brut
  "weight_variation": null,                           // Variation de poids (si pesée)
  "conditioning_unit": "g",                           // Unité ("g", "mL"...)
  "expression_pvc": "Le buffet",                      // Libellé conditionnement (PVC)
  "nb_pieces_dans_boite": "10",
  "libelle_nb_pieces_dans_boite": "la part",
  "nb_portion": "10",                                 // Nombre de portions
  "bac_type": "Frais",                                // Sec / Frais / Surgelé / XXL
  "is_uvcm": "Oui",                                   // Bool : unité de vente conso magasin

  // === Identifiants commerciaux (par type de magasin) ===
  "ean_vente": {
    "EAN vente Hyper":    "3523680261426",
    "EAN vente Super":    "3523680261426",
    "EAN vente Contact":  "3523680261426"
  },
  "plu": {
    "PLU Hyper": "1651",
    "PLU Super": "426"
  },

  // === Images ===
  "image":       "/b/u/buffet_gourmand_500x500.png",  // Image principale
  "image_label": null,                                // Label alt de l'image
  "small_image": "/b/u/buffet_gourmand_500x500.png",
  "thumbnail":   "/b/u/buffet_gourmand_500x500.png",

  // === Préparation / origine / conservation ===
  "delai_prepa":     "5",                             // Délai de préparation (jours)
  "conservation":    "Entre 0 et +4°C",
  "elabore_en":      "Préparé par nos Charcutiers Traiteurs",
  "decongele":       "0",                             // Bool : "0" / "1"
  "origine":         null,                            // Pays / région d'origine

  // === Contenus HTML / textes ===
  "description":               null,                  // Description longue (HTML)
  "short_description":         null,                  // Description courte
  "ingredients":               "<p><b>Jambon cuit</b> : ... </p>",     // HTML INCO
  "en_savoir_plus":            "<p>Vos charcuteries ... </p>",         // HTML descriptif marketing
  "conseil_prepa":             "<p>Conseils de préparation : ... </p>",// HTML préparation
  "mots_cles":                 "Chorizo FQC Coppa Crème forestière ...", // Mots-clés search
  "valeur_energetique":        null,                  // Valeurs nutritionnelles
  "mentions_legales_alcool":   null,                  // Mention légale alcool
  "mentions_legales_danger":   null,                  // Mention légale danger

  // === Délais spécifiques par magasin ===
  // Surcharge le `delai_prepa` global au niveau (a) du type de magasin, ou
  // (b) d'un store_id précis. Permet aussi de définir une heure limite de
  // ramasse au-delà de laquelle un délai alternatif est appliqué.
  // Priorité de résolution : delay[store_id] > <type label> > delai_prepa.
  "carrefour_delay": {
    "Hyper": 3,                                       // Délai par défaut pour les Hyper (en jours)
    "Super": 5,                                       //   idem pour les Super
    "delay": {                                        // Override par store_id (clé = store_id, valeur = délai en jours)
      "453": 6,                                       //   store 453 : 6 jours (au lieu des 3 jours par défaut Hyper)
      "481": 6                                        //   store 481 : 6 jours
    },
    "pickup": {                                       // ISO datetime : heure limite de ramasse pour ce store
      "453": "2021-10-28T13:10:00",                   //   (false si pas configuré)
      "481": false
    },
    "pickup_delay": {                                 // Délai alternatif (en jours) si l'heure pickup est dépassée
      "453": 6,
      "481": false
    },
    "auto_updated": ["453", "481"]                    // Store_ids dont le délai est mis à jour automatiquement (strings)
  },

  // === Composition (plateaux / bundles Calliweb_Caroline) ===
  "composition": {
    "title": "Votre buffet contient : ",
    "key":   "5949192246cce",
    "pieces": [
      {"name": "Tagliatelles au surimi (part de 150g)", "qty": "10", "image": "composition/.../tagliatelle-surimi.png"},
      {"name": "Taboulé oriental (part de 150g)",       "qty": "10", "image": "composition/.../Taboul_.png"},
      {"name": "Tranches de crème forestière (40g)",    "qty":  "4", "image": "composition/.../creme-foresti_re.png"}
      // ... (15 items au total pour ce produit)
    ]
  },

  // === Composition Plateau ===
  // null ici car PID 100 est `type_id: "simple"`. Cf. exemple dédié plus bas
  // pour un produit `type_id: "plateau"` qui expose composition_plateau renseigné.
  "composition_plateau": null,

  // === Pictos promotionnels ===
  "left_picto_hyper": "10€ offerts",                  // Picto promo gauche (Hyper)
  "left_picto_super": "10€ offerts",                  // Picto promo gauche (Super)

  // === Promotion ===
  "promo_display": "Non",                             // Bool affichage du bandeau promo
  "promo_qty":     null,                              // Quantité requise pour la promo
  "promo_value":   "10",                              // Valeur de la promo (ex: "10" pour 10€)
  "promo_name":    "ce buffet et d'un cocktail dinatoire froid pour 10 personnes avec le code promo RECEPTION10",

  // === Multiselects métier traiteur ===
  "type_evenement":  null,                            // Multiselect (mariage, apéritif, etc.)
  "type_envie":      ["salé", "froid", "simple et convivial", "sans poisson"],
  "type_cuisine":    ["simple et convivial"],
  "type_gout":       ["salé"],
  "type_pdt":        null,                            // Type de produit
  "type_allergene":  null,                            // Allergènes
  "spec_produit1":   null,                            // Spécification libre 1
  "spec_produit2":   null,                            // Spécification libre 2
  "complete_meal":   "0",                             // Bool repas complet
  "carrefour_seasonal_offer": "0",                    // Bool offre saisonnière
  "cadencement_auto":         "1",                    // Bool cadencement auto

  // === Période "Nouveau" ===
  "news_from_date": null,
  "news_to_date":   null
}
```

**Notes sur le format**
- Les valeurs `null` sont conservées : un même produit a toujours le même set de clés (~63 pour un produit du set "Produits générés"), avec `null` si la valeur n'est pas renseignée.
- Les attributs spécifiques à un autre type d'attribute_set n'apparaissent **que** sur les produits qui les utilisent. Le partenaire doit donc tester `obj.hasOwnProperty(key)` ou utiliser un accès défensif (`obj.key ?? defaultValue`).
- Les blobs JSON (`ean_vente`, `plu`, `composition*`, `carrefour_delay`, `carrefour_store_restriction`) sont déjà décodés en objets/listes imbriqués.
- Les booleans métier sont exportés comme strings `"0"` / `"1"` ou comme labels FR `"Oui"` / `"Non"` selon la source (les enums Magento natifs comme `status` / `visibility` ont leur label FR ; les booleans custom restent en `"0"`/`"1"`).

### Exemple : produit `type_id: "plateau"` (SKU 3492 — Assiette du charcutier)

Le champ `composition_plateau` est renseigné uniquement pour les produits `type_id == "plateau"`. Il décrit les groupes/pièces parmi lesquels ShopperGPT compose le plateau pour l'utilisateur. Les autres champs (image, prix, dispo, etc.) sont identiques au format ci-dessus.

```jsonc
{
  "product_id": 13914,
  "sku":        "3492",
  "type_id":    "plateau",
  "name":       "Assiette du charcutier à composer",
  // ... (mêmes champs que l'exemple simple ci-dessus) ...

  "composition_plateau": {
    "title":  "Choisissez les charcuteries qui composeront votre assiette",
    "key":    "5d2484d76e979",
    "qty":    "6",                          // Nombre TOTAL de pièces à choisir (somme des choix utilisateur)
    "groups": [
      {
        "group_index": 0,                   // ← Index calculé après tri par `position`
        "position":    "1",
        "name":        "Les jambons cuits et crus",
        "pieces": [
          {
            "piece_index":     0,
            "code":            "0-0",       // ← Identifiant à renvoyer dans options.plateau (format "{group_index}-{piece_index}")
            "position":        "0",
            "name":            "Jambon de Bayonne Label Rouge Reflets de France",
            "conditionnement": "(tranche de 30g)",
            "ingredients":     "...",
            "price":           "",          // extra_price (vide = 0 — pas de surcharge sur le plateau)
            "achat_ean_hyper": "118110",
            "achat_label":     "Jambon de Bayonne Label Rouge Reflets de France (1 tranche de 30g)"
          },
          { "piece_index": 1, "code": "0-1", "name": "Jambon Serrano Filière Qualité Carrefour", "...": "..." },
          { "piece_index": 2, "code": "0-2", "name": "Jambon de Vendée Reflets de France",       "...": "..." }
        ]
      },
      {
        "group_index": 1,
        "position":    "2",
        "name":        "Les saucissons sec et cuits",
        "pieces": [
          { "piece_index": 0, "code": "1-0", "name": "Saucisson à l'ail",     "...": "..." },
          { "piece_index": 3, "code": "1-3", "name": "Coppa de Parme",         "...": "..." }
        ]
      },
      {
        "group_index": 2,
        "position":    "3",
        "name":        "Les rillettes et pâtés",
        "pieces": [
          { "piece_index": 0, "code": "2-0", "name": "Mousse de canard Carrefour", "...": "..." }
        ]
      }
    ]
  }
}
```

**Comment composer un plateau** depuis cet export :
1. ShopperGPT lit `composition_plateau.qty` → ici **6** pièces à choisir au total.
2. Il choisit librement parmi les `groups[].pieces[]`, en récupérant le `code` de chaque pièce sélectionnée.
3. Il envoie l'addition à l'API : `POST /shoppergpt/cart/add { items: [{ sku: "3492", qty: 1, options: { plateau: { "0-0": 2, "0-2": 1, "1-3": 2, "2-0": 1 }}}]}` — la somme des qty (2+1+2+1=6) doit égaler `composition_plateau.qty`.
4. Si la somme ne correspond pas, Magento renvoie l'erreur métier `"Votre <produit> nécessite d'être composé."`.

---

## 2. `products_prices.jsonl` — Prix par produit × magasin (+ disponibilité)

1 ligne par produit. Contient à la fois :
- La **matrice de disponibilité** : dans quels magasins le produit est vendable
- Les **prix BigQuery** par magasin

```jsonc
{
  "product_id": 31,                       // ID produit Magento
  "nb_stores": 921,                       // Nombre de magasins où le produit est vendable
  "stores": [
    {
      "store_id": 338,                    // ID magasin Magento
      "anabel_code": "0158",              // Code Anabel
      "prices": [
        {
          "store_gln_key": "3020476124300", // Code GLN du magasin (BigQuery)
          "price": 4.9                      // Prix unitaire TTC, en €
        }
      ]
    },
    {
      "store_id": 339,
      "anabel_code": "0501",
      "prices": []                        // Pas de prix BQ → fallback sur products.jsonl
    }
  ]
}
```

**Sources de données** :
- Disponibilité : `calliweb_store_association` (recalculée à chaque sauvegarde BO du produit ou du magasin, en croisant les concepts × restrictions par type)
- Prix : `calliweb_bigquery_prices` (synchro BigQuery automatique)

---

## 3. `stores.jsonl` — Référentiel magasins

1 ligne par magasin (1 094 magasins).

```jsonc
{
  "store_id": 370,                                   // ID côté Magento
  "is_active": true,                                 // Actif ou non — les magasins inactifs ne sont pas affichés en front
  "code": "FRA012",                                  // Code interne Magento (Thalès)
  "anabel_code": "0074",                             // Code Anabel
  "type_label": "Hyper",                             // Type : Hyper / Super / City / Express / Contact / Contact Marché / Montagne / Bio
  "name": "Carrefour Bègles",
  "drive": false,
  "withdrawal_store": true,                          // Retrait en magasin possible
  "pspid": "CFRTraiteurTest",                        // Identifiant PSP. Vide = pas de paiement en ligne
  "only_online_payment": false,                      // Paiement en ligne exclusif (sinon paiement en magasin également possible)
  "shipping_distance": "8",                          // Distance max de livraison (km)
  "phone": null,
  "mail": null,
  "schedule": "Du Lundi au Samedi de 8h30 à 21h30",
  "street_1": "Chemin De Tartifume",
  "street_2": "Cc Les Rives D'arcins",
  "street_3": null,
  "postcode": "33130",
  "city": "Bègles",
  "region": null,
  "company": "Carrefour Hypermarches",
  "legal_form": "SAS au capital de 346 758 000 Euros",
  "headquarters": "1 RUE JEAN MERMOZ, ZAE SAINT GUENAULT, 91000 EVRY",
  "rcs": "EVRY 451321335",
  "company_phone": null,
  "franchise": false,                                // Franchisé (true) ou Intégré (false)
  "api_bu_franchise_type": null,                     // Type de franchise (PREMIUM / STANDARD)
  "custom_msg_availability": true,

  "lad_postcodes": [                                 // Livraison à domicile : codes postaux desservis + zones tarifaires
    {
      "postcode": "33800",
      "city": null,
      "zone": {
        "code": "LAD_23€",
        "tax": 20,                                   // Taux de TVA (%)
        "thresholds": {                              // Seuils de frais de livraison
          "50":  23,                                 //   panier ≥ 50€  → 23€ de livraison
          "200": 23                                  //   panier ≥ 200€ → 23€
        }
      }
    }
  ],

  "concepts": [                                      // Concepts / services proposés par le magasin
    {
      "concept_id":      6,                          // ID interne
      "concept_name":    "Sushis Kelly Daily",       // Libellé du concept
      "department_name": "Poisson"                   // Département rattaché
    },
    {
      "concept_id":      71,
      "concept_name":    "PaiementEnLigne",
      "department_name": "A_Magasin"
    }
  ],

  "longitude": "-0.530874",
  "latitude":  "44.7957"
}
```

**À propos des `concepts`** : c'est le mécanisme interne Carrefour qui définit ce qu'un magasin "sait faire" (Boucherie Trad, Sushis Kelly Daily, Paiement en Ligne, Livraison à Domicile, etc.). Chaque produit a également ses concepts requis. Un produit est disponible dans un magasin si **tous** ses concepts requis sont supportés par le magasin (cf. matrice de disponibilité dans `products_prices.jsonl`).

**À propos des `lad_postcodes`** : si une zone LAD est définie, le magasin livre à domicile dans ces codes postaux selon les seuils tarifaires. Champ vide → pas de livraison à domicile, retrait uniquement. *(cette conclusion est à valider avec l'équipe)*

---

# Partie 2 — API REST Cart

## 1. Architecture

```
                       ┌─────────────────────────────────┐
                       │  Utilisateur                    │
                  ┌────│  Navigateur                     │◄────┐
                  │    │  traiteur.carrefour.fr          │     │
                  │    │  (cookie PHPSESSID)             │     │
                  │    └─────────────────────────────────┘     │
                  │                                            │
       ① sessionId│                                            │ ⑦ Réponse JSON
            lu     │                                            │  + injection du
          côté     │                                            │   minicart_html
        front      │                                            │   dans .header-minicart
                  ▼                                            │
       ┌─────────────────────────────────┐                     │
       │  Service IA                     │                     │
       │  ShopperGPT (Redpill)           │─────────────────────┘
       └────────────────┬────────────────┘  ⑥ Relaie la réponse
                        │                      vers le front
       ② Header        │
         X-Session-Id   │                                ▲
                        │                                │
       ③ POST          │                                │ ⑤ Réponse HTTP 200
         /shoppergpt/   ▼                                │    {
         cart/add                                        │      results: [...],
         { items: [...] }                                │      cart: {...},
                ┌──────────────────────────────────────────────┐
                │  Magento — module Carrefour_ShopperGPT       │      minicart_html: "..."
                │  URLs : /shoppergpt/cart/*                   │    }
                │  - Lit la session backend                    │
                │  - Modifie le panier                         │
                │  - Génère le HTML du minicart                │
                └────────┬───────────────────┬─────────────────┘
                         │                   │
                lecture  │                   │  ④ Modifie le panier
                         ▼                   ▼
                ┌──────────────────────┐  ┌────────────────────┐
                │  Sessions            │  │  sales_flat_quote  │
                │                      │  │  (+ quote_item)    │
                └──────────────────────┘  └────────────────────┘
```

**Résumé du flux** :
1. Le front du site (ou l'embed ShopperGPT côté Carrefour) lit le cookie `PHPSESSID` du navigateur et transmet le `sessionId` au service IA ShopperGPT.
2. ShopperGPT envoie le `sessionId` dans le header HTTP `X-Session-Id` vers l'API Magento.
3. ShopperGPT appelle l'endpoint API `/shoppergpt/cart/*` (add / update / clear / cart).
4. Magento lit la session utilisateur, résout le `quote_id` actif (ou en crée un pour `POST /add` s'il n'y en a pas), applique l'opération sur `sales_flat_quote` + `sales_flat_quote_item`.
5. Magento répond avec un JSON 200 contenant : `results` (rapport par item), `cart` (état final du panier), `minicart_html` (HTML du minicart rendu).
6. ShopperGPT relaie la réponse vers le front Carrefour.
7. Le widget JS côté navigateur injecte `d.minicart_html` dans `.header-minicart` (ou `window.location.reload()` si on est sur `/checkout/cart/`) — l'UI est à jour sans nouvel appel.

---

## 2. Format de réponse global

### Succès — `GET /cart`
Le **panier complet** retourné directement (sans `minicart_html` — endpoint en lecture pure, pas de rafraîchissement d'UI à provoquer).

### Succès — `POST /cart/add` et `POST /cart/update`
```json
{
  "results": [
    {"index": 0, "status": "ok", ...},
    {"index": 1, "status": "error", "error": "..."}
  ],
  "cart": { /* panier complet à l'état final */ }
}
```

Chaque item est traité indépendamment : un item en erreur n'empêche pas les autres d'aboutir.

### Succès — `POST /cart/clear`
```json
{
  "status": "ok",
  "removed": 6,
  "cart": { /* panier vide */ },
  "minicart_html": "<a href=...>..."
}
```

### Champ `minicart_html` (présent dans les réponses 2xx des endpoints de modification)

Présent dans les réponses 2xx de `POST /cart/add`, `/cart/update` et `/cart/clear`. **Non présent sur `GET /cart`** (endpoint en lecture pure, le navigateur n'a rien à rafraîchir s'il vient juste de lire le panier). Le champ contient le **HTML rendu** du contenu du bloc minicart Magento (sans le wrapper externe `.header-minicart`), à injecter directement dans le DOM côté navigateur :

```javascript
// Sur la page panier, on reload (totaux, lignes, livraison, etc. à recalculer).
// Ailleurs, on remplace juste le contenu du wrapper .header-minicart.
if (location.pathname.startsWith('/checkout/cart')) {
    location.reload();
} else {
    const el = document.querySelector('.header-minicart');
    if (el) el.innerHTML = d.minicart_html;
}
```

Ce HTML reflète l'état du panier **après** l'opération (l'add/update/clear vient d'être appliqué côté Magento, le HTML est généré à partir de ce nouvel état). Aucun second appel API n'est nécessaire pour rafraîchir l'UI.

### Erreur
```json
{"error": "Message clair"}
```
Toujours accompagné d'un code HTTP approprié (cf. tableau ci-dessous).

---

## 3. Endpoints

### 3.1 `GET /shoppergpt/cart` — Lecture du panier

**Headers**
| Header | Obligatoire | Valeur |
|---|---|---|
| `X-Session-Id` | ✅ | sessionId frontend Magento (= valeur du cookie `PHPSESSID`) |

**Réponse 200** (exemple utilisateur connecté)
```json
{
  "quote_id": 4376212,
  "customer_id": 576548,
  "customer": {
    "id": 576548,
    "email": "mansouriadel@hotmail.fr",
    "firstname": "Adel",
    "lastname": "Mansouri",
    "created_at": "2026-02-05T15:00:23+01:00",
    "billing_address": {
      "street": "123 BOULEVARD DE PORT ROYAL 75014 PARIS\nMATERNITE PORT ROYAL",
      "postcode": "75014",
      "city": "PARIS",
      "region": null,
      "country": "FR",
      "telephone": "0632130468"
    },
    "shipping_address": {
      "street": "123 BOULEVARD DE PORT ROYAL 75014 PARIS\nMATERNITE PORT ROYAL",
      "postcode": "75014",
      "city": "PARIS",
      "region": null,
      "country": "FR",
      "telephone": "0632130468"
    }
  },
  "user_store_id": 474,
  "user_store_anabel_code": "0504",
  "user_store_name": "Carrefour Paris Auteuil",
  "items_count": 2,
  "items_qty": 2,
  "subtotal": 16.53,
  "grand_total": 17.44,
  "items": [
    {
      "item_id": 21996375,
      "product_id": 5248,
      "sku": "2185",
      "name": "Gâteau Happy birthday",
      "qty": 1,
      "price": 15.16,
      "row_total": 15.16,
      "product_type": "simple"
    },
    {
      "item_id": 21996376,
      "product_id": 19171,
      "sku": "5155",
      "name": "Sauce soja salée - Carrefour Sensation",
      "qty": 1,
      "price": 1.37,
      "row_total": 1.37,
      "product_type": "simple"
    },
    {
      "item_id": 21996415,
      "product_id": 13914,
      "sku": "3492",
      "name": "Assiette du charcutier à composer",
      "qty": 1,
      "price": 4.27,
      "row_total": 4.27,
      "product_type": "plateau",
      "plateau_composition": [
        {"code": "0-0", "name": "Jambon de Bayonne Label Rouge Reflets de France", "qty": 2},
        {"code": "0-2", "name": "Jambon de Vendée Reflets de France", "qty": 1},
        {"code": "1-3", "name": "Coppa de Parme", "qty": 2},
        {"code": "2-0", "name": "Mousse de canard Carrefour", "qty": 1}
      ]
    }
  ]
}
```

Pour un **utilisateur non connecté** : `customer_id` et `customer` sont à `null`. Le reste du panier (items, store, totaux) est identique.

Pour un **item plateau composé** (`product_type: "plateau"`) : le champ supplémentaire `plateau_composition` liste les pièces choisies (`code` correspond à la clé `composition_plateau.groups[].pieces[].code` de l'export, et est aussi le format attendu pour `POST /cart/add { options: { plateau: { "0-0": qty }}}`). Pour les items simples, le champ est omis.

**Description des champs**
| Champ | Type | Sens |
|---|---|---|
| `quote_id` | int | Identifiant du panier Magento |
| `customer_id` | int / null | ID client si connecté, `null` sinon |
| `customer` | object / null | Infos client si connecté, `null` sinon. Détail ci-dessous. |
| `customer.id` | int | Doublon de `customer_id` (pour parcours objet) |
| `customer.email` | string | Email du compte client |
| `customer.firstname` | string / null | Prénom |
| `customer.lastname` | string / null | Nom |
| `customer.created_at` | string / null | Date d'inscription (ISO 8601) |
| `customer.billing_address` | object / null | Adresse de facturation par défaut (`null` si pas renseignée) |
| `customer.shipping_address` | object / null | Adresse de livraison par défaut (`null` si pas renseignée) |
| `customer.*_address.street` | string / null | Rue + complément(s) (lignes séparées par `\n`) |
| `customer.*_address.postcode` | string / null | Code postal |
| `customer.*_address.city` | string / null | Ville |
| `customer.*_address.region` | string / null | Région (souvent `null` en France) |
| `customer.*_address.country` | string / null | Code pays ISO (ex: `"FR"`) |
| `customer.*_address.telephone` | string / null | Numéro de téléphone |
| `user_store_id` | int | Identifiant interne Magento du magasin sélectionné |
| `user_store_anabel_code` | string / null | Code Anabel du magasin (référence externe Carrefour) |
| `user_store_name` | string | Nom du magasin sélectionné |
| `items_count` | int | Nombre d'items distincts (ligne) dans le panier |
| `items_qty` | float | Quantité totale (somme des qty) |
| `subtotal` | float | Sous-total HT |
| `grand_total` | float | Total final TTC |
| `items[].item_id` | int | Identifiant unique de la ligne dans le panier (utile pour update/remove) |
| `items[].product_id` | int | Identifiant produit Magento |
| `items[].sku` | string | Référence produit |
| `items[].name` | string | Nom du produit |
| `items[].qty` | float | Quantité commandée |
| `items[].price` | float | Prix unitaire (TTC) |
| `items[].row_total` | float | qty × price (TTC) |
| `items[].product_type` | string | `simple`, `plateau`, etc. |

---

### 3.2 `POST /shoppergpt/cart/add` — Ajout incrémental

**Sémantique** : si le SKU est déjà au panier, Magento **merge** automatiquement les quantités (additif).

**Headers**
| Header | Obligatoire | Valeur |
|---|---|---|
| `X-Session-Id` | ✅ | sessionId Magento |
| `Content-Type` | ✅ | `application/json` |

**Body** — toujours un tableau `items`, même pour un seul produit
```json
{
  "items": [
    {"sku": "6497", "qty": 1},
    {"sku": "3453", "qty": 2}
  ]
}
```

**Champ optionnel** `options.plateau` (objet) pour les produits `type_id = "plateau"` (Calliweb). Le client choisit ses pièces à partir du champ `composition_plateau` de `products.jsonl` (cf. clés `code` exportées) et les renvoie sous la forme `{ "<group>-<piece>": qty }` :

```json
{
  "items": [
    {
      "sku": "3492",
      "qty": 1,
      "options": {
        "plateau": {
          "0-0": 2,
          "0-2": 1,
          "1-3": 3
        }
      }
    }
  ]
}
```

| Clé | Signification |
|---|---|
| `"0-0"` | Groupe 0 (1er groupe trié par `position`), pièce 0 (1ère pièce triée par `position`) |
| `"1-3"` | Groupe 1, pièce 3 |
| valeur | nombre d'unités de cette pièce choisies |

⚠️ La somme des qty doit égaler `composition_plateau.qty` (capacité totale du plateau). Sinon Magento refuse l'ajout avec une erreur métier (ex: `"Votre Assiette du charcutier à composer nécessite d'être composé."`).

ShopperGPT trouve les `code` directement dans l'export : `composition_plateau.groups[].pieces[].code` (déjà au format `"<group>-<piece>"`).

**Réponse 200**
```json
{
  "results": [
    {"index": 0, "sku": "6497", "qty": 1, "status": "ok", "item_id": 21996363, "new_qty": 4},
    {"index": 1, "sku": "3453", "qty": 2, "status": "ok", "item_id": 21996361, "new_qty": 5}
  ],
  "cart": { /* panier complet */ }
}
```

`new_qty` = quantité finale dans le panier (après merge si SKU déjà présent).

**Statuts par item**
| `status` | `error` | Cause |
|---|---|---|
| `ok` | — | Item ajouté avec succès |
| `error` | `Missing sku` | Pas de `sku` dans la ligne |
| `error` | `qty must be > 0` | `qty` absent, négatif ou nul |
| `error` | `Product not found` | SKU inexistant en base |
| `error` | `Product unavailable in user store` | Produit pas disponible dans le magasin sélectionné (matrice `calliweb_store_association`) |
| `error` | message Magento brut | Erreur native (ex: bundle option manquante) |

**Snippet front-end complet** (à injecter via console ou intégré dans le widget chat). Mélange de produits simples et d'un plateau composé en un seul appel :

```javascript
// Exemples produits :
//   Gâteau Naruto                       → sku "6807"  (simple)
//   Plateau Dream Mix - 32 pièces       → sku "6497"  (simple)
//   Assiette du charcutier à composer   → sku "3492"  (plateau composé, 6 pièces)
(async () => {
    const r = await fetch("/shoppergpt/cart/add", {
        method: "POST",
        credentials: "include",
        headers: {
            "Content-Type": "application/json",
            "X-Session-Id": "86eac927b7a31cf0e4330c75024276d9"
        },
        body: JSON.stringify({
            items: [
                { sku: "6807", qty: 2 },
                { sku: "6497", qty: 3 },
                {
                    sku: "3492",
                    qty: 1,
                    options: {
                        plateau: {
                            "0-0": 2,  // Jambon de Bayonne × 2
                            "0-2": 1,  // Jambon de Vendée  × 1
                            "1-3": 2,  // Coppa de Parme    × 2
                            "2-0": 1   // Mousse de canard  × 1
                        }                 // Total = 6 pièces (= composition_plateau.qty)
                    }
                }
            ]
        })
    });
    const d = await r.json();
    console.log("API response:", d);

    if (location.pathname.startsWith("/checkout/cart")) {
        location.reload();
    } else {
        const el = document.querySelector(".header-minicart");
        if (el) {
            el.innerHTML = d.minicart_html;
        } else {
            console.warn(".header-minicart introuvable sur cette page");
        }
    }
})();
```

---

### 3.3 `POST /shoppergpt/cart/update` — Définir la quantité (valeur absolue, écrasement)

**Sémantique** :
- `qty > 0` → fixe la quantité à cette valeur exactement (override, pas incrémental)
- `qty = 0` → supprime l'item du panier (alias de remove)

**Headers** : idem `add`

**Body**
```json
{
  "items": [
    {"item_id": 21996361, "qty": 3},
    {"item_id": 21996363, "qty": 0}
  ]
}
```

L'identification se fait par `item_id` (jamais par sku — pour différencier deux bundles de même SKU avec options différentes).

**Réponse 200**
```json
{
  "results": [
    {"index": 0, "item_id": 21996361, "qty": 3, "status": "ok", "action": "updated", "new_qty": 3},
    {"index": 1, "item_id": 21996363, "qty": 0, "status": "ok", "action": "removed"}
  ],
  "cart": { /* panier complet */ }
}
```

**Statuts par item**
| `status` | `action` | `error` | Cause |
|---|---|---|---|
| `ok` | `updated` | — | qty changée |
| `ok` | `removed` | — | item supprimé (qty=0) |
| `error` | — | `Missing item_id` | Pas de `item_id` |
| `error` | — | `qty must be >= 0` | qty négative |
| `error` | — | `Item not found in your cart` | item_id n'existe pas dans le quote du user |

> ⚠️ L'`item_id` doit provenir d'un `GET /shoppergpt/cart` ou de la réponse `add` faits avec la **même `X-Session-Id`**. Un `item_id` cross-session renverra toujours `Item not found in your cart`.

**Snippet front-end complet** :

```javascript
(async () => {
    const r = await fetch("/shoppergpt/cart/update", {
        method: "POST",
        credentials: "include",
        headers: {
            "Content-Type": "application/json",
            "X-Session-Id": "86eac927b7a31cf0e4330c75024276d9"
        },
        body: JSON.stringify({
            items: [
                { item_id: 21996390, qty: 21 }
            ]
        })
    });

    if (!r.ok) {
        console.error("API error:", r.status, await r.text());
        return;
    }
    const d = await r.json();
    console.log("API response:", d);

    if (location.pathname.startsWith("/checkout/cart")) {
        location.reload();
    } else {
        const el = document.querySelector(".header-minicart");
        if (el) {
            el.innerHTML = d.minicart_html;
        } else {
            console.warn(".header-minicart introuvable sur cette page");
        }
    }
})();
```

---

### 3.4 `POST /shoppergpt/cart/clear` — Vider le panier

**Headers**
| Header | Obligatoire | Valeur |
|---|---|---|
| `X-Session-Id` | ✅ | sessionId Magento |

**Body** : aucun

**Réponse 200**
```json
{
  "status": "ok",
  "removed": 6,
  "cart": { /* panier vide */ }
}
```

`removed` = nombre d'items qui étaient au panier avant le vidage.

**Snippet front-end complet** :

```javascript
(async () => {
    const r = await fetch("/shoppergpt/cart/clear", {
        method: "POST",
        credentials: "include",
        headers: {
            "Content-Type": "application/json",
            "X-Session-Id": "86eac927b7a31cf0e4330c75024276d9"
        }
    });

    if (!r.ok) {
        console.error("API error:", r.status, await r.text());
        return;
    }
    const d = await r.json();
    console.log("API response:", d);

    if (location.pathname.startsWith("/checkout/cart")) {
        location.reload();
    } else {
        const el = document.querySelector(".header-minicart");
        if (el) {
            el.innerHTML = d.minicart_html;
        } else {
            console.warn(".header-minicart introuvable sur cette page");
        }
    }
})();
```

---

## 4. Codes HTTP globaux

Ces codes sont retournés au **niveau de la requête entière** (body = `{"error":"..."}`). Cas validés par tests réels.

| HTTP | Body | Endpoint(s) concernés | Cause |
|---|---|---|---|
| **200** | (payload de succès) | tous | OK |
| **400** | `{"error":"Missing X-Session-Id header"}` | tous | Header `X-Session-Id` absent |
| **400** | `{"error":"Empty body"}` | `POST /add`, `POST /update` | POST sans body |
| **400** | `{"error":"Invalid JSON body"}` | `POST /add`, `POST /update` | Body non JSON parseable |
| **400** | `{"error":"Missing \"items\" array"}` | `POST /add`, `POST /update` | Body sans clé `items` |
| **400** | `{"error":"\"items\" array is empty"}` | `POST /add`, `POST /update` | `items: []` |
| **404** | `{"error":"Session not found"}` | tous | sessionId inconnu, expiré ou supprimé du backend session |
| **404** | `{"error":"No active quote on this session"}` | `GET /cart`, `POST /update`, `POST /clear` | Session valide mais aucun panier rattaché. **`POST /add` ne retourne jamais ce 404** : il crée le panier à la volée. |
| **404** | `{"error":"Quote not loadable"}` | tous | quote_id en session pointe vers une entrée `sales_flat_quote` supprimée (cas marginal) |
| **500** | `{"error":"Internal error"}` | tous | Exception PHP inattendue (loguée dans `var/log/exception.log`) |
| **503** | `{"error":"Session backend unreachable"}` | tous | Backend de sessions injoignable |

Note : les erreurs sur un **item individuel** dans `POST /add` et `POST /update` ne sont **pas** des codes HTTP — la réponse reste 200, et l'entrée du tableau `results[]` a `status: "error"` + un champ `error`. Cf. tableau ci-dessous.

### Erreurs par item — `POST /cart/add`

Retournées dans `results[].status = "error"` (HTTP 200 global).

| `error` | Cause |
|---|---|
| `Missing sku` | Pas de champ `sku` dans l'item |
| `qty must be > 0` | `qty` absent, ≤ 0 ou non numérique |
| `Product not found` | SKU inexistant en base |
| `Product unavailable in user store` | Produit pas associé au magasin du user (`calliweb_store_association`) |
| _<message Magento brut>_ | Exception levée par `$quote->addProduct()` (ex: bundle option manquante) |

### Erreurs par item — `POST /cart/update`

Retournées dans `results[].status = "error"` (HTTP 200 global).

| `error` | Cause |
|---|---|
| `Missing item_id` | Pas de champ `item_id` dans l'item |
| `qty must be >= 0` | `qty` négatif |
| `Item not found in your cart` | `item_id` n'appartient pas au quote du user |
| _<message Magento brut>_ | Exception levée pendant `$item->setQty()` ou `$quote->removeItem()` |

---

## 5. Exemples concrets

### 5.1 Mode **non connecté** (visiteur anonyme)

> Session de test : `6865619ec704d646411da601e36eab54` (cookie `PHPSESSID` du navigateur).

#### `GET /cart`
```bash
curl -k -H "X-Session-Id: 6865619ec704d646411da601e36eab54" \
  https://traiteur.carrefour.fr/shoppergpt/cart
```

```json
{
  "quote_id": 4376218,
  "customer_id": null,
  "customer": null,
  "user_store_id": 474,
  "user_store_anabel_code": "0504",
  "user_store_name": "Carrefour Paris Auteuil",
  "items_count": 3,
  "items_qty": 8,
  "subtotal": 332.37,
  "grand_total": 365.6,
  "items": [
    {"item_id": 21996360, "product_id": 24708, "sku": "6497", "name": "Plateau Dream Mix - 32 pièces", "qty": 2, "price": 26.32, "row_total": 52.64, "product_type": "simple"},
    {"item_id": 21996361, "product_id": 13822, "sku": "3453", "name": "Plateau Hanabi Party - 64 pièces", "qty": 2, "price": 45.41, "row_total": 90.82, "product_type": "simple"},
    {"item_id": 21996362, "product_id": 13825, "sku": "3456", "name": "Plateau Kyoto Party  - 50 pièces", "qty": 4, "price": 47.23, "row_total": 188.91, "product_type": "simple"}
  ]
}
```

#### `POST /cart/add`
```bash
curl -k -X POST \
  -H "X-Session-Id: 6865619ec704d646411da601e36eab54" \
  -H "Content-Type: application/json" \
  -d '{"items":[{"sku":"6497","qty":1},{"sku":"3453","qty":2}]}' \
  https://traiteur.carrefour.fr/shoppergpt/cart/add
```

```json
{
  "results": [
    {"index": 0, "sku": "6497", "qty": 1, "status": "ok", "item_id": 21996363, "new_qty": 4},
    {"index": 1, "sku": "3453", "qty": 2, "status": "ok", "item_id": 21996361, "new_qty": 5}
  ],
  "cart": {
    "quote_id": 4376218,
    "customer_id": null,
    "user_store_id": 474,
    "user_store_anabel_code": "0504",
    "user_store_name": "Carrefour Paris Auteuil",
    "items_count": 3,
    "items_qty": 15,
    "subtotal": 615.68,
    "grand_total": 677.25,
    "items": [
      {"item_id": 21996361, "sku": "3453", "name": "Plateau Hanabi Party - 64 pièces", "qty": 5, "row_total": 227.05, "product_type": "simple"},
      {"item_id": 21996362, "sku": "3456", "name": "Plateau Kyoto Party  - 50 pièces", "qty": 6, "row_total": 283.36, "product_type": "simple"},
      {"item_id": 21996363, "sku": "6497", "name": "Plateau Dream Mix - 32 pièces", "qty": 4, "row_total": 105.27, "product_type": "simple"}
    ]
  }
}
```

#### `POST /cart/update`
```bash
curl -k -X POST \
  -H "X-Session-Id: 6865619ec704d646411da601e36eab54" \
  -H "Content-Type: application/json" \
  -d '{"items":[{"item_id":21996361,"qty":3},{"item_id":21996363,"qty":0}]}' \
  https://traiteur.carrefour.fr/shoppergpt/cart/update
```

```json
{
  "results": [
    {"index": 0, "item_id": 21996361, "qty": 3, "status": "ok", "action": "updated", "new_qty": 3},
    {"index": 1, "item_id": 21996363, "qty": 0, "status": "ok", "action": "removed"}
  ],
  "cart": {
    "quote_id": 4376218,
    "customer_id": null,
    "user_store_id": 474,
    "user_store_anabel_code": "0504",
    "user_store_name": "Carrefour Paris Auteuil",
    "items_count": 1,
    "items_qty": 3,
    "subtotal": 136.23,
    "grand_total": 149.85,
    "items": [
      {"item_id": 21996361, "sku": "3453", "name": "Plateau Hanabi Party - 64 pièces", "qty": 3, "row_total": 136.23, "product_type": "simple"}
    ]
  }
}
```

#### `POST /cart/clear`
```bash
curl -k -X POST \
  -H "X-Session-Id: 6865619ec704d646411da601e36eab54" \
  https://traiteur.carrefour.fr/shoppergpt/cart/clear
```

```json
{
  "status": "ok",
  "removed": 0,
  "cart": {
    "quote_id": 4376218,
    "customer_id": null,
    "user_store_id": 474,
    "user_store_anabel_code": "0504",
    "user_store_name": "Carrefour Paris Auteuil",
    "items_count": 0,
    "items_qty": 0,
    "subtotal": 0,
    "grand_total": 0,
    "items": []
  }
}
```

---

### 5.2 Mode **connecté** (utilisateur authentifié)

> Session de test : `f0dc917e0a66d628db9b92f96bc3f1e3`.
> Le champ `customer_id` est renseigné (`576548`) et `customer` contient le détail (email, nom, adresses par défaut).
> Même magasin que ci-dessus (`user_store_id: 474`, `anabel: 0504`).

#### `GET /cart` — panier de départ
```bash
curl -k -H "X-Session-Id: f0dc917e0a66d628db9b92f96bc3f1e3" \
  https://traiteur.carrefour.fr/shoppergpt/cart
```

```json
{
  "quote_id": 4376212,
  "customer_id": 576548,
  "customer": {
    "id": 576548,
    "email": "mansouriadel@hotmail.fr",
    "firstname": "Adel",
    "lastname": "Mansouri",
    "created_at": "2026-02-05T15:00:23+01:00",
    "billing_address": {
      "street": "123 BOULEVARD DE PORT ROYAL 75014 PARIS\nMATERNITE PORT ROYAL",
      "postcode": "75014",
      "city": "PARIS",
      "region": null,
      "country": "FR",
      "telephone": "0632130468"
    },
    "shipping_address": {
      "street": "123 BOULEVARD DE PORT ROYAL 75014 PARIS\nMATERNITE PORT ROYAL",
      "postcode": "75014",
      "city": "PARIS",
      "region": null,
      "country": "FR",
      "telephone": "0632130468"
    }
  },
  "user_store_id": 474,
  "user_store_anabel_code": "0504",
  "user_store_name": "Carrefour Paris Auteuil",
  "items_count": 2,
  "items_qty": 2,
  "subtotal": 16.53,
  "grand_total": 17.44,
  "items": [
    {"item_id": 21996375, "product_id": 5248,  "sku": "2185", "name": "Gâteau Happy birthday", "qty": 1, "price": 15.16, "row_total": 15.16, "product_type": "simple"},
    {"item_id": 21996376, "product_id": 19171, "sku": "5155", "name": "Sauce soja salée - Carrefour Sensation", "qty": 1, "price": 1.37, "row_total": 1.37, "product_type": "simple"}
  ]
}
```

> Note : présence d'un item `product_type: "plateau"` (composition Calliweb_Caroline).

#### `POST /cart/add`
```bash
curl -k -X POST \
  -H "X-Session-Id: f0dc917e0a66d628db9b92f96bc3f1e3" \
  -H "Content-Type: application/json" \
  -d '{"items":[{"sku":"6497","qty":2},{"sku":"1889","qty":1}]}' \
  https://traiteur.carrefour.fr/shoppergpt/cart/add
```

```json
{
  "results": [
    {"index": 0, "sku": "6497", "qty": 2, "status": "ok", "item_id": 21996354, "new_qty": 12},
    {"index": 1, "sku": "1889", "qty": 1, "status": "ok", "item_id": 21996364, "new_qty": 2}
  ],
  "cart": {
    "quote_id": 4376212,
    "customer_id": 576548,
    "user_store_id": 474,
    "user_store_anabel_code": "0504",
    "user_store_name": "Carrefour Paris Auteuil",
    "items_count": 7,
    "items_qty": 19,
    "subtotal": 368.54,
    "grand_total": 405.37,
    "items": [
      {"item_id": 21996354, "sku": "6497", "qty": 12, "row_total": 315.82, "product_type": "simple"},
      {"item_id": 21996364, "sku": "1889", "qty": 2, "row_total": 9.48, "product_type": "simple"}
    ]
  }
}
```

> Vérification du merge : `6497` est passé de 10 à **12** (`new_qty: 12`), `1889` de 1 à **2**.

#### `POST /cart/update`
```bash
curl -k -X POST \
  -H "X-Session-Id: f0dc917e0a66d628db9b92f96bc3f1e3" \
  -H "Content-Type: application/json" \
  -d '{"items":[{"item_id":21996354,"qty":5},{"item_id":21996356,"qty":0}]}' \
  https://traiteur.carrefour.fr/shoppergpt/cart/update
```

```json
{
  "results": [
    {"index": 0, "item_id": 21996354, "qty": 5, "status": "ok", "action": "updated", "new_qty": 5},
    {"index": 1, "item_id": 21996356, "qty": 0, "status": "ok", "action": "removed"}
  ],
  "cart": {
    "quote_id": 4376212,
    "customer_id": 576548,
    "items_count": 6,
    "items_qty": 11,
    "subtotal": 179.07,
    "grand_total": 196.43
  }
}
```

> `6497` set à 5 (override, plus de merge), `6226` (Vin Rosé) supprimé.

#### `POST /cart/clear`
```bash
curl -k -X POST \
  -H "X-Session-Id: f0dc917e0a66d628db9b92f96bc3f1e3" \
  https://traiteur.carrefour.fr/shoppergpt/cart/clear
```

```json
{
  "status": "ok",
  "removed": 6,
  "cart": {
    "quote_id": 4376212,
    "customer_id": 576548,
    "user_store_id": 474,
    "user_store_anabel_code": "0504",
    "user_store_name": "Carrefour Paris Auteuil",
    "items_count": 0,
    "items_qty": 0,
    "subtotal": 0,
    "grand_total": 0,
    "items": []
  }
}
```

---

## 6. Exemples d'erreurs

Deux formats :

- **Erreur sur la requête** (HTTP 4xx/5xx) — body : `{"error": "..."}`
- **Erreur sur un item** (HTTP 200) — un ou plusieurs items dans `results[]` ont `"status": "error"`, mais la requête a quand même été traitée

### Erreur sur la requête — exemple

```bash
curl -k -H "X-Session-Id: jenexistepas" \
  https://traiteur.carrefour.fr/shoppergpt/cart
```
```http
HTTP/1.1 404 Not Found
```
```json
{"error":"Session not found"}
```

Tous les autres cas (`Missing X-Session-Id header`, `Missing "items" array`, `Invalid JSON body`, etc.) suivent le même format. Voir tableau section 4 pour la liste complète.

### Erreur sur un item — exemple

```bash
curl -k -X POST \
  -H "X-Session-Id: <sessionId>" \
  -H "Content-Type: application/json" \
  -d '{"items":[
    {"sku":"6497","qty":1},
    {"sku":"PROD_INEXISTANT","qty":2}
  ]}' \
  https://traiteur.carrefour.fr/shoppergpt/cart/add
```
```http
HTTP/1.1 200 OK
```
```json
{
  "results": [
    {"index": 0, "sku": "6497", "status": "ok", "item_id": 21996361, "new_qty": 1},
    {"index": 1, "sku": "PROD_INEXISTANT", "status": "error", "error": "Product not found"}
  ],
  "cart": { /* état du panier après l'ajout réussi */ },
  "minicart_html": "..."
}
```

Dans ce cas, le site Magento entier est probablement dégradé — l'utilisateur ne peut pas non plus naviguer côté front. L'IA doit retry plus tard.

---

## 7. Différences mode connecté / non connecté

| Champ | Non connecté | Connecté |
|---|---|---|
| `customer_id` | `null` | int (ex: `576548`) |
| `user_store_id` | obligatoire (sinon panier sans store = pas d'achats possibles) | obligatoire |
| `quote_id` | propre à la session anonyme, perdu si cookie effacé | rattaché au compte client, retrouvable sur autre device après login |

Fonctionnellement les endpoints se comportent **strictement de la même manière** : la sémantique d'ajout/update/clear est identique. La seule différence est dans la persistance du panier (lié au client si connecté).

---

## 8. Intégration côté navigateur — snippets JS

Le champ `minicart_html` retourné dans chaque réponse 2xx contient le HTML du minicart Magento (le bloc `.header-minicart` en haut de page). Le widget IA doit l'injecter dans le DOM pour rafraîchir l'UI sans nouvel appel.

### Logique de rafraîchissement

Selon la page courante du user :
- **Sur `/checkout/cart/`** : la vue panier complète (table d'items, totaux, livraison) est affichée — un simple remplacement du minicart laisserait la vue principale obsolète. On fait un `window.location.reload()`.
- **Sur toutes les autres pages** (catégorie, fiche produit, home...) : il suffit de remplacer le contenu de `.header-minicart` avec le `minicart_html` reçu.

### 8.1 `POST /cart/add` — ajouter un produit

```javascript
(async () => {
  const sessionId = "7b86ba18837a59911c963b6cd5b1bc21";
  const items     = [{ sku: "5155", qty: 1 }];

  const r = await fetch("/shoppergpt/cart/add", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Id": sessionId
    },
    body: JSON.stringify({ items: items })
  });

  if (!r.ok) {
    console.error("API error:", r.status, await r.text());
    return;
  }
  const d = await r.json();
  console.log("API response:", d);

  if (window.location.pathname.startsWith("/checkout/cart")) {
    window.location.reload();
  } else {
    document.querySelector(".header-minicart").innerHTML = d.minicart_html;
  }
})();
```

### 8.2 `POST /cart/update` — modifier la quantité d'un item

```javascript
(async () => {
  const sessionId = "7b86ba18837a59911c963b6cd5b1bc21";
  const items     = [{ item_id: 21996371, qty: 2 }];

  const r = await fetch("/shoppergpt/cart/update", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Id": sessionId
    },
    body: JSON.stringify({ items: items })
  });

  if (!r.ok) {
    console.error("API error:", r.status, await r.text());
    return;
  }
  const d = await r.json();
  console.log("API response:", d);

  if (window.location.pathname.startsWith("/checkout/cart")) {
    window.location.reload();
  } else {
    document.querySelector(".header-minicart").innerHTML = d.minicart_html;
  }
})();
```

### 8.3 `POST /cart/update` — supprimer un item (qty = 0)

```javascript
(async () => {
  const sessionId = "7b86ba18837a59911c963b6cd5b1bc21";
  const items     = [{ item_id: 21996371, qty: 0 }];

  const r = await fetch("/shoppergpt/cart/update", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Id": sessionId
    },
    body: JSON.stringify({ items: items })
  });

  if (!r.ok) {
    console.error("API error:", r.status, await r.text());
    return;
  }
  const d = await r.json();
  console.log("API response:", d);

  if (window.location.pathname.startsWith("/checkout/cart")) {
    window.location.reload();
  } else {
    document.querySelector(".header-minicart").innerHTML = d.minicart_html;
  }
})();
```

### 8.4 `POST /cart/clear` — vider le panier

```javascript
(async () => {
  const sessionId = "7b86ba18837a59911c963b6cd5b1bc21";

  const r = await fetch("/shoppergpt/cart/clear", {
    method: "POST",
    credentials: "include",
    headers: { "X-Session-Id": sessionId }
  });

  if (!r.ok) {
    console.error("API error:", r.status, await r.text());
    return;
  }
  const d = await r.json();
  console.log("API response:", d);

  if (window.location.pathname.startsWith("/checkout/cart")) {
    window.location.reload();
  } else {
    document.querySelector(".header-minicart").innerHTML = d.minicart_html;
  }
})();
```

### 8.5 `GET /cart` — lire le panier (pas de modification)

Utile pour récupérer la liste des `item_id` avant un `/update` ou `/remove`.

```javascript
(async () => {
  const sessionId = "7b86ba18837a59911c963b6cd5b1bc21";

  const r = await fetch("/shoppergpt/cart", {
    credentials: "include",
    headers: { "X-Session-Id": sessionId }
  });

  if (!r.ok) {
    console.error("API error:", r.status, await r.text());
    return;
  }
  const d = await r.json();
  console.log("API response:", d);

  if (window.location.pathname.startsWith("/checkout/cart")) {
    window.location.reload();
  } else {
    document.querySelector(".header-minicart").innerHTML = d.minicart_html;
  }
})();
```
