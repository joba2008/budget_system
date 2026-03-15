-- ============================================================
-- CSV 导入脚本：sample.csv -> bsa_* tables
-- 使用方式：
--   psql 命令行: psql -U <user> -d <dbname> -f import_csv.sql
--   或在 pgAdmin 中执行（需将 \copy 改为 COPY，见注释说明）
-- ============================================================

BEGIN;

-- ============================================================
-- STEP 1: 建立临时 staging 表（含 row_id 用于后续关联）
-- ============================================================
CREATE TEMP TABLE temp_csv (
    row_id SERIAL,
    version VARCHAR(50),
    data_type VARCHAR(50),
    under_ops_control VARCHAR(10),
    ccgl VARCHAR(50),
    glc VARCHAR(50),
    cc VARCHAR(50),
    non_controllable VARCHAR(50),
    area VARCHAR(50),
    dept VARCHAR(50),
    dept_group VARCHAR(50),
    dept_ppt VARCHAR(300),
    category VARCHAR(100),
    discretionary VARCHAR(50),
    at_var NUMERIC(18,4),
    self_study_var NUMERIC(18,4),
    spends_control VARCHAR(10),
    iecs_view VARCHAR(10),
    levels VARCHAR(300),
    accounts VARCHAR(300),
    budgeter VARCHAR(100),
    baseline_adjustment NUMERIC(18,2),
    -- volume_actual_
    volume_actual_fy26_202509 NUMERIC(18,2),
    volume_actual_fy26_202510 NUMERIC(18,2),
    volume_actual_fy26_202511 NUMERIC(18,2),
    volume_actual_fy26_202512 NUMERIC(18,2),
    -- volume_A1_ (CSV header 大写，COPY 会自动 fold 成小写)
    volume_a1_fy26_202509 NUMERIC(18,2),
    volume_a1_fy26_202510 NUMERIC(18,2),
    volume_a1_fy26_202511 NUMERIC(18,2),
    volume_a1_fy26_202512 NUMERIC(18,2),
    volume_a1_fy26_202601 NUMERIC(18,2),
    volume_a1_fy26_202602 NUMERIC(18,2),
    volume_a1_fy26_202603 NUMERIC(18,2),
    volume_a1_fy26_202604 NUMERIC(18,2),
    volume_a1_fy26_202605 NUMERIC(18,2),
    volume_a1_fy26_202606 NUMERIC(18,2),
    volume_a1_fy26_202607 NUMERIC(18,2),
    volume_a1_fy26_202608 NUMERIC(18,2),
    volume_a1_fy27_202609 NUMERIC(18,2),
    volume_a1_fy27_202610 NUMERIC(18,2),
    volume_a1_fy27_202611 NUMERIC(18,2),
    volume_a1_fy27_202612 NUMERIC(18,2),
    volume_a1_fy27_202701 NUMERIC(18,2),
    volume_a1_fy27_202702 NUMERIC(18,2),
    volume_a1_fy27_202703 NUMERIC(18,2),
    volume_a1_fy27_202704 NUMERIC(18,2),
    volume_a1_fy27_202705 NUMERIC(18,2),
    volume_a1_fy27_202706 NUMERIC(18,2),
    volume_a1_fy27_202707 NUMERIC(18,2),
    volume_a1_fy27_202708 NUMERIC(18,2),
    -- volume_B1_
    volume_b1_fy26_202509 NUMERIC(18,2),
    volume_b1_fy26_202510 NUMERIC(18,2),
    volume_b1_fy26_202511 NUMERIC(18,2),
    volume_b1_fy26_202512 NUMERIC(18,2),
    volume_b1_fy26_202601 NUMERIC(18,2),
    volume_b1_fy26_202602 NUMERIC(18,2),
    volume_b1_fy26_202603 NUMERIC(18,2),
    volume_b1_fy26_202604 NUMERIC(18,2),
    volume_b1_fy26_202605 NUMERIC(18,2),
    volume_b1_fy26_202606 NUMERIC(18,2),
    volume_b1_fy26_202607 NUMERIC(18,2),
    volume_b1_fy26_202608 NUMERIC(18,2),
    volume_b1_fy27_202609 NUMERIC(18,2),
    volume_b1_fy27_202610 NUMERIC(18,2),
    volume_b1_fy27_202611 NUMERIC(18,2),
    volume_b1_fy27_202612 NUMERIC(18,2),
    volume_b1_fy27_202701 NUMERIC(18,2),
    volume_b1_fy27_202702 NUMERIC(18,2),
    volume_b1_fy27_202703 NUMERIC(18,2),
    volume_b1_fy27_202704 NUMERIC(18,2),
    volume_b1_fy27_202705 NUMERIC(18,2),
    volume_b1_fy27_202706 NUMERIC(18,2),
    volume_b1_fy27_202707 NUMERIC(18,2),
    volume_b1_fy27_202708 NUMERIC(18,2),
    -- actual_
    actual_fy26_202509 NUMERIC(18,2),
    actual_fy26_202510 NUMERIC(18,2),
    actual_fy26_202511 NUMERIC(18,2),
    actual_fy26_202512 NUMERIC(18,2),
    -- spending_
    spending_fy26_202601 NUMERIC(18,2),
    spending_fy26_202602 NUMERIC(18,2),
    spending_fy26_202603 NUMERIC(18,2),
    spending_fy26_202604 NUMERIC(18,2),
    spending_fy26_202605 NUMERIC(18,2),
    spending_fy26_202606 NUMERIC(18,2),
    spending_fy26_202607 NUMERIC(18,2),
    spending_fy26_202608 NUMERIC(18,2),
    spending_fy27_202609 NUMERIC(18,2),
    spending_fy27_202610 NUMERIC(18,2),
    spending_fy27_202611 NUMERIC(18,2),
    spending_fy27_202612 NUMERIC(18,2),
    spending_fy27_202701 NUMERIC(18,2),
    spending_fy27_202702 NUMERIC(18,2),
    spending_fy27_202703 NUMERIC(18,2),
    spending_fy27_202704 NUMERIC(18,2),
    spending_fy27_202705 NUMERIC(18,2),
    spending_fy27_202706 NUMERIC(18,2),
    spending_fy27_202707 NUMERIC(18,2),
    spending_fy27_202708 NUMERIC(18,2),
    -- rebase_financeview_
    rebase_financeview_fy26_202512 NUMERIC(18,2),
    rebase_financeview_fy26_202601 NUMERIC(18,2),
    rebase_financeview_fy26_202602 NUMERIC(18,2),
    rebase_financeview_fy26_202603 NUMERIC(18,2),
    rebase_financeview_fy26_202604 NUMERIC(18,2),
    rebase_financeview_fy26_202605 NUMERIC(18,2),
    rebase_financeview_fy26_202606 NUMERIC(18,2),
    rebase_financeview_fy26_202607 NUMERIC(18,2),
    rebase_financeview_fy26_202608 NUMERIC(18,2),
    rebase_financeview_fy27_202609 NUMERIC(18,2),
    rebase_financeview_fy27_202610 NUMERIC(18,2),
    rebase_financeview_fy27_202611 NUMERIC(18,2),
    rebase_financeview_fy27_202612 NUMERIC(18,2),
    rebase_financeview_fy27_202701 NUMERIC(18,2),
    rebase_financeview_fy27_202702 NUMERIC(18,2),
    rebase_financeview_fy27_202703 NUMERIC(18,2),
    rebase_financeview_fy27_202704 NUMERIC(18,2),
    rebase_financeview_fy27_202705 NUMERIC(18,2),
    rebase_financeview_fy27_202706 NUMERIC(18,2),
    rebase_financeview_fy27_202707 NUMERIC(18,2),
    rebase_financeview_fy27_202708 NUMERIC(18,2),
    -- rebase_opsview_
    rebase_opsview_fy26_202512 NUMERIC(18,2),
    rebase_opsview_fy26_202601 NUMERIC(18,2),
    rebase_opsview_fy26_202602 NUMERIC(18,2),
    rebase_opsview_fy26_202603 NUMERIC(18,2),
    rebase_opsview_fy26_202604 NUMERIC(18,2),
    rebase_opsview_fy26_202605 NUMERIC(18,2),
    rebase_opsview_fy26_202606 NUMERIC(18,2),
    rebase_opsview_fy26_202607 NUMERIC(18,2),
    rebase_opsview_fy26_202608 NUMERIC(18,2),
    rebase_opsview_fy27_202609 NUMERIC(18,2),
    rebase_opsview_fy27_202610 NUMERIC(18,2),
    rebase_opsview_fy27_202611 NUMERIC(18,2),
    rebase_opsview_fy27_202612 NUMERIC(18,2),
    rebase_opsview_fy27_202701 NUMERIC(18,2),
    rebase_opsview_fy27_202702 NUMERIC(18,2),
    rebase_opsview_fy27_202703 NUMERIC(18,2),
    rebase_opsview_fy27_202704 NUMERIC(18,2),
    rebase_opsview_fy27_202705 NUMERIC(18,2),
    rebase_opsview_fy27_202706 NUMERIC(18,2),
    rebase_opsview_fy27_202707 NUMERIC(18,2),
    rebase_opsview_fy27_202708 NUMERIC(18,2),
    -- saving_
    saving_fy26_202512 NUMERIC(18,2),
    saving_fy26_202601 NUMERIC(18,2),
    saving_fy26_202602 NUMERIC(18,2),
    saving_fy26_202603 NUMERIC(18,2),
    saving_fy26_202604 NUMERIC(18,2),
    saving_fy26_202605 NUMERIC(18,2),
    saving_fy26_202606 NUMERIC(18,2),
    saving_fy26_202607 NUMERIC(18,2),
    saving_fy26_202608 NUMERIC(18,2),
    saving_fy27_202609 NUMERIC(18,2),
    saving_fy27_202610 NUMERIC(18,2),
    saving_fy27_202611 NUMERIC(18,2),
    saving_fy27_202612 NUMERIC(18,2),
    saving_fy27_202701 NUMERIC(18,2),
    saving_fy27_202702 NUMERIC(18,2),
    saving_fy27_202703 NUMERIC(18,2),
    saving_fy27_202704 NUMERIC(18,2),
    saving_fy27_202705 NUMERIC(18,2),
    saving_fy27_202706 NUMERIC(18,2),
    saving_fy27_202707 NUMERIC(18,2),
    saving_fy27_202708 NUMERIC(18,2),
    -- newadd_
    newadd_fy26_202512 NUMERIC(18,2),
    newadd_fy26_202601 NUMERIC(18,2),
    newadd_fy26_202602 NUMERIC(18,2),
    newadd_fy26_202603 NUMERIC(18,2),
    newadd_fy26_202604 NUMERIC(18,2),
    newadd_fy26_202605 NUMERIC(18,2),
    newadd_fy26_202606 NUMERIC(18,2),
    newadd_fy26_202607 NUMERIC(18,2),
    newadd_fy26_202608 NUMERIC(18,2),
    newadd_fy27_202609 NUMERIC(18,2),
    newadd_fy27_202610 NUMERIC(18,2),
    newadd_fy27_202611 NUMERIC(18,2),
    newadd_fy27_202612 NUMERIC(18,2),
    newadd_fy27_202701 NUMERIC(18,2),
    newadd_fy27_202702 NUMERIC(18,2),
    newadd_fy27_202703 NUMERIC(18,2),
    newadd_fy27_202704 NUMERIC(18,2),
    newadd_fy27_202705 NUMERIC(18,2),
    newadd_fy27_202706 NUMERIC(18,2),
    newadd_fy27_202707 NUMERIC(18,2),
    newadd_fy27_202708 NUMERIC(18,2)
);

