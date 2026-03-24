"""SQLAlchemy engine, session factory, and Base configuration."""
import configparser
import logging
from pathlib import Path
from contextlib import contextmanager
from urllib.parse import quote_plus

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

# Read config.ini
cfg = configparser.ConfigParser()
cfg.read(BASE_DIR / 'config.ini', encoding='utf-8')

DB_ENGINE = cfg.get('database', 'engine', fallback='postgresql')
DB_NAME = cfg.get('database', 'name', fallback='budget_system')
DB_HOST = cfg.get('database', 'host', fallback='localhost')
DB_PORT = cfg.get('database', 'port', fallback='5432')
DB_USER = cfg.get('database', 'user', fallback='postgres')
DB_PASSWORD = cfg.get('database', 'password', fallback='')

if DB_ENGINE == 'mssql':
    # 使用 pymssql 驱动连接 SQL Server，无需安装 ODBC 驱动
    SQLALCHEMY_DATABASE_URL = (
        f'mssql+pymssql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}'
        f'@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    )
else:
    SQLALCHEMY_DATABASE_URL = (
        f'postgresql+psycopg2://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}'
        f'@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    )

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


@contextmanager
def get_db():
    """Provide a transactional database session scope."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """
    初始化数据库：创建不存在的表，并为已存在的表补齐缺失的列。
    在 Django 启动时自动调用（通过 AppConfig.ready）。
    """
    # 导入所有 model，确保 Base.metadata 包含全部表定义
    import apps.budget.models       # noqa: F401
    import apps.accounts.models     # noqa: F401
    import apps.status.models       # noqa: F401

    # 1. 创建不存在的表
    Base.metadata.create_all(bind=engine)
    logger.info('Database tables verified/created.')

    # 2. 为已存在的表补齐缺失的列
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    for table_name, table_obj in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue  # 新表已由 create_all 创建

        existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
        model_columns = {col.name for col in table_obj.columns}
        missing_columns = model_columns - existing_columns

        if not missing_columns:
            continue

        logger.warning(
            'Table %s is missing columns: %s — adding them now.',
            table_name, ', '.join(sorted(missing_columns)),
        )

        with engine.begin() as conn:
            for col_name in missing_columns:
                col = table_obj.c[col_name]
                col_type = col.type.compile(dialect=engine.dialect)
                nullable = 'NULL' if col.nullable else 'NOT NULL'

                # 构建 DEFAULT 子句
                default_clause = ''
                if not col.nullable and col.default is not None:
                    # 对于 NOT NULL 列，必须提供 DEFAULT 才能 ALTER TABLE ADD
                    default_clause = " DEFAULT ''"
                elif not col.nullable:
                    # NOT NULL 但无 default，用 GETDATE() 处理 datetime 类型
                    type_str = str(col_type).upper()
                    if 'DATE' in type_str or 'TIME' in type_str:
                        default_clause = ' DEFAULT GETDATE()'
                    else:
                        default_clause = " DEFAULT ''"

                sql = f'ALTER TABLE [{table_name}] ADD [{col_name}] {col_type} {nullable}{default_clause}'
                logger.info('  Running: %s', sql)
                conn.execute(text(sql))
