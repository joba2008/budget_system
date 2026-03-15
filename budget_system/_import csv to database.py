#!/usr/bin/env python3
"""
import_csv.py
将 sample.csv 的数据导入到 bsa_* PostgreSQL tables。

注意：此脚本仅支持 PostgreSQL（使用 psycopg2 + RETURNING 语法）。
      MSSQL 环境请使用 Web 界面的导入功能（apps/importer）。

使用方式:
    python import_csv.py
    python import_csv.py --csv /path/to/file.csv --dbname mydb --user postgres

也可用环境变量设定 DB 连线参数:
    DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD
"""

import argparse
import csv
import logging
import os
import sys
from decimal import Decimal, InvalidOperation

import psycopg2
from psycopg2.extras import execute_values

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── DB 连线预设值（可被 CLI 参数或环境变量覆盖）─────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "192.168.56.101"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME", "budget_system"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "0000"),
}

# ── 主表固定栏位 ────────────────────────────────────────────────────────────────
MAIN_COLS = [
    "version", "data_type", "under_ops_control", "ccgl", "glc", "cc",
    "non_controllable", "area", "dept", "dept_group", "dept_ppt", "category",
    "discretionary", "at_var", "self_study_var", "spends_control", "iecs_view",
    "levels", "accounts", "budgeter", "baseline_adjustment",
]
NUMERIC_MAIN_COLS = {"at_var", "self_study_var", "baseline_adjustment"}

# ── 子表 prefix 对应表（不含 bsa_volume，因为它需要额外的 scenario 栏位）──────────
SIMPLE_SUB_TABLES: list[tuple[str, str]] = [
    ("bsa_actual",            "actual_"),
    ("bsa_spending",          "spending_"),
    ("bsa_rebase_financeview", "rebase_financeview_"),
    ("bsa_rebase_opsview",    "rebase_opsview_"),
    ("bsa_saving",            "saving_"),
    ("bsa_newadd",            "newadd_"),
]


# ── 工具函数 ───────────────────────────────────────────────────────────────────

def to_none(val: str | None) -> str | None:
    """空字串转 None（对应 DB NULL）。"""
    return None if (val is None or val == "") else val


def to_decimal(val: str | None) -> Decimal | None:
    """字串转 Decimal，空值/无效值回传 None。"""
    if val is None or val.strip() == "":
        return None
    try:
        return Decimal(val)
    except InvalidOperation:
        return None


def categorize_columns(headers: list[str]) -> dict[str, list[str]]:
    """
    将 CSV header 依前缀分配到各子表 group。
    回传 dict，key 为 table name，value 为属于该表的 column 名称列表。
    """
    groups: dict[str, list[str]] = {
        "bsa_volume_actual":       [],
        "bsa_volume":              [],
        "bsa_actual":              [],
        "bsa_spending":            [],
        "bsa_rebase_financeview":  [],
        "bsa_rebase_opsview":      [],
        "bsa_saving":              [],
        "bsa_newadd":              [],
    }
    for h in headers:
        hl = h.lower()
        if hl.startswith("volume_actual_"):
            groups["bsa_volume_actual"].append(h)
        elif hl.startswith("volume_"):
            groups["bsa_volume"].append(h)
        elif hl.startswith("actual_"):
            groups["bsa_actual"].append(h)
        elif hl.startswith("spending_"):
            groups["bsa_spending"].append(h)
        elif hl.startswith("rebase_financeview_"):
            groups["bsa_rebase_financeview"].append(h)
        elif hl.startswith("rebase_opsview_"):
            groups["bsa_rebase_opsview"].append(h)
        elif hl.startswith("saving_"):
            groups["bsa_saving"].append(h)
        elif hl.startswith("newadd_"):
            groups["bsa_newadd"].append(h)
    return groups


