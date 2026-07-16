-- =====================================================================
-- Seed de données de TEST — Marketplace B2B (Sika)
-- Comptes (client / vendeur / admin) + profils + rôles + catégories + produits.
--
-- IDEMPOTENT : rejouable sans créer de doublons (garde sur email / slug / rôle).
--
-- Usage :
--   • Éditeur SQL Supabase : coller ce fichier et exécuter.
--   • ou en CLI :  psql "$DATABASE_URL" -f Backend/seed_test_data.sql
--
-- Comptes créés (mots de passe en clair ci-dessous, hash bcrypt dans le SQL) :
--   CLIENT  (buyer)    : client.test@sika.ci   / Client@2026
--   VENDEUR (supplier) : vendeur.test@sika.ci  / Vendeur@2026   (a aussi le rôle buyer)
--   ADMIN   (admin)    : admin.test@sika.ci    / Admin@2026     (accès back-office)
--
-- Les hash ont été générés avec AuthService.hash_password (bcrypt) du backend,
-- donc compatibles avec la vérification de connexion.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) UTILISATEURS (status=active, vérifiés → connexion immédiate possible)
-- ---------------------------------------------------------------------
INSERT INTO users (email, phone, password_hash, user_type, status, email_verified, phone_verified, created_at, updated_at)
SELECT v.email, v.phone, v.ph, v.utype::user_type, 'active'::user_status, TRUE, TRUE, NOW(), NOW()
FROM (VALUES
    ('client.test@sika.ci',  '+2250759000091', '$2b$12$XM4N391E1xi1hwify72Hk.rDRKzbZnyOptyQJ6Dyd5TDjkrxglMde', 'buyer'),
    ('vendeur.test@sika.ci', '+2250759000092', '$2b$12$OxVEKXHMFsBJC6T.JfvciekQNQdIlc4xXFV3ny8W3kFcZ2yMtM6Lm', 'supplier'),
    ('admin.test@sika.ci',   '+2250759000093', '$2b$12$AmxS0S7O5lUkiHrpc1D3TeunTApaD5oREQIvLGr.TRIqNfCov6LjK', 'admin')
) AS v(email, phone, ph, utype)
WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.email = v.email);

-- ---------------------------------------------------------------------
-- 2) PROFILS ENTREPRISE (client + vendeur ; l'admin n'en a pas besoin)
-- ---------------------------------------------------------------------
INSERT INTO company_profiles (user_id, company_name, contact_person, city, phone, is_verified)
SELECT u.id, v.company, v.contact, v.city, u.phone, TRUE
FROM (VALUES
    ('client.test@sika.ci',  'Boutique Awa',                 'Awa Koné',     'Abidjan'),
    ('vendeur.test@sika.ci', 'Sika Distribution (Grossiste)', 'Kouassi Yao',  'Abidjan')
) AS v(email, company, contact, city)
JOIN users u ON u.email = v.email
WHERE NOT EXISTS (SELECT 1 FROM company_profiles c WHERE c.user_id = u.id);

-- ---------------------------------------------------------------------
-- 3) RÔLES (T5) : client→buyer ; vendeur→supplier+buyer ; admin→admin
-- ---------------------------------------------------------------------
INSERT INTO user_roles (user_id, role, created_at)
SELECT u.id, r.role, NOW()
FROM (VALUES
    ('client.test@sika.ci',  'buyer'),
    ('vendeur.test@sika.ci', 'supplier'),
    ('vendeur.test@sika.ci', 'buyer'),
    ('admin.test@sika.ci',   'admin')
) AS r(email, role)
JOIN users u ON u.email = r.email
WHERE NOT EXISTS (
    SELECT 1 FROM user_roles ur WHERE ur.user_id = u.id AND ur.role = r.role
);

