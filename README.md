# SmartClaimer - Time Entry System

Time tracking application with JIRA integration and MetaApp database submission.

## Quick Start

### 1. Setup Environment

```bash
# Clone and navigate to project
git clone https://github.com/michal-palko/smart-claimer.git
cd smartclaimer

# Copy environment file
cp backend/.env.example backend/.env
```

### 2. Configure JIRA (Required)

Edit `backend/.env`:
```bash
JIRA_URL=https://your-company.atlassian.net
JIRA_USER=your-email@company.com
JIRA_TOKEN=your_jira_api_token
```

**Get JIRA Token**: https://id.atlassian.com/manage-profile/security/api-tokens

### 3. Configure MetaApp Database (Required for submission)

```bash
METAAPP_DB_HOST=your-metaapp-host
METAAPP_DB_USER=your-username
METAAPP_DB_PASSWORD=your-password
```

### 4. Start Application

```bash
# Start entire stack
docker compose up --build

# Access points:
# Frontend: http://localhost:8003/frontend/index.html#
```

## Optional Features

### AI Description Enhancement
```bash
OPENAI_API_KEY=sk-your-openai-key
```

### Voice Transcription
Requires separate Whisper server running on port 3001. Not shared yet. 
