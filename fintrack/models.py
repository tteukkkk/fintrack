from datetime import datetime, date, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer,String,Text,ForeignKey,UniqueConstraint,Date,DateTime,Boolean,Index,BigInteger
from .db import Base

def now(): return datetime.now(timezone.utc).replace(tzinfo=None)
class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(120))
    email:Mapped[str]=mapped_column(String(254),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(300))
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now)
class Account(Base):
    __tablename__='accounts'
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(120))
    owner_id:Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'))
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now)
class Membership(Base):
    __tablename__='memberships'
    __table_args__=(UniqueConstraint('user_id','account_id'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'))
    account_id:Mapped[int]=mapped_column(ForeignKey('accounts.id',ondelete='CASCADE'))
    role:Mapped[str]=mapped_column(String(20),default='owner')
class LoginSession(Base):
    __tablename__='login_sessions'
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'))
    token_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True)
    csrf_hash:Mapped[str]=mapped_column(String(64))
    account_id:Mapped[int]=mapped_column(ForeignKey('accounts.id',ondelete='CASCADE'))
    expires_at:Mapped[datetime]=mapped_column(DateTime)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now)
class Category(Base):
    __tablename__='categories'
    __table_args__=(UniqueConstraint('account_id','kind','name'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    account_id:Mapped[int]=mapped_column(ForeignKey('accounts.id',ondelete='CASCADE'))
    name:Mapped[str]=mapped_column(String(80))
    kind:Mapped[str]=mapped_column(String(12))
    color:Mapped[str]=mapped_column(String(7),default='#8b5cf6')
class Transaction(Base):
    __tablename__='transactions'
    __table_args__=(UniqueConstraint('account_id','import_hash'),Index('ix_trans_account_date','account_id','posted_on'))
    id:Mapped[int]=mapped_column(primary_key=True)
    account_id:Mapped[int]=mapped_column(ForeignKey('accounts.id',ondelete='CASCADE'))
    category_id:Mapped[int]=mapped_column(ForeignKey('categories.id',ondelete='RESTRICT'))
    kind:Mapped[str]=mapped_column(String(12))
    amount_cents:Mapped[int]=mapped_column(BigInteger)
    description:Mapped[str]=mapped_column(String(160))
    posted_on:Mapped[date]=mapped_column(Date)
    method:Mapped[str]=mapped_column(String(24),default='outro')
    notes:Mapped[str]=mapped_column(Text,default='')
    import_hash:Mapped[str|None]=mapped_column(String(64),nullable=True)
    recurring_rule_id:Mapped[int|None]=mapped_column(ForeignKey('recurring_rules.id',ondelete='SET NULL'),nullable=True)
    scheduled_for:Mapped[date|None]=mapped_column(Date,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now)
    category:Mapped[Category]=relationship()
class Budget(Base):
    __tablename__='budgets'
    __table_args__=(UniqueConstraint('account_id','category_id','month'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    account_id:Mapped[int]=mapped_column(ForeignKey('accounts.id',ondelete='CASCADE'))
    category_id:Mapped[int]=mapped_column(ForeignKey('categories.id',ondelete='RESTRICT'))
    month:Mapped[str]=mapped_column(String(7))
    limit_cents:Mapped[int]=mapped_column(BigInteger)
    category:Mapped[Category]=relationship()
class Goal(Base):
    __tablename__='goals'
    id:Mapped[int]=mapped_column(primary_key=True)
    account_id:Mapped[int]=mapped_column(ForeignKey('accounts.id',ondelete='CASCADE'))
    name:Mapped[str]=mapped_column(String(120))
    target_cents:Mapped[int]=mapped_column(BigInteger)
    deadline:Mapped[date|None]=mapped_column(Date,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now)
class GoalContribution(Base):
    __tablename__='goal_contributions'
    id:Mapped[int]=mapped_column(primary_key=True)
    goal_id:Mapped[int]=mapped_column(ForeignKey('goals.id',ondelete='CASCADE'))
    amount_cents:Mapped[int]=mapped_column(BigInteger)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now)
class RecurringRule(Base):
    __tablename__='recurring_rules'
    id:Mapped[int]=mapped_column(primary_key=True)
    account_id:Mapped[int]=mapped_column(ForeignKey('accounts.id',ondelete='CASCADE'))
    category_id:Mapped[int]=mapped_column(ForeignKey('categories.id',ondelete='RESTRICT'))
    name:Mapped[str]=mapped_column(String(160))
    kind:Mapped[str]=mapped_column(String(12))
    amount_cents:Mapped[int]=mapped_column(BigInteger)
    cadence:Mapped[str]=mapped_column(String(12))
    anchor_day:Mapped[int]=mapped_column(Integer,default=1)
    next_run_on:Mapped[date]=mapped_column(Date)
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    category:Mapped[Category]=relationship()
class RecurringOccurrence(Base):
    __tablename__='recurring_occurrences'
    __table_args__=(UniqueConstraint('rule_id','scheduled_for'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    rule_id:Mapped[int]=mapped_column(ForeignKey('recurring_rules.id',ondelete='CASCADE'))
    scheduled_for:Mapped[date]=mapped_column(Date)
    transaction_id:Mapped[int]=mapped_column(ForeignKey('transactions.id',ondelete='CASCADE'))
class AuditEvent(Base):
    __tablename__='audit_events'
    id:Mapped[int]=mapped_column(primary_key=True)
    account_id:Mapped[int]=mapped_column(ForeignKey('accounts.id',ondelete='CASCADE'))
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='SET NULL'),nullable=True)
    action:Mapped[str]=mapped_column(String(70))
    target:Mapped[str]=mapped_column(String(140))
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now)
