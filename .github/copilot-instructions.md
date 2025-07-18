# SmartClaimer - Time Entry System Instructions

## Architecture Overview

This is a **time tracking application** with a FastAPI backend, vanilla JavaScript frontend, and PostgreSQL database. The system integrates with JIRA for task metadata and supports voice transcription via Whisper API.

### Core Components
- **Backend**: FastAPI (`backend/app/main.py`) with SQLAlchemy models (`models.py`)
- **Frontend**: Single-page vanilla JS app (`frontend/main.js`) with Bootstrap 5 UI
- **Database**: PostgreSQL with dual connections (local + external MetaApp)
- **External APIs**: JIRA REST API, Whisper transcription, OpenAI chat

## Development Workflow

### Local Development
```bash
# Start entire stack
docker compose up --build

# Backend only (for API changes)
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend only (for UI changes) 
cd frontend && python -m http.server 8080
```

**Access Points:**
- Frontend: http://localhost:8080/index.html
- API docs: http://localhost:8000/docs
- Database: localhost:55432 (postgres/postgres/postgres)

### Cache Invalidation
When making backend changes, use `docker compose up --build --no-cache` to force rebuild - Docker layer caching can prevent code updates from taking effect.

## Project-Specific Patterns

### Data Flow & State Management
- **JIRA Integration**: Autocomplete fields (`uloha`, `jira`) fetch from `/jira-issues` with 30-min localStorage cache
- **Form State**: Uses `dataset.code` to store actual JIRA keys while displaying human-readable labels
- **Entry Management**: All entries loaded into `allEntries` array, filtered for display in `filteredEntries`

### Frontend Architecture
```javascript
// Key pattern: Dual-database approach
form.uloha.value = "PROJ-123: Task Summary"  // Display
form.uloha.dataset.code = "PROJ-123"         // Actual code sent to API

// Critical: JIRA metadata enrichment happens on both form submit and edit
const jiraIssue = issues.find(i => i.key === jiraCode);
data.jira_name = jiraIssue ? jiraIssue.summary : undefined;
```

### Custom Form Behaviors
- **Time Input**: Supports decimal hours (2.5 → 2h 30m), smart parsing ("90min" → 1h 30m)
- **Date Picker**: Force light theme with aggressive CSS overrides in `style.css`
- **Autocomplete**: Custom keyboard navigation (Arrow keys, Tab, Enter) with highlighted selections
- **Templates**: User-defined form presets stored per author

### Database Integration Patterns
```python
# Dual database pattern - local + external MetaApp
from .database import SessionLocal        # Local PostgreSQL
from .metaapp_db import MetaAppSession    # External PostgreSQL

# MetaApp submission via stored procedure
result = session.execute(
    text("SELECT metaapp_metaapp_crm.insert_vykaz_entry(...)"),
    {...}
)
```

## Critical Configuration

### Environment Variables (.env)
```bash
# JIRA (required for autocomplete)
JIRA_URL=https://company.atlassian.net
JIRA_USER=email@company.com
JIRA_TOKEN=api_token

# MetaApp Database (required for submission)
METAAPP_DB_HOST=hostname
METAAPP_DB_USER=username
METAAPP_DB_PASSWORD=password

# Optional AI features
OPENAI_API_KEY=sk-...
WHISPER_API_URL=http://whisper-api:3001/transcribe
```

### Widget Integration
The app uses **modular widgets** (`aiAssistant.js`, `voiceRecorder.js`, `jiraWidget.js`) that auto-attach to form elements. Each widget has its own CSS file and README.

## Common Gotchas

1. **Form Reset Behavior**: Multiple `addEventListener('reset')` handlers set default values - always include `form.hodiny.value = '0'; form.minuty.value = '0';`

2. **JIRA Cache Management**: Use `jiraIssuesCache = []; jiraIssuesLoadedFor = '';` to force refresh when JIRA data seems stale

3. **MetaApp Submission**: Entries show green border when `metaapp_vykaz_id` is not null - this indicates successful submission

4. **Author Permission Model**: Users can only edit/delete their own entries (`entry.autor === form.autor.value.trim()`)

5. **Date Validation**: Shows confirmation dialogs for dates outside current/previous month range

## Key Files to Understand
- `frontend/main.js` (1500+ lines) - Core application logic
- `backend/app/main.py` - API endpoints and business logic  
- `backend/app/jira.py` - JIRA integration with LRU caching
- `backend/sql/001_init.sql` - Database schema
- `docker-compose.yml` - Full stack orchestration
