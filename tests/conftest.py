from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from fintrack.db import Base,get_db
from fintrack.app import app
@pytest.fixture
def env(tmp_path):
    e=create_engine('sqlite:///'+str(tmp_path/'test.sqlite3'),connect_args={'check_same_thread':False})
    @event.listens_for(e,'connect')
    def enable_fk(conn,record):conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(e)
    Local=sessionmaker(bind=e,expire_on_commit=False)
    def db():
        with Local() as session:yield session
    app.dependency_overrides[get_db]=db
    with TestClient(app) as client:yield client,Local
    app.dependency_overrides.clear();e.dispose()
@pytest.fixture
def auth(env):
    c,Local=env
    resp=c.post('/api/auth/register',json={'name':'Alice Souza','email':'alice@example.test','password':'SenhaSegura2026','account_name':'Casa'})
    assert resp.status_code==200,resp.text
    s=c.get('/api/session').json()
    headers={'x-csrf-token':s['csrf']}
    return c,Local,headers,s
