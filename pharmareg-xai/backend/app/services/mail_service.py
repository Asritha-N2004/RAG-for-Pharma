"""Configured SMTP delivery; development outbox is managed by auth routes."""
import os,smtplib,ssl
from email.message import EmailMessage
def deliver_reset(address,token):
    if not os.getenv('SMTP_HOST'):raise ValueError('Production password recovery requires SMTP_HOST')
    message=EmailMessage();message['From']=os.environ['SMTP_FROM'];message['To']=address;message['Subject']='PharmaReg-XAI password recovery'
    message.set_content('A password reset was requested for your account. Token expires in 15 minutes.\n\n'+token+'\n\nIf you did not request this, disregard this message.')
    with smtplib.SMTP(os.environ['SMTP_HOST'],int(os.getenv('SMTP_PORT','587')),timeout=15) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        if os.getenv('SMTP_USER'):smtp.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD'])
        smtp.send_message(message)
