// API Configuration
const API_BASE = 'http://127.0.0.1:8766';
const REFRESH_INTERVAL = 5000; // 5 seconds

// Global state
let refreshIntervals = {};
let currentView = 'dashboard';

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initDashboard();
    initChat();
    initMemory();
    initAgents();
    initCognition();
    initSkills();
    initTerminal();
    testConnection();
});

// Navigation
function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const view = item.dataset.view;
            switchView(view);
        });
    });
}

function switchView(view) {
    // Update nav
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.view === view);
    });
    
    // Update views
    document.querySelectorAll('.view').forEach(v => {
        v.classList.toggle('active', v.id === `${view}-view`);
    });
    
    // Stop previous view's refresh
    if (refreshIntervals[currentView]) {
        clearInterval(refreshIntervals[currentView]);
    }
    
    currentView = view;
    
    // Start new view's refresh
    if (view === 'dashboard') {
        loadDashboard();
        refreshIntervals[view] = setInterval(loadDashboard, REFRESH_INTERVAL);
    } else if (view === 'chat') {
        loadChat();
        refreshIntervals[view] = setInterval(loadChat, REFRESH_INTERVAL);
    } else if (view === 'memory') {
        loadMemory();
    } else if (view === 'agents') {
        loadAgents();
        refreshIntervals[view] = setInterval(loadAgents, REFRESH_INTERVAL);
    } else if (view === 'cognition') {
        loadCognition();
        refreshIntervals[view] = setInterval(loadCognition, REFRESH_INTERVAL);
    } else if (view === 'skills') {
        loadSkills();
    }
}

// Test connection
async function testConnection() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        if (response.ok) {
            updateConnectionStatus(true);
        } else {
            updateConnectionStatus(false);
        }
    } catch (error) {
        updateConnectionStatus(false);
    }
}

function updateConnectionStatus(connected) {
    const badge = document.getElementById('connectionStatus');
    if (connected) {
        badge.classList.add('connected');
        badge.classList.remove('error');
        badge.querySelector('span:last-child').textContent = 'Connected';
    } else {
        badge.classList.remove('connected');
        badge.classList.add('error');
        badge.querySelector('span:last-child').textContent = 'Disconnected';
    }
}

// Dashboard
function initDashboard() {
    document.getElementById('refreshDashboard').addEventListener('click', loadDashboard);
    loadDashboard();
    refreshIntervals['dashboard'] = setInterval(loadDashboard, REFRESH_INTERVAL);
}

async function loadDashboard() {
    try {
        const [status, emotions, episodes] = await Promise.all([
            fetch(`${API_BASE}/status`).then(r => r.json()),
            fetch(`${API_BASE}/emotions`).then(r => r.json()),
            fetch(`${API_BASE}/episodes?limit=10`).then(r => r.json())
        ]);
        
        // Update metrics
        document.getElementById('uptime').textContent = formatUptime(status.uptime_sec);
        document.getElementById('tickCount').textContent = status.tick_count;
        document.getElementById('episodeCount').textContent = status.episode_count;
        document.getElementById('mode').textContent = status.mode;
        
        // Update current goal
        document.getElementById('currentGoal').innerHTML = `
            <div class="metric-value">${status.current_goal || 'No active goal'}</div>
            ${status.goal_stats ? `
                <div class="text-muted" style="margin-top: 12px;">
                    <div>✅ Completed: ${status.goal_stats.total_completed}</div>
                    <div>🔄 Resumes: ${status.goal_stats.resume_count}</div>
                </div>
            ` : ''}
        `;
        
        // Update emotions
        const dominant = emotions.dominant;
        document.getElementById('emotionsWidget').innerHTML = `
            <div class="metric-value">${dominant.name}</div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${dominant.value * 100}%"></div>
            </div>
            <div class="text-muted" style="margin-top: 12px;">${emotions.tone_modifier}</div>
        `;
        
        // Update recent activity
        const activityHtml = episodes.episodes.map(ep => `
            <div class="activity-item">
                <div class="time">${new Date(ep.timestamp).toLocaleString('ru-RU')}</div>
                <div class="event"><strong>${ep.event_type}</strong>: ${ep.description}</div>
            </div>
        `).join('');
        document.getElementById('recentActivity').innerHTML = activityHtml || '<div class="text-muted">No recent activity</div>';
        
        updateConnectionStatus(true);
    } catch (error) {
        console.error('Dashboard load error:', error);
        updateConnectionStatus(false);
    }
}

