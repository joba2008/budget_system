# BSA 部门预算管理系统 - 需求与系统架构文档

## 1. 项目概述

### 1.1 项目名称
BSA (Budget Spending Analysis) 部门预算管理系统

### 1.2 项目背景
当前部门预算数据通过 CSV 文件手工管理，经 Python 脚本/SQL 导入 PostgreSQL 数据库。需要建设一套 Web 端预算管理系统，实现预算编制、追踪、分析的全流程线上化，取代手工 CSV 流转方式。

### 1.3 技术栈
| 层级 | 技术选型 |
|------|----------|
| 后端框架 | Django 4.x (Python) |
| 数据库 | PostgreSQL 15+ / SQL Server 2019+ (双数据库支持) |
| 前端 | Django Templates + HTML5 + CSS3 + JavaScript |
| UI 风格 | Neo Brutalism (新粗野主义) — 见 3.9 UI 设计规范 |
| CSS 框架 | 自定义 CSS (基于 Neo Brutalism 设计语言，不使用 Bootstrap) |
| 图表 | ECharts (支持瀑布图、组合图等复杂图表) |
| 数据表格 | DataTables.js (支持列冻结、排序、筛选) |
| 导入/导出 | pandas + openpyxl (Excel) / csv 标准库 |
| 认证 | Django 内建 Auth + LDAP (可选对接企业 AD) + `bsa_permission` 表权限校验 |

---

## 2. 现有数据模型分析

根据 `_import csv to database.py`、`import_csv.sql`、`_sql to query.txt` 的分析，现有数据库结构如下：

### 2.1 主表 `bsa_main`
存储每一条预算明细行的维度/属性信息：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | 主键 |
| version | VARCHAR(50) | 预算版本 (如 `fy26-B1`) |
| data_type | VARCHAR(50) | 数据类型 (如 `Data`) |
| under_ops_control | VARCHAR(10) | 是否受运营控制 (Y/N) |
| ccgl | VARCHAR(50) | 成本中心 GL 组合码 |
| glc | VARCHAR(50) | 总账科目代码 (如 `515100`) |
| cc | VARCHAR(50) | 成本中心代码 (如 `692225`) |
| non_controllable | VARCHAR(50) | 不可控项标识 |
| area | VARCHAR(50) | 区域 (如 `MOD`) |
| dept | VARCHAR(50) | 部门 (如 `MFG`) |
| dept_group | VARCHAR(50) | 部门组 (如 `MFG`) |
| dept_ppt | VARCHAR(300) | 部门 PPT 展示名称 |
| category | VARCHAR(100) | 费用类别 (如 `Indirect Labor`) |
| discretionary | VARCHAR(50) | 可自由裁量标识 |
| at_var | NUMERIC(18,4) | AT 差异比率 (如 0.05) |
| self_study_var | NUMERIC(18,4) | 自研差异比率 |
| spends_control | VARCHAR(10) | 支出控制标识 (Y/N) |
| iecs_view | VARCHAR(10) | IECS 视图标识 (Y/N) |
| levels | VARCHAR(300) | 层级描述 |
| accounts | VARCHAR(300) | 科目描述 |
| budgeter | VARCHAR(100) | 预算编制人 (邮箱) |
| baseline_adjustment | NUMERIC(18,2) | 基线调整值 |

### 2.2 子表（时间序列数据，按 period 行存储）
所有子表通过 `main_id` 外键关联主表，数据结构为 EAV (Entity-Attribute-Value) 行存储模式：

| 子表名 | 字段 | 说明 |
|--------|------|------|
| `bsa_volume_actual` | main_id, period, value | 产量实际值 (4 个月: 202509-202512) |
| `bsa_volume` | main_id, **scenario**, period, value | 产量预测 (分 A1/B1 两个场景, 各 24 个月) |
| `bsa_actual` | main_id, period, value | 费用实际值 (4 个月) |
| `bsa_spending` | main_id, period, value | 支出计划 (20 个月: 202601-202708) |
| `bsa_rebase_financeview` | main_id, period, value | 重定基准-财务视图 (21 个月) |
| `bsa_rebase_opsview` | main_id, period, value | 重定基准-运营视图 (21 个月) |
| `bsa_saving` | main_id, period, value | 节约金额 (21 个月) |
| `bsa_newadd` | main_id, period, value | 新增项目金额 (21 个月) |

### 2.3 Period 格式
`fyXX_YYYYMM`，例如 `fy26_202509` 表示 FY26 财年中 2025 年 9 月的数据。财年周期为 9 月至次年 8 月。

---

## 3. 功能需求

### 3.1 用户与权限管理

| 角色 | 权限 |
|------|------|
| **系统管理员** (Admin) | 用户管理、角色分配、系统配置、数据导入导出、版本管理、创建预算版本、查看全部门报表、Rebase 操作、查看各部门提交状态 |
| **部门预算员** (Budgeter) | 编制本部门预算（Spending/Saving/NewAdd）、标记编制完成 |
| **只读查看者** (Viewer) | 查看报表和仪表盘，不可编辑 |

- 预算员只能看到和编辑自己负责的成本中心数据（按 `budgeter` 字段过滤）
- 支持 LDAP/AD 集成进行统一认证

#### 3.1.1 登录权限校验 (`bsa_permission` 表)

用户登录时，系统必须查询 `bsa_permission` 表验证该用户是否具有系统访问权限及对应角色。

**表结构**：

```sql
CREATE TABLE bsa_permission (
    id SERIAL PRIMARY KEY,
    user_mail TEXT NOT NULL,
    user_role TEXT NOT NULL,
    CONSTRAINT uq_user_role UNIQUE (user_mail, user_role)
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | SERIAL PK | 主键 |
| `user_mail` | TEXT | 用户邮箱前缀（如 `yuchunwei`），与登录用户名匹配 |
| `user_role` | TEXT | 用户角色（`admin` / `budgeter` / `viewer`） |

**登录校验流程**：

```
用户输入用户名/密码
    │
    ▼
Django Auth 验证凭据 (或 LDAP 认证)
    │
    ├─ [认证失败] → 返回登录页，提示"用户名或密码错误"
    │
    ▼ [认证成功]
查询 bsa_permission 表:
  SELECT user_role FROM bsa_permission WHERE user_mail = <登录用户名>
    │
    ├─ [无记录] → 拒绝登录，提示"您没有系统访问权限，请联系管理员"
    │
    ▼ [有记录]
将查询到的 user_role 写入 session，用户进入系统
    │
    ▼
根据 user_role 控制菜单可见性与功能权限 (参考 3.1 角色权限表)
```

**角色映射关系**：

| `bsa_permission.user_role` | 系统角色 | 说明 |
|---------------------------|---------|------|
| `admin` | 系统管理员 (Admin) | 完全权限（含版本管理、Rebase 编辑、查看全部门、提交状态看板等） |
| `budgeter` | 部门预算员 (Budgeter) | 编制本部门预算 |
| `viewer` | 只读查看者 (Viewer) | 仅查看 |

**注意事项**：
- 同一用户可在 `bsa_permission` 中拥有多条记录（多个角色），系统取最高权限角色生效
- 角色优先级：`admin` > `budgeter` > `viewer`
- 管理员可通过 Django Admin 或系统管理页面维护 `bsa_permission` 表
- `user_mail` 字段存储的是邮箱前缀（不含 `@domain`），需与登录用户名一致

### 3.2 预算版本管理

- **创建版本**: 新建预算周期版本（如 `fy27-A1`, `fy27-B1`）
- **版本状态**: Draft → In Progress → Completed → Locked
- **版本复制**: 基于已有版本创建新版本（继承数据）
- **版本对比**: 两个版本间的差异比较

### 3.3 数据导入

#### 3.3.1 CSV 模板下载

每次预算周期开始前，财务同事需要先下载 CSV 模板，填写数据后再上传系统。

**模板格式**：参考 `sample.csv`，表头结构如下：

```
固定维度列 (21列):
  version, data_type, under_ops_control, ccgl, glc, cc, non_controllable,
  area, dept, dept_group, dept_ppt, category, discretionary, at_var,
  self_study_var, spends_control, iecs_view, levels, accounts, budgeter,
  baseline_adjustment

动态数值列 (根据版本场景自动生成):
  volume_actual_*     → 产量实际值 (历史月份)
  volume_{前序场景}_*  → 前序场景产量 (参考值，不可编辑)
  volume_{当前场景}_*  → 当前场景产量 (待填写)
  actual_*            → 费用实际值 (历史月份)
  spending_*          → 支出计划 (待填写)
  rebase_financeview_* → 重定基准-财务视图
  rebase_opsview_*    → 重定基准-运营视图
  saving_*            → 节约金额
  newadd_*            → 新增项目金额
```

**模板下载功能**：
- 路径: `/import/template/download/`
- 用户选择目标版本 (如 `fy27-B1`) 后，系统自动生成对应的 CSV 模板
- 模板中固定维度列为空行（供填写），数值列表头根据版本场景规则自动生成
- 支持带样例数据的模板下载（附 1~2 行示例数据，帮助理解填写格式）

#### 3.3.2 CSV 上传与导入

- **CSV 导入**: 上传 CSV 文件，系统解析并写入数据库（复用现有 `_import csv to database.py` 逻辑）
- **Excel 导入**: 支持 .xlsx 格式
- **导入预览**: 导入前展示数据摘要和校验结果
- **导入日志**: 记录每次导入的时间、操作人、文件名、成功/失败笔数

#### 3.3.3 导入校验规则

上传 CSV 后系统自动执行以下校验，全部通过后才可确认导入：

**基础校验**：
- 必填字段检查 (version, area, dept, cc, glc, accounts, budgeter 不可为空)
- 数值格式检查 (数值列必须为合法数字或空值)
- 成本中心/科目代码有效性检查
- 重复行检测 (同一 version + cc + glc 不应重复)
- `at_var` 字段校验：必须为 0~1 之间的小数 (如 `0.05`)，不接受整数或百分比格式（详见 3.4.6）

**Volume 栏位顺序校验 (核心规则)**：

CSV 中 volume 相关栏位必须严格按照「前序场景 → 当前场景」的顺序排列。系统根据 version 字段中的场景标识 (A1/B1/C1/D1) 自动判断：

| version 含场景 | volume 栏位要求顺序 | 说明 |
|---------------|---------------------|------|
| **B1** | `volume_A1_*` → `volume_B1_*` | A1 为前序，B1 为当前 |
| **C1** | `volume_B1_*` → `volume_C1_*` | B1 为前序，C1 为当前 |
| **D1** | `volume_C1_*` → `volume_D1_*` | C1 为前序，D1 为当前 |
| **A1** | `volume_D1_*` (上一财年) → `volume_A1_*` | D1 为前序(上季度)，A1 为当前 |

> 场景轮转: A1 → B1 → C1 → D1 → A1(下一财年)，每个场景上传时必须携带前一个场景的 volume 数据作为参考基准。

**校验逻辑伪代码**：
```python
SCENARIO_ORDER = {'B1': 'A1', 'C1': 'B1', 'D1': 'C1', 'A1': 'D1'}