-- ============================================================
-- STEP 2: 载入 CSV 到 staging 表
-- 注意：\copy 为 psql 客户端命令（本机执行），路径为客户端路径
--       若使用 pgAdmin 或其他工具，改用：
--       COPY temp_csv (...) FROM 'C:/Users/yangw/Code/py_project/budget_system/sample.csv' WITH (FORMAT csv, HEADER true);
--       且路径必须是 PostgreSQL server 可访问的路径
-- ============================================================
\copy temp_csv (
    version, data_type, under_ops_control, ccgl, glc, cc, non_controllable,
    area, dept, dept_group, dept_ppt, category, discretionary, at_var,
    self_study_var, spends_control, iecs_view, levels, accounts, budgeter,
    baseline_adjustment,
    volume_actual_fy26_202509, volume_actual_fy26_202510,
    volume_actual_fy26_202511, volume_actual_fy26_202512,
    volume_a1_fy26_202509, volume_a1_fy26_202510, volume_a1_fy26_202511, volume_a1_fy26_202512,
    volume_a1_fy26_202601, volume_a1_fy26_202602, volume_a1_fy26_202603, volume_a1_fy26_202604,
    volume_a1_fy26_202605, volume_a1_fy26_202606, volume_a1_fy26_202607, volume_a1_fy26_202608,
    volume_a1_fy27_202609, volume_a1_fy27_202610, volume_a1_fy27_202611, volume_a1_fy27_202612,
    volume_a1_fy27_202701, volume_a1_fy27_202702, volume_a1_fy27_202703, volume_a1_fy27_202704,
    volume_a1_fy27_202705, volume_a1_fy27_202706, volume_a1_fy27_202707, volume_a1_fy27_202708,
    volume_b1_fy26_202509, volume_b1_fy26_202510, volume_b1_fy26_202511, volume_b1_fy26_202512,
    volume_b1_fy26_202601, volume_b1_fy26_202602, volume_b1_fy26_202603, volume_b1_fy26_202604,
    volume_b1_fy26_202605, volume_b1_fy26_202606, volume_b1_fy26_202607, volume_b1_fy26_202608,
    volume_b1_fy27_202609, volume_b1_fy27_202610, volume_b1_fy27_202611, volume_b1_fy27_202612,
    volume_b1_fy27_202701, volume_b1_fy27_202702, volume_b1_fy27_202703, volume_b1_fy27_202704,
    volume_b1_fy27_202705, volume_b1_fy27_202706, volume_b1_fy27_202707, volume_b1_fy27_202708,
    actual_fy26_202509, actual_fy26_202510, actual_fy26_202511, actual_fy26_202512,
    spending_fy26_202601, spending_fy26_202602, spending_fy26_202603, spending_fy26_202604,
    spending_fy26_202605, spending_fy26_202606, spending_fy26_202607, spending_fy26_202608,
    spending_fy27_202609, spending_fy27_202610, spending_fy27_202611, spending_fy27_202612,
    spending_fy27_202701, spending_fy27_202702, spending_fy27_202703, spending_fy27_202704,
    spending_fy27_202705, spending_fy27_202706, spending_fy27_202707, spending_fy27_202708,
    rebase_financeview_fy26_202512,
    rebase_financeview_fy26_202601, rebase_financeview_fy26_202602, rebase_financeview_fy26_202603,
    rebase_financeview_fy26_202604, rebase_financeview_fy26_202605, rebase_financeview_fy26_202606,
    rebase_financeview_fy26_202607, rebase_financeview_fy26_202608,
    rebase_financeview_fy27_202609, rebase_financeview_fy27_202610, rebase_financeview_fy27_202611,
    rebase_financeview_fy27_202612,
    rebase_financeview_fy27_202701, rebase_financeview_fy27_202702, rebase_financeview_fy27_202703,
    rebase_financeview_fy27_202704, rebase_financeview_fy27_202705, rebase_financeview_fy27_202706,
    rebase_financeview_fy27_202707, rebase_financeview_fy27_202708,
    rebase_opsview_fy26_202512,
    rebase_opsview_fy26_202601, rebase_opsview_fy26_202602, rebase_opsview_fy26_202603,
    rebase_opsview_fy26_202604, rebase_opsview_fy26_202605, rebase_opsview_fy26_202606,
    rebase_opsview_fy26_202607, rebase_opsview_fy26_202608,
    rebase_opsview_fy27_202609, rebase_opsview_fy27_202610, rebase_opsview_fy27_202611,
    rebase_opsview_fy27_202612,
    rebase_opsview_fy27_202701, rebase_opsview_fy27_202702, rebase_opsview_fy27_202703,
    rebase_opsview_fy27_202704, rebase_opsview_fy27_202705, rebase_opsview_fy27_202706,
    rebase_opsview_fy27_202707, rebase_opsview_fy27_202708,
    saving_fy26_202512,
    saving_fy26_202601, saving_fy26_202602, saving_fy26_202603, saving_fy26_202604,
    saving_fy26_202605, saving_fy26_202606, saving_fy26_202607, saving_fy26_202608,
    saving_fy27_202609, saving_fy27_202610, saving_fy27_202611, saving_fy27_202612,
    saving_fy27_202701, saving_fy27_202702, saving_fy27_202703, saving_fy27_202704,
    saving_fy27_202705, saving_fy27_202706, saving_fy27_202707, saving_fy27_202708,
    newadd_fy26_202512,
    newadd_fy26_202601, newadd_fy26_202602, newadd_fy26_202603, newadd_fy26_202604,
    newadd_fy26_202605, newadd_fy26_202606, newadd_fy26_202607, newadd_fy26_202608,
    newadd_fy27_202609, newadd_fy27_202610, newadd_fy27_202611, newadd_fy27_202612,
    newadd_fy27_202701, newadd_fy27_202702, newadd_fy27_202703, newadd_fy27_202704,
    newadd_fy27_202705, newadd_fy27_202706, newadd_fy27_202707, newadd_fy27_202708
)
FROM 'C:/Users/yangw/Code/py_project/budget_system/sample.csv'
WITH (FORMAT csv, HEADER true);

