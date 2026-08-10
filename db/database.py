from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, Integer, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from core.config import get_settings
import uuid, hashlib

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username     = Column(String, unique=True, nullable=False)
    email        = Column(String, unique=True, nullable=True)
    password_hash= Column(String, nullable=False)
    tier         = Column(String, default="free")  # free | pro | admin
    demo_balance = Column(Float, default=10000.0)
    real_balance = Column(Float, default=0.0)
    created_at   = Column(DateTime, default=datetime.utcnow)
    is_active    = Column(Boolean, default=True)
    tg_chat_id   = Column(String, nullable=True)
    tg_link_code = Column(String, nullable=True)
    reset_code   = Column(String, nullable=True)
    reset_expires= Column(Integer, nullable=True)

class Trade(Base):
    __tablename__ = "trades"
    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id      = Column(String, nullable=False)
    symbol       = Column(String, nullable=False)
    direction    = Column(String, nullable=False)  # LONG | SHORT
    trade_type   = Column(String, default="futures")  # futures | spot | meme
    account_type = Column(String, default="demo")  # demo | real
    entry_price  = Column(Float, nullable=False)
    close_price  = Column(Float, nullable=True)
    amount       = Column(Float, nullable=False)
    leverage     = Column(Integer, default=1)
    sl           = Column(Float, nullable=True)
    tp1          = Column(Float, nullable=True)
    tp2          = Column(Float, nullable=True)
    tp3          = Column(Float, nullable=True)
    pnl          = Column(Float, default=0.0)
    status       = Column(String, default="open")  # open | closed | cancelled
    gas_fee      = Column(Float, default=0.0)
    chain        = Column(String, default="sol")
    opened_at    = Column(DateTime, default=datetime.utcnow)
    closed_at    = Column(DateTime, nullable=True)

class Signal(Base):
    __tablename__ = "signals"
    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    radar_type   = Column(String, nullable=False)  # futures | spot | meme
    symbol       = Column(String, nullable=False)
    direction    = Column(String, nullable=False)
    grade        = Column(String, default="B")
    score        = Column(Float, default=0.0)
    confidence   = Column(Float, default=0.0)
    entry        = Column(Float, nullable=True)
    sl           = Column(Float, nullable=True)
    tp1          = Column(Float, nullable=True)
    tp2          = Column(Float, nullable=True)
    tp3          = Column(Float, nullable=True)
    leverage     = Column(Float, nullable=True)
    strategies   = Column(Text, default="")
    is_active    = Column(Boolean, default=True)
    pnl_pct      = Column(Float, nullable=True)
    close_reason = Column(String, nullable=True)
    closed_at    = Column(DateTime, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)

class Subscription(Base):
    __tablename__ = "subscriptions"
    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id      = Column(String, nullable=False)
    plan         = Column(String, default="pro")
    tx_hash      = Column(String, nullable=True)
    amount_paid  = Column(Float, default=50.0)
    expires_at   = Column(DateTime, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain: str, hashed: str) -> bool:
    return hash_password(plain) == hashed

def get_engine():
    s = get_settings()
    return create_engine(s.database_url, connect_args={"check_same_thread": False})

def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def create_tables():
    engine = get_engine()
    Base.metadata.create_all(engine)

def seed_admin():
    db = get_session()
    try:
        existing = db.query(User).filter(User.username == "admin").first()
        if not existing:
            admin = User(
                username="admin",
                email="admin@whalex.io",
                password_hash=hash_password("admin1234"),
                tier="admin",
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()
