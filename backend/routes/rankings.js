const express = require('express');
const Ranking = require('../models/ranking');
const auth = require('../middleware/auth');
const router = express.Router();

router.get('/', auth, async (req, res) => {
    try {
        const rankings = await Ranking.find().sort({ points: -1 }).limit(10);
        res.json(rankings);
    } catch (error) {
        res.status(500).json({ message: 'Server error' });
    }
});

router.post('/update', auth, async (req, res) => {
    try {
        const { userId, points, name, avatar } = req.body;
        let ranking = await Ranking.findOne({ userId });
        if (!ranking) {
            ranking = new Ranking({ userId, name, points, avatar });
        } else {
            ranking.points = points;
            ranking.name = name;
            ranking.avatar = avatar;
        }
        await ranking.save();
        res.json(ranking);
    } catch (error) {
        res.status(500).json({ message: 'Server error' });
    }
});

module.exports = router;