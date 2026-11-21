from alembic import context

from app import models  # register all application tables
from app.db import Base, DATABASE_URL, engine


if context.is_offline_mode():
    context.configure(url=DATABASE_URL, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    def run(connection):
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

    supplied_connection = context.config.attributes.get("connection")
    if supplied_connection is not None:
        run(supplied_connection)
    else:
        with engine.connect() as connection:
            run(connection)
