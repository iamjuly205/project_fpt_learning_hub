const express = require('express');
const router = express.Router();
const auth = require('../middleware/auth');
const Flashcard = require('../models/flashcard');

router.get('/:category', async (req, res) => {
    try {
        const flashcards = await Flashcard.find({ category: req.params.category });
        res.json(flashcards);
    } catch (error) {
        console.error('Error fetching flashcards:', error.message);
        res.status(500).json({ message: 'Server error', error });
    }
});

router.post('/', auth, async (req, res) => {
    if (req.user.role !== 'teacher') return res.status(403).json({ message: 'Access denied' });

    const { category, question, answer } = req.body;
    try {
        const flashcard = new Flashcard({ category, question, answer });
        await flashcard.save();
        res.status(201).json(flashcard);
    } catch (error) {
        console.error('Error adding flashcard:', error.message);
        res.status(500).json({ message: 'Server error', error });
    }
});

module.exports = router;