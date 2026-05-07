-- 一次性清理 game_mechanics 標籤資料
-- 修復 list("multi_zone") 拆字元 + parsedTags 維度混淆 + bingo_card 同義合併

BEGIN;

-- ============================================
-- 1. 修復 layoutTags 拆字元 bug
-- ============================================
-- 字元陣列 ["m","u","l","t","i","_","z","o","n","e"] -> ["multi_zone"]
UPDATE game_mechanics
SET "layoutTags" = '["multi_zone"]'::jsonb
WHERE "layoutTags"::text LIKE '[%"m"%"u"%"l"%"t"%"i"%';

-- ["s","i","n","g","l","e","_","z","o","n","e"] -> ["single_zone"]
UPDATE game_mechanics
SET "layoutTags" = '["single_zone"]'::jsonb
WHERE "layoutTags"::text LIKE '[%"s"%"i"%"n"%"g"%"l"%"e"%';

-- ["f","u","l","l","_","b","o","a","r","d"] -> ["full_board"]
UPDATE game_mechanics
SET "layoutTags" = '["full_board"]'::jsonb
WHERE "layoutTags"::text LIKE '[%"f"%"u"%"l"%"l"%"_"%"b"%';

-- ============================================
-- 2. parsedTags: 移除維度錯置的 tag (應出現在 layoutTags / resultSpeed)
-- ============================================
UPDATE game_mechanics
SET "parsedTags" = (
  SELECT jsonb_agg(t)
  FROM jsonb_array_elements_text("parsedTags"::jsonb) AS t
  WHERE t NOT IN (
    'multi_zone', 'single_zone', 'full_board',  -- layoutTags 維度
    'instant', 'multi_step', 'compare', 'sequence'  -- resultSpeed 維度
  )
)
WHERE "parsedTags" IS NOT NULL
  AND "parsedTags"::jsonb @> ANY(ARRAY[
    '["multi_zone"]'::jsonb, '["single_zone"]'::jsonb, '["full_board"]'::jsonb,
    '["instant"]'::jsonb, '["multi_step"]'::jsonb, '["compare"]'::jsonb, '["sequence"]'::jsonb
  ]);

-- ============================================
-- 3. 同義詞合併: bingo_card -> bingo_line (parsedTags + mechanicTypes)
-- ============================================
UPDATE game_mechanics
SET "parsedTags" = (
  SELECT jsonb_agg(DISTINCT CASE WHEN t = 'bingo_card' THEN 'bingo_line' ELSE t END)
  FROM jsonb_array_elements_text("parsedTags"::jsonb) AS t
)
WHERE "parsedTags"::jsonb @> '["bingo_card"]'::jsonb;

UPDATE game_mechanics
SET "mechanicTypes" = (
  SELECT jsonb_agg(DISTINCT CASE WHEN t = 'bingo_card' THEN 'bingo_line' ELSE t END)
  FROM jsonb_array_elements_text("mechanicTypes"::jsonb) AS t
)
WHERE "mechanicTypes"::jsonb @> '["bingo_card"]'::jsonb;

-- ============================================
-- 驗證
-- ============================================
SELECT '== layoutTags 統計（清理後）==' AS check_step;
SELECT tag, COUNT(*) AS cnt FROM (
  SELECT jsonb_array_elements_text("layoutTags"::jsonb) AS tag
  FROM game_mechanics WHERE "layoutTags" IS NOT NULL
) t GROUP BY tag ORDER BY cnt DESC;

SELECT '== parsedTags 含維度錯置 (應 0)==' AS check_step;
SELECT COUNT(*) FROM game_mechanics
WHERE "parsedTags"::jsonb @> ANY(ARRAY[
  '["multi_zone"]'::jsonb, '["instant"]'::jsonb, '["sequence"]'::jsonb
]);

SELECT '== bingo_card 殘留 (應 0)==' AS check_step;
SELECT COUNT(*) FROM game_mechanics
WHERE "parsedTags"::jsonb @> '["bingo_card"]'::jsonb
   OR "mechanicTypes"::jsonb @> '["bingo_card"]'::jsonb;

COMMIT;
