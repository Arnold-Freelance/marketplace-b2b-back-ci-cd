-- Base de données MVP - Marketplace B2B Local Côte d'Ivoire
-- PostgreSQL avec extensions pour géolocalisation et JSON
-- IDs INTEGER auto-increment pour sécurité

-- Extensions nécessaires
CREATE EXTENSION IF NOT EXISTS "postgis";
-- insensibilité à la casse pour les emails, logins…
CREATE EXTENSION IF NOT EXISTS citext;
-- enlever les accents pour la recherche
CREATE EXTENSION IF NOT EXISTS unaccent;
-- recherche floue/auto-complétion
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Types énumérés
CREATE TYPE user_type AS ENUM ('supplier', 'buyer', 'admin');
CREATE TYPE user_status AS ENUM ('pending', 'active', 'suspended', 'inactive');
CREATE TYPE order_status AS ENUM ('pending', 'confirmed', 'paid', 'shipped', 'delivered', 'cancelled');
CREATE TYPE payment_status AS ENUM ('pending', 'completed', 'failed', 'refunded');
CREATE TYPE payment_method AS ENUM ('wave', 'cinetpay', 'bank_transfer', 'cash');
CREATE TYPE message_status AS ENUM ('sent', 'delivered', 'read');
CREATE TYPE notification_type AS ENUM ('order', 'payment', 'message', 'system');

-- Table des utilisateurs (fournisseurs, acheteurs, admins)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    user_type user_type NOT NULL,
    status user_status DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    email_verified BOOLEAN DEFAULT FALSE,
    phone_verified BOOLEAN DEFAULT FALSE
);

-- Profils détaillés des entreprises
CREATE TABLE company_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    company_name VARCHAR(255) NOT NULL,
    business_registration VARCHAR(100),
    company_description TEXT,
    website VARCHAR(255),
    logo_url VARCHAR(500),
    
    -- Informations de contact
    contact_person VARCHAR(255),
    address TEXT,
    city VARCHAR(100),
    district VARCHAR(100),
    postal_code VARCHAR(20),
    location GEOGRAPHY(POINT),
    
    -- Informations commerciales
    business_category VARCHAR(100),
    years_in_business INTEGER,
    employee_count INTEGER,
    annual_turnover DECIMAL(15,2),
    
    -- Documents et vérifications
    documents JSONB, -- Stockage des URLs des documents
    is_verified BOOLEAN DEFAULT FALSE,
    verification_date TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Catégories de produits/services
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    parent_id INTEGER REFERENCES categories(id),
    description TEXT,
    icon_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Produits/Services
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    supplier_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id),
    
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    description TEXT,
    short_description VARCHAR(500),
    
    -- Informations commerciales
    sku VARCHAR(100),
    price DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'XOF',
    min_order_quantity INTEGER DEFAULT 1,
    stock_quantity INTEGER DEFAULT 0,
    unit VARCHAR(50), -- kg, litre, pièce, etc.
    
    -- Médias
    images JSONB, -- Array d'URLs d'images
    documents JSONB, -- Fiches techniques, certificats
    
    -- Attributs flexibles (caractéristiques produit)
    attributes JSONB,
    
    -- SEO et visibilité
    is_active BOOLEAN DEFAULT TRUE,
    is_featured BOOLEAN DEFAULT FALSE,
    views_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(supplier_id, slug)
);

-- Commandes
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    buyer_id INTEGER REFERENCES users(id) ON DELETE RESTRICT,
    supplier_id INTEGER REFERENCES users(id) ON DELETE RESTRICT,
    
    -- Montants
    subtotal DECIMAL(12,2) NOT NULL,
    tax_amount DECIMAL(12,2) DEFAULT 0,
    shipping_amount DECIMAL(12,2) DEFAULT 0,
    discount_amount DECIMAL(12,2) DEFAULT 0,
    total_amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'XOF',
    
    -- Statuts
    status order_status DEFAULT 'pending',
    payment_status payment_status DEFAULT 'pending',
    
    -- Adresses
    billing_address JSONB,
    shipping_address JSONB,
    
    -- Dates importantes
    ordered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP WITH TIME ZONE,
    shipped_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    
    -- Notes et commentaires
    buyer_notes TEXT,
    supplier_notes TEXT,
    admin_notes TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Détails des commandes (produits commandés)
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE RESTRICT,
    
    product_name VARCHAR(255) NOT NULL,
    product_sku VARCHAR(100),
    unit_price DECIMAL(10,2) NOT NULL,
    quantity INTEGER NOT NULL,
    total_price DECIMAL(12,2) NOT NULL,
    
    -- Snapshot des attributs au moment de la commande
    product_attributes JSONB,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Paiements
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    payment_reference VARCHAR(255) UNIQUE NOT NULL,
    
    amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'XOF',
    method payment_method NOT NULL,
    status payment_status DEFAULT 'pending',
    
    -- Détails du paiement
    provider_reference VARCHAR(255),
    provider_response JSONB,
    
    -- Informations paiement mobile
    payer_phone VARCHAR(20),
    payer_name VARCHAR(255),
    
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Système de messagerie interne
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    buyer_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    supplier_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    subject VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(buyer_id, supplier_id, order_id)
);

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    attachments JSONB,
    status message_status DEFAULT 'sent',
    read_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Notifications système
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    type notification_type NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    data JSONB, -- Données additionnelles (IDs, liens, etc.)
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Évaluations et avis
CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    reviewer_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    reviewed_id INTEGER REFERENCES users(id) ON DELETE CASCADE, -- Fournisseur évalué
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    title VARCHAR(255),
    comment TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    is_public BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(order_id, reviewer_id, reviewed_id)
);

