from fastapi import FastAPI, Depends, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.sql import text
from typing import List, Optional
from datetime import date
import os
import httpx
import json
import time

from . import models, schemas, database
from .jira import fetch_jira_issues_for_author, fetch_jira_issue_by_key, get_issue_details
from .metaapp_db import MetaAppSession

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

# Serve static frontend only at /frontend
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "frontend")
app.mount("/frontend", StaticFiles(directory=frontend_path, html=True), name="frontend")

# Redirect root to /frontend/index.html
@app.get("/")
def root():
    return RedirectResponse(url="/frontend/index.html")

@app.get("/api/config")
def get_config():
    """Get frontend configuration from environment variables"""
    return {
        "whisper": {
            "apiUrl": os.getenv("WHISPER_API_URL", "http://whisper-api:3001/transcribe"),
            "language": os.getenv("WHISPER_LANGUAGE", "sk"),
            "prompt": os.getenv("WHISPER_PROMPT", "Popis práce, technické úlohy, programovanie v softverovej a datovej firme."),
            "temperature": float(os.getenv("WHISPER_TEMPERATURE", "0.2")),
            "maxRecordingTime": int(os.getenv("WHISPER_MAX_RECORDING_TIME", "300"))
        },
        "openai": {
            "apiUrl": "/api/openai/chat",  # Always use backend proxy
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "maxTokens": int(os.getenv("OPENAI_MAX_TOKENS", "500")),
            "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
            "defaultPrompt": os.getenv("OPENAI_DEFAULT_PROMPT", "Pomôž mi napísať lepší popis práce na základe poskytnutých informácií o JIRA úlohe a aktuálneho popisu. Buď konkrétny a technický.")
        }
    }

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

import time

@app.post("/time-entries", response_model=schemas.TimeEntryResponse)
def create_time_entry(entry: schemas.TimeEntryCreate, db: Session = Depends(get_db)):
    start_time = time.time()
    print(f"\n[TimeEntry] Starting creation for autor={entry.autor}, jira={entry.jira}, uloha={entry.uloha}")
    
    # Validation
    validation_start = time.time()
    if entry.hodiny < 0 or not (0 <= entry.minuty <= 59):
        raise HTTPException(status_code=400, detail="Invalid time values.")
    print(f"[TimeEntry] Validation took {(time.time() - validation_start)*1000:.1f}ms")
    
    # Initialize metadata
    jira_name = entry.jira_name
    uloha_name = entry.uloha_name
    
    # Check if we need to fetch JIRA metadata
    if entry.jira or entry.uloha:
        metadata_start = time.time()
        metadata_source = "frontend" if jira_name or uloha_name else "backend"
        print(f"[TimeEntry] Using {metadata_source} metadata")
        
        if not (jira_name and uloha_name):  # Only fetch if we don't have both names
            try:
                # For JIRA metadata lookup, first try the broader search for specific keys
                if entry.jira and not jira_name:
                    print(f"[TimeEntry] Looking up JIRA key: {entry.jira}")
                    jira_lookup_start = time.time()
                    issue = fetch_jira_issue_by_key(entry.jira)
                    if issue:
                        jira_name = issue.get('summary', '')
                        uloha_name = issue.get('parent_summary', '') or uloha_name
                        print(f"[TimeEntry] Found JIRA issue: {entry.jira} -> '{jira_name}' (took {(time.time() - jira_lookup_start)*1000:.1f}ms)")
                    else:
                        print(f"[TimeEntry] JIRA key {entry.jira} not found")
                
                # For uloha, also try broader search if still needed
                if entry.uloha and not uloha_name:
                    print(f"[TimeEntry] Looking up Uloha key: {entry.uloha}")
                    uloha_lookup_start = time.time()
                    parent_issue = fetch_jira_issue_by_key(entry.uloha)
                    if parent_issue:
                        uloha_name = parent_issue.get('summary', '')
                        print(f"[TimeEntry] Found Uloha: {entry.uloha} -> '{uloha_name}' (took {(time.time() - uloha_lookup_start)*1000:.1f}ms)")
                    else:
                        print(f"[TimeEntry] Uloha key {entry.uloha} not found")
                        
            except Exception as e:
                print(f"[TimeEntry] Error fetching JIRA data: {str(e)}")
        print(f"[TimeEntry] Metadata processing took {(time.time() - metadata_start)*1000:.1f}ms")
    # Database operations
    db_start = time.time()
    print(f"[TimeEntry] Starting database operations")
    
    db_entry = models.TimeEntry(
        uloha=entry.uloha,
        autor=entry.autor,
        datum=entry.datum,
        hodiny=entry.hodiny,
        minuty=entry.minuty,
        jira=entry.jira,
        popis=entry.popis,
        jira_name=jira_name,
        uloha_name=uloha_name
    )
    
    db.add(db_entry)
    commit_start = time.time()
    db.commit()
    db.refresh(db_entry)
    print(f"[TimeEntry] Database commit took {(time.time() - commit_start)*1000:.1f}ms")
    print(f"[TimeEntry] Total database operations took {(time.time() - db_start)*1000:.1f}ms")
    
    total_time = (time.time() - start_time) * 1000
    print(f"[TimeEntry] Entry creation completed in {total_time:.1f}ms")
    
    return db_entry

