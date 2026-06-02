"""
Carrefour Traiteur official navigation hierarchy → menu_step mapping.

Structure mirrors traiteur.carrefour.fr/a-la-carte.html exactly.
Each top-level section maps to one of our 6 menu steps:
  Apéritifs | Entrées | Plats | Fromages | Desserts | Boissons

Non-food sections (Arts de la table, Décoration de fête) map to None.

Usage in derive.py: join all product category names, then iterate
CATEGORY_TO_STEP in order — first match wins. More specific entries
must appear before broader ones that could shadow them.
"""

# ---------------------------------------------------------------------------
# Non-food — products in these categories should have menu_step = None
# ---------------------------------------------------------------------------

NON_FOOD_CATEGORY_KEYWORDS: list[str] = [
    # Arts de la table
    "spécial anniversaire",
    "assiettes et contenants",
    "serviettes",
    "gobelets",
    "couverts",
    "nappes",
    "vaisselle",
    "arts de la table",
    # Décoration de fête
    "bougies",
    "ballons",
    "décoration de fête",
    "déco de fête",
    "déco spéciale",
    "déco de table",
    # Misc non-food found in data
    "fleurs et vaisselle",
    "fleurs",
    "bouquets",
]

# ---------------------------------------------------------------------------
# Food categories → menu_step
#
# Carrefour navigation sections and their subcategories.
# Ordered from most specific to most generic within each section.
# Sections are ordered so that unambiguous ones (Boissons, Fromages,
# Desserts) come before broad catch-alls (Plats).
# ---------------------------------------------------------------------------

