import os
import jwt as pyjwt
import logging
import random
from datetime import datetime, timedelta, timezone
from functools import wraps
import time # <<< ADDED >>>
import json # <<< ADDED >>>
from flask import Flask, request, jsonify, send_from_directory, Response, make_response # <<< MODIFIED (Added make_response) >>>
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
from bson import ObjectId
from bson.errors import InvalidId
import requests

# --- Setup logging ---
log_dir = 'backend/logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, 'app.log')
# Prevent duplicate handlers if script is reloaded (e.g., in development)
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    # filename=log_file, # Comment out for easier viewing during development/debugging
    level=logging.INFO, # Use INFO for production, DEBUG for development
    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]',
    handlers=[ # Use handlers for both file and console
        logging.FileHandler(log_file),
        logging.StreamHandler() # Output to console
    ]
)
logger = logging.getLogger(__name__)
# --- Load environment variables ---
load_dotenv()
logger.info("Loading environment variables")
JWT_SECRET = os.getenv("JWT_SECRET")
MONGO_URI = os.getenv("MONGO_URI")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", 5001))

# --- Environment Variable Checks ---
if not MONGO_URI: logger.critical("CRITICAL: MONGO_URI not set."); raise SystemExit("MONGO_URI not set")
if not JWT_SECRET: logger.critical("CRITICAL: JWT_SECRET not set."); raise SystemExit("JWT_SECRET not set")
if not GEMINI_API_KEY: logger.warning("WARNING: GEMINI_API_KEY not set. Chatbot disabled.")

# --- Initialize Flask app ---
app = Flask(__name__, static_folder='../frontend', static_url_path='')

# Configure CORS to allow requests from any origin
CORS(app,
     resources={r"/*": {
         "origins": "*",
         "allow_headers": ["Content-Type", "Authorization", "Access-Control-Allow-Origin",
                          "Access-Control-Allow-Methods", "Access-Control-Allow-Headers"],
         "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         "expose_headers": ["Content-Type", "Authorization"]
     }},
     supports_credentials=True)
logger.info("Flask app initialized with CORS (all methods and origins allowed)")

# Add a global OPTIONS handler to respond to preflight requests
@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def options_handler(path):
    response = app.make_default_options_response()
    return response

# Add a before_request handler to set CORS headers for all responses
@app.before_request
def before_request_func():
    if request.method == 'OPTIONS':
        return '', 200

# --- MongoDB connection ---
try:
    logger.info(f"Connecting to MongoDB...")
    # Increased timeouts for potentially slower connections
    client = MongoClient( MONGO_URI, serverSelectionTimeoutMS=10000, connectTimeoutMS=20000, retryWrites=True, w='majority')
    # The ismaster command is cheap and does not require auth.
    client.admin.command('ping')
    db = client['fpt_learning'] # Explicitly use 'fpt_learning' database
    logger.info(f"Connected to MongoDB (DB: {db.name})")
except ConnectionFailure as e:
    logger.critical(f"CRITICAL: MongoDB ConnectionFailure: {e}"); raise SystemExit(f"MongoDB connection failed: {e}")
except Exception as e:
    logger.critical(f"CRITICAL: MongoDB connection error: {e}"); raise SystemExit(f"MongoDB connection failed: {e}")

# --- Gemini API endpoint ---
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"

# --- Upload Folders Setup ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER_AVATARS = os.path.join(BASE_DIR, 'uploads', 'avatars')
UPLOAD_FOLDER_SUBMISSIONS = os.path.join(BASE_DIR, 'uploads', 'submissions')
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), 'frontend')
ASSETS_DIR = os.path.join(FRONTEND_DIR, 'assets')
ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_SUBMISSION_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm', 'pdf', 'doc', 'docx'}
MAX_AVATAR_SIZE = 2 * 1024 * 1024 # 2MB
MAX_SUBMISSION_SIZE = 50 * 1024 * 1024 # 50MB

os.makedirs(UPLOAD_FOLDER_AVATARS, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_SUBMISSIONS, exist_ok=True)
logger.info(f"Upload folders checked/created.")

# Verify frontend assets directory exists
if not os.path.exists(ASSETS_DIR):
    logger.warning(f"Frontend assets directory not found at {ASSETS_DIR}")

# --- Helper Functions ---
def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

# Convert ObjectId to string in nested structures (lists/dicts)
def stringify_ids(data):
    if isinstance(data, list):
        return [stringify_ids(item) for item in data]
    elif isinstance(data, dict):
        return {key: stringify_ids(value) for key, value in data.items()}
    elif isinstance(data, ObjectId):
        return str(data)
    else:
        return data

# --- Ensure collections and indexes ---
def ensure_db_setup():
    # Collections
    required_collections = ['users', 'courses', 'rankings', 'flashcards', 'challenges', 'learning_path', 'submissions', 'feedback', 'daily_challenges']
    existing_collections = db.list_collection_names()
    for coll_name in required_collections:
        if coll_name not in existing_collections:
            try:
                db.create_collection(coll_name)
                logger.info(f"Created collection: '{coll_name}'")
            except Exception as e:
                logger.error(f"Error creating collection '{coll_name}': {e}")
    # Indexes
    try:
        # users collection
        db.users.create_index([("email", 1)], unique=True, name="email_unique")
        db.users.create_index([("points", -1)], name="user_points_desc") # For potential internal sorting

        # courses collection
        db.courses.create_index([("category", 1)], name="course_category")

        # rankings collection
        # Use sparse=True if not all users might be in rankings (e.g., only students)
        db.rankings.create_index([("userId", 1)], unique=True, sparse=True, name="ranking_userId_unique")
        db.rankings.create_index([("points", -1)], name="ranking_points_desc") # Crucial for fetching sorted rankings

        # flashcards collection
        db.flashcards.create_index([("category", 1)], name="flashcard_category")

        # challenges collection
        db.challenges.create_index([("createdAt", -1)], name="challenge_created_desc")

        # learning_path collection
        db.learning_path.create_index([("order", 1)], name="learningpath_order")

        # submissions collection
        db.submissions.create_index([("userId", 1), ("createdAt", -1)], name="submission_user_created")
        db.submissions.create_index([("status", 1), ("type", 1)], name="submission_status_type") # For filtering by status/type

        # feedback collection
        db.feedback.create_index([("createdAt", -1)], name="feedback_created_desc")

        logger.info("MongoDB indexes checked/ensured.")
    except Exception as e:
        logger.error(f"Error ensuring MongoDB indexes: {e}")
# Run setup on startup
ensure_db_setup()

# --- Token Middleware ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            response = make_response()
            response.headers.add('Access-Control-Allow-Origin', '*')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
            response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
            return response

        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            return jsonify({'message': 'Token missing or invalid'}), 401
        try:
            token = token.split(" ")[1]
            # Decode token, checking expiration
            data = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"verify_exp": True})
            user_id = data.get('id')
            if not user_id or not ObjectId.is_valid(user_id):
                return jsonify({'message': 'Invalid token payload'}), 401

            # Fetch user details from DB, excluding password
            user_info = db.users.find_one({'_id': ObjectId(user_id)}, {'password': 0})
            if not user_info:
                return jsonify({'message': 'User not found'}), 401

            # Stringify ObjectIds before attaching to request
            request.current_user = stringify_ids(user_info)

        except pyjwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except (pyjwt.InvalidTokenError, pyjwt.DecodeError, InvalidId) as e:
            logger.warning(f"Auth failed: {e}")
            return jsonify({'message': 'Invalid token'}), 401
        except Exception as e:
            logger.error(f"Token processing error: {e}", exc_info=True)
            return jsonify({'message': 'Token processing error'}), 500
        return f(*args, **kwargs)
    return decorated

# --- Authorization Middleware ---
def teacher_required(f):
    @wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            response = make_response()
            response.headers.add('Access-Control-Allow-Origin', '*')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
            response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
            return response

        if request.current_user.get('role') != 'teacher':
            return jsonify({'message': 'Access forbidden: Teacher role required'}), 403
        return f(*args, **kwargs)
    return decorated

# --- Helper: Update Ranking ---
def _update_user_ranking(user_id_str, user_data):
     # Only update rankings for students
     if not user_data or user_data.get('role') != 'student':
         return

     try:
         # Use user_id_str which should already be stringified
         db.rankings.update_one(
             {'userId': user_id_str}, # Filter by the string representation of the user ID
             {'$set': {
                 'points': user_data.get('points', 0),
                 'name': user_data.get('name', 'Unknown'),
                 'avatar': user_data.get('avatar', ''),
                 'level': user_data.get('level', 1)
                 # Add any other fields relevant to ranking display
             }},
             upsert=True # Create the ranking document if it doesn't exist
         )
         # <<< MODIFIED >>>: Removed logging here, SSE polling logs changes detected
         # logger.info(f"Ranking data updated in DB for student {user_id_str}")
     except Exception as e:
          logger.error(f"Failed to update ranking for user {user_id_str}: {e}")

# --- Routes ---

@app.route('/api/status', methods=['GET'])
def check_status():
    mongo_status = 'disconnected'
    mongo_db_name = 'N/A'
    try:
        # Check MongoDB connection
        client.admin.command('ping')
        mongo_status = 'connected'
        mongo_db_name = db.name
        logger.info("Status check: OK, MongoDB connected")
        return jsonify({
            'status': 'Server is running',
            'mongodb_status': mongo_status,
            'database_name': mongo_db_name
        }), 200
    except Exception as e:
        logger.error(f"Status check failed: MongoDB connection error: {str(e)}")
        return jsonify({
            'status': 'Server running',
            'mongodb_status': mongo_status,
            'error': str(e)
        }), 500

