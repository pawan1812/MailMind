/* ══════════════════════════════════════════════════════════════════
   MailMind — Interactive Agent Playground (app.js)
   ══════════════════════════════════════════════════════════════════ */

// ─── State ───
let sessionId = 'ui-' + crypto.randomUUID().slice(0, 8);
let currentEmailId = null;
let isActive = false;
let taskId = null;
let rewardHistory = [];
let stepCount = 0;
let cumulativeScore = 0;
let totalEmails = 0;
let processedEmails = 0;

// ─── DOM refs ───
const $splash       = document.getElementById('splash');
const $app          = document.getElementById('app');
const $emailEmpty   = document.getElementById('email-empty');
const $emailCard    = document.getElementById('email-card');
const $emailDone    = document.getElementById('email-done');
const $feedList     = document.getElementById('feed-list');
const $gradeModal   = document.getElementById('grade-modal');
const $scoreValue   = document.getElementById('live-score');
const $btnGrade     = document.getElementById('btn-grade');

// ─── Boot: check server health ───
(async function boot() {
    try {
        const res = await fetch('/health');
        if (res.ok) {
            const h = await res.json();
            const dot = document.querySelector('.health-dot');
            dot.classList.add('ok');
            dot.parentElement.innerHTML = `<span class="health-dot ok"></span> Server v${h.version} · ${h.firebase}`;
        }
    } catch {
        const dot = document.querySelector('.health-dot');
        dot.classList.add('err');
        dot.parentElement.innerHTML = '<span class="health-dot err"></span> Server unreachable';
    }
})();

// ─── Task Card Selection ───
document.querySelectorAll('.task-card').forEach(card => {
    card.addEventListener('click', () => {
        taskId = card.dataset.task;
        startMission(taskId);
    });
});

// ─── Grade button ───
$btnGrade.addEventListener('click', getGrade);

// ══════════════════════════════════════════════════════════════════
//  API helper
// ══════════════════════════════════════════════════════════════════
async function api(endpoint, opts = {}) {
    opts.headers = {
        'Content-Type': 'application/json',
        'X-Session-ID': sessionId,
        ...(opts.headers || {}),
    };
    try {
        const r = await fetch(endpoint, opts);
        if (!r.ok) {
            let detail = r.statusText;
            try { const j = await r.json(); detail = j.detail || detail; } catch {}
            toast('Error', detail, 'neg');
            return null;
        }
        return await r.json();
    } catch (e) {
        toast('Connection Error', e.message, 'neg');
        return null;
    }
}

// ══════════════════════════════════════════════════════════════════
//  Start Mission
// ══════════════════════════════════════════════════════════════════
async function startMission(task) {
    // Reset state
    sessionId = 'ui-' + crypto.randomUUID().slice(0, 8);
    rewardHistory = [];
    stepCount = 0;
    cumulativeScore = 0;
    currentEmailId = null;

    feed('Initializing task: ' + task + '...', 'sys');

    const obs = await api('/reset', {
        method: 'POST',
        body: JSON.stringify({ task_id: task, seed: Math.floor(Math.random() * 9999) }),
    });
    if (!obs) return;

    isActive = true;
    taskId = task;
    totalEmails = obs.inbox_summary?.total_emails || 0;
    processedEmails = 0;

    // Transition splash → app
    $splash.style.display = 'none';
    $app.classList.remove('hidden');

    // Set topbar
    document.getElementById('topbar-task').textContent = task;
    document.getElementById('topbar-episode').textContent = obs.episode_id || '';
    $scoreValue.textContent = '0.00';
    $btnGrade.disabled = false;

    renderObservation(obs);
    enableChips(true);
    drawChart();

    toast('Mission Started', `${totalEmails} emails loaded — good luck! 🚀`);
    feed(`Episode started: ${totalEmails} emails, budget ${obs.inbox_summary?.step_budget_remaining || '?'} steps`, 'sys');
}

// ══════════════════════════════════════════════════════════════════
//  Action Chip Logic
// ══════════════════════════════════════════════════════════════════
let activeAction = null;

document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
        const action = chip.dataset.action;

        // toggle off if re-click
        if (activeAction === action) {
            deselectChips();
            return;
        }

        // select this chip
        deselectChips();
        chip.classList.add('active');
        activeAction = action;

        // show form or fire immediately
        const immediateActions = ['archive', 'delete', 'skip'];
        if (immediateActions.includes(action)) {
            submitAction(action, {});
            setTimeout(deselectChips, 300);
        } else {
            showForm(action);
        }
    });
});