function formatUptime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
}

// Chat
function initChat() {
    const sendBtn = document.getElementById('sendMessage');
    const input = document.getElementById('chatInput');
    
    sendBtn.addEventListener('click', sendMessage);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.ctrlKey) {
            sendMessage();
        }
    });
    
    loadChat();
}

async function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message to chat
    addChatMessage('user', message);
    input.value = '';
    
    try {
        // Write to inbox.txt (через API нужно будет добавить endpoint)
        // Пока просто показываем что сообщение отправлено
        addChatMessage('system', `✅ Сообщение добавлено в inbox.txt. Digital Being ответит в следующем тике.`);
        
        // TODO: Implement POST /inbox endpoint in introspection_api.py
    } catch (error) {
        addChatMessage('system', `❌ Ошибка: ${error.message}`);
    }
}

function addChatMessage(sender, content) {
    const container = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${sender}`;
    messageDiv.innerHTML = `
        <div class="message-content">
            <p>${escapeHtml(content)}</p>
        </div>
    `;
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

async function loadChat() {
    try {
        // Load outgoing messages from SocialLayer
        // This would show Digital Being's responses
        // TODO: Add endpoint to get recent outbox messages
    } catch (error) {
        console.error('Chat load error:', error);
    }
}

// Memory Explorer
function initMemory() {
    document.getElementById('memoryFilter').addEventListener('change', loadMemory);
    document.getElementById('memorySearch').addEventListener('input', debounce(loadMemory, 500));
    loadMemory();
}

async function loadMemory() {
    const filter = document.getElementById('memoryFilter').value;
    const search = document.getElementById('memorySearch').value;
    
    try {
        let url = `${API_BASE}/episodes?limit=50`;
        if (filter) url += `&event_type=${filter}`;
        
        const response = await fetch(url);
        const data = await response.json();
        
        let episodes = data.episodes || [];
        
        // Filter by search
        if (search) {
            episodes = episodes.filter(ep => 
                ep.description.toLowerCase().includes(search.toLowerCase()) ||
                ep.event_type.toLowerCase().includes(search.toLowerCase())
            );
        }
        
        const html = episodes.map(ep => `
            <div class="memory-item">
                <div class="memory-item-header">
                    <span class="memory-item-type">${ep.event_type}</span>
                    <span class="memory-item-time">${new Date(ep.timestamp).toLocaleString('ru-RU')}</span>
                </div>
                <div class="memory-item-description">${escapeHtml(ep.description)}</div>
            </div>
        `).join('');
        
        document.getElementById('memoryList').innerHTML = html || '<div class="text-muted">No episodes found</div>';
    } catch (error) {
        console.error('Memory load error:', error);
        document.getElementById('memoryList').innerHTML = '<div class="text-error">Failed to load memory</div>';
    }
}

// Multi-Agent
function initAgents() {
    document.getElementById('refreshAgents').addEventListener('click', loadAgents);
    loadAgents();
}

async function loadAgents() {
    try {
        const response = await fetch(`${API_BASE}/multi-agent`);
        const data = await response.json();
        
        if (data.error) {
            document.getElementById('agentsGrid').innerHTML = `<div class="text-muted">${data.error}</div>`;
            document.getElementById('agentStats').innerHTML = `<div class="text-muted">N/A</div>`;
            return;
        }
        
        // Render agent cards
        const agentsHtml = data.online_agents.map(agent => `
            <div class="agent-card">
                <div class="agent-card-header">
                    <div class="agent-name">🤖 ${agent.name}</div>
                    <div class="agent-status ${agent.status}">${agent.status}</div>
                </div>
                <div class="agent-specialization">${agent.specialization}</div>
                <div class="agent-capabilities">
                    ${agent.capabilities.map(cap => `<span class="capability-tag">${cap}</span>`).join('')}
                </div>
            </div>
        `).join('');
        
        document.getElementById('agentsGrid').innerHTML = agentsHtml || '<div class="text-muted">No agents online</div>';
        
        // Render stats
        const stats = data.stats;
        document.getElementById('agentStats').innerHTML = `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px;">
                <div>
                    <div class="text-muted">Total Messages</div>
                    <div class="metric-value">${stats.total_messages_sent}</div>
                </div>
                <div>
                    <div class="text-muted">Skills Shared</div>
                    <div class="metric-value">${stats.total_skills_shared}</div>
                </div>
                <div>
                    <div class="text-muted">Collaborations</div>
                    <div class="metric-value">${stats.total_collaborations}</div>
                </div>
                <div>
                    <div class="text-muted">Online Agents</div>
                    <div class="metric-value">${stats.total_agents_registered}</div>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Agents load error:', error);
    }
}