def parse_volume_scenario_period(col: str) -> tuple[str, str]:
    """
    从 volume 子表栏位名称中解析 scenario 与 period。
    例：'volume_A1_fy26_202509' → ('A1', 'fy26_202509')
    """
    tail = col[len("volume_"):]       # 'A1_fy26_202509'
    sep = tail.index("_")
    return tail[:sep], tail[sep + 1:]  # scenario, period


# ── 主要 import 逻辑 ───────────────────────────────────────────────────────────

def import_csv(csv_path: str, db_config: dict) -> None:
    # ── 1. 读取 CSV ────────────────────────────────────────────────────────────
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        rows = list(reader)

    if not rows:
        logger.warning("CSV 档案无资料，略过导入。")
        return

    col_groups = categorize_columns(headers)

    logger.info(f"读取 {len(rows)} 笔资料，来源: {csv_path}")
    logger.info("栏位分布: " + ", ".join(
        f"{k}({len(v)}栏)" for k, v in col_groups.items()
    ))

    # ── 2. 建立连线并在单一 transaction 内完成所有写入 ──────────────────────────
    conn = psycopg2.connect(**db_config)
    try:
        with conn:  # commit on success / rollback on exception
            with conn.cursor() as cur:

                # 各子表的 row 暂存区
                sub: dict[str, list] = {k: [] for k in col_groups}

                main_insert_sql = (
                    f"INSERT INTO bsa_main ({', '.join(MAIN_COLS)}) "
                    f"VALUES ({', '.join(['%s'] * len(MAIN_COLS))}) "
                    f"RETURNING id"
                )

                # ── 3. 逐行处理：insert 主表取得 id，再收集子表资料 ────────────
                for i, row in enumerate(rows):
                    # 主表栏位值
                    main_vals = [
                        to_decimal(row.get(c, "")) if c in NUMERIC_MAIN_COLS
                        else to_none(row.get(c, ""))
                        for c in MAIN_COLS
                    ]
                    cur.execute(main_insert_sql, main_vals)
                    main_id: int = cur.fetchone()[0]

                    # bsa_volume_actual — (main_id, period, value)
                    for col in col_groups["bsa_volume_actual"]:
                        v = to_decimal(row[col])
                        if v is not None:
                            period = col[len("volume_actual_"):]
                            sub["bsa_volume_actual"].append((main_id, period, v))

                    # bsa_volume — (main_id, scenario, period, value)
                    for col in col_groups["bsa_volume"]:
                        v = to_decimal(row[col])
                        if v is not None:
                            scenario, period = parse_volume_scenario_period(col)
                            sub["bsa_volume"].append((main_id, scenario, period, v))

                    # 其余子表 — (main_id, period, value)
                    for table, prefix in SIMPLE_SUB_TABLES:
                        for col in col_groups[table]:
                            v = to_decimal(row[col])
                            if v is not None:
                                period = col[len(prefix):]
                                sub[table].append((main_id, period, v))

                    if (i + 1) % 500 == 0:
                        logger.info(f"  主表进度: {i + 1}/{len(rows)} 笔")

                logger.info(f"  主表进度: {len(rows)}/{len(rows)} 笔 (完成)")

                # ── 4. 批量写入各子表 ─────────────────────────────────────────
                _bulk_insert(cur, "bsa_volume_actual",
                             "INSERT INTO bsa_volume_actual (main_id, period, value) VALUES %s",
                             sub["bsa_volume_actual"])

                _bulk_insert(cur, "bsa_volume",
                             "INSERT INTO bsa_volume (main_id, scenario, period, value) VALUES %s",
                             sub["bsa_volume"])

                for table, _ in SIMPLE_SUB_TABLES:
                    _bulk_insert(cur, table,
                                 f"INSERT INTO {table} (main_id, period, value) VALUES %s",
                                 sub[table])

        logger.info("导入完成。")

    except Exception:
        logger.exception("导入失败，transaction 已 rollback。")
        raise
    finally:
        conn.close()


