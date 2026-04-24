/**
 * OpsTron Dashboard - JavaScript Application
 * OAuth-based session flow. All authenticated calls use:
 *   Authorization: Bearer <ops_token>  (session token from GitHub OAuth)
 */

// ===========================================
// Configuration
// ===========================================
const CONFIG = {
    AGENT_URL: 'https://opstron.onrender.com',
};

// ===========================================
// State Management
// ===========================================
const state = {
    opsToken: localStorage.getItem('ops_token') || '',
    rcaReports: [],
    user: null,     // populated from /auth/me
};

// ===========================================
// DOM Elements
// ===========================================
const elements = {
    navItems: document.querySelectorAll('.nav-item'),
    sections: document.querySelectorAll('.section'),
    pageTitle: document.getElementById('page-title'),
    agentStatus: document.getElementById('agent-status'),
    statErrors: document.getElementById('stat-errors'),
    statCommits: document.getElementById('stat-commits'),
    statStatus: document.getElementById('stat-status'),
    rcaReports: document.getElementById('rca-reports'),
    refreshBtn: document.getElementById('refresh-btn'),
    triggerErrorBtn2: document.getElementById('trigger-error-btn-2'),
};

// ===========================================
// Navigation
// ===========================================
function initNavigation() {
    elements.navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const section = item.dataset.section;

            elements.navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            elements.sections.forEach(sec => sec.classList.add('hidden'));
            document.getElementById(`section-${section}`).classList.remove('hidden');

            const titles = {
                dashboard: 'Dashboard',
                repo: 'Repository',
                errors: 'Error Logs',
                runbooks: 'Runbooks',
            };
            elements.pageTitle.textContent = titles[section] || section;
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
// Auth Helper — all API calls go through here
// ===========================================
function authHeaders() {
    return {
        'Authorization': `Bearer ${state.opsToken}`,
        'Content-Type': 'application/json',
    };
}

// ===========================================
// Logout
// ===========================================
async function logout() {
    try {
        await fetch(`${CONFIG.AGENT_URL}/auth/logout`, {
            method: 'POST',
            headers: authHeaders(),
        });
    } catch (_) { /* best-effort */ }

    localStorage.removeItem('ops_token');
    localStorage.removeItem('ops_agent_key');
    localStorage.removeItem('setup_done');
    window.location.href = 'login.html';
}

// ===========================================
// User Profile — fetches /auth/me once on load
// ===========================================
async function loadUserProfile() {
    if (!state.opsToken) return;

    try {
        const res = await fetch(`${CONFIG.AGENT_URL}/auth/me`, {
            headers: authHeaders(),
        });

        if (res.status === 401) {
            // Session expired — send back to login
            localStorage.removeItem('ops_token');
            window.location.href = 'login.html';
            return;
        }
        if (!res.ok) return;

        const data = await res.json();
        state.user = data.user;

        // Show user panel in sidebar
        const panel = document.getElementById('user-profile');
        if (panel) panel.style.display = 'block';

        const avatarEl  = document.getElementById('user-avatar');
        const loginEl   = document.getElementById('user-login');
        if (avatarEl && state.user.avatar_url) avatarEl.src = state.user.avatar_url;
        if (loginEl  && state.user.login)      loginEl.textContent = state.user.login;

        // Persist agent key for agent status checks
        if (state.user.agent_api_key) {
            localStorage.setItem('ops_agent_key', state.user.agent_api_key);
        }

        // Populate Repository section
        populateRepoSection();

    } catch (e) {
        console.warn('Could not load user profile:', e);
    }
}

// ===========================================
// Repository Section
// ===========================================
function populateRepoSection() {
    const user = state.user;
    if (!user) return;

    // Show GitHub user card
    const ghCard = document.getElementById('gh-user-card');
    if (ghCard) ghCard.style.display = 'block';

    const bigAvatar  = document.getElementById('gh-avatar-big');
    const nameEl     = document.getElementById('gh-name');
    const loginEl    = document.getElementById('gh-login-display');
    const emailEl    = document.getElementById('gh-email-display');
    const apiKeyEl   = document.getElementById('api-key-display');

    if (bigAvatar && user.avatar_url) bigAvatar.src = user.avatar_url;
    if (nameEl)   nameEl.textContent  = user.name  || user.login;
    if (loginEl)  loginEl.textContent = `@${user.login}`;
    if (emailEl && user.email) emailEl.textContent = user.email;
    if (apiKeyEl && user.agent_api_key) {
        apiKeyEl.textContent = user.agent_api_key;
    }

    // Show connected repo from localStorage (set during onboarding)
    const connectedRepo = localStorage.getItem('connected_repo') || '';
    const repoInfoEl = document.getElementById('connected-repo-info');
    if (repoInfoEl && connectedRepo) {
        repoInfoEl.innerHTML = `
            <div style="display:flex;align-items:center;gap:14px;padding:12px;background:var(--bg-tertiary);border-radius:10px;">
                <span style="font-size:1.5rem;">📂</span>
                <div>
                    <div style="font-weight:600;color:var(--text-primary);">${escapeHtml(connectedRepo)}</div>
                    <div style="font-size:.8rem;color:var(--text-muted);margin-top:2px;">Webhook active — OpsTron monitors every push</div>
                </div>
                <a href="onboarding.html" class="btn btn-secondary btn-sm" style="margin-left:auto;">Change →</a>
            </div>
        `;
    }
}

function copyApiKey() {
    const key = document.getElementById('api-key-display')?.textContent || '';
    if (!key || key === '—') return;
    navigator.clipboard.writeText(key);
    showToast('API key copied!', 'success');
}

// ===========================================
// Agent Status
// ===========================================
async function checkAgentStatus() {
    const apiKey = localStorage.getItem('ops_agent_key') || '';

    // 1. Verify backend is reachable
    let backendOk = false;
    try {
        const hRes = await fetch(`${CONFIG.AGENT_URL}/health`);
        backendOk = hRes.ok;
    } catch (_) {}

    if (!backendOk) {
        _setAgentBadge('offline', '🔴 Offline', 'Offline');
        return false;
    }

    // 2. If user has agent key, check Docker agent connection
    if (apiKey) {
        try {
            const sRes = await fetch(`${CONFIG.AGENT_URL}/agent/status`, {
                headers: { 'X-API-Key': apiKey }
            });
            if (sRes.ok) {
                const data = await sRes.json();
                if (data.status === 'connected' || data.agent_connected === true) {
                    const containers = data.monitored_containers?.length ?? 0;
                    _setAgentBadge('connected',
                        `🟢 Agent Connected`,
                        `Connected · ${containers} container${containers !== 1 ? 's' : ''}`);
                    if (elements.statStatus) elements.statStatus.textContent = 'Connected';
                    return true;
                }
            }
        } catch (_) {}
    }

    // 3. Backend up but agent not yet connected
    _setAgentBadge('backend', '🟡 Backend Online', 'Agent not connected');
    return false;
}

function _setAgentBadge(agentState, sidebarLabel, statLabel) {
    const el = elements.agentStatus;
    el.classList.remove('online', 'offline', 'connecting');
    el.classList.add(
        agentState === 'connected' ? 'online' :
        agentState === 'offline'   ? 'offline' : 'connecting'
    );
    el.innerHTML = `<span class="status-dot"></span><span>${sidebarLabel}</span>`;
    if (elements.statStatus) elements.statStatus.textContent = statLabel;
}

// ===========================================
// RCA History
// ===========================================
async function fetchRCAHistory() {
    if (!state.opsToken) return;

    try {
        const response = await fetch(`${CONFIG.AGENT_URL}/rca-history`, {
            headers: authHeaders(),
        });

        if (response.status === 401) {
            // Token expired — but don't redirect, just show empty
            return;
        }

        if (!response.ok) throw new Error('Failed to fetch RCA history');

        const data = await response.json();

        if (data.reports && data.reports.length > 0) {
            state.rcaReports = data.reports.map(report => ({
                id: report.id,
                service: report.service,
                root_cause: report.rca_report?.root_cause || report.error || 'Unknown',
                confidence: report.rca_report?.confidence || 'medium',
                analyzed_at: report.analyzed_at,
                processing_time_ms: report.processing_time_ms,
                recommended_actions:
                    report.rca_report?.recommended_actions ||
                    report.rca_report?.recommendations ||
                    ['Review the error details', 'Check recent code changes'],
            }));
            renderRCAReports();
            if (elements.statErrors)  elements.statErrors.textContent  = state.rcaReports.length;
            if (elements.statCommits) elements.statCommits.textContent = state.rcaReports.length;
            showToast(`Loaded ${data.reports.length} RCA report(s)`, 'success');
        }
    } catch (error) {
        console.error('Failed to fetch RCA history:', error);
    }
}

function renderRCAReports() {
    if (!elements.rcaReports) return;

    if (state.rcaReports.length === 0) {
        elements.rcaReports.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📋</span>
                <p>No RCA reports yet. Push a commit or trigger an error to see AI analysis.</p>
            </div>
        `;
        return;
    }

    elements.rcaReports.innerHTML = state.rcaReports.map(report => `
        <div class="report-item">
            <div class="report-header">
                <span class="report-service">🔧 ${escapeHtml(report.service)}</span>
                <span class="report-confidence ${report.confidence}">${report.confidence} confidence</span>
            </div>
            <div class="report-cause">
                <strong>Root Cause:</strong> ${escapeHtml(report.root_cause)}
            </div>
            <div>
                <strong style="font-size:13px;color:var(--text-secondary);">Recommended Actions:</strong>
                <ul class="report-actions-list">
                    ${report.recommended_actions.map(a => `<li>${escapeHtml(a)}</li>`).join('')}
                </ul>
            </div>
            <div style="margin-top:12px;font-size:12px;color:var(--text-muted);">
                Analyzed at: ${formatDate(report.analyzed_at)}
            </div>
        </div>
    `).join('');
}

// ===========================================
// Utilities
// ===========================================
function formatDate(dateStr) {
    return new Date(dateStr).toLocaleString('en-US', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
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

    // 1. Capture token from URL (if redirected from auth flow)
    const urlParams = new URLSearchParams(window.location.search);
    const tokenFromUrl = urlParams.get('token');
    if (tokenFromUrl) {
        localStorage.setItem('ops_token', tokenFromUrl);
        state.opsToken = tokenFromUrl;
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // 2. Guard — must be logged in
    if (!state.opsToken) {
        window.location.href = 'login.html';
        return;
    }

    // 3. If somehow on login page while logged in, go to onboarding
    if (window.location.pathname.includes('login.html')) {
        window.location.href = 'onboarding.html';
        return;
    }

    // 4. Set up navigation
    initNavigation();

    // 5. Load user profile (also populates repo section)
    await loadUserProfile();

    // 6. Check agent status
    await checkAgentStatus();

    // 7. Load existing RCA reports
    await fetchRCAHistory();

    // 8. Refresh button
    if (elements.refreshBtn) {
        elements.refreshBtn.addEventListener('click', async () => {
            await checkAgentStatus();
            await fetchRCAHistory();
            showToast('Dashboard refreshed', 'success');
        });
    }

    // 9. Error trigger button (section-errors)
    elements.triggerErrorBtn2?.addEventListener('click', triggerTestError);

    // 10. Periodic status check every 30s
    setInterval(checkAgentStatus, 30000);

    localStorage.setItem('setup_done', 'true');
    console.log('✅ OpsTron Dashboard ready!');
}

async function triggerTestError() {
    showToast('Triggering test error...', 'info');
    setTimeout(fetchRCAHistory, 3000);
}

// ===========================================
// Start
// ===========================================
document.addEventListener('DOMContentLoaded', init);

// Expose for onclick handlers
window.logout    = logout;
window.copyApiKey = copyApiKey;
window.fetchRCAHistory = fetchRCAHistory;
