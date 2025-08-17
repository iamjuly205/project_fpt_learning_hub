// seedData.js
const mongoose = require('mongoose');
const bcrypt = require('bcrypt');
require('dotenv').config(); // Đảm bảo dòng này ở đầu file

const connectDB = require('./config/db');
const User = require('./models/user');
const Course = require('./models/course');
const Video = require('./models/video');
const Ranking = require('./models/ranking');
const Flashcard = require('./models/flashcard');
const Challenge = require('./models/challenge');

// Kết nối tới MongoDB
connectDB();

// Hàm hash password
const hashPassword = async (password) => {
    const saltRounds = 10;
    return await bcrypt.hash(password, saltRounds);
};

// Dữ liệu mẫu
const seedData = async () => {
    try {
        // Xóa dữ liệu cũ (nếu cần)
        await User.deleteMany();
        await Course.deleteMany();
        await Video.deleteMany();
        await Ranking.deleteMany();
        await Flashcard.deleteMany();
        await Challenge.deleteMany();

        // Hash password mẫu
        const hashedPassword = await hashPassword('password123');

        // Thêm dữ liệu mẫu cho Users
        const users = await User.insertMany([
            {
                _id: new mongoose.Types.ObjectId(),
                email: 'student@fpt.edu.vn',
                password: hashedPassword,
                name: 'Nguyen Van A',
                role: 'student',
                points: 150,
                level: 2,
                progress: 75,
                badges: ['Beginner'],
                avatar: 'https://picsum.photos/150',
                personalCourses: [],
                googleId: null,
                facebookId: null
            },
            {
                _id: new mongoose.Types.ObjectId(),
                email: 'teacher@fpt.edu.vn',
                password: hashedPassword,
                name: 'Tran Thi B',
                role: 'teacher',
                points: 0,
                level: 1,
                progress: 0,
                badges: [],
                avatar: 'https://picsum.photos/150',
                personalCourses: [],
                googleId: null,
                facebookId: null
            }
        ]);

        // Thêm dữ liệu mẫu cho Courses
        const courses = await Course.insertMany([
            {
                _id: new mongoose.Types.ObjectId(),
                category: 'instruments',
                title: 'Học chơi sáo trúc',
                description: 'Khóa học cơ bản về sáo trúc truyền thống Việt Nam',
                video_url: 'https://example.com/sao-truc-video.mp4',
                thumbnail: 'https://example.com/sao-truc-thumbnail.jpg'
            },
            {
                _id: new mongoose.Types.ObjectId(),
                category: 'martial-arts',
                title: 'Tập Vovinam cơ bản',
                description: 'Khóa học cơ bản về võ thuật Vovinam',
                video_url: 'https://example.com/vovinam-video.mp4',
                thumbnail: 'https://example.com/vovinam-thumbnail.jpg'
            }
        ]);

        // Cập nhật personalCourses cho user
        await User.updateOne(
            { email: 'student@fpt.edu.vn' },
            { $push: { personalCourses: courses[0]._id } }
        );

        // Thêm dữ liệu mẫu cho Videos
        const videos = await Video.insertMany([
            {
                _id: new mongoose.Types.ObjectId(),
                userId: users[0]._id,
                email: 'student@fpt.edu.vn',
                note: 'Video luyện tập sáo',
                url: '/uploads/123456789-video.mp4',
                teacherComment: 'Cần cải thiện nhịp điệu'
            }
        ]);

        // Thêm dữ liệu mẫu cho Rankings
        const rankings = await Ranking.insertMany([
            {
                _id: new mongoose.Types.ObjectId(),
                userId: users[0]._id,
                name: 'Nguyen Van A',
                points: 150,
                avatar: 'https://picsum.photos/150'
            }
        ]);

        // Thêm dữ liệu mẫu cho Flashcards
        const flashcards = await Flashcard.insertMany([
            {
                _id: new mongoose.Types.ObjectId(),
                category: 'sao',
                question: 'Cách cầm sáo trúc đúng là gì?',
                answer: 'Dùng cả hai tay, ngón cái tay trái bấm lỗ cuối, ngón trỏ và giữa bấm các lỗ trên thân sáo.'
            },
            {
                _id: new mongoose.Types.ObjectId(),
                category: 'vovinam',
                question: 'Tư thế ngựa tấn trong Vovinam là gì?',
                answer: 'Chân trái bước lên, gối trái cong 90 độ, chân phải duỗi thẳng, thân người thẳng, mắt nhìn về phía trước.'
            }
        ]);

        // Thêm dữ liệu mẫu cho Challenges
        const challenges = await Challenge.insertMany([
            {
                _id: new mongoose.Types.ObjectId(),
                title: 'Thử thách chơi sáo 5 nốt',
                description: 'Hoàn thành bài tập chơi 5 nốt cơ bản trên sáo trúc',
                reward: '50 điểm',
                thumbnail: 'https://example.com/challenge-sao-thumbnail.jpg'
            }
        ]);

        console.log('Dữ liệu mẫu đã được chèn thành công vào MongoDB Atlas!');
        process.exit(0);
    } catch (error) {
        console.error('Lỗi khi chèn dữ liệu mẫu:', error);
        process.exit(1);
    }
};

seedData();