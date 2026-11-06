import os,time
from fastapi import APIRouter,Depends,HTTPException,Response,Request
from sqlalchemy import select,update
from sqlalchemy.exc import IntegrityError
from app.db.database import get_db
from app.models.entities import ExternalIdentity,User,Token
from app.core.security import current_user,permit,owned,audit,issue,digest
from app.services import oidc_service
from app.services.mfa_service import verify
from app.api.routes import serialize
router=APIRouter(prefix='/api/auth/oidc')
@router.get('/config')
def config():
    return {'enabled':all(os.getenv(k) for k in ['OIDC_ISSUER','OIDC_CLIENT_ID','OIDC_REDIRECT_URI']),'label':os.getenv('OIDC_LABEL','Organization SSO')}
@router.get('/start')
def start(response:Response,db=Depends(get_db)):
    try:url,binding=oidc_service.start(db)
    except Exception as exc:raise HTTPException(503,'SSO unavailable: '+str(exc))
    response.set_cookie('pharmareg_oidc',binding,max_age=600,httponly=True,secure=os.getenv('APP_ENV')=='production',samesite='lax',path='/api/auth/oidc')
    return {'authorization_url':url}
@router.post('/exchange')
def exchange(data:dict,request:Request,response:Response,db=Depends(get_db)):
    if not all(isinstance(data.get(k),str) and 1<=len(data[k])<=5000 for k in ['code','state']):raise HTTPException(422,'SSO code and state required')
    try:result=oidc_service.exchange(db,data['code'],data['state'],request.cookies.get('pharmareg_oidc',''))
    except HTTPException:raise
    except Exception:raise HTTPException(401,'SSO token validation or exchange failed')
    response.delete_cookie('pharmareg_oidc',path='/api/auth/oidc');return result
@router.post('/mfa')
def complete_mfa(data:dict,db=Depends(get_db)):
    row=db.scalar(select(Token).where(Token.digest==digest(str(data.get('challenge_token',''))),Token.kind=='oidc-mfa',Token.revoked==0,Token.expires>int(time.time())))
    if not row:raise HTTPException(401,'SSO MFA challenge invalid or expired')
    user=db.get(User,row.user_id)
    if not verify(db,user,data.get('code')):raise HTTPException(401,'Invalid authenticator or recovery code')
    claimed=db.execute(update(Token).where(Token.id==row.id,Token.revoked==0).values(revoked=1))
    if claimed.rowcount!=1:raise HTTPException(401,'Challenge consumed')
    audit(db,user,'OIDC_MFA_LOGIN',user.id);db.commit();return issue(db,user)
@router.get('/links')
def links(user=Depends(current_user),db=Depends(get_db)):
    permit(user,{'System Administrator'})
    return [serialize(x) for x in db.scalars(select(ExternalIdentity).where(ExternalIdentity.org_id==user.org_id))]
@router.post('/links',status_code=201)
def link(data:dict,user=Depends(current_user),db=Depends(get_db)):
    permit(user,{'System Administrator'});target=owned(db,User,str(data.get('user_id','')),user)
    try:issuer,_,_=oidc_service.settings()
    except ValueError as exc:raise HTTPException(422,str(exc))
    subject=data.get('subject')
    if not isinstance(subject,str) or not 1<=len(subject)<=500:raise HTTPException(422,'Provider subject must be 1–500 characters')
    row=ExternalIdentity(org_id=user.org_id,user_id=target.id,issuer=issuer,subject=subject);db.add(row)
    try:db.flush()
    except IntegrityError:db.rollback();raise HTTPException(409,'Identity already linked')
    audit(db,user,'OIDC_IDENTITY_LINK',row.id,{'user_id':target.id,'issuer':issuer});db.commit();return serialize(row)
@router.delete('/links/{identifier}')
def unlink(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    permit(user,{'System Administrator'});row=owned(db,ExternalIdentity,identifier,user);db.delete(row);audit(db,user,'OIDC_IDENTITY_UNLINK',identifier);db.commit();return {'ok':True}
