import io,pytest
from datetime import date,timedelta
from fintrack.app import parse_money,next_occurrence
from fintrack.models import User,Account,Membership,Transaction,Budget,Category,Goal,RecurringOccurrence
from sqlalchemy import select,func
NOW=date.today().isoformat();MONTH=date.today().strftime('%Y-%m')
def cat(session,kind='expense',name=None):
    cs=session.get('/api/categories').json()
    return next(c['id'] for c in cs if c['kind']==kind and (name is None or c['name']==name))
def tx(c,h,category_id=None,kind='expense',amount=10000,date=NOW,description='Compras'):
    return c.post('/api/transactions',headers=h,json={'category_id':category_id or cat(c,kind),'kind':kind,'amount_cents':amount,'date':date,'description':description,'method':'pix'})
def test_register_and_session(auth):
    c,_,h,s=auth
    assert s['account']['name']=='Casa'
    assert len(c.get('/api/categories').json())>=10
    assert len(s['csrf'])>25

def test_login_invalid(env):
    c,_=env
    assert c.post('/api/auth/login',json={'email':'no@example.com','password':'incorrect'}).status_code==401

def test_unauthenticated(env):
    c,_=env
    assert c.get('/api/overview',params={'month':MONTH}).status_code==401

def test_csrf(auth):
    c,_,h,_=auth
    assert c.post('/api/transactions',json={}).status_code==403
    assert c.post('/api/transactions',headers={'x-csrf-token':'invalid'},json={}).status_code==403

def test_tx_and_month(auth):
    c,_,h,_=auth
    assert tx(c,h).status_code==200
    assert tx(c,h,kind='income',amount=20000).status_code==200
    r=c.get('/api/overview',params={'month':MONTH}).json()
    assert r['income_cents']==20000 and r['expense_cents']==10000 and r['net_cents']==10000
    assert len(c.get('/api/transactions').json()['items'])==2

def test_edit_and_delete(auth):
    c,_,h,_=auth
    ident=tx(c,h).json()['id']
    row={'description':'Mercado','kind':'expense','amount_cents':12000,'category_id':cat(c),'date':NOW,'method':'cartao','notes':'teste'}
    assert c.patch(f'/api/transactions/{ident}',headers=h,json=row).json()['amount_cents']==12000
    assert c.delete(f'/api/transactions/{ident}',headers=h).status_code==200
    assert c.patch(f'/api/transactions/{ident}',headers=h,json=row).status_code==404

def test_invalid_category_kind(auth):
    c,_,h,_=auth
    assert tx(c,h,category_id=cat(c,'income'),kind='expense').status_code==422

def test_cross_account_isolation(auth):
    c,_,h,_=auth
    first=tx(c,h).json()['id'];origcat=cat(c)
    second=c.post('/api/accounts',headers=h,json={'name':'Outra conta'}).json()['id']
    assert c.post(f'/api/accounts/{second}/switch',headers=h).status_code==200
    assert c.get('/api/transactions').json()['total']==0
    assert c.delete(f'/api/transactions/{first}',headers=h).status_code==404
    assert tx(c,h,category_id=origcat).status_code==422

def test_other_user_cannot_switch(env):
    c,_=env
    def register(email):
        c.post('/api/auth/register',json={'name':'Teste Pessoa','email':email,'password':'SenhaForte2026','account_name':'Minha conta'})
        s=c.get('/api/session').json();return s['account']['id'],{'x-csrf-token':s['csrf']}
    a,ha=register('a@test.local')
    b,hb=register('b@test.local')
    assert c.post(f'/api/accounts/{a}/switch',headers=hb).status_code==404

def test_budgets(auth):
    c,_,h,_=auth
    cid=cat(c)
    r=c.post('/api/budgets',headers=h,json={'month':MONTH,'category_id':cid,'limit_cents':20000});assert r.status_code==200
    assert tx(c,h,category_id=cid,amount=7500).status_code==200
    vals=c.get('/api/budgets',params={'month':MONTH}).json();assert vals[0]['spent_cents']==7500
    assert c.post('/api/budgets',headers=h,json={'month':MONTH,'category_id':cid,'limit_cents':15000}).status_code==200
    assert len(c.get('/api/budgets',params={'month':MONTH}).json())==1

def test_goals(auth):
    c,_,h,_=auth
    r=c.post('/api/goals',headers=h,json={'name':'Viagem','target_cents':100000,'deadline':None});assert r.status_code==200
    gid=r.json()['id'];assert c.post(f'/api/goals/{gid}/contributions',headers=h,json={'amount_cents':25000}).status_code==200
    assert c.get('/api/goals').json()[0]['saved_cents']==25000
    assert c.get('/api/overview',params={'month':MONTH}).json()['balance_cents']==0
    assert c.delete(f'/api/goals/{gid}',headers=h).status_code==200

def test_recurrence_generate_idempotent(auth):
    c,_,h,_=auth
    before=date.today()-timedelta(days=16)
    res=c.post('/api/recurrences',headers=h,json={'name':'Mensalidade','kind':'expense','category_id':cat(c),'amount_cents':2400,'cadence':'weekly','next_run_on':before.isoformat()});assert res.status_code==200
    first=c.post('/api/recurrences/run',headers=h).json()['created'];assert first>=3
    second=c.post('/api/recurrences/run',headers=h).json()['created'];assert second==0
    assert c.get('/api/transactions').json()['total']==first