-- ============================================================
-- STEP 3: 在 bsa_main 加临时关联栏位，方便 JOIN 回 temp_csv
-- ============================================================
ALTER TABLE bsa_main ADD COLUMN _import_row_id INT;

-- ============================================================
-- STEP 4: 插入主表
-- ============================================================
INSERT INTO bsa_main (
    version, data_type, under_ops_control, ccgl, glc, cc, non_controllable,
    area, dept, dept_group, dept_ppt, category, discretionary,
    at_var, self_study_var, spends_control, iecs_view,
    levels, accounts, budgeter, baseline_adjustment,
    _import_row_id
)
SELECT
    version, data_type, under_ops_control, ccgl, glc, cc, non_controllable,
    area, dept, dept_group, dept_ppt, category, discretionary,
    at_var, self_study_var, spends_control, iecs_view,
    levels, accounts, budgeter, baseline_adjustment,
    row_id
FROM temp_csv;

-- ============================================================
-- STEP 5: 插入子表1 - bsa_volume_actual
-- 使用 CROSS JOIN LATERAL (VALUES ...) 做 unpivot
-- ============================================================
INSERT INTO bsa_volume_actual (main_id, period, value)
SELECT m.id, v.period, v.value
FROM bsa_main m
JOIN temp_csv t ON m._import_row_id = t.row_id
CROSS JOIN LATERAL (VALUES
    ('fy26_202509', t.volume_actual_fy26_202509),
    ('fy26_202510', t.volume_actual_fy26_202510),
    ('fy26_202511', t.volume_actual_fy26_202511),
    ('fy26_202512', t.volume_actual_fy26_202512)
) AS v(period, value)
WHERE v.value IS NOT NULL;

