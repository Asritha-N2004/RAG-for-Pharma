import hashlib, secrets, time
import jwt
from argon2 import PasswordHasher
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from app.db.database import get_db
from app.models.entities import User, Token, Audit
from app.core.config import SECRET_KEY

hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)
REVIEW_ROLES = {'System Administrator', 'Regulatory Affairs Specialist', 'Quality Assurance Manager', 'Compliance Auditor'}
WRITE_ROLES = REVIEW_ROLES | {'Document Manager'}
ROLES = WRITE_ROLES | {'Standard User'}
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def issue(db, user):
    result = {}
    for kind, lifetime in [('access', 1800), ('refresh', 604800)]:
        token = jwt.encode({'sub':user.id, 'kind':kind, 'exp':int(time.time())+lifetime, 'jti':secrets.token_hex(24)}, SECRET_KEY, algorithm='HS256')
        db.add(Token(user_id=user.id, digest=digest(token), kind=kind, expires=int(time.time())+lifetime))
        result[kind+'_token'] = token
    db.commit()
    return {**result, 'token_type':'bearer'}
def resolve(db, token, kind='access'):
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'], options={'require':['exp','sub','kind','jti']})
        record = db.scalar(select(Token).where(Token.digest == digest(token), Token.revoked == 0, Token.kind == kind))
        if not record or data['kind'] != kind: raise ValueError()
        user = db.get(User, data['sub'])
        if not user: raise ValueError()
        return user, record
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, 'Invalid or expired session')
def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db=Depends(get_db)):
    if not credentials: raise HTTPException(401, 'Login required')
    return resolve(db, credentials.credentials)[0]
def permit(user, roles=WRITE_ROLES):
    if user.role not in roles: raise HTTPException(403, 'Role is not authorized for this operation')
def owned(db, model, identifier, user):
    row = db.scalar(select(model).where(model.id == identifier, model.org_id == user.org_id))
    if row is None: raise HTTPException(404, 'Record not found')
    return row
def audit(db, user, action, target, details=None):
    from app.services.audit_service import append
    append(db,user,action,target,details)