def test_recurrence_toggle(auth):
    c,_,h,_=auth
    rid=c.post('/api/recurrences',headers=h,json={'name':'Conta','kind':'expense','category_id':cat(c),'amount_cents':2000,'cadence':'monthly','next_run_on':NOW}).json()['id']
    assert c.patch(f'/api/recurrences/{rid}',headers=h,json={'active':False}).status_code==200
    assert c.post('/api/recurrences/run',headers=h).json()['created']==0

def test_import_preview_and_duplicate(auth):
    c,_,h,_=auth
    content=f'data;tipo;descricao;valor;categoria;metodo\n{NOW};despesa;Mercado;15,90;Alimentação;pix\n{NOW};despesa;Mercado;15,90;Alimentação;pix\n'.encode()
    pre=c.post('/api/import/preview',headers=h,files={'file':('extrato.csv',content,'text/csv')})
    assert pre.status_code==200,pre.text
    rows=pre.json()['rows'];assert len(rows)==2 and rows[1]['duplicate']
    payload={k:rows[0][k] for k in ['date','kind','amount_cents','description','category_id','method','notes']}
    assert c.post('/api/import/commit',headers=h,json={'rows':[payload,payload]}).json()=={'inserted':1,'skipped':1}
    assert c.post('/api/import/commit',headers=h,json={'rows':[payload]}).json()['skipped']==1

def test_import_bad_csv(auth):
    c,_,h,_=auth
    r=c.post('/api/import/preview',headers=h,files={'file':('x.csv',b'nome;preco\nA;10','text/csv')});assert r.status_code==422

def test_import_negative_and_formula(auth):
    c,_,h,_=auth
    data=f'data;tipo;descricao;valor\n{NOW};despesa;=IMPORTRANGE();40,00\n'.encode()
    pre=c.post('/api/import/preview',headers=h,files={'file':('x.csv',data,'text/csv')})
    assert pre.status_code==200
    assert pre.json()['rows'][0]['description'].startswith('=')
    row={k:pre.json()['rows'][0][k] for k in ['date','kind','amount_cents','description','category_id','method','notes']}
    c.post('/api/import/commit',headers=h,json={'rows':[row]})
    output=c.get('/api/export/transactions',params={'start':NOW,'end':NOW})
    assert output.status_code==200 and "'=IMPORTRANGE()" in output.text

def test_export_csv(auth):
    c,_,h,_=auth
    tx(c,h);r=c.get('/api/export/transactions',params={'start':NOW,'end':NOW});assert r.status_code==200
    assert 'text/csv' in r.headers['content-type'] and 'Compras' in r.text

def test_reports(auth):
    c,_,h,_=auth
    tx(c,h,amount=2500);tx(c,h,kind='income',amount=10000)
    x=c.get('/api/reports',params={'start':NOW,'end':NOW}).json();assert x['net_cents']==7500 and x['count']==2

def test_validation(auth):
    c,_,h,_=auth
    assert tx(c,h,amount=-5).status_code==422
    assert c.get('/api/overview',params={'month':'2026-13'}).status_code==422
    assert c.post('/api/goals',headers=h,json={'name':'A','target_cents':-1}).status_code==422

def test_money_parsing():
    assert parse_money('1.234,50')==123450
    assert parse_money('1,234.50')==123450
    with pytest.raises(ValueError):parse_money('2,999')

def test_monthly_rollover():
    assert next_occurrence(date(2026,1,31),'monthly')==date(2026,2,28)
    assert next_occurrence(date(2024,1,31),'monthly')==date(2024,2,29)

def test_security_cookie(auth):
    c,_,h,_=auth
    assert c.cookies.get('fintrack_session')
    resp=c.post('/api/auth/logout',headers=h);assert resp.status_code==200
    assert c.get('/api/session').status_code==401


def test_recurring_month_day_anchor():
    from fintrack.app import next_occurrence
    feb=next_occurrence(date(2026,1,31),'monthly',31)
    assert feb==date(2026,2,28)
    assert next_occurrence(feb,'monthly',31)==date(2026,3,31)

def test_throttle_bad_login(env):
    from fintrack.app import FAILED_LOGINS
    c,_=env
    email='bruteforce-unique@example.test'
    FAILED_LOGINS.pop(email,None)
    for _ in range(5):assert c.post('/api/auth/login',json={'email':email,'password':'wrong'}).status_code==401
    assert c.post('/api/auth/login',json={'email':email,'password':'wrong'}).status_code==429
    FAILED_LOGINS.pop(email,None)

def test_transaction_detail_isolation(auth):
    c,_,h,_=auth
    tid=tx(c,h).json()['id']
    assert c.get(f'/api/transactions/{tid}').status_code==200
    new=c.post('/api/accounts',headers=h,json={'name':'Segunda conta'}).json()['id']
    c.post(f'/api/accounts/{new}/switch',headers=h)
    assert c.get(f'/api/transactions/{tid}').status_code==404


def test_invalid_year(auth):
    c,_,h,_=auth
    assert c.get('/api/overview',params={'month':'0000-01'}).status_code==422
