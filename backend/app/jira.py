import os
import requests
from typing import List, Optional
from functools import lru_cache
from dotenv import load_dotenv
import base64

# Load environment variables from .env file
load_dotenv()

# Get JIRA credentials from environment variables
JIRA_URL = os.getenv('JIRA_URL')
JIRA_USER = os.getenv('JIRA_USER')
JIRA_TOKEN = os.getenv('JIRA_TOKEN')

if not all([JIRA_URL, JIRA_USER, JIRA_TOKEN]):
    raise ValueError("Missing required JIRA credentials in environment variables. Please check your .env file.")

def get_jira_headers():
    """Get standardized JIRA headers with authentication"""
    auth_string = f"{JIRA_USER}:{JIRA_TOKEN}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    return {
        "Accept": "application/json",
        "Authorization": f"Basic {auth_b64}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

# Helper to fetch epic color by key (with simple in-memory cache)
@lru_cache(maxsize=128)
def fetch_epic_color(epic_key: str) -> Optional[str]:
    if not epic_key:
        return None
    url = f"{JIRA_URL}/rest/api/3/issue/{epic_key}"
    headers = get_jira_headers()
    params = {"fields": "customfield_10011,customfield_10016"}  # customfield_10011: Epic Color, customfield_10016: Epic Name (may vary)
    resp = requests.get(url, headers=headers, params=params)
    if not resp.ok:
        return None
    fields = resp.json().get("fields", {})
    # Try both possible field names for epic color
    color = fields.get("customfield_10011") or fields.get("epic_color")
    return color

def get_board_id():
    # Get first board (or filter by name/type if needed)
    url = f"{JIRA_URL}/rest/agile/1.0/board"
    headers = get_jira_headers()
    resp = requests.get(url, headers=headers)
    boards = resp.json().get("values", [])
    if not boards:
        raise Exception("No JIRA boards found")
    return boards[0]["id"]

def get_current_and_prior_sprints(board_id):
    url = f"{JIRA_URL}/rest/agile/1.0/board/{board_id}/sprint?state=active,future,closed"
    headers = get_jira_headers()
    resp = requests.get(url, headers=headers)
    sprints = resp.json().get("values", [])
    # Find current (active) and most recent closed sprint
    current = next((s for s in sprints if s["state"] == "active"), None)
    closed = [s for s in sprints if s["state"] == "closed"]
    prior = closed[-1] if closed else None
    return current, prior

# JIRA API: Search issues assigned to a user (author) - for dropdown autocomplete
def fetch_jira_issues_for_author(autor: str) -> List[dict]:
    # Simple JQL: assigned to user, not done, recently updated (no sprint filtering)
    # Use single quotes instead of double quotes for JQL
    jql = f"assignee = '{autor}' AND updated >= -30d ORDER BY updated DESC"
    
    # Try v3 API with different approach
    url = f"{JIRA_URL}/rest/api/3/search"
    
    # Use standardized headers with authentication
    headers = get_jira_headers()
    headers["Content-Type"] = "application/json"
    
    # Try POST instead of GET with JSON body
    data = {
        "jql": jql,
        "fields": ["key", "summary", "parent", "customfield_10020"],
        "maxResults": 100
    }
    
    try:
        resp = requests.post(url, headers=headers, json=data)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        # If POST fails, try GET as fallback
        print(f"POST failed, trying GET: {e}")
        headers.pop("Content-Type", None)
        params = {
            "jql": jql,
            "fields": "key,summary,parent,customfield_10020",
            "maxResults": 100
        }
        try:
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e2:
            print(f"JIRA API Error: {e2}")
            print(f"Response status: {resp.status_code}")
            print(f"Response body: {resp.text}")
            print(f"Request URL: {resp.url}")
            raise
    issues = resp.json().get("issues", [])
    result = []
    parent_color_cache = {}
    for issue in issues:
        key = issue["key"]
        summary = issue["fields"].get("summary", "")
        parent = issue["fields"].get("parent")
        parent_key = parent["key"] if parent else None
        parent_summary = parent["fields"].get("summary") if parent and parent.get("fields") else None
        parent_color = None
        # If issue is 'Review - ...', get parent of parent as parent
        if summary.strip().startswith("Review -") and parent_key:
            # Fetch parent issue to get its parent
            parent_url = f"{JIRA_URL}/rest/api/3/issue/{parent_key}"
            parent_resp = requests.get(parent_url, headers=headers)
            if parent_resp.ok:
                parent_fields = parent_resp.json().get("fields", {})
                grandparent = parent_fields.get("parent")
                if grandparent:
                    parent_key = grandparent.get("key")
                    parent_summary = grandparent.get("fields", {}).get("summary")
        if parent_key:
            if parent_key in parent_color_cache:
                parent_color = parent_color_cache[parent_key]
            else:
                parent_color = fetch_epic_color(parent_key)
                parent_color_cache[parent_key] = parent_color
        # Sprint info
        sprint_field = issue["fields"].get("customfield_10020")
        sprint_name = None
        if sprint_field:
            if isinstance(sprint_field, list) and sprint_field:
                sprint_str = sprint_field[-1]
                import re
                name_match = re.search(r'name=([^,]+)', sprint_str)
                if name_match:
                    sprint_name = name_match.group(1)
        result.append({
            "key": key,
            "summary": summary,
            "parent_key": parent_key,
            "parent_summary": parent_summary,
            "parent_color": parent_color,
            "sprint_name": sprint_name
        })
    # Sort alphabetically by key
    result.sort(key=lambda x: x["key"])
    return result

