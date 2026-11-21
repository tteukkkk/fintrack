import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
load_dotenv(Path(__file__).resolve().parent.parent / '.env')
DATABASE_URL = os.environ.get('FINTRACK_DATABASE_URL','sqlite:///./fintrack.sqlite3')
engine=create_engine(DATABASE_URL,connect_args={'check_same_thread':False,'timeout':30} if DATABASE_URL.startswith('sqlite') else {},pool_pre_ping=True)
if DATABASE_URL.startswith('sqlite'):
    @event.listens_for(engine,'connect')
    def fk(dbapi,record):
        cursor=dbapi.cursor();cursor.execute('PRAGMA foreign_keys=ON');cursor.execute('PRAGMA busy_timeout=30000');cursor.close()
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False,autoflush=False)
class Base(DeclarativeBase): pass
def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()
