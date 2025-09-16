import asyncio
import logging
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from TEAMZYRO import backupmongo, mongo_url, OWNER_ID, app
from telegram import Bot
import os

LOGGER = logging.getLogger(__name__)

class AutoBackupSystem:
    def __init__(self):
        self.source_client = AsyncIOMotorClient(mongo_url)
        self.backup_client = AsyncIOMotorClient(backupmongo)
        self.source_db = self.source_client['gaming_create']
        self.backup_db_prefix = 'gaming_create'
        
    async def get_backup_db_name(self, date_str=None):
        """Generate backup database name with date"""
        if not date_str:
            date_str = datetime.now().strftime("%d_%m_%Y")
        return f"{self.backup_db_prefix}_{date_str}"
    
    async def check_last_backup(self):
        """Check when the last backup was created"""
        try:
            # List all databases to find backup databases
            db_list = await self.backup_client.list_database_names()
            backup_dbs = [db for db in db_list if db.startswith(self.backup_db_prefix + "_")]
            
            if not backup_dbs:
                LOGGER.info("No previous backups found")
                return None
                
            # Sort by date (assuming format: gaming_create_DD_MM_YYYY)
            backup_dates = []
            for db_name in backup_dbs:
                try:
                    date_part = db_name.replace(self.backup_db_prefix + "_", "")
                    backup_date = datetime.strptime(date_part, "%d_%m_%Y")
                    backup_dates.append((backup_date, db_name))
                except ValueError:
                    continue
                    
            if backup_dates:
                backup_dates.sort(reverse=True)  # Latest first
                latest_backup = backup_dates[0]
                LOGGER.info(f"Latest backup found: {latest_backup[1]} from {latest_backup[0].strftime('%d-%m-%Y')}")
                return latest_backup[0]
            
            return None
            
        except Exception as e:
            LOGGER.error(f"Error checking last backup: {e}")
            return None
    
    async def create_backup(self):
        """Create a new backup of the main database"""
        try:
            today = datetime.now()
            backup_db_name = await self.get_backup_db_name()
            
            LOGGER.info(f"Starting backup creation: {backup_db_name}")
            
            # Get all collections from source database
            collections = await self.source_db.list_collection_names()
            backup_db = self.backup_client[backup_db_name]
            
            total_docs = 0
            for collection_name in collections:
                source_collection = self.source_db[collection_name]
                backup_collection = backup_db[collection_name]
                
                # Get all documents from source collection
                documents = []
                async for doc in source_collection.find():
                    documents.append(doc)
                
                if documents:
                    await backup_collection.insert_many(documents)
                    total_docs += len(documents)
                    LOGGER.info(f"Backed up {len(documents)} documents from {collection_name}")
            
            LOGGER.info(f"Backup completed: {backup_db_name} with {total_docs} total documents")
            
            # Send notification to owner
            await self.send_backup_notification(backup_db_name, total_docs, len(collections))
            
            return True
            
        except Exception as e:
            LOGGER.error(f"Error creating backup: {e}")
            await self.send_error_notification(str(e))
            return False
    
    async def cleanup_old_backups(self):
        """Keep only last 3 days of backups, delete older ones"""
        try:
            # Get current date and calculate cutoff (3 days ago)
            today = datetime.now()
            cutoff_date = today - timedelta(days=3)
            
            # List all backup databases
            db_list = await self.backup_client.list_database_names()
            backup_dbs = [db for db in db_list if db.startswith(self.backup_db_prefix + "_")]
            
            deleted_count = 0
            for db_name in backup_dbs:
                try:
                    date_part = db_name.replace(self.backup_db_prefix + "_", "")
                    backup_date = datetime.strptime(date_part, "%d_%m_%Y")
                    
                    # If backup is older than 3 days, delete it
                    if backup_date < cutoff_date:
                        await self.backup_client.drop_database(db_name)
                        deleted_count += 1
                        LOGGER.info(f"Deleted old backup: {db_name}")
                        
                except ValueError:
                    # Skip databases with invalid date format
                    continue
            
            if deleted_count > 0:
                LOGGER.info(f"Cleanup completed: Deleted {deleted_count} old backups")
            else:
                LOGGER.info("No old backups to delete")
                
        except Exception as e:
            LOGGER.error(f"Error during backup cleanup: {e}")
    
    async def send_backup_notification(self, backup_name, total_docs, collections_count):
        """Send backup success notification to owner"""
        try:
            bot = Bot(token=os.getenv('TOKEN') or '7392456702:AAEPBt5qkAaP5edIg5_wP3kI00ERdeoH3KA')
            
            message = f"""
🔄 **Auto Backup Completed Successfully!**

📅 **Backup Name:** `{backup_name}`
📊 **Total Documents:** `{total_docs:,}`
📁 **Collections Backed Up:** `{collections_count}`
⏰ **Time:** `{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}`

✅ Your database is safely backed up!
🗂️ Last 3 days of backups are maintained automatically.
            """
            
            await bot.send_message(chat_id=OWNER_ID, text=message, parse_mode='Markdown')
            LOGGER.info("Backup notification sent to owner")
            
        except Exception as e:
            LOGGER.error(f"Error sending backup notification: {e}")
    
    async def send_error_notification(self, error_msg):
        """Send backup error notification to owner"""
        try:
            bot = Bot(token=os.getenv('TOKEN') or '7392456702:AAEPBt5qkAaP5edIg5_wP3kI00ERdeoH3KA')
            
            message = f"""
❌ **Auto Backup Failed!**

🚨 **Error:** `{error_msg}`
⏰ **Time:** `{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}`

⚠️ Please check the logs and fix the issue.
            """
            
            await bot.send_message(chat_id=OWNER_ID, text=message, parse_mode='Markdown')
            LOGGER.error("Backup error notification sent to owner")
            
        except Exception as e:
            LOGGER.error(f"Error sending error notification: {e}")

