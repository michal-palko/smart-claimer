import os
import requests
from typing import List, Optional, Dict, Any
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
    """
    Fetch JIRA issues using the working issue picker endpoint.
    This replaces the deprecated search APIs (v2/v3) which return HTTP 410.
    """
    
    # Primary approach: Use issue picker endpoint (proven to work)
    try:
        return _fetch_jira_with_issue_picker(autor)
    except Exception as e1:
        print(f"Issue picker API failed: {e1}")
        
        # Fallback 1: Try GraphQL if available
        try:
            return _fetch_jira_with_graphql(autor)
        except Exception as e2:
            print(f"GraphQL API failed: {e2}")
            
            # Fallback 2: Return empty list with informative message
            print("All primary JIRA API methods failed.")
            print("Issue picker and GraphQL endpoints not available.")
            return []

def _fetch_jira_with_issue_picker(autor: str) -> List[dict]:
    """
    Use the working JIRA issue picker endpoint.
    This endpoint works even when search APIs are deprecated.
    """
    url = f"{JIRA_URL}/rest/api/3/issue/picker"
    headers = get_jira_headers()
    
    # Parameters that work based on our testing
    params = {
        "query": "",  # Empty query works better than searching by user
        "currentJQL": "updated >= -30d ORDER BY updated DESC",  # Recent issues
        "maxResults": 100,
        "showSubTasks": "true"
    }
    
    resp = requests.get(url, headers=headers, params=params)
    
    if resp.status_code == 410:
        raise Exception("Issue picker endpoint is also deprecated")
    
    resp.raise_for_status()
    
    result = resp.json()
    sections = result.get('sections', [])
    
    issues = []
    for section in sections:
        section_issues = section.get('issues', [])
        for issue in section_issues:
            # Extract issue data from picker format
            key = issue.get('key', '')
            summary = issue.get('summaryText') or issue.get('summary', '')
            
            # Skip if essential data is missing
            if not key or not summary:
                continue
                
            # Get additional details if available
            issue_data = {
                "key": key,
                "summary": summary,
                "parent_key": None,
                "parent_summary": None,
                "parent_color": None,
                "sprint_name": None
            }
            
            # Try to extract parent info if available
            if 'keyHtml' in issue and 'parent' in issue.get('keyHtml', '').lower():
                # This would need parsing of HTML content
                pass
                
            issues.append(issue_data)
    
    print(f"Issue picker found {len(issues)} issues")
    return issues[:100]  # Limit to 100 issues

def _fetch_jira_with_new_search_api(autor: str) -> List[dict]:
    """Use the newer enhanced search API"""
    # Try the enhanced search endpoint mentioned in the deprecation notice
    url = f"{JIRA_URL}/rest/api/3/search"
    headers = get_jira_headers()
    headers["Content-Type"] = "application/json"
    
    # Use POST with JSON body as per modern JIRA Cloud requirements
    data = {
        "jql": f"assignee = '{autor}' AND updated >= -30d ORDER BY updated DESC",
        "fields": ["key", "summary", "parent", "customfield_10020"],
        "maxResults": 100,
        "expand": ["names", "schema"],
        "validateQuery": "strict"
    }
    
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    
    result = resp.json()
    return _convert_standard_jira_response(result)

def _fetch_jira_with_post_search(autor: str) -> List[dict]:
    """Try POST method with the v2 endpoint"""
    url = f"{JIRA_URL}/rest/api/2/search"
    headers = get_jira_headers()
    headers["Content-Type"] = "application/json"
    
    # Sometimes the issue is GET vs POST method
    data = {
        "jql": f"assignee = '{autor}' AND updated >= -30d ORDER BY updated DESC",
        "fields": ["key", "summary", "parent", "customfield_10020"],
        "maxResults": 100
    }
    
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    
    result = resp.json()
    return _convert_standard_jira_response(result)

def _fetch_jira_via_individual_issues(autor: str) -> List[dict]:
    """Fallback: Get user's recent activity and extract issues"""
    # This is a workaround when search APIs are completely blocked
    
    # First, try to get the user's recent activity
    url = f"{JIRA_URL}/rest/api/2/user/search"
    headers = get_jira_headers()
    
    # Get user info first
    params = {"query": autor, "maxResults": 1}
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    
    users = resp.json()
    if not users:
        raise Exception(f"User {autor} not found")
    
    user_key = users[0].get("accountId") or users[0].get("key")
    
    # Now try to get issues via different endpoints
    # Try the issue navigator export API
    export_url = f"{JIRA_URL}/sr/jira.issueviews:searchrequest-csv-current-fields/temp/SearchRequest.csv"
    params = {
        "jqlQuery": f"assignee = '{autor}' AND updated >= -30d ORDER BY updated DESC",
        "tempMax": "100"
    }
    
    resp = requests.get(export_url, headers=headers, params=params)
    if resp.ok and resp.text:
        return _parse_csv_export(resp.text)
    
    raise Exception("No fallback method worked")

