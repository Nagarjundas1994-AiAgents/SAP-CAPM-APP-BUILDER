
import asyncio
from sqlalchemy import select
from backend.database import engine
from backend.models import Session
import json

async def check_session():
    async with engine.connect() as conn:
        result = await conn.execute(select(Session).where(Session.id == 'c96730dd-8707-4ae9-855b-938b46c6a51f'))
        session = result.fetchone()
        if session:
            print(f"Session ID: {session.id}")
            print(f"Status: {session.status}")
            config = json.loads(session.configuration) if isinstance(session.configuration, str) else session.configuration
            print(f"Keys in config: {list(config.keys())}")
            print(f"artifacts_db count: {len(config.get('artifacts_db', []))}")
            print(f"artifacts_srv count: {len(config.get('artifacts_srv', []))}")
            print(f"artifacts_app count: {len(config.get('artifacts_app', []))}")
            print(f"validation_errors count: {len(config.get('validation_errors', []))}")
            if config.get('validation_errors'):
                print(f"First error: {config.get('validation_errors')[0]}")
        else:
            print("Session not found")

if __name__ == "__main__":
    asyncio.run(check_session())
