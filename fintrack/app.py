import os,csv,io,re,json,hashlib,secrets,calendar,unicodedata,time
from pathlib import Path
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from typing import Literal
from fastapi import FastAPI,Request,Depends,HTTPException,Response,UploadFile,File
from fastapi.responses import HTMLResponse,RedirectResponse,StreamingResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel,Field
from sqlalchemy import select,func,and_,or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import Base,engine,get_db
from .models import User,Account,Membership,LoginSession,Category,Transaction,Budget,Goal,GoalContribution,RecurringRule,RecurringOccurrence,AuditEvent
from .security import sha,hash_password,verify_password,valid_password,text,csv_safe
ROOT=Path(__file__).resolve().parent.parent
app=FastAPI(title='FinTrack',version='1.0.0',docs_url=None,redoc_url=None,openapi_url=None)
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
templates=Jinja2Templates(directory=ROOT/'templates')
Base.metadata.create_all(engine)
MAX=10**12
DEFAULTS=[('Alimentação','expense','#f97373'),('Moradia','expense','#8b5cf6'),('Transporte','expense','#f59e0b'),('Saúde','expense','#22c55e'),('Lazer','expense','#06b6d4'),('Assinaturas','expense','#ec4899'),('Educação','expense','#64748b'),('Outros','expense','#a1a1aa'),('Salário','income','#22c55e'),('Freelance','income','#8b5cf6'),('Investimentos','income','#06b6d4'),('Outras receitas','income','#a1a1aa')]
SECURE=os.environ.get('FINTRACK_HTTPS_ONLY','0')=='1'
SESSION_DAYS=14
FAILED_LOGINS={} # proteção básica em memória; produção exige Redis/WAF distribuído

def check_month(value):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',value or ''):raise HTTPException(422,'Mês inválido: use AAAA-MM.')
    return value

def month_bounds(month):
    month=check_month(month)
    y,m=map(int,month.split('-'))
    if y<1900 or y>2100:raise HTTPException(422,'Ano fora do intervalo permitido.')
    start=date(y,m,1)
    end=date(y+(m==12),(m%12)+1,1)
    return start,end

def number(value,allow_zero=False):
    if not isinstance(value,int) or isinstance(value,bool) or value< (0 if allow_zero else 1) or value>MAX:
        raise HTTPException(422,'Valor monetário inválido.')
    return value

def nonblank(s,size=150):
    out=text(s,size)
    if not out:raise HTTPException(422,'Este campo não pode estar vazio.')
    return out

def user_session(request:Request,db:Session=Depends(get_db)):
    token=request.cookies.get('fintrack_session','')
    if not token:raise HTTPException(401,'Faça login para continuar.')
    sess=db.scalar(select(LoginSession).where(LoginSession.token_hash==sha(token),LoginSession.expires_at>datetime.now(timezone.utc).replace(tzinfo=None)))
    if not sess:raise HTTPException(401,'Sessão expirada. Entre novamente.')
    user=db.get(User,sess.user_id)
    if not user:raise HTTPException(401,'Conta não encontrada.')
    member=db.scalar(select(Membership).where(Membership.user_id==user.id,Membership.account_id==sess.account_id))
    if not member:raise HTTPException(403,'Acesso à conta não autorizado.')
    return (user,sess,member)

def private(request:Request,auth=Depends(user_session)):
    incoming=request.headers.get('x-csrf-token','')
    if not incoming or not secrets.compare_digest(sha(incoming),auth[1].csrf_hash):raise HTTPException(403,'CSRF inválido. Atualize a página.')
    if request.headers.get('origin'):
        from urllib.parse import urlparse
        orig=urlparse(request.headers['origin'])
        if orig.netloc!=request.headers.get('host'):raise HTTPException(403,'Origem inválida.')
    return auth

def identify(auth):return auth[1].account_id

def category(db,account_id,cat_id,kind=None):
    c=db.scalar(select(Category).where(Category.id==cat_id,Category.account_id==account_id))
    if not c or (kind and c.kind!=kind):raise HTTPException(422,'Categoria inválida para esta conta ou tipo.')
    return c

def audit(db,auth,action,target):
    db.add(AuditEvent(account_id=identify(auth),user_id=auth[0].id,action=action,target=str(target)[:140]))

