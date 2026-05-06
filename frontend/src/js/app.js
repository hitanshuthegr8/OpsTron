/**
 * OpsTron Dashboard - JavaScript Application
 * Handles GitHub integration, API calls, and UI interactions
 */

// ===========================================
// Configuration
// ===========================================
const CONFIG = {
    AGENT_URL: 'http://localhost:8001',
    DEMO_BACKEND_URL: 'http://localhost:8000',
    GITHUB_API: 'https://api.github.com'
};

// ===========================================
// State Management
// ===========================================
const state = {
    githubToken: localStorage.getItem('github_token') || '',
    githubRepo: localStorage.getItem('github_repo') || '',
    rcaReports: [],
    errorLogs: [],
    commits: []
};

// ===========================================
// DOM Elements
// ===========================================
const elements = {
    navItems: document.querySelectorAll('.nav-item'),
    sections: document.querySelectorAll('.section'),
    pageTitle: document.getElementById('page-title'),
    agentStatus: document.getElementById('agent-status'),

    // Stats
    statErrors: document.getElementById('stat-errors'),
    statCommits: document.getElementById('stat-commits'),
    statStatus: document.getElementById('stat-status'),

    // GitHub
    githubForm: document.getElementById('github-form'),
    githubToken: document.getElementById('github-token'),
    githubRepo: document.getElementById('github-repo'),
    githubStatus: document.getElementById('github-status'),
    toggleToken: document.getElementById('toggle-token'),
    testGithubBtn: document.getElementById('test-github-btn'),
    fetchCommitsBtn: document.getElementById('fetch-commits-btn'),
    commitsList: document.getElementById('commits-list'),

    // Reports
    rcaReports: document.getElementById('rca-reports'),

    // Buttons
    refreshBtn: document.getElementById('refresh-btn'),
    triggerErrorBtn: document.getElementById('trigger-error-btn'),
    triggerErrorBtn2: document.getElementById('trigger-error-btn-2')
};

// ===========================================
// Navigation
// ===========================================
function initNavigation() {
    elements.navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const section = item.dataset.section;

            // Update nav items
            elements.navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            // Update sections
            elements.sections.forEach(sec => sec.classList.add('hidden'));
            document.getElementById(`section-${section}`).classList.remove('hidden');

            // Update title
            const titles = {
                dashboard: 'Dashboard',
                github: 'GitHub Configuration',
                errors: 'Error Logs',
                runbooks: 'Runbooks'
            };
            elements.pageTitle.textContent = titles[section];
        });
    });
}

// ===========================================
// Toast Notifications
// ===========================================
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ===========================================
// Agent Status Check
// ===========================================
async function checkAgentStatus() {
    try {
        const response = await fetch(`${CONFIG.AGENT_URL}/health`);
        const data = await response.json();

        elements.agentStatus.classList.remove('offline');
        elements.agentStatus.classList.add('online');
        elements.agentStatus.innerHTML = `
            <span class="status-dot"></span>
            <span>Agent: Online</span>
        `;
        elements.statStatus.textContent = 'Online';

        return true;
    } catch (error) {
        elements.agentStatus.classList.remove('online');
        elements.agentStatus.classList.add('offline');
        elements.agentStatus.innerHTML = `
            <span class="status-dot"></span>
            <span>Agent: Offline</span>
        `;
        elements.statStatus.textContent = 'Offline';

        return false;
    }
}

// ===========================================
// GitHub Integration
// ===========================================
function initGitHub() {
    // Load saved values
    if (state.githubToken) {
        elements.githubToken.value = state.githubToken;
        elements.githubStatus.textContent = 'Token Saved';
        elements.githubStatus.classList.add('success');
    }
    if (state.githubRepo) {
        elements.githubRepo.value = state.githubRepo;
    }

    // Toggle token visibility
    elements.toggleToken.addEventListener('click', () => {
        const type = elements.githubToken.type === 'password' ? 'text' : 'password';
        elements.githubToken.type = type;
        elements.toggleToken.textContent = type === 'password' ? '👁️' : '🙈';
    });

    // Form submission
    elements.githubForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const token = elements.githubToken.value.trim();
        const repo = elements.githubRepo.value.trim();

        if (!token) {
            showToast('Please enter a GitHub token', 'error');
            return;
        }

        // Save to localStorage
        localStorage.setItem('github_token', token);
        localStorage.setItem('github_repo', repo);
        state.githubToken = token;
        state.githubRepo = repo;

        // Update agent config
        try {
            await updateAgentConfig(token, repo);
            elements.githubStatus.textContent = 'Connected';
            elements.githubStatus.classList.remove('error');
            elements.githubStatus.classList.add('success');
            showToast('GitHub configuration saved!', 'success');

            // Fetch commits if repo is set
            if (repo) {
                fetchCommits();
            }
        } catch (error) {
            showToast('Failed to save configuration', 'error');
        }
    });

    // Test connection
    elements.testGithubBtn.addEventListener('click', testGitHubConnection);

    // Fetch commits button
    elements.fetchCommitsBtn.addEventListener('click', fetchCommits);
}

