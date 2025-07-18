# AI Assistant Setup

The AI Assistant widget has been added to the time entry form. It provides intelligent suggestions for work descriptions based on JIRA task information.

## Features

- **Minimalistic Design**: Star icon (⭐) next to the voice recorder
- **Custom Prompts**: Users can write their own instructions for the AI
- **JIRA Integration**: Automatically includes JIRA task details and comments
- **Context Awareness**: Uses current description text as context
- **Slovak Language**: Full Slovak interface and AI communication

## Setup

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Environment Configuration
Add your OpenAI API key to the `.env` file:
```bash
OPENAI_API_KEY=sk-your-openai-api-key-here
```

### 3. Usage
1. Click the star icon (⭐) next to the voice recorder
2. Write custom instructions in the textarea
3. Click "Odoslať" to send to AI
4. Review the AI response
5. Use "Použiť text" to replace the description field
6. Or "Zahodiť" to discard the response
7. Or "Upraviť prompt" to edit and try again

## API Endpoints

- `POST /api/openai/chat` - Proxy to OpenAI API (handles CORS and API key)
- `GET /api/jira/{issue_key}` - Fetch JIRA issue details for AI context

## Default Prompt
```
Pomôž mi napísať lepší popis práce na základe poskytnutých informácií o JIRA úlohe a aktuálneho popisu. Buď konkrétny a technický.
```

## Model Configuration
- **Model**: `gpt-4o-mini`
- **Max Tokens**: 500
- **Temperature**: 0.7
- **Language**: Slovak

## Files Added/Modified

### Frontend
- `aiAssistant.js` - AI assistant widget functionality
- `aiAssistant.css` - Styling for AI assistant
- `index.html` - Updated to include AI assistant files

### Backend
- `main.py` - Added OpenAI proxy endpoint
- `requirements.txt` - Added httpx dependency
- `.env.example` - Added OpenAI API key configuration

## Security
- API key is stored securely in backend environment variables
- Frontend doesn't expose the OpenAI API key
- Backend acts as a proxy to handle CORS and authentication
