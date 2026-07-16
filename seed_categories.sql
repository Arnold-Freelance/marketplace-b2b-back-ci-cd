-- =====================================================================
-- Seed des catégories — Marketplace B2B (Sika)
-- Table : categories (cf. app/models/category_entity.py)
--
-- Idempotent : n'insère une catégorie que si son `slug` n'existe pas déjà,
-- donc rejouable sans créer de doublons.
--
-- Usage :
--   psql "$DATABASE_URL" -f Backend/seed_categories.sql
--   (ou coller dans l'éditeur SQL Supabase)
-- =====================================================================

INSERT INTO categories (name, slug, description, is_active, is_deleted, created_at)
SELECT v.name, v.slug, v.description, TRUE, FALSE, NOW()
FROM (
    VALUES
        ('Alimentaire & Épicerie',      'alimentaire-epicerie',      'Épicerie sèche, conserves et denrées de base.'),
        ('Céréales & Riz',              'cereales-riz',              'Riz, maïs, mil, blé et autres céréales en gros.'),
        ('Fruits & Légumes',            'fruits-legumes',            'Produits maraîchers frais, locaux et d''import.'),
        ('Produits frais & Surgelés',   'produits-frais-surgeles',   'Viandes, poissons, produits laitiers et surgelés.'),
        ('Boissons',                    'boissons',                  'Eaux, jus, sodas et boissons en gros.'),
        ('Hygiène & Entretien',         'hygiene-entretien',         'Produits d''hygiène, nettoyage et entretien.'),
        ('Cosmétiques & Beauté',        'cosmetiques-beaute',        'Soins, cosmétiques et produits de beauté.'),
        ('Emballage & Conditionnement', 'emballage-conditionnement', 'Cartons, sacs, films et solutions d''emballage.'),
        ('Matériel & Équipement',       'materiel-equipement',       'Équipements pro, outillage et machines.'),
        ('Électronique & Électroménager','electronique-electromenager','Appareils électroniques et électroménager.'),
        ('Textile & Habillement',       'textile-habillement',       'Tissus, vêtements et accessoires en gros.'),
        ('Construction & BTP',          'construction-btp',          'Matériaux de construction et fournitures BTP.'),
        ('Agriculture & Élevage',       'agriculture-elevage',       'Intrants agricoles, semences et produits d''élevage.'),
        ('Papeterie & Bureau',          'papeterie-bureau',          'Fournitures de bureau et papeterie.')
) AS v(name, slug, description)
WHERE NOT EXISTS (
    SELECT 1 FROM categories c WHERE c.slug = v.slug
);

-- Vérification
SELECT id, name, slug, is_active FROM categories WHERE is_deleted = FALSE ORDER BY name;
