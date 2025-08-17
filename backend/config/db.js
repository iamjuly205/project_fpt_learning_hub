const mongoose = require('mongoose');
require('dotenv').config();

const connectDB = async () => {
    try {
        await mongoose.connect(process.env.MONGO_URI, {});
        console.log('MongoDB Atlas connected');

        mongoose.connection.on('open', async () => {
            await mongoose.connection.db.collection('users').createIndex({ email: 1 }, { unique: true });
            await mongoose.connection.db.collection('users').createIndex({ points: -1 });
            await mongoose.connection.db.collection('courses').createIndex({ category: 1 });
            await mongoose.connection.db.collection('videos').createIndex({ userId: 1 });
            await mongoose.connection.db.collection('rankings').createIndex({ points: -1 });
            await mongoose.connection.db.collection('rankings').createIndex({ userId: 1 });
            await mongoose.connection.db.collection('flashcards').createIndex({ category: 1 });
            await mongoose.connection.db.collection('flashcards').createIndex({ question: 1 });
            await mongoose.connection.db.collection('challenges').createIndex({ title: 1 });
            await mongoose.connection.db.collection('minigames').createIndex({ question: 1 });
        });
    } catch (error) {
        console.error('MongoDB Atlas connection error:', error);
        process.exit(1);
    }
};

module.exports = connectDB;