// Cognition
function initCognition() {
    loadCognition();
}

async function loadCognition() {
    try {
        const [values, curiosity, beliefs, metaCog] = await Promise.all([
            fetch(`${API_BASE}/values`).then(r => r.json()),
            fetch(`${API_BASE}/curiosity`).then(r => r.json()),
            fetch(`${API_BASE}/beliefs`).then(r => r.json()),
            fetch(`${API_BASE}/meta-cognition`).then(r => r.json()).catch(() => ({error: 'N/A'}))
        ]);
        
        // Values
        const valuesHtml = Object.entries(values.scores || {}).map(([key, value]) => `
            <div style="margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span>${key}</span>
                    <span class="text-success">${value.toFixed(2)}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${value * 100}%"></div>
                </div>
            </div>
        `).join('');
        document.getElementById('valuesWidget').innerHTML = valuesHtml;
        
        // Curiosity
        const curiosityHtml = `
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 16px;">
                <div>
                    <div class="text-muted">Open</div>
                    <div class="metric-value">${curiosity.stats.open}</div>
                </div>
                <div>
                    <div class="text-muted">Answered</div>
                    <div class="metric-value">${curiosity.stats.answered}</div>
                </div>
                <div>
                    <div class="text-muted">Total</div>
                    <div class="metric-value">${curiosity.stats.total_asked}</div>
                </div>
            </div>
            <div class="text-muted">Recent Questions:</div>
            ${curiosity.open_questions.slice(0, 3).map(q => `
                <div style="padding: 8px; background: #252540; border-radius: 6px; margin-top: 8px;">
                    ${escapeHtml(q.question)}
                </div>
            `).join('') || '<div class="text-muted">No open questions</div>'}
        `;
        document.getElementById('curiosityWidget').innerHTML = curiosityHtml;
        
        // Beliefs
        const beliefsHtml = `
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 16px;">
                <div>
                    <div class="text-muted">Active</div>
                    <div class="metric-value">${beliefs.stats.active}</div>
                </div>
                <div>
                    <div class="text-muted">Strong</div>
                    <div class="metric-value">${beliefs.stats.strong}</div>
                </div>
                <div>
                    <div class="text-muted">Total</div>
                    <div class="metric-value">${beliefs.stats.total_beliefs_formed}</div>
                </div>
            </div>
            ${beliefs.strong.slice(0, 3).map(b => `
                <div style="padding: 8px; background: #252540; border-radius: 6px; margin-top: 8px;">
                    <div style="display: flex; justify-content: space-between;">
                        <span>${escapeHtml(b.text)}</span>
                        <span class="text-success">${b.confidence.toFixed(2)}</span>
                    </div>
                </div>
            `).join('') || '<div class="text-muted">No beliefs formed yet</div>'}
        `;
        document.getElementById('beliefsWidget').innerHTML = beliefsHtml;
        
        // Meta-Cognition
        if (metaCog.error) {
            document.getElementById('metaCognitionWidget').innerHTML = `<div class="text-muted">${metaCog.error}</div>`;
        } else {
            const metaHtml = `
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 16px;">
                    <div>
                        <div class="text-muted">Insights</div>
                        <div class="metric-value">${metaCog.stats.total_insights}</div>
                    </div>
                    <div>
                        <div class="text-muted">Calibration</div>
                        <div class="metric-value">${metaCog.stats.calibration_score.toFixed(2)}</div>
                    </div>
                </div>
                <div class="text-muted">Recent Insights:</div>
                ${metaCog.recent_insights.slice(0, 2).map(ins => `
                    <div style="padding: 8px; background: #252540; border-radius: 6px; margin-top: 8px; font-size: 13px;">
                        <strong>${ins.insight_type}</strong>: ${escapeHtml(ins.description)}
                    </div>
                `).join('') || '<div class="text-muted">No insights yet</div>'}
            `;
            document.getElementById('metaCognitionWidget').innerHTML = metaHtml;
        }
    } catch (error) {
        console.error('Cognition load error:', error);
    }
}