@app.route('/api/teacher/analytics', methods=['GET'])
@teacher_required
def get_teacher_analytics():
    try:
        # Count students
        student_count = db.users.count_documents({'role': 'student'})

        # Count pending submissions
        pending_submissions = db.submissions.count_documents({'status': 'pending', 'type': 'challenge'})

        # Count approved submissions
        approved_submissions = db.submissions.count_documents({'status': 'approved'})

        # Count rejected submissions
        rejected_submissions = db.submissions.count_documents({'status': 'rejected'})

        # Calculate total reviewed submissions
        total_reviewed = approved_submissions + rejected_submissions

        # Calculate average points for students
        avg_points_result = list(db.users.aggregate([
            {'$match': {'role': 'student'}},
            {'$group': {'_id': None, 'avgPoints': {'$avg': '$points'}}}
        ]))
        avg_points = round(avg_points_result[0]['avgPoints']) if avg_points_result else 0

        # Calculate average progress for students
        avg_progress_result = list(db.users.aggregate([
            {'$match': {'role': 'student'}},
            {'$group': {'_id': None, 'avgProgress': {'$avg': '$progress'}}}
        ]))
        avg_progress = round(avg_progress_result[0]['avgProgress']) if avg_progress_result else 0

        analytics_data = {
            'studentCount': student_count,
            'pendingSubmissions': pending_submissions,
            'approvedCount': approved_submissions,
            'rejectedCount': rejected_submissions,
            'totalReviewed': total_reviewed,
            'averagePoints': avg_points,
            'averageProgress': avg_progress
        }

        logger.info(f"Teacher analytics fetched by {request.current_user['_id']}")
        return jsonify(analytics_data)
    except Exception as e:
        logger.error(f"Teacher analytics error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching teacher analytics'}), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        role = data.get('role', 'student').lower() # Default to student

        # --- Basic Validation ---
        errors = {}
        if not email: errors['email'] = 'Email is required'
        elif '@' not in email or '.' not in email.split('@')[-1] or len(email.split('@')[-1].split('.')) < 2 : errors['email'] = 'Invalid email format'
        if not password: errors['password'] = 'Password is required'
        elif len(password) < 6: errors['password'] = 'Password must be at least 6 characters long'
        if not name: errors['name'] = 'Name is required'
        if role not in ['student', 'teacher']: errors['role'] = 'Invalid role specified'

        if errors:
            return jsonify({'message': 'Validation failed', 'errors': errors}), 400

        # Check if email already exists
        if db.users.count_documents({'email': email}, limit=1) > 0:
            return jsonify({'message': 'Email already exists'}), 409 # 409 Conflict

        # Hash password
        hashed_password = generate_password_hash(password)

        # Default avatar (using ui-avatars)
        default_avatar = f'https://ui-avatars.com/api/?name={secure_filename(name).replace("_", "+")}&background=random&color=fff&size=150'

        # Create user document
        user_doc = {
            'email': email,
            'password': hashed_password,
            'name': name,
            'role': role,
            'progress': 0,
            'points': 0,
            'level': 1,
            'badges': [],
            'achievements': [],
            'personalCourses': [], # Store as empty list of ObjectIds initially
            'avatar': default_avatar,
            'streak': 0, # Login streak
            'lastLogin': None,
            'createdAt': datetime.now(timezone.utc),
            'flashcardProgress': {}, # Store flashcard progress { category: { card_id: state } }
            'flashcardScore': 0 # Separate score for flashcards if needed
        }
        # Nullify student-specific fields for teachers
        if role == 'teacher':
            user_doc.update({k: None for k in ['progress', 'points', 'level', 'badges', 'streak', 'flashcardProgress', 'flashcardScore']})

        # Insert user
        result = db.users.insert_one(user_doc)
        user_doc['_id'] = result.inserted_id # Keep as ObjectId for now

        # Generate JWT token
        token_expiry = datetime.now(timezone.utc) + timedelta(days=7) # 7-day expiry
        token_payload = {'id': str(user_doc['_id']), 'role': role, 'exp': token_expiry}
        token = pyjwt.encode(token_payload, JWT_SECRET, algorithm="HS256")

        logger.info(f"User registered: {email} (Role: {role}, ID: {user_doc['_id']})")

        # Prepare user data for client (stringify IDs)
        user_data_for_client = stringify_ids({k: v for k, v in user_doc.items() if k != 'password'})

        return jsonify({'token': token, 'user': user_data_for_client}), 201

    except Exception as e:
        logger.error(f"Registration error: {e}", exc_info=True)
        return jsonify({'message': 'Server error during registration'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        if not email or not password:
            return jsonify({'message': 'Email and password required'}), 400

        user = db.users.find_one({'email': email})

        # Check user and password
        if not user or 'password' not in user or not check_password_hash(user.get('password', ''), password):
            return jsonify({'message': 'Invalid email or password'}), 401

        # --- Login Streak Logic (only for students) ---
        update_fields = {'lastLogin': datetime.now(timezone.utc)}
        inc_updates = {}
        current_streak = user.get('streak', 0)

        if user.get('role') == 'student':
            today = datetime.now(timezone.utc).date()
            last_login_utc = user.get('lastLogin')
            points_to_add = 0

            # Ensure last_login is a datetime object with timezone
            if last_login_utc:
                if not isinstance(last_login_utc, datetime):
                    try: last_login_utc = datetime.fromisoformat(str(last_login_utc)).replace(tzinfo=timezone.utc) # Try parsing if stored as string
                    except: last_login_utc = None # Invalid format
                # Ensure timezone if missing (assuming UTC if none)
                if last_login_utc and last_login_utc.tzinfo is None:
                    last_login_utc = last_login_utc.replace(tzinfo=timezone.utc)

                if last_login_utc:
                    last_login_date = last_login_utc.date()
                    # Check if login is on a new day
                    if today > last_login_date:
                        if (today - last_login_date).days == 1: # Consecutive day
                            current_streak += 1
                        else: # Missed a day
                            current_streak = 1
                        # Award points for login streak
                        points_to_add = 5 # Base points for daily login
                        if current_streak >= 7: points_to_add += 15 # Bonus for 7+ days
                        elif current_streak >= 3: points_to_add += 5 # Bonus for 3+ days
                else: # First login ever recorded properly
                    current_streak = 1
                    points_to_add = 5
            else: # First login ever
                current_streak = 1
                points_to_add = 5

            update_fields['streak'] = current_streak
            if points_to_add > 0:
                inc_updates['points'] = points_to_add

        # Update user in DB
        if inc_updates:
            db.users.update_one({'_id': user['_id']}, {'$inc': inc_updates, '$set': update_fields})
        elif update_fields: # Only update lastLogin if no points were added
             db.users.update_one({'_id': user['_id']}, {'$set': update_fields})


        # Fetch updated user data
        updated_user = db.users.find_one({'_id': user['_id']})
        if not updated_user:
            return jsonify({'message': 'Login failed - internal error fetching updated user'}), 500

        # Generate JWT token
        token_expiry = datetime.now(timezone.utc) + timedelta(days=7)
        token_payload = {'id': str(updated_user['_id']), 'role': updated_user['role'], 'exp': token_expiry}
        token = pyjwt.encode(token_payload, JWT_SECRET, algorithm="HS256")

        logger.info(f"User logged in: {email}, Role: {updated_user['role']}, Streak: {updated_user.get('streak', 'N/A')}")

        # Prepare user data for client (stringify IDs)
        user_data_for_client = stringify_ids({k: v for k, v in updated_user.items() if k != 'password'})

        return jsonify({'token': token, 'user': user_data_for_client})

    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        return jsonify({'message': 'Server error during login'}), 500

@app.route('/api/auth/refresh', methods=['POST'])
@token_required
def refresh_token():
    try:
        user_id = request.current_user['_id'] # Already stringified by decorator
        user_role = request.current_user['role']
        user_email = request.current_user['email'] # For logging

        # Generate new token with fresh expiry
        token_expiry = datetime.now(timezone.utc) + timedelta(days=7)
        new_token_payload = {'id': user_id, 'role': user_role, 'exp': token_expiry}
        new_token = pyjwt.encode(new_token_payload, JWT_SECRET, algorithm="HS256")

        logger.info(f"Token refreshed for user: {user_email} (ID: {user_id})")
        return jsonify({'token': new_token})
    except Exception as e:
        logger.error(f"Token refresh error: {e}", exc_info=True)
        return jsonify({'message': 'Server error during token refresh'}), 500

@app.route('/api/users/me', methods=['GET'])
@token_required
def get_user_profile():
    try:
        # current_user is already prepared and stringified by the decorator
        logger.info(f"Profile fetched for user: {request.current_user.get('email', 'N/A')}")
        return jsonify(request.current_user)
    except Exception as e:
        logger.error(f"Get user profile error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching profile'}), 500

@app.route('/api/users/<user_id_str>', methods=['GET'])
@token_required
def get_user_by_id(user_id_str):
    try:
        requesting_user_role = request.current_user.get('role')

        # Only teachers can view other users' profiles
        if requesting_user_role != 'teacher' and request.current_user['_id'] != user_id_str:
            return jsonify({'message': 'Unauthorized to view this user profile'}), 403

        # Validate user ID format
        if not ObjectId.is_valid(user_id_str):
            return jsonify({'message': 'Invalid user ID format'}), 400

        user_id_obj = ObjectId(user_id_str)

        # Find the user
        user = db.users.find_one({'_id': user_id_obj}, {'password': 0})
        if not user:
            return jsonify({'message': 'User not found'}), 404

        # Return user data (stringified)
        logger.info(f"User {user_id_str} profile fetched by {request.current_user['_id']}")
        return jsonify(stringify_ids(user))
    except Exception as e:
        logger.error(f"Get user by ID error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching user profile'}), 500

@app.route('/api/users', methods=['GET'])
@token_required
def get_users():
    try:
        # Only teachers can list users
        if request.current_user.get('role') != 'teacher':
            return jsonify({'message': 'Unauthorized to list users'}), 403

        # Get query parameters
        role = request.args.get('role')
        limit = int(request.args.get('limit', 100))

        # Build query
        query = {}
        if role:
            query['role'] = role

        # Fetch users
        users_cursor = db.users.find(query, {'password': 0}).limit(limit)
        users = [stringify_ids(user) for user in users_cursor]

        logger.info(f"Users list fetched by {request.current_user['_id']} (Role filter: {role or 'None'})")
        return jsonify(users)
    except Exception as e:
        logger.error(f"Get users list error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching users list'}), 500

@app.route('/api/users/<user_id_str>', methods=['PUT'])
@token_required
def update_user(user_id_str):
    try:
        requesting_user_id = request.current_user['_id'] # Already string
        requesting_user_role = request.current_user.get('role')

        # Authorization: User can update self, or teacher can update anyone
        if requesting_user_id != user_id_str and requesting_user_role != 'teacher':
            return jsonify({'message': 'Unauthorized'}), 403

        # Validate target user ID format
        if not ObjectId.is_valid(user_id_str):
            return jsonify({'message': 'Invalid user ID format'}), 400

        user_id_obj = ObjectId(user_id_str)

        # Find the user to update
        target_user = db.users.find_one({'_id': user_id_obj})
        if not target_user:
            return jsonify({'message': 'User not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        # Define fields allowed for update via this endpoint
        allowed_fields = [
            'progress', 'points', 'level', 'badges', 'achievements',
            'personalCourses', 'name', 'flashcardProgress', 'flashcardScore'
        ]
        updates = {}

        # Process updates carefully, validating types
        if 'name' in data:
            new_name = str(data['name']).strip()
            if new_name and new_name != target_user.get('name'):
                updates['name'] = new_name
        if 'progress' in data:
            try: updates['progress'] = min(100, max(0, int(data['progress'])))
            except (ValueError, TypeError): pass # Ignore invalid progress values
        if 'points' in data:
            try: updates['points'] = max(0, int(data['points']))
            except (ValueError, TypeError): pass # Ignore invalid points values
        if 'level' in data:
            try: updates['level'] = max(1, int(data['level']))
            except (ValueError, TypeError): pass # Ignore invalid level values
        if 'badges' in data and isinstance(data['badges'], list):
            # Ensure badges are strings and non-empty
            updates['badges'] = [str(b).strip() for b in data['badges'] if str(b).strip()]
        if 'achievements' in data and isinstance(data['achievements'], list):
            updates['achievements'] = [str(a).strip() for a in data['achievements'] if str(a).strip()]
        if 'personalCourses' in data and isinstance(data['personalCourses'], list):
            # Convert valid string IDs back to ObjectIds for storage
            valid_course_ids = []
            for cid_str in data['personalCourses']:
                if isinstance(cid_str, str) and ObjectId.is_valid(cid_str):
                    valid_course_ids.append(ObjectId(cid_str))
            # Only update if the list is different from the current one (deep compare needed for ObjectsIds)
            # Simple check: compare lengths and string representations
            current_ids_str = [str(cid) for cid in target_user.get('personalCourses', [])]
            new_ids_str = [str(cid) for cid in valid_course_ids]
            if set(current_ids_str) != set(new_ids_str):
                updates['personalCourses'] = valid_course_ids
        if 'flashcardProgress' in data and isinstance(data['flashcardProgress'], dict):
            updates['flashcardProgress'] = data['flashcardProgress'] # Assume frontend sends valid structure
        if 'flashcardScore' in data:
            try: updates['flashcardScore'] = max(0, int(data['flashcardScore']))
            except (ValueError, TypeError): pass

        # Filter updates to only include allowed fields
        updates = {k: v for k, v in updates.items() if k in allowed_fields}

        # If no valid updates, return current data
        if not updates:
            # Stringify IDs for response
            return jsonify(stringify_ids({k: v for k, v in target_user.items() if k != 'password'}))

        # --- Level calculation based on points ---
        level_changed_by_points = False
        if 'points' in updates and target_user.get('role') == 'student':
            new_points = updates['points']
            # Calculate potential new level based on points (e.g., 100 points/level)
            new_level = max(1, (new_points // 100) + 1)

            # Check if level needs update based on points, considering if 'level' was also in request
            current_level_in_updates = updates.get('level')
            compare_level = current_level_in_updates if current_level_in_updates is not None else target_user.get('level', 1)

            if new_level != compare_level:
                 updates['level'] = new_level # Override requested level if points dictate otherwise
                 level_changed_by_points = True
            # If level WAS in updates but doesn't match calculated, force calculated level
            elif current_level_in_updates is not None and current_level_in_updates != new_level:
                 updates['level'] = new_level
                 level_changed_by_points = True


        # Perform the update
        result = db.users.update_one({'_id': user_id_obj}, {'$set': updates})

        if result.matched_count == 0:
            # Should not happen if find_one succeeded, but check anyway
            return jsonify({'message': 'User not found during update'}), 404

        # Fetch the fully updated user data
        updated_user = db.users.find_one({'_id': user_id_obj}, {'password': 0})

        # Check if ranking needs update (points, level, name changed)
        ranking_needs_update = ('points' in updates or 'name' in updates or 'level' in updates or level_changed_by_points)
        if ranking_needs_update:
            # Pass stringified ID and the updated user dict
            _update_user_ranking(str(user_id_obj), stringify_ids(updated_user))

        logger.info(f"User {user_id_str} updated successfully by {requesting_user_id}. Fields: {list(updates.keys())}")

        # Return updated user data (stringified)
        return jsonify(stringify_ids(updated_user))

    except Exception as e:
        logger.error(f"Update user {user_id_str} error: {e}", exc_info=True)
        return jsonify({'message': 'Server error during user update'}), 500

@app.route('/api/users/personal-courses', methods=['POST'])
@token_required
def add_personal_course():
    try:
        data = request.get_json()
        course_id_str = data.get('courseId')

        if not course_id_str or not ObjectId.is_valid(course_id_str):
            return jsonify({'message': 'Valid Course ID required'}), 400

        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query
        course_id_obj = ObjectId(course_id_str)

        # Verify course exists
        if db.courses.count_documents({'_id': course_id_obj}, limit=1) == 0:
            return jsonify({'message': 'Course not found'}), 404

        # Add courseId to the user's personalCourses array (only if not already present)
        result = db.users.update_one(
            {'_id': user_id_obj},
            {'$addToSet': {'personalCourses': course_id_obj}}
        )

        # Fetch updated user to return
        updated_user = db.users.find_one({'_id': user_id_obj}, {'password': 0})
        user_data_for_client = stringify_ids(updated_user)

        if result.modified_count > 0:
             logger.info(f"Course {course_id_str} added to favorites for user {request.current_user['_id']}")
             return jsonify({'message': 'Course added successfully', 'user': user_data_for_client})
        elif result.matched_count > 0: # Matched but not modified means it was already there
             return jsonify({'message': 'Course already in list', 'user': user_data_for_client})
        else:
            return jsonify({'message': 'User not found'}), 404 # Should not happen with token_required

    except Exception as e:
        logger.error(f"Add personal course error: {e}", exc_info=True)
        return jsonify({'message': 'Server error adding personal course'}), 500

@app.route('/api/users/personal-courses/<course_id_str>', methods=['DELETE'])
@token_required
def remove_personal_course(course_id_str):
    try:
        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query

        if not course_id_str or not ObjectId.is_valid(course_id_str):
            return jsonify({'message': 'Valid Course ID required'}), 400
        course_id_obj = ObjectId(course_id_str)

        # Remove courseId from the user's personalCourses array
        result = db.users.update_one(
            {'_id': user_id_obj},
            {'$pull': {'personalCourses': course_id_obj}}
        )

        # Fetch updated user to return
        updated_user = db.users.find_one({'_id': user_id_obj}, {'password': 0})
        user_data_for_client = stringify_ids(updated_user)

        if result.modified_count > 0:
            logger.info(f"Course {course_id_str} removed from favorites for user {request.current_user['_id']}")
            return jsonify({'message': 'Course removed successfully', 'user': user_data_for_client})
        elif result.matched_count > 0: # Matched but not modified means it wasn't in the list
            return jsonify({'message': 'Course not found in list', 'user': user_data_for_client})
        else:
            return jsonify({'message': 'User not found'}), 404 # Should not happen

    except Exception as e:
        logger.error(f"Remove personal course error: {e}", exc_info=True)
        return jsonify({'message': 'Server error removing personal course'}), 500

@app.route('/api/users/change-password', methods=['POST'])
@token_required
def change_password():
    try:
        data = request.get_json()
        current_password = data.get('currentPassword')
        new_password = data.get('newPassword')

        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query

        if not current_password or not new_password:
            return jsonify({'message': 'Passwords required'}), 400
        if len(new_password) < 6:
            return jsonify({'message': 'New password too short (minimum 6 characters)'}), 400

        user = db.users.find_one({'_id': user_id_obj})
        if not user:
            return jsonify({'message': 'User not found'}), 404 # Should not happen

        # Check if user has a password set (might not if social login implemented later)
        if 'password' not in user or not user['password']:
            return jsonify({'message': 'Cannot change password for this account'}), 400

        # Verify current password
        if not check_password_hash(user.get('password'), current_password):
            return jsonify({'message': 'Current password incorrect'}), 401

        # Prevent setting the same password
        if check_password_hash(user.get('password'), new_password):
            return jsonify({'message': 'New password cannot be the same as the old password'}), 400

        # Hash new password and update
        new_hashed_password = generate_password_hash(new_password)
        result = db.users.update_one({'_id': user_id_obj}, {'$set': {'password': new_hashed_password}})

        if result.matched_count == 0:
            return jsonify({'message': 'User not found during password update'}), 404 # Should not happen

        logger.info(f"Password changed successfully for user {user_id_obj}")
        return jsonify({'message': 'Password changed successfully'})

    except Exception as e:
        logger.error(f"Change password error: {e}", exc_info=True)
        return jsonify({'message': 'Server error changing password'}), 500

@app.route('/api/users/change-avatar', methods=['POST'])
@token_required
def change_avatar():
    try:
        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query

        if 'avatar' not in request.files:
            return jsonify({'message': 'No file part named "avatar"'}), 400
        file = request.files['avatar']
        if file.filename == '':
            return jsonify({'message': 'No selected file'}), 400

        # Validate file type
        filename = secure_filename(file.filename)
        if not allowed_file(filename, ALLOWED_AVATAR_EXTENSIONS):
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else '?'
            return jsonify({'message': f'File type "{ext}" not allowed. Allowed: {", ".join(ALLOWED_AVATAR_EXTENSIONS)}'}), 400

        # Validate file size
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0) # Reset pointer
        if file_length > MAX_AVATAR_SIZE:
            limit_mb = MAX_AVATAR_SIZE / (1024 * 1024)
            return jsonify({'message': f'File size exceeds limit ({limit_mb:.1f}MB)'}), 413 # Payload Too Large

        # Create unique filename and path
        file_ext = filename.rsplit('.', 1)[1].lower()
        unique_filename = f"avatar_{str(user_id_obj)}_{int(datetime.now(timezone.utc).timestamp())}.{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER_AVATARS, unique_filename)
        avatar_url = f"/uploads/avatars/{unique_filename}" # URL path for serving

        # TODO: Add image processing/resizing here if needed before saving

        # Save file
        file.save(file_path)

        # Update user document
        result = db.users.update_one({'_id': user_id_obj}, {'$set': {'avatar': avatar_url}})
        if result.matched_count == 0:
            # Clean up saved file if user not found
            if os.path.exists(file_path): os.remove(file_path)
            return jsonify({'message': 'User not found'}), 404

        # Fetch updated user data for ranking update and response
        updated_user = db.users.find_one({'_id': user_id_obj}, {'password': 0})
        updated_user_data = stringify_ids(updated_user)

        # Update ranking (avatar changed)
        _update_user_ranking(str(user_id_obj), updated_user_data)
        # Also update the avatar in the request context immediately if needed elsewhere in this request cycle
        request.current_user['avatar'] = avatar_url

        logger.info(f"Avatar changed for user {user_id_obj}, URL: {avatar_url}")
        return jsonify({'message': 'Avatar changed successfully', 'avatarUrl': avatar_url, 'user': updated_user_data})

    except Exception as e:
        # Clean up potential partial file uploads on error? Difficult.
        logger.error(f"Change avatar error: {e}", exc_info=True)
        return jsonify({'message': 'Server error changing avatar'}), 500

@app.route('/api/courses', methods=['GET'])
# @token_required # Courses might be public, remove token requirement if needed
def get_courses():
    try:
        category = request.args.get('category')
        query = {}
        if category:
            query['category'] = category

        courses_cursor = db.courses.find(query)
        # Convert ObjectIds to strings for JSON response
        courses = [stringify_ids(c) for c in courses_cursor]

        user_id = request.current_user.get('_id', 'public') if hasattr(request, 'current_user') else 'public'
        logger.info(f"Courses fetched (Category: {category or 'All'}) for user/requester {user_id}")
        return jsonify(courses)

    except Exception as e:
        logger.error(f"Courses fetch error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching courses'}), 500


# <<< ADDED: Global variables for SSE ranking cache >>>
last_rankings_state = None
last_check_time = 0
RANKING_CHECK_INTERVAL = 5 # Check database for ranking changes every 5 seconds


# <<< ADDED: Helper function to get current ranking state (cached) >>>
def get_current_ranking_state(limit=50):
    """Fetches current ranking state, using a cache to reduce DB load."""
    global last_rankings_state, last_check_time
    current_time = time.time()

    # Check cache validity
    if last_rankings_state is None or (current_time - last_check_time > RANKING_CHECK_INTERVAL):
        logger.debug(f"Ranking cache expired or empty. Querying DB at {current_time:.2f}")
        try:
            rankings_cursor = db.rankings.find(
                {},
                {'_id': 0, 'userId': 1, 'name': 1, 'points': 1, 'avatar': 1, 'level': 1} # Exclude MongoDB _id
            ).sort('points', -1).limit(limit)
            current_state_list = list(rankings_cursor) # Convert cursor to list
            # Store as JSON string for easy comparison
            current_state_json = json.dumps(current_state_list)

            # Update cache only if data actually changed to avoid unnecessary downstream processing
            if current_state_json != last_rankings_state:
                 last_rankings_state = current_state_json
                 logger.info(f"Ranking state updated in cache. {len(current_state_list)} users.")
            else:
                 logger.debug("Ranking state unchanged since last DB check.")


            last_check_time = current_time # Update last check time regardless of change
            return last_rankings_state # Return the potentially updated state

        except Exception as e:
            logger.error(f"Error fetching current ranking state from DB: {e}")
            # Return the old cached state on error to avoid breaking SSE stream if possible
            return last_rankings_state
    else:
        # Return cached state if interval hasn't passed
        logger.debug(f"Returning cached ranking state (checked {current_time - last_check_time:.2f}s ago)")
        return last_rankings_state


@app.route('/api/rankings', methods=['GET'])
@token_required # Keep token required for standard GET request
def get_rankings():
    # This route provides a snapshot, mainly for initial load or fallback
    try:
        limit = int(request.args.get('limit', 50))
        # Use the cached state function to potentially avoid DB query
        rankings_json = get_current_ranking_state(limit=limit)
        rankings_list = json.loads(rankings_json) if rankings_json else []

        logger.info(f"Rankings fetched on demand (Snapshot, Top {limit}) for user {request.current_user['_id']}")
        return jsonify(rankings_list)
    except Exception as e:
        logger.error(f"Rankings fetch (snapshot) error: {str(e)}", exc_info=True)
        return jsonify({'message': 'Server error fetching rankings snapshot', 'error': str(e)}), 500


# <<< ADDED: SSE Endpoint for Real-time Ranking Updates >>>
@app.route('/api/rankings/stream')
def stream_rankings():
    def generate():
        yield 'data: {"event": "connected", "rankings": []}\n\n'
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/submissions', methods=['POST'])
@token_required
def upload_submission():
    # Combined route for different submission types (practice, challenge)
    try:
        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query
        user_email = request.current_user['email']
        user_name = request.current_user.get('name', 'Unknown')
        user_role = request.current_user['role']

        # Check for file part
        if 'file' not in request.files:
            return jsonify({'message': 'No file part named "file"'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'message': 'No selected file'}), 400

        # Get form data
        note = request.form.get('note', '').strip()
        # Determine submission type (default to 'practice' if not specified)
        submission_type = request.form.get('type', 'practice').lower()
        related_id_str = request.form.get('relatedId') # e.g., courseId or challengeId
        related_title = request.form.get('relatedTitle', 'N/A')

        # Log received data for debugging
        logger.info(f"Submission data received: type={submission_type}, relatedId={related_id_str}, relatedTitle={related_title}")

        # Check if this is a challenge submission and if the student has already submitted today
        if submission_type == 'challenge' and user_role == 'student':
            # Get today's date in UTC
            today = datetime.now(timezone.utc).date()
            today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
            today_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)

            # Find if there's a submission for today by this user
            existing_submission = db.submissions.find_one({
                'userId': user_id_obj,
                'type': 'challenge',
                'createdAt': {'$gte': today_start, '$lte': today_end}
            })

            if existing_submission:
                # Check if the existing submission was rejected
                if existing_submission.get('status') != 'rejected':
                    return jsonify({
                        'message': 'Bạn chỉ được nộp một thử thách mỗi ngày. Vui lòng thử lại vào ngày mai.'
                    }), 400

        # --- File Validation ---
        filename = secure_filename(file.filename)
        if not allowed_file(filename, ALLOWED_SUBMISSION_EXTENSIONS):
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else '?'
            return jsonify({'message': f'File type "{ext}" not allowed. Allowed: {", ".join(ALLOWED_SUBMISSION_EXTENSIONS)}'}), 400

        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)
        if file_length > MAX_SUBMISSION_SIZE:
            limit_mb = MAX_SUBMISSION_SIZE / (1024 * 1024)
            return jsonify({'message': f'File size exceeds limit ({limit_mb:.1f}MB)'}), 413

        # --- Process Related ID ---
        related_object_id = None
        collection_to_check = None

        try:
            if related_id_str and ObjectId.is_valid(related_id_str):
                related_object_id = ObjectId(related_id_str)
                # Determine which collection to check for the title based on type
                if submission_type == 'challenge':
                    collection_to_check = db.challenges
                elif submission_type in ['practice', 'practice_video']: # Assuming practice relates to courses
                    collection_to_check = db.courses
                # Add other types if necessary (e.g., lessonId)

                if collection_to_check:
                    related_doc = collection_to_check.find_one({'_id': related_object_id}, {'title': 1})
                    if related_doc:
                        # If we found the document, use its title, otherwise use the provided title
                        if not related_title or related_title == 'N/A':
                            related_title = related_doc.get('title', 'Unknown Title')
                    else:
                        logger.warning(f"Related document not found for ID: {related_id_str} in collection {collection_to_check.name}")
                        # Keep the provided title if the document wasn't found
            elif related_id_str:
                # Handle cases where relatedId might be a string identifier (like 'daily')
                related_object_id = related_id_str # Store as string
                # Keep the provided title

            logger.info(f"Processed related ID: {related_id_str} -> {related_object_id}, Title: {related_title}")
        except Exception as e:
            logger.error(f"Error processing related ID: {e}")
            # If there's an error, use the string version of the ID and keep the provided title
            related_object_id = related_id_str


        # --- Save File ---
        file_ext = filename.rsplit('.', 1)[1].lower()
        timestamp = int(datetime.now(timezone.utc).timestamp())
        unique_filename = f"{submission_type}_{str(user_id_obj)}_{timestamp}.{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER_SUBMISSIONS, unique_filename)
        file_url = f"/uploads/submissions/{unique_filename}"

        file.save(file_path)

        # --- Create Submission Document ---
        submission_doc = {
            'userId': user_id_obj,
            'userEmail': user_email,
            'userName': user_name,
            'type': submission_type,
            'relatedId': related_object_id, # Can be ObjectId or string
            'relatedTitle': related_title,
            'url': file_url,
            'note': note,
            'teacherComment': '',
            'status': 'pending', # Default status
            'pointsAwarded': 0,
            'createdAt': datetime.now(timezone.utc),
            'reviewedAt': None,
            'reviewerId': None,
            'originalFilename': filename # Store original filename for reference
        }

        # --- Insert Submission ---
        result = db.submissions.insert_one(submission_doc)
        inserted_id = result.inserted_id
        submission_doc['_id'] = inserted_id # Keep as ObjectId internally

        # --- Auto-approve practice & Award points ---
        points_to_add = 0
        progress_to_add = 0
        response_message = 'Submission received.'

        if user_role == 'student' and submission_type in ['practice', 'practice_video']:
            points_to_add = 10 # Example points for practice
            progress_to_add = 2 # Example progress
            submission_doc['status'] = 'approved'
            submission_doc['pointsAwarded'] = points_to_add
            # Update status and points immediately in DB for auto-approved items
            db.submissions.update_one(
                {'_id': inserted_id},
                {'$set': {'status': 'approved', 'pointsAwarded': points_to_add}}
            )
            response_message = f'Practice submission received, +{points_to_add} points!'
        elif submission_type == 'challenge':
             # Get potential points from the challenge document
             challenge_points = 15 # Default if challenge not found or no points defined
             if isinstance(related_object_id, ObjectId): # Only if it's a valid ID
                 challenge = db.challenges.find_one({'_id': related_object_id})
                 if challenge:
                     challenge_points = challenge.get('points', 15)
             elif related_object_id == 'daily': # Example handling for 'daily' identifier
                 # Fetch the actual daily challenge to get points (more complex)
                 # For simplicity, assume a default or handle based on frontend knowledge
                 pass

             response_message = f'Challenge submission received. Waiting for review (potential +{challenge_points} points).'


        # Update user points/progress if awarded automatically
        if points_to_add > 0 or progress_to_add > 0:
            update_result = db.users.update_one(
                {'_id': user_id_obj},
                {'$inc': {'points': points_to_add, 'progress': progress_to_add}}
            )
            if update_result.modified_count > 0:
                # Fetch updated user data for ranking update
                updated_user = db.users.find_one({'_id': user_id_obj})
                _update_user_ranking(str(user_id_obj), stringify_ids(updated_user))
                logger.info(f"Auto-awarded {points_to_add} points, {progress_to_add}% progress for submission {inserted_id} by {user_email}.")

        # Prepare response (stringify IDs)
        response_submission = stringify_ids(submission_doc)

        logger.info(f"Submission type '{submission_type}' received from {user_email}. ID: {inserted_id}. Status: {response_submission['status']}.")
        return jsonify({'submission': response_submission, 'message': response_message}), 201

    except Exception as e:
        logger.error(f"Submission upload error: {e}", exc_info=True)
        # Return more detailed error message for debugging
        error_message = str(e)
        return jsonify({
            'message': 'Server error during submission upload',
            'error': error_message
        }), 500

@app.route('/api/submissions', methods=['GET', 'OPTIONS'])
@token_required
def get_submissions():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        response.headers.add('Allow', 'GET,OPTIONS')
        return response
    try:
        user_id_str = request.current_user['_id'] # Already string
        user_role = request.current_user['role']
        query = {}

        # --- Filter based on user role and request parameters ---
        if user_role != 'teacher':
            # Students only see their own submissions
            query['userId'] = ObjectId(user_id_str) # Query by ObjectId
        else:
            # Teachers can filter by student ID or email
            student_id_param = request.args.get('userId')
            student_email_param = request.args.get('userEmail')
            if student_id_param and ObjectId.is_valid(student_id_param):
                query['userId'] = ObjectId(student_id_param)
            elif student_email_param:
                query['userEmail'] = student_email_param.strip().lower()
            # If no student filter, teacher sees all (or paginated subset)

        # Optional filters
        sub_type = request.args.get('type')
        status = request.args.get('status')
        if sub_type:
            query['type'] = sub_type.lower()
        if status:
            query['status'] = status.lower()

        # --- Pagination ---
        try: page = int(request.args.get('page', 1))
        except ValueError: page = 1
        try: limit = int(request.args.get('limit', 10))
        except ValueError: limit = 10
        limit = max(1, min(limit, 100)) # Clamp limit
        page = max(1, page)
        skip = (page - 1) * limit

        # --- Fetch Data ---
        submissions_cursor = db.submissions.find(query).sort('createdAt', -1).skip(skip).limit(limit)
        submissions = [stringify_ids(sub) for sub in submissions_cursor] # Stringify results

        # Get total count for pagination info
        total_submissions = db.submissions.count_documents(query)
        total_pages = (total_submissions + limit - 1) // limit if limit > 0 else 0

        logger.info(f"Submissions fetched by {request.current_user['email']} ({user_role}). Query: {query}, Page {page}, Limit {limit}. Found: {len(submissions)}/{total_submissions}")
        return jsonify({
            'submissions': submissions,
            'total': total_submissions,
            'page': page,
            'limit': limit,
            'totalPages': total_pages
        })

    except Exception as e:
        logger.error(f"Submissions fetch error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching submissions'}), 500

@app.route('/api/submissions/user/<user_id>', methods=['GET'])
@token_required
def get_user_submissions(user_id):
    try:
        # Check if the requesting user is the same as the user_id or is a teacher
        current_user_id = request.current_user.get('_id')
        is_teacher = request.current_user.get('role') == 'teacher'

        if current_user_id != user_id and not is_teacher:
            return jsonify({'message': 'Unauthorized access to user submissions'}), 403

        # Get query parameters
        status = request.args.get('status')
        limit = int(request.args.get('limit', 100))
        type = request.args.get('type', 'challenge')

        # Build query
        query = {}
        if ObjectId.is_valid(user_id):
            query['userId'] = ObjectId(user_id)
        else:
            query['userId'] = user_id

        if status: query['status'] = status
        if type: query['type'] = type

        # Fetch submissions
        submissions = list(db.submissions.find(query).sort('createdAt', -1).limit(limit))

        # Stringify ObjectIds
        submissions = stringify_ids(submissions)

        logger.info(f"Fetched {len(submissions)} submissions for user {user_id}")
        return jsonify(submissions)
    except Exception as e:
        logger.error(f"Error fetching user submissions: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching user submissions'}), 500

@app.route('/api/submissions/<submission_id_str>/review', methods=['PUT'])
@teacher_required
def review_submission(submission_id_str):
    try:
        reviewer_id_obj = ObjectId(request.current_user['_id']) # Teacher's ID as ObjectId
        reviewer_email = request.current_user['email']

        if not ObjectId.is_valid(submission_id_str):
            return jsonify({'message': 'Invalid submission ID format'}), 400
        submission_id_obj = ObjectId(submission_id_str)

        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        # Get review data
        status = data.get('status') # 'approved' or 'rejected'
        teacher_comment = data.get('teacherComment', '').strip()
        try:
            # Award points only if approved, default to 0 otherwise
            points_awarded = int(data.get('pointsAwarded', 0)) if status == 'approved' else 0
            points_awarded = max(0, points_awarded) # Ensure non-negative
        except (ValueError, TypeError):
            points_awarded = 0

        # --- Validation ---
        if status not in ['approved', 'rejected']:
            return jsonify({'message': 'Status must be "approved" or "rejected"'}), 400
        if status == 'rejected' and not teacher_comment: # Require comment for rejection
            return jsonify({'message': 'Comment is required for rejection'}), 400

        # --- Find Submission ---
        submission = db.submissions.find_one({'_id': submission_id_obj})
        if not submission:
            return jsonify({'message': 'Submission not found'}), 404
        if submission.get('status') != 'pending':
            # Prevent re-reviewing (or handle differently if needed)
            return jsonify({'message': f"Submission already reviewed (Status: {submission.get('status')})"}), 409 # Conflict

        # --- Update Submission ---
        update_fields = {
            'status': status,
            'teacherComment': teacher_comment,
            'pointsAwarded': points_awarded,
            'reviewedAt': datetime.now(timezone.utc),
            'reviewerId': reviewer_id_obj # Store reviewer's ObjectId
        }
        result = db.submissions.update_one({'_id': submission_id_obj}, {'$set': update_fields})

        if result.modified_count == 0:
             # Check if it was already reviewed by someone else just before this request
             current_sub = db.submissions.find_one({'_id': submission_id_obj});
             if current_sub and current_sub.get('status') != 'pending':
                  return jsonify({'message': f"Submission reviewed concurrently (Status: {current_sub.get('status')})"}), 409
             logger.warning(f"Review failed for submission {submission_id_str}, modified_count was 0.")
             return jsonify({'message': 'Failed to update submission status'}), 500

        # --- Update Student Points/Progress if Approved ---
        student_id_obj = submission.get('userId')
        if status == 'approved' and points_awarded > 0 and student_id_obj and isinstance(student_id_obj, ObjectId):
            student = db.users.find_one({'_id': student_id_obj})
            if student and student.get('role') == 'student':
                # Define progress increase (e.g., based on points or fixed)
                progress_to_add = 5 # Example: 5% progress for approved submission
                update_student_result = db.users.update_one(
                    {'_id': student_id_obj},
                    {'$inc': {'points': points_awarded, 'progress': progress_to_add}}
                )
                if update_student_result.modified_count > 0:
                    # Fetch updated student data for ranking update
                    updated_student = db.users.find_one({'_id': student_id_obj})
                    _update_user_ranking(str(student_id_obj), stringify_ids(updated_student))
                    logger.info(f"Awarded {points_awarded} points, {progress_to_add}% progress to student {student_id_obj} for submission {submission_id_str}")
                else:
                     logger.warning(f"Failed to update points/progress for student {student_id_obj} after reviewing {submission_id_str}")


        # --- Prepare and Return Response ---
        updated_submission = db.submissions.find_one({'_id': submission_id_obj})
        response_data = stringify_ids(updated_submission) # Stringify all ObjectIds

        logger.info(f"Submission {submission_id_str} reviewed by {reviewer_email}. Status: {status}, Points: {points_awarded}")
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Review submission error: {e}", exc_info=True)
        return jsonify({'message': 'Server error during submission review'}), 500

@app.route('/api/flashcards/<category>', methods=['GET', 'OPTIONS'])
def get_flashcards(category):
    if request.method == 'OPTIONS':
        return '', 200
    return jsonify([{'_id': '1', 'question': 'Sample', 'answer': 'Answer'}])

@app.route('/api/flashcards/progress', methods=['POST'])
@token_required
def save_flashcard_progress():
    # This endpoint saves the *state* of flashcards (e.g., learned, reviewed count)
    # Points/score updates should happen via a separate "test complete" endpoint
    try:
        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        category = data.get('category')
        # Expecting 'progressData' based on script.js, which seems to be the list of cards
        progress_data_list = data.get('progressData')

        if not category or not isinstance(progress_data_list, list):
            return jsonify({'message': 'Category and progressData array required'}), 400

        # Prepare MongoDB update operations using dot notation
        update_ops = {}
        valid_updates_found = False
        for card_state in progress_data_list:
            if isinstance(card_state, dict):
                card_id = card_state.get('_id') # Assuming _id is passed in the state
                # Prepare the state to save (exclude _id itself from the saved value)
                state_to_save = {k: v for k, v in card_state.items() if k != '_id'}
                # Validate card_id and ensure there's something to save
                if card_id and ObjectId.is_valid(card_id) and state_to_save:
                     update_ops[f'flashcardProgress.{category}.{str(card_id)}'] = state_to_save
                     valid_updates_found = True

        if not valid_updates_found:
            logger.info(f"No valid flashcard progress updates provided for category '{category}' by user {user_id_obj}")
            # Return current progress state or just success
            current_user = db.users.find_one({'_id': user_id_obj}, {'flashcardProgress': 1})
            return jsonify({'message': 'No valid updates provided', 'flashcardProgress': current_user.get('flashcardProgress', {})})


        # Apply updates to the user document
        result = db.users.update_one({'_id': user_id_obj}, {'$set': update_ops})

        if result.matched_count > 0:
            logger.info(f"Flashcard progress saved for category '{category}' for user {user_id_obj}")
            # Return the updated progress sub-document
            updated_user = db.users.find_one({'_id': user_id_obj}, {'flashcardProgress': 1})
            return jsonify({'message': 'Progress saved successfully', 'flashcardProgress': updated_user.get('flashcardProgress', {})})
        else:
            return jsonify({'message': 'User not found'}), 404

    except Exception as e:
        logger.error(f"Save flashcard progress error: {e}", exc_info=True)
        return jsonify({'message': 'Server error saving flashcard progress'}), 500

@app.route('/api/flashcards/test/complete', methods=['POST'])
@token_required
def complete_flashcard_test():
    # This endpoint receives the *score* from a completed test and updates user points/progress
    try:
        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query
        user_role = request.current_user.get('role')

        # Only students earn points/progress from tests
        if user_role != 'student':
            logger.info(f"Flashcard test completion ignored for non-student user {user_id_obj}")
            return jsonify({'message': 'Only students earn points from tests'}), 200

        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        try:
            points_earned = int(data.get('score', 0))
            points_earned = max(0, points_earned) # Ensure non-negative
        except (ValueError, TypeError):
            return jsonify({'message': 'Invalid score provided'}), 400

        if points_earned == 0:
            logger.info(f"Flashcard test completed with 0 points for student {user_id_obj}")
            return jsonify({'message': 'Test completed, no points earned.'}), 200

        # Define progress gain for completing a test
        progress_earned = 5 # Example: 5% progress boost

        # Update user points and progress
        update_result = db.users.update_one(
            {'_id': user_id_obj},
            {'$inc': {'points': points_earned, 'progress': progress_earned}}
        )

        if update_result.modified_count > 0:
            # Fetch updated user data for ranking update and response
            updated_user = db.users.find_one({'_id': user_id_obj})
            _update_user_ranking(str(user_id_obj), stringify_ids(updated_user)) # Update ranking
            logger.info(f"Flashcard test recorded for student {user_id_obj}. Points: +{points_earned}, Progress: +{progress_earned}%")
            # Return updated user data (stringified)
            user_data_for_client = stringify_ids({k: v for k, v in updated_user.items() if k != 'password'})
            return jsonify({'message': f'Test completed! +{points_earned} points.', 'user': user_data_for_client})
        else:
            # User found but no change occurred (highly unlikely with $inc > 0)
            logger.warning(f"Flashcard test completion recorded for {user_id_obj}, but points/progress did not update.")
            # Return current user data
            current_user_data = db.users.find_one({'_id': user_id_obj}, {'password': 0})
            user_data_for_client = stringify_ids(current_user_data)
            return jsonify({'message': 'Test recorded, but no change in points/progress.', 'user': user_data_for_client}), 200

    except Exception as e:
        logger.error(f"Flashcard test complete error: {e}", exc_info=True)
        return jsonify({'message': 'Server error processing flashcard test completion'}), 500

@app.route('/api/challenges', methods=['GET'])
@token_required # Usually requires login
def get_challenges():
    try:
        # --- Pagination ---
        try: page = int(request.args.get('page', 1))
        except ValueError: page = 1
        try: limit = int(request.args.get('limit', 10))
        except ValueError: limit = 10
        limit = max(1, min(limit, 50)) # Clamp limit
        page = max(1, page)
        skip = (page - 1) * limit

        # --- Fetch Data ---
        challenges_cursor = db.challenges.find({}).sort('createdAt', -1).skip(skip).limit(limit)
        # <<< MODIFIED >>> Ensure _id is stringified correctly
        challenges = [stringify_ids(c) for c in challenges_cursor]

        total_challenges = db.challenges.count_documents({})
        total_pages = (total_challenges + limit - 1) // limit if limit > 0 else 0

        logger.info(f"Challenges fetched by user {request.current_user['_id']}. Page {page}, Limit {limit}. Found: {len(challenges)}/{total_challenges}")
        return jsonify({
            'challenges': challenges,
            'total': total_challenges,
            'page': page,
            'limit': limit,
            'totalPages': total_pages
        })
    except Exception as e:
        logger.error(f"Challenges fetch error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching challenges'}), 500



@app.route('/api/challenges/daily', methods=['GET'])
@token_required
def get_daily_challenge():
    try:
        # Get today's date in UTC
        today = datetime.now(timezone.utc).date()
        today_str = today.strftime('%Y-%m-%d')

        # Try to find a challenge specifically for today (not used in current structure)
        daily_challenge = None

        # If no challenge is specifically set for today, get a random active challenge
        if not daily_challenge:
            # Get the last challenge ID from yesterday (if available)
            yesterday_challenge_id = None
            try:
                # Check if we have a record of yesterday's challenge
                yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().strftime('%Y-%m-%d')
                yesterday_record = db.daily_challenges.find_one({'date': yesterday})
                if yesterday_record:
                    yesterday_challenge_id = yesterday_record.get('challenge_id')
                    logger.info(f"Found yesterday's challenge ID: {yesterday_challenge_id}")
            except Exception as e:
                logger.warning(f"Error getting yesterday's challenge: {e}")

            # Count active challenges
            query = {'active': True}
            # Exclude yesterday's challenge if we have it
            if yesterday_challenge_id:
                try:
                    # Convert string ID to ObjectId if needed
                    if isinstance(yesterday_challenge_id, str) and len(yesterday_challenge_id) == 24:
                        yesterday_challenge_id = ObjectId(yesterday_challenge_id)
                    query['_id'] = {'$ne': yesterday_challenge_id}
                except Exception as e:
                    logger.warning(f"Error excluding yesterday's challenge: {e}")

            active_count = db.challenges.count_documents(query)
            if active_count > 0:
                # Get a random skip value
                random_skip = random.randint(0, active_count - 1)
                # Get a random challenge (excluding yesterday's)
                daily_challenge = db.challenges.find_one(query, skip=random_skip)

                # Store today's challenge ID for tomorrow's reference
                if daily_challenge:
                    try:
                        db.daily_challenges.update_one(
                            {'date': today_str},
                            {'$set': {
                                'date': today_str,
                                'challenge_id': daily_challenge['_id'],
                                'updated_at': datetime.now(timezone.utc)
                            }},
                            upsert=True
                        )
                        logger.info(f"Stored today's challenge ID: {daily_challenge['_id']}")
                    except Exception as e:
                        logger.warning(f"Error storing today's challenge: {e}")

        # If still no challenge found, return an error
        if not daily_challenge:
            logger.warning("No daily challenge found in MongoDB.")
            return jsonify({'message': 'No daily challenge found in database'}), 404

        # Return the challenge (stringify ObjectIds)
        logger.info(f"Daily challenge fetched by user {request.current_user['_id']}")
        return jsonify(stringify_ids(daily_challenge))
    except Exception as e:
        logger.error(f"Daily challenge fetch error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching daily challenge'}), 500

@app.route('/api/learning-path', methods=['GET'])
@token_required # Usually requires login
def get_learning_path():
    try:
        # Fetch items sorted by 'order' field
        learning_path_cursor = db.learning_path.find().sort('order', 1)
        learning_path = [stringify_ids(item) for item in learning_path_cursor]

        logger.info(f"Learning path fetched for user {request.current_user['_id']}")
        return jsonify(learning_path)
    except Exception as e:
        logger.error(f"Learning path fetch error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching learning path'}), 500

# --- Mini-Game Routes (Using Mock Data - Consider moving to DB) ---
# MOCK DATA - REPLACE WITH DB if becomes complex
game_questions_db_mock = {
    'guess-note': [
        {'id': 'gn001', 'question': 'Nốt nhạc này là gì (tên đầy đủ)?', 'imageUrl': '/assets/images/games/note_do.png', 'answer': ['đô', 'do'], 'points': 10, 'level': 1},
        {'id': 'gn002', 'question': 'Nốt nhạc này là gì?', 'imageUrl': '/assets/images/games/note_re.png', 'answer': ['rê', 're'], 'points': 10, 'level': 1},
        {'id': 'gn003', 'question': 'Đây là nốt nhạc gì?', 'imageUrl': '/assets/images/games/note_mi.png', 'answer': ['mi'], 'points': 10, 'level': 1},
        {'id': 'gn004', 'question': 'Nốt nhạc này có tên là gì?', 'imageUrl': '/assets/images/games/note_fa.png', 'answer': ['fa'], 'points': 10, 'level': 1},
        {'id': 'gn005', 'question': 'Đây là nốt nhạc nào?', 'imageUrl': '/assets/images/games/note_sol.png', 'answer': ['son', 'sol'], 'points': 10, 'level': 1},
        {'id': 'gn006', 'question': 'Nốt nhạc trong hình là gì?', 'imageUrl': '/assets/images/games/note_la.png', 'answer': ['la'], 'points': 10, 'level': 1},
        {'id': 'gn007', 'question': 'Bạn có thể cho biết đây là nốt nhạc gì?', 'imageUrl': '/assets/images/games/note_si.png', 'answer': ['si'], 'points': 10, 'level': 1},
        {'id': 'gn008', 'question': 'Nốt nhạc này được gọi là gì trong âm nhạc?', 'imageUrl': '/assets/images/games/note_do.png', 'answer': ['đô', 'do'], 'points': 10, 'level': 1},
        {'id': 'gn009', 'question': 'Hãy cho biết tên của nốt nhạc này?', 'imageUrl': '/assets/images/games/note_re.png', 'answer': ['rê', 're'], 'points': 10, 'level': 1},
        {'id': 'gn010', 'question': 'Nốt nhạc này có tên gọi là gì?', 'imageUrl': '/assets/images/games/note_mi.png', 'answer': ['mi'], 'points': 10, 'level': 1},
    ],
    'listen-note': [
        {'id': 'ln001', 'question': 'Nghe âm thanh và đoán nốt nhạc này là gì?', 'audioUrl': '/assets/audio/notes/do.mp3', 'answer': ['đô', 'do'], 'points': 15, 'level': 2},
        {'id': 'ln002', 'question': 'Nghe âm thanh và cho biết đây là nốt nhạc nào?', 'audioUrl': '/assets/audio/notes/re.mp3', 'answer': ['rê', 're'], 'points': 15, 'level': 2},
        {'id': 'ln003', 'question': 'Âm thanh này là nốt nhạc gì?', 'audioUrl': '/assets/audio/notes/mi.mp3', 'answer': ['mi'], 'points': 15, 'level': 2},
        {'id': 'ln004', 'question': 'Hãy nghe và cho biết tên nốt nhạc:', 'audioUrl': '/assets/audio/notes/fa.mp3', 'answer': ['fa'], 'points': 15, 'level': 2},
        {'id': 'ln005', 'question': 'Nốt nhạc trong âm thanh này là gì?', 'audioUrl': '/assets/audio/notes/sol.mp3', 'answer': ['son', 'sol'], 'points': 15, 'level': 2},
        {'id': 'ln006', 'question': 'Nghe kỹ và đoán tên nốt nhạc:', 'audioUrl': '/assets/audio/notes/la.mp3', 'answer': ['la'], 'points': 15, 'level': 2},
        {'id': 'ln007', 'question': 'Âm thanh này tương ứng với nốt nhạc nào?', 'audioUrl': '/assets/audio/notes/si.mp3', 'answer': ['si'], 'points': 15, 'level': 2},
        {'id': 'ln008', 'question': 'Đây là âm thanh của nốt nhạc gì?', 'audioUrl': '/assets/audio/notes/do.mp3', 'answer': ['đô', 'do'], 'points': 15, 'level': 2},
        {'id': 'ln009', 'question': 'Nghe và nhận biết nốt nhạc này:', 'audioUrl': '/assets/audio/notes/re.mp3', 'answer': ['rê', 're'], 'points': 15, 'level': 2},
        {'id': 'ln010', 'question': 'Nốt nhạc phát ra trong âm thanh này là gì?', 'audioUrl': '/assets/audio/notes/mi.mp3', 'answer': ['mi'], 'points': 15, 'level': 2},
    ],
    'match-note': [
        {'id': 'mn001', 'question': 'Nghe âm thanh và chọn nốt nhạc tương ứng:', 'audioUrl': '/assets/audio/notes/do.mp3', 'answer': ['đô', 'do'], 'points': 20, 'level': 3,
         'options': [
            {'id': 'opt1', 'imageUrl': '/assets/images/games/note_do.png', 'label': 'Đô'},
            {'id': 'opt2', 'imageUrl': '/assets/images/games/note_re.png', 'label': 'Rê'},
            {'id': 'opt3', 'imageUrl': '/assets/images/games/note_mi.png', 'label': 'Mi'},
            {'id': 'opt4', 'imageUrl': '/assets/images/games/note_fa.png', 'label': 'Fa'}
         ]},
        {'id': 'mn002', 'question': 'Nghe âm thanh và chọn nốt nhạc tương ứng:', 'audioUrl': '/assets/audio/notes/re.mp3', 'answer': ['rê', 're'], 'points': 20, 'level': 3,
         'options': [
            {'id': 'opt1', 'imageUrl': '/assets/images/games/note_sol.png', 'label': 'Sol'},
            {'id': 'opt2', 'imageUrl': '/assets/images/games/note_re.png', 'label': 'Rê'},
            {'id': 'opt3', 'imageUrl': '/assets/images/games/note_la.png', 'label': 'La'},
            {'id': 'opt4', 'imageUrl': '/assets/images/games/note_si.png', 'label': 'Si'}
         ]},
        {'id': 'mn003', 'question': 'Nghe âm thanh và chọn nốt nhạc tương ứng:', 'audioUrl': '/assets/audio/notes/mi.mp3', 'answer': ['mi'], 'points': 20, 'level': 3,
         'options': [
            {'id': 'opt1', 'imageUrl': '/assets/images/games/note_fa.png', 'label': 'Fa'},
            {'id': 'opt2', 'imageUrl': '/assets/images/games/note_sol.png', 'label': 'Sol'},
            {'id': 'opt3', 'imageUrl': '/assets/images/games/note_mi.png', 'label': 'Mi'},
            {'id': 'opt4', 'imageUrl': '/assets/images/games/note_do.png', 'label': 'Đô'}
         ]},
        {'id': 'mn004', 'question': 'Nghe âm thanh và chọn nốt nhạc tương ứng:', 'audioUrl': '/assets/audio/notes/fa.mp3', 'answer': ['fa'], 'points': 20, 'level': 3,
         'options': [
            {'id': 'opt1', 'imageUrl': '/assets/images/games/note_fa.png', 'label': 'Fa'},
            {'id': 'opt2', 'imageUrl': '/assets/images/games/note_la.png', 'label': 'La'},
            {'id': 'opt3', 'imageUrl': '/assets/images/games/note_si.png', 'label': 'Si'},
            {'id': 'opt4', 'imageUrl': '/assets/images/games/note_re.png', 'label': 'Rê'}
         ]},
        {'id': 'mn005', 'question': 'Nghe âm thanh và chọn nốt nhạc tương ứng:', 'audioUrl': '/assets/audio/notes/sol.mp3', 'answer': ['son', 'sol'], 'points': 20, 'level': 3,
         'options': [
            {'id': 'opt1', 'imageUrl': '/assets/images/games/note_mi.png', 'label': 'Mi'},
            {'id': 'opt2', 'imageUrl': '/assets/images/games/note_sol.png', 'label': 'Sol'},
            {'id': 'opt3', 'imageUrl': '/assets/images/games/note_do.png', 'label': 'Đô'},
            {'id': 'opt4', 'imageUrl': '/assets/images/games/note_re.png', 'label': 'Rê'}
         ]},
        {'id': 'mn006', 'question': 'Nghe âm thanh và chọn nốt nhạc tương ứng:', 'audioUrl': '/assets/audio/notes/la.mp3', 'answer': ['la'], 'points': 20, 'level': 3,
         'options': [
            {'id': 'opt1', 'imageUrl': '/assets/images/games/note_si.png', 'label': 'Si'},
            {'id': 'opt2', 'imageUrl': '/assets/images/games/note_fa.png', 'label': 'Fa'},
            {'id': 'opt3', 'imageUrl': '/assets/images/games/note_la.png', 'label': 'La'},
            {'id': 'opt4', 'imageUrl': '/assets/images/games/note_mi.png', 'label': 'Mi'}
         ]},
        {'id': 'mn007', 'question': 'Nghe âm thanh và chọn nốt nhạc tương ứng:', 'audioUrl': '/assets/audio/notes/si.mp3', 'answer': ['si'], 'points': 20, 'level': 3,
         'options': [
            {'id': 'opt1', 'imageUrl': '/assets/images/games/note_re.png', 'label': 'Rê'},
            {'id': 'opt2', 'imageUrl': '/assets/images/games/note_si.png', 'label': 'Si'},
            {'id': 'opt3', 'imageUrl': '/assets/images/games/note_sol.png', 'label': 'Sol'},
            {'id': 'opt4', 'imageUrl': '/assets/images/games/note_la.png', 'label': 'La'}
         ]},
        {'id': 'mn008', 'question': 'Nghe âm thanh và chọn nốt nhạc tương ứng:', 'audioUrl': '/assets/audio/notes/do.mp3', 'answer': ['đô', 'do'], 'points': 20, 'level': 3,
         'options': [
            {'id': 'opt1', 'imageUrl': '/assets/images/games/note_do.png', 'label': 'Đô'},
            {'id': 'opt2', 'imageUrl': '/assets/images/games/note_mi.png', 'label': 'Mi'},
            {'id': 'opt3', 'imageUrl': '/assets/images/games/note_sol.png', 'label': 'Sol'},
            {'id': 'opt4', 'imageUrl': '/assets/images/games/note_si.png', 'label': 'Si'}
         ]},
        {'id': 'mn009', 'question': 'Nghe âm thanh và chọn nốt nhạc tương ứng:', 'audioUrl': '/assets/audio/notes/re.mp3', 'answer': ['rê', 're'], 'points': 20, 'level': 3,
         'options': [
            {'id': 'opt1', 'imageUrl': '/assets/images/games/note_fa.png', 'label': 'Fa'},
            {'id': 'opt2', 'imageUrl': '/assets/images/games/note_re.png', 'label': 'Rê'},
            {'id': 'opt3', 'imageUrl': '/assets/images/games/note_do.png', 'label': 'Đô'},
            {'id': 'opt4', 'imageUrl': '/assets/images/games/note_la.png', 'label': 'La'}
         ]},
        {'id': 'mn010', 'question': 'Nghe âm thanh và chọn nốt nhạc tương ứng:', 'audioUrl': '/assets/audio/notes/mi.mp3', 'answer': ['mi'], 'points': 20, 'level': 3,
         'options': [
            {'id': 'opt1', 'imageUrl': '/assets/images/games/note_la.png', 'label': 'La'},
            {'id': 'opt2', 'imageUrl': '/assets/images/games/note_si.png', 'label': 'Si'},
            {'id': 'opt3', 'imageUrl': '/assets/images/games/note_mi.png', 'label': 'Mi'},
            {'id': 'opt4', 'imageUrl': '/assets/images/games/note_sol.png', 'label': 'Sol'}
         ]},
    ],
    'guess-pose': [
        {'id': 'gp001', 'question': 'Thế võ Vovinam này?', 'imageUrl': '/assets/images/games/pose_dontay1.png', 'answer': ['đòn tay số 1', 'đòn tay 1', 'don tay 1'], 'points': 15},
        {'id': 'gp002', 'question': 'Tên thế võ này là gì?', 'imageUrl': '/assets/images/games/pose_chemso4.png', 'answer': ['chém số 4', 'chem so 4', 'đòn chân số 4', 'don chan 4'], 'points': 15},
    ],
    'guess-stance': [
        {'id': 'gs001', 'question': 'Tên thế tấn này?', 'imageUrl': '/assets/images/games/stance_trungbinhtan.png', 'answer': ['trung bình tấn', 'trung binh tan'], 'points': 12},
        {'id': 'gs002', 'question': 'Đây là thế tấn gì trong Vovinam?', 'imageUrl': '/assets/images/games/stance_chuadinh.png', 'answer': ['thế tấn chữ đinh', 'tấn chữ đinh', 'chữ đinh tấn', 'chu dinh tan', 'tan chu dinh'], 'points': 12},
    ]
}
# Create a flat lookup for faster answer checking by ID
game_questions_lookup = {q['id']: q for type_list in game_questions_db_mock.values() for q in type_list}
# END MOCK

@app.route('/api/mini-game/start', methods=['GET'])
@token_required
def start_mini_game():
     try:
         user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query

         # Get game type and level from query params
         game_type = request.args.get('type')
         level = request.args.get('level')

         if not game_type:
             return jsonify({'message': 'Game type required'}), 400
         if game_type not in game_questions_db_mock or not game_questions_db_mock[game_type]:
             # Log available types if type is invalid
             logger.warning(f"Invalid game type requested: '{game_type}'. Available: {list(game_questions_db_mock.keys())}")
             return jsonify({'message': f'Invalid or no questions available for game type: {game_type}'}), 404

         # Filter questions by level if specified
         available_questions = game_questions_db_mock[game_type]
         if level:
             try:
                 level_int = int(level)
                 available_questions = [q for q in available_questions if q.get('level', 1) == level_int]
             except ValueError:
                 # If level is not a valid integer, ignore it
                 pass

         if not available_questions:
             return jsonify({'message': f'No questions available for game type {game_type} and level {level}'}), 404

         # Select a random question from the filtered list
         game_data = random.choice(available_questions)

         # Prepare response for the frontend
         response_data = {
             'gameId': game_data['id'],
             'question': game_data['question'],
             'imageUrl': game_data.get('imageUrl'), # Include if available
             'audioUrl': game_data.get('audioUrl'), # Include audio URL if available
             'gameType': game_type, # Include type for context if needed
             'level': game_data.get('level', 1) # Include level
         }

         # Include options for multiple choice questions (level 3)
         if game_data.get('options'):
             response_data['options'] = game_data['options']

         logger.info(f"Mini-game '{game_type}' (ID: {game_data['id']}) level {game_data.get('level', 1)} started for user {request.current_user['_id']}")
         return jsonify(response_data)
     except Exception as e:
         logger.error(f"Start mini-game error: {e}", exc_info=True)
         return jsonify({'message': 'Server error starting mini-game'}), 500

@app.route('/api/mini-game/submit', methods=['POST'])
@token_required
def submit_mini_game_answer():
    try:
        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query
        user_role = request.current_user.get('role')

        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        game_id = data.get('gameId')
        user_answer = data.get('answer', '').lower().strip() # Normalize answer

        if not game_id or not user_answer:
            return jsonify({'message': 'Game ID and answer required'}), 400

        # Lookup game data using the ID (from MOCK data for now)
        game_data = game_questions_lookup.get(game_id)
        if not game_data:
            return jsonify({'message': 'Invalid game ID'}), 404

        # Check answer (case-insensitive)
        correct_answer_list = [ans.lower() for ans in game_data.get('answer', [])]
        points_to_award = game_data.get('points', 10) # Default points
        is_correct = user_answer in correct_answer_list

        # Prepare response structure
        response_data = {
            'isCorrect': is_correct,
            'pointsAwarded': 0,
            # Include correct answer in response if user was wrong
            'correctAnswer': correct_answer_list[0] if not is_correct and correct_answer_list else None
        }

        # Award points and update ranking if correct and user is a student
        if is_correct and user_role == 'student':
            response_data['pointsAwarded'] = points_to_award
            update_result = db.users.update_one(
                {'_id': user_id_obj},
                {'$inc': {'points': points_to_award}}
            )
            if update_result.modified_count > 0:
                # Fetch updated user data for ranking update
                updated_user = db.users.find_one({'_id': user_id_obj})
                _update_user_ranking(str(user_id_obj), stringify_ids(updated_user))
                logger.info(f"Mini-game {game_id} correct for student {user_id_obj}. Points: +{points_to_award}")
            else:
                 logger.warning(f"Mini-game {game_id} correct, but failed to update points for student {user_id_obj}.")

        elif is_correct:
             logger.info(f"Mini-game {game_id} correct for non-student {user_id_obj}. No points awarded.")
        else:
             logger.info(f"Mini-game {game_id} incorrect for user {user_id_obj}. Answer: '{user_answer}', Correct: {correct_answer_list}")

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Submit mini-game answer error: {e}", exc_info=True)
        return jsonify({'message': 'Server error submitting mini-game answer'}), 500

@app.route('/api/chat', methods=['POST'])
@token_required
def chat_with_gemini():
    # Check if API key is configured
    if not GEMINI_API_KEY:
        logger.error("Chatbot request received but GEMINI_API_KEY is not configured.")
        return jsonify({'reply': 'Sorry, the chatbot is currently unavailable (Configuration Error).'}), 503 # Service Unavailable

    try:
        user_info = request.current_user # Already stringified
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        # Get question (which includes context/prompt from frontend)
        question_with_context = data.get('question', '').strip()
        # Get optional chat history from frontend for context
        chat_history = data.get('history', [])

        if not question_with_context:
            return jsonify({'message': 'Question required'}), 400

        # --- Prepare payload for Gemini API ---
        contents = []
        # Add validated history (basic check)
        if isinstance(chat_history, list):
            valid_history = [
                msg for msg in chat_history
                if isinstance(msg, dict) and
                   msg.get('role') in ['user', 'model'] and # Valid roles
                   isinstance(msg.get('parts'), list) and len(msg['parts']) > 0 and
                   isinstance(msg['parts'][0].get('text'), str) # Basic text part check
            ]
            contents.extend(valid_history)
        # Add the current user question
        contents.append({"role": "user", "parts": [{"text": question_with_context}]})

        # API Payload
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7, # Controls randomness (0=deterministic, 1=creative)
                "topK": 40,         # Considers top K tokens
                "topP": 0.95,       # Considers tokens with cumulative probability >= P
                "maxOutputTokens": 1500, # Limit response length
                # "stopSequences": ["\n\n"] # Optional sequences to stop generation
            },
            "safetySettings": [ # Configure safety filters
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
        }

        # --- Make API Call ---
        api_url_with_key = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}

        logger.info(f"Sending chat request to Gemini for user {user_info['_id']}...")
        # Set a reasonable timeout (e.g., 45 seconds)
        response = requests.post(api_url_with_key, headers=headers, json=payload, timeout=45)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        response_data = response.json()

        # --- Process Response ---
        # Check for blocked content or missing candidates
        if not response_data.get('candidates'):
             block_reason = response_data.get('promptFeedback', {}).get('blockReason', 'Unknown')
             safety_ratings = response_data.get('promptFeedback', {}).get('safetyRatings', [])
             logger.warning(f"Gemini response blocked or empty for user {user_info['_id']}. Reason: {block_reason}, Ratings: {safety_ratings}")
             # Provide a user-friendly message based on reason if possible
             reply_message = "I cannot provide a response due to content restrictions."
             if block_reason == 'SAFETY':
                 reply_message = "My safety filters prevented generating a response for this topic."
             return jsonify({'reply': reply_message})

        # Extract reply text
        try:
            reply = response_data['candidates'][0]['content']['parts'][0]['text']
        except (IndexError, KeyError) as e:
             logger.error(f"Error parsing Gemini response structure for user {user_info['_id']}: {e}. Response: {response_data}")
             return jsonify({'reply': 'Sorry, I encountered an issue processing the response.'})


        # Check finish reason (optional, but informative)
        finish_reason = response_data['candidates'][0].get('finishReason', 'STOP')
        if finish_reason != 'STOP':
            logger.warning(f"Gemini generation finished with reason: {finish_reason} for user {user_info['_id']}")
            if finish_reason == 'MAX_TOKENS':
                reply += "\n(Note: My response might have been cut short.)"
            elif finish_reason == 'SAFETY':
                # This case might be handled by the 'candidates' check earlier, but double-check
                reply = "The generated response was partially blocked due to safety filters."
            elif finish_reason == 'RECITATION':
                 reply += "\n(Note: Response might contain recited content.)"


        logger.info(f"Chatbot reply generated successfully for user {user_info['_id']}")
        return jsonify({'reply': reply.strip()})

    # --- Error Handling for API Call ---
    except requests.exceptions.HTTPError as e:
         status_code = e.response.status_code
         error_detail = e.response.text
         logger.error(f"Gemini API HTTP error ({status_code}) for user {request.current_user['_id']}: {error_detail}")
         reply = f"Sorry, the AI service encountered an error ({status_code}). Please try again later."
         if status_code == 429: # Too Many Requests
             reply = "The chatbot is experiencing high traffic right now. Please try again in a moment."
         elif status_code >= 500: # Server errors
              reply = "The AI service is temporarily unavailable. Please try again later."
         # Return the appropriate status code from the API if possible
         return jsonify({'reply': reply}), status_code if status_code in [429, 500, 503] else 502 # Bad Gateway
    except requests.exceptions.Timeout:
        logger.error(f"Gemini API request timed out for user {request.current_user['_id']}")
        return jsonify({'reply': 'The AI assistant took too long to respond. Please try again.'}), 504 # Gateway Timeout
    except requests.exceptions.RequestException as e:
        # Catch other network-related errors (DNS, connection refused, etc.)
        logger.error(f"Network error calling Gemini API: {e}")
        return jsonify({'reply': 'There was a network problem connecting to the AI assistant.'}), 504 # Gateway Timeout
    except Exception as e:
        # Catch-all for unexpected errors during processing
        logger.error(f"Chat processing error: {e}", exc_info=True)
        return jsonify({'message': 'Server error processing chat request'}), 500

# --- Static File Serving (Uploads) ---

@app.route('/uploads/avatars/<path:filename>')
def serve_avatar(filename):
    # Serve avatar files, no authentication needed usually
    try:
        # Basic security check
        if '..' in filename or filename.startswith('/'):
            raise ValueError("Invalid filename pattern")
        return send_from_directory(UPLOAD_FOLDER_AVATARS, filename)
    except FileNotFoundError:
        logger.warning(f"Avatar file not found: {filename}")
        # Return a default avatar or 404
        # return send_from_directory('path/to/defaults', 'default_avatar.png')
        return jsonify({'message': 'Avatar not found'}), 404
    except ValueError as e:
        logger.warning(f"Invalid avatar filename request: {filename}. Error: {e}")
        return jsonify({'message': 'Invalid filename'}), 400
    except Exception as e:
        logger.error(f"Serve avatar error: {e}")
        return jsonify({'message': 'Server error serving avatar'}), 500

@app.route('/uploads/submissions/<path:filename>')
@token_required # Require login to access submission files
def serve_submission(filename):
    # Serve submission files, requires authentication and authorization
    try:
        # Basic security check
        if '..' in filename or filename.startswith('/'):
            raise ValueError("Invalid filename pattern")

        # Construct the URL path as stored in the database
        file_url_path = f"/uploads/submissions/{filename}"

        # Find the submission document by its URL
        submission = db.submissions.find_one({'url': file_url_path})
        if not submission:
             # Try finding by just filename if URL storage might be inconsistent
             alt_submission = db.submissions.find_one({'originalFilename': filename}) # Less reliable
             if alt_submission: submission = alt_submission
             else:
                logger.warning(f"Submission file or record not found for filename: {filename} (URL Path: {file_url_path})")
                return jsonify({'message': 'Submission record not found or file path mismatch'}), 404


        # --- Authorization Check ---
        user_id_str = request.current_user['_id'] # Requesting user (string)
        user_role = request.current_user['role']
        submission_owner_id_str = str(submission.get('userId')) # Owner (stringified)

        # Allow access if user is the owner OR if user is a teacher
        if user_id_str == submission_owner_id_str or user_role == 'teacher':
            logger.info(f"Serving submission '{filename}' to user {user_id_str} (Role: {user_role})")
            # Send the file from the correct directory
            return send_from_directory(UPLOAD_FOLDER_SUBMISSIONS, filename, as_attachment=False) # Display inline if possible
        else:
            # User is neither the owner nor a teacher
            logger.warning(f"Unauthorized attempt to access submission '{filename}' by user {user_id_str}")
            return jsonify({'message': 'Unauthorized access to this submission'}), 403

    except FileNotFoundError:
        # This means the file exists in DB record but not on disk
        logger.error(f"Submission file missing on disk: {filename}. DB record exists for URL: {file_url_path}")
        return jsonify({'message': 'Submission file data missing on server'}), 404
    except ValueError as e:
        logger.warning(f"Invalid submission filename request: {filename}. Error: {e}")
        return jsonify({'message': 'Invalid filename'}), 400
    except Exception as e:
        logger.error(f"Serve submission error: {e}")
        return jsonify({'message': 'Server error serving submission'}), 500


# --- Feedback Routes ---

@app.route('/api/feedback', methods=['POST'])
@token_required
def submit_feedback():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        feedback_text = data.get('text', '').strip()
        if not feedback_text:
            return jsonify({'message': 'Feedback text cannot be empty'}), 400

        # Get context URL (optional)
        page_url = data.get('url', request.referrer) # Use referrer as fallback

        # Create feedback document
        feedback_doc = {
            'userId': ObjectId(request.current_user['_id']), # Store as ObjectId
            'userName': request.current_user.get('name', 'Anonymous'), # Use current name
            'userEmail': request.current_user.get('email'),
            'text': feedback_text,
            'url': page_url, # URL where feedback was submitted
            'createdAt': datetime.now(timezone.utc),
            'status': 'new', # Initial status
            'reply': None,   # Teacher's reply
            'repliedAt': None,
            'repliedBy': None # Teacher's ObjectId
        }

        result = db.feedback.insert_one(feedback_doc)
        # Prepare response data (stringify IDs)
        response_data = stringify_ids(feedback_doc)
        response_data['_id'] = str(result.inserted_id) # Ensure _id from insert result is used

        logger.info(f"Feedback received from user {request.current_user['_id']} (Name: {response_data['userName']})")
        return jsonify({'message': 'Feedback submitted successfully!', 'feedback': response_data}), 201

    except Exception as e:
        logger.error(f"Submit feedback error: {e}", exc_info=True)
        return jsonify({'message': 'Server error submitting feedback'}), 500

@app.route('/api/feedback', methods=['GET'])
@token_required
def get_feedback():
    # Get feedback: Teachers see all, students see their own
    try:
        user_id_str = request.current_user['_id'] # Already string
        user_role = request.current_user['role']
        query = {}
        limit = int(request.args.get('limit', 20)) # Paginate results
        limit = max(1, min(limit, 100))

        if user_role != 'teacher':
            # Students only see their feedback
            query['userId'] = ObjectId(user_id_str) # Query by ObjectId

        # Optional status filter (e.g., /api/feedback?status=new)
        status_filter = request.args.get('status')
        if status_filter:
            query['status'] = status_filter.lower()


        feedback_cursor = db.feedback.find(query).sort('createdAt', -1).limit(limit)
        feedback_list = [stringify_ids(fb) for fb in feedback_cursor] # Stringify results

        logger.info(f"Feedback list fetched by user {user_id_str} ({user_role}). Filter: {query}, Limit: {limit}")
        return jsonify(feedback_list)

    except Exception as e:
        logger.error(f"Get feedback error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching feedback'}), 500

@app.route('/api/feedback/<feedback_id_str>/reply', methods=['PUT'])
@teacher_required # Only teachers can reply
def reply_to_feedback(feedback_id_str):
     try:
        if not ObjectId.is_valid(feedback_id_str):
            return jsonify({'message': 'Invalid feedback ID format'}), 400
        feedback_id_obj = ObjectId(feedback_id_str)
        replier_id_obj = ObjectId(request.current_user['_id']) # Teacher's ObjectId

        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        reply_text = data.get('reply', '').strip()
        # Allow setting status when replying (e.g., 'addressed', 'viewed')
        new_status = data.get('status', 'addressed').lower() # Default to addressed

        if not reply_text:
            return jsonify({'message': 'Reply text cannot be empty'}), 400
        if new_status not in ['new', 'viewed', 'addressed', 'rejected', 'spam']: # Define allowed statuses
             return jsonify({'message': f'Invalid status provided: {new_status}'}), 400

        # --- Update Feedback Document ---
        update_fields = {
            'reply': reply_text,
            'status': new_status,
            'repliedAt': datetime.now(timezone.utc),
            'repliedBy': replier_id_obj # Store teacher's ObjectId
        }
        result = db.feedback.update_one({'_id': feedback_id_obj}, {'$set': update_fields})

        if result.matched_count == 0:
            return jsonify({'message': 'Feedback item not found'}), 404
        if result.modified_count == 0:
            # May happen if update fields are same as existing
            logger.warning(f"Feedback {feedback_id_str} reply submitted, but no fields were modified.")


        # --- Fetch and Return Updated Feedback ---
        updated_feedback = db.feedback.find_one({'_id': feedback_id_obj})
        response_data = stringify_ids(updated_feedback) # Stringify ObjectIds

        logger.info(f"Feedback {feedback_id_str} replied/status updated by teacher {request.current_user['_id']}. New Status: {new_status}")
        # TODO: Optionally notify the student who submitted the feedback
        return jsonify({'message': 'Feedback updated successfully', 'feedback': response_data})

     except Exception as e:
        logger.error(f"Reply feedback error: {e}", exc_info=True)
        return jsonify({'message': 'Server error replying to feedback'}), 500


# --- Main Execution ---
if __name__ == '__main__':
    print(f"--- Attempting to start server on port {PORT} ---")
    logger.info(f"--- Starting FPT Learning Hub Server (PID: {os.getpid()}) ---")
    # Use Waitress for production, fallback to Flask dev server
    try:
        from waitress import serve
        logger.info(f"Starting server with Waitress on http://0.0.0.0:{PORT}")
        print(f"--- Production Server (Waitress) running on http://0.0.0.0:{PORT} ---")
        # Adjust threads as needed based on expected load and server cores
        serve(app, host='0.0.0.0', port=PORT, threads=8)
    except ImportError:
        logger.warning("Waitress not found, using Flask development server (NOT FOR PRODUCTION).")
        print(f"--- Development Server (Flask) running on http://0.0.0.0:{PORT} ---")
        # Set debug=True for development features like auto-reloading and debugger
        # Ensure debug=False in production environments
        app.run(host='0.0.0.0', port=PORT, debug=False) # Set debug=False for production simulation
    except Exception as e:
        print(f"!!! SERVER STARTUP FAILED: {e} !!!")
        logger.critical(f"Server failed to start: {e}", exc_info=True)
        raise # Reraise exception to indicate failure
init.py
# backend/app.py
import os
import jwt
import logging
import random
from datetime import datetime, timedelta, timezone
from functools import wraps
import time # <<< ADDED >>>
import json # <<< ADDED >>>
from flask import Flask, request, jsonify, send_from_directory, Response # <<< MODIFIED (Added Response) >>>
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
from bson import ObjectId
from bson.errors import InvalidId
import requests

# --- Setup logging ---
log_dir = 'backend/logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, 'app.log')
# Prevent duplicate handlers if script is reloaded (e.g., in development)
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    # filename=log_file, # Comment out for easier viewing during development/debugging
    level=logging.INFO, # Use INFO for production, DEBUG for development
    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]',
    handlers=[ # Use handlers for both file and console
        logging.FileHandler(log_file),
        logging.StreamHandler() # Output to console
    ]
)
logger = logging.getLogger(__name__)
logger.info("--- Logging Initialized ---")

# --- Load environment variables ---
load_dotenv()
logger.info("Loading environment variables")
JWT_SECRET = os.getenv("JWT_SECRET")
MONGO_URI = os.getenv("MONGO_URI")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", 5001))

# --- Environment Variable Checks ---
if not MONGO_URI: logger.critical("CRITICAL: MONGO_URI not set."); raise SystemExit("MONGO_URI not set")
if not JWT_SECRET: logger.critical("CRITICAL: JWT_SECRET not set."); raise SystemExit("JWT_SECRET not set")
if not GEMINI_API_KEY: logger.warning("WARNING: GEMINI_API_KEY not set. Chatbot disabled.")

# --- Initialize Flask app ---
app = Flask(__name__)
# Consider more specific origins in production
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True) # Allow all origins for now
logger.info("Flask app initialized with CORS")

# --- MongoDB connection ---
try:
    logger.info(f"Connecting to MongoDB...")
    # Increased timeouts for potentially slower connections
    client = MongoClient( MONGO_URI, serverSelectionTimeoutMS=10000, connectTimeoutMS=20000, retryWrites=True, w='majority')
    # The ismaster command is cheap and does not require auth.
    client.admin.command('ping')
    db = client['fpt_learning'] # Explicitly use 'fpt_learning' database
    logger.info(f"Connected to MongoDB (DB: {db.name})")
except ConnectionFailure as e:
    logger.critical(f"CRITICAL: MongoDB ConnectionFailure: {e}"); raise SystemExit(f"MongoDB connection failed: {e}")
except Exception as e:
    logger.critical(f"CRITICAL: MongoDB connection error: {e}"); raise SystemExit(f"MongoDB connection failed: {e}")

# --- Gemini API endpoint ---
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"

# --- Upload Folders Setup ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER_AVATARS = os.path.join(BASE_DIR, 'uploads', 'avatars')
UPLOAD_FOLDER_SUBMISSIONS = os.path.join(BASE_DIR, 'uploads', 'submissions')
ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_SUBMISSION_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm', 'pdf', 'doc', 'docx'}
MAX_AVATAR_SIZE = 2 * 1024 * 1024 # 2MB
MAX_SUBMISSION_SIZE = 50 * 1024 * 1024 # 50MB

os.makedirs(UPLOAD_FOLDER_AVATARS, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_SUBMISSIONS, exist_ok=True)
logger.info(f"Upload folders checked/created.")

# --- Helper Functions ---
def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

# Convert ObjectId to string in nested structures (lists/dicts)
def stringify_ids(data):
    if isinstance(data, list):
        return [stringify_ids(item) for item in data]
    elif isinstance(data, dict):
        return {key: stringify_ids(value) for key, value in data.items()}
    elif isinstance(data, ObjectId):
        return str(data)
    else:
        return data

# --- Ensure collections and indexes ---
def ensure_db_setup():
    # Collections
    required_collections = ['users', 'courses', 'rankings', 'flashcards', 'challenges', 'learning_path', 'submissions', 'feedback']
    existing_collections = db.list_collection_names()
    for coll_name in required_collections:
        if coll_name not in existing_collections:
            try:
                db.create_collection(coll_name)
                logger.info(f"Created collection: '{coll_name}'")
            except Exception as e:
                logger.error(f"Error creating collection '{coll_name}': {e}")
    # Indexes
    try:
        # users collection
        db.users.create_index([("email", 1)], unique=True, name="email_unique")
        db.users.create_index([("points", -1)], name="user_points_desc") # For potential internal sorting

        # courses collection
        db.courses.create_index([("category", 1)], name="course_category")

        # rankings collection
        # Use sparse=True if not all users might be in rankings (e.g., only students)
        db.rankings.create_index([("userId", 1)], unique=True, sparse=True, name="ranking_userId_unique")
        db.rankings.create_index([("points", -1)], name="ranking_points_desc") # Crucial for fetching sorted rankings

        # flashcards collection
        db.flashcards.create_index([("category", 1)], name="flashcard_category")

        # challenges collection
        db.challenges.create_index([("createdAt", -1)], name="challenge_created_desc")

        # learning_path collection
        db.learning_path.create_index([("order", 1)], name="learningpath_order")

        # submissions collection
        db.submissions.create_index([("userId", 1), ("createdAt", -1)], name="submission_user_created")
        db.submissions.create_index([("status", 1), ("type", 1)], name="submission_status_type") # For filtering by status/type

        # feedback collection
        db.feedback.create_index([("createdAt", -1)], name="feedback_created_desc")

        logger.info("MongoDB indexes checked/ensured.")
    except Exception as e:
        logger.error(f"Error ensuring MongoDB indexes: {e}")
# Run setup on startup
ensure_db_setup()

# --- Token Middleware ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            return jsonify({'message': 'Token missing or invalid'}), 401
        try:
            token = token.split(" ")[1]
            # Decode token, checking expiration
            data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"verify_exp": True})
            user_id = data.get('id')
            if not user_id or not ObjectId.is_valid(user_id):
                return jsonify({'message': 'Invalid token payload'}), 401

            # Fetch user details from DB, excluding password
            user_info = db.users.find_one({'_id': ObjectId(user_id)}, {'password': 0})
            if not user_info:
                return jsonify({'message': 'User not found'}), 401

            # Stringify ObjectIds before attaching to request
            request.current_user = stringify_ids(user_info)

        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except (jwt.InvalidTokenError, jwt.DecodeError, InvalidId) as e:
            logger.warning(f"Auth failed: {e}")
            return jsonify({'message': 'Invalid token'}), 401
        except Exception as e:
            logger.error(f"Token processing error: {e}", exc_info=True)
            return jsonify({'message': 'Token processing error'}), 500
        return f(*args, **kwargs)
    return decorated

# --- Authorization Middleware ---
def teacher_required(f):
    @wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        if request.current_user.get('role') != 'teacher':
            return jsonify({'message': 'Access forbidden: Teacher role required'}), 403
        return f(*args, **kwargs)
    return decorated

# --- Helper: Update Ranking ---
def _update_user_ranking(user_id_str, user_data):
     # Only update rankings for students
     if not user_data or user_data.get('role') != 'student':
         return

     try:
         # Use user_id_str which should already be stringified
         db.rankings.update_one(
             {'userId': user_id_str}, # Filter by the string representation of the user ID
             {'$set': {
                 'points': user_data.get('points', 0),
                 'name': user_data.get('name', 'Unknown'),
                 'avatar': user_data.get('avatar', ''),
                 'level': user_data.get('level', 1)
                 # Add any other fields relevant to ranking display
             }},
             upsert=True # Create the ranking document if it doesn't exist
         )
         # <<< MODIFIED >>>: Removed logging here, SSE polling logs changes detected
         # logger.info(f"Ranking data updated in DB for student {user_id_str}")
     except Exception as e:
          logger.error(f"Failed to update ranking for user {user_id_str}: {e}")

# --- Routes ---

@app.route('/api/status', methods=['GET'])
def check_status():
    mongo_status = 'disconnected'
    mongo_db_name = 'N/A'
    try:
        # Check MongoDB connection
        client.admin.command('ping')
        mongo_status = 'connected'
        mongo_db_name = db.name
        logger.info("Status check: OK, MongoDB connected")
        return jsonify({
            'status': 'Server is running',
            'mongodb_status': mongo_status,
            'database_name': mongo_db_name
        }), 200
    except Exception as e:
        logger.error(f"Status check failed: MongoDB connection error: {str(e)}")
        return jsonify({
            'status': 'Server running',
            'mongodb_status': mongo_status,
            'error': str(e)
        }), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        role = data.get('role', 'student').lower() # Default to student

        # --- Basic Validation ---
        errors = {}
        if not email: errors['email'] = 'Email is required'
        elif '@' not in email or '.' not in email.split('@')[-1] or len(email.split('@')[-1].split('.')) < 2 : errors['email'] = 'Invalid email format'
        if not password: errors['password'] = 'Password is required'
        elif len(password) < 6: errors['password'] = 'Password must be at least 6 characters long'
        if not name: errors['name'] = 'Name is required'
        if role not in ['student', 'teacher']: errors['role'] = 'Invalid role specified'

        if errors:
            return jsonify({'message': 'Validation failed', 'errors': errors}), 400

        # Check if email already exists
        if db.users.count_documents({'email': email}, limit=1) > 0:
            return jsonify({'message': 'Email already exists'}), 409 # 409 Conflict

        # Hash password
        hashed_password = generate_password_hash(password)

        # Default avatar (using ui-avatars)
        default_avatar = f'https://ui-avatars.com/api/?name={secure_filename(name).replace("_", "+")}&background=random&color=fff&size=150'

        # Create user document
        user_doc = {
            'email': email,
            'password': hashed_password,
            'name': name,
            'role': role,
            'progress': 0,
            'points': 0,
            'level': 1,
            'badges': [],
            'achievements': [],
            'personalCourses': [], # Store as empty list of ObjectIds initially
            'avatar': default_avatar,
            'streak': 0, # Login streak
            'lastLogin': None,
            'createdAt': datetime.now(timezone.utc),
            'flashcardProgress': {}, # Store flashcard progress { category: { card_id: state } }
            'flashcardScore': 0 # Separate score for flashcards if needed
        }
        # Nullify student-specific fields for teachers
        if role == 'teacher':
            user_doc.update({k: None for k in ['progress', 'points', 'level', 'badges', 'streak', 'flashcardProgress', 'flashcardScore']})

        # Insert user
        result = db.users.insert_one(user_doc)
        user_doc['_id'] = result.inserted_id # Keep as ObjectId for now

        # Generate JWT token
        token_expiry = datetime.now(timezone.utc) + timedelta(days=7) # 7-day expiry
        token_payload = {'id': str(user_doc['_id']), 'role': role, 'exp': token_expiry}
        token = jwt.encode(token_payload, JWT_SECRET, algorithm="HS256")

        logger.info(f"User registered: {email} (Role: {role}, ID: {user_doc['_id']})")

        # Prepare user data for client (stringify IDs)
        user_data_for_client = stringify_ids({k: v for k, v in user_doc.items() if k != 'password'})

        return jsonify({'token': token, 'user': user_data_for_client}), 201

    except Exception as e:
        logger.error(f"Registration error: {e}", exc_info=True)
        return jsonify({'message': 'Server error during registration'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        if not email or not password:
            return jsonify({'message': 'Email and password required'}), 400

        user = db.users.find_one({'email': email})

        # Check user and password
        if not user or 'password' not in user or not check_password_hash(user.get('password', ''), password):
            return jsonify({'message': 'Invalid email or password'}), 401

        # --- Login Streak Logic (only for students) ---
        update_fields = {'lastLogin': datetime.now(timezone.utc)}
        inc_updates = {}
        current_streak = user.get('streak', 0)

        if user.get('role') == 'student':
            today = datetime.now(timezone.utc).date()
            last_login_utc = user.get('lastLogin')
            points_to_add = 0

            # Ensure last_login is a datetime object with timezone
            if last_login_utc:
                if not isinstance(last_login_utc, datetime):
                    try: last_login_utc = datetime.fromisoformat(str(last_login_utc)).replace(tzinfo=timezone.utc) # Try parsing if stored as string
                    except: last_login_utc = None # Invalid format
                # Ensure timezone if missing (assuming UTC if none)
                if last_login_utc and last_login_utc.tzinfo is None:
                    last_login_utc = last_login_utc.replace(tzinfo=timezone.utc)

                if last_login_utc:
                    last_login_date = last_login_utc.date()
                    # Check if login is on a new day
                    if today > last_login_date:
                        if (today - last_login_date).days == 1: # Consecutive day
                            current_streak += 1
                        else: # Missed a day
                            current_streak = 1
                        # Award points for login streak
                        points_to_add = 5 # Base points for daily login
                        if current_streak >= 7: points_to_add += 15 # Bonus for 7+ days
                        elif current_streak >= 3: points_to_add += 5 # Bonus for 3+ days
                else: # First login ever recorded properly
                    current_streak = 1
                    points_to_add = 5
            else: # First login ever
                current_streak = 1
                points_to_add = 5

            update_fields['streak'] = current_streak
            if points_to_add > 0:
                inc_updates['points'] = points_to_add

        # Update user in DB
        if inc_updates:
            db.users.update_one({'_id': user['_id']}, {'$inc': inc_updates, '$set': update_fields})
        elif update_fields: # Only update lastLogin if no points were added
             db.users.update_one({'_id': user['_id']}, {'$set': update_fields})


        # Fetch updated user data
        updated_user = db.users.find_one({'_id': user['_id']})
        if not updated_user:
            return jsonify({'message': 'Login failed - internal error fetching updated user'}), 500

        # Generate JWT token
        token_expiry = datetime.now(timezone.utc) + timedelta(days=7)
        token_payload = {'id': str(updated_user['_id']), 'role': updated_user['role'], 'exp': token_expiry}
        token = jwt.encode(token_payload, JWT_SECRET, algorithm="HS256")

        logger.info(f"User logged in: {email}, Role: {updated_user['role']}, Streak: {updated_user.get('streak', 'N/A')}")

        # Prepare user data for client (stringify IDs)
        user_data_for_client = stringify_ids({k: v for k, v in updated_user.items() if k != 'password'})

        return jsonify({'token': token, 'user': user_data_for_client})

    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        return jsonify({'message': 'Server error during login'}), 500

@app.route('/api/auth/refresh', methods=['POST'])
@token_required
def refresh_token():
    try:
        user_id = request.current_user['_id'] # Already stringified by decorator
        user_role = request.current_user['role']
        user_email = request.current_user['email'] # For logging

        # Generate new token with fresh expiry
        token_expiry = datetime.now(timezone.utc) + timedelta(days=7)
        new_token_payload = {'id': user_id, 'role': user_role, 'exp': token_expiry}
        new_token = jwt.encode(new_token_payload, JWT_SECRET, algorithm="HS256")

        logger.info(f"Token refreshed for user: {user_email} (ID: {user_id})")
        return jsonify({'token': new_token})
    except Exception as e:
        logger.error(f"Token refresh error: {e}", exc_info=True)
        return jsonify({'message': 'Server error during token refresh'}), 500

@app.route('/api/users/me', methods=['GET'])
@token_required
def get_user_profile():
    try:
        # current_user is already prepared and stringified by the decorator
        logger.info(f"Profile fetched for user: {request.current_user.get('email', 'N/A')}")
        return jsonify(request.current_user)
    except Exception as e:
        logger.error(f"Get user profile error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching profile'}), 500

@app.route('/api/users/<user_id_str>', methods=['PUT'])
@token_required
def update_user(user_id_str):
    try:
        requesting_user_id = request.current_user['_id'] # Already string
        requesting_user_role = request.current_user.get('role')

        # Authorization: User can update self, or teacher can update anyone
        if requesting_user_id != user_id_str and requesting_user_role != 'teacher':
            return jsonify({'message': 'Unauthorized'}), 403

        # Validate target user ID format
        if not ObjectId.is_valid(user_id_str):
            return jsonify({'message': 'Invalid user ID format'}), 400

        user_id_obj = ObjectId(user_id_str)

        # Find the user to update
        target_user = db.users.find_one({'_id': user_id_obj})
        if not target_user:
            return jsonify({'message': 'User not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        # Define fields allowed for update via this endpoint
        allowed_fields = [
            'progress', 'points', 'level', 'badges', 'achievements',
            'personalCourses', 'name', 'flashcardProgress', 'flashcardScore'
        ]
        updates = {}

        # Process updates carefully, validating types
        if 'name' in data:
            new_name = str(data['name']).strip()
            if new_name and new_name != target_user.get('name'):
                updates['name'] = new_name
        if 'progress' in data:
            try: updates['progress'] = min(100, max(0, int(data['progress'])))
            except (ValueError, TypeError): pass # Ignore invalid progress values
        if 'points' in data:
            try: updates['points'] = max(0, int(data['points']))
            except (ValueError, TypeError): pass # Ignore invalid points values
        if 'level' in data:
            try: updates['level'] = max(1, int(data['level']))
            except (ValueError, TypeError): pass # Ignore invalid level values
        if 'badges' in data and isinstance(data['badges'], list):
            # Ensure badges are strings and non-empty
            updates['badges'] = [str(b).strip() for b in data['badges'] if str(b).strip()]
        if 'achievements' in data and isinstance(data['achievements'], list):
            updates['achievements'] = [str(a).strip() for a in data['achievements'] if str(a).strip()]
        if 'personalCourses' in data and isinstance(data['personalCourses'], list):
            # Convert valid string IDs back to ObjectIds for storage
            valid_course_ids = []
            for cid_str in data['personalCourses']:
                if isinstance(cid_str, str) and ObjectId.is_valid(cid_str):
                    valid_course_ids.append(ObjectId(cid_str))
            # Only update if the list is different from the current one (deep compare needed for ObjectsIds)
            # Simple check: compare lengths and string representations
            current_ids_str = [str(cid) for cid in target_user.get('personalCourses', [])]
            new_ids_str = [str(cid) for cid in valid_course_ids]
            if set(current_ids_str) != set(new_ids_str):
                updates['personalCourses'] = valid_course_ids
        if 'flashcardProgress' in data and isinstance(data['flashcardProgress'], dict):
            updates['flashcardProgress'] = data['flashcardProgress'] # Assume frontend sends valid structure
        if 'flashcardScore' in data:
            try: updates['flashcardScore'] = max(0, int(data['flashcardScore']))
            except (ValueError, TypeError): pass

        # Filter updates to only include allowed fields
        updates = {k: v for k, v in updates.items() if k in allowed_fields}

        # If no valid updates, return current data
        if not updates:
            # Stringify IDs for response
            return jsonify(stringify_ids({k: v for k, v in target_user.items() if k != 'password'}))

        # --- Level calculation based on points ---
        level_changed_by_points = False
        if 'points' in updates and target_user.get('role') == 'student':
            new_points = updates['points']
            # Calculate potential new level based on points (e.g., 100 points/level)
            new_level = max(1, (new_points // 100) + 1)

            # Check if level needs update based on points, considering if 'level' was also in request
            current_level_in_updates = updates.get('level')
            compare_level = current_level_in_updates if current_level_in_updates is not None else target_user.get('level', 1)

            if new_level != compare_level:
                 updates['level'] = new_level # Override requested level if points dictate otherwise
                 level_changed_by_points = True
            # If level WAS in updates but doesn't match calculated, force calculated level
            elif current_level_in_updates is not None and current_level_in_updates != new_level:
                 updates['level'] = new_level
                 level_changed_by_points = True


        # Perform the update
        result = db.users.update_one({'_id': user_id_obj}, {'$set': updates})

        if result.matched_count == 0:
            # Should not happen if find_one succeeded, but check anyway
            return jsonify({'message': 'User not found during update'}), 404

        # Fetch the fully updated user data
        updated_user = db.users.find_one({'_id': user_id_obj}, {'password': 0})

        # Check if ranking needs update (points, level, name changed)
        ranking_needs_update = ('points' in updates or 'name' in updates or 'level' in updates or level_changed_by_points)
        if ranking_needs_update:
            # Pass stringified ID and the updated user dict
            _update_user_ranking(str(user_id_obj), stringify_ids(updated_user))

        logger.info(f"User {user_id_str} updated successfully by {requesting_user_id}. Fields: {list(updates.keys())}")

        # Return updated user data (stringified)
        return jsonify(stringify_ids(updated_user))

    except Exception as e:
        logger.error(f"Update user {user_id_str} error: {e}", exc_info=True)
        return jsonify({'message': 'Server error during user update'}), 500

@app.route('/api/users/personal-courses', methods=['POST'])
@token_required
def add_personal_course():
    try:
        data = request.get_json()
        course_id_str = data.get('courseId')

        if not course_id_str or not ObjectId.is_valid(course_id_str):
            return jsonify({'message': 'Valid Course ID required'}), 400

        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query
        course_id_obj = ObjectId(course_id_str)

        # Verify course exists
        if db.courses.count_documents({'_id': course_id_obj}, limit=1) == 0:
            return jsonify({'message': 'Course not found'}), 404

        # Add courseId to the user's personalCourses array (only if not already present)
        result = db.users.update_one(
            {'_id': user_id_obj},
            {'$addToSet': {'personalCourses': course_id_obj}}
        )

        # Fetch updated user to return
        updated_user = db.users.find_one({'_id': user_id_obj}, {'password': 0})
        user_data_for_client = stringify_ids(updated_user)

        if result.modified_count > 0:
             logger.info(f"Course {course_id_str} added to favorites for user {request.current_user['_id']}")
             return jsonify({'message': 'Course added successfully', 'user': user_data_for_client})
        elif result.matched_count > 0: # Matched but not modified means it was already there
             return jsonify({'message': 'Course already in list', 'user': user_data_for_client})
        else:
            return jsonify({'message': 'User not found'}), 404 # Should not happen with token_required

    except Exception as e:
        logger.error(f"Add personal course error: {e}", exc_info=True)
        return jsonify({'message': 'Server error adding personal course'}), 500

@app.route('/api/users/personal-courses/<course_id_str>', methods=['DELETE'])
@token_required
def remove_personal_course(course_id_str):
    try:
        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query

        if not course_id_str or not ObjectId.is_valid(course_id_str):
            return jsonify({'message': 'Valid Course ID required'}), 400
        course_id_obj = ObjectId(course_id_str)

        # Remove courseId from the user's personalCourses array
        result = db.users.update_one(
            {'_id': user_id_obj},
            {'$pull': {'personalCourses': course_id_obj}}
        )

        # Fetch updated user to return
        updated_user = db.users.find_one({'_id': user_id_obj}, {'password': 0})
        user_data_for_client = stringify_ids(updated_user)

        if result.modified_count > 0:
            logger.info(f"Course {course_id_str} removed from favorites for user {request.current_user['_id']}")
            return jsonify({'message': 'Course removed successfully', 'user': user_data_for_client})
        elif result.matched_count > 0: # Matched but not modified means it wasn't in the list
            return jsonify({'message': 'Course not found in list', 'user': user_data_for_client})
        else:
            return jsonify({'message': 'User not found'}), 404 # Should not happen

    except Exception as e:
        logger.error(f"Remove personal course error: {e}", exc_info=True)
        return jsonify({'message': 'Server error removing personal course'}), 500

@app.route('/api/users/change-password', methods=['POST'])
@token_required
def change_password():
    try:
        data = request.get_json()
        current_password = data.get('currentPassword')
        new_password = data.get('newPassword')

        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query

        if not current_password or not new_password:
            return jsonify({'message': 'Passwords required'}), 400
        if len(new_password) < 6:
            return jsonify({'message': 'New password too short (minimum 6 characters)'}), 400

        user = db.users.find_one({'_id': user_id_obj})
        if not user:
            return jsonify({'message': 'User not found'}), 404 # Should not happen

        # Check if user has a password set (might not if social login implemented later)
        if 'password' not in user or not user['password']:
            return jsonify({'message': 'Cannot change password for this account'}), 400

        # Verify current password
        if not check_password_hash(user.get('password'), current_password):
            return jsonify({'message': 'Current password incorrect'}), 401

        # Prevent setting the same password
        if check_password_hash(user.get('password'), new_password):
            return jsonify({'message': 'New password cannot be the same as the old password'}), 400

        # Hash new password and update
        new_hashed_password = generate_password_hash(new_password)
        result = db.users.update_one({'_id': user_id_obj}, {'$set': {'password': new_hashed_password}})

        if result.matched_count == 0:
            return jsonify({'message': 'User not found during password update'}), 404 # Should not happen

        logger.info(f"Password changed successfully for user {user_id_obj}")
        return jsonify({'message': 'Password changed successfully'})

    except Exception as e:
        logger.error(f"Change password error: {e}", exc_info=True)
        return jsonify({'message': 'Server error changing password'}), 500

@app.route('/api/users/change-avatar', methods=['POST'])
@token_required
def change_avatar():
    try:
        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query

        if 'avatar' not in request.files:
            return jsonify({'message': 'No file part named "avatar"'}), 400
        file = request.files['avatar']
        if file.filename == '':
            return jsonify({'message': 'No selected file'}), 400

        # Validate file type
        filename = secure_filename(file.filename)
        if not allowed_file(filename, ALLOWED_AVATAR_EXTENSIONS):
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else '?'
            return jsonify({'message': f'File type "{ext}" not allowed. Allowed: {", ".join(ALLOWED_AVATAR_EXTENSIONS)}'}), 400

        # Validate file size
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0) # Reset pointer
        if file_length > MAX_AVATAR_SIZE:
            limit_mb = MAX_AVATAR_SIZE / (1024 * 1024)
            return jsonify({'message': f'File size exceeds limit ({limit_mb:.1f}MB)'}), 413 # Payload Too Large

        # Create unique filename and path
        file_ext = filename.rsplit('.', 1)[1].lower()
        unique_filename = f"avatar_{str(user_id_obj)}_{int(datetime.now(timezone.utc).timestamp())}.{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER_AVATARS, unique_filename)
        avatar_url = f"/uploads/avatars/{unique_filename}" # URL path for serving

        # TODO: Add image processing/resizing here if needed before saving

        # Save file
        file.save(file_path)

        # Update user document
        result = db.users.update_one({'_id': user_id_obj}, {'$set': {'avatar': avatar_url}})
        if result.matched_count == 0:
            # Clean up saved file if user not found
            if os.path.exists(file_path): os.remove(file_path)
            return jsonify({'message': 'User not found'}), 404

        # Fetch updated user data for ranking update and response
        updated_user = db.users.find_one({'_id': user_id_obj}, {'password': 0})
        updated_user_data = stringify_ids(updated_user)

        # Update ranking (avatar changed)
        _update_user_ranking(str(user_id_obj), updated_user_data)
        # Also update the avatar in the request context immediately if needed elsewhere in this request cycle
        request.current_user['avatar'] = avatar_url

        logger.info(f"Avatar changed for user {user_id_obj}, URL: {avatar_url}")
        return jsonify({'message': 'Avatar changed successfully', 'avatarUrl': avatar_url, 'user': updated_user_data})

    except Exception as e:
        # Clean up potential partial file uploads on error? Difficult.
        logger.error(f"Change avatar error: {e}", exc_info=True)
        return jsonify({'message': 'Server error changing avatar'}), 500

@app.route('/api/courses', methods=['GET'])
# @token_required # Courses might be public, remove token requirement if needed
def get_courses():
    try:
        category = request.args.get('category')
        query = {}
        if category:
            query['category'] = category

        courses_cursor = db.courses.find(query)
        # Convert ObjectIds to strings for JSON response
        courses = [stringify_ids(c) for c in courses_cursor]

        user_id = request.current_user.get('_id', 'public') if hasattr(request, 'current_user') else 'public'
        logger.info(f"Courses fetched (Category: {category or 'All'}) for user/requester {user_id}")
        return jsonify(courses)

    except Exception as e:
        logger.error(f"Courses fetch error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching courses'}), 500

@app.route('/api/courses/<course_id_str>', methods=['GET'])
# @token_required # Courses might be public, remove token requirement if needed
def get_course_by_id(course_id_str):
    try:
        # Validate course ID format
        if not ObjectId.is_valid(course_id_str):
            return jsonify({'message': 'Invalid course ID format'}), 400

        course_id_obj = ObjectId(course_id_str)

        # Find the course
        course = db.courses.find_one({'_id': course_id_obj})
        if not course:
            return jsonify({'message': 'Course not found'}), 404

        # Convert ObjectIds to strings for JSON response
        course_data = stringify_ids(course)

        user_id = request.current_user.get('_id', 'public') if hasattr(request, 'current_user') else 'public'
        logger.info(f"Course {course_id_str} fetched for user/requester {user_id}")
        return jsonify(course_data)

    except Exception as e:
        logger.error(f"Course fetch error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching course'}), 500


# <<< ADDED: Global variables for SSE ranking cache >>>
last_rankings_state = None
last_check_time = 0
RANKING_CHECK_INTERVAL = 5 # Check database for ranking changes every 5 seconds


# <<< ADDED: Helper function to get current ranking state (cached) >>>
def get_current_ranking_state(limit=50):
    """Fetches current ranking state, using a cache to reduce DB load."""
    global last_rankings_state, last_check_time
    current_time = time.time()

    # Check cache validity
    if last_rankings_state is None or (current_time - last_check_time > RANKING_CHECK_INTERVAL):
        logger.debug(f"Ranking cache expired or empty. Querying DB at {current_time:.2f}")
        try:
            rankings_cursor = db.rankings.find(
                {},
                {'_id': 0, 'userId': 1, 'name': 1, 'points': 1, 'avatar': 1, 'level': 1} # Exclude MongoDB _id
            ).sort('points', -1).limit(limit)
            current_state_list = list(rankings_cursor) # Convert cursor to list
            # Store as JSON string for easy comparison
            current_state_json = json.dumps(current_state_list)

            # Update cache only if data actually changed to avoid unnecessary downstream processing
            if current_state_json != last_rankings_state:
                 last_rankings_state = current_state_json
                 logger.info(f"Ranking state updated in cache. {len(current_state_list)} users.")
            else:
                 logger.debug("Ranking state unchanged since last DB check.")


            last_check_time = current_time # Update last check time regardless of change
            return last_rankings_state # Return the potentially updated state

        except Exception as e:
            logger.error(f"Error fetching current ranking state from DB: {e}")
            # Return the old cached state on error to avoid breaking SSE stream if possible
            return last_rankings_state
    else:
        # Return cached state if interval hasn't passed
        logger.debug(f"Returning cached ranking state (checked {current_time - last_check_time:.2f}s ago)")
        return last_rankings_state


@app.route('/api/rankings', methods=['GET'])
@token_required # Keep token required for standard GET request
def get_rankings():
    # This route provides a snapshot, mainly for initial load or fallback
    try:
        limit = int(request.args.get('limit', 50))
        # Use the cached state function to potentially avoid DB query
        rankings_json = get_current_ranking_state(limit=limit)
        rankings_list = json.loads(rankings_json) if rankings_json else []

        logger.info(f"Rankings fetched on demand (Snapshot, Top {limit}) for user {request.current_user['_id']}")
        return jsonify(rankings_list)
    except Exception as e:
        logger.error(f"Rankings fetch (snapshot) error: {str(e)}", exc_info=True)
        return jsonify({'message': 'Server error fetching rankings snapshot', 'error': str(e)}), 500


# <<< ADDED: SSE Endpoint for Real-time Ranking Updates >>>
@app.route('/api/rankings/stream')
def stream_rankings():
    def generate():
        yield 'data: {"event": "connected", "rankings": []}\n\n'
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/submissions', methods=['POST'])
@token_required
def upload_submission():
    # Combined route for different submission types (practice, challenge)
    try:
        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query
        user_email = request.current_user['email']
        user_name = request.current_user.get('name', 'Unknown')
        user_role = request.current_user['role']

        # Check for file part
        if 'file' not in request.files:
            return jsonify({'message': 'No file part named "file"'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'message': 'No selected file'}), 400

        # Get form data
        note = request.form.get('note', '').strip()
        # Determine submission type (default to 'practice' if not specified)
        submission_type = request.form.get('type', 'practice').lower()
        related_id_str = request.form.get('relatedId') # e.g., courseId or challengeId

        # --- File Validation ---
        filename = secure_filename(file.filename)
        if not allowed_file(filename, ALLOWED_SUBMISSION_EXTENSIONS):
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else '?'
            return jsonify({'message': f'File type "{ext}" not allowed. Allowed: {", ".join(ALLOWED_SUBMISSION_EXTENSIONS)}'}), 400

        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)
        if file_length > MAX_SUBMISSION_SIZE:
            limit_mb = MAX_SUBMISSION_SIZE / (1024 * 1024)
            return jsonify({'message': f'File size exceeds limit ({limit_mb:.1f}MB)'}), 413

        # --- Process Related ID ---
        related_object_id = None
        related_title = "N/A"
        collection_to_check = None

        if related_id_str and ObjectId.is_valid(related_id_str):
             related_object_id = ObjectId(related_id_str)
             # Determine which collection to check for the title based on type
             if submission_type == 'challenge':
                 collection_to_check = db.challenges
             elif submission_type in ['practice', 'practice_video']: # Assuming practice relates to courses
                 collection_to_check = db.courses
             # Add other types if necessary (e.g., lessonId)

             if collection_to_check:
                  related_doc = collection_to_check.find_one({'_id': related_object_id}, {'title': 1})
                  if related_doc:
                      related_title = related_doc.get('title', 'Unknown Title')
                  else:
                       related_title = f"Unknown {submission_type} (ID: {related_id_str})" # Title not found
        elif related_id_str:
             # Handle cases where relatedId might be a string identifier (like 'daily')
             related_object_id = related_id_str # Store as string
             related_title = related_id_str


        # --- Save File ---
        file_ext = filename.rsplit('.', 1)[1].lower()
        timestamp = int(datetime.now(timezone.utc).timestamp())
        unique_filename = f"{submission_type}_{str(user_id_obj)}_{timestamp}.{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER_SUBMISSIONS, unique_filename)
        file_url = f"/uploads/submissions/{unique_filename}"

        file.save(file_path)

        # --- Create Submission Document ---
        submission_doc = {
            'userId': user_id_obj,
            'userEmail': user_email,
            'userName': user_name,
            'type': submission_type,
            'relatedId': related_object_id, # Can be ObjectId or string
            'relatedTitle': related_title,
            'url': file_url,
            'note': note,
            'teacherComment': '',
            'status': 'pending', # Default status
            'pointsAwarded': 0,
            'createdAt': datetime.now(timezone.utc),
            'reviewedAt': None,
            'reviewerId': None,
            'originalFilename': filename # Store original filename for reference
        }

        # --- Insert Submission ---
        result = db.submissions.insert_one(submission_doc)
        inserted_id = result.inserted_id
        submission_doc['_id'] = inserted_id # Keep as ObjectId internally

        # --- Auto-approve practice & Award points ---
        points_to_add = 0
        progress_to_add = 0
        response_message = 'Submission received.'

        if user_role == 'student' and submission_type in ['practice', 'practice_video']:
            points_to_add = 10 # Example points for practice
            progress_to_add = 2 # Example progress
            submission_doc['status'] = 'approved'
            submission_doc['pointsAwarded'] = points_to_add
            # Update status and points immediately in DB for auto-approved items
            db.submissions.update_one(
                {'_id': inserted_id},
                {'$set': {'status': 'approved', 'pointsAwarded': points_to_add}}
            )
            response_message = f'Practice submission received, +{points_to_add} points!'
        elif submission_type == 'challenge':
             # Get potential points from the challenge document
             challenge_points = 15 # Default if challenge not found or no points defined
             if isinstance(related_object_id, ObjectId): # Only if it's a valid ID
                 challenge = db.challenges.find_one({'_id': related_object_id})
                 if challenge:
                     challenge_points = challenge.get('points', 15)
             elif related_object_id == 'daily': # Example handling for 'daily' identifier
                 # Fetch the actual daily challenge to get points (more complex)
                 # For simplicity, assume a default or handle based on frontend knowledge
                 pass

             response_message = f'Challenge submission received. Waiting for review (potential +{challenge_points} points).'


        # Update user points/progress if awarded automatically
        if points_to_add > 0 or progress_to_add > 0:
            update_result = db.users.update_one(
                {'_id': user_id_obj},
                {'$inc': {'points': points_to_add, 'progress': progress_to_add}}
            )
            if update_result.modified_count > 0:
                # Fetch updated user data for ranking update
                updated_user = db.users.find_one({'_id': user_id_obj})
                _update_user_ranking(str(user_id_obj), stringify_ids(updated_user))
                logger.info(f"Auto-awarded {points_to_add} points, {progress_to_add}% progress for submission {inserted_id} by {user_email}.")

        # Prepare response (stringify IDs)
        response_submission = stringify_ids(submission_doc)

        logger.info(f"Submission type '{submission_type}' received from {user_email}. ID: {inserted_id}. Status: {response_submission['status']}.")
        return jsonify({'submission': response_submission, 'message': response_message}), 201

    except Exception as e:
        logger.error(f"Submission upload error: {e}", exc_info=True)
        return jsonify({'message': 'Server error during submission upload'}), 500

# This route is already defined above with OPTIONS method
# @app.route('/api/submissions', methods=['GET'])
# @token_required
# def get_submissions():
#     try:
#         user_id_str = request.current_user['_id'] # Already string
#         user_role = request.current_user['role']
#         query = {}
#
#         # --- Filter based on user role and request parameters ---
#         if user_role != 'teacher':
#             # Students only see their own submissions
#             query['userId'] = ObjectId(user_id_str) # Query by ObjectId
#         else:
#             # Teachers can filter by student ID or email
#             student_id_param = request.args.get('userId')
#             student_email_param = request.args.get('userEmail')
#             if student_id_param and ObjectId.is_valid(student_id_param):
#                 query['userId'] = ObjectId(student_id_param)
#             elif student_email_param:
#                 query['userEmail'] = student_email_param.strip().lower()
#             # If no student filter, teacher sees all (or paginated subset)
#
#         # Optional filters
#         sub_type = request.args.get('type')
#         status = request.args.get('status')
#         if sub_type:
#             query['type'] = sub_type.lower()
#         if status:
#             query['status'] = status.lower()
#
#         # --- Pagination ---
#         try: page = int(request.args.get('page', 1))
#         except ValueError: page = 1
#         try: limit = int(request.args.get('limit', 10))
#         except ValueError: limit = 10
#         limit = max(1, min(limit, 100)) # Clamp limit
#         page = max(1, page)
#         skip = (page - 1) * limit
#
#         # --- Fetch Data ---
#         submissions_cursor = db.submissions.find(query).sort('createdAt', -1).skip(skip).limit(limit)
#         submissions = [stringify_ids(sub) for sub in submissions_cursor] # Stringify results
#
#         # Get total count for pagination info
#         total_submissions = db.submissions.count_documents(query)
#         total_pages = (total_submissions + limit - 1) // limit if limit > 0 else 0
#
#         logger.info(f"Submissions fetched by {request.current_user['email']} ({user_role}). Query: {query}, Page {page}, Limit {limit}. Found: {len(submissions)}/{total_submissions}")
#         return jsonify({
#             'submissions': submissions,
#             'total': total_submissions,
#             'page': page,
#             'limit': limit,
#             'totalPages': total_pages
#         })
#
#     except Exception as e:
#         logger.error(f"Submissions fetch error: {e}", exc_info=True)
#         return jsonify({'message': 'Server error fetching submissions'}), 500

@app.route('/api/submissions/<submission_id_str>/review', methods=['PUT'])
@teacher_required
def review_submission(submission_id_str):
    try:
        reviewer_id_obj = ObjectId(request.current_user['_id']) # Teacher's ID as ObjectId
        reviewer_email = request.current_user['email']

        if not ObjectId.is_valid(submission_id_str):
            return jsonify({'message': 'Invalid submission ID format'}), 400
        submission_id_obj = ObjectId(submission_id_str)

        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        # Get review data
        status = data.get('status') # 'approved' or 'rejected'
        teacher_comment = data.get('teacherComment', '').strip()
        try:
            # Award points only if approved, default to 0 otherwise
            points_awarded = int(data.get('pointsAwarded', 0)) if status == 'approved' else 0
            points_awarded = max(0, points_awarded) # Ensure non-negative
        except (ValueError, TypeError):
            points_awarded = 0

        # --- Validation ---
        if status not in ['approved', 'rejected']:
            return jsonify({'message': 'Status must be "approved" or "rejected"'}), 400
        if status == 'rejected' and not teacher_comment: # Require comment for rejection
            return jsonify({'message': 'Comment is required for rejection'}), 400

        # --- Find Submission ---
        submission = db.submissions.find_one({'_id': submission_id_obj})
        if not submission:
            return jsonify({'message': 'Submission not found'}), 404
        if submission.get('status') != 'pending':
            # Prevent re-reviewing (or handle differently if needed)
            return jsonify({'message': f"Submission already reviewed (Status: {submission.get('status')})"}), 409 # Conflict

        # --- Update Submission ---
        update_fields = {
            'status': status,
            'teacherComment': teacher_comment,
            'pointsAwarded': points_awarded,
            'reviewedAt': datetime.now(timezone.utc),
            'reviewerId': reviewer_id_obj # Store reviewer's ObjectId
        }
        result = db.submissions.update_one({'_id': submission_id_obj}, {'$set': update_fields})

        if result.modified_count == 0:
             # Check if it was already reviewed by someone else just before this request
             current_sub = db.submissions.find_one({'_id': submission_id_obj});
             if current_sub and current_sub.get('status') != 'pending':
                  return jsonify({'message': f"Submission reviewed concurrently (Status: {current_sub.get('status')})"}), 409
             logger.warning(f"Review failed for submission {submission_id_str}, modified_count was 0.")
             return jsonify({'message': 'Failed to update submission status'}), 500

        # --- Update Student Points/Progress if Approved ---
        student_id_obj = submission.get('userId')
        if status == 'approved' and points_awarded > 0 and student_id_obj and isinstance(student_id_obj, ObjectId):
            student = db.users.find_one({'_id': student_id_obj})
            if student and student.get('role') == 'student':
                # Define progress increase (e.g., based on points or fixed)
                progress_to_add = 5 # Example: 5% progress for approved submission
                update_student_result = db.users.update_one(
                    {'_id': student_id_obj},
                    {'$inc': {'points': points_awarded, 'progress': progress_to_add}}
                )
                if update_student_result.modified_count > 0:
                    # Fetch updated student data for ranking update
                    updated_student = db.users.find_one({'_id': student_id_obj})
                    _update_user_ranking(str(student_id_obj), stringify_ids(updated_student))
                    logger.info(f"Awarded {points_awarded} points, {progress_to_add}% progress to student {student_id_obj} for submission {submission_id_str}")
                else:
                     logger.warning(f"Failed to update points/progress for student {student_id_obj} after reviewing {submission_id_str}")

                # --- Handle Challenge-specific logic ---
                if submission.get('type') == 'challenge':
                    # If this is a challenge submission, update the user's challenge history
                    challenge_id = submission.get('relatedId')
                    if challenge_id:
                        # Add to completedChallenges array if approved
                        if status == 'approved':
                            db.users.update_one(
                                {'_id': student_id_obj},
                                {'$addToSet': {'completedChallenges': challenge_id}}
                            )

                        # Create a notification for the user
                        notification = {
                            'userId': student_id_obj,
                            'type': 'challenge_review',
                            'status': status,
                            'message': f"Your challenge submission has been {status}" +
                                      (f" with {points_awarded} points!" if status == 'approved' else
                                       f". Teacher comment: {teacher_comment}"),
                            'relatedId': submission_id_obj,
                            'createdAt': datetime.now(timezone.utc),
                            'read': False
                        }
                        db.notifications.insert_one(notification)


        # --- Prepare and Return Response ---
        updated_submission = db.submissions.find_one({'_id': submission_id_obj})
        response_data = stringify_ids(updated_submission) # Stringify all ObjectIds

        logger.info(f"Submission {submission_id_str} reviewed by {reviewer_email}. Status: {status}, Points: {points_awarded}")
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Review submission error: {e}", exc_info=True)
        return jsonify({'message': 'Server error during submission review'}), 500

@app.route('/api/flashcards', methods=['GET'])
@token_required # Usually requires login to access learning materials
def get_flashcards():
    try:
        category = request.args.get('category', 'sao') # Default category if none provided
        user_id = request.current_user['_id'] # For logging

        # Validate category if needed
        allowed_categories = ['sao', 'dan-tranh', 'dan-nguyet', 'vovinam'] # Example categories
        if category not in allowed_categories:
            return jsonify({'message': 'Invalid flashcard category'}), 400

        flashcards_cursor = db.flashcards.find({'category': category})

        # <<< MODIFIED >>> Correctly format for frontend JS, ensuring _id is present and stringified
        flashcards = []
        for card in flashcards_cursor:
             card_data = stringify_ids(card) # Convert all ObjectIds, including _id
             flashcards.append(card_data)


        logger.info(f"Flashcards fetched for category '{category}' for user {user_id}")

        # Optionally, retrieve and merge user-specific progress for these cards
        user_progress_map = request.current_user.get('flashcardProgress', {}).get(category, {})
        # Example merge (can be done on frontend too):
        # for card in flashcards:
        #     card_id_str = card.get('_id')
        #     if card_id_str in user_progress_map:
        #         card.update(user_progress_map[card_id_str]) # Add progress fields like 'completed', 'lastReviewed'

        return jsonify(flashcards) # Return the list directly

    except Exception as e:
        logger.error(f"Flashcards fetch error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching flashcards'}), 500

@app.route('/api/flashcards/progress', methods=['POST'])
@token_required
def save_flashcard_progress():
    # This endpoint saves the *state* of flashcards (e.g., learned, reviewed count)
    # Points/score updates should happen via a separate "test complete" endpoint
    try:
        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        category = data.get('category')
        # Expecting 'progressData' based on script.js, which seems to be the list of cards
        progress_data_list = data.get('progressData')

        if not category or not isinstance(progress_data_list, list):
            return jsonify({'message': 'Category and progressData array required'}), 400

        # Prepare MongoDB update operations using dot notation
        update_ops = {}
        valid_updates_found = False
        for card_state in progress_data_list:
            if isinstance(card_state, dict):
                card_id = card_state.get('_id') # Assuming _id is passed in the state
                # Prepare the state to save (exclude _id itself from the saved value)
                state_to_save = {k: v for k, v in card_state.items() if k != '_id'}
                # Validate card_id and ensure there's something to save
                if card_id and ObjectId.is_valid(card_id) and state_to_save:
                     update_ops[f'flashcardProgress.{category}.{str(card_id)}'] = state_to_save
                     valid_updates_found = True

        if not valid_updates_found:
            logger.info(f"No valid flashcard progress updates provided for category '{category}' by user {user_id_obj}")
            # Return current progress state or just success
            current_user = db.users.find_one({'_id': user_id_obj}, {'flashcardProgress': 1})
            return jsonify({'message': 'No valid updates provided', 'flashcardProgress': current_user.get('flashcardProgress', {})})


        # Apply updates to the user document
        result = db.users.update_one({'_id': user_id_obj}, {'$set': update_ops})

        if result.matched_count > 0:
            logger.info(f"Flashcard progress saved for category '{category}' for user {user_id_obj}")
            # Return the updated progress sub-document
            updated_user = db.users.find_one({'_id': user_id_obj}, {'flashcardProgress': 1})
            return jsonify({'message': 'Progress saved successfully', 'flashcardProgress': updated_user.get('flashcardProgress', {})})
        else:
            return jsonify({'message': 'User not found'}), 404

    except Exception as e:
        logger.error(f"Save flashcard progress error: {e}", exc_info=True)
        return jsonify({'message': 'Server error saving flashcard progress'}), 500

@app.route('/api/flashcards/test/complete', methods=['POST'])
@token_required
def complete_flashcard_test():
    # This endpoint receives the *score* from a completed test and updates user points/progress
    try:
        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query
        user_role = request.current_user.get('role')

        # Only students earn points/progress from tests
        if user_role != 'student':
            logger.info(f"Flashcard test completion ignored for non-student user {user_id_obj}")
            return jsonify({'message': 'Only students earn points from tests'}), 200

        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        try:
            points_earned = int(data.get('score', 0))
            points_earned = max(0, points_earned) # Ensure non-negative
        except (ValueError, TypeError):
            return jsonify({'message': 'Invalid score provided'}), 400

        if points_earned == 0:
            logger.info(f"Flashcard test completed with 0 points for student {user_id_obj}")
            return jsonify({'message': 'Test completed, no points earned.'}), 200

        # Define progress gain for completing a test
        progress_earned = 5 # Example: 5% progress boost

        # Update user points and progress
        update_result = db.users.update_one(
            {'_id': user_id_obj},
            {'$inc': {'points': points_earned, 'progress': progress_earned}}
        )

        if update_result.modified_count > 0:
            # Fetch updated user data for ranking update and response
            updated_user = db.users.find_one({'_id': user_id_obj})
            _update_user_ranking(str(user_id_obj), stringify_ids(updated_user)) # Update ranking
            logger.info(f"Flashcard test recorded for student {user_id_obj}. Points: +{points_earned}, Progress: +{progress_earned}%")
            # Return updated user data (stringified)
            user_data_for_client = stringify_ids({k: v for k, v in updated_user.items() if k != 'password'})
            return jsonify({'message': f'Test completed! +{points_earned} points.', 'user': user_data_for_client})
        else:
            # User found but no change occurred (highly unlikely with $inc > 0)
            logger.warning(f"Flashcard test completion recorded for {user_id_obj}, but points/progress did not update.")
            # Return current user data
            current_user_data = db.users.find_one({'_id': user_id_obj}, {'password': 0})
            user_data_for_client = stringify_ids(current_user_data)
            return jsonify({'message': 'Test recorded, but no change in points/progress.', 'user': user_data_for_client}), 200

    except Exception as e:
        logger.error(f"Flashcard test complete error: {e}", exc_info=True)
        return jsonify({'message': 'Server error processing flashcard test completion'}), 500

@app.route('/api/challenges', methods=['GET'])
@token_required # Usually requires login
def get_challenges():
    try:
        # --- Pagination ---
        try: page = int(request.args.get('page', 1))
        except ValueError: page = 1
        try: limit = int(request.args.get('limit', 10))
        except ValueError: limit = 10
        limit = max(1, min(limit, 50)) # Clamp limit
        page = max(1, page)
        skip = (page - 1) * limit

        # --- Fetch Data ---
        challenges_cursor = db.challenges.find({}).sort('createdAt', -1).skip(skip).limit(limit)
        # <<< MODIFIED >>> Ensure _id is stringified correctly
        challenges = [stringify_ids(c) for c in challenges_cursor]

        total_challenges = db.challenges.count_documents({})
        total_pages = (total_challenges + limit - 1) // limit if limit > 0 else 0

        logger.info(f"Challenges fetched by user {request.current_user['_id']}. Page {page}, Limit {limit}. Found: {len(challenges)}/{total_challenges}")
        return jsonify({
            'challenges': challenges,
            'total': total_challenges,
            'page': page,
            'limit': limit,
            'totalPages': total_pages
        })
    except Exception as e:
        logger.error(f"Challenges fetch error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching challenges'}), 500

@app.route('/api/challenges/daily', methods=['GET'])
@token_required # Usually requires login
def get_daily_challenge():
    try:
        # Get today's date in UTC
        today = datetime.now(timezone.utc).date()
        today_str = today.strftime('%Y-%m-%d')

        # Try to find a challenge marked for today's date
        daily_challenge = db.challenges.find_one({
            'active': True,
            'date': {'$regex': f'^{today_str}'}
        })

        # If no challenge is specifically set for today, get the most recent active challenge
        if not daily_challenge:
            daily_challenge = db.challenges.find_one({'active': True}, sort=[('createdAt', -1)])

        # If still no challenge found, return a default one
        if not daily_challenge:
            default_challenge = {
                '_id': 'default_daily_001',
                'title': 'Thử Thách Hàng Ngày: Học Bài Mới!',
                'description': 'Hoàn thành một bài học bất kỳ trong các khóa học bạn đã tham gia để nhận điểm thưởng.',
                'points': 10,
                'thumbnail': '/assets/images/default-challenge.jpg',
                'createdAt': datetime.now(timezone.utc).isoformat(),
                'date': today_str,
                'active': True
            }
            logger.warning("No challenges found, returning default daily challenge.")
            return jsonify(default_challenge)

        # Check if user has already submitted this challenge
        user_id_obj = ObjectId(request.current_user['_id'])
        challenge_id = daily_challenge['_id']

        # Find if there's a submission for this challenge by this user
        submission = db.submissions.find_one({
            'userId': user_id_obj,
            'relatedId': challenge_id,
            'type': 'challenge'
        })

        # Add submission status to the response
        response_data = stringify_ids(daily_challenge)
        response_data['submitted'] = submission is not None
        if submission:
            response_data['submissionStatus'] = submission.get('status', 'pending')
            response_data['submissionId'] = str(submission['_id'])
            if submission.get('teacherComment'):
                response_data['teacherComment'] = submission['teacherComment']

        logger.info(f"Daily challenge fetched: ID {response_data['_id']}, Title: '{response_data.get('title', 'N/A')}'")
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Daily challenge fetch error: {e}", exc_info=True)
        # Don't return a default challenge on general errors, return error message
        return jsonify({'message': 'Server error fetching daily challenge'}), 500

@app.route('/api/learning-path', methods=['GET'])
@token_required # Usually requires login
def get_learning_path():
    try:
        # Fetch items sorted by 'order' field
        learning_path_cursor = db.learning_path.find().sort('order', 1)
        learning_path = [stringify_ids(item) for item in learning_path_cursor]

        logger.info(f"Learning path fetched for user {request.current_user['_id']}")
        return jsonify(learning_path)
    except Exception as e:
        logger.error(f"Learning path fetch error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching learning path'}), 500

# --- Mini-Game Routes (Using Mock Data - Consider moving to DB) ---
# MOCK DATA - REPLACE WITH DB if becomes complex
game_questions_db_mock = {
    'guess-note': [
        {'id': 'gn001', 'question': 'Nghe âm thanh và đoán nốt nhạc này là gì (tên đầy đủ)?', 'imageUrl': '/assets/images/games/note-do.png', 'audioUrl': '/assets/audio/notes/do.mp3', 'answer': ['đô'], 'points': 10},
        {'id': 'gn002', 'question': 'Nghe âm thanh và đoán nốt nhạc này?', 'imageUrl': '/assets/images/games/note-sol.png', 'audioUrl': '/assets/audio/notes/sol.mp3', 'answer': ['son', 'sol'], 'points': 10},
        {'id': 'gn003', 'question': 'Nghe âm thanh và đoán đây là nốt gì?', 'imageUrl': '/assets/images/games/note-mi.png', 'audioUrl': '/assets/audio/notes/mi.mp3', 'answer': ['mi'], 'points': 10},
        ],
    'listen-note': [
        {'id': 'ln001', 'question': 'Nghe âm thanh và đoán nốt nhạc này là gì?', 'audioUrl': '/assets/audio/notes/do.mp3', 'answer': ['đô'], 'points': 15, 'level': 2},
        {'id': 'ln002', 'question': 'Nghe âm thanh và đoán nốt nhạc này?', 'audioUrl': '/assets/audio/notes/sol.mp3', 'answer': ['son', 'sol'], 'points': 15, 'level': 2},
        {'id': 'ln003', 'question': 'Nghe âm thanh và đoán đây là nốt gì?', 'audioUrl': '/assets/audio/notes/mi.mp3', 'answer': ['mi'], 'points': 15, 'level': 2},
        ],
    'match-note': [
        {'id': 'mn001', 'question': 'Ghép Nốt Nhạc', 'audioUrl': '/assets/audio/notes/do.mp3', 'answer': ['Rê'], 'points': 20, 'level': 3, 'options': [
            {'label': 'Rê', 'imageUrl': '/assets/images/games/note-re.png'},
            {'label': 'Mi', 'imageUrl': '/assets/images/games/note-mi.png'},
            {'label': 'Sol', 'imageUrl': '/assets/images/games/note-sol.png'},
            {'label': 'La', 'imageUrl': '/assets/images/games/note-la.png'}
        ]},
        {'id': 'mn002', 'question': 'Ghép Nốt Nhạc', 'audioUrl': '/assets/audio/notes/sol.mp3', 'answer': ['Sol'], 'points': 20, 'level': 3, 'options': [
            {'label': 'Rê', 'imageUrl': '/assets/images/games/note-re.png'},
            {'label': 'Mi', 'imageUrl': '/assets/images/games/note-mi.png'},
            {'label': 'Sol', 'imageUrl': '/assets/images/games/note-sol.png'},
            {'label': 'La', 'imageUrl': '/assets/images/games/note-la.png'}
        ]},
        {'id': 'mn003', 'question': 'Ghép Nốt Nhạc', 'audioUrl': '/assets/audio/notes/mi.mp3', 'answer': ['Mi'], 'points': 20, 'level': 3, 'options': [
            {'label': 'Rê', 'imageUrl': '/assets/images/games/note-re.png'},
            {'label': 'Mi', 'imageUrl': '/assets/images/games/note-mi.png'},
            {'label': 'Sol', 'imageUrl': '/assets/images/games/note-sol.png'},
            {'label': 'La', 'imageUrl': '/assets/images/games/note-la.png'}
        ]},
        {'id': 'mn004', 'question': 'Ghép Nốt Nhạc', 'audioUrl': '/assets/audio/notes/do.mp3', 'answer': ['Rê'], 'points': 20, 'level': 3, 'options': [
            {'label': 'Rê', 'imageUrl': '/assets/images/games/note-re.png'},
            {'label': 'Mi', 'imageUrl': '/assets/images/games/note-mi.png'},
            {'label': 'Sol', 'imageUrl': '/assets/images/games/note-sol.png'},
            {'label': 'La', 'imageUrl': '/assets/images/games/note-la.png'}
        ]},
        {'id': 'mn005', 'question': 'Ghép Nốt Nhạc', 'audioUrl': '/assets/audio/notes/sol.mp3', 'answer': ['Sol'], 'points': 20, 'level': 3, 'options': [
            {'label': 'Rê', 'imageUrl': '/assets/images/games/note-re.png'},
            {'label': 'Mi', 'imageUrl': '/assets/images/games/note-mi.png'},
            {'label': 'Sol', 'imageUrl': '/assets/images/games/note-sol.png'},
            {'label': 'La', 'imageUrl': '/assets/images/games/note-la.png'}
        ]},
        {'id': 'mn006', 'question': 'Ghép Nốt Nhạc', 'audioUrl': '/assets/audio/notes/mi.mp3', 'answer': ['Mi'], 'points': 20, 'level': 3, 'options': [
            {'label': 'Rê', 'imageUrl': '/assets/images/games/note-re.png'},
            {'label': 'Mi', 'imageUrl': '/assets/images/games/note-mi.png'},
            {'label': 'Sol', 'imageUrl': '/assets/images/games/note-sol.png'},
            {'label': 'La', 'imageUrl': '/assets/images/games/note-la.png'}
        ]},
        {'id': 'mn007', 'question': 'Ghép Nốt Nhạc', 'audioUrl': '/assets/audio/notes/do.mp3', 'answer': ['Rê'], 'points': 20, 'level': 3, 'options': [
            {'label': 'Rê', 'imageUrl': '/assets/images/games/note-re.png'},
            {'label': 'Mi', 'imageUrl': '/assets/images/games/note-mi.png'},
            {'label': 'Sol', 'imageUrl': '/assets/images/games/note-sol.png'},
            {'label': 'La', 'imageUrl': '/assets/images/games/note-la.png'}
        ]},
        {'id': 'mn008', 'question': 'Ghép Nốt Nhạc', 'audioUrl': '/assets/audio/notes/sol.mp3', 'answer': ['Sol'], 'points': 20, 'level': 3, 'options': [
            {'label': 'Rê', 'imageUrl': '/assets/images/games/note-re.png'},
            {'label': 'Mi', 'imageUrl': '/assets/images/games/note-mi.png'},
            {'label': 'Sol', 'imageUrl': '/assets/images/games/note-sol.png'},
            {'label': 'La', 'imageUrl': '/assets/images/games/note-la.png'}
        ]},
        {'id': 'mn009', 'question': 'Ghép Nốt Nhạc', 'audioUrl': '/assets/audio/notes/mi.mp3', 'answer': ['Mi'], 'points': 20, 'level': 3, 'options': [
            {'label': 'Rê', 'imageUrl': '/assets/images/games/note-re.png'},
            {'label': 'Mi', 'imageUrl': '/assets/images/games/note-mi.png'},
            {'label': 'Sol', 'imageUrl': '/assets/images/games/note-sol.png'},
            {'label': 'La', 'imageUrl': '/assets/images/games/note-la.png'}
        ]},
        {'id': 'mn010', 'question': 'Ghép Nốt Nhạc', 'audioUrl': '/assets/audio/notes/do.mp3', 'answer': ['Rê'], 'points': 20, 'level': 3, 'options': [
            {'label': 'Rê', 'imageUrl': '/assets/images/games/note-re.png'},
            {'label': 'Mi', 'imageUrl': '/assets/images/games/note-mi.png'},
            {'label': 'Sol', 'imageUrl': '/assets/images/games/note-sol.png'},
            {'label': 'La', 'imageUrl': '/assets/images/games/note-la.png'}
        ]},
        ],
    'guess-pose': [
        {'id': 'gp001', 'question': 'Thế võ Vovinam này?', 'imageUrl': '/assets/images/games/pose-dontay1.png', 'answer': ['đòn tay số 1', 'đòn tay 1', 'don tay 1'], 'points': 15},
        {'id': 'gp002', 'question': 'Tên thế võ này là gì?', 'imageUrl': '/assets/images/games/pose-chemso4.png', 'answer': ['chém số 4', 'chem so 4', 'đòn chân số 4', 'don chan 4'], 'points': 15},
        ],
    'guess-stance': [
        {'id': 'gs001', 'question': 'Tên thế tấn này?', 'imageUrl': '/assets/images/games/stance-trungbinhtan.png', 'answer': ['trung bình tấn', 'trung binh tan'], 'points': 12},
        {'id': 'gs002', 'question': 'Đây là thế tấn gì trong Vovinam?', 'imageUrl': '/assets/images/games/stance-chuadinh.png', 'answer': ['thế tấn chữ đinh', 'tấn chữ đinh', 'chữ đinh tấn', 'chu dinh tan', 'tan chu dinh'], 'points': 12},
        ]
}
# Create a flat lookup for faster answer checking by ID
game_questions_lookup = {q['id']: q for type_list in game_questions_db_mock.values() for q in type_list}
# Ensure the lookup is updated with all questions
logger.info(f"Mini-game questions loaded: {len(game_questions_lookup)} total questions across {len(game_questions_db_mock)} game types")
# END MOCK

@app.route('/api/mini-game/start', methods=['GET'])
@token_required
def start_mini_game():
     try:
         game_type = request.args.get('type')
         if not game_type:
             return jsonify({'message': 'Game type required'}), 400
         if game_type not in game_questions_db_mock or not game_questions_db_mock[game_type]:
             # Log available types if type is invalid
             logger.warning(f"Invalid game type requested: '{game_type}'. Available: {list(game_questions_db_mock.keys())}")
             return jsonify({'message': f'Invalid or no questions available for game type: {game_type}'}), 404

         # Select a random question for the chosen type
         game_data = random.choice(game_questions_db_mock[game_type])

         # Prepare response for the frontend
         response_data = {
             'gameId': game_data['id'],
             'question': game_data['question'],
             'imageUrl': game_data.get('imageUrl'), # Include if available
             'audioUrl': game_data.get('audioUrl'), # Include audio URL if available
             'gameType': game_type # Include type for context if needed
         }
         logger.info(f"Mini-game '{game_type}' (ID: {game_data['id']}) started for user {request.current_user['_id']}")
         return jsonify(response_data)
     except Exception as e:
         logger.error(f"Start mini-game error: {e}", exc_info=True)
         return jsonify({'message': 'Server error starting mini-game'}), 500

@app.route('/api/mini-game/next', methods=['GET'])
@token_required
def get_next_mini_game_question():
    try:
        # Get game type and level from query params
        game_type = request.args.get('type')
        level = request.args.get('level')
        current_game_id = request.args.get('currentId')  # ID of the current question to avoid repeating

        if not game_type:
            return jsonify({'message': 'Game type required'}), 400
        if game_type not in game_questions_db_mock or not game_questions_db_mock[game_type]:
            logger.warning(f"Invalid game type requested: '{game_type}'. Available: {list(game_questions_db_mock.keys())}")
            return jsonify({'message': f'Invalid or no questions available for game type: {game_type}'}), 404

        # Filter questions by level if specified
        available_questions = game_questions_db_mock[game_type]
        if level:
            try:
                level_int = int(level)
                available_questions = [q for q in available_questions if q.get('level', 1) == level_int]
            except ValueError:
                # If level is not a valid integer, ignore it
                pass

        if not available_questions:
            return jsonify({'message': f'No questions available for game type {game_type} and level {level}'}), 404

        # Filter out the current question if provided
        if current_game_id and len(available_questions) > 1:
            available_questions = [q for q in available_questions if q['id'] != current_game_id]

        # Select a random question from the filtered list
        game_data = random.choice(available_questions)

        # Prepare response for the frontend
        response_data = {
            'gameId': game_data['id'],
            'question': game_data['question'],
            'imageUrl': game_data.get('imageUrl'),  # Include if available
            'audioUrl': game_data.get('audioUrl'),  # Include audio URL if available
            'gameType': game_type,  # Include type for context if needed
            'level': game_data.get('level', 1)  # Include level
        }

        # Include options for multiple choice questions (level 3)
        if game_data.get('options'):
            response_data['options'] = game_data['options']
            # Log the options format for debugging
            logger.info(f"Options format for question {game_data['id']}: {type(game_data['options'])}")

        logger.info(f"Next mini-game question '{game_type}' (ID: {game_data['id']}) level {game_data.get('level', 1)} fetched for user {request.current_user['_id']}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Get next mini-game question error: {e}", exc_info=True)
        return jsonify({'message': 'Server error getting next mini-game question'}), 500

@app.route('/api/mini-game/submit', methods=['POST'])
@token_required
def submit_mini_game_answer():
    try:
        user_id_obj = ObjectId(request.current_user['_id']) # Need ObjectId for DB query
        user_role = request.current_user.get('role')

        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        game_id = data.get('gameId')
        user_answer = data.get('answer', '').lower().strip() # Normalize answer

        if not game_id or not user_answer:
            return jsonify({'message': 'Game ID and answer required'}), 400

        # Lookup game data using the ID (from MOCK data for now)
        game_data = game_questions_lookup.get(game_id)
        if not game_data:
            return jsonify({'message': 'Invalid game ID'}), 404

        # Check answer (case-insensitive)
        correct_answer_list = [ans.lower() for ans in game_data.get('answer', [])]
        points_to_award = game_data.get('points', 10) # Default points
        is_correct = user_answer in correct_answer_list

        # Prepare response structure
        response_data = {
            'isCorrect': is_correct,
            'pointsAwarded': 0,
            # Include correct answer in response if user was wrong
            'correctAnswer': correct_answer_list[0] if not is_correct and correct_answer_list else None
        }

        # Award points and update ranking if correct and user is a student
        if is_correct and user_role == 'student':
            response_data['pointsAwarded'] = points_to_award
            update_result = db.users.update_one(
                {'_id': user_id_obj},
                {'$inc': {'points': points_to_award}}
            )
            if update_result.modified_count > 0:
                # Fetch updated user data for ranking update
                updated_user = db.users.find_one({'_id': user_id_obj})
                _update_user_ranking(str(user_id_obj), stringify_ids(updated_user))
                logger.info(f"Mini-game {game_id} correct for student {user_id_obj}. Points: +{points_to_award}")
            else:
                 logger.warning(f"Mini-game {game_id} correct, but failed to update points for student {user_id_obj}.")

        elif is_correct:
             logger.info(f"Mini-game {game_id} correct for non-student {user_id_obj}. No points awarded.")
        else:
             logger.info(f"Mini-game {game_id} incorrect for user {user_id_obj}. Answer: '{user_answer}', Correct: {correct_answer_list}")

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Submit mini-game answer error: {e}", exc_info=True)
        return jsonify({'message': 'Server error submitting mini-game answer'}), 500

@app.route('/api/chat', methods=['POST'])
@token_required
def chat_with_gemini():
    # Check if API key is configured
    if not GEMINI_API_KEY:
        logger.error("Chatbot request received but GEMINI_API_KEY is not configured.")
        return jsonify({'reply': 'Sorry, the chatbot is currently unavailable (Configuration Error).'}), 503 # Service Unavailable

    try:
        user_info = request.current_user # Already stringified
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        # Get question (which includes context/prompt from frontend)
        question_with_context = data.get('question', '').strip()
        # Get optional chat history from frontend for context
        chat_history = data.get('history', [])

        if not question_with_context:
            return jsonify({'message': 'Question required'}), 400

        # --- Prepare payload for Gemini API ---
        contents = []
        # Add validated history (basic check)
        if isinstance(chat_history, list):
            valid_history = [
                msg for msg in chat_history
                if isinstance(msg, dict) and
                   msg.get('role') in ['user', 'model'] and # Valid roles
                   isinstance(msg.get('parts'), list) and len(msg['parts']) > 0 and
                   isinstance(msg['parts'][0].get('text'), str) # Basic text part check
            ]
            contents.extend(valid_history)
        # Add the current user question
        contents.append({"role": "user", "parts": [{"text": question_with_context}]})

        # API Payload
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7, # Controls randomness (0=deterministic, 1=creative)
                "topK": 40,         # Considers top K tokens
                "topP": 0.95,       # Considers tokens with cumulative probability >= P
                "maxOutputTokens": 1500, # Limit response length
                # "stopSequences": ["\n\n"] # Optional sequences to stop generation
            },
            "safetySettings": [ # Configure safety filters
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
        }

        # --- Make API Call ---
        api_url_with_key = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}

        logger.info(f"Sending chat request to Gemini for user {user_info['_id']}...")
        # Set a reasonable timeout (e.g., 45 seconds)
        response = requests.post(api_url_with_key, headers=headers, json=payload, timeout=45)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        response_data = response.json()

        # --- Process Response ---
        # Check for blocked content or missing candidates
        if not response_data.get('candidates'):
             block_reason = response_data.get('promptFeedback', {}).get('blockReason', 'Unknown')
             safety_ratings = response_data.get('promptFeedback', {}).get('safetyRatings', [])
             logger.warning(f"Gemini response blocked or empty for user {user_info['_id']}. Reason: {block_reason}, Ratings: {safety_ratings}")
             # Provide a user-friendly message based on reason if possible
             reply_message = "I cannot provide a response due to content restrictions."
             if block_reason == 'SAFETY':
                 reply_message = "My safety filters prevented generating a response for this topic."
             return jsonify({'reply': reply_message})

        # Extract reply text
        try:
            reply = response_data['candidates'][0]['content']['parts'][0]['text']
        except (IndexError, KeyError) as e:
             logger.error(f"Error parsing Gemini response structure for user {user_info['_id']}: {e}. Response: {response_data}")
             return jsonify({'reply': 'Sorry, I encountered an issue processing the response.'})


        # Check finish reason (optional, but informative)
        finish_reason = response_data['candidates'][0].get('finishReason', 'STOP')
        if finish_reason != 'STOP':
            logger.warning(f"Gemini generation finished with reason: {finish_reason} for user {user_info['_id']}")
            if finish_reason == 'MAX_TOKENS':
                reply += "\n(Note: My response might have been cut short.)"
            elif finish_reason == 'SAFETY':
                # This case might be handled by the 'candidates' check earlier, but double-check
                reply = "The generated response was partially blocked due to safety filters."
            elif finish_reason == 'RECITATION':
                 reply += "\n(Note: Response might contain recited content.)"


        logger.info(f"Chatbot reply generated successfully for user {user_info['_id']}")
        return jsonify({'reply': reply.strip()})

    # --- Error Handling for API Call ---
    except requests.exceptions.HTTPError as e:
         status_code = e.response.status_code
         error_detail = e.response.text
         logger.error(f"Gemini API HTTP error ({status_code}) for user {request.current_user['_id']}: {error_detail}")
         reply = f"Sorry, the AI service encountered an error ({status_code}). Please try again later."
         if status_code == 429: # Too Many Requests
             reply = "The chatbot is experiencing high traffic right now. Please try again in a moment."
         elif status_code >= 500: # Server errors
              reply = "The AI service is temporarily unavailable. Please try again later."
         # Return the appropriate status code from the API if possible
         return jsonify({'reply': reply}), status_code if status_code in [429, 500, 503] else 502 # Bad Gateway
    except requests.exceptions.Timeout:
        logger.error(f"Gemini API request timed out for user {request.current_user['_id']}")
        return jsonify({'reply': 'The AI assistant took too long to respond. Please try again.'}), 504 # Gateway Timeout
    except requests.exceptions.RequestException as e:
        # Catch other network-related errors (DNS, connection refused, etc.)
        logger.error(f"Network error calling Gemini API: {e}")
        return jsonify({'reply': 'There was a network problem connecting to the AI assistant.'}), 504 # Gateway Timeout
    except Exception as e:
        # Catch-all for unexpected errors during processing
        logger.error(f"Chat processing error: {e}", exc_info=True)
        return jsonify({'message': 'Server error processing chat request'}), 500

# --- Static File Serving (Uploads) ---

@app.route('/uploads/avatars/<path:filename>')
def serve_avatar(filename):
    # Serve avatar files, no authentication needed usually
    try:
        # Basic security check
        if '..' in filename or filename.startswith('/'):
            raise ValueError("Invalid filename pattern")
        return send_from_directory(UPLOAD_FOLDER_AVATARS, filename)
    except FileNotFoundError:
        logger.warning(f"Avatar file not found: {filename}")
        # Return a default avatar or 404
        # return send_from_directory('path/to/defaults', 'default_avatar.png')
        return jsonify({'message': 'Avatar not found'}), 404
    except ValueError as e:
        logger.warning(f"Invalid avatar filename request: {filename}. Error: {e}")
        return jsonify({'message': 'Invalid filename'}), 400
    except Exception as e:
        logger.error(f"Serve avatar error: {e}")
        return jsonify({'message': 'Server error serving avatar'}), 500

@app.route('/assets/<path:filepath>')
def serve_assets(filepath):
    # Serve static assets from frontend/assets directory
    try:
        # Basic security check
        if '..' in filepath or filepath.startswith('/'):
            raise ValueError("Invalid path pattern")

        # Construct the full path to the asset
        asset_path = os.path.join(FRONTEND_DIR, 'assets')
        logger.info(f"Serving asset: {filepath} from {asset_path}")

        # Enable debug mode to see more information
        response = send_from_directory(asset_path, filepath)
        logger.info(f"Response for {filepath}: {response}")
        return response
    except FileNotFoundError as e:
        logger.warning(f"Asset file not found: {filepath}, Error: {str(e)}")
        return jsonify({'message': f'Asset not found: {filepath}'}), 404
    except ValueError as e:
        logger.warning(f"Invalid asset request: {filepath}. Error: {e}")
        return jsonify({'message': 'Invalid filename'}), 400
    except Exception as e:
        logger.error(f"Serve asset error for {filepath}: {str(e)}")
        return jsonify({'message': f'Server error serving asset: {str(e)}'}), 500

@app.route('/uploads/submissions/<path:filename>')
@token_required # Require login to access submission files
def serve_submission(filename):
    # Serve submission files, requires authentication and authorization
    try:
        # Basic security check
        if '..' in filename or filename.startswith('/'):
            raise ValueError("Invalid filename pattern")

        # Construct the URL path as stored in the database
        file_url_path = f"/uploads/submissions/{filename}"

        # Find the submission document by its URL
        submission = db.submissions.find_one({'url': file_url_path})
        if not submission:
             # Try finding by just filename if URL storage might be inconsistent
             alt_submission = db.submissions.find_one({'originalFilename': filename}) # Less reliable
             if alt_submission: submission = alt_submission
             else:
                logger.warning(f"Submission file or record not found for filename: {filename} (URL Path: {file_url_path})")
                return jsonify({'message': 'Submission record not found or file path mismatch'}), 404


        # --- Authorization Check ---
        user_id_str = request.current_user['_id'] # Requesting user (string)
        user_role = request.current_user['role']
        submission_owner_id_str = str(submission.get('userId')) # Owner (stringified)

        # Allow access if user is the owner OR if user is a teacher
        if user_id_str == submission_owner_id_str or user_role == 'teacher':
            logger.info(f"Serving submission '{filename}' to user {user_id_str} (Role: {user_role})")
            # Send the file from the correct directory
            return send_from_directory(UPLOAD_FOLDER_SUBMISSIONS, filename, as_attachment=False) # Display inline if possible
        else:
            # User is neither the owner nor a teacher
            logger.warning(f"Unauthorized attempt to access submission '{filename}' by user {user_id_str}")
            return jsonify({'message': 'Unauthorized access to this submission'}), 403

    except FileNotFoundError:
        # This means the file exists in DB record but not on disk
        logger.error(f"Submission file missing on disk: {filename}. DB record exists for URL: {file_url_path}")
        return jsonify({'message': 'Submission file data missing on server'}), 404
    except ValueError as e:
        logger.warning(f"Invalid submission filename request: {filename}. Error: {e}")
        return jsonify({'message': 'Invalid filename'}), 400
    except Exception as e:
        logger.error(f"Serve submission error: {e}")
        return jsonify({'message': 'Server error serving submission'}), 500


# --- Feedback Routes ---

@app.route('/api/feedback', methods=['POST'])
@token_required
def submit_feedback():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        feedback_text = data.get('text', '').strip()
        if not feedback_text:
            return jsonify({'message': 'Feedback text cannot be empty'}), 400

        # Get context URL (optional)
        page_url = data.get('url', request.referrer) # Use referrer as fallback

        # Create feedback document
        feedback_doc = {
            'userId': ObjectId(request.current_user['_id']), # Store as ObjectId
            'userName': request.current_user.get('name', 'Anonymous'), # Use current name
            'userEmail': request.current_user.get('email'),
            'text': feedback_text,
            'url': page_url, # URL where feedback was submitted
            'createdAt': datetime.now(timezone.utc),
            'status': 'new', # Initial status
            'reply': None,   # Teacher's reply
            'repliedAt': None,
            'repliedBy': None # Teacher's ObjectId
        }

        result = db.feedback.insert_one(feedback_doc)
        # Prepare response data (stringify IDs)
        response_data = stringify_ids(feedback_doc)
        response_data['_id'] = str(result.inserted_id) # Ensure _id from insert result is used

        logger.info(f"Feedback received from user {request.current_user['_id']} (Name: {response_data['userName']})")
        return jsonify({'message': 'Feedback submitted successfully!', 'feedback': response_data}), 201

    except Exception as e:
        logger.error(f"Submit feedback error: {e}", exc_info=True)
        return jsonify({'message': 'Server error submitting feedback'}), 500

@app.route('/api/feedback', methods=['GET'])
@token_required
def get_feedback():
    # Get feedback: Teachers see all, students see their own
    try:
        user_id_str = request.current_user['_id'] # Already string
        user_role = request.current_user['role']
        query = {}
        limit = int(request.args.get('limit', 20)) # Paginate results
        limit = max(1, min(limit, 100))

        if user_role != 'teacher':
            # Students only see their feedback
            query['userId'] = ObjectId(user_id_str) # Query by ObjectId

        # Optional status filter (e.g., /api/feedback?status=new)
        status_filter = request.args.get('status')
        if status_filter:
            query['status'] = status_filter.lower()


        feedback_cursor = db.feedback.find(query).sort('createdAt', -1).limit(limit)
        feedback_list = [stringify_ids(fb) for fb in feedback_cursor] # Stringify results

        logger.info(f"Feedback list fetched by user {user_id_str} ({user_role}). Filter: {query}, Limit: {limit}")
        return jsonify(feedback_list)

    except Exception as e:
        logger.error(f"Get feedback error: {e}", exc_info=True)
        return jsonify({'message': 'Server error fetching feedback'}), 500

@app.route('/api/feedback/<feedback_id_str>/reply', methods=['POST'])
@teacher_required # Only teachers can reply
def reply_to_feedback(feedback_id_str):
     try:
        if not ObjectId.is_valid(feedback_id_str):
            return jsonify({'message': 'Invalid feedback ID format'}), 400
        feedback_id_obj = ObjectId(feedback_id_str)
        replier_id_obj = ObjectId(request.current_user['_id']) # Teacher's ObjectId

        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid JSON payload'}), 400

        reply_text = data.get('reply', '').strip()
        # Allow setting status when replying (e.g., 'addressed', 'viewed')
        new_status = data.get('status', 'addressed').lower() # Default to addressed

        if not reply_text:
            return jsonify({'message': 'Reply text cannot be empty'}), 400
        if new_status not in ['new', 'viewed', 'addressed', 'rejected', 'spam']: # Define allowed statuses
             return jsonify({'message': f'Invalid status provided: {new_status}'}), 400

        # --- Update Feedback Document ---
        update_fields = {
            'reply': reply_text,
            'status': new_status,
            'repliedAt': datetime.now(timezone.utc),
            'repliedBy': replier_id_obj # Store teacher's ObjectId
        }
        result = db.feedback.update_one({'_id': feedback_id_obj}, {'$set': update_fields})

        if result.matched_count == 0:
            return jsonify({'message': 'Feedback item not found'}), 404
        if result.modified_count == 0:
            # May happen if update fields are same as existing
            logger.warning(f"Feedback {feedback_id_str} reply submitted, but no fields were modified.")


        # --- Fetch and Return Updated Feedback ---
        updated_feedback = db.feedback.find_one({'_id': feedback_id_obj})
        response_data = stringify_ids(updated_feedback) # Stringify ObjectIds

        logger.info(f"Feedback {feedback_id_str} replied/status updated by teacher {request.current_user['_id']}. New Status: {new_status}")
        # TODO: Optionally notify the student who submitted the feedback
        return jsonify({'success': True, 'message': 'Feedback updated successfully', 'feedback': response_data})

     except Exception as e:
        logger.error(f"Reply feedback error: {e}", exc_info=True)
        return jsonify({'message': 'Server error replying to feedback'}), 500

@app.route('/api/feedback/<feedback_id_str>/notify', methods=['POST'])
@teacher_required # Only teachers can send notifications
def notify_feedback_user(feedback_id_str):
    try:
        if not ObjectId.is_valid(feedback_id_str):
            return jsonify({'message': 'Invalid feedback ID format'}), 400
        feedback_id_obj = ObjectId(feedback_id_str)
        teacher_id_obj = ObjectId(request.current_user['_id']) # Teacher's ObjectId
        teacher_name = request.current_user.get('name', 'Teacher')

        # Get the feedback item
        feedback = db.feedback.find_one({'_id': feedback_id_obj})
        if not feedback:
            return jsonify({'message': 'Feedback item not found'}), 404

        # Check if feedback has a reply
        if not feedback.get('reply'):
            return jsonify({'message': 'Cannot notify user about a feedback without a reply'}), 400

        # Get the user who submitted the feedback
        user_id_obj = feedback.get('userId')
        if not user_id_obj:
            return jsonify({'message': 'Feedback has no associated user ID'}), 400

        # Create a notification document
        notification = {
            'userId': user_id_obj,
            'type': 'feedback_reply',
            'title': 'New Response to Your Feedback',
            'message': f"{teacher_name} has responded to your feedback.",
            'relatedId': feedback_id_obj,
            'createdAt': datetime.now(timezone.utc),
            'createdBy': teacher_id_obj,
            'read': False
        }

        # Insert the notification
        result = db.notifications.insert_one(notification)

        # Update the feedback to mark it as notified
        db.feedback.update_one(
            {'_id': feedback_id_obj},
            {'$set': {
                'notified': True,
                'notifiedAt': datetime.now(timezone.utc),
                'notifiedBy': teacher_id_obj
            }}
        )

        logger.info(f"Notification sent for feedback {feedback_id_str} by teacher {request.current_user['_id']} to user {user_id_obj}")
        return jsonify({
            'success': True,
            'message': 'Notification sent successfully',
            'notificationId': str(result.inserted_id)
        })

    except Exception as e:
        logger.error(f"Notify feedback user error: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Server error sending notification'}), 500


# --- Main Execution ---
if __name__ == '__main__':
    print(f"--- Attempting to start server on port {PORT} ---")
    logger.info(f"--- Starting FPT Learning Hub Server (PID: {os.getpid()}) ---")
    # Use Waitress for production, fallback to Flask dev server
    try:
        from waitress import serve
        logger.info(f"Starting server with Waitress on http://0.0.0.0:{PORT}")
        print(f"--- Production Server (Waitress) running on http://0.0.0.0:{PORT} ---")
        # Adjust threads as needed based on expected load and server cores
        serve(app, host='0.0.0.0', port=PORT, threads=8)
    except ImportError:
        logger.warning("Waitress not found, using Flask development server (NOT FOR PRODUCTION).")
        print(f"--- Development Server (Flask) running on http://0.0.0.0:{PORT} ---")
        # Set debug=True for development features like auto-reloading and debugger
        # Ensure debug=False in production environments
        app.run(host='0.0.0.0', port=PORT, debug=False) # Set debug=False for production simulation
    except Exception as e:
        print(f"!!! SERVER STARTUP FAILED: {e} !!!")
        logger.critical(f"Server failed to start: {e}", exc_info=True)
        raise # Reraise exception to indicate failure