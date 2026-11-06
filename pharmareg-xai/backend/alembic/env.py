from alembic import context
from app.db.database import engine, Base
from app.models import entities
with engine.connect() as connection:
    context.configure(connection=connection,target_metadata=Base.metadata,compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