# JIRA API: Search for any issue by key (for metadata lookup during form submission)
def fetch_jira_issue_by_key(issue_key: str) -> Optional[dict]:
    """
    Fetch a specific JIRA issue by key for metadata lookup.
    Used when user manually enters a JIRA key and we need to get its details.
    Searches all issues regardless of assignee, status, or sprint.
    """
    if not issue_key:
        return None
    
    jql = f"key = '{issue_key}'"
    url = f"{JIRA_URL}/rest/api/2/search"
    headers = get_jira_headers()
    params = {
        "jql": jql,
        "fields": "key,summary,parent,customfield_10020",  # customfield_10020: Sprint
        "maxResults": 1
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        issues = resp.json().get("issues", [])
        
        if not issues:
            return None
            
        issue = issues[0]
        key = issue["key"]
        summary = issue["fields"].get("summary", "")
        parent = issue["fields"].get("parent")
        parent_key = parent["key"] if parent else None
        parent_summary = parent["fields"].get("summary") if parent and parent.get("fields") else None
        parent_color = None
        
        # If issue is 'Review - ...', get parent of parent as parent
        if summary.strip().startswith("Review -") and parent_key:
            # Fetch parent issue to get its parent
            parent_url = f"{JIRA_URL}/rest/api/3/issue/{parent_key}"
            parent_resp = requests.get(parent_url, headers=headers)
            if parent_resp.ok:
                parent_fields = parent_resp.json().get("fields", {})
                grandparent = parent_fields.get("parent")
                if grandparent:
                    parent_key = grandparent.get("key")
                    parent_summary = grandparent.get("fields", {}).get("summary")
        
        if parent_key:
            parent_color = fetch_epic_color(parent_key)
        
        # Sprint info
        sprint_field = issue["fields"].get("customfield_10020")
        sprint_name = None
        if sprint_field:
            if isinstance(sprint_field, list) and sprint_field:
                sprint_str = sprint_field[-1]
                import re
                name_match = re.search(r'name=([^,]+)', sprint_str)
                if name_match:
                    sprint_name = name_match.group(1)
        
        return {
            "key": key,
            "summary": summary,
            "parent_key": parent_key,
            "parent_summary": parent_summary,
            "parent_color": parent_color,
            "sprint_name": sprint_name
        }
        
    except Exception as e:
        print(f"Error fetching JIRA issue {issue_key}: {str(e)}")
        return None

def clean_text(text):
    """Clean up text content by removing excessive whitespace."""
    if not text:
        return ""
    # Remove multiple blank lines
    text = "\n".join(line for line in text.splitlines() if line.strip())
    # Remove extra spaces
    text = " ".join(text.split())
    return text

def process_jira_body(body):
    """Process a Jira comment/description body that can be either HTML, plain text, or ADF format."""
    if not body:
        return ""
    
    if isinstance(body, dict):
        # This is ADF (Atlassian Document Format)
        try:
            result = []
            for content in body.get("content", []):
                if content["type"] == "paragraph":
                    paragraph_text = []
                    for text in content.get("content", []):
                        if text["type"] == "text":
                            paragraph_text.append(clean_text(text.get("text", "")))
                    cleaned_text = "".join(paragraph_text).strip()
                    if cleaned_text:  # Only add non-empty paragraphs
                        result.append(f"<p>{cleaned_text}</p>")
                elif content["type"] == "bulletList":
                    list_items = []
                    for item in content.get("content", []):
                        if item["type"] == "listItem":
                            item_text = []
                            for paragraph in item.get("content", []):
                                if paragraph["type"] == "paragraph":
                                    for text in paragraph.get("content", []):
                                        if text["type"] == "text":
                                            item_text.append(clean_text(text.get("text", "")))
                            cleaned_text = "".join(item_text).strip()
                            if cleaned_text:  # Only add non-empty items
                                list_items.append(f"<li>{cleaned_text}</li>")
                    if list_items:
                        result.append("<ul>" + "".join(list_items) + "</ul>")
                elif content["type"] == "orderedList":
                    list_items = []
                    for item in content.get("content", []):
                        if item["type"] == "listItem":
                            item_text = []
                            for paragraph in item.get("content", []):
                                if paragraph["type"] == "paragraph":
                                    for text in paragraph.get("content", []):
                                        if text["type"] == "text":
                                            item_text.append(clean_text(text.get("text", "")))
                            cleaned_text = "".join(item_text).strip()
                            if cleaned_text:  # Only add non-empty items
                                list_items.append(f"<li>{cleaned_text}</li>")
                    if list_items:
                        result.append("<ol>" + "".join(list_items) + "</ol>")
            return "".join(result)
        except (KeyError, TypeError):
            return clean_text(str(body))  # Fallback if we can't parse the structure
    else:
        # For HTML content, preserve the formatting while cleaning up whitespace
        if isinstance(body, str):
            # Split by HTML tags and clean text content while preserving tags
            import re
            parts = re.split('(<[^>]*>)', str(body))
            cleaned_parts = []
            for part in parts:
                if part.startswith('<'):
                    # This is an HTML tag, keep as is
                    cleaned_parts.append(part)
                else:
                    # This is text content, clean it up
                    cleaned_parts.append(clean_text(part))
            return "".join(cleaned_parts)
        return clean_text(str(body))

def get_issue_details(issue_key: str):
    """Fetch detailed information about a JIRA issue."""
    if not issue_key:
        return None

    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    headers.update(get_jira_headers())  # Add authentication to existing headers
    params = {
        "fields": "summary,status,priority,description,comment",
        "expand": "renderedFields"
    }

    try:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        fields = data.get("fields", {})
        rendered = data.get("renderedFields", {})

        # Extract and format the relevant fields
        issue_data = {
            "key": data.get("key", issue_key),
            "summary": fields.get("summary", ""),
            "status": {
                "name": fields.get("status", {}).get("name", "Unknown"),
                "statusCategory": fields.get("status", {}).get("statusCategory", {})
            },
            "priority": fields.get("priority", {"name": "Medium", "iconUrl": None}),
            "description": process_jira_body(rendered.get("description") or fields.get("description", "")),
            "comments": [],
            "baseUrl": JIRA_URL
        }

        # Extract comments if available
        comments = fields.get("comment", {}).get("comments", [])
        rendered_comments = rendered.get("comment", {}).get("comments", []) if isinstance(rendered.get("comment"), dict) else rendered.get("comment", [])
        
        issue_data["comments"] = []
        for c in comments:
            comment_id = c.get("id")
            # Try to find rendered version of this comment
            rendered_comment = None
            if rendered_comments:
                rendered_comment = next((rc for rc in rendered_comments if rc.get("id") == comment_id), None)
            
            comment_body = rendered_comment.get("body") if rendered_comment else c.get("body", "")
            
            issue_data["comments"].append({
                "id": comment_id,
                "body": process_jira_body(comment_body),
                "author": {
                    "displayName": c.get("author", {}).get("displayName", "Unknown"),
                    "avatarUrl": c.get("author", {}).get("avatarUrls", {}).get("24x24")
                },
                "created": c.get("created")
            })

        return issue_data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching JIRA issue {issue_key}: {str(e)}")
        return None
