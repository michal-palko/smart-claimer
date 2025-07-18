// AI Assistant Widget for OpenAI GPT-4o-mini Integration
// Completely independent module from voice recorder

// Environment configuration helper for OpenAI API
async function getOpenAIConfig() {
    try {
        const response = await fetch('/api/config');
        if (response.ok) {
            const config = await response.json();
            return config.openai;
        }
    } catch (error) {
        console.warn('Failed to fetch OpenAI config from API, using defaults:', error);
    }
    
    // Fallback to defaults if API fails
    return {
        apiUrl: '/api/openai/chat', // Backend proxy endpoint
        model: 'gpt-4o-mini',
        maxTokens: 500,
        temperature: 0.7,
        defaultPrompt: 'Pomôž mi napísať lepší popis práce na základe poskytnutých informácií o JIRA úlohe a aktuálneho popisu.'
    };
}

class AIAssistant {
    constructor(targetFieldId, options = {}) {
        this.targetField = document.getElementById(targetFieldId);
        this.options = {
            // Default options that can be overridden
            ...options
        };
        
        this.isProcessing = false;
        this.currentResponse = null;
        this.customPrompt = null;
        this.configLoaded = false;
        
        this.init();
    }
    
    async init() {
        // Load configuration from backend
        await this.loadConfig();
        
        this.createWidget();
        this.attachEventListeners();
    }
    
    async loadConfig() {
        try {
            const config = await getOpenAIConfig();
            this.options = {
                apiUrl: this.options.apiUrl || config.apiUrl,
                model: this.options.model || config.model,
                maxTokens: this.options.maxTokens || config.maxTokens,
                temperature: this.options.temperature !== undefined ? this.options.temperature : config.temperature,
                defaultPrompt: this.options.defaultPrompt || config.defaultPrompt,
                ...this.options
            };
            this.customPrompt = this.customPrompt || this.options.defaultPrompt;
            this.configLoaded = true;
            console.log('OpenAI config loaded:', this.options);
        } catch (error) {
            console.error('Failed to load OpenAI config:', error);
            // Use fallback defaults
            const fallbackConfig = await getOpenAIConfig();
            this.options = {
                ...fallbackConfig,
                ...this.options
            };
            this.customPrompt = this.customPrompt || this.options.defaultPrompt;
            this.configLoaded = true;
        }
    }
    
    createWidget() {
        // Create the AI assistant widget container
        const widget = document.createElement('div');
        widget.className = 'ai-assistant-widget';
        widget.innerHTML = `
            <div class="ai-assistant-inline">
                <button type="button" class="ai-assistant-btn-mini" id="aiAssistantBtn" title="AI asistent">
                    <svg class="ai-icon-svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                    </svg>
                </button>
                <div class="ai-status-mini" id="aiStatus"></div>
            </div>
            <div class="ai-prompt-container" id="aiPromptContainer" style="display: none;">
                <div class="prompt-header">
                    <label for="aiPrompt">Inštrukcie pre AI:</label>
                    <button type="button" class="btn-close-prompt" id="closePromptBtn">×</button>
                </div>
                <textarea id="aiPrompt" class="ai-prompt-input" rows="3" placeholder="Napíš inštrukcie pre AI...">${this.customPrompt}</textarea>
                <div class="prompt-options">
                    <label class="checkbox-label">
                        <input type="checkbox" id="includeJiraInfo" checked> 
                        Zahrnúť informácie z JIRA úlohy
                    </label>
                </div>
                <div class="prompt-actions">
                    <button type="button" class="btn-send-ai">Odoslať</button>
                    <button type="button" class="btn-cancel-ai">Zrušiť</button>
                </div>
            </div>
            <div class="ai-result" id="aiResult" style="display: none;">
                <div class="result-text"></div>
                <div class="result-actions">
                    <button type="button" class="btn-accept-ai">Použiť text</button>
                    <button type="button" class="btn-discard-ai">Zahodiť</button>
                    <button type="button" class="btn-edit-prompt">Upraviť prompt</button>
                </div>
            </div>
        `;
        
        // Find the label for the target field and insert AI assistant inline
        const targetLabel = document.querySelector(`label[for="${this.targetField.id}"]`);
        if (targetLabel) {
            // Ensure label is flex container
            if (!targetLabel.style.display || targetLabel.style.display === 'block') {
                targetLabel.style.display = 'flex';
                targetLabel.style.alignItems = 'center';
                targetLabel.style.gap = '0.5rem';
            }
            targetLabel.appendChild(widget);
        } else {
            // Fallback: insert before the target field's parent wrapper
            const wrapper = this.targetField.closest('.mb-3') || this.targetField.parentNode;
            wrapper.parentNode.insertBefore(widget, wrapper);
        }
        
        // Store references to widget elements
        this.widget = widget;
        this.aiBtn = widget.querySelector('#aiAssistantBtn');
        this.status = widget.querySelector('#aiStatus');
        this.promptContainer = widget.querySelector('#aiPromptContainer');
        this.promptInput = widget.querySelector('#aiPrompt');
        this.resultContainer = widget.querySelector('#aiResult');
    }
    