def set_auth(response,user,account,db):
    token=secrets.token_urlsafe(40);csrf=secrets.token_urlsafe(36)
    sess=LoginSession(user_id=user.id,account_id=account.id,token_hash=sha(token),csrf_hash=sha(csrf),expires_at=datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(days=SESSION_DAYS))
    db.add(sess);db.commit()
    response.set_cookie('fintrack_session',token,max_age=SESSION_DAYS*86400,httponly=True,secure=SECURE,samesite='lax',path='/')
    response.set_cookie('fintrack_csrf',csrf,max_age=SESSION_DAYS*86400,httponly=False,secure=SECURE,samesite='strict',path='/')

def serialize_tx(t):return dict(id=t.id,date=t.posted_on.isoformat(),kind=t.kind,amount_cents=t.amount_cents,description=t.description,category_id=t.category_id,category=t.category.name if t.category else '',color=t.category.color if t.category else '#8b5cf6',method=t.method,notes=t.notes or '',recurring=bool(t.recurring_rule_id))

def serialize_category(c):return dict(id=c.id,name=c.name,kind=c.kind,color=c.color)

def clean_user(u):return {'id':u.id,'name':u.name,'email':u.email}

def import_fingerprint(account_id,row):
    txt='|'.join([str(account_id),str(row['date']),row['kind'],str(row['amount_cents']),unicodedata.normalize('NFKC',row['description']).strip().casefold()])
    return hashlib.sha256(txt.encode()).hexdigest()

class RegisterIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    email:str=Field(min_length=5,max_length=254)
    password:str
    account_name:str=Field(min_length=2,max_length=120)
class LoginIn(BaseModel):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=1,max_length=128)
class CategoryIn(BaseModel):
    name:str=Field(min_length=1,max_length=80)
    kind:Literal['income','expense']
    color:str='#8b5cf6'
class TxIn(BaseModel):
    description:str=Field(min_length=1,max_length=160)
    kind:Literal['income','expense']
    amount_cents:int
    category_id:int
    date:date
    method:Literal['pix','cartao','dinheiro','transferencia','boleto','outro']='outro'
    notes:str=Field(default='',max_length=500)
class BudgetIn(BaseModel):
    month:str
    category_id:int
    limit_cents:int
class GoalIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    target_cents:int
    deadline:date|None=None
class ContributionIn(BaseModel):
    amount_cents:int
class RecurringIn(BaseModel):
    name:str=Field(min_length=2,max_length=160)
    kind:Literal['income','expense']
    category_id:int
    amount_cents:int
    cadence:Literal['weekly','monthly']
    next_run_on:date
class RecurrenceToggle(BaseModel):active:bool
class AccountIn(BaseModel):name:str=Field(min_length=2,max_length=120)
class ImportRow(BaseModel):
    date:date
    kind:Literal['income','expense']
    amount_cents:int
    description:str=Field(min_length=1,max_length=160)
    category_id:int
    method:Literal['pix','cartao','dinheiro','transferencia','boleto','outro']='outro'
    notes:str=Field(default='',max_length=500)
class CommitImport(BaseModel):rows:list[ImportRow]=Field(min_length=1,max_length=250)

@app.get('/',response_class=HTMLResponse)
def landing(request:Request):return templates.TemplateResponse('landing.html',{'request':request})
@app.get('/login',response_class=HTMLResponse)
def login_page(request:Request):return templates.TemplateResponse('auth.html',{'request':request})
@app.get('/app',response_class=HTMLResponse)
def app_page(request:Request,db:Session=Depends(get_db)):
    try:user_session(request,db)
    except HTTPException:return RedirectResponse('/login',status_code=302)
    return templates.TemplateResponse('app.html',{'request':request})

@app.post('/api/auth/register')
def register(data:RegisterIn,response:Response,db:Session=Depends(get_db)):
    valid_password(data.password)
    mail=data.email.lower().strip()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',mail):raise HTTPException(422,'E-mail inválido.')
    if db.scalar(select(User).where(User.email==mail)):raise HTTPException(409,'E-mail já cadastrado.')
    try:
        user=User(name=nonblank(data.name,120),email=mail,password_hash=hash_password(data.password));db.add(user);db.flush()
        acc=Account(name=nonblank(data.account_name,120),owner_id=user.id);db.add(acc);db.flush()
        db.add(Membership(user_id=user.id,account_id=acc.id,role='owner'))
        for name,kind,color in DEFAULTS:db.add(Category(account_id=acc.id,name=name,kind=kind,color=color))
        db.commit();set_auth(response,user,acc,db)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'E-mail já cadastrado.')
    return {'ok':True,'user':clean_user(user)}
