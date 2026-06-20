-- Remove duplicate player rows per telegram_id, keep the latest
DELETE FROM players p
WHERE p.id NOT IN (
    SELECT MAX(p2.id)
    FROM players p2
    GROUP BY p2.telegram_id, p2.squad_id
);

CREATE UNIQUE INDEX IF NOT EXISTS players_telegram_squad_uidx
    ON players (telegram_id, squad_id);

CREATE TABLE user_preferences (
    telegram_id INTEGER PRIMARY KEY,
    primary_squad_id INTEGER REFERENCES squads(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO user_preferences (telegram_id, primary_squad_id)
SELECT telegram_id, squad_id
FROM players
WHERE squad_id IS NOT NULL
ON CONFLICT (telegram_id) DO NOTHING;