def validate_volume_columns(headers: list[str], version: str):
    # 1. 提取 version 中的场景标识
    current_scenario = extract_scenario(version)   # e.g. 'fy26-B1' → 'B1'
    prev_scenario = SCENARIO_ORDER[current_scenario]  # 'B1' → 'A1'

    # 2. 收集所有 volume 栏位 (排除 volume_actual_*)
    vol_cols = [h for h in headers if h.startswith('volume_') and not h.startswith('volume_actual_')]

    # 3. 检查前序场景栏位必须出现在当前场景栏位之前
    prev_cols = [h for h in vol_cols if h.startswith(f'volume_{prev_scenario}_')]
    curr_cols = [h for h in vol_cols if h.startswith(f'volume_{current_scenario}_')]

    if not prev_cols:
        raise ValidationError(f'缺少前序场景 volume_{prev_scenario}_* 栏位')
    if not curr_cols:
        raise ValidationError(f'缺少当前场景 volume_{current_scenario}_* 栏位')

    last_prev_idx = max(headers.index(c) for c in prev_cols)
    first_curr_idx = min(headers.index(c) for c in curr_cols)
    if last_prev_idx >= first_curr_idx:
        raise ValidationError(
            f'volume_{prev_scenario}_* 栏位必须全部排在 volume_{current_scenario}_* 栏位之前'
        )

    # 4. 不应出现其他场景的 volume 栏位
    allowed_prefixes = {f'volume_{prev_scenario}_', f'volume_{current_scenario}_', 'volume_actual_'}
    for h in headers:
        if h.startswith('volume_') and not any(h.startswith(p) for p in allowed_prefixes):
            raise ValidationError(f'不允许出现非相关场景栏位: {h}')
```

**Volume 与 Spending 栏位数量一致性校验**：

```python
def validate_column_count_match(headers: list[str]):
    """每个 volume 场景的栏位数必须与 spending 栏位数一致"""
    spending_cols = [h for h in headers if h.startswith('spending_')]
    vol_cols = [h for h in headers if h.startswith('volume_') and not h.startswith('volume_actual_')]

    # 按场景分组
    scenarios = set()
    for h in vol_cols:
        # volume_A1_fy26_202509 → 'A1'
        scenario = h.split('_')[1]
        scenarios.add(scenario)

    for scenario in scenarios:
        scenario_cols = [h for h in vol_cols if h.startswith(f'volume_{scenario}_')]
        if len(scenario_cols) != len(spending_cols):
            raise ValidationError(
                f'volume_{scenario}_* 栏位数 ({len(scenario_cols)}) '
                f'与 spending_* 栏位数 ({len(spending_cols)}) 不一致'
            )
```

**校验结果展示**：

校验失败时，系统在导入预览页面以 Neo Brutalism 风格的红色错误卡片展示所有问题：

```
┌─ VALIDATION ERRORS ──────────────────────────────────────────┐
│                                                               │
│  ✗ [栏位顺序] volume_B1_fy26_202509 (第29列) 出现在            │
│    volume_A1_fy26_202601 (第33列) 之前，                       │
│    B1 版本要求 volume_A1 全部在 volume_B1 之前                  │
│                                                               │
│  ✗ [栏位数量] volume_B1_* 有 24 栏，spending_* 有 20 栏，      │
│    两者数量不一致                                               │
│                                                               │
│  ✗ [必填字段] 第 15 行: budgeter 为空                           │
│                                                               │
│  共 3 项错误，请修正后重新上传                                    │
│                                            [重新上传 CSV]      │
└───────────────────────────────────────────────────────────────┘
```

### 3.4 预算编制 (核心功能)

#### 3.4.1 Spending 编制
- 以表格形式展示某版本下的预算明细
- 按月份列横向展开（类似 Excel 的 Pivot 视图）
- 支持单元格直接编辑金额
- 自动汇总行：按 dept / dept_group / category / area 多层汇总
- 支持批量填充（如将某月金额复制到后续月份）
- **编辑权限**: 部门预算员 (Budgeter) 和管理员 (Admin) 均可编辑
- **输入校验**: 保存时前端+后端校验输入值必须为合法数字

#### 3.4.2 Saving 编制
- 录入节约计划金额（按月按科目）
- 关联说明/备注
- **编辑权限**: 部门预算员 (Budgeter) 和管理员 (Admin) 均可编辑
- **输入校验**: 保存时前端+后端校验输入值必须为合法数字，非数字输入拒绝保存并提示错误
- **联动计算**: Saving 值保存后，系统自动将同行同期的 **第一个 Rebase 栏位 (rebase_financeview)** 减去该 Saving 值（详见 3.4.9）

#### 3.4.3 New Add 编制
- 录入新增项目金额
- 需填写新增理由说明
- **编辑权限**: 部门预算员 (Budgeter) 和管理员 (Admin) 均可编辑
- **输入校验**: 保存时前端+后端校验输入值必须为合法数字，非数字输入拒绝保存并提示错误
- **联动计算**: NewAdd 值保存后，系统自动将同行同期的 **第一个 Rebase 栏位 (rebase_financeview)** 加上该 NewAdd 值（详见 3.4.9）

#### 3.4.4 Rebase 操作
- Finance View / Ops View 两种重定基准
- Rebase Finance View 由系统根据公式自动计算（见下方），用户也可手动覆盖
- Rebase Ops View 由用户手动输入或参考 Finance View 调整
- **编辑权限**: Rebase 栏位（rebase_financeview / rebase_opsview）**仅管理员 (Admin) 可编辑**，部门预算员只读不可修改

#### 3.4.5 Rebase Finance View 自动计算逻辑

CSV 上传或预算编辑时，系统根据以下规则自动计算 `rebase_financeview` 各期数值。

以 version = `fy26-B1` 为例（前序场景 A1，当前场景 B1）：

**规则一：`under_ops_control = 'N'` 时**

Rebase Finance View 直接等于对应期的 Spending 值，不做调整：

```
rebase_financeview[i] = spending[i]
```

**规则二：`under_ops_control = 'Y'` 时**

Rebase Finance View 需根据产量变动比率进行调整，公式如下：

```
rebase_financeview[i] = spending[i] * (1 - at_var) + at_var * (volume_prev[i] / volume_curr[i]) * spending[i]
```

其中：
| 变量 | 说明 |
|------|------|
| `spending[i]` | 第 i 期的 spending 值 |
| `at_var` | 该预算条目的 AT 差异比率（必须为 0~1 之间的小数） |
| `volume_prev[i]` | 第 i 期的前序场景产量（B1 版本时为 `volume_A1[i]`） |
| `volume_curr[i]` | 第 i 期的当前场景产量（B1 版本时为 `volume_B1[i]`） |

公式展开：
```
rebase_financeview[i] = spending[i] * [(1 - at_var) + at_var * (volume_prev[i] / volume_curr[i])]
```

> **直觉理解**：spending 中有 `at_var` 比例的部分随产量 (volume) 变动而浮动，其余 `(1 - at_var)` 比例为固定成本不受产量影响。当前序场景产量与当前场景产量不同时，浮动部分按比例缩放。

**场景映射关系**（与 3.3.3 中版本-场景规则一致）：

| version 场景 | volume_prev | volume_curr |
|-------------|-------------|-------------|
| B1 | volume_A1 | volume_B1 |
| C1 | volume_B1 | volume_C1 |
| D1 | volume_C1 | volume_D1 |
| A1 | volume_D1 (上一财年) | volume_A1 |

**计算示例** (version = `fy26-B1`, 某一行数据)：

```
given:
  at_var           = 0.05
  spending[1]      = 9978.47     (spending_fy26_202601)
  volume_A1[1]     = 22000       (volume_A1_fy26_202601)
  volume_B1[1]     = 24000       (volume_B1_fy26_202601)

under_ops_control = 'N':
  rebase_financeview[1] = 9978.47

under_ops_control = 'Y':
  rebase_financeview[1] = 9978.47 * (1 - 0.05) + 0.05 * (22000 / 24000) * 9978.47
                        = 9978.47 * 0.95 + 0.05 * 0.9167 * 9978.47
                        = 9479.55 + 457.35
                        = 9936.90
```

**边界条件处理**：

| 情况 | 处理方式 |
|------|----------|
| `volume_curr[i] = 0` | Rebase 值设为 `spending[i]`（避免除零错误），并标记警告 |
| `volume_prev[i] = 0` 且 `volume_curr[i] > 0` | 浮动部分视为 0，`rebase = spending * (1 - at_var)` |
| `at_var` 为空或 NULL | 视为 `at_var = 0`，即 `rebase = spending`（全部为固定成本） |
| `spending[i]` 为空 | `rebase` 也为空 |

**伪代码**：

```python
SCENARIO_ORDER = {'B1': 'A1', 'C1': 'B1', 'D1': 'C1', 'A1': 'D1'}

def calc_rebase_financeview(row: dict, version: str, periods: list[str]):
    """
    计算单行所有期间的 rebase_financeview 值。
    row: 该行所有栏位的 dict
    periods: spending 期间列表，如 ['fy26_202601', 'fy26_202602', ...]
    """
    current_scenario = extract_scenario(version)       # 'B1'
    prev_scenario = SCENARIO_ORDER[current_scenario]   # 'A1'

    at_var = to_decimal(row.get('at_var')) or Decimal(0)
    under_ops = row.get('under_ops_control', '')

    results = {}
    for period in periods:
        spending_val = to_decimal(row.get(f'spending_{period}'))
        if spending_val is None:
            results[period] = None
            continue

        if under_ops != 'Y':
            # 规则一: 非运营控制 → 直接等于 spending
            results[period] = spending_val
        else:
            # 规则二: 运营控制 → 按 volume 比率调整
            vol_prev = to_decimal(row.get(f'volume_{prev_scenario}_{period}'))
            vol_curr = to_decimal(row.get(f'volume_{current_scenario}_{period}'))

            if vol_curr is None or vol_curr == 0:
                results[period] = spending_val  # 避免除零
            elif vol_prev is None or vol_prev == 0:
                results[period] = spending_val * (1 - at_var)
            else:
                ratio = vol_prev / vol_curr
                results[period] = spending_val * ((1 - at_var) + at_var * ratio)

    return results
```

#### 3.4.6 Rebase Ops View 自动计算逻辑

Rebase Ops View 基于历史实际值 (actual) 的加权平均计算出一个 **月度 run-rate 基准**，然后对所有 rebase_opsview 期间统一赋值。

**关键中间变量**：

以 version = `fy26-B1` 为例，`actual` 有 4 个月 (202509~202512)，`volume_actual` 也有 4 个月。系统取前 3 个月进行加权平均：

```
actual_wavg = (actual[0] * 4 + actual[1] * 4 + actual[2] * 5) / 13
vol_actual_wavg = (volume_actual[0] * 4 + volume_actual[1] * 4 + volume_actual[2] * 5) / 13
```

> 权重 4, 4, 5 (合计 13) 对应各月的周数加权。`actual[0]` = 第 1 个 actual 栏位 (如 `actual_fy26_202509`)，依此类推。

**规则一：`under_ops_control = 'N'` 时**

所有 rebase_opsview 期间取相同的值 — 即历史 actual 加权月均：

```
rebase_opsview[i] = actual_wavg       (所有期间 i 值相同)
```

**规则二：`under_ops_control = 'Y'` 时**

将 actual 拆分为固定成本与变动成本两部分：

```
fixed_part  = (1 - at_var) * (actual_wavg - baseline_adjustment)
variable_part = at_var * (actual_wavg / vol_actual_wavg) * (actual_wavg - baseline_adjustment)

rebase_opsview[i] = fixed_part + variable_part       (所有期间 i 值相同)
```

各变量说明：

| 变量 | 说明 |
|------|------|
| `actual_wavg` | actual 前 3 期加权平均 |
| `vol_actual_wavg` | volume_actual 前 3 期加权平均 |
| `baseline_adjustment` | 该行的基线调整值 (来自 `bsa_main.baseline_adjustment`) |
| `at_var` | AT 差异比率 (0~1 小数) |
| `actual_wavg / vol_actual_wavg` | 历史单位成本 ($ per unit) |

公式合并：

```
rebase_opsview[i] = (actual_wavg - baseline_adjustment) * [(1 - at_var) + at_var * (actual_wavg / vol_actual_wavg)]
```

> **直觉理解**：先用 actual 加权平均算出月度 run-rate，减去 baseline_adjustment 得到调整后的基准成本。其中固定部分 `(1 - at_var)` 不变；变动部分 `at_var` 按历史单位成本 (actual/volume) 进行缩放。

**计算示例** (version = `fy26-B1`, 某一行数据)：

```
given:
  actual_fy26_202509    = 10000
  actual_fy26_202510    = 12000
  actual_fy26_202511    = 11000
  volume_actual_fy26_202509 = 20000
  volume_actual_fy26_202510 = 22000
  volume_actual_fy26_202511 = 21000
  at_var                = 0.05
  baseline_adjustment   = 500

