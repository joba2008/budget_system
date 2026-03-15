# Budget System

基于 Django 4.2 + SQLAlchemy 的部门预算管理系统。项目围绕预算版本管理、模板导入、预算编制、提交流转、分析报表和仪表盘展开，当前实际代码位于 `budget_system/` 目录。

## 1. 项目结构

```text
budget_system/
├─ README.md
└─ budget_system/
   ├─ apps/
   │  ├─ accounts/      # 登录、角色、用户权限管理
   │  ├─ budget/        # 预算版本、预算编辑、AJAX 保存、重算
   │  ├─ dashboard/     # KPI 与图表看板
   │  ├─ importer/      # CSV / Excel 导入、预览、确认导入
   │  ├─ reports/       # 各类分析报表与导出
   │  └─ status/        # 部门提交状态跟踪
   ├─ config/
   │  ├─ database.py    # SQLAlchemy 数据库连接
   │  ├─ settings/
   │  │  ├─ base.py
   │  │  ├─ dev.py
   │  │  └─ prod.py
   │  └─ urls.py
   ├─ docs/
   │  └─ requirements_and_architecture.md
   ├─ templates/
   ├─ static/
   ├─ uploads/
   ├─ config.ini.example
   ├─ requirements.txt
   ├─ _table schema.txt
   ├─ _sql permission.txt
   └─ manage.py
```

## 2. 技术架构

- Web 框架：Django 4.2
- 业务数据访问：SQLAlchemy ORM
- 业务数据库：PostgreSQL 或 SQL Server
- Django 内部数据库：SQLite，仅用于 Django 自身必需配置
- 前端模板：Django Templates
- 静态资源：WhiteNoise
- 可选配置：LDAP、Redis（当前代码仅保留配置入口）

这个项目不是标准的“纯 Django ORM”结构。

- 业务表 `bsa_main`、`bsa_spending`、`bsa_rebase_financeview` 等都通过 SQLAlchemy 访问。
- `config/settings/base.py` 中的 `DATABASES` 仅供 Django 内部使用，业务数据不走 Django ORM。
- 登录态也不是 Django 默认 `auth_user`，而是 `apps.accounts.middleware.SessionAuthMiddleware` 基于 session 注入 `request.user`。

## 3. 主要功能

### 3.1 账户与权限

- 登录入口：`/accounts/login/`
- 用户角色：`admin`、`budgeter`、`viewer`
- 权限来源：`bsa_permission` 表
- 用户管理入口：`/accounts/users/`

当前登录逻辑的实际行为：

- 密码在代码中固定为 `0000`
- 用户名通过 `bsa_permission` 校验角色
- 如果用户名首次登录且表中不存在，会自动创建一条 `admin` 权限记录

这更像是当前阶段的内网原型登录方案，不适合作为正式生产认证方案。

### 3.2 预算版本与编辑

- 版本列表：`/budget/versions/`
- 编辑页面：`/budget/versions/<version_name>/edit/`
- 版本对比：`/budget/versions/<v1>/compare/<v2>/`

支持的数据视图：

- `overall`
- `rebase_financeview`
- `rebase_opsview`
- `saving`
- `newadd`
- `newadd_approved`
- `final_budget`

AJAX 接口：

- `POST /budget/api/cell/save/`：保存单元格
- `GET /budget/api/row/data/`：懒加载单行 period 数据
- `POST /budget/api/recalc-rebase/`：管理员批量重算 rebase

编辑权限规则：

- `admin`、`budgeter` 可以编辑 `spending`、`saving`、`newadd`、`newadd_approved`
- `rebase_*` 仅 `admin` 可调整
- `actual`、`volume_actual` 只读
- 如果部门状态已经进入 `under_review` 或 `complete`，预算员不能继续修改

### 3.3 数据导入

入口：

- 样例模板：`/import/sample.csv`
- 按版本下载模板：`/import/template/download/`
- 上传导入：`/import/upload/`
- 确认导入：`/import/confirm/`

支持格式：

- CSV
- Excel（`.xlsx` / `.xls`）

当前导入流程：

1. 上传文件
2. 解析表头与数据行
3. 按版本校验字段、数值和 volume 列规则
4. 生成预览
5. 将临时导入数据写入 `uploads/import_temp/`
6. 用户确认后执行入库

导入校验的关键约束来自 `apps/importer/validators.py`：

- 必须包含维度列，如 `version`、`area`、`dept`、`cc`、`glc`、`accounts`、`budgeter`
- `at_var` 必须为 0 到 1 之间的小数
- 所有 period 数值列必须是数字或空值
- `volume_<previous_scenario>_*` 列必须排在 `volume_<current_scenario>_*` 之前
- 各 scenario 的 `volume_*` 列数必须和 `spending_*` 列数一致

### 3.4 报表

入口前缀：`/reports/`

当前已实现报表：

- `b1-vs-rebase/`
- `saving-detail/`
- `budget-heatmap/`
- `category-mix/`
- `yoy-comparison/`
- `controllable/`
- `budgeter-status/`
- `export/`

### 3.5 Dashboard

- 首页：`/`
- 图表数据接口：`/api/chart-data/`

当前首页已实现：

