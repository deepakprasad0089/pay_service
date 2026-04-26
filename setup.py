from db import engine, SessionLocal
from models import Base, Event
import seed

Base.metadata.create_all(engine)

db = SessionLocal()


if not db.query(Event).first():
    seed.run()

db.close()

print("database ready")