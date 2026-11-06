import os,time,secrets,hashlib,base64,hmac
from urllib.parse import urlsplit,urlencode
import httpx,jwt
from fastapi import HTTPException
from sqlalchemy import select,update,delete
from app.models.entities import OidcState,ExternalIdentity,User,Token
from app.core.security import digest,issue,audit
from app.services.mfa_service import encrypt,decrypt,credential
def settings():
    issuer=os.getenv('OIDC_ISSUER','').rstrip('/');client=os.getenv('OIDC_CLIENT_ID','');redirect=os.getenv('OIDC_REDIRECT_URI','')
    if not all([issuer,client,redirect]):raise ValueError('OIDC_ISSUER, OIDC_CLIENT_ID and OIDC_REDIRECT_URI must be configured')
    for url in [issuer,redirect]:validate_endpoint(url)
    return issuer,client,redirect
def validate_endpoint(url):
    parsed=urlsplit(url)
    local=parsed.hostname in {'localhost','127.0.0.1','::1'} and os.getenv('APP_ENV','development')!='production'
    if parsed.username or parsed.password or not parsed.hostname or (parsed.scheme!='https' and not (local and parsed.scheme=='http')):raise ValueError('OIDC endpoints require HTTPS (loopback HTTP is development-only)')
def discovery():
    issuer,client,redirect=settings();response=httpx.get(issuer+'/.well-known/openid-configuration',timeout=15);response.raise_for_status();data=response.json()
    if data.get('issuer')!=issuer:raise ValueError('Discovery issuer mismatch')
    for name in ['authorization_endpoint','token_endpoint','jwks_uri']:validate_endpoint(data[name])
    return data
def start(db):
    issuer,client,redirect=settings();metadata=discovery();state=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(32);binding=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(64)
    db.execute(delete(OidcState).where(OidcState.expires<int(time.time())-600))
    db.add(OidcState(digest=digest(state),nonce_digest=digest(nonce),binding_digest=digest(binding),encrypted_verifier=encrypt(verifier),expires=int(time.time())+600));db.commit()
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    return metadata['authorization_endpoint']+'?'+urlencode({'client_id':client,'redirect_uri':redirect,'response_type':'code','scope':'openid email profile','state':state,'nonce':nonce,'code_challenge':challenge,'code_challenge_method':'S256'}),binding
def exchange(db,code,state,binding):
    issuer,client,redirect=settings()
    record=db.scalar(select(OidcState).where(OidcState.digest==digest(state),OidcState.expires>int(time.time()),OidcState.consumed==0))
    if not record or not binding or not hmac.compare_digest(record.binding_digest,digest(binding)):raise HTTPException(401,'Invalid, expired or browser-unbound SSO state')
    claimed=db.execute(update(OidcState).where(OidcState.id==record.id,OidcState.consumed==0).values(consumed=1))
    if claimed.rowcount!=1:raise HTTPException(401,'SSO state already consumed')
    verifier=decrypt(record.encrypted_verifier);nonce=record.nonce_digest;db.commit();metadata=discovery()
    body={'grant_type':'authorization_code','client_id':client,'redirect_uri':redirect,'code':code,'code_verifier':verifier}
    if os.getenv('OIDC_CLIENT_SECRET'):body['client_secret']=os.environ['OIDC_CLIENT_SECRET']
    response=httpx.post(metadata['token_endpoint'],data=body,timeout=20);response.raise_for_status();token=response.json()['id_token']
    header=jwt.get_unverified_header(token)
    if header.get('alg') not in {'RS256','ES256'}:raise ValueError('Unsupported ID-token signing algorithm')
    jwks=httpx.get(metadata['jwks_uri'],timeout=15);jwks.raise_for_status();keys=[k for k in jwks.json()['keys'] if k.get('kid')==header.get('kid') and k.get('use','sig')=='sig']
    if len(keys)!=1:raise ValueError('ID-token signing key not uniquely recognized')
    key=jwt.PyJWK.from_dict(keys[0],algorithm=header['alg']).key
    claims=jwt.decode(token,key,algorithms=[header['alg']],audience=client,issuer=issuer,leeway=30,options={'require':['iss','sub','aud','exp','iat','nonce']})
    if not hmac.compare_digest(digest(str(claims['nonce'])),nonce):raise ValueError('ID-token nonce mismatch')
    if (('azp' in claims or isinstance(claims['aud'],list) and len(claims['aud'])>1) and claims.get('azp')!=client):raise ValueError('ID-token authorized-party mismatch')
    identity=db.scalar(select(ExternalIdentity).where(ExternalIdentity.issuer==issuer,ExternalIdentity.subject==claims['sub']))
    if not identity:raise HTTPException(403,'This SSO identity has not been linked by your organization administrator')
    user=db.get(User,identity.user_id)
    if not user or user.org_id!=identity.org_id:raise HTTPException(401,'Invalid linked identity')
    mfa=credential(db,user)
    if mfa and mfa.enabled:
        value=secrets.token_urlsafe(48);db.add(Token(user_id=user.id,digest=digest(value),kind='oidc-mfa',expires=int(time.time())+300));db.commit();return {'mfa_required':True,'challenge_token':value}
    audit(db,user,'OIDC_LOGIN',user.id,{'issuer':issuer});db.commit();return issue(db,user)
