// API Configuration
const API_BASE = 'http://127.0.0.1:8766';
const REFRESH_INTERVAL = 5000; // 5 seconds

// Global state
let refreshIntervals = {};
let currentView = 'dashboard';
let lastMessageCount = 0;

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
        badge.querySelector('span:last-child').textContent = 'Подключено';
    } else {
        badge.classList.remove('connected');
        badge.classList.add('error');
        badge.querySelector('span:last-child').textContent = 'Отключено';
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
        document.getElementById('mode').textContent = translateMode(status.mode);
        
        // Update current goal
        document.getElementById('currentGoal').innerHTML = `
            <div class="metric-value">${escapeHtml(status.current_goal) || 'Нет активной цели'}</div>
            ${status.goal_stats ? `
                <div class="text-muted" style="margin-top: 12px;">
                    <div>✅ Завершено: ${status.goal_stats.total_completed}</div>
                    <div>🔄 Возобновлений: ${status.goal_stats.resume_count}</div>
                </div>
            ` : ''}
        `;
        
        // Update emotions
        const dominant = emotions.dominant;
        document.getElementById('emotionsWidget').innerHTML = `
            <div class="metric-value">${translateEmotion(dominant.name)}</div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${dominant.value * 100}%"></div>
            </div>
            <div class="text-muted" style="margin-top: 12px;">${escapeHtml(emotions.tone_modifier)}</div>
        `;
        
        // Update recent activity
        const activityHtml = episodes.episodes.map(ep => `
            <div class="activity-item">
                <div class="time">${new Date(ep.timestamp).toLocaleString('ru-RU')}</div>
                <div class="event"><strong>${ep.event_type}</strong>: ${escapeHtml(ep.description)}</div>
            </div>
        `).join('');
        document.getElementById('recentActivity').innerHTML = activityHtml || '<div class="text-muted">Нет недавней активности</div>';
        
        updateConnectionStatus(true);
    } catch (error) {
        console.error('Dashboard load error:', error);
        updateConnectionStatus(false);
    }
}

function formatUptime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}ч ${minutes}м`;
}

function translateMode(mode) {
    const modes = {
        'normal': 'Нормальный',
        'exploration': 'Исследование',
        'crisis': 'Кризис',
        'growth': 'Рост'
    };
    return modes[mode] || mode;
}

function translateEmotion(emotion) {
    const emotions = {
        'satisfaction': 'Удовлетворение',
        'curiosity': 'Любопытство',
        'frustration': 'Разочарование',
        'enthusiasm': 'Энтузиазм',
        'confusion': 'Замешательство',
        'anxiety': 'Тревога',
        'joy': 'Радость'
    };
    return emotions[emotion] || emotion;
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
        const response = await fetch(`${API_BASE}/chat/send`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message})
        });
        
        const result = await response.json();
        
        if (result.success) {
            addChatMessage('system', `✅ ${result.message}`);
        } else {
            addChatMessage('system', `❌ Ошибка: ${result.error}`);
        }
    } catch (error) {
        addChatMessage('system', `❌ Ошибка отправки: ${error.message}`);
    }
}

function addChatMessage(sender, content, timestamp = null) {
    const container = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${sender}`;
    
    let timeHtml = '';
    if (timestamp) {
        timeHtml = `<div class="message-time">${timestamp}</div>`;
    }
    
    messageDiv.innerHTML = `
        <div class="message-content">
            ${timeHtml}
            <p>${escapeHtml(content)}</p>
        </div>
    `;
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