step 1 — 加权平均:
  actual_wavg      = (10000*4 + 12000*4 + 11000*5) / 13
                   = (40000 + 48000 + 55000) / 13
                   = 143000 / 13
                   = 11000.00

  vol_actual_wavg  = (20000*4 + 22000*4 + 21000*5) / 13
                   = (80000 + 88000 + 105000) / 13
                   = 273000 / 13
                   = 21000.00

step 2 — under_ops_control = 'N':
  rebase_opsview[i] = 11000.00   (所有期间统一)

step 3 — under_ops_control = 'Y':
  fixed_part    = (1 - 0.05) * (11000 - 500) = 0.95 * 10500 = 9975.00
  variable_part = 0.05 * (11000 / 21000) * (11000 - 500)
                = 0.05 * 0.5238 * 10500
                = 275.00

  rebase_opsview[i] = 9975.00 + 275.00 = 10250.00   (所有期间统一)
```

**与 Rebase Finance View 的区别对比**：

| 维度 | Rebase Finance View (3.4.5) | Rebase Ops View (3.4.6) |
|------|---------------------------|------------------------|
| 基准数据 | 各期 spending 值 (逐期不同) | actual 加权月均 (所有期间统一) |
| Volume 参考 | volume_prev[i] / volume_curr[i] (逐期) | actual_wavg / vol_actual_wavg (固定比值) |
| baseline_adjustment | 不参与 | 参与 (从基准中扣除) |
| 结果特征 | 每期值不同，随 spending 和 volume 变化 | 每期值相同，为一个固定 run-rate |

**边界条件处理**：

| 情况 | 处理方式 |
|------|----------|
| `vol_actual_wavg = 0` | variable_part 设为 0，仅保留 fixed_part |
| `at_var` 为空或 NULL | 视为 `at_var = 0`，即 `rebase_opsview = actual_wavg`（N 情况）或 `actual_wavg - baseline_adjustment`（Y 情况） |
| actual 栏位不足 3 个 | 按实际可用栏位数调整权重 |
| `baseline_adjustment` 为空 | 视为 0 |

**伪代码**：

```python
def calc_rebase_opsview(row: dict, actual_periods: list[str], vol_actual_periods: list[str],
                        output_periods: list[str]):
    """
    计算单行所有期间的 rebase_opsview 值。
    actual_periods: actual 栏位对应的期间列表 (前 3 个)
    vol_actual_periods: volume_actual 栏位对应的期间列表 (前 3 个)
    output_periods: rebase_opsview 要输出的期间列表
    """
    WEIGHTS = [4, 4, 5]
    WEIGHT_SUM = 13

    # Step 1: 计算 actual 加权平均
    actual_vals = [to_decimal(row.get(f'actual_{p}')) or Decimal(0) for p in actual_periods[:3]]
    actual_wavg = sum(v * w for v, w in zip(actual_vals, WEIGHTS)) / WEIGHT_SUM

    under_ops = row.get('under_ops_control', '')
    at_var = to_decimal(row.get('at_var')) or Decimal(0)
    baseline_adj = to_decimal(row.get('baseline_adjustment')) or Decimal(0)

    if under_ops != 'Y':
        # 规则一: 所有期间 = actual_wavg
        value = actual_wavg
    else:
        # Step 2: 计算 volume_actual 加权平均
        vol_vals = [to_decimal(row.get(f'volume_actual_{p}')) or Decimal(0) for p in vol_actual_periods[:3]]
        vol_actual_wavg = sum(v * w for v, w in zip(vol_vals, WEIGHTS)) / WEIGHT_SUM

        adjusted_base = actual_wavg - baseline_adj
        fixed_part = (1 - at_var) * adjusted_base

        if vol_actual_wavg == 0:
            variable_part = Decimal(0)
        else:
            unit_cost = actual_wavg / vol_actual_wavg
            variable_part = at_var * unit_cost * adjusted_base

        value = fixed_part + variable_part

    # 所有输出期间赋相同值
    return {period: value for period in output_periods}
```

#### 3.4.7 `at_var` 字段校验

`at_var` 参与 rebase 计算，必须满足以下约束：

| 规则 | 说明 |
|------|------|
| 类型 | 必须为小数 (Decimal)，不接受整数或非数值字符 |
| 范围 | `0 ≤ at_var ≤ 1`（0 表示全部固定成本，1 表示全部可变成本） |
| 格式 | 如 `0.05`、`0.15`、`0.00`；不接受 `5`、`15`、`100%` 等格式 |
| 空值 | 允许为空，空值视为 `0`（全部固定成本） |

导入校验时若 `at_var` 不满足上述约束，报错提示：
```
✗ [字段格式] 第 23 行: at_var 值为 "5"，必须为 0~1 之间的小数 (如 0.05)
```

#### 3.4.8 编辑功能要求
- 单元格行内编辑（inline edit），保存时异步提交
- 修改历史追踪（audit trail）
- 自动计算列：合计、YTD、全年预算
- 列冻结：左侧维度列固定，右侧金额列可水平滚动

#### 3.4.9 Saving / NewAdd 与 Rebase 联动计算规则

当用户编辑 Saving 或 NewAdd 栏位并保存后，系统自动调整同行同期的 `rebase_financeview` 值。

**规则**：

```
rebase_financeview[i] (调整后) = rebase_financeview[i] (原值) - saving[i] + newadd[i]
```

即：
- **Saving 输入/修改** → 对应期 rebase_financeview **减去** saving 值（节约减少了预算）
- **NewAdd 输入/修改** → 对应期 rebase_financeview **加上** newadd 值（新增增加了预算）

**计算示例**：

```
given:
  rebase_financeview_fy26_202601 = 9936.90   (由 3.4.5 公式自动算出)
  saving_fy26_202601             = 500.00     (用户新输入)
  newadd_fy26_202601             = 200.00     (用户新输入)

result:
  rebase_financeview_fy26_202601 = 9936.90 - 500.00 + 200.00 = 9636.90
```

**交互流程**：

```
用户编辑 saving/newadd 单元格 → 失焦触发保存
    │
    ▼
前端 JS 校验: 输入值是否为合法数字?
    │
    ├─ [非数字] → 单元格标红，Tooltip 提示"请输入数字"，不发送请求
    │
    ▼ [合法数字]
POST /budget/api/cell/save/
    │
    ▼
后端处理:
  ├─ 再次校验数值合法性
  ├─ 保存 saving/newadd 值
  ├─ 重新计算: rebase_financeview[i] = 原始 rebase[i] - saving[i] + newadd[i]
  ├─ 更新 rebase_financeview 记录
  ├─ 写入 AuditLog
  └─ 返回 {status: "ok", updated_rebase: 9636.90, ...}
    │
    ▼
前端联动更新:
  ├─ rebase_financeview 对应单元格显示新值
  ├─ 汇总行重新计算
  └─ 已修改单元格高亮标识
```

**边界条件**：

| 情况 | 处理方式 |
|------|----------|
| saving 为空或清空 | 视为 0，rebase 不扣减 |
| newadd 为空或清空 | 视为 0，rebase 不增加 |
| saving 和 newadd 同时存在 | 同时生效：`rebase = 原始rebase - saving + newadd` |
| rebase_financeview 被管理员手动覆盖过 | 以手动覆盖值为基准再做加减 |

#### 3.4.10 栏位编辑权限汇总

| 栏位类型 | 部门预算员 (Budgeter) | 管理员 (Admin) | 输入校验 |
|----------|----------------------|--------------------------|---------|
| `spending_*` | ✓ 可编辑 | ✓ 可编辑 | 必须为数字 |
| `saving_*` | ✓ 可编辑 | ✓ 可编辑 | 必须为数字 |
| `newadd_*` | ✓ 可编辑 | ✓ 可编辑 | 必须为数字 |
| `rebase_financeview_*` | ✗ 只读 | ✓ 可编辑 | 必须为数字 |
| `rebase_opsview_*` | ✗ 只读 | ✓ 可编辑 | 必须为数字 |
| `volume_*` (当前场景) | ✓ 可编辑 | ✓ 可编辑 | 必须为数字 |
| `volume_*` (前序场景) | ✗ 只读 | ✗ 只读 | — |
| `actual_*` / `volume_actual_*` | ✗ 只读 | ✗ 只读 | — |

### 3.5 数据查询与报表

> 参考: `reference/003.jpg`, `reference/004.jpg`

#### 3.5.1 多维筛选
- Version（版本）
- Area（区域）
- Dept PPT（部门展示名，支持多选）
- Category（费用类别）
- Accounts / Levels（科目/层级）
- Budgeter（预算员）
- Under Ops Control（运营控制标识，Y/N 筛选）
- Spends Control / IECS View（控制标识）
- Type（数据类型筛选：Spending / Saving / Rebase 等）

#### 3.5.2 报表一：B1 vs Rebase 部门汇总表 (参考 003.jpg)

按 Dept PPT 分组的 Pivot 汇总报表，支持展开/折叠明细行：

```
筛选器: [Under Ops Control: Y ▼]

┌──────────────────┬──────────┬──────────┬────────┐
│                  │  FY26    │  FY26    │ FY26   │
│ Row Labels       │  B1      │  Rebase  │ B1 vs  │  ...更多列
│ (Dept PPT)       │  Q2-Q4   │  Q2-Q4   │ Rebase │
├──────────────────┼──────────┼──────────┼────────┤
│ ⊞ Automaton      │  $0.315M │  $0.237M │ $0.079M│
│ ⊞ Cross charge   │  $0.000M │  $0.000M │ $0.000M│
│ ⊞ EHS            │  $0.326M │  $0.087M │ $0.239M│
│ ⊞ Facility       │ $27.593M │ $27.254M │ $0.339M│
│ ⊞ PCDRAM Assy    │ $10.983M │ $11.104M │-$0.121M│
│ ⊞ LPDRAM Assy    │ $11.056M │ $10.658M │ $0.398M│
│ ⊞ Mod ENG        │  $2.204M │  $2.293M │-$0.089M│
│ ⊞ Mod MFG        │  $0.038M │  $0.038M │ $0.000M│
│ ⊞ Test ENG       │  $8.788M │  $8.831M │-$0.043M│
│ ⊞ Test MFG       │  $6.221M │  $6.231M │-$0.010M│
│   ...            │          │          │        │
├──────────────────┼──────────┼──────────┼────────┤
│ Grand Total      │ $78.871M │ $77.417M │ $1.453M│
└──────────────────┴──────────┴──────────┴────────┘
```

**列定义**（按财年/季度汇总）：
| 列名 | 说明 |
|------|------|
| Sum of FY26B1 Q2-Q4 | FY26 B1 Spending 第 2-4 季度合计 |
| Sum of FY26RebaseQ2-Q4 | FY26 Rebase 第 2-4 季度合计 |
| Sum of FY26 B1 vs Rebase | B1 与 Rebase 差额 |
| Sum of FY26 B1 vs Rebase% | B1 与 Rebase 差异百分比 |
| Sum of FY27B1 | FY27 B1 全年合计 |
| Sum of FY27Rebase | FY27 Rebase 全年合计 |
| Sum of FY27 B1 vs Rebase | FY27 差额 |
| Sum of FY27 B1 vs Rebase% | FY27 差异百分比 |
| Sum of F26A... | FY26 Actual 合计 |

**功能要求**：
- 行分组可展开：Dept PPT → Category → Accounts → Levels 多层明细
- 展开用 `⊞` / `⊟` 图标，类似 Excel Pivot 的行分组
- Grand Total 固定在最底部
- 百分比列显示 `#DIV/0!` 当分母为零时
- 金额格式化为 `$X.XXXM`（百万）或 `$X,XXX`（千）

