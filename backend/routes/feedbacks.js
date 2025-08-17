const express = require('express');
const Feedback = require('../models/feedback');
const auth = require('../middleware/auth');
const router = express.Router();

router.post('/', auth, async (req, res) => {
    try {
        const feedback = new Feedback({
            userId: req.user.id,
            userName: req.body.userName || 'Ẩn danh',
            text: req.body.text
        });
        await feedback.save();
        res.json(feedback);
    } catch (error) {
        res.status(500).json({ message: 'Server error' });
    }
});

router.get('/', auth, async (req, res) => {
    try {
        const feedback = await Feedback.find().sort({ created_at: -1 });
        res.json(feedback);
    } catch (error) {
        res.status(500).json({ message: 'Server error' });
    }
});

module.exports = router;