-- ============================================================
-- STEP 6: 插入子表2 - bsa_volume（含 scenario 字段）
-- ============================================================
INSERT INTO bsa_volume (main_id, scenario, period, value)
SELECT m.id, v.scenario, v.period, v.value
FROM bsa_main m
JOIN temp_csv t ON m._import_row_id = t.row_id
CROSS JOIN LATERAL (VALUES
    -- A1
    ('A1', 'fy26_202509', t.volume_a1_fy26_202509),
    ('A1', 'fy26_202510', t.volume_a1_fy26_202510),
    ('A1', 'fy26_202511', t.volume_a1_fy26_202511),
    ('A1', 'fy26_202512', t.volume_a1_fy26_202512),
    ('A1', 'fy26_202601', t.volume_a1_fy26_202601),
    ('A1', 'fy26_202602', t.volume_a1_fy26_202602),
    ('A1', 'fy26_202603', t.volume_a1_fy26_202603),
    ('A1', 'fy26_202604', t.volume_a1_fy26_202604),
    ('A1', 'fy26_202605', t.volume_a1_fy26_202605),
    ('A1', 'fy26_202606', t.volume_a1_fy26_202606),
    ('A1', 'fy26_202607', t.volume_a1_fy26_202607),
    ('A1', 'fy26_202608', t.volume_a1_fy26_202608),
    ('A1', 'fy27_202609', t.volume_a1_fy27_202609),
    ('A1', 'fy27_202610', t.volume_a1_fy27_202610),
    ('A1', 'fy27_202611', t.volume_a1_fy27_202611),
    ('A1', 'fy27_202612', t.volume_a1_fy27_202612),
    ('A1', 'fy27_202701', t.volume_a1_fy27_202701),
    ('A1', 'fy27_202702', t.volume_a1_fy27_202702),
    ('A1', 'fy27_202703', t.volume_a1_fy27_202703),
    ('A1', 'fy27_202704', t.volume_a1_fy27_202704),
    ('A1', 'fy27_202705', t.volume_a1_fy27_202705),
    ('A1', 'fy27_202706', t.volume_a1_fy27_202706),
    ('A1', 'fy27_202707', t.volume_a1_fy27_202707),
    ('A1', 'fy27_202708', t.volume_a1_fy27_202708),
    -- B1
    ('B1', 'fy26_202509', t.volume_b1_fy26_202509),
    ('B1', 'fy26_202510', t.volume_b1_fy26_202510),
    ('B1', 'fy26_202511', t.volume_b1_fy26_202511),
    ('B1', 'fy26_202512', t.volume_b1_fy26_202512),
    ('B1', 'fy26_202601', t.volume_b1_fy26_202601),
    ('B1', 'fy26_202602', t.volume_b1_fy26_202602),
    ('B1', 'fy26_202603', t.volume_b1_fy26_202603),
    ('B1', 'fy26_202604', t.volume_b1_fy26_202604),
    ('B1', 'fy26_202605', t.volume_b1_fy26_202605),
    ('B1', 'fy26_202606', t.volume_b1_fy26_202606),
    ('B1', 'fy26_202607', t.volume_b1_fy26_202607),
    ('B1', 'fy26_202608', t.volume_b1_fy26_202608),
    ('B1', 'fy27_202609', t.volume_b1_fy27_202609),
    ('B1', 'fy27_202610', t.volume_b1_fy27_202610),
    ('B1', 'fy27_202611', t.volume_b1_fy27_202611),
    ('B1', 'fy27_202612', t.volume_b1_fy27_202612),
    ('B1', 'fy27_202701', t.volume_b1_fy27_202701),
    ('B1', 'fy27_202702', t.volume_b1_fy27_202702),
    ('B1', 'fy27_202703', t.volume_b1_fy27_202703),
    ('B1', 'fy27_202704', t.volume_b1_fy27_202704),
    ('B1', 'fy27_202705', t.volume_b1_fy27_202705),
    ('B1', 'fy27_202706', t.volume_b1_fy27_202706),
    ('B1', 'fy27_202707', t.volume_b1_fy27_202707),
    ('B1', 'fy27_202708', t.volume_b1_fy27_202708)
) AS v(scenario, period, value)
WHERE v.value IS NOT NULL;