def _bulk_insert(cur, table_name: str, sql: str, data: list) -> None:
    """执行 execute_values 并记录写入笔数，空列表则略过。"""
    if not data:
        logger.info(f"  {table_name}: 0 笔 (略过)")
        return
    execute_values(cur, sql, data, page_size=1000)
    logger.info(f"  {table_name}: 写入 {len(data)} 笔")


# # ── Export（DB → CSV 格式）────────────────────────────────────────────────────

# def _group_sub_rows(rows: list[tuple]) -> dict[int, dict[str, Decimal]]:
#     """
#     将 (main_id, period, value) 的 rows 整理成
#     {main_id: {period: value}}
#     """
#     result: dict[int, dict] = {}
#     for main_id, period, value in rows:
#         result.setdefault(main_id, {})[period] = value
#     return result


# def _sorted_periods(grouped: dict) -> list[str]:
#     """从 {main_id: {period: value}} 中收集并排序所有 period。"""
#     all_periods = {p for d in grouped.values() for p in d}
#     return sorted(all_periods)


# def _fmt(val) -> str:
#     """
#     将 DB 取出的值转为 CSV 字串。
#     Decimal 使用 normalize 去除尾部零，再用 'f' 格式避免科学记号。
#     """
#     if val is None:
#         return ""
#     if isinstance(val, Decimal):
#         return format(val.normalize(), "f")
#     return str(val)


# def export_csv(db_config: dict, output_path: str | None = None) -> None:
#     """
#     从所有 bsa_* tables 读取资料，还原成与原始 CSV 相同的格式。

#     output_path: 输出 CSV 档案路径；若为 None 则输出到 stdout。
#     """
#     conn = psycopg2.connect(**db_config)
#     try:
#         with conn.cursor() as cur:

#             # ── 1. 主表 ────────────────────────────────────────────────────────
#             cur.execute(f"SELECT id, {', '.join(MAIN_COLS)} FROM bsa_main ORDER BY id")
#             main_rows = cur.fetchall()
#             if not main_rows:
#                 logger.warning("bsa_main 无资料。")
#                 return
#             # {main_id: {col: value}}
#             main_data: dict[int, dict] = {
#                 row[0]: dict(zip(MAIN_COLS, row[1:]))
#                 for row in main_rows
#             }
#             main_ids_ordered = [row[0] for row in main_rows]

#             # ── 2. bsa_volume_actual ───────────────────────────────────────────
#             cur.execute(
#                 "SELECT main_id, period, value FROM bsa_volume_actual ORDER BY main_id, period"
#             )
#             va_grouped = _group_sub_rows(cur.fetchall())
#             va_periods = _sorted_periods(va_grouped)

#             # ── 3. bsa_volume（含 scenario）────────────────────────────────────
#             cur.execute(
#                 "SELECT main_id, scenario, period, value FROM bsa_volume "
#                 "ORDER BY main_id, scenario, period"
#             )
#             v_grouped: dict[int, dict[tuple[str, str], Decimal]] = {}
#             for main_id, scenario, period, value in cur.fetchall():
#                 v_grouped.setdefault(main_id, {})[(scenario, period)] = value
#             # 收集所有 (scenario, period) 组合并排序（A1 先、B1 后，period 升序）
#             all_scenario_periods = sorted(
#                 {sp for d in v_grouped.values() for sp in d},
#                 key=lambda x: (x[0], x[1]),
#             )

#             # ── 4. 其余简单子表 ────────────────────────────────────────────────
#             simple_grouped: dict[str, dict] = {}
#             simple_periods: dict[str, list[str]] = {}
#             for table, _ in SIMPLE_SUB_TABLES:
#                 cur.execute(
#                     f"SELECT main_id, period, value FROM {table} ORDER BY main_id, period"
#                 )
#                 simple_grouped[table] = _group_sub_rows(cur.fetchall())
#                 simple_periods[table] = _sorted_periods(simple_grouped[table])

#     finally:
#         conn.close()

