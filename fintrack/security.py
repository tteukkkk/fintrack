import re,secrets,hashlib
from datetime import datetime,timedelta
from fastapi import HTTPException
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError,VerificationError
ph=PasswordHasher(time_cost=2,memory_cost=32768,parallelism=2)
def sha(value): return hashlib.sha256(value.encode()).hexdigest()
def hash_password(p): return ph.hash(p)
def verify_password(p,h):
    try: return ph.verify(h,p)
    except (VerifyMismatchError,VerificationError):return False
def valid_password(p):
    if not isinstance(p,str) or len(p)<10 or len(p)>128 or not re.search(r'[A-Za-z]',p) or not re.search(r'\d',p):
        raise HTTPException(422,'Senha: 10 a 128 caracteres, incluindo letras e números.')
def text(value,length=160):
    if not isinstance(value,str):raise HTTPException(422,'Texto inválido.')
    return value.strip()[:length]
def csv_safe(s):
    s=str(s or '').replace('\r',' ').replace('\n',' ')
    return "'"+s if s.lstrip().startswith(('=','+','-','@','\t')) else s