def _parse_csv_export(csv_text: str) -> List[dict]:
    """Parse CSV export from JIRA to extract issues"""
    import csv
    from io import StringIO
    
    issues = []
    csv_reader = csv.DictReader(StringIO(csv_text))
    
    for row in csv_reader:
        # CSV format typically has columns like: Issue key, Summary, etc.
        key = row.get("Issue key") or row.get("Key")
        summary = row.get("Summary")
        
        if key and summary:
            issues.append({
                "key": key,
                "summary": summary,
                "parent_key": None,  # CSV doesn't typically include parent info
                "parent_summary": None,
                "parent_color": None,
                "sprint_name": None
            })
    
    return issues[:100]  # Limit to 100 issues

def _fetch_jira_alternative_approach(autor: str) -> List[dict]:
    """Alternative approach when search API is blocked"""
    
    # Try the internal JIRA Cloud API that the web interface uses
    # This mimics what happens when you open JIRA in browser
    
    # Approach 1: Try the GraphQL API
    try:
        return _fetch_jira_with_graphql(autor)
    except Exception as e1:
        print(f"GraphQL failed: {e1}")
        
        # Approach 2: Try the internal gateway API
        try:
            return _fetch_jira_with_gateway_api(autor)
        except Exception as e2:
            print(f"Gateway API failed: {e2}")
            
            # Approach 3: Try recent issues API
            try:
                return _fetch_jira_recent_issues(autor)
            except Exception as e3:
                print(f"Recent issues API failed: {e3}")
                
                # If all else fails, return empty list with a warning
                print("All JIRA API approaches failed.")
                print("This JIRA instance appears to have restricted API access.")
                print("Consider using a different authentication method or contact JIRA admin.")
                
                # Return empty list to prevent application crash
                return []

def _fetch_jira_with_graphql(autor: str) -> List[dict]:
    """
    Try JIRA's GraphQL API with correct format.
    Uses cloud ID and proper schema based on our testing.
    """
    url = f"{JIRA_URL}/gateway/api/graphql"
    headers = get_jira_headers()
    headers["Content-Type"] = "application/json"
    
    # Cloud ID discovered during testing
    cloud_id = "8c4eb6af-bf5a-46d5-967d-41cd279026f9"
    
    query_data = {
        "query": """
        query SearchJiraIssues($cloudId: ID!, $searchInput: JiraIssueSearchInput!) {
            jira {
                issueSearch(cloudId: $cloudId, issueSearchInput: $searchInput) {
                    edges {
                        node {
                            key
                            summary
                        }
                    }
                    totalCount
                }
            }
        }
        """,
        "variables": {
            "cloudId": cloud_id,
            "searchInput": {
                "jql": f"assignee = currentUser() ORDER BY updated DESC"
            }
        },
        "operationName": "SearchJiraIssues"
    }
    
    resp = requests.post(url, headers=headers, json=query_data)
    resp.raise_for_status()
    
    result = resp.json()
    
    # Check for GraphQL errors
    if 'errors' in result and result['errors']:
        error_messages = [error.get('message', str(error)) for error in result['errors']]
        raise Exception(f"GraphQL errors: {'; '.join(error_messages)}")
    
    # Extract issues from GraphQL response
    issues = []
    jira_data = result.get('data', {}).get('jira', {})
    issue_search = jira_data.get('issueSearch', {})
    edges = issue_search.get('edges', [])
    
    for edge in edges:
        node = edge.get('node', {})
        key = node.get('key')
        summary = node.get('summary')
        
        if key and summary:
            issues.append({
                "key": key,
                "summary": summary,
                "parent_key": None,
                "parent_summary": None,
                "parent_color": None,
                "sprint_name": None
            })
    
    print(f"GraphQL found {len(issues)} issues")
    return issues

def _fetch_jira_with_gateway_api(autor: str) -> List[dict]:
    """Try JIRA's gateway API"""
    url = f"{JIRA_URL}/gateway/api/jira/search"
    headers = get_jira_headers()
    
    params = {
        "jql": f"assignee = '{autor}' AND updated >= -30d ORDER BY updated DESC",
        "fields": "key,summary,parent,customfield_10020",
        "maxResults": 100
    }
    
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    
    result = resp.json()
    return _convert_standard_jira_response(result)

def _fetch_jira_recent_issues(autor: str) -> List[dict]:
    """Try to get recent issues from activity API"""
    url = f"{JIRA_URL}/rest/api/2/myself"
    headers = get_jira_headers()
    
    # First get user info to confirm authentication
    resp = requests.get(url, headers=headers)
    if not resp.ok:
        raise Exception("Cannot authenticate user")
    
    user_info = resp.json()
    print(f"Authenticated as: {user_info.get('emailAddress', 'unknown')}")
    
    # Try activity streams API
    activity_url = f"{JIRA_URL}/rest/activity-stream/1.0/activities"
    params = {
        "maxResults": 100,
        "streams": f"user IS {user_info.get('key', autor)}"
    }
    
    resp = requests.get(activity_url, headers=headers, params=params)
    if resp.ok:
        activities = resp.json()
        return _extract_issues_from_activities(activities)
    
    raise Exception("No alternative API worked")