async function updateAgentConfig(token, repo) {
    // This would update the agent configuration
    // For now, we'll store it locally and use it in API calls
    console.log('Config updated:', { token: token.slice(0, 10) + '...', repo });
}

async function testGitHubConnection() {
    const token = elements.githubToken.value.trim();

    if (!token) {
        showToast('Please enter a GitHub token first', 'error');
        return;
    }

    elements.testGithubBtn.innerHTML = '<span class="loading"></span> Testing...';
    elements.testGithubBtn.disabled = true;

    try {
        const response = await fetch(`${CONFIG.GITHUB_API}/user`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Accept': 'application/vnd.github.v3+json'
            }
        });

        if (response.ok) {
            const user = await response.json();
            showToast(`Connected as ${user.login}!`, 'success');
            elements.githubStatus.textContent = `Connected (${user.login})`;
            elements.githubStatus.classList.add('success');
        } else {
            throw new Error('Invalid token');
        }
    } catch (error) {
        showToast('GitHub connection failed. Check your token.', 'error');
        elements.githubStatus.textContent = 'Connection Failed';
        elements.githubStatus.classList.add('error');
    } finally {
        elements.testGithubBtn.innerHTML = 'Test Connection';
        elements.testGithubBtn.disabled = false;
    }
}

async function fetchCommits() {
    const token = state.githubToken;
    const repo = state.githubRepo || elements.githubRepo.value.trim();

    if (!token) {
        showToast('Please configure GitHub token first', 'error');
        return;
    }

    if (!repo) {
        showToast('Please enter a repository (owner/repo)', 'error');
        return;
    }

    // Validate repo format: must be "owner/repo"
    if (!repo.includes('/') || repo.split('/').length !== 2) {
        showToast('Repository must be in format: owner/repo (e.g., microsoft/vscode)', 'error');
        elements.commitsList.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">⚠️</span>
                <p><strong>Invalid repository format!</strong></p>
                <p style="font-size: 13px; margin-top: 8px;">
                    Please use: <code style="background: rgba(99,102,241,0.2); padding: 4px 8px; border-radius: 4px;">owner/repo</code>
                </p>
                <p style="font-size: 12px; color: var(--text-muted); margin-top: 8px;">
                    Examples: microsoft/vscode, hitanshuthegr8/OpsTron
                </p>
            </div>
        `;
        return;
    }

    elements.fetchCommitsBtn.innerHTML = '<span class="loading"></span> Fetching...';
    elements.fetchCommitsBtn.disabled = true;

    try {
        const response = await fetch(`${CONFIG.GITHUB_API}/repos/${repo}/commits?per_page=10`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Accept': 'application/vnd.github.v3+json'
            }
        });

        if (!response.ok) {
            throw new Error(`GitHub API error: ${response.status}`);
        }

        const commits = await response.json();
        state.commits = commits;

        renderCommits(commits);
        elements.statCommits.textContent = commits.length;
        showToast(`Fetched ${commits.length} commits`, 'success');

    } catch (error) {
        console.error('Failed to fetch commits:', error);
        showToast('Failed to fetch commits. Check repo name.', 'error');
        elements.commitsList.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">❌</span>
                <p>Failed to fetch commits: ${error.message}</p>
            </div>
        `;
    } finally {
        elements.fetchCommitsBtn.innerHTML = 'Fetch Commits';
        elements.fetchCommitsBtn.disabled = false;
    }
}

