const mongoose = require('mongoose');

const userSchema = new mongoose.Schema({
    name: { type: String, required: true },
    email: { type: String, required: true, unique: true },
    password: { type: String },
    role: { type: String, enum: ['student', 'teacher'], default: 'student' },
    avatar: { type: String, default: 'https://picsum.photos/150' },
    progress: { type: Number, default: 0 },
    points: { type: Number, default: 0 },
    level: { type: Number, default: 1 },
    badges: [{ type: String }],
    personalCourses: [{ type: mongoose.Schema.Types.ObjectId, ref: 'Course' }],
    flashcardProgress: { type: Map, of: Object },
    flashcardScore: { type: Number, default: 0 },
    activityHistory: [{ message: String, timestamp: Date }],
    streak: { type: Number, default: 0 },
    lastLogin: { type: Date, default: Date.now }
}, { timestamps: true });

module.exports = mongoose.model('User', userSchema);