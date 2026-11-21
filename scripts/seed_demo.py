"""Dados totalmente fictícios para demonstração local. Nunca usar em produção."""
import sys,random,os,calendar
from pathlib import Path
from datetime import date,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from sqlalchemy import select
from fintrack.db import Base,engine,SessionLocal,DATABASE_URL
from fintrack.models import User,Account,Membership,Category,Transaction,Budget,Goal,GoalContribution,RecurringRule
from fintrack.security import hash_password
if not DATABASE_URL.startswith('sqlite') or os.environ.get('FINTRACK_HTTPS_ONLY')=='1':
    raise SystemExit('O seed de demonstração só pode rodar em SQLite local, sem modo de produção.')
Base.metadata.create_all(engine)
random.seed(29)
with SessionLocal() as db:
    mail='demo@fintrack.example.com'
    if db.scalar(select(User).where(User.email==mail)):
        print('Dados fictícios já presentes. Nenhuma alteração realizada.');raise SystemExit(0)
    user=User(name='Matheus Demo',email=mail,password_hash=hash_password('DemoSeguro#2026'));db.add(user);db.flush()
    account=Account(name='Minhas finanças',owner_id=user.id);db.add(account);db.flush()
    db.add(Membership(user_id=user.id,account_id=account.id,role='owner'))
    defs=[('Alimentação','expense','#f97373'),('Moradia','expense','#8b5cf6'),('Transporte','expense','#f59e0b'),('Saúde','expense','#22c55e'),('Lazer','expense','#06b6d4'),('Assinaturas','expense','#ec4899'),('Educação','expense','#64748b'),('Outros','expense','#a1a1aa'),('Salário','income','#22c55e'),('Freelance','income','#8b5cf6'),('Investimentos','income','#06b6d4'),('Outras receitas','income','#a1a1aa')]
    cats={}
    for name,kind,color in defs:
        c=Category(account_id=account.id,name=name,kind=kind,color=color);db.add(c);db.flush();cats[name]=c.id
    month=date.today().replace(day=1)
    for d in range(6,-1,-1):
        year=month.year;mo=month.month-d
        while mo<1:year-=1;mo+=12
        daymax=calendar.monthrange(year,mo)[1]
        start=date(year,mo,1)
        incomes=[('Salário mensal','Salário',620000,5),('Projeto freelance','Freelance',random.randint(500,2000)*100,random.randint(12,18))]
        if d%2==0:incomes.append(('Rendimentos','Investimentos',random.randint(170,350)*100,20))
        expenses=[('Aluguel','Moradia',185000,7),('Compras do mercado','Alimentação',random.randint(470,750)*100,10),('Supermercado e hortifruti','Alimentação',random.randint(180,330)*100,24),('Internet e celular','Assinaturas',12990,9),('Academia','Saúde',9900,12),('Combustível','Transporte',random.randint(130,290)*100,17),('Café e restaurante','Lazer',random.randint(80,180)*100,20),('Cursos online','Educação',random.randint(70,180)*100,26)]
        for desc,cat,amount,day in incomes:
            dt=date(year,mo,min(day,daymax))
            if dt<=date.today():db.add(Transaction(account_id=account.id,category_id=cats[cat],kind='income',amount_cents=amount,description=desc,posted_on=dt,method='pix'))
        for desc,cat,amount,day in expenses:
            dt=date(year,mo,min(day,daymax))
            if dt<=date.today():db.add(Transaction(account_id=account.id,category_id=cats[cat],kind='expense',amount_cents=amount,description=desc,posted_on=dt,method='cartao' if cat!='Moradia' else 'pix'))
    current=month.strftime('%Y-%m')
    for cat,v in [('Alimentação',120000),('Moradia',200000),('Transporte',38000),('Lazer',28000),('Assinaturas',20000)]:db.add(Budget(account_id=account.id,category_id=cats[cat],month=current,limit_cents=v))
    for name,target,saved,deadline in [('Viagem dos sonhos',1200000,834000,month+timedelta(days=240)),('Reserva de emergência',2500000,930000,None),('Novo notebook',850000,512000,month+timedelta(days=160))]:
        g=Goal(account_id=account.id,name=name,target_cents=target,deadline=deadline);db.add(g);db.flush();db.add(GoalContribution(goal_id=g.id,amount_cents=saved))
    db.add(RecurringRule(account_id=account.id,category_id=cats['Moradia'],name='Aluguel mensal',kind='expense',amount_cents=185000,cadence='monthly',anchor_day=(month+timedelta(days=35)).day,next_run_on=month+timedelta(days=35),active=True))
    db.add(RecurringRule(account_id=account.id,category_id=cats['Assinaturas'],name='Streaming',kind='expense',amount_cents=3990,cadence='monthly',anchor_day=(month+timedelta(days=35)).day,next_run_on=month+timedelta(days=35),active=True))
    db.commit()
    print('Ambiente fictício preparado: demo@fintrack.example.com | senha DemoSeguro#2026')
