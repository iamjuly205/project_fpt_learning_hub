const express = require('express');
const multer = require('multer');
const Video = require('../models/video');
const auth = require('../middleware/auth');
const router = express.Router();

const storage = multer.diskStorage({
    destination: (req, file, cb) => cb(null, 'uploads/'),
    filename: (req, file, cb) => cb(null, `${Date.now()}-${file.originalname}`)
});
const upload = multer({ storage });

router.post('/', auth, upload.single('file'), async (req, res) => {
    try {
        const video = new Video({
            userId: req.user.id,
            email: req.body.email || 'anonymous',
            url: `/uploads/${req.file.filename}`,
            note: req.body.note
        });
        await video.save();
        res.json(video);
    } catch (error) {
        res.status(500).json({ message: 'Server error' });
    }
});

router.get('/', auth, async (req, res) => {
    try {
        const videos = await Video.find();
        res.json(videos);
    } catch (error) {
        res.status(500).json({ message: 'Server error' });
    }
});

router.put('/:id/comment', auth, async (req, res) => {
    try {
        const video = await Video.findById(req.params.id);
        if (!video) return res.status(404).json({ message: 'Video not found' });
        video.teacherComment = req.body.teacherComment;
        await video.save();
        res.json(video);
    } catch (error) {
        res.status(500).json({ message: 'Server error' });
    }
});

module.exports = router;