#### 3.5.3 报表二：Saving 明细追踪表 (参考 004.jpg)

按 Type=Saving 筛选的详细节约项目清单：

```
筛选器: [Type: Saving ▼]

┌─────────────┬────────────────────┬────────────────────────────────────┬───────────┬───────────┐
│ Row Labels  │ Category           │ Spends description                 │ FY26 Plan │ FY27 Plan │
│ (Dept PPT)  │                    │                                    │ $(Q2-Q4)  │ $(Q1-Q4)  │
├─────────────┼────────────────────┼────────────────────────────────────┼───────────┼───────────┤
│ ⊟ Test MFG  │                    │                                    │           │           │
│             │ ⊟ Spares           │ Minimize B2(100k) cleanroom        │ ($24,687) │    $0     │
│             │                    │ printers                           │           │           │
├─────────────┤                    │                                    ├───────────┼───────────┤
│Test MFG Tot │                    │                                    │ ($24,687) │    $0     │
├─────────────┼────────────────────┼────────────────────────────────────┼───────────┼───────────┤
│ ⊟ QA        │                    │                                    │           │           │
│             │ ⊟ Spares           │ Share TSM calibration standard     │    $0     │ ($17,200) │
│             │                    │ sample with MSB for cost saving    │           │           │
│             │                    │ EOTPR QuickSim software study to   │  ($8,000) │  ($8,000) │
│             │                    │ cancel license fee                 │           │           │
│             │                    │ TSM in-house maintenance           │ ($17,200) │ ($17,200) │
│             │ ⊟ Material         │ Optimization IQC sample size to    │ ($36,000) │ ($48,000) │
│             │                    │ reduce SBT scrap cost              │           │           │
├─────────────┤                    │                                    ├───────────┼───────────┤
│ QA Total    │                    │                                    │ ($61,200) │ ($90,400) │
├─────────────┼────────────────────┼────────────────────────────────────┼───────────┼───────────┤
│ ⊟ Mod MFG   │                    │                                    │           │           │
│             │ ⊟ Packing Material │ Module shipping tray re-used for   │  ($8,172) │ ($10,898) │
│             │                    │ reject module ship out             │           │           │
│             │                    │ LPCAMM label second source         │  ($8,240) │ ($10,999) │
│             │ ⊟ IndirectMaterial │ SMT SP 350mm Squeegee to save      │ ($76,500) │($102,000) │
│             │                    │ non-print area solder paste        │           │           │
├─────────────┤                    │                                    ├───────────┼───────────┤
│Mod MFG Total│                    │                                    │ ($92,921) │($123,895) │
│   ...       │                    │                                    │           │           │
└─────────────┴────────────────────┴────────────────────────────────────┴───────────┴───────────┘
```

**功能要求**：
- 行分组层级：Dept PPT → Category → 逐笔 Spends Description 明细
- 每个 Dept PPT 有小计行（红色粗体显示负数总额）
- **Spends Description**：节约措施的详细文字说明（需新增字段，见 4.3 补充）
- 金额以括号表示负数 `($24,687)` — 表示节约（成本减少）
- 列按财年季度汇总：FY26 Plan $(Q2-Q4)、FY27 Plan $(Q1-Q4)
- 支持导出为 Excel，保留分组格式

#### 3.5.4 报表三：月度预算执行率热力图 (Monthly Budget Utilization Heatmap)

按部门 x 月份展示预算消耗比率的热力图，快速定位异常月份：

```
筛选器: [Version: fy26-B1 ▼]  [期间: FY26 ▼]

              │ 202601 │ 202602 │ 202603 │ 202604 │ 202605 │ ...
──────────────┼────────┼────────┼────────┼────────┼────────┼────
Facility      │  98%   │ 102%   │  95%   │ 110%   │  97%   │
PCDRAM Assy   │  88%   │  91%   │  94%   │  89%   │  92%   │
LPDRAM Assy   │ 105%   │  99%   │  97%   │  96%   │ 101%   │
Test ENG      │  92%   │  93%   │  90%   │  88%   │  95%   │
Mod MFG       │  78%   │  82%   │  85%   │  80%   │  79%   │
...           │        │        │        │        │        │

颜色编码:
  ■ <80%  深绿 (显著低于预算)      ■ 80-95% 浅绿 (正常偏低)
  ■ 95-105% 白/浅灰 (正常范围)    ■ 105-120% 浅红 (轻微超支)
  ■ >120% 深红 (严重超支)
```

**说明**：
- 每个单元格 = `Actual / Spending * 100%`（当月实际 / 当月预算）
- Actual 尚未入账的未来月份显示为灰色 `—`
- 点击单元格可下钻到该部门该月的科目明细
- 底部汇总行显示全厂各月执行率

#### 3.5.5 报表四：费用类别 Category 占比分析 (Category Mix Analysis)

按费用类别 (Category) 拆解各部门的支出结构：

```
筛选器: [Version: fy26-B1 ▼]  [Dept PPT: 全部 ▼]  [期间: FY26 Q2-Q4 ▼]

┌──────────────────┬─────────────┬─────────────┬──────────┬──────────┐
│                  │ Indirect    │ Spares      │ Material │          │
│ Dept PPT         │ Labor ($)   │ ($)         │ ($)      │ ... 更多  │ Total ($)
├──────────────────┼─────────────┼─────────────┼──────────┼──────────┤
│ Facility         │   $12.5M    │    $8.2M    │   $3.1M  │          │  $27.6M
│                  │    45.3%    │    29.7%    │   11.2%  │          │  100%
├──────────────────┼─────────────┼─────────────┼──────────┼──────────┤
│ PCDRAM Assy      │    $4.2M    │    $3.8M    │   $1.9M  │          │  $11.0M
│                  │    38.2%    │    34.5%    │   17.3%  │          │  100%
├──────────────────┼─────────────┼─────────────┼──────────┼──────────┤
│ Grand Total      │   $35.2M    │   $22.1M    │  $10.8M  │          │  $78.9M
│                  │    44.6%    │    28.0%    │   13.7%  │          │  100%
└──────────────────┴─────────────┴─────────────┴──────────┴──────────┘

附带: 堆叠条形图 — 每个部门一行，各 Category 按比例堆叠
```

#### 3.5.6 报表五：YoY 同比分析 (Year-over-Year Comparison)

对比 FY26 vs FY27 的预算变动趋势：

```
┌──────────────┬───────────┬───────────┬───────────┬──────────┐
│              │ FY26      │ FY27      │ YoY       │ YoY      │
│ Dept PPT     │ Budget    │ Budget    │ Change    │ Change % │
├──────────────┼───────────┼───────────┼───────────┼──────────┤
│ Facility     │ $27.59M   │ $36.12M   │ +$8.52M   │  +30.9%  │  ▲
│ PCDRAM Assy  │ $10.98M   │ $12.41M   │ +$1.43M   │  +13.0%  │  ▲
│ LPDRAM Assy  │ $11.06M   │ $17.40M   │ +$6.34M   │  +57.3%  │  ▲▲
│ ...          │           │           │           │          │
├──────────────┼───────────┼───────────┼───────────┼──────────┤
│ Grand Total  │ $78.87M   │$101.52M   │+$22.65M   │  +28.7%  │
└──────────────┴───────────┴───────────┴───────────┴──────────┘

附带: 蝴蝶图 (Butterfly Chart) — 左侧 FY26，右侧 FY27，中间为 Dept PPT
```

**说明**：
- 增长超过 50% 的行标记 `▲▲` 重点关注
- 负增长（减少）标记 `▼` 并用绿色显示
- 可下钻到 Category 层级查看哪些费用类别驱动了变化

#### 3.5.7 报表六：Controllable vs Non-Controllable 支出分析

区分可控与不可控支出，帮助管理层聚焦可优化的预算：

```
┌──────────────┬───────────────────────────┬───────────────────────────┬──────────┐
│              │     Controllable          │   Non-Controllable        │          │
│ Dept PPT     ├───────────┬───────────────┼───────────┬───────────────┤ Total    │
│              │ Amount    │ % of Dept     │ Amount    │ % of Dept     │          │
├──────────────┼───────────┼───────────────┼───────────┼───────────────┼──────────┤
│ Facility     │ $18.2M    │    66%        │ $9.4M     │    34%        │ $27.6M   │
│ PCDRAM Assy  │  $9.1M    │    83%        │ $1.9M     │    17%        │ $11.0M   │
│ Test ENG     │  $7.5M    │    85%        │ $1.3M     │    15%        │  $8.8M   │
│ ...          │           │               │           │               │          │
├──────────────┼───────────┼───────────────┼───────────┼───────────────┼──────────┤
│ Grand Total  │ $58.3M    │    74%        │ $20.6M    │    26%        │ $78.9M   │
└──────────────┴───────────┴───────────────┴───────────┴───────────────┴──────────┘

附带: 双环甜甜圈图 — 内圈 Controllable/Non-Controllable 占比，外圈按 Category 拆分
```

#### 3.5.8 报表七：Budgeter 工作负载与提交状态看板

按预算编制人维度的管理视图，用于追踪各 budgeter 的编制进度：

```
┌──────────────────┬──────────┬──────────┬──────────┬──────┬──────────┐
│                  │ 负责     │ 已填写   │ 空值     │ 完成 │ 最后     │
│ Budgeter         │ 条目数   │ 条目数   │ 条目数   │ 率   │ 编辑时间 │
├──────────────────┼──────────┼──────────┼──────────┼──────┼──────────┤
│ smjiao@micron    │    45    │    42    │     3    │  93% │ 03-01    │
│ alee@micron      │    38    │    38    │     0    │ 100% │ 02-28    │
│ bwang@micron     │    52    │    30    │    22    │  58% │ 02-15    │  ⚠
│ cchen@micron     │    28    │     0    │    28    │   0% │   —      │  ✗
├──────────────────┼──────────┼──────────┼──────────┼──────┼──────────┤
│ Total            │   280    │   220    │    60    │  79% │          │
└──────────────────┴──────────┴──────────┴──────────┴──────┴──────────┘

状态标记: ✓ 100%完成  ⚠ <80%需跟进  ✗ 0%未开始
```

#### 3.5.9 导出
- 导出当前查询/报表结果为 CSV / Excel
- 导出格式与导入 CSV 格式一致（可反向导入）
- Saving 明细报表导出保留层级分组与小计行

### 3.6 仪表盘 (Dashboard)

> 参考: `reference/001.png`, `reference/002.png`

#### 3.6.1 界面一：Spend & Loading Trend (用于 Slide Review) — 参考 001.png

顶部为两行汇总摘要卡片 + 左侧 Dept PPT 筛选器 + 右侧组合图表：

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  [Refresh spends Pivot before copy>>>]                                       │
├──────────────┬───────────┬───────────┬───────────┬───────────┬──────────────┤
│              │ Q4'25     │ Q1'26     │ Q2'26     │ Q3'26     │              │
│              │ Actual    │ A1        │ B1        │ B1        │ ...更多季度   │
├──────────────┼───────────┼───────────┼───────────┼───────────┼──────────────┤
│ B1 Spending  │   2.84M   │   2.98M   │   2.92M   │   2.87M   │    ...       │
│ B1 Rebase    │   2.84M   │   2.98M   │   2.91M   │   2.87M   │    ...       │
└──────────────┴───────────┴───────────┴───────────┴───────────┴──────────────┘