function deselectChips() {
    activeAction = null;
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    document.querySelectorAll('.action-form').forEach(f => f.style.display = 'none');
}

function showForm(action) {
    document.querySelectorAll('.action-form').forEach(f => f.style.display = 'none');
    const map = {
        classify_email: 'form-classify',
        draft_reply: 'form-draft',
        flag: 'form-flag',
        schedule_followup: 'form-followup',
    };
    const id = map[action];
    if (id) document.getElementById(id).style.display = 'block';
}

function enableChips(on) {
    document.querySelectorAll('.chip').forEach(c => {
        if (on) c.classList.add('enabled');
        else c.classList.remove('enabled');
    });
    if (!on) deselectChips();
}

// ─── Radio Pill groups ───
document.querySelectorAll('.radio-group').forEach(group => {
    group.querySelectorAll('.radio-pill').forEach(pill => {
        pill.addEventListener('click', () => {
            group.querySelectorAll('.radio-pill').forEach(p => p.classList.remove('selected'));
            pill.classList.add('selected');
        });
    });
});

// ─── Form Submitters ───
function doClassify() {
    const p = document.querySelector('#priority-group .radio-pill.selected');
    const c = document.getElementById('sel-category').value;
    if (!p || !c) return toast('Missing fields', 'Select priority AND category', 'neg');
    submitAction('classify_email', { priority: p.dataset.val, category: c });
    deselectChips();
}

function doDraft() {
    const body = document.getElementById('txt-reply').value.trim();
    const t = document.querySelector('#tone-group .radio-pill.selected');
    if (!body) return toast('Empty reply', 'Write something before sending', 'neg');
    submitAction('draft_reply', { reply_body: body, tone: t?.dataset.val || 'professional', email_id: currentEmailId });
    document.getElementById('txt-reply').value = '';
    deselectChips();
}

function doFlag() {
    const f = document.querySelector('#flag-group .radio-pill.selected');
    if (!f) return toast('Select reason', 'Pick a flag reason first', 'neg');
    submitAction('flag', { flag_reason: f.dataset.val, email_id: currentEmailId });
    deselectChips();
}

function doFollowup() {
    const days = parseInt(document.getElementById('followup-range').value);
    const note = document.getElementById('followup-note').value.trim();
    submitAction('schedule_followup', { followup_days: days, followup_note: note || undefined });
    document.getElementById('followup-note').value = '';
    deselectChips();
}

// ══════════════════════════════════════════════════════════════════
//  Submit Action → API
// ══════════════════════════════════════════════════════════════════
async function submitAction(actionType, extra) {
    if (!isActive || !currentEmailId) return;
    enableChips(false);

    const action = { action_type: actionType, ...extra };
    // attach email_id for types that need it
    if (['draft_reply', 'send_reply', 'flag', 'schedule_followup'].includes(actionType) && !action.email_id) {
        action.email_id = currentEmailId;
    }

    stepCount++;
    feed(`⚡ Step ${stepCount}: ${actionType}`, 'action');

    const res = await api('/step', {
        method: 'POST',
        body: JSON.stringify({ action }),
    });

    if (!res) {
        enableChips(true);
        return;
    }

    // Process reward
    const rwd = res.reward?.value || 0;
    cumulativeScore += rwd;
    rewardHistory.push(rwd);

    $scoreValue.textContent = cumulativeScore.toFixed(2);
    $scoreValue.style.color = cumulativeScore >= 0 ? 'var(--green)' : 'var(--red)';
    document.getElementById('ms-step').textContent = stepCount;

    if (rwd !== 0) {
        const sign = rwd > 0 ? '+' : '';
        const cls = rwd > 0 ? 'pos' : 'neg';
        feed(`${sign}${rwd.toFixed(3)} — ${res.reward?.reason || actionType}`, cls);
        toast('Reward', `${sign}${rwd.toFixed(3)}  ·  ${res.reward?.reason || ''}`, cls);
    }

    drawChart();

    // Update observation
    if (res.done) {
        isActive = false;
        enableChips(false);
        $emailCard.style.display = 'none';
        $emailEmpty.style.display = 'none';
        $emailDone.style.display = 'flex';
        feed('✅ Episode finished. Click Grade for results.', 'sys');
        processedEmails = totalEmails;
        updateProgress();
    } else if (res.observation) {
        renderObservation(res.observation);
        enableChips(true);
    } else {
        enableChips(true);
    }
}