    attachEventListeners() {
        this.aiBtn.addEventListener('click', () => this.togglePrompt());
        
        // Prompt container buttons
        this.widget.querySelector('.btn-close-prompt').addEventListener('click', () => this.hidePrompt());
        this.widget.querySelector('.btn-send-ai').addEventListener('click', () => this.sendToAI());
        this.widget.querySelector('.btn-cancel-ai').addEventListener('click', () => this.hidePrompt());
        
        // Result action buttons
        this.widget.querySelector('.btn-accept-ai').addEventListener('click', () => this.acceptResponse());
        this.widget.querySelector('.btn-discard-ai').addEventListener('click', () => this.discardResponse());
        this.widget.querySelector('.btn-edit-prompt').addEventListener('click', () => this.editPrompt());
        
        // Close popup when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.widget.contains(e.target)) {
                this.hidePrompt();
                this.hideAIResult();
            }
        });
    }
    
    togglePrompt() {
        if (this.isProcessing) return;
        
        if (this.promptContainer.style.display === 'none') {
            this.showPrompt();
        } else {
            this.hidePrompt();
        }
    }
    
    showPrompt() {
        this.promptContainer.style.display = 'block';
        this.resultContainer.style.display = 'none';
        this.promptInput.focus();
    }
    
    hidePrompt() {
        this.promptContainer.style.display = 'none';
    }
    
    editPrompt() {
        this.resultContainer.style.display = 'none';
        this.showPrompt();
    }
    
    async sendToAI() {
        const prompt = this.promptInput.value.trim();
        if (!prompt) {
            this.showError('Zadajte inštrukcie pre AI.');
            return;
        }
        
        // Wait for configuration to load if not already loaded
        if (!this.configLoaded) {
            this.showError('Načítavam konfiguráciu...');
            return;
        }
        
        this.customPrompt = prompt;
        this.isProcessing = true;
        this.updateUI();
        this.hidePrompt();
        
        try {
            // Get current description
            const currentDescription = this.targetField.value || '';
            
            // Check if JIRA information should be included
            const includeJiraInfo = this.widget.querySelector('#includeJiraInfo').checked;
            console.log('[AI Assistant] Include JIRA info:', includeJiraInfo);
            
            // Get JIRA information only if checkbox is checked
            const jiraInfo = includeJiraInfo ? await this.getJiraInformation() : null;
            if (!includeJiraInfo) {
                console.log('[AI Assistant] JIRA info excluded by user choice');
            }
            
            // Send to OpenAI API
            const response = await this.sendToOpenAI(prompt, currentDescription, jiraInfo);
            
            if (response && response.trim()) {
                this.showAIResult(response);
            } else {
                this.showError('AI nevrátila odpoveď. Skúste to znovu.');
            }
            
        } catch (error) {
            console.error('Error processing AI request:', error);
            this.showError('Chyba pri komunikácii s AI: ' + error.message);
        } finally {
            this.isProcessing = false;
            this.updateUI();
        }
    }
    
    async getJiraInformation() {
        try {
            // Get JIRA code using the same method as jiraWidget.js
            const jiraCode = this.extractJiraCode();
            if (!jiraCode) {
                console.log('[AI Assistant] No JIRA code found');
                return null;
            }
            
            console.log('[AI Assistant] Fetching JIRA info for:', jiraCode);
            
            // Use the same endpoint as the "i" button: /jira-issue-details/
            const response = await fetch(`/jira-issue-details/${jiraCode}`);
            
            if (response.ok) {
                const jiraDataText = await response.text();
                console.log('[AI Assistant] Raw JIRA JSON received:', jiraDataText);
                return jiraDataText; // Return raw JSON string instead of parsed object
            } else {
                console.warn('Could not fetch JIRA information, status:', response.status);
                return null;
            }
        } catch (error) {
            console.warn('Error fetching JIRA information:', error);
            return null;
        }
    }
    
    extractJiraCode() {
        // Use the same extraction method as jiraWidget.js
        const jiraField = document.getElementById('jira');
        if (!jiraField || !jiraField.value) {
            return null;
        }
        
        const fieldValue = jiraField.value.trim();
        // Extract just the JIRA code (e.g., "CARTV-123" from "CARTV-123: Some description")
        // This is the same pattern used by the "i" button
        const match = fieldValue.match(/^([A-Z]+-\d+)/);
        return match ? match[1] : null;
    }
    
    async sendToOpenAI(prompt, description, jiraInfo) {
        const requestBody = {
            model: this.options.model,
            messages: [
                {
                    role: 'system',
                    content: `Si AI asistent, ktorý pomáha s písaním popisov práce. Komunikuj v slovenčine. ${prompt}`
                },
                {
                    role: 'user',
                    content: this.buildUserMessage(description, jiraInfo)
                }
            ],
            max_tokens: this.options.maxTokens,
            temperature: this.options.temperature
        };
        
        try {
            const response = await fetch(this.options.apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody),
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
            return result.choices?.[0]?.message?.content || result.content || '';
            
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error('Časový limit vypršal. Skúste to znovu.');
            } else if (error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
                throw new Error('Chyba siete. Skontrolujte pripojenie k OpenAI API.');
            } else {
                throw error;
            }
        }
    }
    
    buildUserMessage(description, jiraInfo) {
        let message = `Aktuálny popis práce:\n"${description || 'Žiadny popis'}"`;
        
        if (jiraInfo) {
            console.log('[AI Assistant] Adding raw JIRA JSON to message');
            message += `\n\nInformácie o JIRA úlohe (raw JSON):\n${jiraInfo}`;
        } else {
            console.log('[AI Assistant] No JIRA info available');
        }
        
        console.log('[AI Assistant] Final message length:', message.length);
        return message;
    }
    
    showAIResult(text) {
        this.resultContainer.querySelector('.result-text').textContent = text;
        this.resultContainer.style.display = 'block';
        this.currentResponse = text;
    }
    
    acceptResponse() {
        if (this.currentResponse) {
            // Replace the content of the target field with AI response
            this.targetField.value = this.currentResponse;
            
            // Trigger input event to update any counters or validators
            this.targetField.dispatchEvent(new Event('input', { bubbles: true }));
            
            this.hideAIResult();
        }
    }
    
    discardResponse() {
        this.hideAIResult();
    }
    
    hideAIResult() {
        this.resultContainer.style.display = 'none';
        this.currentResponse = null;
    }
    
    updateUI() {
        if (this.isProcessing) {
            this.aiBtn.classList.add('processing');
            this.status.textContent = 'AI pracuje...';
            this.status.style.display = 'inline';
        } else {
            this.aiBtn.classList.remove('processing');
            this.status.textContent = '';
            this.status.style.display = 'none';
        }
        
        this.aiBtn.disabled = this.isProcessing;
    }
    
    showError(message) {
        this.status.textContent = message;
        this.status.className = 'ai-status-mini error';
        
        // Clear error after 5 seconds
        setTimeout(() => {
            if (this.status.className.includes('error')) {
                this.status.textContent = '';
                this.status.className = 'ai-status-mini';
            }
        }, 5000);
    }
    
    destroy() {
        if (this.widget) {
            this.widget.remove();
        }
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    // Initialize AI assistant for the popis field
    const opisField = document.getElementById('popis');
    if (opisField) {
        // Create AIAssistant instance (configuration will be loaded asynchronously)
        new AIAssistant('popis');
    }
});
