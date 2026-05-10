import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 当前目录
DB_PATH = os.path.join(BASE_DIR, "exam.db")            # 固定在 exam_system_backend 目录下

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# 依赖注入 - 获取数据库 Session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
