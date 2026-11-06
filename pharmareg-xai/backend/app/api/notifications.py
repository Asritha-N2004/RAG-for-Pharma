from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import select,func,update
from app.db.database import get_db
from app.models.entities import Notification,Setting,now
from app.core.security import current_user,owned,audit
from app.api.routes import serialize
from app.services.notification_service import sync,preferences
router=APIRouter(prefix='/api/notifications')
@router.get('')
def inbox(unread:bool=False,limit:int=Query(25,ge=1,le=200),offset:int=Query(0,ge=0),user=Depends(current_user),db=Depends(get_db)):
    sync(db,user);db.commit();conditions=[Notification.org_id==user.org_id,Notification.user_id==user.id]
    if unread:conditions.append(Notification.read_at.is_(None))
    total=db.scalar(select(func.count()).select_from(Notification).where(*conditions))
    unread_count=db.scalar(select(func.count()).select_from(Notification).where(Notification.org_id==user.org_id,Notification.user_id==user.id,Notification.read_at.is_(None)))
    return {'items':[serialize(x) for x in db.scalars(select(Notification).where(*conditions).order_by(Notification.created_at.desc(),Notification.id).offset(offset).limit(limit))],'total':total,'unread_count':unread_count,'limit':limit,'offset':offset}
@router.post('/read-all')
def read_all(user=Depends(current_user),db=Depends(get_db)):
    db.execute(update(Notification).where(Notification.org_id==user.org_id,Notification.user_id==user.id,Notification.read_at.is_(None)).values(read_at=now()));db.commit();return {'ok':True}
@router.post('/{identifier}/read')
def read(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    row=owned(db,Notification,identifier,user)
    if row.user_id!=user.id:raise HTTPException(404,'Notification not found')
    row.read_at=now();db.commit();return serialize(row)
@router.get('/preferences')
def prefs(user=Depends(current_user),db=Depends(get_db)):return preferences(db,user)
@router.patch('/preferences')
def update_preferences(data:dict,user=Depends(current_user),db=Depends(get_db)):
    if set(data)!={'due_in_days','pending_reviews','failed_jobs','enabled'} or type(data['due_in_days']) is not int or not 0<=data['due_in_days']<=90 or any(type(data[k]) is not bool for k in ['pending_reviews','failed_jobs','enabled']):raise HTTPException(422,'Supply due_in_days 0–90 and boolean notification preferences')
    row=db.scalar(select(Setting).where(Setting.org_id==user.org_id,Setting.key=='notifications:'+user.id))
    if row:row.value=data
    else:db.add(Setting(org_id=user.org_id,key='notifications:'+user.id,value=data))
    audit(db,user,'NOTIFICATION_PREFERENCES',user.id,data);db.commit();return data
