"""
Carrefour Traiteur official navigation hierarchy → menu_step mapping.

Structure mirrors traiteur.carrefour.fr/a-la-carte.html exactly.
Each top-level section maps to one of our 11 menu steps:
  Apéritifs | Entrées | Plats | Plateaux | Fromages | Desserts | Boissons | Pains | Petit Déj | Table & Déco | Fleurs

Non-food sections (Arts de la table, Décoration de fête) now map to "Table & Déco"
so they are indexed in Pinecone and surfaceable by the assistant.
Only true non-product categories (fleurs, bouquets) remain excluded.

Usage in derive.py: join all product category names, then iterate
CATEGORY_TO_STEP in order — first match wins. More specific entries
must appear before broader ones that could shadow them.
"""

# ---------------------------------------------------------------------------
# Non-food — products in these categories should have menu_step = None.
# Arts de la table and Déco de fête are intentionally NOT here anymore —
# they now map to "Table & Déco" so the assistant can recommend them.
# ---------------------------------------------------------------------------

NON_FOOD_CATEGORY_KEYWORDS: list[str] = [
    # Nothing excluded at this level anymore — all categories with products
    # now map to an explicit step so the assistant can recommend them.
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
    # Section: Boissons — specific categories first, generic last.
    # "boissons & déco de fête" / "boisson & déco de fête" are INTENTIONALLY
    # placed after the specific Boissons categories (vins, champagnes, etc.)
    # because Carrefour uses them as a shared parent for BOTH wine products
    # AND party tableware. Real beverages already carry a specific category
    # (e.g. "Vins", "Champagnes et vins pétillants") that fires earlier.
    # Only products with NO specific boissons category (serviettes, chemins
    # de table…) fall through to the "& déco de fête" rule → Table & Déco.
    ("eaux, sodas et jus de fruits",    "Boissons"),
    ("bières & cidres",                 "Boissons"),
    ("champagnes et vins pétillants",   "Boissons"),
    ("apéritifs et digestifs",          "Boissons"),
    ("cafés et thés",                   "Boissons"),
    ("carte des boissons",              "Boissons"),
    ("boissons chaudes",                "Boissons"),
    ("vins",                            "Boissons"),
    # Mixed "boissons & déco" categories — redirect to Table & Déco when the
    # product has no real beverage category above.
    ("boissons & déco de fête",         "Table & Déco"),
    ("boisson & déco de fête",          "Table & Déco"),
    ("boissons",                        "Boissons"),

    # ── Plateaux ─────────────────────────────────────────────────────────
    # Section: Les plateaux — mixed assorted platters (meat, charcuterie, BBQ)
    # Must come before Apéritifs/Plats/Fromages to win over generic matches.
    ("les plateaux du boucher",         "Plateaux"),
    ("plateaux déjà composés",          "Plateaux"),
    ("plateaux à composer",             "Plateaux"),
    ("plateaux grands formats",         "Plateaux"),
    ("accompagnez votre plateau",       "Plateaux"),
    ("plateaux barbecue",               "Plateaux"),
    ("les plateaux de charcuterie",     "Plateaux"),
    ("plateau de charcuterie",          "Plateaux"),
    ("plateaux de charcuteries",        "Plateaux"),

    # ── Fromages ─────────────────────────────────────────────────────────
    # Section: Fromages — cheese-specific boards and products
    ("fromages à la carte",             "Fromages"),
    ("plateaux de fromages",            "Fromages"),
    ("fromages & pains",                "Fromages"),
    ("fromages",                        "Fromages"),

    # ── Desserts (high-priority specific keywords) ───────────────────────
    # These must come BEFORE Petit Déj because Carrefour sometimes tags pastry
    # and dessert products with "Petit déjeuner & goûter" as a secondary
    # category. The product-specific signals win.
    ("pâtisseries individuelles",       "Desserts"),
    ("les individuels",                 "Desserts"),
    ("petits fours et mignardises",     "Desserts"),
    ("gâteaux enfants",                 "Desserts"),

    # ── Petit Déj ─────────────────────────────────────────────────────────
    # Section: Petit déjeuner & goûter
    ("petit déjeuner & goûter",         "Petit Déj"),
    ("viennoiseries",                   "Petit Déj"),
    ("au petit déjeuner",               "Petit Déj"),
    ("au petit-déjeuner",               "Petit Déj"),
    ("petit déjeuner",                  "Petit Déj"),
    ("café et petit déjeuner",          "Petit Déj"),

    # ── Desserts ─────────────────────────────────────────────────────────
    # Section: Gâteaux & desserts
    ("tartes",                          "Desserts"),
    ("fruits et corbeilles de fruits",  "Desserts"),
    ("gâteaux et desserts",             "Desserts"),
    ("gâteaux",                         "Desserts"),
    ("farandole de desserts",           "Desserts"),
    ("bûches et desserts",              "Desserts"),
    ("desserts et gâteaux",             "Desserts"),
    ("desserts et gourmandises",        "Desserts"),
    ("desserts",                        "Desserts"),
    # Petit-déj items that also appear under dessert sections
    ("mignardises et petits plaisirs",  "Desserts"),
    ("pâtisseries américaines",         "Desserts"),
    ("pâtisseries individuelles",       "Desserts"),
    ("gâteaux et tartes",               "Desserts"),
    ("bonbons et friandises",           "Desserts"),
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
    ("prêts à griller",                 "Plats"),
    ("spécial barbecue",                "Plats"),
    ("plats",                           "Plats"),  # broad — keep last

    # ── Pains ─────────────────────────────────────────────────────────────
    # Section: Pains — breads, baguettes, rolls for serving alongside food
    ("baguettes",                       "Pains"),
    ("tranchés",                        "Pains"),
    ("à garnir / à tartiner",           "Pains"),
    ("à garnir",                        "Pains"),
    ("mini pains",                      "Pains"),
    ("petits pains",                    "Pains"),
    ("pains burger",                    "Pains"),
    ("navettes",                        "Pains"),
    # "produits bio" is too generic — omitted, let department fallback decide

    # ── Les à côtés → Plats ───────────────────────────────────────────────
    # Section: Les à côtés (side dishes)
    ("sauces et condiments",            "Plats"),

    # ── Table & Déco ──────────────────────────────────────────────────────
    # Section: Arts de la table — tableware for serving and decoration
    ("arts de la table",                "Table & Déco"),
    ("assiettes et contenants",         "Table & Déco"),
    ("gobelets",                        "Table & Déco"),
    ("couverts",                        "Table & Déco"),
    ("nappes",                          "Table & Déco"),
    ("vaisselle",                       "Table & Déco"),
    # NOTE: "a table !" intentionally omitted — in Carrefour's taxonomy it
    # means "foods ready to eat at the table" (pains, fromages…), not tableware.
    # Products with this tag fall through to their other categories instead.
    ("vaisselle & déco de fête",        "Table & Déco"),
    ("vaisselle et déco de table",      "Table & Déco"),
    ("vaisselle et décoration de table","Table & Déco"),  # actual spelling in export
    ("vaisselle et accessoires",        "Table & Déco"),
    # Section: Décoration de fête
    ("décoration de fête",              "Table & Déco"),
    ("déco de fête",                    "Table & Déco"),
    ("déco spéciale",                   "Table & Déco"),
    ("déco de table",                   "Table & Déco"),
    ("bougies",                         "Table & Déco"),
    ("ballons",                         "Table & Déco"),
    ("spécial anniversaire",            "Table & Déco"),
    ("serviettes",                      "Table & Déco"),

    # ── Fleurs ────────────────────────────────────────────────────────────
    # Note: "Fleurs" department products are caught earlier by _DEPARTMENT_STEP
    # in derive.py, so these keywords are a safety fallback only.
    # "fleurs et vaisselle" intentionally omitted — it's a shared parent
    # category that also applies to tableware products (Non AL dept), causing
    # them to be misclassified as Fleurs instead of Table & Déco.
    ("fleurs fraîches",                 "Fleurs"),
    ("fleurs séchées",                  "Fleurs"),
    ("fleurs artificielles",            "Fleurs"),
    ("composition florale",             "Fleurs"),
    ("bouquets",                        "Fleurs"),
    ("fleurs",                          "Fleurs"),
]
