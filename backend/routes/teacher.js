const express = require('express');
const router = express.Router();
const auth = require('../middleware/auth'); // Middleware xác thực token
const User = require('../models/user');
const Submission = require('../models/submission');
const mongoose = require('mongoose');

// Middleware kiểm tra quyền giáo viên
const teacherAuth = (req, res, next) => {
    if (req.user.role !== 'teacher') {
        return res.status(403).json({ message: 'Không có quyền truy cập' });
    }
    next();
};

// API lấy danh sách sinh viên
router.get('/students', auth, teacherAuth, async (req, res) => {
    try {
        // Lấy danh sách sinh viên (role = 'student' hoặc không có role)
        const students = await User.find({
            $or: [
                { role: 'student' },
                { role: { $exists: false } }
            ]
        }).select('-password');

        res.json(students);
    } catch (error) {
        console.error('Error fetching students:', error);
        res.status(500).json({ message: 'Lỗi server', error: error.message });
    }
});

// API lấy thông tin chi tiết của một sinh viên
router.get('/users/:id', auth, teacherAuth, async (req, res) => {
    try {
        const studentId = req.params.id;
        if (!mongoose.Types.ObjectId.isValid(studentId)) {
            return res.status(400).json({ message: 'ID sinh viên không hợp lệ' });
        }

        // Lấy thông tin chi tiết của sinh viên
        const student = await User.findById(studentId).select('-password');
        if (!student) {
            return res.status(404).json({ message: 'Sinh viên không tồn tại' });
        }

        // Kiểm tra nếu người dùng không phải là sinh viên
        if (student.role && student.role !== 'student') {
            return res.status(400).json({ message: 'Người dùng này không phải là sinh viên' });
        }

        // Lấy thêm thông tin về khóa học và thành tựu của sinh viên
        const studentData = {
            ...student.toObject(),
            courses: student.personalCourses || [],
            achievements: [],
            lastActive: student.lastLogin || new Date(),
            joinDate: student.createdAt || new Date()
        };

        // Tính toán thành tựu dựa trên dữ liệu của sinh viên
        if (student.points >= 500) {
            studentData.achievements.push('Đạt 500 điểm');
        } else if (student.points >= 300) {
            studentData.achievements.push('Đạt 300 điểm');
        } else if (student.points >= 100) {
            studentData.achievements.push('Đạt 100 điểm');
        }

        if (student.loginStreak >= 20) {
            studentData.achievements.push('Chuỗi đăng nhập 20 ngày');
        } else if (student.loginStreak >= 10) {
            studentData.achievements.push('Chuỗi đăng nhập 10 ngày');
        } else if (student.loginStreak >= 5) {
            studentData.achievements.push('Chuỗi đăng nhập 5 ngày');
        }

        if (student.completedLessons && student.completedLessons.length >= 20) {
            studentData.achievements.push('Hoàn thành 20 bài học');
        } else if (student.completedLessons && student.completedLessons.length >= 10) {
            studentData.achievements.push('Hoàn thành 10 bài học');
        } else if (student.completedLessons && student.completedLessons.length >= 5) {
            studentData.achievements.push('Hoàn thành 5 bài học');
        }

        res.json(studentData);
    } catch (error) {
        console.error('Error fetching student details:', error);
        res.status(500).json({ message: 'Lỗi server', error: error.message });
    }
});

// API cập nhật tiến độ của sinh viên
router.put('/users/:id/progress', auth, teacherAuth, async (req, res) => {
    try {
        const studentId = req.params.id;
        if (!mongoose.Types.ObjectId.isValid(studentId)) {
            return res.status(400).json({ message: 'ID sinh viên không hợp lệ' });
        }

        const { progress } = req.body;
        if (progress === undefined || progress < 0 || progress > 100) {
            return res.status(400).json({ message: 'Giá trị tiến độ không hợp lệ (0-100)' });
        }

        // Cập nhật tiến độ của sinh viên
        const student = await User.findById(studentId);
        if (!student) {
            return res.status(404).json({ message: 'Sinh viên không tồn tại' });
        }

        // Kiểm tra nếu người dùng không phải là sinh viên
        if (student.role && student.role !== 'student') {
            return res.status(400).json({ message: 'Người dùng này không phải là sinh viên' });
        }

        student.progress = progress;
        await student.save();

        res.json({
            message: 'Cập nhật tiến độ thành công',
            student: {
                _id: student._id,
                name: student.name,
                email: student.email,
                progress: student.progress
            }
        });
    } catch (error) {
        console.error('Error updating student progress:', error);
        res.status(500).json({ message: 'Lỗi server', error: error.message });
    }
});

// API lấy thống kê cho giáo viên
router.get('/analytics', auth, teacherAuth, async (req, res) => {
    try {
        // Đếm số lượng sinh viên
        const studentCount = await User.countDocuments({
            $or: [
                { role: 'student' },
                { role: { $exists: false } }
            ]
        });

        // Đếm số lượng bài nộp đang chờ duyệt
        const pendingSubmissions = await Submission.countDocuments({ status: 'pending' });

        // Đếm số lượng bài nộp đã duyệt
        const approvedSubmissions = await Submission.countDocuments({ status: 'approved' });

        // Tính điểm trung bình của sinh viên
        const averagePointsResult = await User.aggregate([
            {
                $match: {
                    $or: [
                        { role: 'student' },
                        { role: { $exists: false } }
                    ]
                }
            },
            {
                $group: {
                    _id: null,
                    averagePoints: { $avg: '$points' }
                }
            }
        ]);

        const averagePoints = averagePointsResult.length > 0 ? Math.round(averagePointsResult[0].averagePoints) : 0;

        // Tính tiến độ trung bình của sinh viên
        const averageProgressResult = await User.aggregate([
            {
                $match: {
                    $or: [
                        { role: 'student' },
                        { role: { $exists: false } }
                    ]
                }
            },
            {
                $group: {
                    _id: null,
                    averageProgress: { $avg: '$progress' }
                }
            }
        ]);

        const averageProgress = averageProgressResult.length > 0 ? Math.round(averageProgressResult[0].averageProgress) : 0;

        res.json({
            studentCount,
            pendingSubmissions,
            approvedSubmissions,
            averagePoints,
            averageProgress
        });
    } catch (error) {
        console.error('Error fetching teacher analytics:', error);
        res.status(500).json({ message: 'Lỗi server', error: error.message });
    }
});

module.exports = router;
