const mongoose = require('mongoose');

const videoSchema = new mongoose.Schema({
    userId: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
    email: { type: String, required: true },
    note: { type: String },
    url: { type: String, required: true },
    teacherComment: { type: String, default: '' }
});

videoSchema.index({ userId: 1 });

module.exports = mongoose.model('Video', videoSchema);