@app.post('/api/auth/login')
def login(data:LoginIn,response:Response,db:Session=Depends(get_db)):
    email=data.email.lower().strip()
    key=email[:254]
    fails,ts=FAILED_LOGINS.get(key,(0,0.0))
    if time.monotonic()-ts>900:fails=0
    if fails>=5:raise HTTPException(429,'Muitas tentativas. Tente novamente mais tarde.')
    user=db.scalar(select(User).where(User.email==email))
    if not user or not verify_password(data.password,user.password_hash):
        FAILED_LOGINS[key]=(fails+1,time.monotonic())
        raise HTTPException(401,'E-mail ou senha inválidos.')
    FAILED_LOGINS.pop(key,None)
    member=db.scalar(select(Membership).where(Membership.user_id==user.id).order_by(Membership.id))
    if not member:raise HTTPException(403,'Conta sem espaço financeiro.')
    set_auth(response,user,db.get(Account,member.account_id),db)
    return {'ok':True,'user':clean_user(user)}
@app.post('/api/auth/logout')
def logout(response:Response,auth=Depends(private),db:Session=Depends(get_db)):
    db.delete(auth[1]);db.commit()
    response.delete_cookie('fintrack_session',path='/');response.delete_cookie('fintrack_csrf',path='/')
    return {'ok':True}
@app.get('/api/session')
def session_info(request:Request,auth=Depends(user_session),db:Session=Depends(get_db)):
    acc=db.get(Account,identify(auth));mine=db.scalars(select(Membership).where(Membership.user_id==auth[0].id)).all()
    return {'user':clean_user(auth[0]),'account':{'id':acc.id,'name':acc.name},'accounts':[{'id':m.account_id,'name':db.get(Account,m.account_id).name,'role':m.role} for m in mine], 'csrf':request.cookies.get('fintrack_csrf','')}
@app.post('/api/accounts')
def new_account(data:AccountIn,auth=Depends(private),db:Session=Depends(get_db)):
    account=Account(name=nonblank(data.name,120),owner_id=auth[0].id);db.add(account);db.flush();db.add(Membership(user_id=auth[0].id,account_id=account.id,role='owner'))
    for name,kind,color in DEFAULTS:db.add(Category(account_id=account.id,name=name,kind=kind,color=color))
    audit(db,auth,'account.create',account.name);db.commit()
    return {'id':account.id,'name':account.name}
@app.post('/api/accounts/{account_id}/switch')
def switch(account_id:int,auth=Depends(private),db:Session=Depends(get_db)):
    member=db.scalar(select(Membership).where(Membership.account_id==account_id,Membership.user_id==auth[0].id))
    if not member:raise HTTPException(404,'Conta não encontrada.')
    auth[1].account_id=account_id;db.commit();return {'ok':True}
@app.patch('/api/account')
def rename(data:AccountIn,auth=Depends(private),db:Session=Depends(get_db)):
    a=db.get(Account,identify(auth))
    if a.owner_id!=auth[0].id:raise HTTPException(403,'Somente proprietário pode alterar.')
    a.name=nonblank(data.name,120);audit(db,auth,'account.rename',a.name);db.commit();return {'name':a.name}

@app.get('/api/categories')
def categories(auth=Depends(user_session),db:Session=Depends(get_db)):
    return [serialize_category(c) for c in db.scalars(select(Category).where(Category.account_id==identify(auth)).order_by(Category.kind,Category.name))]
@app.post('/api/categories')
def new_category(data:CategoryIn,auth=Depends(private),db:Session=Depends(get_db)):
    if not re.fullmatch('#[0-9A-Fa-f]{6}',data.color):raise HTTPException(422,'Cor hexadecimal inválida.')
    c=Category(account_id=identify(auth),name=nonblank(data.name,80),kind=data.kind,color=data.color)
    db.add(c)
    try:db.flush();audit(db,auth,'category.create',c.name);db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Categoria já existente.')
    return serialize_category(c)