┌─────────────────┐  ┌───────────────────────────────────────────────────────┐
│ Dept PPT        │  │                                                       │
│ ┌─────────────┐ │  │  45M ┤                                                │
│ │LPDRAM Assy  │ │  │      │                                                │
│ │MO           │ │  │  30M ┤  ██  ──────────────────────── ─ ─ ─ ─          │
│ │Mod ENG      │ │  │      │  ██     ██     ██     ██     ██     ██         │
│ │Mod MFG      │ │  │  15M ┤  ██     ██     ██     ██     ██     ██         │
│ │NPM          │ │  │      │  ██     ██     ██     ██     ██     ██         │
│ │PCDRAM Assy  │ │  │   0  ┤──██─────██─────██─────██─────██─────██──       │
│ │Planning     │ │  │      Q4FY25  Q1FY26  Q2FY26  Q3FY26  Q4FY26  ...     │
│ │PMO          │ │  │       Actual   A1                                     │
│ │Procurement  │ │  │                                                       │
│ │QA           │ │  │  图例: ██ B1 Vol  ── B1 Spending  ─ ─ B1 Rebase      │
│ │Security     │ │  │                                                       │
│ │Site service │ │  └───────────────────────────────────────────────────────┘
│ │▶ Test ENG   │ │
│ │Test MFG     │ │
│ └─────────────┘ │
└─────────────────┘
```

**图表详细说明**：
- **图表类型**: 组合图 (柱状图 + 折线图)
- **X 轴**: 按季度分组 — Q4FY25 (Actual), Q1FY26 (A1), Q2FY26~Q4FY26 (B1), Q1FY27~Q4FY27 (B1)
- **柱状图 (B1 Vol)**: 灰蓝色柱体，表示该季度的产量 Volume
- **折线图 1 (B1 Spending)**: 深色实线，表示 B1 版本的支出计划金额
- **折线图 2 (B1 Rebase)**: 绿色实线，表示 B1 版本的 Rebase 金额
- **左侧 Y 轴**: Volume 数值刻度
- **右侧 Y 轴**: Spending / Rebase 金额刻度
- **顶部汇总行**: 两行分别显示 B1 Spending 和 B1 Rebase 的各季度合计值
- **左侧 Dept PPT 筛选器**: 多选列表，勾选部门后图表和汇总行联动刷新
- **数据联动**: 选择不同的 Dept PPT 组合后，图表和顶部数值实时更新

#### 3.6.2 界面二：Budget Waterfall (用于 Slide Review) — 参考 002.png

展示预算构成的瀑布图，体现从 Actual 到最终 Budget 的调整过程：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FY26(Q2-Q4) Budget Waterfall                         │
│                                                                         │
│  12M ┤                                                                  │
│      │                                                                  │
│  10M ┤ ████                          ░░░░                        ████   │
│      │ ████      ████                ░░░░                        ████   │
│   8M ┤ ████      ████    ┄┄┄┄       ░░░░      ████    ████      ████   │
│      │ ████      ████    ┄┄┄┄       ░░░░      ████    ████  ..  ████   │
│   6M ┤ ████      ████    ┄┄┄┄       ░░░░      ████    ████      ████   │
│      │ ████      ████               ░░░░                         ████   │
│   4M ┤ ████                         ░░░░                         ████   │
│      │ ████                         ░░░░                         ████   │
│   2M ┤ ████                         ░░░░                         ████   │
│      │ ████                         ░░░░                         ████   │
│   0  ┤──────────────────────────────────────────────────────────────    │
│       Actual  Volume  Baseline   Rebase   Cost     Adder         Budget│
│                       adjustment          Saving   new                  │
└─────────────────────────────────────────────────────────────────────────┘
```

**瀑布图各柱含义**：
| 柱 | 说明 | 示例值 | 颜色/方向 |
|----|------|--------|-----------|
| **Actual** | 基准实际花费 (起始柱) | $9,865,956 | 紫色实心柱 |
| **Volume** | 产量变动带来的费用影响 | +$822,914 | 橙色向上浮动柱 |
| **Baseline Adjustment** | 基线调整 | -$30,946 | 绿色向下浮动柱 |
| **Rebase** | 重定基准后的累计值 (中间合计柱) | $10,657,925 | 浅蓝/灰色实心柱 |
| **Cost Saving** | 节约措施减少的金额 | -$743,978 | 绿色向下浮动柱 |
| **Adder New** | 新增项目金额 | +$1,141,622 | 橙色向上浮动柱 |
| **Budget** | 最终预算 (终止柱) | $11,055,569 | 灰蓝色实心柱 |

**功能要求**：
- 支持按 Dept PPT 筛选，仅显示选定部门的瀑布图
- 支持按季度范围切换：Q2-Q4, 全年等
- 每个柱顶部显示精确数值标签
- 浮动柱（增加/减少）使用不同颜色区分方向
- Rebase 和 Budget 为落地柱（从 0 开始），其余为浮动柱
- 鼠标悬停显示详细计算公式 Tooltip

#### 3.6.3 Dashboard 页面布局

Dashboard 首页整合上述两个核心图表和额外指标：

```
┌─────────────────────────────────────────────────────────────────────────┐
│  版本: [fy26-B1 ▼]    Dept PPT: [全部 / 多选 ▼]    期间: [Q2-Q4 ▼]     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Spend & Loading Trend ────────────────────────────────────────────┐ │
│  │ (界面一: 季度柱状+折线组合图, B1 Vol / B1 Spending / B1 Rebase)     │ │
│  │                          [参考 001.png]                            │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌─ Budget Waterfall ─────────────────────────────────────────────────┐ │
│  │ (界面二: 瀑布图, Actual→Volume→Baseline→Rebase→Saving→Adder→Budget)│ │
│  │                          [参考 002.png]                            │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌─ 关键指标卡片 ─────────────────────────────────────────────────────┐ │
│  │ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │ │
│  │ │ $11.06M      │ │ $9.87M       │ │ ($743K)      │ │ +$1.45M    │ │ │
│  │ │ BUDGET       │ │ ACTUAL       │ │ COST SAVING  │ │ B1vsREBASE │ │ │
│  │ └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌─ 超预算预警 TOP 5 ────────────────────────────────────────────────┐ │
│  │ Dept PPT    │ Category │ FY26 B1   │ FY26 Rebase │ 差异   │ 差异%│ │
│  │ EHS         │ ...      │ $0.326M   │ $0.087M     │$0.239M │ 274% │ │
│  │ Planning    │ ...      │ $0.032M   │ $0.008M     │$0.024M │ 321% │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 3.6.4 Dashboard 附加图表

**卡片 A: Volume vs Spending 相关性散点图**
- X 轴: Volume (产量)，Y 轴: Spending (支出)
- 每个散点代表一个 Dept PPT，散点大小 = 该部门预算总额
- 附加回归趋势线

**卡片 B: 季度环比增长率折线图 (QoQ Growth)**
- 每条折线代表一个 Dept PPT
- Y 轴: Spending 季度环比增长率 (%)

**卡片 C: Saving 达成率雷达图**
- 每个轴代表一个 Dept PPT
- 数值 = 实际节约 / 计划节约 * 100%

### 3.7 部门编制完成状态标识

取消传统审批流程，改为轻量级的「编制完成标识」机制，让管理员（财务同事）能一目了然地掌握各部门的编制进度。

#### 3.7.1 预算员操作

- 预算员完成本部门所有预算编制后，点击 **[标记为已完成]** 按钮
- 标记后该部门对应版本的状态变为 `submitted`（已提交），页面显示绿色 `✓ 已完成` 标识
- 预算员可随时撤回完成标记（状态回到 `editing`），继续修改数据
- 标记完成时系统自动记录时间戳和操作人

#### 3.7.2 管理员视图 — 部门提交状态看板

管理员在版本管理页面可看到所有部门的编制状态汇总：

```
┌─ 版本 fy26-B1 — 部门编制状态 ──────────────────────────────────────┐
│                                                                      │
│  ✓ COMPLETED        ● EDITING           ✗ NOT STARTED               │
│  ██████ 6/12        ██████ 4/12         ██ 2/12                     │
│                                                                      │
├──────────────┬──────────┬──────────────┬────────────────────────────┤
│ Dept PPT     │ 状态     │ 完成时间      │ 预算员                      │
├──────────────┼──────────┼──────────────┼────────────────────────────┤
│ Facility     │ ✓ 已完成  │ 03-01 14:30  │ smjiao@micron              │
│ PCDRAM Assy  │ ✓ 已完成  │ 02-28 16:45  │ alee@micron                │
│ Test ENG     │ ✓ 已完成  │ 03-01 09:20  │ bwang@micron               │
│ Mod MFG      │ ● 编辑中  │    —         │ cchen@micron               │
│ QA           │ ● 编辑中  │    —         │ dli@micron                 │
│ EHS          │ ✗ 未开始  │    —         │ ewu@micron                 │
│ ...          │          │              │                             │
├──────────────┼──────────┼──────────────┼────────────────────────────┤
│ 合计 12 部门  │ 6 完成    │ 4 编辑中     │ 2 未开始                    │
└──────────────┴──────────┴──────────────┴────────────────────────────┘
```

#### 3.7.3 状态定义

| 状态 | 标识 | 颜色 | 说明 |
|------|------|------|------|
| `not_started` | ✗ 未开始 | 灰色 | 该部门在此版本无任何编辑记录 |
| `editing` | ● 编辑中 | 橙色/黄色 | 有编辑记录但尚未标记完成 |
| `submitted` | ✓ 已完成 | 绿色 | 预算员已标记编制完成 |

#### 3.7.4 通知机制

- 预算员标记完成时，管理员收到站内通知（如顶部导航栏消息提醒）
- 当所有部门均标记完成时，系统向管理员发送汇总通知
- 管理员确认全部完成后可手动将版本状态改为 Locked

### 3.8 审计日志

- 记录所有数据修改操作（谁、何时、改了什么、旧值→新值）
- 支持按版本、budgeter、时间范围查询

### 3.9 UI 设计规范 — Neo Brutalism (新粗野主义)

系统采用 Neo Brutalism 风格，以粗黑边框、高对比色块、硬阴影为核心视觉语言。

#### 3.9.1 设计原则

| 原则 | 说明 |
|------|------|
| **粗黑边框** | 所有卡片、按钮、输入框、表格使用 `2~3px solid #000` 黑色实线边框 |
| **硬阴影** | 不使用 `box-shadow` 模糊阴影，改用偏移硬阴影 `4px 4px 0px #000` |
| **高饱和色块** | 使用高饱和度的纯色背景（黄、蓝、粉、绿），不使用渐变 |
| **无圆角或微圆角** | `border-radius: 0` 或最多 `4px`，保持硬朗几何感 |
| **粗字体** | 标题使用 `font-weight: 800~900`，正文 `500~600` |
| **大间距** | 组件间留足空白，让粗边框和色块有呼吸感 |

#### 3.9.2 色彩体系

```
主色板 (高饱和色块，用于卡片/区域背景):
┌──────────────┬──────────────┬──────────────┬──────────────┐
│  ██ #FFD43B  │  ██ #74C0FC  │  ██ #B2F2BB  │  ██ #FFC9C9  │
│  亮黄 (主要)  │  天蓝 (信息)  │  薄荷绿 (正向)│  浅粉红 (警示)│
└──────────────┴──────────────┴──────────────┴──────────────┘

功能色:
┌──────────────┬──────────────┬──────────────┬──────────────┐
│  ██ #000000  │  ██ #FFFFFF  │  ██ #FF6B6B  │  ██ #51CF66  │
│  黑 (边框/文字)│  白 (底色)   │  红 (超支/负数)│  绿 (节约/正向)│
└──────────────┴──────────────┴──────────────┴──────────────┘

扩展色 (用于图表系列区分):
  ██ #845EF7 紫   ██ #FF922B 橙   ██ #20C997 青绿   ██ #E64980 玫红
```

#### 3.9.3 核心组件样式

**按钮**
```css
.btn-neo {
    border: 3px solid #000;
    border-radius: 0;
    box-shadow: 4px 4px 0px #000;
    font-weight: 700;
    text-transform: uppercase;
    padding: 10px 24px;
    transition: transform 0.1s, box-shadow 0.1s;
}
.btn-neo:active {
    transform: translate(4px, 4px);
    box-shadow: 0 0 0 #000;       /* 按下时阴影消失，模拟物理按压 */
}
.btn-neo-primary { background: #FFD43B; color: #000; }
.btn-neo-danger  { background: #FF6B6B; color: #000; }
.btn-neo-info    { background: #74C0FC; color: #000; }
```

