# backend/init.py
from pymongo import MongoClient
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from bson import ObjectId # Needed if referencing ObjectIds, though not strictly needed for seeding here

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    print("Error: MONGO_URI environment variable not set.")
    exit(1)

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping') # Test connection
    db = client['fpt_learning'] # Use the specific DB name
    print(f"Connected to MongoDB. Using database: {db.name}")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    exit(1)

print("\n--- Seeding Data (Upsert Mode) ---")

# --- Seed Courses ---
courses_data = [
    {'category': 'instruments', 'title': 'Sáo Trúc Cơ Bản', 'description': 'Khóa học nhập môn về cách cầm sáo, thổi hơi và các nốt cơ bản.', 'video_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ', 'thumbnail': '/assets/images/courses/sao_truc_cb.jpg'},
    {'category': 'instruments', 'title': 'Kỹ Thuật Láy Sáo', 'description': 'Nâng cao kỹ thuật chơi sáo với các kỹ thuật láy hơi, rung hơi.', 'video_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ', 'thumbnail': '/assets/images/courses/sao_truc_nc.jpg'},
    {'category': 'instruments', 'title': 'Đàn Tranh Nhập Môn', 'description': 'Tìm hiểu cấu tạo đàn tranh và cách gảy các dây cơ bản.', 'video_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ', 'thumbnail': '/assets/images/courses/dan_tranh_cb.jpg'},
    {'category': 'martial-arts', 'title': 'Vovinam Căn Bản', 'description': 'Các thế tấn, đòn tay, đòn chân và bài quyền nhập môn Vovinam.', 'video_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ', 'thumbnail': '/assets/images/courses/vovinam_cb.jpg'},
    {'category': 'martial-arts', 'title': 'Chiến Lược Vovinam', 'description': 'Phân tích các đòn thế chiến lược và đối kháng trong Vovinam.', 'video_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ', 'thumbnail': '/assets/images/courses/vovinam_cl.jpg'}
]
print("\nUpserting Courses...")
course_upsert_count = 0
course_modified_count = 0
for course in courses_data:
    result = db.courses.update_one(
        {'title': course['title'], 'category': course['category']}, # Filter based on title and category
        {
            '$set': { # Update these fields if found
                'description': course['description'],
                'video_url': course['video_url'],
                'thumbnail': course['thumbnail']
                # Add other fields to update if needed
            },
            '$setOnInsert': { # Set these only if inserting new
                 'createdAt': datetime.now(timezone.utc),
                 'title': course['title'],
                 'category': course['category']
                 # Add other fields to set only on insert
            }
        },
        upsert=True
    )
    if result.upserted_id:
        course_upsert_count += 1
    elif result.modified_count > 0:
        course_modified_count += 1
print(f"Courses: {course_upsert_count} inserted, {course_modified_count} updated.")


# --- Seed Flashcards ---
flashcards_data = [
    # Sáo
    {'category': 'sao', 'question': 'Bộ phận nào của sáo trúc tạo ra âm thanh chính?', 'answer': 'Lỗ thổi'},
    {'category': 'sao', 'question': 'Kỹ thuật "láy hơi" dùng để làm gì?', 'answer': 'Tạo âm thanh luyến láy, mềm mại'},
    {'category': 'sao', 'question': 'Nốt Đô (C) trên sáo 6 lỗ thường bấm như thế nào?', 'answer': 'Bịt tất cả các lỗ'},
    # Đàn Tranh
    {'category': 'dan-tranh', 'question': 'Đàn tranh truyền thống thường có bao nhiêu dây?', 'answer': '16 dây'},
    {'category': 'dan-tranh', 'question': 'Bộ phận dùng để gảy đàn tranh gọi là gì?', 'answer': 'Móng gảy'},
    # Vovinam
    {'category': 'vovinam', 'question': 'Màu đai cao nhất trong Vovinam là gì?', 'answer': 'Đai đỏ (Hồng đai)'},
    {'category': 'vovinam', 'question': 'Tên đầy đủ của Vovinam là gì?', 'answer': 'Vovinam - Việt Võ Đạo'},
    {'category': 'vovinam', 'question': '"Chân tấn công" là đòn đá nào?', 'answer': 'Đá thẳng về phía trước'},
    {'category': 'vovinam', 'question': 'Thế tấn "Trung bình tấn" yêu cầu đầu gối như thế nào?', 'answer': 'Chùng thấp, trọng tâm hạ'},
]
print("\nUpserting Flashcards...")
flashcard_upsert_count = 0
flashcard_modified_count = 0
for card in flashcards_data:
    result = db.flashcards.update_one(
        {'category': card['category'], 'question': card['question']}, # Filter based on category and question
        {
            '$set': {'answer': card['answer']}, # Update answer if found
            '$setOnInsert': { # Set these only if inserting new
                'category': card['category'],
                'question': card['question'],
            }
        },
        upsert=True
    )
    if result.upserted_id:
        flashcard_upsert_count += 1
    elif result.modified_count > 0:
        flashcard_modified_count += 1
