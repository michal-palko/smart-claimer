// Jira Issue Widget
class JiraWidget {
    constructor(jiraField) {
        this.jiraField = jiraField;
        this.widget = null;
        this.currentIssueKey = null;
        this.searchBtn = null;
        this.init();
    }

    init() {
        // Create widget container
        this.widget = document.createElement('div');
        this.widget.className = 'jira-widget';
        
        // Create close button
        const closeButton = document.createElement('button');
        closeButton.className = 'jira-close';
        closeButton.setAttribute('aria-label', 'Close');
        closeButton.innerHTML = '×';
        closeButton.onclick = () => this.hideWidget();
        
        // Create content container
        const contentContainer = document.createElement('div');
        contentContainer.className = 'jira-content';
        
        // Add button and content to widget
        this.widget.appendChild(closeButton);
        this.widget.appendChild(contentContainer);
        
        // Find the input-clear-wrapper parent
        const wrapper = this.jiraField.closest('.input-clear-wrapper');
        if (wrapper) {
            // Create info button
            this.searchBtn = document.createElement('button');
            this.searchBtn.type = 'button';
            this.searchBtn.className = 'jira-search-btn';
            this.searchBtn.innerHTML = '<i>i</i>';
            this.searchBtn.setAttribute('aria-label', 'Show JIRA details');
            this.searchBtn.onclick = () => this.toggleJiraInfo();
            
            // Add button next to input
            wrapper.appendChild(this.searchBtn);
        }
        
        // Add widget to document body
        document.body.appendChild(this.widget);
    }
    
    async toggleJiraInfo() {
        if (this.widget.classList.contains('active')) {
            // If widget is visible, hide it
            this.hideWidget();
        } else {
            // If widget is hidden, fetch and show info
            this.widget.style.display = 'block';
            this.searchBtn.classList.add('active');
            // Allow DOM to update before animation
            requestAnimationFrame(() => {
                this.widget.classList.add('active');
            });
            await this.fetchJiraInfo();
        }
    }

    async fetchJiraInfo() {
        const fieldValue = this.jiraField.value.trim();
        // Extract just the JIRA code (e.g., "CARTV-123" from "CARTV-123: Some description")
        const match = fieldValue.match(/^([A-Z]+-\d+)/);
        const issueKey = match ? match[1] : null;
        
        // We don't need to check again or show an alert here since we've already checked in toggleJiraInfo
        // Just use the issue key directly
        this.currentIssueKey = issueKey;

        // Show loading state
        const content = this.widget.querySelector('.jira-content');
        content.innerHTML = '<div class="jira-details">Loading JIRA information...</div>';
        
        try {
            const response = await fetch(`/jira-issue-details/${issueKey}`);
            if (!response.ok) {
                const errorData = await response.text();
                throw new Error(errorData || 'Failed to fetch JIRA issue');
            }
            const issue = await response.json();
            this.renderWidget(issue);
        } catch (error) {
            this.renderError(error);
        }
    }

    renderWidget(issue) {
        const statusCategory = this.getStatusCategory(issue.status?.statusCategory?.key);
        const priorityIcon = this.getPriorityIcon(issue.priority?.name);

        const content = this.widget.querySelector('.jira-content');
        content.innerHTML = `
            <div class="jira-widget-header">
                <a href="${issue.baseUrl}/browse/${issue.key}" class="jira-widget-key" target="_blank">${issue.key}</a>
                <span class="jira-status status-${statusCategory}">${issue.status?.name || 'Unknown'}</span>
                <span class="jira-priority">${priorityIcon}</span>
            </div>
            <div class="jira-summary">${issue.summary || ''}</div>
            ${issue.description ? `
                <div class="jira-description">
                    ${issue.description}
                </div>
            ` : ''}
            ${this.renderComments(issue.comments)}
        `;

        // Update toggle text based on state
        this.updateToggleText();
    }

    renderError(error) {
        const content = this.widget.querySelector('.jira-content');
        content.innerHTML = `
            <div class="jira-details error">
                <strong>Error fetching ${this.currentIssueKey}:</strong><br>
                ${error.message}
            </div>
        `;
    }

    renderComments(comments = []) {
        if (!comments.length) return '';

        return `
            <div class="jira-comments">
                <h3>Comments</h3>
                ${comments.sort((a, b) => new Date(b.created) - new Date(a.created))
                    .map(comment => `
                        <div class="jira-comment">
                            <div class="jira-comment-header">
                                <img src="${comment.author.avatarUrl || ''}" 
                                     alt="${comment.author.displayName}"
                                     class="jira-comment-avatar"
                                     onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22><circle fill=%22%23DDD%22 cx=%2212%22 cy=%2212%22 r=%2212%22/></svg>'">
                                <span class="jira-comment-author">${comment.author.displayName}</span>
                                <span class="jira-comment-time">${this.formatRelativeTime(new Date(comment.created))}</span>
                            </div>
                            <div class="jira-comment-body">
                                ${comment.body}
                            </div>
                        </div>
                    `).join('')}
            </div>
        `;
    }

    getStatusCategory(categoryKey) {
        const map = {
            'done': 'green',
            'in-progress': 'yellow',
            'to-do': 'grey'
        };
        return map[categoryKey] || 'grey';
    }

    getPriorityIcon(priority) {
        const map = {
            'Highest': '🔺',
            'High': '🔺',
            'Medium': '⬆️',
            'Low': '⬇️',
            'Lowest': '⬇️'
        };
        return map[priority] || '⬆️';
    }

    formatRelativeTime(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffSec = Math.floor(diffMs / 1000);
        const diffMin = Math.floor(diffSec / 60);
        const diffHour = Math.floor(diffMin / 60);
        const diffDay = Math.floor(diffHour / 24);
        const diffMonth = Math.floor(diffDay / 30);
        const diffYear = Math.floor(diffMonth / 12);

        if (diffYear > 0) return `${diffYear}y ago`;
        if (diffMonth > 0) return `${diffMonth}mo ago`;
        if (diffDay > 0) return `${diffDay}d ago`;
        if (diffHour > 0) return `${diffHour}h ago`;
        if (diffMin > 0) return `${diffMin}m ago`;
        return 'just now';
    }

    updateToggleText() {
        const toggle = this.widget.querySelector('.jira-toggle');
        if (!toggle) return;

        const isCollapsed = this.widget.classList.contains('collapsed');
        toggle.innerHTML = `
            <span class="toggle-text">${isCollapsed ? 'Show details' : 'Hide details'}</span>
            <span class="toggle-icon">${isCollapsed ? '▼' : '▲'}</span>
        `;
    }

    escapeHtml(html) {
        const div = document.createElement('div');
        div.textContent = html;
        return div.innerHTML;
    }

    hideWidget() {
        this.widget.classList.remove('active');
        this.searchBtn.classList.remove('active');
        
        // Wait for transition to complete before hiding
        this.widget.addEventListener('transitionend', () => {
            if (!this.widget.classList.contains('active')) {
                this.widget.style.display = 'none';
            }
        }, { once: true });
    }
}

// Initialize widget when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Initialize for each Jira field (handle both edit form and main form)
    ['jira', 'editJira'].forEach(id => {
        const field = document.getElementById(id);
        if (field) {
            new JiraWidget(field);
        }
    });
});