@app.get('/api/transactions')
def transactions(month:str|None=None,kind:str|None=None,category_id:int|None=None,q:str='',page:int=1,per_page:int=25,auth=Depends(user_session),db:Session=Depends(get_db)):
    if page<1 or not 1<=per_page<=100:raise HTTPException(422,'Paginação inválida.')
    query=select(Transaction).where(Transaction.account_id==identify(auth))
    if month:
        a,b=month_bounds(month);query=query.where(Transaction.posted_on>=a,Transaction.posted_on<b)
    if kind:
        if kind not in ('income','expense'):raise HTTPException(422,'Tipo inválido.')
        query=query.where(Transaction.kind==kind)
    if category_id:query=query.where(Transaction.category_id==category_id)
    if q:query=query.where(Transaction.description.ilike('%'+q[:100].replace('%','\\%').replace('_','\\_')+'%',escape='\\'))
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    records=db.scalars(query.order_by(Transaction.posted_on.desc(),Transaction.id.desc()).offset((page-1)*per_page).limit(per_page)).all()
    return {'items':[serialize_tx(t) for t in records],'total':total,'page':page,'per_page':per_page}
@app.get('/api/transactions/{tid}')
def get_transaction(tid:int,auth=Depends(user_session),db:Session=Depends(get_db)):
    t=db.scalar(select(Transaction).where(Transaction.id==tid,Transaction.account_id==identify(auth)))
    if not t:raise HTTPException(404,'Lançamento não encontrado.')
    return serialize_tx(t)

@app.post('/api/transactions')
def create_tx(data:TxIn,auth=Depends(private),db:Session=Depends(get_db)):
    number(data.amount_cents);c=category(db,identify(auth),data.category_id,data.kind)
    t=Transaction(account_id=identify(auth),category_id=c.id,kind=data.kind,amount_cents=data.amount_cents,posted_on=data.date,description=nonblank(data.description),method=data.method,notes=text(data.notes,500));db.add(t);db.flush();audit(db,auth,'transaction.create',t.id);db.commit()
    return serialize_tx(t)
@app.patch('/api/transactions/{tid}')
def change_tx(tid:int,data:TxIn,auth=Depends(private),db:Session=Depends(get_db)):
    t=db.scalar(select(Transaction).where(Transaction.account_id==identify(auth),Transaction.id==tid))
    if not t:raise HTTPException(404,'Lançamento não encontrado.')
    number(data.amount_cents);category(db,identify(auth),data.category_id,data.kind)
    t.category_id=data.category_id;t.kind=data.kind;t.amount_cents=data.amount_cents;t.posted_on=data.date;t.description=nonblank(data.description);t.method=data.method;t.notes=text(data.notes,500)
    t.import_hash=None
    audit(db,auth,'transaction.update',tid);db.commit();db.refresh(t);return serialize_tx(t)
@app.delete('/api/transactions/{tid}')
def delete_tx(tid:int,auth=Depends(private),db:Session=Depends(get_db)):
    t=db.scalar(select(Transaction).where(Transaction.account_id==identify(auth),Transaction.id==tid))
    if not t:raise HTTPException(404,'Lançamento não encontrado.')
    db.delete(t);audit(db,auth,'transaction.delete',tid);db.commit();return {'ok':True}

@app.get('/api/budgets')
def budgets(month:str,auth=Depends(user_session),db:Session=Depends(get_db)):
    a,b=month_bounds(month);account=identify(auth)
    spent=dict(db.execute(select(Transaction.category_id,func.sum(Transaction.amount_cents)).where(Transaction.account_id==account,Transaction.kind=='expense',Transaction.posted_on>=a,Transaction.posted_on<b).group_by(Transaction.category_id)).all())
    limits=db.scalars(select(Budget).where(Budget.account_id==account,Budget.month==month)).all()
    return [{'id':x.id,'month':x.month,'category_id':x.category_id,'category':x.category.name,'color':x.category.color,'limit_cents':x.limit_cents,'spent_cents':int(spent.get(x.category_id) or 0)} for x in limits]