function renderCommits(commits) {
    if (!commits || commits.length === 0) {
        elements.commitsList.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📝</span>
                <p>No commits found</p>
            </div>
        `;
        return;
    }

    elements.commitsList.innerHTML = commits.map(commit => `
        <div class="commit-item">
            <div class="commit-header">
                <span class="commit-sha">${commit.sha.slice(0, 7)}</span>
                <span class="commit-date">${formatDate(commit.commit.author.date)}</span>
            </div>
            <div class="commit-message">${escapeHtml(commit.commit.message.split('\n')[0])}</div>
            <div class="commit-author">by ${commit.commit.author.name}</div>
        </div>
    `).join('');
}

// ===========================================
// Error Triggering & RCA
// ===========================================
async function triggerTestError() {
    showToast('Triggering test error...', 'info');

    try {
        const response = await fetch(`${CONFIG.DEMO_BACKEND_URL}/trigger-error`);
        // This will fail with 500, which is expected
    } catch (error) {
        // Expected - error was triggered
    }

    showToast('Error triggered! Waiting for RCA analysis...', 'warning');
    state.errorLogs.push({
        time: new Date().toISOString(),
        level: 'ERROR',
        message: 'ValueError: This is a test error for MVP3 demonstration'
    });
    elements.statErrors.textContent = state.errorLogs.length;

    // Wait a bit and check for new RCA report
    setTimeout(checkForNewRCA, 5000);
}

async function checkForNewRCA() {
    showToast('Checking for RCA results...', 'info');

    // In a real implementation, we'd poll the agent for results
    // For now, add a sample report
    const mockReport = {
        id: Date.now(),
        service: 'checkout-api',
        root_cause: 'ValueError triggered in test endpoint',
        confidence: 'medium',
        analyzed_at: new Date().toISOString(),
        recommended_actions: [
            'Check input validation',
            'Review error handling logic',
            'Add proper exception handling'
        ]
    };

    state.rcaReports.unshift(mockReport);
    renderRCAReports();
    showToast('RCA analysis completed!', 'success');
}

function renderRCAReports() {
    if (state.rcaReports.length === 0) {
        elements.rcaReports.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📋</span>
                <p>No RCA reports yet. Trigger an error to see analysis.</p>
                <button class="btn btn-primary" onclick="triggerTestError()">Trigger Test Error</button>
            </div>
        `;
        return;
    }

    elements.rcaReports.innerHTML = state.rcaReports.map(report => `
        <div class="report-item">
            <div class="report-header">
                <span class="report-service">🔧 ${report.service}</span>
                <span class="report-confidence ${report.confidence}">${report.confidence} confidence</span>
            </div>
            <div class="report-cause">
                <strong>Root Cause:</strong> ${escapeHtml(report.root_cause)}
            </div>
            <div>
                <strong style="font-size: 13px; color: var(--text-secondary);">Recommended Actions:</strong>
                <ul class="report-actions-list">
                    ${report.recommended_actions.map(action => `<li>${escapeHtml(action)}</li>`).join('')}
                </ul>
            </div>
            <div style="margin-top: 12px; font-size: 12px; color: var(--text-muted);">
                Analyzed at: ${formatDate(report.analyzed_at)}
            </div>
        </div>
    `).join('');
}

// ===========================================
// Utility Functions
// ===========================================
function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===========================================
// Initialization
// ===========================================
async function init() {
    console.log('🚀 OpsTron Dashboard initializing...');

    // Initialize components
    initNavigation();
    initGitHub();

    // Check agent status
    await checkAgentStatus();

    // Set up refresh button
    elements.refreshBtn.addEventListener('click', async () => {
        await checkAgentStatus();
        if (state.githubRepo) {
            await fetchCommits();
        }
        showToast('Dashboard refreshed', 'success');
    });

    // Set up error trigger buttons
    elements.triggerErrorBtn?.addEventListener('click', triggerTestError);
    elements.triggerErrorBtn2?.addEventListener('click', triggerTestError);

    // Periodic status check
    setInterval(checkAgentStatus, 30000);

    // Render any existing reports
    renderRCAReports();

    console.log('✅ OpsTron Dashboard ready!');
}

// Start the application
document.addEventListener('DOMContentLoaded', init);

// Expose functions globally for onclick handlers
window.triggerTestError = triggerTestError;
