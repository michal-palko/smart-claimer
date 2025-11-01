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

def get_enhanced_jql_query(autor: str = None, for_current_user: bool = False) -> str:
    """
    Generate enhanced JQL query for both active sprints and recent updates.
    
    Args:
        autor: Specific user email to filter by (when not using currentUser())
        for_current_user: If True, uses currentUser(), else uses autor parameter
    
    Returns:
        JQL query string combining active sprints and recent updates
    """
    if for_current_user:
        assignee_clause = "assignee = currentUser() AND "
    elif autor:
        assignee_clause = f"assignee = '{autor}' AND "
    else:
        assignee_clause = ""
    
    # Enhanced query: Active sprint items + future sprint items + backlog items in sprints + recent updates
    return (
        f"{assignee_clause}("
        "sprint in openSprints() OR "                           # Issues in active/open sprints
        "sprint in futureSprints() OR "                         # Issues in future sprints
        "(status = 'Backlog' AND sprint in openSprints()) OR "  # Backlog items in active sprints
        "(status = 'Backlog' AND sprint in futureSprints()) OR " # Backlog items in future sprints
        "(summary ~ \"Review\" AND statusCategory != Done) OR "  # Review items sitting in backlog
        "updated >= -7d"                                        # Recently updated items
        ") "
        "ORDER BY updated DESC"
    )

