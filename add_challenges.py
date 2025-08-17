#!/usr/bin/env python3
# add_challenges.py
# Script to add new challenges to MongoDB

import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

# Get MongoDB URI from environment variable
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    print("Error: MONGO_URI environment variable not set.")
    exit(1)

# Define challenges data
challenges_data = [
    {
        "title": "Thử Thách Sáo Trúc: Bài Hát Dân Ca",
        "description": "Quay video thể hiện kỹ năng thổi sáo trúc với một bài hát dân ca Việt Nam tự chọn. Thời lượng tối thiểu 1 phút.",
        "points": 30,
        "thumbnail": "/assets/images/challenges/challenge_folk_song.jpg",
        "type": "practice_video",
        "active": True
    },
    {
        "title": "Thử Thách Đàn Tranh: Kỹ Thuật Rung Dây",
        "description": "Thực hiện và quay video kỹ thuật rung dây đàn tranh với 3 mức độ khác nhau: nhẹ, vừa và mạnh.",
        "points": 25,
        "thumbnail": "/assets/images/challenges/challenge_dan_tranh.jpg",
        "type": "practice_video",
        "active": True
    },
    {
        "title": "Thử Thách Vovinam: Đòn Chân Tấn Công",
        "description": "Thực hiện chính xác và quay video kỹ thuật đòn chân tấn công trong Vovinam. Chú ý đến tư thế, góc đá và lực.",
        "points": 35,
        "thumbnail": "/assets/images/challenges/challenge_vovinam_kick.jpg",
        "type": "practice_video",
        "active": True
    },
    {
        "title": "Thử Thách Lý Thuyết Âm Nhạc",
        "description": "Hoàn thành bài kiểm tra 15 câu hỏi về lý thuyết âm nhạc cơ bản, bao gồm các nốt nhạc, nhịp điệu và hòa âm.",
        "points": 20,
        "thumbnail": "/assets/images/challenges/challenge_music_theory.jpg",
        "type": "quiz",
        "active": True
    },
    {
        "title": "Thử Thách Sáng Tạo: Biến Tấu Giai Điệu",
        "description": "Tạo một biến tấu sáng tạo từ một giai điệu truyền thống và quay video trình diễn. Hãy giải thích cách bạn thay đổi giai điệu gốc.",
        "points": 40,
        "thumbnail": "/assets/images/challenges/challenge_creative.jpg",
        "type": "practice_video",
        "active": True
    },
    {
        "title": "Thử Thách Võ Thuật: Bài Quyền Cơ Bản",
        "description": "Thực hiện và quay video một bài quyền cơ bản trong võ thuật bạn đang học. Chú ý đến tư thế, nhịp điệu và sự chính xác của các động tác.",
        "points": 30,
        "thumbnail": "/assets/images/challenges/challenge_martial_form.jpg",
        "type": "practice_video",
        "active": True
    },
    {
        "title": "Thử Thách Flashcards: Thuật Ngữ Chuyên Ngành",
        "description": "Hoàn thành bài kiểm tra 20 flashcards về thuật ngữ chuyên ngành trong lĩnh vực bạn đang học (nhạc cụ hoặc võ thuật).",
        "points": 25,
        "thumbnail": "/assets/images/challenges/challenge_terminology.jpg",
        "type": "flashcard_test",
        "active": True
    }
]

def add_challenges():
    try:
        # Connect to MongoDB
        print(f"Connecting to MongoDB...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')  # Test connection
        db = client['fpt_learning']  # Use the specific DB name
        print(f"Connected to MongoDB. Using database: {db.name}")

        # Track results
        inserted = 0
        updated = 0
        errors = 0

        # Process each challenge
        print("Adding challenges to database...")
        for challenge in challenges_data:
            try:
                # Add createdAt if not present
                if 'createdAt' not in challenge:
                    challenge['createdAt'] = datetime.now(timezone.utc)

                # Check if challenge with same title already exists
                existing_challenge = db.challenges.find_one({'title': challenge['title']})

                if existing_challenge:
                    # Update existing challenge
                    result = db.challenges.update_one(
                        {'title': challenge['title']},
                        {'$set': challenge}
                    )

                    if result.modified_count > 0:
                        print(f"Updated challenge: {challenge['title']}")
                        updated += 1
                    else:
                        print(f"No changes needed for: {challenge['title']}")
                else:
                    # Insert new challenge
                    result = db.challenges.insert_one(challenge)
                    print(f"Added new challenge: {challenge['title']}")
                    inserted += 1
            except Exception as err:
                print(f"Error processing challenge '{challenge['title']}': {err}")
                errors += 1

        # Summary
        print("\nSummary:")
        print(f"- {inserted} challenges inserted")
        print(f"- {updated} challenges updated")
        print(f"- {errors} errors encountered")

    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
    finally:
        # Close the connection
        if 'client' in locals():
            client.close()
            print("Disconnected from MongoDB")

if __name__ == "__main__":
    add_challenges()
