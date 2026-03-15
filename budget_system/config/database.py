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
    # driver 为可选配置，默认使用 ODBC Driver 17 for SQL Server
    # 如果安装了 ODBC Driver 18，可在 config.ini 中指定: driver = ODBC Driver 18 for SQL Server
    DB_DRIVER = cfg.get('database', 'driver', fallback='ODBC Driver 17 for SQL Server')
    SQLALCHEMY_DATABASE_URL = (
        f'mssql+pyodbc://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}'
        f'@{DB_HOST}:{DB_PORT}/{DB_NAME}'
        f'?driver={quote_plus(DB_DRIVER)}'
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
