-- 修補 resultSpeed 維度錯置 (multi_zone 是 layoutTags 維度,不該出現在 resultSpeed)

BEGIN;

-- multi_zone 在 resultSpeed 場景 -> 用 multi_step (語意接近: 多區依序判讀 = 多步驟)
UPDATE game_mechanics
SET "resultSpeed" = 'multi_step'
WHERE "resultSpeed" = 'multi_zone';

-- 驗證
SELECT '== resultSpeed 統計 (清理後) ==' AS check_step;
SELECT "resultSpeed" AS tag, COUNT(*) AS cnt
FROM game_mechanics
WHERE "resultSpeed" IS NOT NULL AND "resultSpeed" <> ''
GROUP BY "resultSpeed" ORDER BY cnt DESC;

SELECT '== resultSpeed multi_zone 殘留 (應 0) ==' AS check_step;
SELECT COUNT(*) FROM game_mechanics WHERE "resultSpeed" = 'multi_zone';

COMMIT;
