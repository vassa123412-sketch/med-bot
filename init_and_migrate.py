import asyncio
from core.database import init_db
import sys
sys.path.append(r'C:\Users\K\OneDrive\Desktop\Медицинский асистент\med-telegram-bot')
async def main():
    await init_db()
    print("Database initialized")
    # Now run migration
    from migrate import migrate
    await migrate()
if __name__ == "__main__":
    asyncio.run(main())