-- ============================================================
-- STEP 7: 插入子表3 - bsa_actual
-- ============================================================
INSERT INTO bsa_actual (main_id, period, value)
SELECT m.id, v.period, v.value
FROM bsa_main m
JOIN temp_csv t ON m._import_row_id = t.row_id
CROSS JOIN LATERAL (VALUES
    ('fy26_202509', t.actual_fy26_202509),
    ('fy26_202510', t.actual_fy26_202510),
    ('fy26_202511', t.actual_fy26_202511),
    ('fy26_202512', t.actual_fy26_202512)
) AS v(period, value)
WHERE v.value IS NOT NULL;

-- ============================================================
-- STEP 8: 插入子表4 - bsa_spending
-- ============================================================
INSERT INTO bsa_spending (main_id, period, value)
SELECT m.id, v.period, v.value
FROM bsa_main m
JOIN temp_csv t ON m._import_row_id = t.row_id
CROSS JOIN LATERAL (VALUES
    ('fy26_202601', t.spending_fy26_202601),
    ('fy26_202602', t.spending_fy26_202602),
    ('fy26_202603', t.spending_fy26_202603),
    ('fy26_202604', t.spending_fy26_202604),
    ('fy26_202605', t.spending_fy26_202605),
    ('fy26_202606', t.spending_fy26_202606),
    ('fy26_202607', t.spending_fy26_202607),
    ('fy26_202608', t.spending_fy26_202608),
    ('fy27_202609', t.spending_fy27_202609),
    ('fy27_202610', t.spending_fy27_202610),
    ('fy27_202611', t.spending_fy27_202611),
    ('fy27_202612', t.spending_fy27_202612),
    ('fy27_202701', t.spending_fy27_202701),
    ('fy27_202702', t.spending_fy27_202702),
    ('fy27_202703', t.spending_fy27_202703),
    ('fy27_202704', t.spending_fy27_202704),
    ('fy27_202705', t.spending_fy27_202705),
    ('fy27_202706', t.spending_fy27_202706),
    ('fy27_202707', t.spending_fy27_202707),
    ('fy27_202708', t.spending_fy27_202708)
) AS v(period, value)
WHERE v.value IS NOT NULL;

