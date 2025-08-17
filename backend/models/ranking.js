const mongoose = require('mongoose');

const rankingSchema = new mongoose.Schema({
    userId: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
    name: { type: String, required: true },
    points: { type: Number, required: true },
    avatar: { type: String, required: true }
});

rankingSchema.index({ points: -1 });
rankingSchema.index({ userId: 1 });

module.exports = mongoose.model('Ranking', rankingSchema);