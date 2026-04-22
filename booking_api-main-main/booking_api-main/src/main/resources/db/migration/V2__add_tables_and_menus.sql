-- Создаем таблицу для столиков в ресторане
CREATE TABLE restaurant_tables (
    id BIGSERIAL PRIMARY KEY,
    restaurant_id BIGINT NOT NULL,
    table_number INT NOT NULL,
    capacity INT NOT NULL, -- Вместимость (на сколько человек)
    CONSTRAINT fk_table_restaurant FOREIGN KEY (restaurant_id) REFERENCES restaurants (id) ON DELETE CASCADE
);

-- Создаем таблицу для позиций меню
CREATE TABLE menu_items (
    id BIGSERIAL PRIMARY KEY,
    restaurant_id BIGINT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    category VARCHAR(100), -- Например: Салаты, Горячее, Напитки
    CONSTRAINT fk_menu_restaurant FOREIGN KEY (restaurant_id) REFERENCES restaurants (id) ON DELETE CASCADE
);