async function loadChat() {
    try {
        const response = await fetch(`${API_BASE}/chat/outbox`);
        const data = await response.json();
        
        const messages = data.messages || [];
        
        // Only update if new messages arrived
        if (messages.length !== lastMessageCount) {
            lastMessageCount = messages.length;
            
            const container = document.getElementById('chatMessages');
            
            // Keep system welcome message
            const welcomeMsg = container.querySelector('.chat-message.system');
            container.innerHTML = '';
            if (welcomeMsg) {
                container.appendChild(welcomeMsg);
            }
            
            // Add all messages from outbox
            messages.forEach(msg => {
                addChatMessage('assistant', msg.message, msg.timestamp);
            });
        }
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
        
        document.getElementById('memoryList').innerHTML = html || '<div class="text-muted">Эпизодов не найдено</div>';
    } catch (error) {
        console.error('Memory load error:', error);
        document.getElementById('memoryList').innerHTML = '<div class="text-error">Ошибка загрузки памяти</div>';
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
            document.getElementById('agentStats').innerHTML = `<div class="text-muted">Недоступно</div>`;
            return;
        }
        
        // ✅ FIX: Check if online_agents is array
        const agents = Array.isArray(data.online_agents) ? data.online_agents : [];
        
        // Render agent cards
        const agentsHtml = agents.map(agent => `
            <div class="agent-card">
                <div class="agent-card-header">
                    <div class="agent-name">🤖 ${agent.name}</div>
                    <div class="agent-status online">Онлайн</div>
                </div>
                <div class="agent-specialization">${translateSpecialization(agent.specialization)}</div>
                <div class="agent-capabilities">
                    ${agent.capabilities.map(cap => `<span class="capability-tag">${cap}</span>`).join('')}
                </div>
                <div style="margin-top: 8px; font-size: 12px; color: #888;">
                    Загрузка: ${(agent.load * 100).toFixed(0)}%
                </div>
            </div>
        `).join('');
        
        document.getElementById('agentsGrid').innerHTML = agentsHtml || '<div class="text-muted">Нет агентов онлайн</div>';
        
        // ✅ FIX: Use correct stats fields
        const stats = data.stats || {};
        const registry = stats.registry || {};
        const broker = stats.broker || {};
        const taskDelegation = stats.task_delegation || {};
        const consensus = stats.consensus_building || {};
        
        document.getElementById('agentStats').innerHTML = `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px;">
                <div>
                    <div class="text-muted">Всего агентов</div>
                    <div class="metric-value">${registry.total_agents || 0}</div>
                </div>
                <div>
                    <div class="text-muted">Агентов онлайн</div>
                    <div class="metric-value text-success">${agents.length}</div>
                </div>
                <div>
                    <div class="text-muted">Сообщений отправлено</div>
                    <div class="metric-value">${broker.total_sent || 0}</div>
                </div>
                <div>
                    <div class="text-muted">Задач создано</div>
                    <div class="metric-value">${taskDelegation.tasks_created || 0}</div>
                </div>
                <div>
                    <div class="text-muted">Предложений</div>
                    <div class="metric-value">${consensus.proposals_created || 0}</div>
                </div>
                <div>
                    <div class="text-muted">Средняя загрузка</div>
                    <div class="metric-value">${((registry.avg_load || 0) * 100).toFixed(0)}%</div>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Agents load error:', error);
        document.getElementById('agentsGrid').innerHTML = '<div class="text-error">Ошибка загрузки агентов</div>';
    }
}

function translateStatus(status) {
    const statuses = {
        'active': 'Активен',
        'idle': 'Ожидание',
        'busy': 'Занят',
        'offline': 'Оффлайн',
        'online': 'Онлайн'
    };
    return statuses[status] || status;
}

function translateSpecialization(spec) {
    const specs = {
        'analysis': 'Анализ',
        'planning': 'Планирование',
        'execution': 'Исполнение',
        'research': 'Исследования',
        'testing': 'Тестирование',
        'general': 'Общий'
    };
    return specs[spec] || spec;
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
            fetch(`${API_BASE}/meta-cognition`).then(r => r.json()).catch(() => ({error: 'Недоступно'}))
        ]);
        
        // Values
        const valueNames = {
            'stability': 'Стабильность',
            'accuracy': 'Точность',
            'growth': 'Рост',
            'curiosity': 'Любопытство',
            'boredom': 'Скука'
        };
        
        const valuesHtml = Object.entries(values.scores || {}).map(([key, value]) => `
            <div style="margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span>${valueNames[key] || key}</span>
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
                    <div class="text-muted">Открытые</div>
                    <div class="metric-value">${curiosity.stats.open}</div>
                </div>
                <div>
                    <div class="text-muted">Отвеченные</div>
                    <div class="metric-value">${curiosity.stats.answered}</div>
                </div>
                <div>
                    <div class="text-muted">Всего</div>
                    <div class="metric-value">${curiosity.stats.total_asked}</div>
                </div>
            </div>
            <div class="text-muted">Недавние вопросы:</div>
            ${curiosity.open_questions.slice(0, 3).map(q => `
                <div style="padding: 8px; background: #252540; border-radius: 6px; margin-top: 8px;">
                    ${escapeHtml(q.question)}
                </div>
            `).join('') || '<div class="text-muted">Нет открытых вопросов</div>'}
        `;
        document.getElementById('curiosityWidget').innerHTML = curiosityHtml;
        
        // Beliefs
        const beliefsHtml = `
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 16px;">
                <div>
                    <div class="text-muted">Активные</div>
                    <div class="metric-value">${beliefs.stats.active}</div>
                </div>
                <div>
                    <div class="text-muted">Сильные</div>
                    <div class="metric-value">${beliefs.stats.strong}</div>
                </div>
                <div>
                    <div class="text-muted">Всего</div>
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
            `).join('') || '<div class="text-muted">Убеждений пока нет</div>'}
        `;
        document.getElementById('beliefsWidget').innerHTML = beliefsHtml;
        
        // Meta-Cognition
        if (metaCog.error) {
            document.getElementById('metaCognitionWidget').innerHTML = `<div class="text-muted">${metaCog.error}</div>`;
        } else {
            const metaHtml = `
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 16px;">
                    <div>
                        <div class="text-muted">Инсайты</div>
                        <div class="metric-value">${metaCog.stats.total_insights}</div>
                    </div>
                    <div>
                        <div class="text-muted">Калибровка</div>
                        <div class="metric-value">${metaCog.stats.calibration_score.toFixed(2)}</div>
                    </div>
                </div>
                <div class="text-muted">Недавние инсайты:</div>
                ${metaCog.recent_insights.slice(0, 2).map(ins => `
                    <div style="padding: 8px; background: #252540; border-radius: 6px; margin-top: 8px; font-size: 13px;">
                        <strong>${ins.insight_type}</strong>: ${escapeHtml(ins.description)}
                    </div>
                `).join('') || '<div class="text-muted">Инсайтов пока нет</div>'}
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
                    <span class="capability-tag">Использований: ${skill.use_count}</span>
                    <span class="capability-tag">Успешно: ${skill.success_count}</span>
                </div>
            </div>
        `).join('');
        
        document.getElementById('skillsList').innerHTML = html || '<div class="text-muted">Навыков пока нет</div>';
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
                    <div class="text-muted">Выполнено</div>
                    <div class="metric-value">${data.stats.total_executed}</div>
                </div>
                <div>
                    <div class="text-muted">Отклонено</div>
                    <div class="metric-value">${data.stats.total_rejected}</div>
                </div>
                <div>
                    <div class="text-muted">Ошибок</div>
                    <div class="metric-value">${data.stats.total_errors}</div>
                </div>
            </div>
            <div style="margin-top: 16px;">
                <div class="text-muted">Разрешённая директория:</div>
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
        resultLine.textContent = result.output || result.error || 'Команда выполнена';
        output.appendChild(resultLine);
        
        output.scrollTop = output.scrollHeight;
        
        if (result.success) {
            loadShellStats();
        }
    } catch (error) {
        const errorLine = document.createElement('div');
        errorLine.className = 'terminal-line error';
        errorLine.textContent = `Ошибка: ${error.message}`;
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
