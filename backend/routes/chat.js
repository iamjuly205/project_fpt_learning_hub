const express = require('express');
const router = express.Router();
const auth = require('../middleware/auth');
const axios = require('axios');
const mongoose = require('mongoose');
require('dotenv').config();

const faqSchema = new mongoose.Schema({
    question: { type: String, required: true, unique: true },
    answer: { type: String, required: true },
    category: { type: String, default: 'general' },
    source: { type: String, default: 'manual' } // Nguồn: manual (tự nhập) hoặc ai (Gemini)
});
const FAQ = mongoose.model('FAQ', faqSchema);

async function callGeminiAPI(question, context) {
    const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
    const GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent';

    try {
        const response = await axios.post(
            `${GEMINI_API_URL}?key=${GEMINI_API_KEY}`,
            {
                contents: [{
                    parts: [{ text: `${context}\nCâu hỏi: ${question}\nTrả lời ngắn gọn, chính xác bằng tiếng Việt.` }]
                }]
            },
            { headers: { 'Content-Type': 'application/json' } }
        );
        return response.data.candidates[0].content.parts[0].text.trim();
    } catch (error) {
        console.error('Gemini API error:', error.response?.data || error.message);
        throw new Error('Không thể kết nối tới Gemini API');
    }
}

router.post('/', auth, async (req, res) => {
    const { question } = req.body;
    if (!question || typeof question !== 'string') {
        return res.status(400).json({ reply: 'Câu hỏi không hợp lệ!' });
    }

    const lowerCaseQuestion = question.toLowerCase();

    try {
        // Quét FAQ trước
        const faq = await FAQ.findOne({ question: { $regex: new RegExp(`^${lowerCaseQuestion}$`, 'i') } });
        if (faq) return res.json({ reply: faq.answer, source: 'faq' });

        // Quét dữ liệu từ Course
        const Course = require('../models/course');
        const courses = await Course.find({
            $or: [
                { title: { $regex: lowerCaseQuestion, $options: 'i' } },
                { description: { $regex: lowerCaseQuestion, $options: 'i' } }
            ]
        });
        if (courses.length > 0) {
            const reply = courses.map(c => `${c.title}: ${c.description}`).join('\n');
            return res.json({ reply, source: 'course' });
        }

        // Quét dữ liệu từ Flashcard
        const Flashcard = require('../models/flashcard');
        const flashcards = await Flashcard.find({
            $or: [
                { question: { $regex: lowerCaseQuestion, $options: 'i' } },
                { answer: { $regex: lowerCaseQuestion, $options: 'i' } }
            ]
        });
        if (flashcards.length > 0) {
            const reply = flashcards.map(f => `${f.question} - ${f.answer}`).join('\n');
            return res.json({ reply, source: 'flashcard' });
        }

        // Nếu không tìm thấy trong DB, gọi Gemini API
        const context = `Tôi là chatbot của FPT Learning Hub hỗ trợ học tập về nhạc cụ dân tộc và Vovinam.`;
        const reply = await callGeminiAPI(question, context);

        // Lưu câu trả lời từ Gemini vào FAQ để tái sử dụng
        await FAQ.create({ question: lowerCaseQuestion, answer: reply, category: 'auto', source: 'ai' });
        res.json({ reply, source: 'gemini' });
    } catch (error) {
        res.status(500).json({ reply: error.message || 'Có lỗi xảy ra, vui lòng thử lại!' });
    }
});

module.exports = router;