@app.post('/api/budgets')
def put_budget(data:BudgetIn,auth=Depends(private),db:Session=Depends(get_db)):
    check_month(data.month);number(data.limit_cents);c=category(db,identify(auth),data.category_id,'expense')
    b=db.scalar(select(Budget).where(Budget.account_id==identify(auth),Budget.month==data.month,Budget.category_id==c.id))
    if b:b.limit_cents=data.limit_cents
    else:b=Budget(account_id=identify(auth),month=data.month,category_id=c.id,limit_cents=data.limit_cents);db.add(b)
    db.flush();audit(db,auth,'budget.upsert',b.id);db.commit();return {'id':b.id,'ok':True}
@app.delete('/api/budgets/{bid}')
def del_budget(bid:int,auth=Depends(private),db:Session=Depends(get_db)):
    b=db.scalar(select(Budget).where(Budget.account_id==identify(auth),Budget.id==bid))
    if not b:raise HTTPException(404,'Orçamento não encontrado.')
    db.delete(b);audit(db,auth,'budget.delete',bid);db.commit();return {'ok':True}

@app.get('/api/goals')
def goals(auth=Depends(user_session),db:Session=Depends(get_db)):
    goals=db.scalars(select(Goal).where(Goal.account_id==identify(auth)).order_by(Goal.id.desc())).all()
    return [dict(id=g.id,name=g.name,target_cents=g.target_cents,saved_cents=int(db.scalar(select(func.coalesce(func.sum(GoalContribution.amount_cents),0)).where(GoalContribution.goal_id==g.id)) or 0),deadline=g.deadline.isoformat() if g.deadline else None) for g in goals]
@app.post('/api/goals')
def create_goal(data:GoalIn,auth=Depends(private),db:Session=Depends(get_db)):
    number(data.target_cents);g=Goal(account_id=identify(auth),name=nonblank(data.name,120),target_cents=data.target_cents,deadline=data.deadline);db.add(g);db.flush();audit(db,auth,'goal.create',g.id);db.commit();return {'id':g.id,'ok':True}
@app.post('/api/goals/{gid}/contributions')
def contribute(gid:int,data:ContributionIn,auth=Depends(private),db:Session=Depends(get_db)):
    number(data.amount_cents)
    goal=db.scalar(select(Goal).where(Goal.id==gid,Goal.account_id==identify(auth)))
    if not goal:raise HTTPException(404,'Meta não encontrada.')
    current=int(db.scalar(select(func.coalesce(func.sum(GoalContribution.amount_cents),0)).where(GoalContribution.goal_id==gid)) or 0)
    if current+data.amount_cents>MAX:raise HTTPException(422,'Limite monetário excedido.')
    db.add(GoalContribution(goal_id=gid,amount_cents=data.amount_cents));audit(db,auth,'goal.contribute',gid);db.commit();return {'ok':True,'saved_cents':current+data.amount_cents}
@app.delete('/api/goals/{gid}')
def delete_goal(gid:int,auth=Depends(private),db:Session=Depends(get_db)):
    goal=db.scalar(select(Goal).where(Goal.id==gid,Goal.account_id==identify(auth)))
    if not goal:raise HTTPException(404,'Meta não encontrada.')
    db.delete(goal);audit(db,auth,'goal.delete',gid);db.commit();return {'ok':True}

def next_occurrence(day,cadence,anchor_day=None):
    if cadence=='weekly':return day+timedelta(days=7)
    year=day.year+(day.month==12);month=day.month%12+1
    return date(year,month,min(anchor_day or day.day,calendar.monthrange(year,month)[1]))
@app.get('/api/recurrences')
def recurrences(auth=Depends(user_session),db:Session=Depends(get_db)):
    return [dict(id=x.id,name=x.name,kind=x.kind,category=x.category.name,category_id=x.category_id,amount_cents=x.amount_cents,cadence=x.cadence,next_run_on=x.next_run_on.isoformat(),active=x.active) for x in db.scalars(select(RecurringRule).where(RecurringRule.account_id==identify(auth)).order_by(RecurringRule.id.desc()))]
