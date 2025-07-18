// Voice Recording Widget for Whisper API Integration
// AI Assistant Widget for OpenAI GPT-4o-mini Integration

// Environment configuration helper
async function getWhisperConfig() {
    try {
        const response = await fetch('/api/config');
        if (response.ok) {
            const config = await response.json();
            return config.whisper;
        }
    } catch (error) {
        console.warn('Failed to fetch Whisper config from API, using defaults:', error);
    }
    
    // Fallback to environment-based detection if API fails
    return {
        apiUrl: getWhisperApiUrl(),
        language: 'sk',
        prompt: 'Popis práce, technické úlohy, programovanie v softverovej a datovej firme.',
        temperature: 0.2,
        maxRecordingTime: 300
    };
}

function getWhisperApiUrl() {
    // Check if we're in development (localhost)
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return 'http://localhost:3001/transcribe';
    }
    
    // Check if we're running in Docker with service name
    if (window.location.hostname.includes('docker') || window.location.hostname === 'web') {
        return 'http://whisper-api:3001/transcribe';
    }
    
    // For production, use environment variable or default
    return process.env.WHISPER_API_URL || 'http://whisper-api:3001/transcribe';
}

// Environment configuration helper for OpenAI API
function getOpenAIApiUrl() {
    // Check if we're in development (localhost)
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return 'http://localhost:3001/openai';
    }
    
    // Check if we're running in Docker with service name
    if (window.location.hostname.includes('docker') || window.location.hostname === 'web') {
        return 'http://whisper-api:3001/openai';
    }
    
    // For production, use environment variable or default
    return process.env.OPENAI_API_URL || 'http://whisper-api:3001/openai';
}

class VoiceRecorder {
    constructor(targetFieldId, options = {}) {
        this.targetField = document.getElementById(targetFieldId);
        this.options = {
            // Default options that can be overridden
            ...options
        };
        
        this.isRecording = false;
        this.isProcessing = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.recordingTime = 0;
        this.timerInterval = null;
        this.stream = null;
        this.configLoaded = false;
        
        this.init();
    }
    
    async init() {
        // Load configuration from backend
        await this.loadConfig();
        
        // Check browser compatibility
        if (!this.checkBrowserSupport()) {
            this.showError('Váš prehliadač nepodporuje nahrávanie zvuku.');
            return;
        }
        
        this.createWidget();
        this.attachEventListeners();
    }
    
    async loadConfig() {
        try {
            const config = await getWhisperConfig();
            this.options = {
                apiUrl: this.options.apiUrl || config.apiUrl,
                language: this.options.language || config.language,
                prompt: this.options.prompt || config.prompt,
                temperature: this.options.temperature !== undefined ? this.options.temperature : config.temperature,
                maxRecordingTime: this.options.maxRecordingTime || config.maxRecordingTime,
                ...this.options
            };
            this.configLoaded = true;
            console.log('Whisper config loaded:', this.options);
        } catch (error) {
            console.error('Failed to load Whisper config:', error);
            // Use fallback defaults
            this.options = {
                apiUrl: getWhisperApiUrl(),
                language: 'sk',
                prompt: 'Popis práce, technické úlohy, programovanie v softverovej a datovej firme.',
                temperature: 0.2,
                maxRecordingTime: 300,
                ...this.options
            };
            this.configLoaded = true;
        }
    }
    
    checkBrowserSupport() {
        return !!(navigator.mediaDevices && 
                 navigator.mediaDevices.getUserMedia && 
                 window.MediaRecorder);
    }
    