#     # ── 5. 组合 CSV headers（顺序与原始 CSV 一致）────────────────────────────
#     headers: list[str] = list(MAIN_COLS)
#     headers += [f"volume_actual_{p}" for p in va_periods]
#     headers += [f"volume_{s}_{p}" for s, p in all_scenario_periods]
#     for table, prefix in SIMPLE_SUB_TABLES:
#         headers += [f"{prefix}{p}" for p in simple_periods[table]]

#     # ── 6. 组合每一笔资料 ──────────────────────────────────────────────────────
#     result_rows: list[dict] = []
#     for main_id in main_ids_ordered:
#         flat: dict[str, str] = {c: _fmt(main_data[main_id].get(c)) for c in MAIN_COLS}

#         for p in va_periods:
#             flat[f"volume_actual_{p}"] = _fmt(va_grouped.get(main_id, {}).get(p))

#         for s, p in all_scenario_periods:
#             flat[f"volume_{s}_{p}"] = _fmt(v_grouped.get(main_id, {}).get((s, p)))

#         for table, prefix in SIMPLE_SUB_TABLES:
#             for p in simple_periods[table]:
#                 flat[f"{prefix}{p}"] = _fmt(simple_grouped[table].get(main_id, {}).get(p))

#         result_rows.append(flat)

#     # ── 7. 写出 CSV ────────────────────────────────────────────────────────────
#     if output_path:
#         out = open(output_path, "w", newline="", encoding="utf-8")
#         close_out = True
#     else:
#         out = sys.stdout
#         close_out = False

#     try:
#         writer = csv.DictWriter(out, fieldnames=headers, extrasaction="ignore")
#         writer.writeheader()
#         writer.writerows(result_rows)
#     finally:
#         if close_out:
#             out.close()

#     dest = output_path or "stdout"
#     logger.info(f"已输出 {len(result_rows)} 笔资料，{len(headers)} 个栏位 → {dest}")


# # ── CLI 入口 ───────────────────────────────────────────────────────────────────

# def parse_args() -> argparse.Namespace:
#     script_dir = os.path.dirname(os.path.abspath(__file__))
#     default_csv = os.path.join(script_dir, "sample.csv")

#     parser = argparse.ArgumentParser(
#         description="将 sample.csv 导入 bsa_* PostgreSQL tables，或从 DB 汇出为 CSV"
#     )
#     parser.add_argument("--csv",      default=default_csv,          help="导入用 CSV 档案路径")
#     parser.add_argument("--host",     default=DB_CONFIG["host"],     help="DB host")
#     parser.add_argument("--port",     default=DB_CONFIG["port"],     type=int, help="DB port")
#     parser.add_argument("--dbname",   default=DB_CONFIG["dbname"],   help="DB 名称")
#     parser.add_argument("--user",     default=DB_CONFIG["user"],     help="DB 使用者")
#     parser.add_argument("--password", default=DB_CONFIG["password"], help="DB 密码")
#     parser.add_argument(
#         "--export",
#         metavar="OUTPUT_CSV",
#         nargs="?",          # 0 或 1 个参数：不给路径则输出到 stdout
#         const="",           # --export 但没给路径时的标记
#         default=None,       # 未使用 --export 时为 None
#         help="从 DB 汇出资料为 CSV（不指定路径则输出到 stdout）",
#     )
#     return parser.parse_args()


# if __name__ == "__main__":
#     args = parse_args()

#     cfg = {
#         "host":     args.host,
#         "port":     args.port,
#         "dbname":   args.dbname,
#         "user":     args.user,
#         "password": args.password,
#     }

#     if args.export is not None:
#         # --export 模式：从 DB 汇出
#         output = args.export if args.export != "" else None
#         export_csv(cfg, output_path=output)
#     else:
#         # 预设模式：导入 CSV
#         if not os.path.exists(args.csv):
#             logger.error(f"找不到 CSV 档案: {args.csv}")
#             sys.exit(1)
#         import_csv(args.csv, cfg)