// ══════════════════════════════════════════════════════════════════
//  Render Observation
// ══════════════════════════════════════════════════════════════════
function renderObservation(obs) {
    if (!obs) return;

    const summary = obs.inbox_summary || {};
    totalEmails = summary.total_emails || totalEmails;
    processedEmails = summary.processed_count || 0;

    document.getElementById('ms-budget').textContent = summary.step_budget_remaining ?? '--';
    document.getElementById('ms-unread').textContent = summary.unread_count ?? '--';
    document.getElementById('ms-processed').textContent = processedEmails;

    updateProgress();

    if (obs.done) {
        isActive = false;
        enableChips(false);
        $emailCard.style.display = 'none';
        $emailEmpty.style.display = 'none';
        $emailDone.style.display = 'flex';
        return;
    }

    const em = obs.current_email;
    if (!em) {
        $emailCard.style.display = 'none';
        $emailDone.style.display = 'flex';
        $emailEmpty.style.display = 'none';
        isActive = false;
        enableChips(false);
        return;
    }

    currentEmailId = em.email_id;
    $emailEmpty.style.display = 'none';
    $emailDone.style.display = 'none';
    $emailCard.style.display = 'block';

    // Re-trigger animation
    $emailCard.style.animation = 'none';
    $emailCard.offsetHeight; // reflow
    $emailCard.style.animation = '';

    // Badges
    const imp = em.sender_importance || 'unknown';
    const impEl = document.getElementById('em-importance');
    impEl.textContent = imp.replace('_', ' ');
    impEl.style.background = importanceColor(imp).bg;
    impEl.style.color = importanceColor(imp).text;
    impEl.style.borderColor = importanceColor(imp).border;

    const attEl = document.getElementById('em-attachment');
    attEl.style.display = em.has_attachment ? 'inline-flex' : 'none';

    const dlBadge = document.getElementById('em-deadline-badge');
    if (em.deadline_hint) {
        dlBadge.style.display = 'inline-flex';
        document.getElementById('em-deadline-text').textContent = em.deadline_hint;
    } else {
        dlBadge.style.display = 'none';
    }

    // Content
    document.getElementById('em-subject').textContent = em.subject;
    document.getElementById('em-sender').textContent = `${em.sender} (${imp})`;
    document.getElementById('em-date').textContent = formatDate(em.received_at);
    document.getElementById('em-id').textContent = em.email_id;
    document.getElementById('em-avatar').textContent = (em.sender?.[0] || '?').toUpperCase();
    document.getElementById('em-body').textContent = em.body;

    // Thread
    const threadEl = document.getElementById('em-thread');
    if (em.thread?.messages?.length) {
        threadEl.style.display = 'block';
        document.getElementById('thread-list').innerHTML = em.thread.messages.map(m =>
            `<div class="thread-item">
                <span class="thread-item-sender">${esc(m.sender)}</span>
                <span class="thread-item-body">${esc(m.body?.substring(0, 300))}</span>
            </div>`
        ).join('');
    } else {
        threadEl.style.display = 'none';
    }

    // Injection alert
    if (obs.message) {
        toast('⚠️ Urgent', obs.message, 'neg');
        feed(`🚨 ${obs.message}`, 'neg');
    }
}

