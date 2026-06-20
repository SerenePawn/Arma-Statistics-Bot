-- Global games catalog: remove community binding
ALTER TABLE games DROP COLUMN IF EXISTS chatters_id;

CREATE UNIQUE INDEX IF NOT EXISTS games_title_uidx ON games (title);

-- schedules_presets: squad_id + game_id
ALTER TABLE schedules_presets
    ADD COLUMN IF NOT EXISTS squad_id INT REFERENCES squads(id);

UPDATE schedules_presets AS sp
SET squad_id = s.id
FROM squads AS s
WHERE sp.squad_id IS NULL
    AND sp.chatters_id IS NOT NULL
    AND s.chatters_id = sp.chatters_id;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
            AND table_name = 'schedules_presets'
            AND column_name = 'game'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
            AND table_name = 'schedules_presets'
            AND column_name = 'game_id'
    ) THEN
        ALTER TABLE schedules_presets RENAME COLUMN game TO game_id;
    END IF;
END $$;

ALTER TABLE schedules_presets
    ADD COLUMN IF NOT EXISTS game_id INT REFERENCES games(id) ON DELETE SET NULL;

ALTER TABLE schedules_presets
    ALTER COLUMN game_id DROP NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
            AND table_name = 'schedules_presets'
            AND column_name = 'game_name'
    ) THEN
        INSERT INTO games (title)
        SELECT DISTINCT TRIM(sp.game_name)
        FROM schedules_presets AS sp
        WHERE sp.game_name IS NOT NULL
            AND TRIM(sp.game_name) <> ''
        ON CONFLICT (title) DO NOTHING;

        UPDATE schedules_presets AS sp
        SET game_id = g.id
        FROM games AS g
        WHERE sp.game_id IS NULL
            AND sp.game_name IS NOT NULL
            AND g.title = TRIM(sp.game_name);

        ALTER TABLE schedules_presets DROP COLUMN game_name;
    END IF;
END $$;

ALTER TABLE schedules_presets DROP COLUMN IF EXISTS game_name;

CREATE INDEX IF NOT EXISTS idx_schedules_presets_game_id ON schedules_presets (game_id);

-- squads & players: JSON list of game ids
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
            AND table_name = 'squads'
            AND column_name = 'games'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
            AND table_name = 'squads'
            AND column_name = 'games_ids'
    ) THEN
        ALTER TABLE squads RENAME COLUMN games TO games_ids;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
            AND table_name = 'players'
            AND column_name = 'games'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
            AND table_name = 'players'
            AND column_name = 'games_ids'
    ) THEN
        ALTER TABLE players RENAME COLUMN games TO games_ids;
    END IF;
END $$;

ALTER TABLE squads
    ADD COLUMN IF NOT EXISTS games_ids JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE players
    ADD COLUMN IF NOT EXISTS games_ids JSONB NOT NULL DEFAULT '[]'::jsonb;
