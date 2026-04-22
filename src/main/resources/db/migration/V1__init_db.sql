-- Создаем таблицу пользователей (владельцев ресторанов, клиентов, админов)
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL, -- например: ROLE_CUSTOMER, ROLE_OWNER, ROLE_ADMIN
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создаем таблицу ресторанов
CREATE TABLE restaurants (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id BIGINT NOT NULL, -- Ссылка на ID владельца из таблицы users
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_restaurant_owner FOREIGN KEY (owner_id) REFERENCES users (id) ON DELETE CASCADE
);