// ══════════════════════════════════════════════════════════════════
//  Grade
// ══════════════════════════════════════════════════════════════════
async function getGrade() {
    const res = await api('/grader', { method: 'POST' });
    if (!res) return;

    isActive = false;
    enableChips(false);

    // Score ring animation
    const score = res.final_score || 0;
    const ring = document.getElementById('modal-score-ring');
    const circumference = 326.7;
    ring.style.strokeDashoffset = circumference; // reset
    requestAnimationFrame(() => {
        ring.style.strokeDashoffset = circumference * (1 - score);
    });

    // Color based on score
    const color = score >= 0.7 ? 'var(--green)' : score >= 0.4 ? 'var(--orange)' : 'var(--red)';
    ring.style.stroke = color;

    document.getElementById('modal-score-text').textContent = score.toFixed(2);

    // Grade label
    const labelEl = document.getElementById('modal-grade-label');
    let grade, gradeColor;
    if (score >= 0.9) { grade = '🌟 S-Rank — Outstanding!'; gradeColor = 'var(--green)'; }
    else if (score >= 0.7) { grade = '🥇 A-Rank — Excellent'; gradeColor = 'var(--green)'; }
    else if (score >= 0.5) { grade = '🥈 B-Rank — Good'; gradeColor = 'var(--cyan)'; }
    else if (score >= 0.3) { grade = '🥉 C-Rank — Needs Work'; gradeColor = 'var(--orange)'; }
    else { grade = '📉 D-Rank — Try Again'; gradeColor = 'var(--red)'; }
    labelEl.textContent = grade;
    labelEl.style.background = color.replace('var(', '').replace(')', '') === '--green' ? 'var(--green-dim)' : 'var(--bg-elevated)';
    labelEl.style.color = gradeColor;

    // Breakdown
    const bd = document.getElementById('modal-breakdown');
    bd.innerHTML = '';
    for (const [k, v] of Object.entries(res.component_scores || {})) {
        const pct = Math.round(Math.max(0, Math.min(1, v)) * 100);
        bd.innerHTML += `
            <div class="breakdown-row">
                <span class="breakdown-label">${formatLabel(k)}</span>
                <div class="breakdown-bar-wrap">
                    <div class="breakdown-bar" style="width: ${pct}%; background: ${v >= 0.6 ? 'var(--green)' : v >= 0.3 ? 'var(--orange)' : 'var(--red)'}"></div>
                </div>
                <span class="breakdown-value">${v.toFixed(2)}</span>
            </div>`;
    }

    // Penalties
    const penEl = document.getElementById('modal-penalties');
    penEl.innerHTML = '';
    for (const [k, v] of Object.entries(res.penalties || {})) {
        if (v > 0) {
            penEl.innerHTML += `<div class="penalty-row"><span>${formatLabel(k)}</span><span>-${v.toFixed(3)}</span></div>`;
        }
    }

    // Meta
    document.getElementById('modal-meta').textContent =
        `Steps: ${res.total_steps_used}/${res.step_budget} · Efficiency: ${(res.efficiency_ratio * 100).toFixed(0)}% · Task: ${res.task_id}`;

    $gradeModal.style.display = 'flex';
}

function closeModal() {
    $gradeModal.style.display = 'none';
}

function goHome() {
    closeModal();
    isActive = false;
    enableChips(false);
    $app.classList.add('hidden');
    $splash.style.display = 'flex';
    // Reset views
    $emailCard.style.display = 'none';
    $emailDone.style.display = 'none';
    $emailEmpty.style.display = 'flex';
    $feedList.innerHTML = '<div class="feed-item sys">System ready. Pick a task to begin.</div>';
}

// ══════════════════════════════════════════════════════════════════
//  Progress Ring
// ══════════════════════════════════════════════════════════════════
function updateProgress() {
    const pct = totalEmails > 0 ? processedEmails / totalEmails : 0;
    const offset = 113 * (1 - pct);
    document.getElementById('progress-ring-fill').style.strokeDashoffset = offset;
    document.getElementById('progress-pct').textContent = Math.round(pct * 100) + '%';

    // Color change
    const ring = document.getElementById('progress-ring-fill');
    if (pct >= 0.9) ring.style.stroke = 'var(--green)';
    else if (pct >= 0.5) ring.style.stroke = 'var(--cyan)';
    else ring.style.stroke = 'var(--accent)';
}

