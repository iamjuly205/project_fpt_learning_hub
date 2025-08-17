const express = require('express');
const router = express.Router();
const auth = require('../middleware/auth');
const multer = require('multer');
const path = require('path');
const mongoose = require('mongoose');
const User = require('../models/user');

// Middleware để kiểm tra quyền giáo viên
const teacherAuth = (req, res, next) => {
    if (req.user.role !== 'teacher') {
        return res.status(403).json({ message: 'Không có quyền truy cập' });
    }
    next();
};

// Cấu hình multer cho upload file
const storage = multer.diskStorage({
    destination: (req, file, cb) => cb(null, 'uploads/submissions/'),
    filename: (req, file, cb) => {
        const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1e9);
        cb(null, file.fieldname + '-' + uniqueSuffix + path.extname(file.originalname));
    }
});
const upload = multer({ storage });

// API lấy danh sách bài nộp (chỉ giáo viên)
router.get('/', auth, teacherAuth, async (req, res) => {
    try {
        const { status, limit = 100, type } = req.query;
        
        // Xây dựng query
        const query = {};
        if (status) query.status = status;
        if (type) query.type = type;
        
        // Lấy danh sách bài nộp
        const submissions = await mongoose.connection.db.collection('submissions')
            .find(query)
            .limit(parseInt(limit))
            .sort({ createdAt: -1 })
            .toArray();
        
        res.json(submissions);
    } catch (error) {
        console.error('Error fetching submissions:', error);
        res.status(500).json({ message: 'Lỗi server', error: error.message });
    }
});

// API lấy chi tiết bài nộp (chỉ giáo viên hoặc người nộp)
router.get('/:id', auth, async (req, res) => {
    try {
        const submissionId = req.params.id;
        
        // Kiểm tra ID hợp lệ
        if (!mongoose.Types.ObjectId.isValid(submissionId)) {
            return res.status(400).json({ message: 'ID bài nộp không hợp lệ' });
        }
        
        // Lấy thông tin bài nộp
        const submission = await mongoose.connection.db.collection('submissions')
            .findOne({ _id: new mongoose.Types.ObjectId(submissionId) });
        
        if (!submission) {
            return res.status(404).json({ message: 'Bài nộp không tồn tại' });
        }
        
        // Kiểm tra quyền truy cập
        if (req.user.role !== 'teacher' && submission.userId !== req.user.id) {
            return res.status(403).json({ message: 'Không có quyền truy cập' });
        }
        
        res.json(submission);
    } catch (error) {
        console.error('Error fetching submission details:', error);
        res.status(500).json({ message: 'Lỗi server', error: error.message });
    }
});

// API nộp bài (cho học viên)
router.post('/', auth, upload.single('file'), async (req, res) => {
    try {
        const { type = 'submission', note, relatedTitle, challengeId } = req.body;
        
        if (!req.file) {
            return res.status(400).json({ message: 'Không có file được tải lên' });
        }
        
        // Tạo bài nộp mới
        const newSubmission = {
            userId: req.user.id,
            userName: req.user.name,
            userEmail: req.user.email,
            type,
            url: `/uploads/submissions/${req.file.filename}`,
            originalFilename: req.file.originalname,
            note,
            relatedTitle,
            challengeId,
            status: 'pending',
            createdAt: new Date(),
            updatedAt: new Date()
        };
        
        // Lưu vào database
        const result = await mongoose.connection.db.collection('submissions').insertOne(newSubmission);
        
        res.status(201).json({
            message: 'Nộp bài thành công',
            submission: {
                _id: result.insertedId,
                ...newSubmission
            }
        });
    } catch (error) {
        console.error('Error submitting challenge:', error);
        res.status(500).json({ message: 'Lỗi server', error: error.message });
    }
});

// API đánh giá bài nộp (chỉ giáo viên)
router.put('/:id/review', auth, teacherAuth, async (req, res) => {
    try {
        const submissionId = req.params.id;
        
        // Kiểm tra ID hợp lệ
        if (!mongoose.Types.ObjectId.isValid(submissionId)) {
            return res.status(400).json({ message: 'ID bài nộp không hợp lệ' });
        }
        
        const { status, teacherComment, pointsAwarded, teacherId, teacherName, reviewedAt } = req.body;
        
        // Kiểm tra dữ liệu đầu vào
        if (!status || !['approved', 'rejected'].includes(status)) {
            return res.status(400).json({ message: 'Trạng thái không hợp lệ' });
        }
        
        if (status === 'rejected' && !teacherComment) {
            return res.status(400).json({ message: 'Cần có nhận xét khi từ chối bài nộp' });
        }
        
        // Lấy thông tin bài nộp
        const submission = await mongoose.connection.db.collection('submissions')
            .findOne({ _id: new mongoose.Types.ObjectId(submissionId) });
        
        if (!submission) {
            return res.status(404).json({ message: 'Bài nộp không tồn tại' });
        }
        
        // Cập nhật bài nộp
        const updateData = {
            status,
            teacherComment,
            teacherId,
            teacherName,
            reviewedAt,
            updatedAt: new Date()
        };
        
        if (status === 'approved') {
            updateData.pointsAwarded = pointsAwarded || 0;
            
            // Cập nhật điểm cho học viên nếu bài được chấp nhận
            if (pointsAwarded > 0) {
                await User.findByIdAndUpdate(
                    submission.userId,
                    {
                        $inc: { points: pointsAwarded },
                        $set: { updatedAt: new Date() }
                    }
                );
            }
        }
        
        // Cập nhật bài nộp
        await mongoose.connection.db.collection('submissions').updateOne(
            { _id: new mongoose.Types.ObjectId(submissionId) },
            { $set: updateData }
        );
        
        res.json({
            message: `Bài nộp đã được ${status === 'approved' ? 'chấp nhận' : 'từ chối'}`,
            submission: {
                _id: submissionId,
                ...submission,
                ...updateData
            }
        });
    } catch (error) {
        console.error('Error reviewing submission:', error);
        res.status(500).json({ message: 'Lỗi server', error: error.message });
    }
});

module.exports = router;
