from pymongo import MongoClient
import os
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
MONGO_URI = os.getenv('MONGO_URI', 'mongodb+srv://admin:admin@cluster0.ixdxvxl.mongodb.net/?retryWrites=true&w=majority')

try:
    # Connect to MongoDB
    logger.info("Connecting to MongoDB...")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000, connectTimeoutMS=20000, retryWrites=True, w='majority')
    client.admin.command('ping')
    db = client['fpt_learning']
    logger.info(f"Connected to MongoDB (DB: {db.name})")
    
    # List existing indexes on users collection
    logger.info("Checking existing indexes on users collection...")
    existing_indexes = list(db.users.list_indexes())
    
    # Check if email index exists
    email_index_exists = False
    for idx in existing_indexes:
        logger.info(f"Found index: {idx['name']}")
        if 'email_1' in idx['name'] or 'email_unique' in idx['name']:
            email_index_exists = True
            logger.info(f"Email index found: {idx['name']}")
    
    # If email_1 index exists but not email_unique, drop it and create the new one
    if email_index_exists:
        logger.info("Dropping existing email index...")
        try:
            db.users.drop_index('email_1')
            logger.info("Dropped email_1 index")
        except Exception as e:
            logger.warning(f"Could not drop email_1 index: {e}")
        
        try:
            db.users.drop_index('email_unique')
            logger.info("Dropped email_unique index")
        except Exception as e:
            logger.warning(f"Could not drop email_unique index: {e}")
    
    # Create the email_unique index
    logger.info("Creating email_unique index...")
    db.users.create_index([("email", 1)], unique=True, name="email_unique")
    logger.info("Email index created successfully")
    
    # Verify indexes
    logger.info("Current indexes on users collection:")
    for idx in db.users.list_indexes():
        logger.info(f"Index: {idx['name']}")
    
    logger.info("Index fix completed successfully")
    
except Exception as e:
    logger.error(f"Error: {e}")