@app.post('/api/recurrences')
def create_recurrence(data:RecurringIn,auth=Depends(private),db:Session=Depends(get_db)):
    number(data.amount_cents);category(db,identify(auth),data.category_id,data.kind)
    x=RecurringRule(account_id=identify(auth),category_id=data.category_id,name=nonblank(data.name),kind=data.kind,amount_cents=data.amount_cents,cadence=data.cadence,anchor_day=data.next_run_on.day,next_run_on=data.next_run_on,active=True);db.add(x);db.flush();audit(db,auth,'recurrence.create',x.id);db.commit();return {'id':x.id,'ok':True}
@app.patch('/api/recurrences/{rid}')
def toggle_recurrence(rid:int,data:RecurrenceToggle,auth=Depends(private),db:Session=Depends(get_db)):
    x=db.scalar(select(RecurringRule).where(RecurringRule.id==rid,RecurringRule.account_id==identify(auth)))
    if not x:raise HTTPException(404,'Recorrência não encontrada.')
    x.active=data.active;audit(db,auth,'recurrence.toggle',rid);db.commit();return {'ok':True}
@app.delete('/api/recurrences/{rid}')
def delete_recurrence(rid:int,auth=Depends(private),db:Session=Depends(get_db)):
    x=db.scalar(select(RecurringRule).where(RecurringRule.id==rid,RecurringRule.account_id==identify(auth)))
    if not x:raise HTTPException(404,'Recorrência não encontrada.')
    db.delete(x);audit(db,auth,'recurrence.delete',rid);db.commit();return {'ok':True}
@app.post('/api/recurrences/run')
def run_recurrences(auth=Depends(private),db:Session=Depends(get_db)):
    today=date.today();made=0
    for x in db.scalars(select(RecurringRule).where(RecurringRule.account_id==identify(auth),RecurringRule.active.is_(True))).all():
        loops=0
        while x.next_run_on<=today and loops<60:
            due=x.next_run_on
            found=db.scalar(select(RecurringOccurrence).where(RecurringOccurrence.rule_id==x.id,RecurringOccurrence.scheduled_for==due))
            if not found:
                t=Transaction(account_id=identify(auth),category_id=x.category_id,kind=x.kind,amount_cents=x.amount_cents,description=x.name,posted_on=due,method='outro',notes='Lançamento recorrente',recurring_rule_id=x.id,scheduled_for=due)
                db.add(t);db.flush();db.add(RecurringOccurrence(rule_id=x.id,scheduled_for=due,transaction_id=t.id));made+=1
            x.next_run_on=next_occurrence(due,x.cadence,x.anchor_day);loops+=1
        if loops==60 and x.next_run_on<=today: x.active=False
    audit(db,auth,'recurrence.generate',made);db.commit();return {'created':made,'until':today.isoformat()}

@app.get('/api/overview')
def overview(month:str,auth=Depends(user_session),db:Session=Depends(get_db)):
    start,end=month_bounds(month);aid=identify(auth)
    totals=dict(db.execute(select(Transaction.kind,func.sum(Transaction.amount_cents)).where(Transaction.account_id==aid,Transaction.posted_on>=start,Transaction.posted_on<end).group_by(Transaction.kind)).all())
    income=int(totals.get('income') or 0);expense=int(totals.get('expense') or 0)
    prev_balance_rows=db.execute(select(Transaction.kind,func.sum(Transaction.amount_cents)).where(Transaction.account_id==aid,Transaction.posted_on<end).group_by(Transaction.kind)).all();bals=dict(prev_balance_rows)
    balance=int(bals.get('income') or 0)-int(bals.get('expense') or 0)
    by_category=db.execute(select(Category.name,Category.color,func.sum(Transaction.amount_cents)).join(Category,Category.id==Transaction.category_id).where(Transaction.account_id==aid,Transaction.kind=='expense',Transaction.posted_on>=start,Transaction.posted_on<end).group_by(Category.id).order_by(func.sum(Transaction.amount_cents).desc())).all()
    months=[]
    for delta in range(5,-1,-1):
        y=start.year;m=start.month-delta
        while m<1:y-=1;m+=12
        dt=date(y,m,1);enddt=date(y+(m==12),m%12+1,1)
        parts=dict(db.execute(select(Transaction.kind,func.sum(Transaction.amount_cents)).where(Transaction.account_id==aid,Transaction.posted_on>=dt,Transaction.posted_on<enddt).group_by(Transaction.kind)).all())
        months.append({'month':dt.strftime('%Y-%m'),'income':int(parts.get('income') or 0),'expense':int(parts.get('expense') or 0)})
    recent=db.scalars(select(Transaction).where(Transaction.account_id==aid,Transaction.posted_on>=start,Transaction.posted_on<end).order_by(Transaction.posted_on.desc(),Transaction.id.desc()).limit(6)).all()
    budget_rows=budgets(month,auth,db)
    return {'month':month,'income_cents':income,'expense_cents':expense,'net_cents':income-expense,'balance_cents':balance,'transaction_count':int(db.scalar(select(func.count()).select_from(Transaction).where(Transaction.account_id==aid,Transaction.posted_on>=start,Transaction.posted_on<end)) or 0),'categories':[{'name':n,'color':c,'amount_cents':int(v)} for n,c,v in by_category],'months':months,'recent':[serialize_tx(x) for x in recent],'budgets':budget_rows}