- KPI 汇总：budget、actual、saving、B1 vs rebase
- Spend & Loading Trend
- Budget Waterfall
- 按版本与 `dept_ppt` 过滤

### 3.6 提交流程状态

入口前缀：`/status/`

- `overview/`：管理员查看全局提交状态
- `update/`：管理员直接更新部门状态
- `submit/<version_name>/`：预算员或管理员提交审核
- `withdraw/<version_name>/`：预算员撤回提交

状态值：

- `not_started`
- `editing`
- `under_review`
- `complete`

## 4. 数据模型

核心主表：

- `bsa_main`

按 `period` 拆分的子表：

- `bsa_volume_actual`
- `bsa_volume`
- `bsa_actual`
- `bsa_spending`
- `bsa_rebase_financeview`
- `bsa_rebase_opsview`
- `bsa_saving`
- `bsa_newadd`
- `bsa_newadd_approved`
- `bsa_final_budget`

辅助表：

- `bsa_permission`：用户与角色
- `bsa_submission_status`：部门提交状态

版本信息没有独立版本表，直接从 `bsa_main.version` 去重得到。

## 5. 环境要求

- Python 3.10+
- PostgreSQL 或 SQL Server
- SQL Server 模式下需要可用的 ODBC Driver（默认读取 `ODBC Driver 17 for SQL Server`）

## 6. 安装与启动

### 6.1 安装依赖

在仓库根目录执行：

```powershell
cd .\budget_system
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 6.2 配置文件

复制配置模板：

```powershell
Copy-Item .\config.ini.example .\config.ini
```

然后按实际环境修改：

```ini
[app]
secret_key = your-django-secret-key
debug = true
allowed_hosts = localhost,127.0.0.1

[database]
engine = postgresql
name = budget_system
host = localhost
port = 5432
user = postgres
password =

[ldap]
enabled = false

[redis]
enabled = false
```

数据库配置说明：

- `engine = postgresql` 时走 `psycopg2`
- `engine = mssql` 时走 `pyodbc`
- `driver` 仅在 SQL Server 模式下使用，默认是 `ODBC Driver 17 for SQL Server`

### 6.3 初始化数据库

这个项目当前没有为业务表提供自动建表命令，也没有通过 Django migrations 管理核心业务表。

你需要先准备业务数据库：

- SQL Server 建表可参考 [`budget_system/_table schema.txt`](./budget_system/_table%20schema.txt)
- 权限初始化示例可参考 [`budget_system/_sql permission.txt`](./budget_system/_sql%20permission.txt)
- PostgreSQL 没有单独提供完整建表脚本，需按 SQLAlchemy 模型自行建表或基于现有库接入

注意：

- Django 的迁移只会覆盖 Django 自己的内部表，不会创建 `bsa_main` 等 SQLAlchemy 业务表
- 仓库中虽然存在 `apps/status/migrations/`，但当前 `status` 模块实际也是 SQLAlchemy 模型

如需初始化 Django 内部表，可执行：

```powershell
python manage.py migrate
```

### 6.4 本地运行

默认 `manage.py` 使用 `config.settings.dev`。

```powershell
python manage.py runserver
```

启动后访问：

- `http://127.0.0.1:8000/`

### 6.5 生产环境

生产配置文件为 `config.settings.prod`。本地验证生产配置时可以这样启动：

```powershell
$env:DJANGO_SETTINGS_MODULE="config.settings.prod"
python manage.py runserver
```

依赖中已包含：

- `waitress`
- `gunicorn`

如果使用 Waitress，可参考：

```powershell
$env:DJANGO_SETTINGS_MODULE="config.settings.prod"
waitress-serve --listen=0.0.0.0:8000 config.wsgi:application
```

但仓库当前没有提供完整的部署脚本、服务注册或反向代理配置。

## 7. 关键 URL

```text
/                          Dashboard
/accounts/login/           登录
/accounts/users/           用户权限管理
/budget/versions/          预算版本列表
/budget/versions/<v>/edit/ 预算编辑
/import/upload/            上传导入
/reports/*                 报表
/status/overview/          提交状态总览
```

## 8. 相关文档

- 需求与架构文档：[`budget_system/docs/requirements_and_architecture.md`](./budget_system/docs/requirements_and_architecture.md)
- 参考页面截图：`budget_system/reference/`

## 9. 当前实现边界

基于当前代码，下面这些点需要特别注意：

- 认证仍是简化方案，固定密码 `0000` 不适合直接上线
- LDAP 和 Redis 目前主要是配置占位，业务流程里没有完整接入
- 业务表依赖外部数据库预先建好，项目本身不会自动创建
- `request.user` 由自定义 middleware 注入，不依赖 Django 默认认证系统
- 预算核心逻辑集中在 `apps/budget/services.py`、`apps/importer/services.py`、`apps/reports/services.py`

## 10. 开发建议

- 先阅读 [`budget_system/docs/requirements_and_architecture.md`](./budget_system/docs/requirements_and_architecture.md)，再改核心计算逻辑
- 修改预算规则时优先检查 `apps/budget/services.py`
- 修改导入模板或校验规则时同步检查 `apps/importer/validators.py`
- 如果要推进生产化，优先替换当前登录机制，并补齐数据库初始化与部署脚本