    createWidget() {
        // Create the voice recording widget container
        const widget = document.createElement('div');
        widget.className = 'voice-recorder-widget';
        widget.innerHTML = `
            <div class="voice-recorder-inline">
                <button type="button" class="voice-recorder-btn-mini" id="voiceRecorderBtn" title="Nahrávať hlas">
                    <svg class="mic-icon-svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
                        <path d="M19 10v1a7 7 0 0 1-14 0v-1"/>
                        <path d="M12 18v4m-4 0h8"/>
                    </svg>
                </button>
                <div class="recording-timer-mini" id="recordingTimer" style="display: none;">
                    <span class="timer-text">00:00</span>
                </div>
                <div class="recording-status-mini" id="recordingStatus"></div>
            </div>
            <div class="transcription-result" id="transcriptionResult" style="display: none;">
                <div class="result-text"></div>
                <div class="result-actions">
                    <button type="button" class="btn-accept">Použiť text</button>
                    <button type="button" class="btn-discard">Zahodiť</button>
                </div>
            </div>
        `;
        
        // Find the label for the target field and insert the mini recorder inline
        const targetLabel = document.querySelector(`label[for="${this.targetField.id}"]`);
        if (targetLabel) {
            targetLabel.style.display = 'flex';
            targetLabel.style.alignItems = 'center';
            targetLabel.style.gap = '0.5rem';
            targetLabel.appendChild(widget);
        } else {
            // Fallback: insert before the target field's parent wrapper
            const wrapper = this.targetField.closest('.mb-3') || this.targetField.parentNode;
            wrapper.parentNode.insertBefore(widget, wrapper);
        }
        
        // Store references to widget elements
        this.widget = widget;
        this.recordBtn = widget.querySelector('#voiceRecorderBtn');
        this.timer = widget.querySelector('#recordingTimer');
        this.status = widget.querySelector('#recordingStatus');
        this.resultContainer = widget.querySelector('#transcriptionResult');
    }
    
    attachEventListeners() {
        this.recordBtn.addEventListener('click', () => this.toggleRecording());
        
        // Result action buttons
        this.widget.querySelector('.btn-accept').addEventListener('click', () => this.acceptTranscription());
        this.widget.querySelector('.btn-discard').addEventListener('click', () => this.discardTranscription());
    }
    
    async toggleRecording() {
        if (this.isProcessing) return;
        
        // Wait for configuration to load if not already loaded
        if (!this.configLoaded) {
            this.showError('Načítavam konfiguráciu...');
            return;
        }
        
        if (this.isRecording) {
            this.stopRecording();
        } else {
            await this.startRecording();
        }
    }
    
