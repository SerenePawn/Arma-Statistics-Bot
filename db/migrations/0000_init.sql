CREATE TABLE "migrations" (
    "id" VARCHAR(6) NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "bug_reports" (
    "id" INTEGER PRIMARY KEY,
    "telegram_id" INTEGER NOT NULL,
    "telegram_tag" VARCHAR(200) NOT NULL,
    "description" TEXT NOT NULL,
    "solved" BOOLEAN NOT NULL DEFAULT FALSE,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "squads" (
    "id" INTEGER PRIMARY KEY,
    "telegram_chat_id" varchar(20) NOT NULL,
    "telegram_chat_thread_id" varchar(20) NOT NULL DEFAULT '',
    "ui_message_id" INTEGER,
    "ui_message_hash" VARCHAR(31),
    "name" varchar(50) NOT NULL,
    "tags" varchar(100) NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "players" (
    "id" INTEGER PRIMARY KEY,
    "telegram_id" INTEGER NOT NULL,
    "telegram_tag" VARCHAR(200) NOT NULL,
    "squad_id" INT NOT NULL REFERENCES squads(id),
    "name" varchar(50) NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "schedules_presets" (
    "id" INTEGER PRIMARY KEY,
    "squad_id" INT NOT NULL REFERENCES squads(id),
    "game_name" VARCHAR(50) NOT NULL,
    "game_time" TIME NOT NULL,
    "game_day_of_week" INT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "attendances" (
    "id" INTEGER PRIMARY KEY,
    "schedule_preset_id" INT NOT NULL REFERENCES schedules_presets(id),
    "player_id" INT NOT NULL REFERENCES players(id),
    "attend_status" VARCHAR(20),
    --"attended" BOOLEAN NOT NULL DEFAULT false,
    "comment" VARCHAR(100) NOT NULL DEFAULT '',
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "schedules" (
    "id" INTEGER PRIMARY KEY,
    "player_id" INT NOT NULL REFERENCES players(id),
    "schedule_preset_id" INT NOT NULL REFERENCES schedules_presets(id),
    "will_attend_default" BOOLEAN NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- OCAP cache
CREATE TABLE "ocaps" (
    "id" INTEGER PRIMARY KEY,
    "filename" TEXT NOT NULL UNIQUE,
    "date_number" INTEGER NOT NULL,
    "length_seconds" INTEGER NOT NULL,  -- Длина миски без учета фриз-тайма
    "game_type" VARCHAR(5) NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "ocaps_players" (
    "game_id" INTEGER NOT NULL,
    "ocap_id" INTEGER NOT NULL REFERENCES ocaps(id) ON DELETE CASCADE,
    "name" VARCHAR(100) NOT NULL,
    "group_name" VARCHAR(100) NOT NULL,
    "side" VARCHAR(20) NOT NULL,
    "dead_at_frame" INTEGER DEFAULT 0
);

CREATE TABLE "ocaps_kills" (
    "ocap_id" INTEGER NOT NULL REFERENCES ocaps(id) ON DELETE CASCADE,
    "killer_id" INTEGER NOT NULL REFERENCES ocaps_players(game_id) ON DELETE CASCADE,
    "killer_vehicle" VARCHAR(100), -- Если игрок убил с техники (по крайней мере, алгоритм нашел), то не нулевое
    "killed_id" INTEGER REFERENCES ocaps_players(game_id) ON DELETE CASCADE, -- Если убит игрок, то не нулевое
    "killed_vehicle" VARCHAR(100), -- Если минус техника, то не нулевое
    "team_kill" BOOLEAN NOT NULL DEFAULT false,
    "frame" INT NOT NULL DEFAULT '',
    "weapon" VARCHAR(100) NOT NULL DEFAULT '',
    "weapon_is_vehicle" BOOLEAN NOT NULL DEFAULT false,
    "distance" INT
);

-- Utility
CREATE TABLE "usage_statistics" (
    -- Таблица для ведения статистики, кто, каким, и сколько пользуются функционалом бота
    "id" INTEGER PRIMARY KEY,
    "squad_id" INT NOT NULL REFERENCES squads(id),
    "telegram_id" INTEGER NOT NULL,
    "telegram_tag" VARCHAR(200) NOT NULL,
    "function" VARCHAR(100) NOT NULL UNIQUE,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