@app.get("/time-entries", response_model=List[schemas.TimeEntryResponse])
def list_time_entries(
    db: Session = Depends(get_db),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to")
):
    query = db.query(models.TimeEntry)
    if from_date:
        query = query.filter(models.TimeEntry.datum >= from_date)
    if to_date:
        query = query.filter(models.TimeEntry.datum <= to_date)
    return query.order_by(models.TimeEntry.datum.desc(), models.TimeEntry.id.desc()).all()

@app.delete("/time-entries/{entry_id}")
def delete_time_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.query(models.TimeEntry).filter(models.TimeEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
    return {"ok": True}

@app.put("/time-entries/{entry_id}", response_model=schemas.TimeEntryResponse)
def update_time_entry(entry_id: int, entry: schemas.TimeEntryCreate = Body(...), db: Session = Depends(get_db)):
    db_entry = db.query(models.TimeEntry).filter(models.TimeEntry.id == entry_id).first()
    if not db_entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    # Try to populate jira_name and uloha_name from JIRA issues if not provided
    jira_name = entry.jira_name
    uloha_name = entry.uloha_name
    if entry.jira or entry.uloha:
        try:
            issues = fetch_jira_issues_for_author(entry.autor)
            if entry.jira:
                issue = next((i for i in issues if i.get('key') == entry.jira), None)
                if issue:
                    jira_name = issue.get('summary', '')
                    uloha_name = issue.get('parent_summary', '') or uloha_name
            if entry.uloha and not uloha_name:
                parent_issue = next((i for i in issues if i.get('key') == entry.uloha), None)
                if parent_issue:
                    uloha_name = parent_issue.get('summary', '')
        except Exception:
            pass
    db_entry.uloha = entry.uloha
    db_entry.datum = entry.datum
    db_entry.hodiny = entry.hodiny
    db_entry.minuty = entry.minuty
    db_entry.jira = entry.jira
    db_entry.popis = entry.popis
    db_entry.jira_name = jira_name
    db_entry.uloha_name = uloha_name
    db.commit()
    db.refresh(db_entry)
    return db_entry

@app.post("/templates", response_model=schemas.TemplateResponse)
def create_template(template: schemas.TemplateCreate, db: Session = Depends(get_db)):
    db_template = models.Template(**template.dict())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

@app.get("/templates", response_model=List[schemas.TemplateResponse])
def list_templates(autor: str = Query(...), db: Session = Depends(get_db)):
    return db.query(models.Template).filter(models.Template.autor == autor).all()

@app.delete("/templates/{template_id}")
def delete_template(template_id: int, autor: str = Query(...), db: Session = Depends(get_db)):
    template = db.query(models.Template).filter(models.Template.id == template_id, models.Template.autor == autor).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(template)
    db.commit()
    return {"ok": True}

@app.get("/jira-issues", response_model=List[schemas.JiraIssue])
def get_jira_issues(autor: str = Query(...)):
    try:
        return fetch_jira_issues_for_author(autor)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JIRA fetch failed: {e}")

@app.get("/api/validate-jira")
def validate_jira_key(key: str = Query(...)):
    """Validate if a JIRA key exists using broader search"""
    try:
        issue = fetch_jira_issue_by_key(key)
        return {"valid": issue is not None, "issue": issue}
    except Exception as e:
        return {"valid": False, "error": str(e)}

@app.get("/metaapp-tasks")
def get_metaapp_tasks(autor: str = Query(...)):
    """Fetch tasks from MetaApp database for a specific user"""
    try:
        with MetaAppSession() as session:
            result = session.execute(
                text("""
                SELECT 
                    u.znacky, 
                    u.nazov, 
                    a.login
                FROM metaapp_metaapp_crm.dale_uloha_riesitel r
                    LEFT JOIN metaapp_metaapp_crm.uloha u ON 
                        r.fk3033 = u.id
                    LEFT JOIN metaapp_metaapp_crm.app_user a ON 
                        COALESCE(r.fk3040, r.fk3062) = a.userid
                WHERE r.validto IS NULL
                    AND a.login = :login
                GROUP BY 
                    u.znacky,
                    u.nazov,
                    a.login
                ORDER BY u.znacky
                """),
                {"login": autor}
            )
            
            tasks = []
            for row in result:
                tasks.append({
                    "code": row[0],  # u.znacky
                    "summary": row[1],  # u.nazov
                    "login": row[2]  # a.login
                })
            
            return tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MetaApp fetch failed: {e}")

@app.post("/time-entries/{entry_id}/submit-to-metaapp", response_model=schemas.TimeEntryResponse)
def submit_time_entry_to_metaapp(entry_id: int, db: Session = Depends(get_db)):
    """Submit a time entry to MetaApp database"""
    from .metaapp_db import submit_to_metaapp
    
    # Get the entry
    entry = db.query(models.TimeEntry).filter(models.TimeEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Don't resubmit if already submitted
    if entry.metaapp_vykaz_id:
        return entry
        
    try:
        # Submit to MetaApp
        vykaz_id = submit_to_metaapp(entry)
        
        # Update local entry with MetaApp vykaz_id and submission timestamp
        entry.metaapp_vykaz_id = vykaz_id
        entry.submitted_to_metaapp_at = func.now()
        db.commit()
        db.refresh(entry)
        return entry
        
    except Exception as e:
        error_message = str(e)
        if "User with login" in error_message:
            raise HTTPException(status_code=400, detail=f"MetaApp Error: {error_message}")
        elif "No uloha found for epic tag" in error_message:
            raise HTTPException(status_code=400, detail=f"MetaApp Error: {error_message}")
        else:
            raise HTTPException(status_code=500, detail=f"MetaApp Error: {error_message}")

@app.get("/jira-issue-details/{issue_key}")
async def get_jira_issue_details(issue_key: str):
    """Fetch detailed information about a JIRA issue."""
    if not issue_key:
        raise HTTPException(status_code=400, detail="Issue key is required")
    
    issue_data = get_issue_details(issue_key)
    if not issue_data:
        raise HTTPException(status_code=404, detail=f"Issue {issue_key} not found or error occurred")
    
    return issue_data

@app.post("/api/openai/chat")
async def openai_chat_proxy(request_data: dict):
    """Proxy endpoint for OpenAI Chat API to handle CORS and API key security."""
    
    # Get OpenAI API key from environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    # Prepare headers for OpenAI API
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }
    
    try:
        # Forward request to OpenAI API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=request_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                # Return error details from OpenAI
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"error": response.text}
                raise HTTPException(status_code=response.status_code, detail=error_data)
                
    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="OpenAI API request timed out")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to OpenAI API: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(e)}")