    async startRecording() {
        try {
            // Request microphone access
            this.stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 44100
                } 
            });
            
            // Initialize MediaRecorder
            const options = { mimeType: 'audio/webm;codecs=opus' };
            if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                options.mimeType = 'audio/webm';
            }
            if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                options.mimeType = 'audio/mp4';
            }
            if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                options.mimeType = '';
            }
            
            this.mediaRecorder = new MediaRecorder(this.stream, options);
            this.audioChunks = [];
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            this.mediaRecorder.onstop = () => {
                this.processAudio();
            };
            
            // Start recording
            this.mediaRecorder.start();
            this.isRecording = true;
            this.recordingTime = 0;
            
            this.updateUI();
            this.startTimer();
            
        } catch (error) {
            console.error('Error starting recording:', error);
            this.showError('Chyba pri prístupe k mikrofónu. Skontrolujte povolenia.');
        }
    }
    
    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
            this.stopTimer();
            
            // Stop all tracks
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
            }
            
            this.updateUI();
        }
    }
    
    startTimer() {
        this.timerInterval = setInterval(() => {
            this.recordingTime++;
            this.updateTimer();
            
            // Auto-stop at max recording time
            if (this.recordingTime >= this.options.maxRecordingTime) {
                this.stopRecording();
            }
        }, 1000);
    }
    
    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }
    
    updateTimer() {
        const minutes = Math.floor(this.recordingTime / 60);
        const seconds = this.recordingTime % 60;
        const timeString = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        this.timer.querySelector('.timer-text').textContent = timeString;
    }
    
    updateUI() {
        if (this.isRecording) {
            this.recordBtn.classList.add('recording');
            this.timer.style.display = 'inline-flex';
            this.status.textContent = 'Nahrávam...';
            this.status.style.display = 'inline';
        } else if (this.isProcessing) {
            this.recordBtn.classList.remove('recording');
            this.recordBtn.classList.add('processing');
            this.timer.style.display = 'none';
            this.status.textContent = 'Spracúvam...';
            this.status.style.display = 'inline';
        } else {
            this.recordBtn.classList.remove('recording', 'processing');
            this.timer.style.display = 'none';
            this.status.textContent = '';
            this.status.style.display = 'none';
        }
        
        this.recordBtn.disabled = this.isProcessing;
    }
    
    async processAudio() {
        if (this.audioChunks.length === 0) {
            this.showError('Žiadne audio dáta na spracovanie.');
            return;
        }
        
        this.isProcessing = true;
        this.updateUI();
        
        try {
            // Create audio blob
            const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
            
            // Send to Whisper API
            const transcription = await this.sendToWhisperAPI(audioBlob);
            
            if (transcription && transcription.trim()) {
                this.showTranscriptionResult(transcription);
            } else {
                this.showError('Prepis sa nepodaril. Skúste to znovu.');
            }
            
        } catch (error) {
            console.error('Error processing audio:', error);
            this.showError('Chyba pri spracovaní zvuku: ' + error.message);
        } finally {
            this.isProcessing = false;
            this.updateUI();
        }
    }
    
    async sendToWhisperAPI(audioBlob) {
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');
        
        if (this.options.language) {
            formData.append('language', this.options.language);
        }
        
        if (this.options.prompt) {
            formData.append('prompt', this.options.prompt);
        }
        
        if (this.options.temperature !== undefined) {
            formData.append('temperature', this.options.temperature.toString());
        }
        
        try {
            const response = await fetch(this.options.apiUrl, {
                method: 'POST',
                body: formData,
                // Add timeout handling
                signal: AbortSignal.timeout(30000) // 30 second timeout
            });
            
            if (!response.ok) {
                let errorMessage = `HTTP ${response.status}`;
                try {
                    const errorText = await response.text();
                    if (errorText) {
                        errorMessage += `: ${errorText}`;
                    }
                } catch (e) {
                    // Ignore error reading response body
                }
                throw new Error(errorMessage);
            }
            
            const result = await response.json();
            return result.transcription || result.text || result.transcript || '';
            
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error('Časový limit vypršal. Skúste kratšie nahrávanie.');
            } else if (error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
                throw new Error('Chyba siete. Skontrolujte pripojenie k Whisper API.');
            } else {
                throw error;
            }
        }
    }
    
    showTranscriptionResult(text) {
        this.resultContainer.querySelector('.result-text').textContent = text;
        this.resultContainer.style.display = 'block';
        this.currentTranscription = text;
    }
    
    acceptTranscription() {
        if (this.currentTranscription) {
            // Add transcription to the target field
            const currentValue = this.targetField.value;
            const newValue = currentValue ? currentValue + ' ' + this.currentTranscription : this.currentTranscription;
            this.targetField.value = newValue;
            
            // Trigger input event to update any counters or validators
            this.targetField.dispatchEvent(new Event('input', { bubbles: true }));
            
            this.hideTranscriptionResult();
        }
    }
    
    discardTranscription() {
        this.hideTranscriptionResult();
    }
    
    hideTranscriptionResult() {
        this.resultContainer.style.display = 'none';
        this.currentTranscription = null;
    }
    
    showError(message) {
        this.status.textContent = message;
        this.status.className = 'recording-status error';
        
        // Clear error after 5 seconds
        setTimeout(() => {
            if (this.status.className.includes('error')) {
                this.status.textContent = '';
                this.status.className = 'recording-status';
            }
        }, 5000);
    }
    
    destroy() {
        this.stopRecording();
        if (this.widget) {
            this.widget.remove();
        }
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    // Initialize voice recorder for the popis field
    const opisField = document.getElementById('popis');
    if (opisField) {
        // Create VoiceRecorder instance (configuration will be loaded asynchronously)
        new VoiceRecorder('popis');
    }
});