# Helper to fetch epic color by key (no caching for fresh data)
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
    Fetch JIRA issues assigned to the specified author.
    Tries the modern search API first for full fidelity, then falls back
    to the issue picker and GraphQL as needed.
    """
    fetch_jira_issues_for_author.last_meta = {
        "source": None,
        "limit": None,
        "requested": None,
        "returned": 0,
        "reported_total": None,
        "note": None,
    }
    errors = []

    try:
        search_issues = _fetch_jira_with_new_search_api(autor)
        if search_issues:
            meta = getattr(_fetch_jira_with_new_search_api, "last_meta", {})
            fetch_jira_issues_for_author.last_meta.update(meta)
            print(
                f"[JIRA Fetch] search_api returned {len(search_issues)} issues "
                f"(requested={meta.get('requested')}, limit={meta.get('limit')}, total={meta.get('reported_total')})"
            )
            return search_issues
        print("[JIRA Fetch] search_api returned no issues, continuing with fallbacks")
    except Exception as exc:
        print(f"[JIRA Fetch] search_api failed: {exc}")
        errors.append(("search_api", str(exc)))

    try:
        picker_issues = _fetch_jira_with_issue_picker(autor)
        if picker_issues:
            meta = getattr(_fetch_jira_with_issue_picker, "last_meta", {})
            fetch_jira_issues_for_author.last_meta.update(meta)
            print(
                f"[JIRA Fetch] issue_picker returned {len(picker_issues)} issues "
                f"(requested={meta.get('requested')}, limit={meta.get('limit')}, total={meta.get('reported_total')})"
            )
            return picker_issues
    except Exception as exc:
        print(f"[JIRA Fetch] issue_picker failed: {exc}")
        errors.append(("issue_picker", str(exc)))

    try:
        graphql_issues = _fetch_jira_with_graphql(autor)
        if graphql_issues:
            meta = getattr(_fetch_jira_with_graphql, "last_meta", {})
            fetch_jira_issues_for_author.last_meta.update(meta)
            print(
                f"[JIRA Fetch] graphql returned {len(graphql_issues)} issues "
                f"(requested={meta.get('requested')}, limit={meta.get('limit')}, total={meta.get('reported_total')})"
            )
            return graphql_issues
    except Exception as exc:
        print(f"[JIRA Fetch] graphql failed: {exc}")
        errors.append(("graphql", str(exc)))

    print("[JIRA Fetch] No issues returned by any method.")
    if errors:
        for name, err in errors:
            print(f"  - {name} error: {err}")
        fetch_jira_issues_for_author.last_meta["note"] = "all fetchers failed or returned empty"
    return []

def _fetch_jira_with_issue_picker(autor: str) -> List[dict]:
    """
    Use the working JIRA issue picker endpoint.
    This endpoint works even when search APIs are deprecated.
    Returns basic issue information without parent details for better performance.
    
    Query strategy: Get issues from active sprints OR recently updated (last 3 days)
    """
    url = f"{JIRA_URL}/rest/api/3/issue/picker"
    headers = get_jira_headers()
    
    # Enhanced JQL: Active sprints OR recent updates (last 3 days) for specific user
    # This gives a comprehensive view of current work assigned to the user
    enhanced_jql = get_enhanced_jql_query(autor=autor, for_current_user=False)
    
    # Parameters that work based on our testing
    params = {
        "query": "",  # Empty query works better than searching by user
        "currentJQL": enhanced_jql,
        "maxResults": 150,  # Increased to account for more comprehensive query
        "showSubTasks": "true"
    }
    
    resp = requests.get(url, headers=headers, params=params)
    
    if resp.status_code == 410:
        raise Exception("Issue picker endpoint is also deprecated")
    
    resp.raise_for_status()
    
    result = resp.json()
    sections = result.get('sections', [])
    
    # Collect issue keys first
    issue_keys = []
    issue_summaries = {}
    
    for section in sections:
        section_issues = section.get('issues', [])
        for issue in section_issues:
            key = issue.get('key', '')
            summary = issue.get('summaryText') or issue.get('summary', '')
            
            if key and summary:
                issue_keys.append(key)
                issue_summaries[key] = summary
    
    if not issue_keys:
        print("No issues found in issue picker")
        _fetch_jira_with_issue_picker.last_meta = {
            "source": "issue_picker",
            "limit": params.get("maxResults"),
            "requested": params.get("maxResults"),
            "returned": 0,
            "reported_total": 0,
            "note": f"sections={len(sections)}"
        }
        return []

    print(f"Issue picker found {len(issue_keys)} issues - returning basic info for performance")
    print(f"Issue keys found: {issue_keys}")
    
    # Check if CARTV-60 is in the results
    if "CARTV-60" in issue_keys:
        print("✓ CARTV-60 found in issue picker results")
    else:
        print("✗ CARTV-60 NOT found in issue picker results")
        print(f"JQL used: {enhanced_jql}")
    
    # Enrich issues with parent information when possible
    enhanced_issues = []
    headers = get_jira_headers()

    print(f"[ENRICHMENT] Starting parent enrichment for {len(issue_keys)} issues")
    for issue_key in issue_keys:
        details = None
        try:
            print(f"[ENRICHMENT] Fetching details for {issue_key}")
            details = _fetch_issue_details(issue_key, headers)
            if details:
                print(f"[ENRICHMENT] ✓ Got details for {issue_key}: parent_key={details.get('parent_key')}")
            else:
                print(f"[ENRICHMENT] ✗ No details returned for {issue_key}")
        except Exception as detail_exc:
            print(f"[ENRICHMENT] ✗ Failed to fetch details for {issue_key}: {detail_exc}")

        if details:
            if not details.get("summary"):
                details["summary"] = issue_summaries.get(issue_key, "")
            enhanced_issues.append(details)
        else:
            enhanced_issues.append({
                "key": issue_key,
                "summary": issue_summaries.get(issue_key, ""),
                "parent_key": None,
                "parent_summary": None,
                "parent_color": None,
                "sprint_name": None
            })

    print(f"Returned {len(enhanced_issues)} issues (issue picker with parent enrichment)")
    meta = {
        "source": "issue_picker",
        "limit": params.get("maxResults"),
        "requested": params.get("maxResults"),
        "returned": len(enhanced_issues),
        "reported_total": result.get("total") or len(issue_keys),
        "note": f"sections={len(sections)}"
    }
    _fetch_jira_with_issue_picker.last_meta = meta
    return enhanced_issues

def _fetch_issue_details(issue_key: str, headers: dict) -> Optional[Dict[str, Any]]:
    """
    Fetch detailed information for a single issue including parent data.
    """
    print(f"[DEBUG] _fetch_issue_details called for {issue_key}")
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}"
    
    # Request specific fields we need
    params = {
        "fields": "key,summary,parent,issuelinks,customfield_10020,customfield_10014,customfield_10016"
    }
    
    resp = requests.get(url, headers=headers, params=params)
    
    if not resp.ok:
        return None
    
    issue_data = resp.json()
    fields = issue_data.get('fields', {})
    
    # Extract basic issue info
    result = {
        "key": issue_key,
        "summary": "",  # Will be set by caller
        "parent_key": None,
        "parent_summary": None,
        "parent_color": None,
        "sprint_name": None
    }
    
    # Get the issue summary first
    issue_summary = fields.get('summary', '') or ""
    result["summary"] = issue_summary
    print(f"[DEBUG] _fetch_issue_details for {issue_key}: summary='{issue_summary}'")
    
    # Extract parent information
    parent = fields.get('parent')
    if parent:
        result["parent_key"] = parent.get('key')
        parent_fields = parent.get('fields', {})
        result["parent_summary"] = parent_fields.get('summary', '')
        
        # Try to get parent color if it's an epic
        parent_key = result["parent_key"]
        if parent_key:
            try:
                parent_color = fetch_epic_color(parent_key)
                result["parent_color"] = parent_color
            except:
                pass  # Color is optional
    
    # Check for epic link in custom fields (alternative to parent)
    if not result["parent_key"]:
        epic_link = fields.get('customfield_10014') or fields.get('customfield_10016')
        if epic_link:
            # Epic link might be just a key or an object
            if isinstance(epic_link, str):
                result["parent_key"] = epic_link
            elif isinstance(epic_link, dict):
                result["parent_key"] = epic_link.get('key')
                result["parent_summary"] = epic_link.get('summary', '')
    
    # Special handling for Review issues - use grandparent as uloha
    issue_summary = fields.get('summary', '') or ""
    print(f"[PARENT LOOKUP] Issue {issue_key}: summary='{issue_summary}', has_parent={result['parent_key'] is not None}")
    if issue_summary.lower().startswith('review') and result["parent_key"]:
        print(f"[REVIEW DETECTED] {issue_key} is a Review issue, fetching grandparent for parent {result['parent_key']}")
        try:
            # For Review issues, fetch the parent of parent (grandparent)
            grandparent_info = _fetch_grandparent_info(result["parent_key"], headers)
            if grandparent_info:
                print(f"[GRANDPARENT FOUND] {issue_key}: Replacing parent {result['parent_key']} with grandparent {grandparent_info['key']}")
                # Replace parent with grandparent for Review issues
                result["parent_key"] = grandparent_info["key"]
                result["parent_summary"] = grandparent_info["summary"]
                result["parent_color"] = grandparent_info["color"]
                print(f"✓ Review issue {issue_key}: Using grandparent {grandparent_info['key']} as uloha")
            else:
                print(f"✗ Review issue {issue_key}: No grandparent found, keeping original parent {result['parent_key']}")
        except Exception as e:
            print(f"✗ Failed to fetch grandparent for review issue {issue_key}: {e}")
            # Keep original parent if grandparent fetch fails
    else:
        if result["parent_key"]:
            print(f"[REGULAR ISSUE] {issue_key}: Using parent {result['parent_key']} as uloha")
    
    # Extract sprint information if available
    sprint_field = fields.get('customfield_10020')  # Common sprint field
    if sprint_field and isinstance(sprint_field, list) and sprint_field:
        # Sprint is usually an array, take the first active one
        sprint = sprint_field[0]
        if isinstance(sprint, dict):
            result["sprint_name"] = sprint.get('name', '')
        elif isinstance(sprint, str) and 'name=' in sprint:
            # Parse sprint string format
            try:
                name_part = sprint.split('name=')[1].split(',')[0]
                result["sprint_name"] = name_part
            except:
                pass
    
    return result

def _fetch_grandparent_info(parent_key: str, headers: dict) -> Optional[Dict[str, Any]]:
    """
    Fetch grandparent information for Review issues.
    Returns the parent of the given parent issue.
    """
    if not parent_key:
        return None
    
    url = f"{JIRA_URL}/rest/api/3/issue/{parent_key}"
    params = {
        "fields": "key,summary,parent,customfield_10014,customfield_10016"
    }
    
    resp = requests.get(url, headers=headers, params=params)
    if not resp.ok:
        return None
    
    parent_data = resp.json()
    parent_fields = parent_data.get('fields', {})
    
    # Look for grandparent (parent's parent)
    grandparent = parent_fields.get('parent')
    if grandparent:
        grandparent_key = grandparent.get('key')
        grandparent_fields = grandparent.get('fields', {})
        grandparent_summary = grandparent_fields.get('summary', '')
        
        # Try to get grandparent color
        grandparent_color = None
        if grandparent_key:
            try:
                grandparent_color = fetch_epic_color(grandparent_key)
            except:
                pass
        
        return {
            "key": grandparent_key,
            "summary": grandparent_summary,
            "color": grandparent_color
        }
    
    # Check for epic link as alternative
    epic_link = parent_fields.get('customfield_10014') or parent_fields.get('customfield_10016')
    if epic_link:
        if isinstance(epic_link, str):
            return {"key": epic_link, "summary": "", "color": None}
        elif isinstance(epic_link, dict):
            return {
                "key": epic_link.get('key'),
                "summary": epic_link.get('summary', ''),
                "color": None
            }
    
    return None

def _fetch_jira_with_new_search_api(autor: str) -> List[dict]:
    """Use the newer enhanced search API"""
    # Try the enhanced search endpoint mentioned in the deprecation notice
    url = f"{JIRA_URL}/rest/api/3/search"
    headers = get_jira_headers()
    headers["Content-Type"] = "application/json"
    
    # Use POST with JSON body as per modern JIRA Cloud requirements
    data = {
        "jql": get_enhanced_jql_query(autor=autor, for_current_user=False),
        "fields": ["key", "summary", "parent", "customfield_10020", "customfield_10014", "customfield_10016"],
        "maxResults": 200,
        "validateQuery": False
    }
    
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    
    result = resp.json()
    issues = _convert_standard_jira_response(result)
    meta = {
        "source": "search_api",
        "limit": data.get("maxResults"),
        "requested": data.get("maxResults"),
        "returned": len(issues),
        "reported_total": result.get("total"),
        "note": f"startAt={result.get('startAt', 0)}"
    }
    _fetch_jira_with_new_search_api.last_meta = meta
    return issues

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
                "jql": get_enhanced_jql_query(for_current_user=True)
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
    meta = {
        "source": "graphql",
        "limit": None,
        "requested": None,
        "returned": len(issues),
        "reported_total": issue_search.get('totalCount'),
        "note": f"edges={len(edges)}"
    }
    _fetch_jira_with_graphql.last_meta = meta
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
    
    # Use direct issue endpoint instead of deprecated search API
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}"
    headers = get_jira_headers()
    params = {"fields": "key,summary,parent,customfield_10020"}  # customfield_10020: Sprint
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        
        if resp.status_code == 404:
            print(f"JIRA issue {issue_key} not found")
            return None
        elif not resp.ok:
            print(f"JIRA API error for {issue_key}: {resp.status_code}")
            return None
        
        issue_data = resp.json()
        fields = issue_data.get("fields", {})
        
        key = issue_key
        summary = fields.get("summary", "")
        parent = fields.get("parent")
        parent_key = parent.get("key") if parent else None
        parent_summary = parent.get("fields", {}).get("summary") if parent and parent.get("fields") else None
        parent_color = None
        
        print(f"[JIRA Validation] Found {key}: '{summary}'")
        
        # If issue is 'Review - ...', get grandparent as uloha  
        if summary.strip().startswith("Review -") and parent_key:
            print(f"[JIRA Validation] Review issue detected, looking for grandparent")
            # Fetch parent issue to get its parent (grandparent)
            parent_url = f"{JIRA_URL}/rest/api/3/issue/{parent_key}"
            parent_resp = requests.get(parent_url, headers=headers)
            if parent_resp.ok:
                parent_fields = parent_resp.json().get("fields", {})
                grandparent = parent_fields.get("parent")
                if grandparent:
                    parent_key = grandparent.get("key")
                    parent_summary = grandparent.get("fields", {}).get("summary")
                    print(f"[JIRA Validation] Using direct grandparent {parent_key} as uloha")
                else:
                    # No direct grandparent, check Epic Link
                    print(f"[JIRA Validation] No direct grandparent, checking Epic Link")
                    epic_link = parent_fields.get('customfield_10014') or parent_fields.get('customfield_10016')
                    if epic_link:
                        if isinstance(epic_link, str):
                            parent_key = epic_link
                            parent_summary = ""
                        elif isinstance(epic_link, dict):
                            parent_key = epic_link.get('key')
                            parent_summary = epic_link.get('summary', '')
                        print(f"[JIRA Validation] Using Epic Link {parent_key} as grandparent")
                    else:
                        print(f"[JIRA Validation] No grandparent or Epic Link found, using NO EPIC ASSIGNED")
                        parent_key = "NO_EPIC_ASSIGNED"
                        parent_summary = "NO EPIC ASSIGNED"
            else:
                print(f"[JIRA Validation] Could not fetch parent {parent_key}")
                parent_key = "NO_EPIC_ASSIGNED"
                parent_summary = "NO EPIC ASSIGNED"
        
        if parent_key and parent_key != "NO_EPIC_ASSIGNED":
            parent_color = fetch_epic_color(parent_key)
        
        # Sprint info
        sprint_field = fields.get("customfield_10020")
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

def process_adf_node(node):
    """Process a single ADF node and return HTML or raw markdown for unsupported elements."""
    if not isinstance(node, dict):
        return clean_text(str(node))
    
    node_type = node.get("type", "")
    content = node.get("content", [])
    attrs = node.get("attrs", {})
    
    # Handle text nodes with marks (bold, italic, etc.)
    if node_type == "text":
        text = clean_text(node.get("text", ""))
        marks = node.get("marks", [])
        
        for mark in marks:
            mark_type = mark.get("type", "")
            if mark_type == "strong":
                text = f"<strong>{text}</strong>"
            elif mark_type == "em":
                text = f"<em>{text}</em>"
            elif mark_type == "code":
                text = f"<code>{text}</code>"
            elif mark_type == "link":
                href = mark.get("attrs", {}).get("href", "#")
                text = f'<a href="{href}" target="_blank">{text}</a>'
            else:
                # Unsupported mark - show as raw
                text = f"{text} [mark:{mark_type}]"
        
        return text
    
    # Handle paragraph nodes
    elif node_type == "paragraph":
        paragraph_content = []
        for child in content:
            paragraph_content.append(process_adf_node(child))
        text = "".join(paragraph_content).strip()
        return f"<p>{text}</p>" if text else ""
    
    # Handle lists
    elif node_type == "bulletList":
        list_items = []
        for item in content:
            if item.get("type") == "listItem":
                item_content = []
                for child in item.get("content", []):
                    item_content.append(process_adf_node(child))
                item_text = "".join(item_content).strip()
                if item_text:
                    # Remove <p> tags from list items for cleaner display
                    item_text = item_text.replace("<p>", "").replace("</p>", "")
                    list_items.append(f"<li>{item_text}</li>")
        return "<ul>" + "".join(list_items) + "</ul>" if list_items else ""
    
    elif node_type == "orderedList":
        list_items = []
        for item in content:
            if item.get("type") == "listItem":
                item_content = []
                for child in item.get("content", []):
                    item_content.append(process_adf_node(child))
                item_text = "".join(item_content).strip()
                if item_text:
                    # Remove <p> tags from list items for cleaner display
                    item_text = item_text.replace("<p>", "").replace("</p>", "")
                    list_items.append(f"<li>{item_text}</li>")
        return "<ol>" + "".join(list_items) + "</ol>" if list_items else ""
    
    # Handle code blocks
    elif node_type == "codeBlock":
        language = attrs.get("language", "")
        code_text = []
        for child in content:
            if child.get("type") == "text":
                code_text.append(child.get("text", ""))
        code = "".join(code_text)
        return f'<pre><code class="language-{language}">{clean_text(code)}</code></pre>'
    
    # Handle headings
    elif node_type == "heading":
        level = attrs.get("level", 1)
        heading_content = []
        for child in content:
            heading_content.append(process_adf_node(child))
        text = "".join(heading_content).strip()
        return f"<h{level}>{text}</h{level}>" if text else ""
    
    # Handle emojis
    elif node_type == "emoji":
        shortName = attrs.get("shortName", "")
        text = attrs.get("text", "")
        if text:
            return text  # Use the actual emoji character if available
        elif shortName:
            return f":{shortName}:"  # Fallback to :emoji_name: format
        else:
            return "[emoji]"
    
    # Handle mentions
    elif node_type == "mention":
        display_name = attrs.get("text", attrs.get("displayName", ""))
        user_id = attrs.get("id", "")
        if display_name:
            return f"@{display_name}"
        elif user_id:
            return f"@{user_id}"
        else:
            return "@[user]"
    
    # Handle tables (basic support)
    elif node_type == "table":
        table_rows = []
        for row in content:
            if row.get("type") == "tableRow":
                cells = []
                for cell in row.get("content", []):
                    if cell.get("type") in ["tableCell", "tableHeader"]:
                        cell_content = []
                        for child in cell.get("content", []):
                            cell_content.append(process_adf_node(child))
                        cell_text = "".join(cell_content).strip()
                        tag = "th" if cell.get("type") == "tableHeader" else "td"
                        cells.append(f"<{tag}>{cell_text}</{tag}>")
                if cells:
                    table_rows.append("<tr>" + "".join(cells) + "</tr>")
        return "<table>" + "".join(table_rows) + "</table>" if table_rows else ""
    
    # Handle hard breaks
    elif node_type == "hardBreak":
        return "<br/>"
    
    # Handle rules (horizontal lines)
    elif node_type == "rule":
        return "<hr/>"
    
    # For unsupported node types, show raw markdown
    else:
        # Try to extract text content if available
        if content:
            child_content = []
            for child in content:
                child_content.append(process_adf_node(child))
            text = "".join(child_content).strip()
            if text:
                return f"[{node_type}: {text}]"
        
        # Show node type and attributes as raw markdown
        attrs_str = ""
        if attrs:
            attr_parts = []
            for key, value in attrs.items():
                attr_parts.append(f"{key}={value}")
            attrs_str = f" ({', '.join(attr_parts)})" if attr_parts else ""
        
        return f"[{node_type}{attrs_str}]"

def process_jira_body(body):
    """Process a Jira comment/description body that can be either HTML, plain text, or ADF format."""
    if not body:
        return ""
    
    if isinstance(body, dict):
        # This is ADF (Atlassian Document Format)
        try:
            result = []
            for content in body.get("content", []):
                processed = process_adf_node(content)
                if processed:
                    result.append(processed)
            return "".join(result)
        except (KeyError, TypeError, Exception) as e:
            # If parsing fails completely, show raw JSON
            import json
            return f'<pre><code>[ADF Parse Error: {str(e)}]\n{json.dumps(body, indent=2)}</code></pre>'
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
        "fields": "summary,status,priority,description,comment,parent",
        "expand": "renderedFields"
    }

    try:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        fields = data.get("fields", {})
        rendered = data.get("renderedFields", {})

        # Check if this is a Review issue - if so, return parent details instead
        summary = fields.get("summary", "")
        if summary.startswith("Review -"):
            parent = fields.get("parent")
            if parent:
                parent_key = parent.get("key")
                if parent_key:
                    return get_issue_details(parent_key)

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

def fetch_issue_parent_info(issue_key: str) -> Optional[Dict[str, Any]]:
    """
    Fetch parent information for a specific JIRA issue.
    If the issue summary starts with 'Review -', returns grandparent instead of parent.
    
    Returns:
        Dict with parent_key, parent_summary, or None if no parent found
    """
    print(f"[DEBUG] fetch_issue_parent_info called for {issue_key}")
    if not issue_key:
        print(f"[DEBUG] No issue_key provided, returning None")
        return None

    headers = get_jira_headers()
    print(f"[DEBUG] Got JIRA headers, about to call _fetch_issue_details")
    
    # First, get the issue details including parent info
    issue_details = _fetch_issue_details(issue_key, headers)
    print(f"[DEBUG] _fetch_issue_details returned: {issue_details}")
    if not issue_details:
        print(f"Could not fetch details for issue {issue_key}")
        return None    # Return the parent info (Review handling is already done in _fetch_issue_details)
    parent_key = issue_details.get("parent_key")
    if parent_key:
        return {
            "parent_key": parent_key,
            "parent_summary": issue_details.get("parent_summary")
        }
    else:
        print(f"Issue {issue_key}: No parent found")
        return None


def fetch_jira_subtasks_for_parent(autor: str, parent_key: str) -> List[dict]:
    """
    Fetch sub-tasks for a specific parent issue, filtered by author.
    This supports hierarchical filtering where selecting a parent task (uloha) 
    shows only its child tasks in the JIRA dropdown.
    
    Args:
        autor: User email to filter sub-tasks by assignee
        parent_key: Parent issue key (e.g., "PROJ-123")
    
    Returns:
        List of sub-task dictionaries with keys: key, summary, assignee, etc.
    """
    try:
        url = f"{JIRA_URL}/rest/api/3/issue/picker"
        headers = get_jira_headers()
        
        # JQL to find sub-tasks of the parent issue assigned to the author
        # This includes both direct sub-tasks and sub-sub-tasks (for Review workflows)
        jql = f"""
        assignee = '{autor}' AND (
            parent = '{parent_key}' OR 
            parent in issuesWithParent('{parent_key}')
        )
        """
        
        params = {
            "query": "",
            "currentJQL": jql.strip(),
            "maxResults": 100,
            "showSubTasks": "true"
        }
        
        resp = requests.get(url, headers=headers, params=params)
        
        if resp.status_code == 410:
            # Fallback to direct API if picker is deprecated
            return _fetch_subtasks_direct_api(autor, parent_key)
        
        resp.raise_for_status()
        result = resp.json()
        sections = result.get('sections', [])
        
        # Collect issues from all sections
        subtasks = []
        for section in sections:
            for issue in section.get('issues', []):
                subtasks.append({
                    "key": issue.get('key'),
                    "summary": issue.get('summaryText', ''),
                    "assignee": issue.get('keyHtml', ''),  # May contain assignee info
                    "parent_key": None,  # Will be populated if needed
                    "parent_summary": None,
                    "parent_color": None,
                })
        
        print(f"Found {len(subtasks)} sub-tasks for parent {parent_key} assigned to {autor}")
        return subtasks
        
    except Exception as e:
        print(f"Error fetching sub-tasks for parent {parent_key}: {e}")
        return []


def _fetch_subtasks_direct_api(autor: str, parent_key: str) -> List[dict]:
    """
    Fallback method using direct JIRA API for sub-task queries.
    Used when the issue picker endpoint is not available.
    """
    try:
        url = f"{JIRA_URL}/rest/api/3/search"
        headers = get_jira_headers()
        
        # JQL to find sub-tasks with parent hierarchy support
        jql = f"""
        assignee = '{autor}' AND (
            parent = '{parent_key}' OR 
            parent in issuesWithParent('{parent_key}')
        )
        ORDER BY key ASC
        """
        
        params = {
            "jql": jql.strip(),
            "maxResults": 100,
            "fields": "key,summary,parent,assignee"
        }
        
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        
        result = resp.json()
        issues = result.get('issues', [])
        
        subtasks = []
        for issue in issues:
            fields = issue.get('fields', {})
            subtasks.append({
                "key": issue.get('key'),
                "summary": fields.get('summary', ''),
                "assignee": fields.get('assignee', {}).get('emailAddress', ''),
                "parent_key": None,
                "parent_summary": None, 
                "parent_color": None,
            })
        
        print(f"Found {len(subtasks)} sub-tasks via direct API for parent {parent_key}")
        return subtasks
        
    except Exception as e:
        print(f"Direct API sub-task fetch failed for parent {parent_key}: {e}")
        return []


def debug_jira_issue_visibility(issue_key: str) -> dict:
    """
    Debug why a specific JIRA issue might not be showing up in the regular query.
    Tests various JQL queries to understand the issue's status.
    """
    results = {
        "issue_key": issue_key,
        "tests": {}
    }
    
    try:
        # Test 1: Check if issue exists at all
        url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}"
        headers = get_jira_headers()
        resp = requests.get(url, headers=headers)
        
        if resp.status_code == 200:
            issue_data = resp.json()
            fields = issue_data.get('fields', {})
            
            results["tests"]["issue_exists"] = True
            results["issue_summary"] = fields.get('summary', 'N/A')
            results["assignee"] = fields.get('assignee', {}).get('emailAddress', 'Unassigned') if fields.get('assignee') else 'Unassigned'
            results["status"] = fields.get('status', {}).get('name', 'N/A')
            
            # Check sprint information
            sprint_field = fields.get('customfield_10020', [])  # Sprint field
            if sprint_field:
                results["sprints"] = [sprint for sprint in sprint_field if isinstance(sprint, str)]
            else:
                results["sprints"] = []
            
            # Check if updated recently
            updated = fields.get('updated', '')
            results["updated"] = updated
            
        else:
            results["tests"]["issue_exists"] = False
            results["error"] = f"Issue not found: {resp.status_code}"
            return results
            
        # Test 2: Test different JQL queries
        test_queries = [
            f"key = '{issue_key}'",
            f"key = '{issue_key}' AND assignee = 'palko@metaapp.sk'",
            f"assignee = 'palko@metaapp.sk' AND sprint in openSprints()",
            f"assignee = 'palko@metaapp.sk' AND sprint in futureSprints()",
            f"assignee = 'palko@metaapp.sk' AND updated >= -1d",
            f"assignee = 'palko@metaapp.sk' AND (sprint in openSprints() OR sprint in futureSprints() OR updated >= -1d)"
        ]
        
        for i, jql in enumerate(test_queries):
            try:
                search_url = f"{JIRA_URL}/rest/api/3/search"
                params = {
                    "jql": jql,
                    "maxResults": 100,
                    "fields": "key,summary"
                }
                
                search_resp = requests.get(search_url, headers=headers, params=params)
                if search_resp.status_code == 200:
                    search_data = search_resp.json()
                    issues = search_data.get('issues', [])
                    found = any(issue['key'] == issue_key for issue in issues)
                    results["tests"][f"query_{i+1}"] = {
                        "jql": jql,
                        "found": found,
                        "total_results": len(issues)
                    }
                else:
                    results["tests"][f"query_{i+1}"] = {
                        "jql": jql,
                        "error": f"Query failed: {search_resp.status_code}"
                    }
                    
            except Exception as e:
                results["tests"][f"query_{i+1}"] = {
                    "jql": jql,
                    "error": str(e)
                }
        
        return results
        
    except Exception as e:
        results["error"] = str(e)
        return results
