#!/usr/bin/env python3
# check_challenges.py
# Script to check challenges in MongoDB

import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import json_util

# Load environment variables
load_dotenv()

# Get MongoDB URI from environment variable
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    print("Error: MONGO_URI environment variable not set.")
    exit(1)

def check_challenges():
    try:
        # Connect to MongoDB
        print(f"Connecting to MongoDB...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')  # Test connection
        db = client['fpt_learning']  # Use the specific DB name
        print(f"Connected to MongoDB. Using database: {db.name}")

        # Count challenges
        challenge_count = db.challenges.count_documents({})
        print(f"Total challenges in database: {challenge_count}")

        # Get all challenges
        challenges = list(db.challenges.find({}))
        
        # Print challenge titles
        print("\nChallenge Titles:")
        for i, challenge in enumerate(challenges, 1):
            print(f"{i}. {challenge.get('title')} - {challenge.get('points')} points")

        # Print full details of the first challenge
        if challenges:
            print("\nDetails of first challenge:")
            # Convert ObjectId to string for JSON serialization
            challenge_json = json.loads(json_util.dumps(challenges[0]))
            print(json.dumps(challenge_json, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
    finally:
        # Close the connection
        if 'client' in locals():
            client.close()
            print("\nDisconnected from MongoDB")

if __name__ == "__main__":
    check_challenges()