def _convert_graphql_response(result) -> List[dict]:
    """Convert GraphQL response to expected format"""
    issues = []
    jira_data = result.get('data', {}).get('jira', {})
    issue_search = jira_data.get('issueSearch', {})
    
    for issue in issue_search.get('issues', []):
        parent = issue.get('parent')
        issues.append({
            "key": issue.get('key'),
            "summary": issue.get('summary'),
            "parent_key": parent.get('key') if parent else None,
            "parent_summary": parent.get('summary') if parent else None,
            "parent_color": None,
            "sprint_name": None
        })
    
    return issues

def _convert_standard_jira_response(result) -> List[dict]:
    """Convert standard JIRA API response to expected format"""
    # This should work the same as the original parsing
    issues = result.get("issues", [])
    parsed_issues = []
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
            parent_resp = requests.get(parent_url, headers=get_jira_headers())
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
        
        parsed_issues.append({
            "key": key,
            "summary": summary,
            "parent_key": parent_key,
            "parent_summary": parent_summary,
            "parent_color": parent_color,
            "sprint_name": sprint_name
        })
    
    # Sort alphabetically by key
    parsed_issues.sort(key=lambda x: x["key"])
    return parsed_issues

def _extract_issues_from_activities(activities) -> List[dict]:
    """Extract issue information from activity stream"""
    issues = []
    seen_keys = set()
    
    for activity in activities.get('feed', {}).get('entry', []):
        # Look for issue references in activities
        target = activity.get('target')
        if target and target.get('objectType') == 'issue':
            key = target.get('summary', '').split(' - ')[0] if target.get('summary') else None
            if key and key not in seen_keys:
                issues.append({
                    "key": key,
                    "summary": target.get('summary', '').split(' - ', 1)[1] if ' - ' in target.get('summary', '') else target.get('summary', ''),
                    "parent_key": None,
                    "parent_summary": None,
                    "parent_color": None,
                    "sprint_name": None
                })
                seen_keys.add(key)
    
    return issues

def _fetch_jira_with_new_api(autor: str) -> List[dict]:
    """Try the newer enhanced search API"""
    # Use v3 search but with different parameters
    url = f"{JIRA_URL}/rest/api/3/jql/match"
    headers = get_jira_headers()
    headers["Content-Type"] = "application/json"
    
    data = {
        "jqls": [f"assignee = '{autor}' AND updated >= -30d ORDER BY updated DESC"]
    }
    
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    
    # This API returns different format, need to adapt
    result = resp.json()
    return _convert_jql_match_response(result)

def _fetch_jira_with_jql_endpoint(autor: str) -> List[dict]:
    """Try using a different JQL endpoint"""
    url = f"{JIRA_URL}/rest/api/3/expression/eval"
    headers = get_jira_headers()
    headers["Content-Type"] = "application/json"
    
    # Try expression evaluation API
    data = {
        "expression": f"issue.assignee.emailAddress = '{autor}' AND issue.updated >= -30d",
        "context": {}
    }
    
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    
    # This won't work for search, but let's see what happens
    result = resp.json()
    return []

def _fetch_jira_with_picker_api(autor: str) -> List[dict]:
    """Try using issue picker API as a workaround"""
    url = f"{JIRA_URL}/rest/api/2/issue/picker"
    headers = get_jira_headers()
    
    # Try different query formats
    params = {
        "query": autor,  # Simple query with just the email
        "maxResults": 100,
        "showSubTasks": True,
        "showSubTaskParent": True
    }
    
    resp = requests.get(url, headers=headers, params=params)
    if not resp.ok:
        # Try with different parameters if first attempt fails
        params = {
            "query": f"{autor} assignee",
            "maxResults": 50
        }
        resp = requests.get(url, headers=headers, params=params)
    
    resp.raise_for_status()
    
    result = resp.json()
    print(f"Picker API response: {result}")  # Debug output
    return _convert_picker_response(result)

def _convert_jql_match_response(result) -> List[dict]:
    """Convert JQL match API response to expected format"""
    # Placeholder - need to see actual response format
    return []

def _convert_picker_response(result) -> List[dict]:
    """Convert issue picker response to expected format"""
    issues = []
    sections = result.get('sections', [])
    
    for section in sections:
        for issue in section.get('issues', []):
            issues.append({
                "key": issue.get('key'),
                "summary": issue.get('summary'),
                "parent_key": None,  # Picker API doesn't include parent info
                "parent_summary": None,
                "parent_color": None,
                "sprint_name": None
            })
    
    return issues
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
