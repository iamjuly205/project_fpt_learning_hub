const mongoose = require('mongoose');

const courseSchema = new mongoose.Schema({
    category: { type: String, required: true },
    title: { type: String, required: true },
    description: { type: String, required: true },
    video_url: { type: String, required: true },
    theory_url: { type: String, default: '' },
    thumbnail: { type: String, required: true }
});

courseSchema.index({ category: 1 });

module.exports = mongoose.model('Course', courseSchema);