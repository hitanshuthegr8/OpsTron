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
// Setup Banner — shown when no repo connected
// ===========================================
function showSetupBanner() {
    const dashboard = document.getElementById('section-dashboard');
    if (!dashboard) return;
    if (document.getElementById('setup-banner')) return; // already shown

    const banner = document.createElement('div');
    banner.id = 'setup-banner';
    banner.style.cssText = `
        background: linear-gradient(135deg, rgba(99,102,241,.2), rgba(139,92,246,.15));
        border: 1px solid rgba(99,102,241,.4);
        border-radius: 14px;
        padding: 20px 24px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
    `;
    banner.innerHTML = `
        <div style="display:flex;align-items:center;gap:16px;">
            <span style="font-size:2rem;">🚀</span>
            <div>
                <div style="font-weight:600;color:var(--text-primary);font-size:1rem;margin-bottom:4px;">
                    Complete your setup — connect a repository
                </div>
                <div style="font-size:.875rem;color:var(--text-secondary);">
                    OpsTron needs a GitHub repo to watch. Connect one and we'll install the webhook automatically.
                </div>
            </div>
        </div>
        <a href="onboarding.html" class="btn btn-primary" style="white-space:nowrap;flex-shrink:0;">
            Connect Repo →
        </a>
    `;
    dashboard.insertBefore(banner, dashboard.firstChild);
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

        if (response.status === 401) return;
        if (!response.ok) throw new Error('Failed to fetch RCA history');

        const data = await response.json();

        // Store full raw objects — modal needs every field
        state.rcaReports = data.reports || [];
        renderRCAReports();

        if (state.rcaReports.length > 0) {
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
            </div>`;
        return;
    }

    elements.rcaReports.innerHTML = state.rcaReports.map((report, idx) => {
        const rca          = report.rca_report || {};
        const confidence   = (rca.confidence  || 'medium').toLowerCase();
        const rootCause    = rca.root_cause   || report.error || 'Unknown root cause';
        const service      = report.service   || 'Unknown Service';
        const env          = report.environment || report.env || 'production';
        const analyzedAt   = report.analyzed_at;
        const procMs       = report.processing_time_ms;
        const isDeployment = report.is_deployment_related === true;
        const depCtx       = report.deployment_context || null;
        const actions      = rca.recommended_actions || rca.recommendations || [];

        const severityClass = isDeployment    ? 'severity-deployment'
            : confidence === 'high'           ? 'severity-high'
            : confidence === 'medium'         ? 'severity-medium'
            : 'severity-low';

        const timeAgo = analyzedAt ? timeAgoStr(analyzedAt) : '';
        const procStr = procMs ? `${(procMs / 1000).toFixed(1)}s` : '';
        const sha     = depCtx?.commit_sha || '';

        return `
        <div class="rca-card ${severityClass}" data-rca-idx="${idx}" role="button" tabindex="0"
             onclick="openRCADetail(${idx})" onkeydown="if(event.key==='Enter')openRCADetail(${idx})">

            <div class="rca-card-top">
                <div class="rca-card-meta">
                    <span class="rca-service-pill">⚡ ${escapeHtml(service)}</span>
                    <span class="rca-env-pill">${escapeHtml(env)}</span>
                    ${isDeployment ? '<span class="rca-deploy-pill">🚀 Deployment</span>' : ''}
                    <span class="rca-confidence-pill ${confidence}">${capitalise(confidence)} Confidence</span>
                </div>
                <div class="rca-card-actions">
                    ${timeAgo ? `<span class="rca-timestamp">${timeAgo}</span>` : ''}
                    <button class="rca-view-btn" onclick="event.stopPropagation();openRCADetail(${idx})">
                        View Details →
                    </button>
                </div>
            </div>

            <div class="rca-card-error">${escapeHtml(report.error || rootCause)}</div>
            <div class="rca-card-cause">${escapeHtml(rootCause)}</div>

            <div class="rca-card-footer">
                <span class="rca-proc-time">
                    ${procStr ? `⏱ Analyzed in ${procStr}` : ''}
                    ${sha ? ` &nbsp;·&nbsp; 🔗 commit <code style="color:var(--accent-primary);font-size:.75rem;">${sha.slice(0,7)}</code>` : ''}
                    ${actions.length > 0 ? ` &nbsp;·&nbsp; ${actions.length} action${actions.length !== 1 ? 's' : ''}` : ''}
                </span>
                <span style="font-size:.75rem;color:var(--text-muted);">ID: ${escapeHtml(String(report.id || ''))}</span>
            </div>
        </div>`;
    }).join('');
}

// ===========================================
// RCA Detail Modal
// ===========================================

function openRCADetail(idx) {
    const report = state.rcaReports[idx];
    if (!report) return;

    const rca          = report.rca_report || {};
    const confidence   = (rca.confidence  || 'medium').toLowerCase();
    const rootCause    = rca.root_cause   || report.error || 'Unknown root cause';
    const actions      = rca.recommended_actions || rca.recommendations || [];
    const signals      = rca.error_signals || rca.signals || [];
    const summary      = rca.summary || '';
    const service      = report.service   || 'Unknown Service';
    const env          = report.environment || report.env || 'production';
    const isDeployment = report.is_deployment_related === true;
    const depCtx       = report.deployment_context || null;
    const analyzedAt   = report.analyzed_at;
    const procMs       = report.processing_time_ms;
    const confPct      = confidence === 'high' ? 92 : confidence === 'medium' ? 62 : 30;

    // --- Header ---
    document.getElementById('rca-modal-service').textContent = `⚡ ${service}`;
    document.getElementById('rca-modal-pills').innerHTML = `
        <span class="rca-env-pill">${escapeHtml(env)}</span>
        ${isDeployment ? '<span class="rca-deploy-pill">🚀 Deployment Regression</span>' : ''}
        <span class="rca-confidence-pill ${confidence}">${capitalise(confidence)} Confidence</span>
        ${analyzedAt ? `<span class="rca-timestamp">${formatDate(analyzedAt)}</span>` : ''}`;

    const body = document.getElementById('rca-modal-body');
    body.innerHTML = '';

    // --- Deployment Regression Banner ---
    if (isDeployment && depCtx) {
        const sha    = depCtx.commit_sha  || '';
        const author = depCtx.author      || 'Unknown';
        const branch = depCtx.branch      || 'main';
        const msg    = depCtx.commit_msg  || depCtx.message || '';
        const files  = depCtx.changed_files || depCtx.files || [];

        const filesHtml = files.length > 0 ? `
            <div class="deploy-files">
                ${files.slice(0, 8).map(f => {
                    const name   = typeof f === 'string' ? f : (f.filename || f.name || 'unknown');
                    const status = typeof f === 'object' ? (f.status || 'modified') : 'modified';
                    const adds   = typeof f === 'object' ? f.additions : null;
                    const dels   = typeof f === 'object' ? f.deletions  : null;
                    return `<div class="deploy-file-item">
                        <span class="deploy-file-status ${status}">${status}</span>
                        <span class="deploy-file-name">${escapeHtml(name)}</span>
                        ${adds !== null ? `<span class="deploy-file-stats">+${adds} -${dels}</span>` : ''}
                    </div>`;
                }).join('')}
                ${files.length > 8 ? `<div style="font-size:.75rem;color:var(--text-muted);padding-top:8px;">+${files.length - 8} more files</div>` : ''}
            </div>` : '';

        const deployEl = document.createElement('div');
        deployEl.innerHTML = `
            <div class="deploy-banner">
                <span class="deploy-banner-icon">🚀</span>
                <div style="flex:1">
                    <div class="deploy-banner-title">Deployment Regression Detected</div>
                    <div class="deploy-banner-sub">
                        This error occurred during the post-deployment watch window.
                        ${msg ? `Commit: <em>"${escapeHtml(msg.slice(0, 120))}"</em>` : ''}
                    </div>
                    <div class="deploy-meta">
                        <div class="deploy-meta-item">
                            <div class="deploy-meta-label">Commit SHA</div>
                            <div class="deploy-meta-value">${sha.slice(0, 12) || '—'}</div>
                        </div>
                        <div class="deploy-meta-item">
                            <div class="deploy-meta-label">Author</div>
                            <div class="deploy-meta-value">${escapeHtml(author)}</div>
                        </div>
                        <div class="deploy-meta-item">
                            <div class="deploy-meta-label">Branch</div>
                            <div class="deploy-meta-value">${escapeHtml(branch)}</div>
                        </div>
                        <div class="deploy-meta-item">
                            <div class="deploy-meta-label">Files Changed</div>
                            <div class="deploy-meta-value">${files.length}</div>
                        </div>
                    </div>
                    ${filesHtml}
                </div>
            </div>`;
        body.appendChild(deployEl);
    }

    // --- Root Cause ---
    const rcSection = _makeSection('🎯', 'Root Cause Analysis');
    rcSection.querySelector('.rca-section-body').innerHTML = `
        <div class="rca-root-cause-text">${escapeHtml(rootCause)}</div>
        ${summary ? `<div style="font-size:.85rem;color:var(--text-secondary);margin-bottom:18px;line-height:1.6;">${escapeHtml(summary)}</div>` : ''}
        <div class="confidence-row">
            <span class="confidence-label">AI Confidence</span>
            <span class="confidence-value ${confidence}">${capitalise(confidence)} (${confPct}%)</span>
        </div>
        <div class="confidence-track">
            <div class="confidence-fill ${confidence}" id="conf-bar-fill"></div>
        </div>`;
    body.appendChild(rcSection);

    // Animate confidence bar after paint
    requestAnimationFrame(() => setTimeout(() => {
        const fill = document.getElementById('conf-bar-fill');
        if (fill) fill.style.width = `${confPct}%`;
    }, 60));

    // --- Error Signals ---
    if (signals.length > 0) {
        const sigSection = _makeSection('🔍', 'Error Signals Detected');
        sigSection.querySelector('.rca-section-body').innerHTML = `
            <div class="signal-tags">
                ${signals.map(s => `<span class="signal-tag">${escapeHtml(String(s))}</span>`).join('')}
            </div>`;
        body.appendChild(sigSection);
    }

    // --- Recommended Actions ---
    if (actions.length > 0) {
        const actSection = _makeSection('✅', 'Recommended Actions');
        actSection.querySelector('.rca-section-body').innerHTML = `
            <div class="action-list">
                ${actions.map((action, i) => `
                    <div class="action-item" id="action-${idx}-${i}" onclick="toggleAction('action-${idx}-${i}')">
                        <div class="action-checkbox"></div>
                        <div class="action-num">${i + 1}</div>
                        <div class="action-text">${escapeHtml(String(action))}</div>
                    </div>`).join('')}
            </div>`;
        body.appendChild(actSection);
    }

    // --- Metadata ---
    const metaSection = _makeSection('📊', 'Analysis Metadata');
    metaSection.querySelector('.rca-section-body').innerHTML = `
        <div class="rca-meta-grid">
            <div class="rca-meta-item">
                <span class="rca-meta-val">${procMs ? (procMs / 1000).toFixed(1) + 's' : '—'}</span>
                <span class="rca-meta-lbl">Analysis Time</span>
            </div>
            <div class="rca-meta-item">
                <span class="rca-meta-val">${actions.length}</span>
                <span class="rca-meta-lbl">Action Items</span>
            </div>
            <div class="rca-meta-item">
                <span class="rca-meta-val">${signals.length || '—'}</span>
                <span class="rca-meta-lbl">Signals Found</span>
            </div>
        </div>`;
    body.appendChild(metaSection);

    // --- Raw Stacktrace Accordion ---
    const rawError = report.error || report.raw_error || '';
    if (rawError) {
        const accId = `acc-${idx}`;
        const accEl = document.createElement('div');
        accEl.className = 'rca-section';
        accEl.innerHTML = `
            <button class="rca-accordion-trigger" id="${accId}-trigger"
                    onclick="toggleAccordion('${accId}')" aria-expanded="false">
                <span>🗒 Raw Error / Stacktrace</span>
                <span class="rca-accordion-arrow">▶</span>
            </button>
            <div class="rca-accordion-body" id="${accId}-body">
                <pre class="rca-stacktrace">${escapeHtml(rawError)}</pre>
            </div>`;
        body.appendChild(accEl);
    }

    // Open overlay
    document.getElementById('rca-modal-overlay').classList.add('open');
    document.body.style.overflow = 'hidden';
}

function closeRCADetail() {
    document.getElementById('rca-modal-overlay').classList.remove('open');
    document.body.style.overflow = '';
}

function toggleAction(id) {
    document.getElementById(id)?.classList.toggle('done');
}

function toggleAccordion(accId) {
    const trigger = document.getElementById(`${accId}-trigger`);
    const body    = document.getElementById(`${accId}-body`);
    if (!trigger || !body) return;
    trigger.classList.toggle('open');
    body.classList.toggle('open');
    trigger.setAttribute('aria-expanded', body.classList.contains('open'));
}

function _makeSection(icon, title) {
    const el = document.createElement('div');
    el.className = 'rca-section';
    el.innerHTML = `
        <div class="rca-section-header">
            <span class="rca-section-icon">${icon}</span>
            <span class="rca-section-title">${title}</span>
        </div>
        <div class="rca-section-body"></div>`;
    return el;
}

function capitalise(str) {
    return str ? str.charAt(0).toUpperCase() + str.slice(1) : str;
}

function timeAgoStr(dateStr) {
    const diff  = Date.now() - new Date(dateStr).getTime();
    const mins  = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days  = Math.floor(diff / 86400000);
    if (days  > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (mins  > 0) return `${mins}m ago`;
    return 'just now';
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

    // 6. If no repo connected yet, show setup banner on dashboard
    const connectedRepo = localStorage.getItem('connected_repo') || '';
    if (!connectedRepo) {
        showSetupBanner();
    }

    // 7. Check agent status
    await checkAgentStatus();

    // 8. Load existing RCA reports
    await fetchRCAHistory();

    // 9. Refresh button
    if (elements.refreshBtn) {
        elements.refreshBtn.addEventListener('click', async () => {
            await checkAgentStatus();
            await fetchRCAHistory();
            showToast('Dashboard refreshed', 'success');
        });
    }

    // 10. Error trigger button (section-errors)
    elements.triggerErrorBtn2?.addEventListener('click', triggerTestError);

    // 11. RCA Modal — close button, backdrop click, ESC key
    document.getElementById('rca-modal-close')
        ?.addEventListener('click', closeRCADetail);
    document.getElementById('rca-modal-overlay')
        ?.addEventListener('click', e => {
            if (e.target === document.getElementById('rca-modal-overlay')) closeRCADetail();
        });
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeRCADetail();
    });

    // 12. Periodic status check every 30s
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

// Expose for onclick / HTML handlers
window.logout          = logout;
window.copyApiKey      = copyApiKey;
window.fetchRCAHistory = fetchRCAHistory;
window.openRCADetail   = openRCADetail;
window.closeRCADetail  = closeRCADetail;
window.toggleAction    = toggleAction;
window.toggleAccordion = toggleAccordion;
