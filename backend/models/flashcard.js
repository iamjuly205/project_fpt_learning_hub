const mongoose = require('mongoose');

const flashcardSchema = new mongoose.Schema({
    category: { type: String, required: true, enum: ['sao', 'dan-tranh', 'dan-nguyet', 'vovinam'] },
    question: { type: String, required: true },
    answer: { type: String, required: true },
    completed: { type: Boolean, default: false }
});

flashcardSchema.index({ category: 1 });
flashcardSchema.index({ question: 1 });

module.exports = mongoose.model('Flashcard', flashcardSchema);