// Skills
function initSkills() {
    document.getElementById('refreshSkills').addEventListener('click', loadSkills);
    loadSkills();
}

async function loadSkills() {
    try {
        const response = await fetch(`${API_BASE}/skills`);
        const data = await response.json();
        
        if (data.error) {
            document.getElementById('skillsList').innerHTML = `<div class="text-muted">${data.error}</div>`;
            return;
        }
        
        const html = data.skills.map(skill => `
            <div style="padding: 16px; background: #252540; border-radius: 8px; margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <strong style="color: #00d4ff;">${escapeHtml(skill.name)}</strong>
                    <span class="text-success">${skill.confidence.toFixed(2)}</span>
                </div>
                <div class="text-muted" style="font-size: 13px; margin-bottom: 8px;">
                    ${escapeHtml(skill.description)}
                </div>
                <div style="display: flex; gap: 8px; font-size: 11px;">
                    <span class="capability-tag">Uses: ${skill.use_count}</span>
                    <span class="capability-tag">Success: ${skill.success_count}</span>
                </div>
            </div>
        `).join('');
        
        document.getElementById('skillsList').innerHTML = html || '<div class="text-muted">No skills learned yet</div>';
    } catch (error) {
        console.error('Skills load error:', error);
    }
}

// Terminal
function initTerminal() {
    document.getElementById('executeCommand').addEventListener('click', executeShellCommand);
    document.getElementById('shellCommand').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') executeShellCommand();
    });
    loadShellStats();
}

async function loadShellStats() {
    try {
        const response = await fetch(`${API_BASE}/shell/stats`);
        const data = await response.json();
        
        if (data.error) {
            document.getElementById('shellStats').innerHTML = `<div class="text-muted">${data.error}</div>`;
            return;
        }
        
        const html = `
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;">
                <div>
                    <div class="text-muted">Executed</div>
                    <div class="metric-value">${data.stats.total_executed}</div>
                </div>
                <div>
                    <div class="text-muted">Rejected</div>
                    <div class="metric-value">${data.stats.total_rejected}</div>
                </div>
                <div>
                    <div class="text-muted">Errors</div>
                    <div class="metric-value">${data.stats.total_errors}</div>
                </div>
            </div>
            <div style="margin-top: 16px;">
                <div class="text-muted">Allowed directory:</div>
                <code style="background: #252540; padding: 4px 8px; border-radius: 4px; display: block; margin-top: 4px;">
                    ${data.allowed_dir}
                </code>
            </div>
        `;
        
        document.getElementById('shellStats').innerHTML = html;
    } catch (error) {
        console.error('Shell stats load error:', error);
    }
}

async function executeShellCommand() {
    const input = document.getElementById('shellCommand');
    const command = input.value.trim();
    
    if (!command) return;
    
    const output = document.getElementById('shellOutput');
    const cmdLine = document.createElement('div');
    cmdLine.className = 'terminal-line info';
    cmdLine.textContent = `$ ${command}`;
    output.appendChild(cmdLine);
    
    input.value = '';
    
    try {
        const response = await fetch(`${API_BASE}/shell/execute`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({command})
        });
        
        const result = await response.json();
        
        const resultLine = document.createElement('div');
        resultLine.className = `terminal-line ${result.success ? '' : 'error'}`;
        resultLine.textContent = result.output || result.error || 'Command executed';
        output.appendChild(resultLine);
        
        output.scrollTop = output.scrollHeight;
        
        if (result.success) {
            loadShellStats();
        }
    } catch (error) {
        const errorLine = document.createElement('div');
        errorLine.className = 'terminal-line error';
        errorLine.textContent = `Error: ${error.message}`;
        output.appendChild(errorLine);
    }
}

// Utilities
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
