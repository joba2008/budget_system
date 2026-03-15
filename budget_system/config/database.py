"""SQLAlchemy engine, session factory, and Base configuration."""
import configparser
from pathlib import Path
from contextlib import contextmanager
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

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