# Global backup system instance
backup_system = AutoBackupSystem()

async def initialize_backup_system():
    """Initialize and run the backup system on bot startup"""
    try:
        LOGGER.info("Initializing Auto Backup System...")
        
        # Check last backup
        last_backup = await backup_system.check_last_backup()
        today = datetime.now().date()
        
        should_backup = False
        
        if last_backup is None:
            LOGGER.info("No previous backup found, creating first backup...")
            should_backup = True
        else:
            last_backup_date = last_backup.date()
            if last_backup_date < today:
                LOGGER.info(f"Last backup was on {last_backup_date}, creating new backup for today...")
                should_backup = True
            else:
                LOGGER.info(f"Backup already exists for today ({today})")
        
        if should_backup:
            # Create new backup
            success = await backup_system.create_backup()
            if success:
                # Cleanup old backups after successful backup
                await backup_system.cleanup_old_backups()
        
        LOGGER.info("Auto Backup System initialized successfully")
        
    except Exception as e:
        LOGGER.error(f"Error initializing backup system: {e}")

# Task to run backup check daily
async def daily_backup_task():
    """Daily task to check and create backups"""
    while True:
        try:
            # Wait for 24 hours
            await asyncio.sleep(24 * 60 * 60)  # 24 hours in seconds
            
            # Run backup check
            await initialize_backup_system()
            
        except Exception as e:
            LOGGER.error(f"Error in daily backup task: {e}")
            await asyncio.sleep(60 * 60)  # Wait 1 hour before retrying

# Start the backup system when module is imported
async def start_backup_system():
    """Start the backup system"""
    # Initialize backup system on startup
    await initialize_backup_system()
    
    # Start daily backup task
    asyncio.create_task(daily_backup_task())

# Auto-start backup system
asyncio.create_task(start_backup_system())

LOGGER.info("Auto Backup Module Loaded Successfully! 🔄")
