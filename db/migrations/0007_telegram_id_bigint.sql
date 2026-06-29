-- Telegram user IDs can exceed signed int32 (2_147_483_647).
ALTER TABLE players ALTER COLUMN telegram_id TYPE BIGINT;
ALTER TABLE user_preferences ALTER COLUMN telegram_id TYPE BIGINT;
ALTER TABLE bug_reports ALTER COLUMN telegram_id TYPE BIGINT;
ALTER TABLE notifications ALTER COLUMN telegram_id TYPE BIGINT;
ALTER TABLE usage_statistics ALTER COLUMN telegram_id TYPE BIGINT;
ALTER TABLE squad_requests ALTER COLUMN telegram_id TYPE BIGINT;
