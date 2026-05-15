"""
Migration script to add last_symptom_analysis column to users table
"""
import asyncio
import aiosqlite

async def migrate():
    # Use the same database URL as your app
    db_path = r"C:\Users\K\OneDrive\Desktop\Медицинский асистент\med-telegram-bot\medical_bot.db"  # Adjust if your DB is elsewhere
    
    async with aiosqlite.connect(db_path) as db:
        try:
            # Check if column exists
            cursor = await db.execute("""
                PRAGMA table_info(users)
            """)
            columns = [row[1] for row in await cursor.fetchall()]
            
            if 'last_symptom_analysis' not in columns:
                print("Adding last_symptom_analysis column...")
                await db.execute("""
                    ALTER TABLE users ADD COLUMN last_symptom_analysis DATETIME
                """)
                await db.commit()
                print("Column added successfully!")
            else:
                print("Column already exists.")
            
        except Exception as e:
            print(f"Error during migration: {e}")
            await db.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(migrate())