**卡片 (Dashboard 指标卡片、报表容器)**
```css
.card-neo {
    border: 3px solid #000;
    border-radius: 0;
    box-shadow: 6px 6px 0px #000;
    background: #fff;
    padding: 20px;
}
.card-neo-yellow { background: #FFD43B; }
.card-neo-blue   { background: #74C0FC; }
.card-neo-green  { background: #B2F2BB; }
.card-neo-pink   { background: #FFC9C9; }
```

**数据表格**
```css
.table-neo {
    border: 3px solid #000;
    border-collapse: separate;
    border-spacing: 0;
}
.table-neo th {
    background: #000;
    color: #FFD43B;
    font-weight: 800;
    text-transform: uppercase;
    padding: 12px 16px;
    border-bottom: 3px solid #000;
}
.table-neo td {
    border-bottom: 2px solid #000;
    border-right: 1px solid #ddd;
    padding: 10px 16px;
    font-variant-numeric: tabular-nums;   /* 等宽数字对齐 */
}
.table-neo tr:hover {
    background: #FFF3BF;                  /* 悬停高亮黄 */
}
.table-neo .subtotal-row {
    background: #E9ECEF;
    font-weight: 700;
    border-top: 3px solid #000;
}
.table-neo .grand-total-row {
    background: #FFD43B;
    font-weight: 900;
    border-top: 4px solid #000;
}
```

**输入框 (预算编辑单元格)**
```css
.input-neo {
    border: 2px solid #000;
    border-radius: 0;
    padding: 8px 12px;
    font-weight: 600;
    outline: none;
}
.input-neo:focus {
    box-shadow: 3px 3px 0px #74C0FC;
    border-color: #000;
}
.input-neo-changed {
    background: #FFF3BF;                  /* 已修改未保存 */
    border-color: #FF922B;
}
```

#### 3.9.4 页面布局示意

```
┌─────────────────────────────────────────────────────────────────────┐
│ ████████████████████████████████████████████████████████████████████ │
│ ██  BSA BUDGET SYSTEM          [smjiao@micron]  [Logout]        ██ │
│ ████████████████████████████████████████████████████████████████████ │
│ ▌黑底黄字顶部导航栏，粗体大写字母                                     │
├────────────┬────────────────────────────────────────────────────────┤
│            │                                                        │
│ ┌────────┐ │  内容区域                                               │
│ │DASH    │ │                                                        │
│ │BOARD   │ │  - 所有容器: 3px 黑色实线边框 + 硬阴影                    │
│ ├────────┤ │  - 导航栏: 纯黑底，黄色/白色粗体文字                      │
│ │BUDGET  │ │  - 侧边栏: 纯黑底，白色菜单项，当前页黄色高亮              │
│ │EDIT    │ │  - 指标卡片: 高饱和色块背景，黑色粗字                     │
│ ├────────┤ │  - 表格: 黑色表头 + 黄色文字，行悬停黄色高亮               │
│ │REPORTS │ │  - 按钮: 有物理按压效果 (点击时阴影消失 + 位移)            │
│ ├────────┤ │                                                        │
│ │IMPORT  │ │                                                        │
│ ├────────┤ │                                                        │
│ │STATUS  │ │                                                        │
│ └────────┘ │                                                        │
│ ▌黑底白字   │                                                        │
│ ▌侧边栏    │                                                        │
└────────────┴────────────────────────────────────────────────────────┘
```

#### 3.9.5 图表主题配色 (ECharts Neo Brutalism Theme)

```javascript
// static/js/echarts_neo_theme.js
const NEO_THEME = {
    color: ['#845EF7', '#FF922B', '#20C997', '#FF6B6B', '#74C0FC',
            '#FFD43B', '#E64980', '#51CF66'],
    backgroundColor: '#FFFFFF',
    title: {
        textStyle: { fontWeight: 900, fontSize: 18, color: '#000' }
    },
    legend: {
        textStyle: { fontWeight: 700, color: '#000' }
    },
    categoryAxis: {
        axisLine: { lineStyle: { color: '#000', width: 2 } },
        axisTick: { lineStyle: { color: '#000', width: 2 } },
        axisLabel: { fontWeight: 700, color: '#000' }
    },
    valueAxis: {
        axisLine: { lineStyle: { color: '#000', width: 2 } },
        splitLine: { lineStyle: { color: '#E9ECEF', width: 1 } }
    },
    bar: {
        itemStyle: { borderColor: '#000', borderWidth: 2 }
    },
    line: {
        lineStyle: { width: 3 },
        symbol: 'rect',    // 方形数据点，呼应 Neo Brutalism
        symbolSize: 8
    }
};
```

---

## 4. 系统架构

### 4.1 整体架构图

```
┌─────────────────────────────────────────────────────┐
│                    浏览器 (Browser)                    │
│  HTML5 + CSS3 (Neo Brutalism) + JavaScript            │
│  DataTables.js | ECharts (瀑布图/组合图)              │
└────────────────────┬────────────────────────────────┘
                     │ HTTP / HTTPS
┌────────────────────▼────────────────────────────────┐
│              Nginx (反向代理 + 静态文件)                │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│              Gunicorn / uWSGI (WSGI 服务器)           │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│                Django Application                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │ accounts │ │  budget  │ │  reports │             │
│  │  (用户)   │ │ (预算核心)│ │  (报表)   │             │
│  └──────────┘ └──────────┘ └──────────┘             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │ importer │ │  status  │ │dashboard │             │
│  │ (导入导出)│ │(提交状态) │ │ (仪表盘)  │             │
│  └──────────┘ └──────────┘ └──────────┘             │
│  ┌──────────────────────────────────────┐           │
│  │   Django ORM (数据库抽象层)            │           │
│  │   支持 PostgreSQL / SQL Server 切换   │           │
│  └──────────────────────────────────────┘           │
└──────────┬─────────────────────┬────────────────────┘
           │                     │
┌──────────▼──────────┐ ┌───────▼─────────────────────┐
│  PostgreSQL 15+     │ │  SQL Server 2019+            │
│  (开发/默认环境)     │ │  (企业部署可选)               │
│  bsa_build_sql()    │ │  使用 ORM 构造等效查询        │
│  bsa_get_by_version │ │  (不依赖 PL/pgSQL 函数)      │
└─────────────────────┘ └─────────────────────────────┘
```

### 4.2 Django 项目结构

```
budget_system/
├── manage.py
├── requirements.txt
├── .gitignore                      # 版本控制忽略规则 (含 config.ini、*.pyc、venv/ 等)
├── config.ini                      # 系统配置文件 (INI 格式，含数据库/应用/LDAP 等，见 4.4.1)
├── config.ini.example              # 配置文件模板 (提交到 git，供参考)
├── config/                      # 项目配置
│   ├── settings/
│   │   ├── base.py              # 通用配置 (读取 config.ini)
│   │   ├── dev.py               # 开发环境
│   │   └── prod.py              # 生产环境
│   ├── urls.py                  # 根 URL 路由
│   └── wsgi.py
│
├── apps/
│   ├── accounts/                # 用户与权限
│   │   ├── models.py            # BsaPermission (权限校验)
│   │   ├── views.py             # 登录 (含 bsa_permission 校验)、用户管理
│   │   ├── backends.py          # 自定义认证后端 (查询 bsa_permission 表)
│   │   └── templates/accounts/
│   │
│   ├── budget/                  # 预算核心 (最重要的 App)
│   │   ├── models.py            # BsaMain, BsaVolume, BsaSpending, ...
│   │   ├── views.py             # 预算编制、版本管理
│   │   ├── forms.py             # 版本创建表单
│   │   ├── services.py          # 业务逻辑层
│   │   ├── db_compat.py         # 数据库兼容层 (PG/MSSQL 查询适配)
│   │   ├── api.py               # AJAX 接口 (单元格保存等)
│   │   └── templates/budget/
│   │       ├── version_list.html
│   │       ├── budget_edit.html # 核心编辑页面 (Pivot 表格)
│   │       └── version_compare.html
│   │
│   ├── importer/                # 数据导入导出
│   │   ├── models.py            # ImportLog
│   │   ├── views.py             # 上传、预览、确认导入
│   │   ├── services.py          # CSV/Excel 解析与写入逻辑
│   │   ├── validators.py        # Volume 栏位顺序/数量校验逻辑
│   │   └── templates/importer/
│   │
│   ├── reports/                 # 报表
│   │   ├── views.py             # 各类报表视图
│   │   ├── services.py          # 复用 bsa_build_sql 或 ORM 聚合
│   │   └── templates/reports/
│   │
│   ├── dashboard/               # 仪表盘
│   │   ├── views.py
│   │   └── templates/dashboard/
│   │
│   └── status/                  # 部门编制完成状态
│       ├── models.py            # BudgetSubmissionStatus
│       ├── views.py
│       └── templates/status/
│
├── static/                      # 静态资源
│   ├── css/
│   │   ├── neo_brutalism.css    # Neo Brutalism 核心样式 (变量/组件)
│   │   ├── layout.css           # 布局 (导航栏/侧边栏/网格)
│   │   └── budget.css           # 业务页面自定义样式
│   ├── js/
│   │   ├── echarts_neo_theme.js # ECharts Neo Brutalism 主题
│   │   ├── budget_edit.js       # 表格编辑交互逻辑
│   │   ├── dashboard_charts.js  # 图表初始化
│   │   └── import_upload.js     # 导入文件上传
│   └── vendor/                  # 第三方 JS/CSS
│
└── templates/                   # 全局模板
    ├── base.html                # 基础布局 (导航栏、侧边栏)
    ├── includes/
    │   ├── navbar.html
    │   ├── sidebar.html
    │   └── messages.html
    └── 403.html / 404.html / 500.html
```

### 4.3 Django Models 设计

#### 4.3.1 用户权限模型 (`apps/accounts/models.py`)

```python
# apps/accounts/models.py

from django.db import models


class BsaPermission(models.Model):
    """用户权限表 - 登录时校验用户是否有系统访问权限及角色"""
    ROLE_CHOICES = [
        ('admin', '系统管理员'),
        ('budgeter', '部门预算员'),
        ('viewer', '只读查看者'),
    ]
    user_mail = models.TextField()
    user_role = models.TextField(choices=ROLE_CHOICES)

    class Meta:
        db_table = 'bsa_permission'
        unique_together = ('user_mail', 'user_role')

    def __str__(self):
        return f'{self.user_mail} - {self.user_role}'
```

#### 4.3.2 预算核心模型 (`apps/budget/models.py`)