-- Favoris/Wishlist
CREATE TABLE favorites (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, product_id)
);

-- Suivi des activités (pour analytics)
CREATE TABLE activity_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL, -- login, view_product, create_order, etc.
    resource_type VARCHAR(50), -- user, product, order, etc.
    resource_id INTEGER,
    metadata JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Configuration système
CREATE TABLE system_settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour les performances
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_phone ON users(phone);
CREATE INDEX idx_users_type_status ON users(user_type, status);
CREATE INDEX idx_company_profiles_user_id ON company_profiles(user_id);
CREATE INDEX idx_company_profiles_location ON company_profiles USING GIST(location);
CREATE INDEX idx_products_supplier ON products(supplier_id);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_active ON products(is_active);
CREATE INDEX idx_products_search ON products USING GIN(to_tsvector('french', name || ' ' || description));
CREATE INDEX idx_orders_buyer ON orders(buyer_id);
CREATE INDEX idx_orders_supplier ON orders(supplier_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_date ON orders(ordered_at);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);
CREATE INDEX idx_payments_order ON payments(order_id);
CREATE INDEX idx_payments_reference ON payments(payment_reference);
CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_notifications_user ON notifications(user_id, is_read);
CREATE INDEX idx_activity_logs_user ON activity_logs(user_id);
CREATE INDEX idx_activity_logs_date ON activity_logs(created_at);

-- Triggers pour updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_company_profiles_updated_at BEFORE UPDATE ON company_profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON products FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_payments_updated_at BEFORE UPDATE ON payments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_reviews_updated_at BEFORE UPDATE ON reviews FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Données de base pour le MVP
INSERT INTO categories (name, slug, description) VALUES
('Alimentation & Boissons', 'alimentation-boissons', 'Produits alimentaires et boissons'),
('Agriculture & Élevage', 'agriculture-elevage', 'Produits agricoles et d''élevage'),
('Textile & Habillement', 'textile-habillement', 'Tissus, vêtements et accessoires'),
('Matériaux de Construction', 'materiaux-construction', 'Matériaux pour la construction'),
('Équipements & Machines', 'equipements-machines', 'Machines et équipements industriels'),
('Services Logistiques', 'services-logistiques', 'Transport et logistique'),
('Cosmétiques & Hygiène', 'cosmetiques-hygiene', 'Produits de beauté et d''hygiène'),
('Électronique & IT', 'electronique-it', 'Matériel électronique et informatique');

INSERT INTO system_settings (key, value, description) VALUES
('platform_commission_rate', '0.025', 'Taux de commission de la plateforme (2.5%)'),
('min_order_amount', '10000', 'Montant minimum de commande en XOF'),
('currency_default', '"XOF"', 'Devise par défaut'),
('payment_methods_enabled', '["wave", "cinetpay", "bank_transfer"]', 'Méthodes de paiement activées'),
('auto_confirm_orders', 'false', 'Confirmation automatique des commandes'),
('email_notifications', 'true', 'Notifications par email activées'),
('sms_notifications', 'true', 'Notifications SMS activées');

-- Commentaires pour la documentation
COMMENT ON TABLE users IS 'Utilisateurs de la plateforme (fournisseurs, acheteurs, admins)';
COMMENT ON TABLE company_profiles IS 'Profils détaillés des entreprises';
COMMENT ON TABLE products IS 'Catalogue des produits et services';
COMMENT ON TABLE orders IS 'Commandes passées sur la plateforme';
COMMENT ON TABLE payments IS 'Transactions de paiement';
COMMENT ON TABLE conversations IS 'Conversations entre utilisateurs';
COMMENT ON TABLE messages IS 'Messages échangés dans les conversations';
COMMENT ON TABLE notifications IS 'Notifications système pour les utilisateurs';
COMMENT ON TABLE reviews IS 'Évaluations et avis des utilisateurs';
COMMENT ON TABLE activity_logs IS 'Journal des activités pour l''analytics';