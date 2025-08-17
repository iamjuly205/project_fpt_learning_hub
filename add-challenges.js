// add-challenges.js
// Script to add new challenges to MongoDB

const mongoose = require('mongoose');
require('dotenv').config();
const challengesData = require('./challenges-data');

// Connect to MongoDB
const connectDB = async () => {
  try {
    // Get MongoDB URI from environment variable
    const mongoURI = process.env.MONGO_URI;
    if (!mongoURI) {
      console.error('MONGO_URI environment variable is not set');
      return false;
    }

    // Connect to MongoDB
    await mongoose.connect(mongoURI, {
      useNewUrlParser: true,
      useUnifiedTopology: true
    });
    console.log('MongoDB connected successfully');
    return true;
  } catch (error) {
    console.error('MongoDB connection error:', error);
    return false;
  }
};

// Define Challenge schema directly in this script
// This ensures we don't need to rely on the model file
const challengeSchema = new mongoose.Schema({
  title: { type: String, required: true },
  description: { type: String, required: true },
  points: { type: Number, default: 10 },
  thumbnail: { type: String, required: true },
  type: { type: String, default: 'practice_video' },
  createdAt: { type: Date, default: Date.now },
  active: { type: Boolean, default: true }
});

// Add challenges to database
const addChallenges = async () => {
  try {
    // Connect to database
    const connected = await connectDB();
    if (!connected) {
      console.error('Failed to connect to MongoDB. Exiting...');
      process.exit(1);
    }

    // Get the database name from the connection string
    const dbName = 'fpt_learning'; // Use the same database name as in app.py

    // Get the challenges collection
    const db = mongoose.connection.db;
    const challengesCollection = db.collection('challenges');

    console.log(`Adding challenges to database ${dbName}...`);

    // Track results
    let inserted = 0;
    let updated = 0;
    let errors = 0;

    // Process each challenge
    for (const challenge of challengesData) {
      try {
        // Add createdAt if not present
        if (!challenge.createdAt) {
          challenge.createdAt = new Date();
        }

        // Ensure active flag is set
        if (challenge.active === undefined) {
          challenge.active = true;
        }

        // Check if challenge with same title already exists
        const existingChallenge = await challengesCollection.findOne({ title: challenge.title });

        if (existingChallenge) {
          // Update existing challenge
          const result = await challengesCollection.updateOne(
            { title: challenge.title },
            { $set: challenge }
          );

          if (result.modifiedCount > 0) {
            console.log(`Updated challenge: ${challenge.title}`);
            updated++;
          } else {
            console.log(`No changes needed for: ${challenge.title}`);
          }
        } else {
          // Insert new challenge
          const result = await challengesCollection.insertOne(challenge);
          console.log(`Added new challenge: ${challenge.title}`);
          inserted++;
        }
      } catch (err) {
        console.error(`Error processing challenge "${challenge.title}":`, err);
        errors++;
      }
    }

    // Summary
    console.log('\nSummary:');
    console.log(`- ${inserted} challenges inserted`);
    console.log(`- ${updated} challenges updated`);
    console.log(`- ${errors} errors encountered`);

    // Disconnect from database
    await mongoose.disconnect();
    console.log('Disconnected from MongoDB');

  } catch (error) {
    console.error('Error adding challenges:', error);
  }
};

// Run the function
addChallenges();
