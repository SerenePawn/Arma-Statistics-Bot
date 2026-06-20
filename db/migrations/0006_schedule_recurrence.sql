ALTER TABLE schedules_presets
    ADD COLUMN IF NOT EXISTS recurrence_type VARCHAR(10) NOT NULL DEFAULT 'weekly';

ALTER TABLE schedules_presets
    DROP CONSTRAINT IF EXISTS schedules_presets_recurrence_type_check;

ALTER TABLE schedules_presets
    ADD CONSTRAINT schedules_presets_recurrence_type_check
    CHECK (recurrence_type IN ('weekly', 'monthly', 'once'));

ALTER TABLE schedules_presets
    ADD COLUMN IF NOT EXISTS recurrence_date DATE;

ALTER TABLE schedules_presets
    ADD COLUMN IF NOT EXISTS day_of_month INT;

ALTER TABLE schedules_presets
    DROP CONSTRAINT IF EXISTS schedules_presets_day_of_month_check;

ALTER TABLE schedules_presets
    ADD CONSTRAINT schedules_presets_day_of_month_check
    CHECK (day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 31));
