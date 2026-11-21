"""Smoke test de UI: frontend real, chamadas encaminhadas à API FastAPI TestClient.
Uso opcional: pip install playwright; Chromium precisa estar instalado.
A navegação HTTP local é bloqueada no ambiente de captura, portanto usa ponte.
"""
import sys,re,tempfile,json
from pathlib import Path
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fintrack.app import app
from fintrack.db import Base,get_db
from datetime import date
CSS=re.sub(r'^@import[^\n]*\n','',(ROOT/'static/style.css').read_text(),count=1)
JS=(ROOT/'static/app.js').read_text()
html=(ROOT/'templates/app.html').read_text();html=re.sub(r'<link rel="stylesheet"[^>]*>','',html).replace('<script src="/static/app.js" defer></script>','').replace('</head>',f'<style>{CSS}</style></head>')
with tempfile.TemporaryDirectory() as tmp:
    e=create_engine('sqlite:///'+str(Path(tmp)/'smoke.db'),connect_args={'check_same_thread':False})
    @event.listens_for(e,'connect')
    def fk(conn,rec):conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(e)
    Local=sessionmaker(bind=e,expire_on_commit=False)
    def dep():
        with Local() as db:yield db
    app.dependency_overrides[get_db]=dep
    with TestClient(app) as c:
        r=c.post('/api/auth/register',json={'name':'Usuário Teste','email':'ui@fintrack.example.com','password':'TesteSeguro2026','account_name':'Minha carteira'})
        assert r.status_code==200,r.text
        # As requisições do JS utilizam a mesma sessão de teste.
        def api_bridge(path,method='GET',headers=None,body=None):
            kwargs={'headers':headers or {}}
            if body is not None:kwargs['content']=body
            res=c.request(method,path,**kwargs)
            try:data=res.json()
            except Exception:data={'raw':res.text}
            return {'status':res.status_code,'body':data}
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1350,'height':950});errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.expose_function('__apiBridge',api_bridge)
            page.set_content(html)
            page.evaluate('''() =>{
             const cache={};Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:key=>cache[key]||null,setItem:(k,v)=>cache[k]=v}});
             window.fetch=async (url,opts={})=>{
              const response=await window.__apiBridge(String(url),opts.method||'GET',opts.headers||{},typeof opts.body==='string'?opts.body:null);
              return new Response(JSON.stringify(response.body),{status:response.status,headers:{'Content-Type':'application/json'}});
             };
            }''')
            page.add_script_tag(content=JS)
            page.wait_for_selector('.kpi-card')
            page.locator('#newTxBtn').click();page.wait_for_selector('#modalSubmit')
            page.locator('#modalForm input[name=description]').fill('Café da manhã')
            page.locator('#modalForm input[name=amount]').fill('19,90')
            page.locator('#modalSubmit').click()
            page.wait_for_selector('.toast')
            page.locator('button[data-page="transactions"]').click();page.wait_for_selector('.data-table')
            assert 'Café da manhã' in page.locator('.data-table').inner_text()
            page.locator('button[data-page="budgets"]').click()
            page.locator('button[data-action="new-budget"]').first.click();page.wait_for_selector('#modalForm')
            page.locator('#modalForm input[name=amount]').fill('300.00');page.locator('#modalSubmit').click();page.wait_for_selector('.budget-card')
            page.locator('button[data-page="goals"]').click()
            page.locator('button[data-action="new-goal"]').first.click();page.wait_for_selector('#modalForm')
            page.locator('#modalForm input[name=name]').fill('Comprar notebook');page.locator('#modalForm input[name=amount]').fill('4200.00');page.locator('#modalSubmit').click();page.wait_for_selector('.goal-card')
            page.locator('.goal-card button[data-action=contribute-goal]').click();page.wait_for_selector('#modalForm');page.locator('#modalForm input[name=amount]').fill('50.00');page.locator('#modalSubmit').click();page.locator('.modal-backdrop').wait_for(state='detached');page.get_by_text('R$ 50,00 guardados').wait_for(timeout=3000)
            page.locator('#themeToggle').click();assert page.locator('html').get_attribute('data-theme')=='dark'
            assert not errors,errors
            print(json.dumps({'result':'ok','checks':['transaction-create','transaction-list','budget-create','goal-create','goal-contribute','theme-toggle'],'js_errors':errors},ensure_ascii=False))
            browser.close()
    app.dependency_overrides.clear();e.dispose()
