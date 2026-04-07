let sessionId = "ui-session-" + Math.random().toString(36).substr(2, 9);
let currentEmailId = null;
let isSessionActive = false;
let currentScore = 0.0;

document.getElementById('btn-reset').addEventListener('click', startMission);
document.getElementById('btn-grade').addEventListener('click', getGrade);

async function req(endpoint, opts = {}) {
    opts.headers = {
        'Content-Type': 'application/json',
        'X-Session-ID': sessionId,
        ...(opts.headers || {})
    };
    try {
        const r = await fetch(endpoint, opts);
        if(!r.ok) {
            const err = await r.json();
            showToast("Error", err.detail || r.statusText, "neg");
            return null;
        }
        return await r.json();
    } catch (e) {
        showToast("Connection Error", e.message, "neg");
        return null;
    }
}

function updateLog(msg, type = "normal") {
    const log = document.getElementById('agent-log');
    const p = document.createElement('div');
    p.className = `log-entry ${type}`;
    p.textContent = msg;
    log.prepend(p);
}

function showToast(title, msg, type = "normal") {
    const cont = document.getElementById('toast-container');
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerHTML = `<h4>${title}</h4><p style="font-size: 0.85rem; color: #cbd5e1;">${msg}</p>`;
    cont.appendChild(t);
    setTimeout(() => {
        t.style.opacity = '0';
        setTimeout(() => t.remove(), 300);
    }, 4000);
}

function toggleActions(enable) {
    document.querySelectorAll('.action-btn').forEach(b => {
        if(enable) b.classList.add('active');
        else b.classList.remove('active');
    });
    if(!enable) document.getElementById('draft-slider').classList.add('hidden');
}

function draftReplyAction() {
    const sl = document.getElementById('draft-slider');
    sl.classList.toggle('hidden');
}

async function submitDraft() {
    const body = document.getElementById('reply-text').value;
    const tone = document.getElementById('reply-tone').value;
    if(!body) return showToast("Error", "Reply body missing", "neg");
    
    document.getElementById('draft-slider').classList.add('hidden');
    document.getElementById('reply-text').value = '';
    
    await submitAction('draft_reply', { reply_body: body, tone: tone });
}

async function startMission() {
    const task = document.getElementById('task-selector').value;
    updateLog(`Initializing ${task}...`);
    
    const obs = await req('/reset', {
        method: 'POST',
        body: JSON.stringify({ task_id: task, seed: Math.floor(Math.random()*1000) })
    });
    
    if(!obs) return;

    isSessionActive = true;
    currentScore = 0.0;
    document.getElementById('current-score').textContent = "0.00";
    document.getElementById('agent-log').innerHTML = '';
    document.getElementById('btn-grade').disabled = false;
    document.getElementById('btn-grade').classList.remove('disabled');

    updateUI(obs);
    showToast("Mission Started", `Loaded ${obs.inbox_summary.total_emails} emails into inbox.`);
}

async function submitAction(actionType, extraParams) {
    if(!isSessionActive || !currentEmailId) return;

    // Turn off buttons while loading
    toggleActions(false);

    const action = { action_type: actionType, ...extraParams };
    if(actionType === 'draft_reply' || actionType === 'schedule_followup' || actionType === 'send_reply' || actionType === 'flag') {
        action.email_id = currentEmailId;
    }

    updateLog(`Action Triggered: ${actionType}`);

    const res = await req('/step', {
        method: 'POST',
        body: JSON.stringify({ action })
    });

    if(res) {
        // Handle Reward
        const rwd = res.reward.value;
        currentScore += rwd;
        document.getElementById('current-score').textContent = currentScore.toFixed(2);
        
        let rwdType = rwd > 0 ? "pos" : (rwd < 0 ? "neg" : "normal");
        if(rwd !== 0) {
            updateLog(`Reward: ${rwd > 0 ? '+'+rwd.toFixed(2) : rwd.toFixed(2)} (${res.reward.reason})`, rwdType === 'pos' ? 'reward-pos' : 'reward-neg');
            showToast("Action Graded", res.reward.reason + `<br><b>Score: ${rwd > 0 ? '+'+rwd.toFixed(2) : rwd.toFixed(2)}</b>`, rwdType);
        }

        updateUI(res.observation);
    } else {
        toggleActions(true); // Re-enable if error
    }
}

function updateUI(obs) {
    if(!obs) return;

    // Stats
    const summary = obs.inbox_summary || {};
    document.getElementById('stat-total').textContent = summary.total_emails || 0;
    document.getElementById('stat-unread').textContent = summary.unread_count || 0;
    document.getElementById('stat-processed').textContent = summary.processed_count || 0;
    document.getElementById('stat-budget').textContent = summary.step_budget_remaining || 0;

    if(obs.done) {
        isSessionActive = false;
        toggleActions(false);
        document.getElementById('email-header').innerHTML = `<h2>🎉 Simulation Complete</h2>`;
        document.getElementById('email-meta').style.display = 'none';
        document.getElementById('email-body').innerHTML = `<p style="padding: 20px; text-align: center;">There are no more emails to process. Click <b>Get Grade</b> to see your final performance.</p>`;
        document.getElementById('thread-history').style.display = 'none';
        return;
    }

    // Email View
    toggleActions(true);
    const em = obs.current_email;
    currentEmailId = em.email_id;
    
    document.getElementById('email-header').innerHTML = `<h2>${em.subject}</h2>`;
    document.getElementById('email-meta').style.display = 'flex';
    document.getElementById('em-sender').textContent = `${em.sender} (${em.sender_importance || 'unknown'})`;
    document.getElementById('em-date').textContent = new Date(em.received_at).toLocaleDateString() || '--';
    document.getElementById('em-deadline').textContent = em.deadline_hint || 'None';
    
    document.getElementById('email-body').innerHTML = em.body;

    // Thread
    const hist = document.getElementById('thread-history');
    if(em.thread && em.thread.messages && em.thread.messages.length > 0) {
        hist.style.display = 'block';
        let txt = '';
        em.thread.messages.forEach(m => {
            txt += `<div class="thread-msg"><span>${m.sender} - ${new Date(m.timestamp).toLocaleDateString()}:</span>${m.body}</div>`;
        });
        document.getElementById('thread-content').innerHTML = txt;
    } else {
        hist.style.display = 'none';
    }
}

async function getGrade() {
    const res = await req('/grader', { method: 'POST' });
    if(res) {
        document.getElementById('grade-modal').classList.remove('hidden');
        document.getElementById('final-score-display').textContent = res.final_score.toFixed(2);
        
        let bd = '';
        for(const [k, v] of Object.entries(res.component_scores || {})) {
            bd += `<div style="display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.1); padding: 5px 0;"><span>${k}</span><b>${v.toFixed(2)}</b></div>`;
        }
        document.getElementById('grade-breakdown').innerHTML = bd;
        isSessionActive = false;
        toggleActions(false);
    }
}

function closeModal() {
    document.getElementById('grade-modal').classList.add('hidden');
}