-- ---------------------------------------------------------------------
-- 4) CATÉGORIES (idempotent par slug)
-- ---------------------------------------------------------------------
INSERT INTO categories (name, slug, description, is_active, is_deleted, created_at)
SELECT v.name, v.slug, v.descr, TRUE, FALSE, NOW()
FROM (VALUES
    ('Alimentaire & Épicerie', 'alimentaire-epicerie', 'Denrées de base, céréales, conserves.'),
    ('Électroménager',         'electromenager',       'Appareils et équipements pour la maison.'),
    ('Téléphones & Accessoires','telephones',          'Smartphones, accessoires et pièces.'),
    ('Informatique',           'informatique',         'Ordinateurs, périphériques et fournitures.'),
    ('Cosmétique & Beauté',    'cosmetique',           'Soins, hygiène et produits de beauté.')
) AS v(name, slug, descr)
WHERE NOT EXISTS (SELECT 1 FROM categories c WHERE c.slug = v.slug);

-- ---------------------------------------------------------------------
-- 5) PRODUITS (appartiennent au VENDEUR ; certains featured pour l'accueil)
-- ---------------------------------------------------------------------
INSERT INTO products (
    supplier_id, category_id, name, slug, description, short_description,
    price, currency, min_order_quantity, stock_quantity, unit,
    is_active, is_featured, views_count, is_deleted, created_at, updated_at
)
SELECT s.id, c.id, v.name, v.slug, v.descr, v.short,
       v.price, 'XOF', v.moq, v.stock, v.unit,
       TRUE, v.featured, 0, FALSE, NOW(), NOW()
FROM (VALUES
    -- name, slug, description, short, price, moq, stock, unit, featured, cat_slug
    ('Sac de riz parfumé 25 kg',        'riz-parfume-25kg',        'Riz parfumé longue tenue, sac de 25 kg.',              'Riz parfumé 25 kg',        18000, 10, 200, 'sac',    TRUE,  'alimentaire-epicerie'),
    ('Bidon d''huile végétale 20 L',    'huile-vegetale-20l',      'Huile de cuisine raffinée, bidon de 20 litres.',       'Huile végétale 20 L',      22000, 5,  120, 'bidon',  TRUE,  'alimentaire-epicerie'),
    ('Ventilateur brasseur d''air',     'ventilateur-brasseur',    'Ventilateur sur pied, débit d''air élevé.',            'Ventilateur sur pied',     35000, 2,  40,  'pièce',  TRUE,  'electromenager'),
    ('Smartphone Android 128 Go',       'smartphone-android-128',  'Smartphone 128 Go, double SIM, écran 6.5".',           'Android 128 Go',           95000, 1,  60,  'pièce',  TRUE,  'telephones'),
    ('Chargeur rapide USB-C 25W',       'chargeur-usbc-25w',       'Chargeur secteur USB-C charge rapide 25 W.',           'Chargeur USB-C 25W',        6500, 10, 300, 'pièce',  FALSE, 'telephones'),
    ('Clé USB 64 Go',                   'cle-usb-64go',            'Clé USB 3.0 64 Go haute vitesse.',                     'Clé USB 64 Go',             5000, 10, 250, 'pièce',  FALSE, 'informatique'),
    ('Savon de beauté (carton 48)',     'savon-beaute-carton-48',  'Carton de 48 savons de toilette parfumés.',            'Savon carton x48',         12000, 3,  80,  'carton', TRUE,  'cosmetique')
) AS v(name, slug, descr, short, price, moq, stock, unit, featured, cat_slug)
JOIN users s      ON s.email = 'vendeur.test@sika.ci'
JOIN categories c ON c.slug  = v.cat_slug
WHERE NOT EXISTS (SELECT 1 FROM products p WHERE p.slug = v.slug);

-- ---------------------------------------------------------------------
-- Vérifications (facultatif)
-- ---------------------------------------------------------------------
-- SELECT email, user_type, status FROM users WHERE email LIKE '%@sika.ci';
-- SELECT u.email, array_agg(ur.role) FROM users u JOIN user_roles ur ON ur.user_id=u.id
--   WHERE u.email LIKE '%@sika.ci' GROUP BY u.email;
-- SELECT name, price, is_featured FROM products WHERE supplier_id =
--   (SELECT id FROM users WHERE email='vendeur.test@sika.ci');