@app.get("/api/jira/{issue_key}")
async def get_jira_issue_for_ai(issue_key: str):
    """Fetch detailed JIRA issue information for AI assistant."""
    if not issue_key:
        raise HTTPException(status_code=400, detail="Issue key is required")
    
    issue_data = get_issue_details(issue_key)
    if not issue_data:
        raise HTTPException(status_code=404, detail=f"Issue {issue_key} not found or error occurred")
    
    return issue_data

@app.post("/import-from-metaapp")
def import_from_metaapp(request: dict = Body(...), db: Session = Depends(get_db)):
    """Import time entries from MetaApp database for a specific author."""
    autor = request.get("autor")
    if not autor:
        raise HTTPException(status_code=400, detail="Autor je povinný")
    
    start_time = time.time()
    print(f"[Import] Starting import for author: {autor}")
    
    try:
        # Query MetaApp database
        query = text("""
                     
        SELECT
            a.id AS vykaz_id,
            a.login AS autor,
            a.datum,
            a.hodiny,
            a.minuty,
            a.jira,
            a.poznamka AS popis,
            b.znacky AS uloha
            FROM
            (
                SELECT
                    vykaz.id,
                    app_user.login,
                    vykaz.datum,
                    vykaz.hodiny,
                    vykaz.minuty,
                    vykaz.jira,
                    vykaz.poznamka
                FROM
                    metaapp_metaapp_crm.vykaz vykaz
                    CROSS JOIN metaapp_metaapp_crm.dale dale
                    CROSS JOIN metaapp_metaapp_crm.app_user app_user
                WHERE
                    app_user.userid = dale.fk3040
                    AND dale.fk3038 = vykaz.id
                    AND vykaz.validto IS NULL
                    AND app_user.validto IS NULL
                    AND dale.validto IS NULL
            ) a
            LEFT JOIN (
                SELECT
                    uloha.id uloha_id,
                    uloha.znacky, 
                    vykaz.id vykaz_id
                FROM
                    metaapp_metaapp_crm.vykaz vykaz
                    CROSS JOIN metaapp_metaapp_crm.dale dale
                    CROSS JOIN metaapp_metaapp_crm.uloha uloha
                WHERE
                    uloha.id = dale.fk3033
                    AND dale.fk3038 = vykaz.id
                    AND vykaz.validto IS NULL
                    AND uloha.validto IS NULL
                    AND dale.validto IS NULL
            ) b ON a.id = b.vykaz_id
            WHERE a.login = :autor
            ORDER BY datum DESC 
            LIMIT 100
        """)
        print(query)
        with MetaAppSession() as metaapp_session:
            result = metaapp_session.execute(query, {"autor": autor})
            metaapp_entries = result.fetchall()
        
        print(f"[Import] Found {len(metaapp_entries)} entries in MetaApp")
        
        # Get existing entries with metaapp_vykaz_id to avoid duplicates
        existing_vykaz_ids = {
            row[0] for row in db.query(models.TimeEntry.metaapp_vykaz_id)
            .filter(models.TimeEntry.metaapp_vykaz_id.isnot(None))
            .filter(models.TimeEntry.autor == autor)
            .all()
        }
        
        print(f"[Import] Found {len(existing_vykaz_ids)} existing entries with vykaz_id")
        
        imported_count = 0
        skipped_count = 0
        
        for entry in metaapp_entries:
            vykaz_id = entry.vykaz_id
            
            # Skip if already exists
            if vykaz_id in existing_vykaz_ids:
                skipped_count += 1
                continue
            
            # Create new entry
            new_entry = models.TimeEntry(
                uloha=entry.uloha or "",
                autor=entry.autor,
                datum=entry.datum,
                hodiny=entry.hodiny or 0,
                minuty=entry.minuty or 0,
                jira=entry.jira,
                popis=entry.popis,
                metaapp_vykaz_id=vykaz_id
            )
            
            db.add(new_entry)
            imported_count += 1
        
        # Commit all new entries
        if imported_count > 0:
            db.commit()
            print(f"[Import] Committed {imported_count} new entries")
        
        total_time = (time.time() - start_time) * 1000
        print(f"[Import] Import completed in {total_time:.1f}ms")
        
        return {
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "total_found": len(metaapp_entries)
        }
        
    except Exception as e:
        print(f"[Import] Error during import: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Chyba pri importe: {str(e)}")
