const express = require('express');
const Challenge = require('../models/challenge');
const auth = require('../middleware/auth');
const multer = require('multer');
const router = express.Router();

const storage = multer.diskStorage({
    destination: (req, file, cb) => cb(null, 'uploads/'),
    filename: (req, file, cb) => cb(null, `${Date.now()}-${file.originalname}`)
});
const upload = multer({ storage });

router.get('/daily', auth, async (req, res) => {
    try {
        const challenge = await Challenge.findOne().sort({ date: -1 });
        if (!challenge) {
            const newChallenge = new Challenge({
                title: 'Thử thách ngày mới',
                description: 'Hoàn thành một bài tập bất kỳ hôm nay.',
                thumbnail: 'https://via.placeholder.com/150'
            });
            await newChallenge.save();
            return res.json(newChallenge);
        }
        res.json(challenge);
    } catch (error) {
        res.status(500).json({ message: 'Server error' });
    }
});

router.post('/submit', auth, upload.single('file'), async (req, res) => {
    try {
        res.json({ message: 'Challenge submitted', url: `/uploads/${req.file.filename}` });
    } catch (error) {
        res.status(500).json({ message: 'Server error' });
    }
});

module.exports = router;