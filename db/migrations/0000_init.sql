CREATE TABLE migrations (
    id VARCHAR(6) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE bug_reports (
    id SERIAL PRIMARY KEY,
    telegram_id INTEGER NOT NULL,
    telegram_tag VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    solved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- chatters - Общая конфа ТГ, где могут присутствовать как одиночки, так и другие отряды, помимо основного
CREATE TABLE chatters (
    id SERIAL PRIMARY KEY,
    telegram_chat_id VARCHAR(20) NOT NULL,
    telegram_chat_thread_id VARCHAR(20) NOT NULL DEFAULT '',
    ui_message_id INTEGER,
    ui_message_hash VARCHAR(31)
);

CREATE TABLE squads (
    id SERIAL PRIMARY KEY,
    chatters_id INT NOT NULL REFERENCES chatters(id),
    name varchar(50) NOT NULL,
    tags varchar(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    telegram_id INTEGER NOT NULL,
    telegram_tag VARCHAR(200) NOT NULL,
    chatters_id INT NOT NULL REFERENCES chatters(id),
    squad_id INT REFERENCES squads(id),
    name varchar(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    title VARCHAR(50) NOT NULL,
    chatters_id INT NOT NULL REFERENCES chatters(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE schedules_presets (
    id SERIAL PRIMARY KEY,
    chatters_id INT NOT NULL REFERENCES chatters(id),
    game INT NOT NULL REFERENCES games(id),
    name VARCHAR(50) NOT NULL,
    game_time TIME NOT NULL,
    game_day_of_week INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE schedules (
    id SERIAL PRIMARY KEY,
    player_id INT NOT NULL REFERENCES players(id),
    schedule_preset_id INT NOT NULL REFERENCES schedules_presets(id),
    will_attend_default BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE attendances (
    id SERIAL PRIMARY KEY,
    schedule_preset_id INT NOT NULL REFERENCES schedules_presets(id),
    player_id INT NOT NULL REFERENCES players(id),
    attend_status VARCHAR(20),
    --attended BOOLEAN NOT NULL DEFAULT false,
    comment VARCHAR(100) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    telegram_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE ocaps (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL UNIQUE,
    length_seconds INTEGER NOT NULL,
    game_type VARCHAR(50) NOT NULL,
    date_number BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE ocaps_players (
    id SERIAL PRIMARY KEY,
    ocap_id INT NOT NULL REFERENCES ocaps(id) ON DELETE CASCADE,
    game_id INTEGER NOT NULL,
    name VARCHAR(200) NOT NULL,
    group_name VARCHAR(200) NOT NULL,
    side VARCHAR(50) NOT NULL,
    dead_at_frame INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE ocaps_kills (
    id SERIAL PRIMARY KEY,
    ocap_id INT NOT NULL REFERENCES ocaps(id) ON DELETE CASCADE,
    killer_id INTEGER NOT NULL,
    killed_id INTEGER,
    killer_vehicle VARCHAR(200),
    killed_vehicle VARCHAR(200),
    team_kill BOOLEAN NOT NULL DEFAULT FALSE,
    frame INTEGER NOT NULL,
    weapon VARCHAR(200) NOT NULL,
    weapon_is_vehicle BOOLEAN NOT NULL DEFAULT FALSE,
    distance INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ocaps_game_type_date_number ON ocaps(game_type, date_number DESC);
CREATE INDEX idx_ocaps_players_ocap_game_id ON ocaps_players(ocap_id, game_id);
CREATE INDEX idx_ocaps_players_name ON ocaps_players(name);
CREATE INDEX idx_ocaps_kills_ocap_id ON ocaps_kills(ocap_id);

-- Utility
CREATE TABLE usage_statistics (
    -- Таблица для ведения статистики, кто, каким, и сколько пользуются функционалом бота
    id INTEGER PRIMARY KEY,
    squad_id INT NOT NULL REFERENCES squads(id),
    telegram_id INTEGER NOT NULL,
    telegram_tag VARCHAR(200) NOT NULL,
    function VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