```python
# apps/budget/models.py

from django.db import models
from django.conf import settings


# 注意：不使用独立的 BudgetVersion 模型/表。
# 版本信息直接从 bsa_main.version 字段获取。
# 使用以下辅助函数获取版本列表：

def get_all_versions():
    """从 bsa_main 获取所有不同的版本名称"""
    return list(
        BsaMain.objects.values_list('version', flat=True)
        .distinct().order_by('version')
    )

def parse_version_name(version_name):
    """解析版本名称如 'fy26-B1' 为 (fiscal_year, scenario)"""
    parts = version_name.split('-', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return version_name, ''


class BsaMain(models.Model):
    """预算主表 - 每行代表一个成本中心+科目的预算条目"""
    version = models.CharField(max_length=50, db_index=True)
    data_type = models.CharField(max_length=50, blank=True)
    under_ops_control = models.CharField(max_length=10, blank=True)
    ccgl = models.CharField(max_length=50, blank=True)
    glc = models.CharField(max_length=50, blank=True)
    cc = models.CharField(max_length=50, blank=True)
    non_controllable = models.CharField(max_length=50, blank=True)
    area = models.CharField(max_length=50, db_index=True)
    dept = models.CharField(max_length=50, db_index=True)
    dept_group = models.CharField(max_length=50, db_index=True)
    dept_ppt = models.CharField(max_length=300, blank=True)
    category = models.CharField(max_length=100, db_index=True)
    discretionary = models.CharField(max_length=50, blank=True)
    at_var = models.DecimalField(max_digits=18, decimal_places=4, null=True)
    self_study_var = models.DecimalField(max_digits=18, decimal_places=4, null=True)
    spends_control = models.CharField(max_length=10, blank=True)
    iecs_view = models.CharField(max_length=10, blank=True)
    levels = models.CharField(max_length=300, blank=True)
    accounts = models.CharField(max_length=300, blank=True)
    budgeter = models.CharField(max_length=100, db_index=True)
    baseline_adjustment = models.DecimalField(max_digits=18, decimal_places=2, null=True)

    class Meta:
        db_table = 'bsa_main'
        indexes = [
            models.Index(fields=['version', 'dept']),
            models.Index(fields=['version', 'budgeter']),
        ]


class BsaVolumeActual(models.Model):
    main = models.ForeignKey(BsaMain, on_delete=models.CASCADE, related_name='volume_actuals')
    period = models.CharField(max_length=20)
    value = models.DecimalField(max_digits=18, decimal_places=2, null=True)
    class Meta:
        db_table = 'bsa_volume_actual'
        unique_together = ('main', 'period')


class BsaVolume(models.Model):
    main = models.ForeignKey(BsaMain, on_delete=models.CASCADE, related_name='volumes')
    scenario = models.CharField(max_length=10)
    period = models.CharField(max_length=20)
    value = models.DecimalField(max_digits=18, decimal_places=2, null=True)
    class Meta:
        db_table = 'bsa_volume'
        unique_together = ('main', 'scenario', 'period')


class BsaActual(models.Model):
    main = models.ForeignKey(BsaMain, on_delete=models.CASCADE, related_name='actuals')
    period = models.CharField(max_length=20)
    value = models.DecimalField(max_digits=18, decimal_places=2, null=True)
    class Meta:
        db_table = 'bsa_actual'
        unique_together = ('main', 'period')


class BsaSpending(models.Model):
    main = models.ForeignKey(BsaMain, on_delete=models.CASCADE, related_name='spendings')
    period = models.CharField(max_length=20)
    value = models.DecimalField(max_digits=18, decimal_places=2, null=True)
    class Meta:
        db_table = 'bsa_spending'
        unique_together = ('main', 'period')


class BsaRebaseFinanceview(models.Model):
    main = models.ForeignKey(BsaMain, on_delete=models.CASCADE, related_name='rebase_financeviews')
    period = models.CharField(max_length=20)
    value = models.DecimalField(max_digits=18, decimal_places=2, null=True)
    class Meta:
        db_table = 'bsa_rebase_financeview'
        unique_together = ('main', 'period')


class BsaRebaseOpsview(models.Model):
    main = models.ForeignKey(BsaMain, on_delete=models.CASCADE, related_name='rebase_opsviews')
    period = models.CharField(max_length=20)
    value = models.DecimalField(max_digits=18, decimal_places=2, null=True)
    class Meta:
        db_table = 'bsa_rebase_opsview'
        unique_together = ('main', 'period')


class BsaSaving(models.Model):
    main = models.ForeignKey(BsaMain, on_delete=models.CASCADE, related_name='savings')
    period = models.CharField(max_length=20)
    value = models.DecimalField(max_digits=18, decimal_places=2, null=True)
    spends_description = models.TextField(blank=True)  # 节约措施说明 (参考 004.jpg)
    class Meta:
        db_table = 'bsa_saving'
        unique_together = ('main', 'period')


class BsaNewadd(models.Model):
    main = models.ForeignKey(BsaMain, on_delete=models.CASCADE, related_name='newadds')
    period = models.CharField(max_length=20)
    value = models.DecimalField(max_digits=18, decimal_places=2, null=True)
    spends_description = models.TextField(blank=True)  # 新增项目说明
    class Meta:
        db_table = 'bsa_newadd'
        unique_together = ('main', 'period')
```

#### 4.3.3 导入日志模型 (`apps/importer/models.py`)

```python
# apps/importer/models.py

from django.db import models
from django.conf import settings


class ImportLog(models.Model):
    """导入日志 - 记录每次 CSV/Excel 导入操作"""
    version = models.CharField(max_length=50, db_index=True)       # 导入的目标版本
    file_name = models.CharField(max_length=255)                    # 上传文件名
    file_size = models.IntegerField(default=0)                      # 文件大小 (bytes)
    total_rows = models.IntegerField(default=0)                     # 总行数
    success_rows = models.IntegerField(default=0)                   # 成功导入行数
    failed_rows = models.IntegerField(default=0)                    # 失败行数
    error_details = models.TextField(blank=True)                    # 错误详情 (JSON 格式)
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bsa_import_log'
        ordering = ['-imported_at']
```

#### 4.3.4 提交状态模型 (`apps/status/models.py`)

```python
# apps/status/models.py

from django.db import models
from django.conf import settings


class BudgetSubmissionStatus(models.Model):
    """部门编制完成状态 - 追踪各部门在各版本下的预算编制进度"""
    STATUS_CHOICES = [
        ('not_started', '未开始'),
        ('editing', '编辑中'),
        ('submitted', '已完成'),
    ]
    version = models.CharField(max_length=50, db_index=True)       # 预算版本 (如 fy26-B1)
    dept_ppt = models.CharField(max_length=300, db_index=True)      # 部门 PPT 展示名称
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, blank=True)        # 标记完成的操作人
    submitted_at = models.DateTimeField(null=True, blank=True)      # 标记完成时间
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bsa_submission_status'
        unique_together = ('version', 'dept_ppt')
```

#### 4.3.5 审计日志模型 (`apps/budget/models.py` 补充)

```python
# apps/budget/models.py (补充)

class AuditLog(models.Model):
    """审计日志 - 记录所有预算数据的修改操作"""
    table_name = models.CharField(max_length=50)                    # 被修改的表名 (如 bsa_spending)
    main_id = models.BigIntegerField(db_index=True)                 # 关联的 bsa_main 主键
    period = models.CharField(max_length=20, blank=True)            # 修改的期间
    field_name = models.CharField(max_length=50, blank=True)        # 修改的字段名
    old_value = models.TextField(blank=True, null=True)             # 旧值
    new_value = models.TextField(blank=True, null=True)             # 新值
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'bsa_audit_log'
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['table_name', 'main_id']),
            models.Index(fields=['changed_by', 'changed_at']),
        ]
```

### 4.4 双数据库兼容设计

系统同时支持 PostgreSQL 和 SQL Server，通过以下策略实现：

#### 4.4.1 配置切换 — `config.ini` 配置文件

通过项目根目录下的 `config.ini` 文件集中管理所有可配置项（数据库、应用、LDAP、缓存等），运维人员无需修改 Python 代码即可完成部署配置。

**`config.ini` 文件格式**：

```ini
; ============================================================
; BSA Budget System 配置文件
; 部署时复制 config.ini.example 为 config.ini 并按实际环境修改
; ============================================================

; ------------------------------------------------------------
; 应用基础配置
; ------------------------------------------------------------
[app]
secret_key = your-django-secret-key-here
debug = false
allowed_hosts = localhost,127.0.0.1,bsa.yourcompany.com

; ------------------------------------------------------------
; 数据库配置
; 切换数据库只需修改 engine 值:
;   engine = postgresql   → 使用 PostgreSQL
;   engine = mssql        → 使用 SQL Server
; ------------------------------------------------------------
[database]
engine = postgresql
name = budget_system
host = 192.168.56.101
port = 5432
user = postgres
password = yourpassword
; SQL Server 专用配置 (engine = mssql 时生效):
; driver = ODBC Driver 17 for SQL Server

; ------------------------------------------------------------
; SQL Server 配置示例 (取消注释并替换上方 [database] 段即可)
; ------------------------------------------------------------
; [database]
; engine = mssql
; name = budget_system
; host = 10.0.0.50
; port = 1433
; user = sa
; password = yourpassword
; driver = ODBC Driver 17 for SQL Server

; ------------------------------------------------------------
; LDAP / Active Directory 配置 (可选)
; ------------------------------------------------------------
[ldap]
enabled = false
server_uri = ldap://ad.yourcompany.com:389
bind_dn = CN=svc_bsa,OU=ServiceAccounts,DC=yourcompany,DC=com
bind_password =
search_base = OU=Users,DC=yourcompany,DC=com
user_attr = sAMAccountName

; ------------------------------------------------------------
; Redis 缓存配置 (可选，不配置则使用 Django 默认本地缓存)
; ------------------------------------------------------------
[redis]
enabled = false
host = 127.0.0.1
port = 6379
db = 0
; password =
```

**Django settings 读取 `config.ini`**：

```python
# config/settings/base.py — 从 config.ini 读取所有配置

import configparser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 读取 config.ini
cfg = configparser.ConfigParser()
cfg.read(BASE_DIR / 'config.ini', encoding='utf-8')

# ---- 应用配置 ----
SECRET_KEY = cfg.get('app', 'secret_key', fallback='django-insecure-change-me')
DEBUG = cfg.getboolean('app', 'debug', fallback=True)
ALLOWED_HOSTS = [
    h.strip() for h in cfg.get('app', 'allowed_hosts', fallback='*').split(',')
]

# ---- 数据库配置 ----
DB_ENGINE = cfg.get('database', 'engine', fallback='postgresql')
DB_NAME = cfg.get('database', 'name', fallback='budget_system')
DB_HOST = cfg.get('database', 'host', fallback='localhost')
DB_PORT = cfg.get('database', 'port', fallback='5432')
DB_USER = cfg.get('database', 'user', fallback='postgres')
DB_PASSWORD = cfg.get('database', 'password', fallback='')

if DB_ENGINE == "mssql":
    DB_DRIVER = cfg.get('database', 'driver', fallback='ODBC Driver 17 for SQL Server')
    DATABASES = {
        "default": {
            "ENGINE": "mssql",
            "NAME": DB_NAME,
            "HOST": DB_HOST,
            "PORT": DB_PORT,
            "USER": DB_USER,
            "PASSWORD": DB_PASSWORD,
            "OPTIONS": { "driver": DB_DRIVER },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": DB_NAME,
            "HOST": DB_HOST,
            "PORT": DB_PORT,
            "USER": DB_USER,
            "PASSWORD": DB_PASSWORD,
        }
    }

# ---- LDAP 配置 (可选) ----
LDAP_ENABLED = cfg.getboolean('ldap', 'enabled', fallback=False)
if LDAP_ENABLED:
    LDAP_SERVER_URI = cfg.get('ldap', 'server_uri')
    LDAP_BIND_DN = cfg.get('ldap', 'bind_dn')
    LDAP_BIND_PASSWORD = cfg.get('ldap', 'bind_password')
    LDAP_SEARCH_BASE = cfg.get('ldap', 'search_base')
    LDAP_USER_ATTR = cfg.get('ldap', 'user_attr', fallback='sAMAccountName')

# ---- Redis 配置 (可选) ----
REDIS_ENABLED = cfg.getboolean('redis', 'enabled', fallback=False)
if REDIS_ENABLED:
    REDIS_HOST = cfg.get('redis', 'host', fallback='127.0.0.1')
    REDIS_PORT = cfg.get('redis', 'port', fallback='6379')
    REDIS_DB = cfg.get('redis', 'db', fallback='0')
    REDIS_PASSWORD = cfg.get('redis', 'password', fallback=None)
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
        }
    }
```

**注意事项**：
- `config.ini` 包含密码和密钥，**不应提交到版本控制**，需加入 `.gitignore`
- 项目提供 `config.ini.example` 作为模板（密码字段留空），提交到 git 供参考
- 部署时由运维人员复制 `config.ini.example` 为 `config.ini` 并填入实际值