@app.get('/api/reports')
def reports(start:date,end:date,auth=Depends(user_session),db:Session=Depends(get_db)):
    if start>end or (end-start).days>731:raise HTTPException(422,'Intervalo inválido (máximo de dois anos).')
    aid=identify(auth)
    txs=db.scalars(select(Transaction).where(Transaction.account_id==aid,Transaction.posted_on>=start,Transaction.posted_on<=end).order_by(Transaction.posted_on)).all()
    categories={};months={};income=expense=0
    for t in txs:
        mm=t.posted_on.strftime('%Y-%m');item=months.setdefault(mm,{'income_cents':0,'expense_cents':0})
        item[t.kind+'_cents']+=t.amount_cents
        if t.kind=='income':income+=t.amount_cents
        else:
            expense+=t.amount_cents
            c=categories.setdefault(t.category_id,{'name':t.category.name,'color':t.category.color,'amount_cents':0});c['amount_cents']+=t.amount_cents
    return {'income_cents':income,'expense_cents':expense,'net_cents':income-expense,'count':len(txs),'by_month':[{'month':m,**v} for m,v in sorted(months.items())],'by_category':sorted(categories.values(),key=lambda r:-r['amount_cents'])}

@app.get('/api/activity')
def activity(auth=Depends(user_session),db:Session=Depends(get_db)):
    return [{'action':e.action,'target':e.target,'created_at':e.created_at.isoformat()} for e in db.scalars(select(AuditEvent).where(AuditEvent.account_id==identify(auth)).order_by(AuditEvent.id.desc()).limit(25))]

