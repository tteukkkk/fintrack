"""Capturas do frontend real com respostas gravadas da API real.
O Chromium deste ambiente bloqueia navegação HTTP, inclusive localhost. Por isso
esta ferramenta coleta snapshots de respostas via FastAPI TestClient e renderiza
os arquivos HTML/CSS/JS reais offline. Não representa execução online/deploy.
"""
import sys,re,json
from pathlib import Path
from datetime import date
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fintrack.app import app
PREV=ROOT/'previews';PREV.mkdir(exist_ok=True)
CSS=re.sub(r'^@import[^\n]*\n','',(ROOT/'static/style.css').read_text(),count=1)
# Valida a iluminação amarela do login antes de atualizar as capturas públicas.
assert 'rgba(144,102,246,.15)' not in CSS, 'Login ainda está com o brilho roxo antigo.'
assert 'rgba(255,228,83' in CSS, 'Não foi encontrada a iluminação amarela do login.'
JS=(ROOT/'static/app.js').read_text()
AUTHJS=(ROOT/'static/auth.js').read_text()
month=date.today().strftime('%Y-%m');from datetime import timedelta
start=month+'-01';end=date.today().isoformat()
with TestClient(app) as c:
    result=c.post('/api/auth/login',json={'email':'demo@fintrack.example.com','password':'DemoSeguro#2026'})
    assert result.status_code==200,result.text
    fixtures={
        '/api/session':c.get('/api/session').json(),
        '/api/categories':c.get('/api/categories').json(),
        '/api/overview':c.get('/api/overview',params={'month':month}).json(),
        '/api/transactions':c.get('/api/transactions',params={'month':month,'page':1,'per_page':100}).json(),
        '/api/budgets':c.get('/api/budgets',params={'month':month}).json(),
        '/api/goals':c.get('/api/goals').json(),
        '/api/recurrences':c.get('/api/recurrences').json(),
        '/api/reports':c.get('/api/reports',params={'start':start,'end':end}).json(),
        '/api/activity':c.get('/api/activity').json(),
    }
    print('Respostas da API:',len(fixtures['/api/transactions']['items']),'transações,',len(fixtures['/api/budgets']),'orçamentos')

def html_template(name):
    html=(ROOT/'templates'/name).read_text()
    html=re.sub(r'<link rel="stylesheet"[^>]*>','',html)
    html=re.sub(r'<script src="/static/(app|auth).js" defer></script>','',html)
    html=html.replace('</head>',f'<style>{CSS}</style></head>')
    return html

with sync_playwright() as pw:
    browser=pw.chromium.launch(**({'executable_path':'/usr/bin/chromium'} if Path('/usr/bin/chromium').exists() else {}),headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    issues=[]
    def capture_static(name,file,theme='light',w=1440,h=920):
        page=browser.new_page(viewport={'width':w,'height':h},device_scale_factor=1)
        page.on('pageerror',lambda exc:issues.append([name,str(exc)]))
        page.set_content(html_template(file),wait_until='domcontentloaded')
        page.evaluate('(v)=>document.documentElement.dataset.theme=v',theme)
        page.screenshot(path=str(PREV/(name+'.png')),full_page=True,animations='disabled')
        page.close();print(name,'capturado')
    capture_static('landing-claro','landing.html')
    capture_static('landing-escuro','landing.html','dark')
    capture_static('login-claro','auth.html')
    capture_static('login-escuro','auth.html','dark')
    capture_static('landing-mobile','landing.html','light',390,844)
    capture_static('landing-mobile-escuro','landing.html','dark',390,844)
    def app_capture(name,view='dashboard',theme='light',w=1440,h=920):
        page=browser.new_page(viewport={'width':w,'height':h},device_scale_factor=1,locale='pt-BR',reduced_motion='reduce')
        page.on('pageerror',lambda exc:issues.append([name,str(exc)]))
        page.set_content(html_template('app.html'),wait_until='domcontentloaded')
        page.evaluate('''(args)=>{
          const store={'fintrack-theme':args.theme};
          Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>store[k]||null,setItem:(k,v)=>store[k]=v,removeItem:k=>delete store[k]}});
          window.fetch=(resource,opts={})=>{
            const key=String(resource).split('?')[0];let response=args.fixtures[key];
            if(!response){response={detail:'Arquivo de prévia não contém esta resposta da API: '+key};return Promise.resolve(new Response(JSON.stringify(response),{status:404,headers:{'Content-Type':'application/json'}}));}
            return Promise.resolve(new Response(JSON.stringify(response),{status:200,headers:{'Content-Type':'application/json'}}));
          }
        }''',{'theme':theme,'fixtures':fixtures})
        page.evaluate('(theme)=>document.documentElement.dataset.theme=theme',theme)
        page.add_script_tag(content=JS)
        try:page.wait_for_selector('.kpi-card',timeout=6000)
        except Exception:
            print('DEBUG:',issues,page.locator('#pageContent').inner_text());raise
        if view!='dashboard':
            if w<680:
                page.locator('#mobileMenu').click()
            page.locator(f'[data-page="{view}"]').first.click()
            selectors={'transactions':'.data-table','budgets':'.budget-card','goals':'.goal-card','recurrences':'.recurrence-card','reports':'.report-summary','imports':'.import-upload','settings':'.settings-grid'}
            page.wait_for_selector(selectors[view],timeout=6000)
        page.wait_for_timeout(100)
        if w<680:
            sizes=page.evaluate('({scroll:document.documentElement.scrollWidth,inner:innerWidth,body:document.body.scrollWidth})');print('MOBILE',name,sizes)
        page.screenshot(path=str(PREV/(name+'.png')),full_page=True,animations='disabled')
        page.close();print(name,'capturado')
    app_capture('painel-claro')
    app_capture('painel-escuro',theme='dark')
    app_capture('lancamentos-claro','transactions')
    app_capture('lancamentos-escuro','transactions','dark')
    app_capture('orcamentos-claro','budgets')
    app_capture('orcamentos-escuro','budgets','dark')
    app_capture('metas-claro','goals')
    app_capture('metas-escuro','goals','dark')
    app_capture('recorrentes-claro','recurrences')
    app_capture('recorrentes-escuro','recurrences','dark')
    app_capture('relatorios-claro','reports')
    app_capture('relatorios-escuro','reports','dark')
    app_capture('importar-claro','imports')
    app_capture('importar-escuro','imports','dark')
    app_capture('configuracoes-claro','settings')
    app_capture('configuracoes-escuro','settings','dark')
    app_capture('painel-mobile','dashboard','light',390,844)
    app_capture('painel-mobile-escuro','dashboard','dark',390,844)
    app_capture('metas-mobile','goals','light',390,844)
    app_capture('metas-mobile-escuro','goals','dark',390,844)
    browser.close();print('ERROS_JS',issues)
    if issues:raise RuntimeError(str(issues))
