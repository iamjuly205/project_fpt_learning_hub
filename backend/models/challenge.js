const mongoose = require('mongoose');

const challengeSchema = new mongoose.Schema({
    title: { type: String, required: true },
    description: { type: String, required: true },
    points: { type: Number, default: 10 },
    thumbnail: { type: String, required: true },
    type: { type: String, default: 'practice_video' },
    createdAt: { type: Date, default: Date.now },
    active: { type: Boolean, default: true }
});

challengeSchema.index({ title: 1 });
challengeSchema.index({ createdAt: -1 });

module.exports = mongoose.model('Challenge', challengeSchema);