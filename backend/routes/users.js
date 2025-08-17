const express = require('express');
const router = express.Router();
const auth = require('../middleware/auth'); // Middleware xác thực token
const User = require('../models/user');
const bcrypt = require('bcrypt');
const multer = require('multer');
const path = require('path');
const mongoose = require('mongoose');

// Cấu hình multer cho avatar
const storage = multer.diskStorage({
    destination: (req, file, cb) => cb(null, 'uploads/avatars/'),
    filename: (req, file, cb) => {
        const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1e9);
        cb(null, file.fieldname + '-' + uniqueSuffix + path.extname(file.originalname));
    }
});
const upload = multer({ storage });

// Lấy thông tin người dùng hiện tại
router.get('/me', auth, async (req, res) => {
    try {
        const user = await User.findById(req.user.id).select('-password');
        if (!user) return res.status(404).json({ message: 'Người dùng không tồn tại' });
        res.json(user);
    } catch (error) {
        res.status(500).json({ message: 'Lỗi server', error: error.message });
    }
});

// Cập nhật thông tin người dùng
router.put('/:id', auth, async (req, res) => {
    try {
        const userId = req.params.id;
        if (!mongoose.Types.ObjectId.isValid(userId)) return res.status(400).json({ message: 'ID người dùng không hợp lệ' });

        const updates = req.body;
        const updatedUser = await User.findByIdAndUpdate(
            userId,
            { $set: updates },
            { new: true, runValidators: true }
        ).select('-password');

        if (!updatedUser) return res.status(404).json({ message: 'Người dùng không tồn tại' });
        res.json(updatedUser);
    } catch (error) {
        res.status(500).json({ message: 'Lỗi server', error: error.message });
    }
});

// Cập nhật avatar
router.put('/:id/avatar', auth, upload.single('avatar'), async (req, res) => {
    try {
        const userId = req.params.id;
        if (!mongoose.Types.ObjectId.isValid(userId)) return res.status(400).json({ message: 'ID người dùng không hợp lệ' });

        const user = await User.findById(userId);
        if (!user) return res.status(404).json({ message: 'Người dùng không tồn tại' });

        if (req.file) {
            user.avatar = `/avatars/${req.file.filename}`;
            await user.save();
            res.json(user);
        } else {
            res.status(400).json({ message: 'Không có file avatar được tải lên' });
        }
    } catch (error) {
        res.status(500).json({ message: 'Lỗi server', error: error.message });
    }
});

// Đổi mật khẩu
router.put('/:id/password', auth, async (req, res) => {
    try {
        const userId = req.params.id;
        if (!mongoose.Types.ObjectId.isValid(userId)) return res.status(400).json({ message: 'ID người dùng không hợp lệ' });

        const { currentPassword, newPassword } = req.body;
        const user = await User.findById(userId);

        if (!user) return res.status(404).json({ message: 'Người dùng không tồn tại' });
        if (!user.password) return res.status(400).json({ message: 'Không thể đổi mật khẩu cho tài khoản qua Google/Facebook' });

        const isMatch = await bcrypt.compare(currentPassword, user.password);
        if (!isMatch) return res.status(400).json({ message: 'Mật khẩu hiện tại không đúng' });

        if (newPassword.length < 6) return res.status(400).json({ message: 'Mật khẩu mới phải có ít nhất 6 ký tự' });

        user.password = await bcrypt.hash(newPassword, 10);
        await user.save();
        res.json({ message: 'Đổi mật khẩu thành công' });
    } catch (error) {
        res.status(500).json({ message: 'Lỗi server', error: error.message });
    }
});

// Lưu tiến độ flashcard
router.put('/:id/flashcards', auth, async (req, res) => {
    try {
        const userId = req.params.id;
        if (!mongoose.Types.ObjectId.isValid(userId)) return res.status(400).json({ message: 'ID người dùng không hợp lệ' });

        const { flashcardProgress, flashcardScore } = req.body;
        const user = await User.findById(userId);

        if (!user) return res.status(404).json({ message: 'Người dùng không tồn tại' });

        user.flashcardProgress = flashcardProgress || user.flashcardProgress;
        user.flashcardScore = flashcardScore || user.flashcardScore;
        await user.save();
        res.json(user);
    } catch (error) {
        res.status(500).json({ message: 'Lỗi server', error: error.message });
    }
});

// Lấy thông tin người dùng theo ID (cho Bảng Xếp Hạng)
router.get('/:id', auth, async (req, res) => {
    try {
        const user = await User.findById(req.params.id).select('-password');
        if (!user) return res.status(404).json({ message: 'Người dùng không tồn tại' });
        res.json(user);
    } catch (error) {
        res.status(500).json({ message: 'Lỗi server', error: error.message });
    }
});

// API cho giáo viên lấy danh sách sinh viên
router.get('/teacher/students', auth, async (req, res) => {
    try {
        // Kiểm tra quyền giáo viên
        if (req.user.role !== 'teacher') {
            return res.status(403).json({ message: 'Không có quyền truy cập' });
        }

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

// API cho giáo viên lấy thông tin chi tiết của một sinh viên
router.get('/teacher/students/:id', auth, async (req, res) => {
    try {
        // Kiểm tra quyền giáo viên
        if (req.user.role !== 'teacher') {
            return res.status(403).json({ message: 'Không có quyền truy cập' });
        }

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

        res.json(student);
    } catch (error) {
        console.error('Error fetching student details:', error);
        res.status(500).json({ message: 'Lỗi server', error: error.message });
    }
});

// API cho giáo viên cập nhật tiến độ của sinh viên
router.put('/teacher/students/:id/progress', auth, async (req, res) => {
    try {
        // Kiểm tra quyền giáo viên
        if (req.user.role !== 'teacher') {
            return res.status(403).json({ message: 'Không có quyền truy cập' });
        }

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

module.exports = router;