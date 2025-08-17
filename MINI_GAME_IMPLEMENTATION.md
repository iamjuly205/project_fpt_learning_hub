# Mini-Game Implementation: Listen and Guess Musical Notes

This document provides an overview of the implementation of the "Listen and Guess Musical Notes" mini-game feature.

## Implementation Overview

The mini-game allows users to listen to audio of musical notes and guess which note is being played. The implementation includes:

1. A new mini-game card in the mini-games section
2. Backend support for the new mini-game type
3. Audio playback functionality in the mini-game modal
4. Translations for the new mini-game type

## Files Modified

1. `frontend/index.html` - Added a new mini-game card for "Listen and Guess Note"
2. `backend/app.py` - Added the new mini-game type with audio files
3. `frontend/script.js` - Updated translations for the new mini-game type

## Directory Structure

The implementation uses the following directory structure for audio files:

```
frontend/
└── assets/
    ├── audio/
    │   └── notes/
    │       ├── do.mp3
    │       ├── re.mp3
    │       ├── mi.mp3
    │       ├── fa.mp3
    │       ├── sol.mp3
    │       ├── la.mp3
    │       └── si.mp3
    └── images/
        └── games/
            └── listen-note-thumb.png
```

## Required Audio Files

You need to add the following MP3 files to the `frontend/assets/audio/notes/` directory:

1. `do.mp3` - Audio for the "Do" note
2. `re.mp3` - Audio for the "Re" note
3. `mi.mp3` - Audio for the "Mi" note
4. `fa.mp3` - Audio for the "Fa" note
5. `sol.mp3` - Audio for the "Sol" note
6. `la.mp3` - Audio for the "La" note
7. `si.mp3` - Audio for the "Si" note

You can find free musical note audio files online or record your own.

## Required Images

You need to add the following image to the `frontend/assets/images/games/` directory:

1. `listen-note-thumb.png` - Thumbnail for the "Listen and Guess Note" mini-game

## How It Works

1. The user clicks on the "Listen and Guess Note" mini-game card in the mini-games section
2. The mini-game modal opens with an audio player
3. The user listens to the audio of a musical note
4. The user enters their guess in the input field
5. The user clicks the "Submit" button to check their answer
6. If the answer is correct, the user earns points and the modal closes after a short delay
7. If the answer is incorrect, the user can try again

## Testing

To test the mini-game:

1. Start the backend server: `cd backend && python app.py`
2. Open the frontend in a web browser: `http://localhost:5001`
3. Log in to the application
4. Navigate to the mini-games section
5. Click on the "Listen and Guess Note" mini-game card
6. Test the mini-game functionality

## Notes

- The mini-game uses the existing mini-game infrastructure, so it inherits all the features of the other mini-games
- The audio player is only shown when the mini-game has an audio file
- The image container is only shown when the mini-game has an image file
- The mini-game supports both audio and image files, but the "Listen and Guess Note" mini-game only uses audio files
