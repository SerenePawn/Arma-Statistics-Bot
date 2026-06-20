ALTER TABLE squads
    ADD COLUMN IF NOT EXISTS friends_ids JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS squad_requests (
    id SERIAL PRIMARY KEY,
    squad_id INT NOT NULL REFERENCES squads(id) ON DELETE CASCADE,
    telegram_id INT NOT NULL,
    player_id INT NOT NULL REFERENCES players(id),
    request_type VARCHAR(10) NOT NULL CHECK (request_type IN ('join', 'friend')),
    status VARCHAR(10) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'rejected', 'blocked', 'unblocked')),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS squad_requests_pending_uidx
    ON squad_requests (squad_id, telegram_id)
    WHERE status = 'pending';