@app.get('/api/export/transactions')
def export_transactions(start:date,end:date,auth=Depends(user_session),db:Session=Depends(get_db)):
    if start>end or (end-start).days>3650:raise HTTPException(422,'Intervalo inválido.')
    txs=db.scalars(select(Transaction).where(Transaction.account_id==identify(auth),Transaction.posted_on>=start,Transaction.posted_on<=end).order_by(Transaction.posted_on,Transaction.id)).all()
    data=io.StringIO();w=csv.writer(data,delimiter=';');w.writerow(['data','tipo','descricao','valor','categoria','metodo','observacao'])
    for t in txs:
        w.writerow([t.posted_on.isoformat(),t.kind,csv_safe(t.description),f'{Decimal(t.amount_cents)/100:.2f}'.replace('.',','),csv_safe(t.category.name),t.method,csv_safe(t.notes)])
    raw='\ufeff'+data.getvalue();return Response(raw,media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="fintrack-extrato.csv"','Cache-Control':'no-store'})

def parse_money(s):
    v=str(s).strip().replace('R$','').replace(' ','')
    if not v:raise ValueError('Valor vazio')
    if ',' in v and '.' in v:
        v=v.replace('.','').replace(',','.') if v.rfind(',')>v.rfind('.') else v.replace(',','')
    elif ',' in v:v=v.replace(',','.')
    try:amount=Decimal(v)
    except InvalidOperation:raise ValueError('Valor inválido')
    if not amount.is_finite() or amount<=0 or amount>Decimal(MAX)/100:raise ValueError('Valor fora do intervalo')
    if amount.as_tuple().exponent< -2:raise ValueError('Use no máximo duas casas decimais')
    return int((amount*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))

def normalize_type(s):
    s=str(s).lower().strip()
    return {'receita':'income','entrada':'income','income':'income','despesa':'expense','saida':'expense','saída':'expense','expense':'expense'}.get(s)

def normalize_date(s):
    s=str(s).strip()
    for pattern in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y'):
        try:return datetime.strptime(s,pattern).date()
        except ValueError:pass
    raise ValueError('Data inválida')

@app.post('/api/import/preview')
async def import_preview(file:UploadFile=File(...),auth=Depends(private),db:Session=Depends(get_db)):
    raw=await file.read(1024*1024+1)
    if len(raw)>1024*1024:raise HTTPException(413,'Arquivo CSV maior que 1 MB.')
    try:content=raw.decode('utf-8-sig')
    except UnicodeDecodeError:raise HTTPException(422,'Use CSV em UTF-8.')
    sample=content[:2000]
    try:delimiter=csv.Sniffer().sniff(sample,delimiters=';,\t').delimiter
    except csv.Error:delimiter=';'
    rows=csv.DictReader(io.StringIO(content),delimiter=delimiter)
    if not rows.fieldnames:raise HTTPException(422,'CSV sem cabeçalho.')
    if not {'data','tipo','descricao','valor'}.issubset({(x or '').strip().casefold() for x in rows.fieldnames}):raise HTTPException(422,'Colunas obrigatórias: data, tipo, descricao, valor.')
    cats=db.scalars(select(Category).where(Category.account_id==identify(auth))).all()
    lookup={(c.kind,c.name.casefold()):c for c in cats}
    others={c.kind:next((x for x in cats if x.kind==c.kind and x.name.casefold() in ('outros','outras receitas')),None) for c in cats}
    result=[];errors=[];seen=set()
    for i,r in enumerate(rows,2):
        if i>251:raise HTTPException(422,'Máximo de 250 linhas por importação.')
        try:
            row={(k or '').strip().casefold():str(v or '').strip() for k,v in r.items() if k is not None}
            kind=normalize_type(row.get('tipo'))
            if not kind:raise ValueError('Tipo deve ser receita ou despesa')
            cat=lookup.get((kind,row.get('categoria','').casefold())) or others.get(kind)
            if not cat:raise ValueError('Categoria padrão não encontrada')
            rowdata={'date':normalize_date(row.get('data')).isoformat(),'kind':kind,'description':nonblank(row.get('descricao'),160),'amount_cents':parse_money(row.get('valor')),'category_id':cat.id,'category':cat.name,'method':row.get('metodo','outro').lower() if row.get('metodo','outro').lower() in ('pix','cartao','dinheiro','transferencia','boleto','outro') else 'outro','notes':text(row.get('observacao',''),500)}
            digest=import_fingerprint(identify(auth),rowdata)
            exists=bool(db.scalar(select(Transaction.id).where(Transaction.account_id==identify(auth),Transaction.import_hash==digest)))
            rowdata['duplicate']=exists or digest in seen
            seen.add(digest);result.append(rowdata)
        except (ValueError,HTTPException) as e:errors.append({'line':i,'error':str(e.detail if isinstance(e,HTTPException) else e)})
    return {'rows':result,'errors':errors,'duplicates':sum(x['duplicate'] for x in result)}

@app.post('/api/import/commit')
def import_commit(data:CommitImport,auth=Depends(private),db:Session=Depends(get_db)):
    inserted=0;skipped=0;seen=set();aid=identify(auth)
    for row in data.rows:
        number(row.amount_cents);category(db,aid,row.category_id,row.kind)
        rd={'date':row.date.isoformat(),'kind':row.kind,'amount_cents':row.amount_cents,'description':nonblank(row.description)}
        digest=import_fingerprint(aid,rd)
        if digest in seen or db.scalar(select(Transaction.id).where(Transaction.account_id==aid,Transaction.import_hash==digest)):
            skipped+=1;continue
        seen.add(digest)
        db.add(Transaction(account_id=aid,category_id=row.category_id,kind=row.kind,amount_cents=row.amount_cents,posted_on=row.date,description=rd['description'],method=row.method,notes=text(row.notes,500),import_hash=digest));inserted+=1
    audit(db,auth,'import.csv',f'{inserted} inseridos, {skipped} repetidos')
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Conflito durante importação; tente novamente.')
    return {'inserted':inserted,'skipped':skipped}