-- ============================================================
-- STEP 9: 插入子表5 - bsa_rebase_financeview
-- ============================================================
INSERT INTO bsa_rebase_financeview (main_id, period, value)
SELECT m.id, v.period, v.value
FROM bsa_main m
JOIN temp_csv t ON m._import_row_id = t.row_id
CROSS JOIN LATERAL (VALUES
    ('fy26_202512', t.rebase_financeview_fy26_202512),
    ('fy26_202601', t.rebase_financeview_fy26_202601),
    ('fy26_202602', t.rebase_financeview_fy26_202602),
    ('fy26_202603', t.rebase_financeview_fy26_202603),
    ('fy26_202604', t.rebase_financeview_fy26_202604),
    ('fy26_202605', t.rebase_financeview_fy26_202605),
    ('fy26_202606', t.rebase_financeview_fy26_202606),
    ('fy26_202607', t.rebase_financeview_fy26_202607),
    ('fy26_202608', t.rebase_financeview_fy26_202608),
    ('fy27_202609', t.rebase_financeview_fy27_202609),
    ('fy27_202610', t.rebase_financeview_fy27_202610),
    ('fy27_202611', t.rebase_financeview_fy27_202611),
    ('fy27_202612', t.rebase_financeview_fy27_202612),
    ('fy27_202701', t.rebase_financeview_fy27_202701),
    ('fy27_202702', t.rebase_financeview_fy27_202702),
    ('fy27_202703', t.rebase_financeview_fy27_202703),
    ('fy27_202704', t.rebase_financeview_fy27_202704),
    ('fy27_202705', t.rebase_financeview_fy27_202705),
    ('fy27_202706', t.rebase_financeview_fy27_202706),
    ('fy27_202707', t.rebase_financeview_fy27_202707),
    ('fy27_202708', t.rebase_financeview_fy27_202708)
) AS v(period, value)
WHERE v.value IS NOT NULL;

