ALTER TABLE squads
    ADD COLUMN IF NOT EXISTS main_game_ids JSONB NOT NULL DEFAULT '[]'::jsonb;
