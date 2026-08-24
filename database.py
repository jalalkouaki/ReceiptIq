import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import load_settings
from logger import log_event

try:
    import sqlcipher3
    SQLCIPHER_MODULE = sqlcipher3
except ImportError:  # pragma: no cover
    try:
        from pysqlcipher3 import dbapi2 as sqlcipher3
        SQLCIPHER_MODULE = sqlcipher3
    except ImportError:
        SQLCIPHER_MODULE = None

Base = declarative_base()

_engine = None
_SessionLocal = None


def get_db_url(db_path: str, encryption_key: str) -> str:
    """Generate SQLAlchemy connection URL for SQLCipher."""
    # Ensure Windows forward slashes or escaped path for SQLAlchemy URI
    clean_path = Path(db_path).resolve().as_posix()
    return f"sqlite+pysqlcipher://:{encryption_key}@/{clean_path}"


def init_db(db_path: str = None, encryption_key: str = None):
    global _engine, _SessionLocal
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
    cfg = load_settings()
    
    if not db_path:
        db_path = cfg.get("DB_PATH")
    if not encryption_key:
        encryption_key = os.environ.get("ENCRYPTION_KEY") or cfg.get("ENCRYPTION_KEY")

    if not encryption_key:
        raise ValueError("ENCRYPTION_KEY environment variable or setting is missing!")

    if SQLCIPHER_MODULE is None:
        raise RuntimeError("Neither sqlcipher3 nor pysqlcipher3 is available in python environment!")

    os.makedirs(Path(db_path).parent, exist_ok=True)
    db_url = get_db_url(db_path, encryption_key)

    _engine = create_engine(
        db_url,
        module=SQLCIPHER_MODULE,
        connect_args={"check_same_thread": False}
    )

    # Import models here to ensure metadata is populated
    import models  # noqa: F401
    Base.metadata.create_all(_engine)

    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    log_event("server", f"Initialized encrypted database at {db_path}", level="INFO")
    return _engine, _SessionLocal


def get_db_session():
    """Get a new database session."""
    global _SessionLocal
    if _SessionLocal is None:
        init_db()
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_db_encryption(db_path: str, encryption_key: str) -> bool:
    """Test if database can be created/opened with given passphrase."""
    if not encryption_key:
        return False
    if SQLCIPHER_MODULE is None:
        return False

    db_file = Path(db_path).resolve()
    db_exists = db_file.exists() and db_file.stat().st_size > 0

    try:
        # Direct raw DBAPI connection test
        conn = SQLCIPHER_MODULE.connect(str(db_file))
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA key = '{encryption_key}'")
        
        if db_exists:
            # Query sqlite_master to verify key decrypts the file
            cursor.execute("SELECT count(*) FROM sqlite_master;")
            cursor.fetchone()
        else:
            # Create a test table to test write capability
            cursor.execute("CREATE TABLE IF NOT EXISTS _enc_test (id INT);")
            conn.commit()

        conn.close()
        return True
    except Exception as e:
        log_event("error", f"Database encryption test failed: {e}", level="ERROR")
        return False