-- ============================================================
-- STEP 10: 插入子表6 - bsa_rebase_opsview
-- ============================================================
INSERT INTO bsa_rebase_opsview (main_id, period, value)
SELECT m.id, v.period, v.value
FROM bsa_main m
JOIN temp_csv t ON m._import_row_id = t.row_id
CROSS JOIN LATERAL (VALUES
    ('fy26_202512', t.rebase_opsview_fy26_202512),
    ('fy26_202601', t.rebase_opsview_fy26_202601),
    ('fy26_202602', t.rebase_opsview_fy26_202602),
    ('fy26_202603', t.rebase_opsview_fy26_202603),
    ('fy26_202604', t.rebase_opsview_fy26_202604),
    ('fy26_202605', t.rebase_opsview_fy26_202605),
    ('fy26_202606', t.rebase_opsview_fy26_202606),
    ('fy26_202607', t.rebase_opsview_fy26_202607),
    ('fy26_202608', t.rebase_opsview_fy26_202608),
    ('fy27_202609', t.rebase_opsview_fy27_202609),
    ('fy27_202610', t.rebase_opsview_fy27_202610),
    ('fy27_202611', t.rebase_opsview_fy27_202611),
    ('fy27_202612', t.rebase_opsview_fy27_202612),
    ('fy27_202701', t.rebase_opsview_fy27_202701),
    ('fy27_202702', t.rebase_opsview_fy27_202702),
    ('fy27_202703', t.rebase_opsview_fy27_202703),
    ('fy27_202704', t.rebase_opsview_fy27_202704),
    ('fy27_202705', t.rebase_opsview_fy27_202705),
    ('fy27_202706', t.rebase_opsview_fy27_202706),
    ('fy27_202707', t.rebase_opsview_fy27_202707),
    ('fy27_202708', t.rebase_opsview_fy27_202708)
) AS v(period, value)
WHERE v.value IS NOT NULL;