print(f"Flashcards: {flashcard_upsert_count} inserted, {flashcard_modified_count} updated.")


# --- Seed Challenges ---
challenges_data = [
    {'title': 'Thổi Đoạn Nhạc Ngắn', 'description': 'Thực hiện thổi một đoạn nhạc tự chọn bằng sáo và quay video.', 'points': 20, 'type': 'practice_video', 'thumbnail': '/assets/images/challenges/challenge_sao1.jpg'},
    {'title': 'Thực Hiện Đòn Tay Số 1', 'description': 'Quay video thực hiện đúng kỹ thuật Đòn tay số 1 của Vovinam.', 'points': 15, 'type': 'practice_video', 'thumbnail': '/assets/images/challenges/challenge_vvn1.jpg'},
    {'title': 'Ôn Tập 10 Flashcards', 'description': 'Hoàn thành bài kiểm tra 10 flashcards ngẫu nhiên về Vovinam.', 'points': 10, 'type': 'flashcard_test', 'thumbnail': '/assets/images/challenges/challenge_flashcard.jpg'}
]
print("\nUpserting Challenges...")
challenge_upsert_count = 0
challenge_modified_count = 0
for challenge in challenges_data:
    result = db.challenges.update_one(
        {'title': challenge['title']}, # Filter based on title (assuming titles are unique for seeding)
        {
            '$set': { # Update these fields if found
                'description': challenge['description'],
                'points': challenge['points'],
                'type': challenge['type'],
                'thumbnail': challenge['thumbnail']
            },
            '$setOnInsert': { # Set these only if inserting new
                 'createdAt': datetime.now(timezone.utc),
                 'title': challenge['title']
            }
        },
        upsert=True
    )
    if result.upserted_id:
        challenge_upsert_count += 1
    elif result.modified_count > 0:
        challenge_modified_count += 1
print(f"Challenges: {challenge_upsert_count} inserted, {challenge_modified_count} updated.")


# --- Seed Default Users (Insert Only If Not Existing - Doesn't update existing users) ---
users_data = [
     {
        'email': 'teacher@fpt.edu.vn',
        'password': generate_password_hash('password123'),
        'name': 'Giang Vien A', 'role': 'teacher',
        'avatar': 'https://ui-avatars.com/api/?name=Giang+Vien+A&background=0D8ABC&color=fff',
        'createdAt': datetime.now(timezone.utc)
     },
     {
        'email': 'student@fpt.edu.vn',
        'password': generate_password_hash('password123'),
        'name': 'Sinh Vien B', 'role': 'student',
        'progress': 10, 'points': 55, 'level': 1, 'badges': ['Beginner Learner'],
        'personalCourses': [], 'avatar': 'https://ui-avatars.com/api/?name=Sinh+Vien+B&background=random&color=fff',
        'streak': 2, 'lastLogin': datetime.now(timezone.utc) - timedelta(days=1),
        'createdAt': datetime.now(timezone.utc), 'flashcardProgress': {}, 'flashcardScore': 0
     }
]
print("\nChecking/Inserting Default Users...")
user_insert_count = 0
for user_data in users_data:
    # Only insert if email doesn't exist
    result = db.users.update_one(
        {'email': user_data['email']},
        {'$setOnInsert': user_data}, # Set all fields only on insert
        upsert=True
    )
    if result.upserted_id:
        user_insert_count += 1
        print(f"  Inserted default user: {user_data['email']}")
if user_insert_count == 0:
    print("  Default users already exist or were not inserted.")
print(f"Users: {user_insert_count} inserted.")

# --- Seed Ranking Data based on Existing Students (Upsert) ---
print("\nUpdating rankings based on current student data...")
student_users = db.users.find({'role': 'student'})
ranking_upsert_count = 0
ranking_modified_count = 0
for student in student_users:
    student_id_str = str(student['_id'])
    result = db.rankings.update_one(
        {'userId': student_id_str}, # Match based on user ID (string)
        {'$set': {
            'name': student.get('name', 'Unknown'),
            'points': student.get('points', 0),
            'avatar': student.get('avatar', ''),
            'level': student.get('level', 1)
        }},
        upsert=True
    )
    if result.upserted_id:
        ranking_upsert_count += 1
    elif result.modified_count > 0:
        ranking_modified_count += 1
print(f"Rankings: {ranking_upsert_count} created, {ranking_modified_count} updated.")


print("\n--- Database Seed/Update Complete ---")

client.close()
print("MongoDB connection closed.")