CATEGORY_TO_STEP: list[tuple[str, str]] = [

    # ── Boissons ─────────────────────────────────────────────────────────
    # Section: Boissons
    ("eaux, sodas et jus de fruits",    "Boissons"),
    ("bières & cidres",                 "Boissons"),
    ("champagnes et vins pétillants",   "Boissons"),
    ("apéritifs et digestifs",          "Boissons"),
    ("cafés et thés",                   "Boissons"),
    ("carte des boissons",              "Boissons"),
    ("boissons chaudes",                "Boissons"),
    ("vins",                            "Boissons"),
    ("boissons",                        "Boissons"),

    # ── Fromages ─────────────────────────────────────────────────────────
    # Section: Fromages
    ("plateaux déjà composés",          "Fromages"),
    ("plateaux à composer",             "Fromages"),
    ("fromages à la carte",             "Fromages"),
    ("plateaux grands formats",         "Fromages"),
    ("accompagnez votre plateau",       "Fromages"),
    ("plateaux de fromages",            "Fromages"),
    ("fromages & pains",                "Fromages"),
    ("fromages",                        "Fromages"),

    # ── Desserts ─────────────────────────────────────────────────────────
    # Section: Gâteaux & desserts
    ("petits fours et mignardises",     "Desserts"),
    ("tartes",                          "Desserts"),
    ("gâteaux enfants",                 "Desserts"),
    ("les individuels",                 "Desserts"),
    ("fruits et corbeilles de fruits",  "Desserts"),
    ("gâteaux et desserts",             "Desserts"),
    ("gâteaux",                         "Desserts"),
    ("farandole de desserts",           "Desserts"),
    ("bûches et desserts",              "Desserts"),
    ("desserts et gâteaux",             "Desserts"),
    ("desserts et gourmandises",        "Desserts"),
    ("desserts",                        "Desserts"),
    # Section: Petit déjeuner & goûter
    ("viennoiseries",                   "Desserts"),
    ("mignardises et petits plaisirs",  "Desserts"),
    ("pâtisseries américaines",         "Desserts"),
    ("pâtisseries individuelles",       "Desserts"),
    ("gâteaux et tartes",               "Desserts"),
    ("bonbons et friandises",           "Desserts"),
    ("petit déjeuner",                  "Desserts"),
    ("pâtisserie",                      "Desserts"),
    # Letter/Number cakes (found in data)
    ("letter cake",                     "Desserts"),
    ("number cake",                     "Desserts"),

    # ── Apéritifs ────────────────────────────────────────────────────────
    # Section: Apéritifs
    ("verrines",                        "Apéritifs"),
    ("pains surprises",                 "Apéritifs"),
    ("petits fours & canapés",          "Apéritifs"),
    ("à partager",                      "Apéritifs"),
    ("légumes à croquer",               "Apéritifs"),
    ("tartinables et antipastis",       "Apéritifs"),
    ("à picorer",                       "Apéritifs"),
    ("a picorer",                       "Apéritifs"),
    ("formules apéro",                  "Apéritifs"),
    # Section: Les plateaux (charcuterie platters = apéritif)
    ("les plateaux de charcuterie",     "Apéritifs"),
    ("plateau de charcuterie",          "Apéritifs"),
    ("plateaux de charcuteries",        "Apéritifs"),
    # Section: Pizzas & Bruschettas — whole pizzas are main course
    ("pizzas & bruschettas",            "Plats"),
    ("bruschettas",                     "Apéritifs"),
    # Section: Buffets & cocktails dinatoires — MUST come before "plats"
    ("buffets & cocktails dinatoires",  "Apéritifs"),
    ("buffets & cocktails",             "Apéritifs"),
    ("cocktail dinatoire",              "Apéritifs"),
    ("apéritif dinatoire",              "Apéritifs"),
    ("traiteur pour 6 personnes",       "Apéritifs"),
    ("traiteur pour 10 personnes",      "Apéritifs"),
    ("traiteur pour 20 personnes",      "Apéritifs"),
    ("traiteur pour 30 personnes",      "Apéritifs"),
    ("a la part",                       "Apéritifs"),
    # Section: Sushis & cuisine du monde (finger food = apéritif)
    ("plateaux de sushis",              "Apéritifs"),
    ("petits plus japonais",            "Apéritifs"),
    ("saveurs d'asie",                  "Plats"),
    ("saveurs d'orient",                "Plats"),
    ("sushis pour le nouvel an",        "Apéritifs"),
    ("envie de sushis",                 "Apéritifs"),
    ("sushis",                          "Apéritifs"),
    # "cuisine du monde" covers Asian/Oriental full dishes → Plats
    ("cuisine du monde",                "Plats"),
    # "repas de rue" removed — Carrefour tags pasta/asian dishes with this too
    # Generic apéritif signals (from data, not in main nav)
    ("pour l'apéritif",                 "Apéritifs"),
    ("autour d'un apéritif",            "Apéritifs"),
    ("apéritifs de noël",               "Apéritifs"),
    ("amuse-bouche",                    "Apéritifs"),
    ("apéro festif",                    "Apéritifs"),
    ("cocktail d'entreprise",           "Apéritifs"),
    ("pour le cocktail",                "Apéritifs"),
    ("apéritif",                        "Apéritifs"),

    # ── Entrées ───────────────────────────────────────────────────────────
    # Section: Entrées & salades composées
    ("salades composées",               "Entrées"),
    ("entrées froides",                 "Entrées"),
    ("entrées chaudes",                 "Entrées"),
    ("salades vertes",                  "Entrées"),
    ("entrées de noël",                 "Entrées"),
    ("entrées spécial réveillon",       "Entrées"),
    ("apéritifs et entrées de fête",    "Entrées"),  # mixed category → Entrées
    ("entrée mariage",                  "Entrées"),
    ("entrées",                         "Entrées"),
    # Section: Soupes et Veloutés
    ("soupes et veloutés",              "Entrées"),
    ("velouté",                         "Entrées"),
    ("soupes",                          "Entrées"),

    # ── Plats ────────────────────────────────────────────────────────────
    # Section: Les plateaux (boucher = main course)
    ("les plateaux du boucher",         "Plats"),
    ("les pizzas & quiches géantes",    "Plats"),
    # Section: Fruits de mer
    ("plateaux de fruits de mer",       "Plats"),
    ("huîtres",                         "Plats"),
    ("condiment spécial fruits de mer", "Plats"),
    ("fruits de mer",                   "Plats"),
    # Section: Plats cuisinés
    ("viandes et volailles",            "Plats"),
    ("plats complets",                  "Plats"),
    ("prêts à cuire",                   "Plats"),
    ("exotiques",                       "Plats"),
    ("pizzas & quiches",                "Plats"),
    ("plats cuisinés",                  "Plats"),
    # Section: Menus traiteur
    ("menus classiques",                "Plats"),
    ("menus et plat principal",         "Plats"),
    ("menus et plats cuisinés",         "Plats"),
    ("menus traiteur",                  "Plats"),
    ("plats et menus de réveillon",     "Plats"),
    # Generic plat signals (from data)
    ("grillade",                        "Plats"),
    ("plateaux barbecue",               "Plats"),
    ("prêts à griller",                 "Plats"),
    ("spécial barbecue",                "Plats"),
    ("plats",                           "Plats"),  # broad — keep last

    # ── Pains → Apéritifs ────────────────────────────────────────────────
    # Section: Pains (bread served at reception = apéritif context)
    ("baguettes",                       "Apéritifs"),
    ("tranchés",                        "Apéritifs"),
    ("à garnir / à tartiner",           "Apéritifs"),
    ("à garnir",                        "Apéritifs"),
    # "produits bio" is too generic — omitted, let department fallback decide

    # ── Les à côtés → Plats ───────────────────────────────────────────────
    # Section: Les à côtés (side dishes)
    ("sauces et condiments",            "Plats"),
]
