from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from app.db.database import get_db
from app.models.entities import ChatSession,ChatTurn,Chunk
from app.core.security import current_user,owned,audit
from app.api.routes import serialize
from app.schemas.requests import Search
from app.services.hybrid_retrieval_service import search
from app.services.chat_service import answer
router=APIRouter(prefix='/api/conversations')
@router.post('',status_code=201)
def create(data:dict,user=Depends(current_user),db=Depends(get_db)):
    title=data.get('title','Evidence conversation')
    if not isinstance(title,str) or not 1<=len(title)<=200:raise HTTPException(422,'Title must be 1–200 characters')
    row=ChatSession(org_id=user.org_id,user_id=user.id,title=title);db.add(row);db.flush();audit(db,user,'CHAT_SESSION_CREATE',row.id);db.commit();return serialize(row)
@router.get('')
def sessions(user=Depends(current_user),db=Depends(get_db)):
    return [serialize(x) for x in db.scalars(select(ChatSession).where(ChatSession.org_id==user.org_id,ChatSession.user_id==user.id).order_by(ChatSession.created_at.desc()).limit(100))]
def session(db,identifier,user):
    row=owned(db,ChatSession,identifier,user)
    if row.user_id!=user.id:raise HTTPException(404,'Conversation not found')
    return row
@router.get('/{identifier}')
def detail(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    row=session(db,identifier,user)
    return {**serialize(row),'turns':[serialize(x) for x in db.scalars(select(ChatTurn).where(ChatTurn.session_id==identifier,ChatTurn.org_id==user.org_id).order_by(ChatTurn.created_at))]}
@router.post('/{identifier}/messages')
def message(identifier:str,data:Search,user=Depends(current_user),db=Depends(get_db)):
    session(db,identifier,user)
    recent=list(db.scalars(select(ChatTurn).where(ChatTurn.session_id==identifier,ChatTurn.org_id==user.org_id).order_by(ChatTurn.created_at.desc()).limit(6)))
    context=[{'question':r.question,'answer':r.response['answer']} for r in reversed(recent)]
    refs=search(db,user.org_id,data.query,document_ids=data.document_ids,top_k=data.top_k,mode=data.mode)
    try:result=answer(data.query,refs,context)
    except Exception as exc:raise HTTPException(422,'Grounded response rejected: '+str(exc))
    result['evidence']=refs
    row=ChatTurn(org_id=user.org_id,session_id=identifier,user_id=user.id,question=data.query,response=result);db.add(row);db.flush();audit(db,user,'CHAT_TURN',row.id,{'source_count':len(refs)});db.commit();return serialize(row)