-- ============================================================
-- STEP 11: 插入子表7 - bsa_saving
-- ============================================================
INSERT INTO bsa_saving (main_id, period, value)
SELECT m.id, v.period, v.value
FROM bsa_main m
JOIN temp_csv t ON m._import_row_id = t.row_id
CROSS JOIN LATERAL (VALUES
    ('fy26_202512', t.saving_fy26_202512),
    ('fy26_202601', t.saving_fy26_202601),
    ('fy26_202602', t.saving_fy26_202602),
    ('fy26_202603', t.saving_fy26_202603),
    ('fy26_202604', t.saving_fy26_202604),
    ('fy26_202605', t.saving_fy26_202605),
    ('fy26_202606', t.saving_fy26_202606),
    ('fy26_202607', t.saving_fy26_202607),
    ('fy26_202608', t.saving_fy26_202608),
    ('fy27_202609', t.saving_fy27_202609),
    ('fy27_202610', t.saving_fy27_202610),
    ('fy27_202611', t.saving_fy27_202611),
    ('fy27_202612', t.saving_fy27_202612),
    ('fy27_202701', t.saving_fy27_202701),
    ('fy27_202702', t.saving_fy27_202702),
    ('fy27_202703', t.saving_fy27_202703),
    ('fy27_202704', t.saving_fy27_202704),
    ('fy27_202705', t.saving_fy27_202705),
    ('fy27_202706', t.saving_fy27_202706),
    ('fy27_202707', t.saving_fy27_202707),
    ('fy27_202708', t.saving_fy27_202708)
) AS v(period, value)
WHERE v.value IS NOT NULL;

-- ============================================================
-- STEP 12: 插入子表8 - bsa_newadd
-- ============================================================
INSERT INTO bsa_newadd (main_id, period, value)
SELECT m.id, v.period, v.value
FROM bsa_main m
JOIN temp_csv t ON m._import_row_id = t.row_id
CROSS JOIN LATERAL (VALUES
    ('fy26_202512', t.newadd_fy26_202512),
    ('fy26_202601', t.newadd_fy26_202601),
    ('fy26_202602', t.newadd_fy26_202602),
    ('fy26_202603', t.newadd_fy26_202603),
    ('fy26_202604', t.newadd_fy26_202604),
    ('fy26_202605', t.newadd_fy26_202605),
    ('fy26_202606', t.newadd_fy26_202606),
    ('fy26_202607', t.newadd_fy26_202607),
    ('fy26_202608', t.newadd_fy26_202608),
    ('fy27_202609', t.newadd_fy27_202609),
    ('fy27_202610', t.newadd_fy27_202610),
    ('fy27_202611', t.newadd_fy27_202611),
    ('fy27_202612', t.newadd_fy27_202612),
    ('fy27_202701', t.newadd_fy27_202701),
    ('fy27_202702', t.newadd_fy27_202702),
    ('fy27_202703', t.newadd_fy27_202703),
    ('fy27_202704', t.newadd_fy27_202704),
    ('fy27_202705', t.newadd_fy27_202705),
    ('fy27_202706', t.newadd_fy27_202706),
    ('fy27_202707', t.newadd_fy27_202707),
    ('fy27_202708', t.newadd_fy27_202708)
) AS v(period, value)
WHERE v.value IS NOT NULL;

-- ============================================================
-- STEP 13: 清理临时栏位与 staging 表
-- ============================================================
ALTER TABLE bsa_main DROP COLUMN _import_row_id;
DROP TABLE temp_csv;

COMMIT;