#### 4.4.2 兼容性约束

| 事项 | 策略 |
|------|------|
| **ORM 优先** | 所有业务查询尽量使用 Django ORM，避免原生 SQL |
| **Pivot 查询** | PostgreSQL 可调用 `bsa_build_sql()` 函数；SQL Server 使用 ORM 聚合 + Python 端 pivot |
| **自增主键** | 使用 `BigAutoField`，PG 映射 `BIGSERIAL`，MSSQL 映射 `BIGINT IDENTITY` |
| **UPSERT** | PG 使用 `ON CONFLICT DO UPDATE`；MSSQL 使用 `MERGE`；统一封装在 `db_compat.py` |
| **批量写入** | PG 使用 `execute_values`；MSSQL 使用 `fast_executemany` |
| **布尔/字符** | 不使用 `BooleanField`，维持 `CharField(Y/N)` 以保持两端兼容 |

### 4.5 关键页面与 URL 设计

```
/                                  → Dashboard 仪表盘
/accounts/login/                   → 登录页 (校验 bsa_permission 表权限)
/accounts/profile/                 → 个人信息

/budget/versions/                  → 版本列表
/budget/versions/create/           → 创建新版本
/budget/versions/<id>/edit/        → 预算编辑主页面 (Pivot 表格)
/budget/versions/<id>/compare/<id2>/ → 版本对比

/budget/api/cell/save/             → [POST] 单元格保存 (AJAX)
/budget/api/row/data/              → [GET]  获取行数据 (AJAX, 懒加载)
/budget/api/summary/               → [GET]  汇总数据 (AJAX)

/import/template/download/         → CSV 模板下载 (选择版本后生成)
/import/upload/                    → CSV/Excel 上传页
/import/preview/<task_id>/         → 导入预览 (含校验结果展示)
/import/logs/                      → 导入历史记录

/reports/b1-vs-rebase/             → B1 vs Rebase 部门汇总表 (参考 003.jpg)
/reports/saving-detail/            → Saving 明细追踪表 (参考 004.jpg)
/reports/budget-heatmap/           → 月度预算执行率热力图
/reports/category-mix/             → 费用类别占比分析
/reports/yoy-comparison/           → YoY 同比分析
/reports/controllable/             → Controllable vs Non-Controllable
/reports/budgeter-status/          → Budgeter 工作负载看板
/reports/export/                   → 导出 CSV/Excel

/status/overview/                  → 部门编制状态看板 (管理员视图)
/status/submit/<version_id>/       → [POST] 预算员标记编制完成
/status/withdraw/<version_id>/     → [POST] 预算员撤回完成标记

/admin/                            → Django Admin 管理后台
```

### 4.6 核心页面交互设计

#### 4.6.1 预算编辑页面 (budget_edit.html)

这是系统最核心的页面，类似 Excel 的 Pivot 表格：

```
┌─────────────────────────────────────────────────────────────────────┐
│ 版本: fy26-B1 ▼  │ 数据类型: Spending ▼ │ 筛选: [Area][Dept][Cat] │
├───────┬──────┬────┬────────┬────────┬────────┬────────┬──────┬─────┤
│ 冻结列                     │ ← 可水平滚动 →                        │
├───────┬──────┬────┬────────┼────────┬────────┬────────┬──────┬─────┤
│ Dept  │ Cat  │ CC │ Account│ 202601 │ 202602 │ 202603 │ ...  │ 合计│
├───────┼──────┼────┼────────┼────────┼────────┼────────┼──────┼─────┤
│ MFG   │Indir │6922│ 515100 │[9,978] │[12,473]│[9,978] │ ...  │ xxx │
│       │Labor │    │        │  可编辑  │  可编辑  │  可编辑  │      │     │
├───────┼──────┼────┼────────┼────────┼────────┼────────┼──────┼─────┤
│ MFG   │...   │... │ ...    │  ...   │  ...   │  ...   │ ...  │ xxx │
├───────┴──────┴────┴────────┼────────┼────────┼────────┼──────┼─────┤
│ ▶ MFG 小计                 │ 合计值 │ 合计值  │ 合计值  │ ...  │ xxx │
├────────────────────────────┼────────┼────────┼────────┼──────┼─────┤
│ ▶ 总计                     │ 合计值 │ 合计值  │ 合计值  │ ...  │ xxx │
└────────────────────────────┴────────┴────────┴────────┴──────┴─────┘
```

- 单元格 `[值]` 可直接点击编辑，失焦后自动保存
- 小计/合计行自动计算更新
- 修改的单元格高亮显示

> Dashboard 与报表页面的详细交互设计见 3.5 和 3.6 节。

---

## 5. 数据流设计

### 5.1 CSV 导入流程

```
用户下载 CSV 模板 (/import/template/download/)
    │
    ▼
用户填写数据后上传 CSV
    │
    ▼
Django View 接收文件并保存到临时目录
    │
    ▼
importer/validators.py 执行校验:
  ├─ 基础校验 (必填、数值格式、重复行)
  ├─ at_var 字段校验 (必须为 0~1 小数)
  ├─ Volume 栏位顺序校验 (前序场景 → 当前场景)
  ├─ Volume 与 Spending 栏位数量一致性校验
  └─ 返回校验结果 (通过 / 错误列表)
    │
    ├─ [校验失败] → 展示错误卡片，用户修正后重新上传
    │
    ▼ [校验通过]
importer/services.py 解析数据并展示预览摘要
  └─ (N 行, M 个科目, 涉及部门列表)
    │
    ▼
用户确认导入
    │
    ▼
services.py 在单一 Transaction 中:
  ├─ 写入 bsa_main (PG: RETURNING id / MSSQL: SCOPE_IDENTITY)
  ├─ 自动计算 rebase_financeview (见 3.4.5)
  ├─ 批量写入各子表 (PG: execute_values / MSSQL: fast_executemany)
  └─ 写入 ImportLog
    │
    ▼
返回导入结果 (成功 N 笔, 失败 M 笔)
```

### 5.2 预算编辑流程 (AJAX 单元格保存)

```
用户修改单元格值
    │
    ▼
前端 JS 捕获 blur 事件
    │
    ▼
前端校验: 输入值是否为合法数字?
    │
    ├─ [非数字] → 单元格标红，Tooltip 提示"请输入数字"，恢复原值，不发送请求
    │
    ▼ [合法数字]
前端校验: 用户角色 + 栏位权限?
    │
    ├─ [Budgeter 编辑 rebase 栏位] → 阻止，提示"Rebase 栏位仅管理员可编辑"
    │
    ▼ [权限通过]
POST /budget/api/cell/save/
{
  "table": "bsa_spending",   // 或 bsa_saving / bsa_newadd / bsa_rebase_*
  "main_id": 123,
  "period": "fy26_202603",
  "value": 12500.00
}
    │
    ▼
Django View:
  ├─ 权限检查 (budgeter 匹配 + 版本未锁定 + 部门状态非 submitted)
  ├─ 栏位权限检查 (rebase 栏位仅 admin 角色可写)
  ├─ 数值合法性校验 (后端二次校验，防绕过前端)
  ├─ UPDATE or INSERT (upsert via db_compat.py)
  ├─ 联动计算:
  │   ├─ 如修改 spending → 自动重算 rebase_financeview (见 3.4.5)
  │   ├─ 如修改 saving  → rebase_financeview[i] 减去 saving[i] (见 3.4.9)
  │   └─ 如修改 newadd  → rebase_financeview[i] 加上 newadd[i] (见 3.4.9)
  ├─ 写入 AuditLog (旧值 → 新值)
  └─ 返回 {status: "ok", new_total: ..., updated_rebase: ...}
    │
    ▼
前端联动更新:
  ├─ 小计/合计行重新计算
  ├─ 如有 rebase 联动 → rebase 对应单元格更新显示新值
  └─ 已修改单元格高亮标识
```

### 5.3 Pivot 查询流程 (兼容双数据库)

```
用户选择 版本 + 筛选条件
    │
    ▼
Django View 调用 db_compat.build_pivot_query(version):
    │
    ├─ [PostgreSQL] → 调用 bsa_build_sql() PL/pgSQL 函数
    │                  返回动态 SQL → cursor.execute(sql)
    │
    └─ [SQL Server] → 使用 Django ORM 聚合查询
                       Python 端完成 pivot (行转列)
    │
    ▼
返回扁平化结果集 → 模板渲染为 HTML 表格 / DataTables 初始化
```

---

## 6. 非功能需求

### 6.1 性能
- 页面加载时间 < 3 秒 (含 5000 行以内数据)
- 单元格保存响应时间 < 500ms
- 大数据量表格使用分页或虚拟滚动
- 子表查询利用 `main_id` 索引

### 6.2 安全
- CSRF 保护 (Django 内建)
- XSS 防护 (Django 模板自动转义)
- SQL 注入防护 (ORM 参数化查询)
- 敏感操作日志记录
- 密码策略与登录失败锁定

### 6.3 兼容性
- 支持 Chrome、Edge、Firefox 最新版本
- 响应式布局（主要面向桌面端）

### 6.4 数据备份
- PostgreSQL: 定时 pg_dump
- SQL Server: 定时 BACKUP DATABASE 或 SQL Agent Job
- 版本锁定后数据不可修改

---

## 7. 部署架构

```
┌──────────────────────────────────────────────────────────────────┐
│                     生产环境 (Linux / Windows Server)              │
│                                                                  │
│  Nginx (443/80)  或  IIS (Windows 部署时)                         │
│    ├── 静态文件 /static/                                          │
│    └── 反向代理 → Gunicorn :8000 (Linux) / waitress (Windows)    │
│                                                                  │
│  Gunicorn / waitress (WSGI 服务器)                                │
│    └── Django Application                                        │
│                                                                  │
│  ┌──────────────────────────┐  ┌───────────────────────────────┐ │
│  │  PostgreSQL 15 (:5432)   │  │  SQL Server 2019+ (:1433)    │ │
│  │  └─ budget_system DB     │  │  └─ budget_system DB          │ │
│  │  (方案 A: 默认)           │  │  (方案 B: 企业环境)           │ │
│  └──────────────────────────┘  └───────────────────────────────┘ │
│              ↑ 二选一，通过 config.ini 配置文件切换                    │
│                                                                  │
│  (可选) Redis (:6379)                                             │
│    └── Django Cache / Session                                    │
└──────────────────────────────────────────────────────────────────┘
```

### 7.1 requirements.txt

```
Django>=4.2,<5.0
psycopg2-binary>=2.9
mssql-django>=1.4
pyodbc>=5.0
gunicorn>=21.0
waitress>=2.1
django-filter>=23.0
django-crispy-forms>=2.0
pandas>=2.0
openpyxl>=3.1
django-import-export>=3.3
whitenoise>=6.5
```

---

## 8. 开发里程碑

| 阶段 | 内容 |
|------|------|
| **Phase 1 - 基础框架** | Django 项目初始化、Models 建立、用户认证、Neo Brutalism 基础页面布局 |
| **Phase 2 - 数据导入** | CSV 模板下载、上传导入、Volume 栏位校验、at_var 校验、导入日志 |
| **Phase 3 - 预算编辑** | Pivot 表格展示、单元格编辑、自动汇总、Rebase Finance View 自动计算、AJAX 保存 |
| **Phase 4 - 报表** | B1 vs Rebase 汇总、Saving 明细、热力图、Category 占比、YoY 对比、Controllable 分析、Budgeter 看板 |
| **Phase 5 - 仪表盘** | Spend & Loading Trend 组合图、Budget Waterfall 瀑布图、指标卡片、附加图表 |
| **Phase 6 - 提交状态** | 部门编制完成标识、提交状态看板、通知机制、版本锁定 |
| **Phase 7 - 完善优化** | 权限细化、双数据库测试、性能优化、部署上线 |