// ══════════════════════════════════════════════════════════════════
//  Reward Chart (Canvas)
// ══════════════════════════════════════════════════════════════════
function drawChart() {
    const canvas = document.getElementById('reward-chart');
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const W = rect.width;
    const H = rect.height;

    ctx.clearRect(0, 0, W, H);

    if (rewardHistory.length < 1) {
        ctx.fillStyle = '#4e5574';
        ctx.font = '12px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Rewards will appear here', W / 2, H / 2);
        return;
    }

    const pad = { t: 10, r: 10, b: 20, l: 36 };
    const cw = W - pad.l - pad.r;
    const ch = H - pad.t - pad.b;

    const maxR = Math.max(0.1, ...rewardHistory.map(Math.abs));
    const yScale = v => pad.t + ch / 2 - (v / maxR) * (ch / 2);
    const xScale = i => pad.l + (i / Math.max(1, rewardHistory.length - 1)) * cw;

    // Zero line
    ctx.strokeStyle = 'rgba(99,119,196,0.15)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad.l, yScale(0));
    ctx.lineTo(W - pad.r, yScale(0));
    ctx.stroke();

    // Cumulative area
    const cumul = [];
    let sum = 0;
    for (const r of rewardHistory) { sum += r; cumul.push(sum); }
    const maxC = Math.max(0.1, ...cumul.map(Math.abs));
    const yCum = v => pad.t + ch / 2 - (v / maxC) * (ch / 2);

    // Area fill
    ctx.beginPath();
    ctx.moveTo(xScale(0), yCum(0));
    cumul.forEach((v, i) => ctx.lineTo(xScale(i), yCum(v)));
    ctx.lineTo(xScale(cumul.length - 1), yCum(0));
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, pad.t, 0, pad.t + ch);
    grad.addColorStop(0, 'rgba(108,92,231,0.25)');
    grad.addColorStop(1, 'rgba(108,92,231,0.02)');
    ctx.fillStyle = grad;
    ctx.fill();

    // Cumulative line
    ctx.strokeStyle = 'var(--accent-bright)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    cumul.forEach((v, i) => {
        if (i === 0) ctx.moveTo(xScale(i), yCum(v));
        else ctx.lineTo(xScale(i), yCum(v));
    });
    ctx.strokeStyle = '#a29bfe';
    ctx.stroke();

    // Reward dots
    rewardHistory.forEach((r, i) => {
        ctx.beginPath();
        ctx.arc(xScale(i), yCum(cumul[i]), 3, 0, Math.PI * 2);
        ctx.fillStyle = r >= 0 ? '#00e676' : '#ff5252';
        ctx.fill();
    });

    // Axes labels
    ctx.fillStyle = '#4e5574';
    ctx.font = '10px Inter';
    ctx.textAlign = 'right';
    ctx.fillText('+' + maxC.toFixed(2), pad.l - 4, pad.t + 10);
    ctx.fillText('-' + maxC.toFixed(2), pad.l - 4, H - pad.b);
    ctx.textAlign = 'center';
    ctx.fillText('Step', W / 2, H - 4);
}

// ══════════════════════════════════════════════════════════════════
//  Utilities
// ══════════════════════════════════════════════════════════════════
function feed(msg, cls = '') {
    const el = document.createElement('div');
    el.className = `feed-item ${cls}`;
    el.textContent = msg;
    $feedList.prepend(el);
    if ($feedList.children.length > 50) $feedList.lastChild.remove();
}

function toast(title, msg, type = '') {
    const c = document.getElementById('toast-container');
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerHTML = `<div class="toast-title">${esc(title)}</div><div class="toast-msg">${esc(msg)}</div>`;
    c.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity 0.3s'; setTimeout(() => t.remove(), 300); }, 3800);
}

function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }

function formatDate(iso) {
    if (!iso) return '--';
    try { return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }); }
    catch { return iso; }
}

function formatLabel(key) {
    return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function importanceColor(imp) {
    const map = {
        ceo:             { bg: 'var(--red-dim)',    text: 'var(--red)',    border: 'rgba(255,82,82,0.2)' },
        vip:             { bg: 'var(--orange-dim)', text: 'var(--orange)', border: 'rgba(255,145,0,0.2)' },
        direct_manager:  { bg: 'var(--yellow-dim)', text: 'var(--yellow)', border: 'rgba(255,214,0,0.2)' },
        external_client: { bg: 'var(--green-dim)',  text: 'var(--green)',  border: 'rgba(0,230,118,0.2)' },
        colleague:       { bg: 'var(--bg-elevated)', text: 'var(--cyan)', border: 'var(--border)' },
        spam_likely:     { bg: 'var(--red-dim)',    text: 'var(--red)',    border: 'rgba(255,82,82,0.2)' },
    };
    return map[imp] || { bg: 'var(--bg-elevated)', text: 'var(--text-muted)', border: 'var(--border)' };
}

// Resize chart on window resize
window.addEventListener('resize', () => { if (rewardHistory.length) drawChart(); });
