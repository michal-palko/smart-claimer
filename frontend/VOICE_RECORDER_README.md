# Voice Recording Feature

This feature allows users to record their voice and automatically transcribe it to text using a Whisper API service. The transcribed text is then inserted into the "Popis" (Description) field.

## Features

- **One-click recording**: Start/stop recording with a single button
- **Real-time timer**: Shows recording duration
- **Visual feedback**: Button changes color and animations during recording
- **Transcription preview**: Shows transcribed text before inserting
- **Slovak language support**: Optimized for Slovak language transcription
- **Mobile responsive**: Works on both desktop and mobile devices
- **Dark mode support**: Adapts to dark theme if enabled
- **Error handling**: Comprehensive error messages and timeout handling

## Setup

### 1. Whisper API Service

Make sure you have the Whisper API service running. The voice recorder expects:

- **Development**: `http://localhost:3001/transcribe`
- **Docker**: `http://whisper-api:3001/transcribe`

### 2. API Endpoint

The API should accept POST requests with:
- `audio`: Audio file (WebM format preferred)
- `language`: Language code (optional, defaults to 'sk' for Slovak)
- `prompt`: Context prompt for better transcription (optional)

Expected response format:
```json
{
  "transcription": "transcribed text here"
}
```

### 3. Files Included

- `voiceRecorder.js` - Main JavaScript functionality
- `voiceRecorder.css` - Styling for the voice recorder widget
- `voice-recorder-test.html` - Test page for the voice recorder

### 4. Integration

The voice recorder is automatically initialized for the `popis` field when the page loads. It appears as a widget below the textarea.

## Usage

1. **Start Recording**: Click the "Nahrávať" (Record) button
2. **Grant Permissions**: Allow microphone access when prompted
3. **Record**: Speak clearly in Slovak (or your configured language)
4. **Stop Recording**: Click the "Zastaviť" (Stop) button
5. **Review**: Check the transcribed text in the preview
6. **Accept**: Click "Použiť text" to add to the description field
7. **Discard**: Click "Zahodiť" to discard the transcription

## Browser Support

- Chrome 47+
- Firefox 29+
- Safari 14+
- Edge 79+

Requires:
- `navigator.mediaDevices.getUserMedia()`
- `MediaRecorder` API
- Modern JavaScript (ES6+)

## Configuration

You can customize the voice recorder by modifying the initialization in `voiceRecorder.js`:

```javascript
new VoiceRecorder('popis', {
    apiUrl: 'http://localhost:3001/transcribe',
    language: 'sk',                    // Language code
    prompt: 'Technical work description',  // Context for better transcription
    maxRecordingTime: 300             // Max recording time in seconds (5 minutes)
});
```

## Testing

Use the `voice-recorder-test.html` file to test the voice recorder functionality:

1. Open `voice-recorder-test.html` in your browser
2. Make sure your Whisper API is running
3. Test recording and transcription
4. Verify the API endpoint is correct

## Troubleshooting

### Common Issues

1. **Microphone not working**
   - Check browser permissions
   - Ensure HTTPS is used (required for microphone access)
   - Try refreshing the page

2. **API connection failed**
   - Verify Whisper API is running on the correct port
   - Check CORS settings on the API server
   - Verify the API URL configuration

3. **Poor transcription quality**
   - Speak clearly and slowly
   - Reduce background noise
   - Adjust the `prompt` parameter for better context
   - Check microphone quality

4. **Browser compatibility**
   - Use a modern browser that supports MediaRecorder API
   - Enable JavaScript
   - Check console for error messages

### Error Messages

- "Váš prehliadač nepodporuje nahrávanie zvuku" - Browser doesn't support audio recording
- "Chyba pri prístupe k mikrofónu" - Microphone access denied or failed
- "Časový limit vypršal" - API request timeout (30 seconds)
- "Chyba siete" - Network connection problem
- "Prepis sa nepodaril" - Transcription failed or returned empty

## Security Notes

- Microphone access requires user permission
- Audio data is sent to the Whisper API service
- No audio data is stored locally in the browser
- Ensure your Whisper API service is secure and trusted

## Performance

- Maximum recording time: 5 minutes (configurable)
- Audio format: WebM with Opus codec (preferred)
- Fallback formats: WebM, MP4
- API timeout: 30 seconds
- File size: Approximately 1MB per minute of recording
