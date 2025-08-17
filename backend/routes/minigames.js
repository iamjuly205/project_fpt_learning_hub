const express = require('express');
const auth = require('../middleware/auth');
const router = express.Router();

const miniGames = {
    'guess-note': { answers: ['đô', 'do'] },
    'guess-pose': { answers: ['đòn tay 1', 'hand strike 1'] },
    'guess-stance': { answers: ['thế tấn chữ đinh', 'ding stance'] }
};

router.post('/', auth, async (req, res) => {
    const { answer, gameType } = req.body;
    const correctAnswers = miniGames[gameType]?.answers || [];
    const isCorrect = correctAnswers.includes(answer.toLowerCase());
    res.json({ isCorrect });
});

module.exports = router;