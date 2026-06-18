// ─── State ────────────────────────────────────────────────────────────────────
let allJobs = [];
let filteredJobs = [];
let selectedJobIds = new Set();
let currentCLJobId = null;
let currentCLJob = null;
let currentEmailJob = null;
let emailConfigured = false;
let dailyCount = 0;
const RATE_LIMIT_MS = 12000; // 5 per minute

// ─── Toast ────────────────────────────────────────────────────────────────────
function showToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  const icons = {
    success: '✓',
    error: '✕',
    info: 'ℹ',
    warning: '⚠',
  };
  toast.innerHTML = `<span style="font-weight:600">${icons[type] || 'ℹ'}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('removing');
    setTimeout(() => toast.remove(), 200);
  }, duration);
}

// ─── Progress ─────────────────────────────────────────────────────────────────
async function refreshStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    dailyCount = data.today_count;
    updateProgressBar(dailyCount);
  } catch (_) {}
}

function updateProgressBar(count) {
  const bar = document.getElementById('progress-bar');
  const countEl = document.getElementById('progress-count');
  const navCount = document.getElementById('nav-count');
  const badge = document.getElementById('daily-badge');
  if (bar) {
    const pct = Math.min((count / 50) * 100, 100);
    bar.style.width = pct + '%';
    if (pct >= 100) {
      bar.classList.add('from-green-500', 'to-emerald-400');
      bar.classList.remove('from-violet-600', 'to-indigo-500');
    }
  }
  if (countEl) countEl.textContent = count;
  if (navCount) navCount.textContent = count;
  if (badge) badge.classList.toggle('hidden', count === 0);
  badge && badge.classList.toggle('flex', count > 0);
}

// ─── Resume Upload ─────────────────────────────────────────────────────────────
async function loadCurrentResume() {
  try {
    const res = await fetch('/api/resume/current');
    const data = await res.json();
    if (data.resume) renderResumeLoaded(data.resume);
  } catch (_) {}
}

function renderResumeLoaded(resume) {
  const area = document.getElementById('upload-area');
  const loaded = document.getElementById('resume-loaded');
  if (!area || !loaded) return;
  area.classList.add('hidden');
  loaded.classList.remove('hidden');

  const nameEl = document.getElementById('resume-name-display');
  const emailEl = document.getElementById('resume-email-display');
  const skillsEl = document.getElementById('resume-skills-display');
  if (nameEl) nameEl.textContent = resume.name || 'Unknown';
  if (emailEl) emailEl.textContent = resume.email || '';
  if (skillsEl) {
    skillsEl.innerHTML = (resume.skills || []).slice(0, 8).map(s =>
      `<span class="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded-md">${s}</span>`
    ).join('');
  }
}

function clearResume() {
  const area = document.getElementById('upload-area');
  const loaded = document.getElementById('resume-loaded');
  if (area) area.classList.remove('hidden');
  if (loaded) loaded.classList.add('hidden');
}

function initUpload() {
  const fileInput = document.getElementById('resume-file');
  const dropZone = document.getElementById('drop-zone');
  if (!fileInput) return;

  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) uploadResume(fileInput.files[0]);
  });

  if (dropZone) {
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
    dropZone.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (file) uploadResume(file);
    });
  }
}

async function uploadResume(file) {
  const idle = document.getElementById('upload-idle');
  const loading = document.getElementById('upload-loading');
  if (idle) idle.classList.add('hidden');
  if (loading) loading.classList.remove('hidden');

  const formData = new FormData();
  formData.append('resume', file);

  try {
    const res = await fetch('/api/upload-resume', { method: 'POST', body: formData });

    // Handle non-JSON responses (HTML error pages from server)
    const contentType = res.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
      showToast(`Upload failed (${res.status}). Please try again.`, 'error');
      return;
    }

    // Redirect to login if session expired
    if (res.status === 401) {
      showToast('Session expired — please log in again.', 'error');
      setTimeout(() => { window.location.href = '/login'; }, 1500);
      return;
    }

    const data = await res.json();
    if (!res.ok || data.error) {
      showToast(data.error || 'Upload failed. Please try again.', 'error');
    } else {
      showToast(`Resume parsed — found ${data.resume.skills.length} skills`, 'success');
      renderResumeLoaded(data.resume);
    }
  } catch (e) {
    showToast('Network error — please check your connection and try again.', 'error');
  } finally {
    if (idle) idle.classList.remove('hidden');
    if (loading) loading.classList.add('hidden');
  }
}

// ─── Search ───────────────────────────────────────────────────────────────────
function initSearch() {
  const form = document.getElementById('search-form');
  if (!form) return;
  form.addEventListener('submit', async e => {
    e.preventDefault();
    await searchJobs();
  });
}

async function searchJobs() {
  const query = document.getElementById('search-query')?.value?.trim() || 'software engineer';
  const location = document.getElementById('search-location')?.value?.trim() || '';
  const remote = document.getElementById('search-remote')?.checked || false;
  const salaryStr = document.getElementById('search-salary')?.value?.trim() || '';
  const salary_min = salaryStr ? parseInt(salaryStr) : null;

  const grid = document.getElementById('jobs-grid');
  const empty = document.getElementById('empty-state');
  const loading = document.getElementById('search-loading');
  const header = document.getElementById('jobs-header');

  if (grid) grid.innerHTML = '';
  if (empty) empty.classList.add('hidden');
  if (loading) loading.classList.remove('hidden');
  if (header) header.classList.add('hidden');

  const searchBtn = document.getElementById('search-btn');
  if (searchBtn) searchBtn.disabled = true;

  try {
    const res = await fetch('/api/search-jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, location, remote, salary_min }),
    });
    const data = await res.json();
    allJobs = data.jobs || [];
    filteredJobs = [...allJobs];
    selectedJobIds.clear();
    renderJobs(filteredJobs);
    if (allJobs.length > 0) {
      showToast(`Found ${allJobs.length} jobs across sources`, 'success');
    } else {
      showToast('No jobs found. Try different keywords.', 'warning');
    }
  } catch (e) {
    showToast('Search failed. Check your connection.', 'error');
  } finally {
    if (loading) loading.classList.add('hidden');
    if (searchBtn) searchBtn.disabled = false;
  }
}

function renderJobs(jobs) {
  const grid = document.getElementById('jobs-grid');
  const empty = document.getElementById('empty-state');
  const header = document.getElementById('jobs-header');
  const countEl = document.getElementById('jobs-count');

  if (!grid) return;

  if (jobs.length === 0) {
    grid.innerHTML = '';
    if (empty) empty.classList.remove('hidden');
    if (header) header.classList.add('hidden');
    return;
  }

  if (empty) empty.classList.add('hidden');
  if (header) {
    header.classList.remove('hidden');
    header.classList.add('flex');
  }
  if (countEl) countEl.textContent = `${jobs.length} jobs`;

  grid.innerHTML = jobs.map(job => buildJobCard(job)).join('');
  updateBulkPanel();
}

function buildJobCard(job) {
  const score = job.match_score || 0;
  const scoreClass = score >= 70 ? 'score-high' : score >= 40 ? 'score-mid' : 'score-low';
  const sourceClass = `source-${job.source?.toLowerCase().replace(/\s+/g, '') || 'other'}`;
  const isSelected = selectedJobIds.has(job.id);
  const salaryText = job.salary_max > 0
    ? `$${Math.round((job.salary_min || 0) / 1000)}k–$${Math.round(job.salary_max / 1000)}k`
    : '';

  return `
  <div class="job-card bg-gray-900 border border-gray-800 hover:border-gray-700 rounded-2xl p-4 transition-all cursor-pointer ${isSelected ? 'selected' : ''}"
       id="job-${job.id}" onclick="toggleSelect(${job.id})">
    <div class="flex items-start justify-between mb-2">
      <div class="flex-1 min-w-0">
        <h3 class="font-semibold text-white text-sm truncate">${escHtml(job.title)}</h3>
        <p class="text-xs text-gray-400 mt-0.5 truncate">${escHtml(job.company)} · ${escHtml(job.location)}</p>
      </div>
      <div class="flex items-center gap-2 ml-2 flex-shrink-0">
        <span class="text-xs font-semibold ${scoreClass}">${score}%</span>
        ${job.email_apply ? '<span title="Direct email apply available" class="text-xs bg-emerald-900/40 text-emerald-400 px-1.5 py-0.5 rounded-md">✉</span>' : ''}
        <div class="w-5 h-5 rounded border-2 ${isSelected ? 'bg-violet-600 border-violet-600' : 'border-gray-700'} flex items-center justify-center flex-shrink-0 transition-all" id="check-${job.id}">
          ${isSelected ? '<svg class="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>' : ''}
        </div>
      </div>
    </div>

    <p class="text-xs text-gray-500 line-clamp-2 mb-3">${escHtml(job.description || '')}</p>

    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="text-xs px-2 py-0.5 rounded-md ${sourceClass}">${escHtml(job.source)}</span>
        ${job.remote ? '<span class="text-xs bg-emerald-900/40 text-emerald-400 px-2 py-0.5 rounded-md">Remote</span>' : ''}
        ${salaryText ? `<span class="text-xs text-gray-500">${salaryText}</span>` : ''}
      </div>
      <div class="flex items-center gap-2">
        ${job.url ? `<a href="${escHtml(job.url)}" target="_blank" onclick="event.stopPropagation()" class="text-xs text-gray-500 hover:text-white transition-colors">View</a>` : ''}
        ${job.email_apply ? `<button onclick="event.stopPropagation(); openEmailModal(${job.id})"
          class="text-xs bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 px-2.5 py-1 rounded-lg transition-colors font-medium flex items-center gap-1">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
          Email
        </button>` : ''}
        <button onclick="event.stopPropagation(); openCoverLetter(${job.id})"
          class="text-xs bg-violet-600/20 hover:bg-violet-600/30 text-violet-400 px-3 py-1 rounded-lg transition-colors font-medium">
          Apply + Letter
        </button>
      </div>
    </div>
  </div>`;
}

// ─── Selection ────────────────────────────────────────────────────────────────
function toggleSelect(jobId) {
  if (selectedJobIds.has(jobId)) {
    selectedJobIds.delete(jobId);
  } else {
    if (selectedJobIds.size >= 50) {
      showToast('Max 50 jobs per batch', 'warning');
      return;
    }
    selectedJobIds.add(jobId);
  }
  const card = document.getElementById(`job-${jobId}`);
  const check = document.getElementById(`check-${jobId}`);
  if (card) card.classList.toggle('selected', selectedJobIds.has(jobId));
  if (check) {
    check.classList.toggle('bg-violet-600', selectedJobIds.has(jobId));
    check.classList.toggle('border-violet-600', selectedJobIds.has(jobId));
    check.innerHTML = selectedJobIds.has(jobId)
      ? '<svg class="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>'
      : '';
  }
  updateBulkPanel();
}

function selectAll() {
  const toAdd = filteredJobs.slice(0, 50);
  toAdd.forEach(j => selectedJobIds.add(j.id));
  filteredJobs.forEach(j => {
    const card = document.getElementById(`job-${j.id}`);
    const check = document.getElementById(`check-${j.id}`);
    if (card) card.classList.toggle('selected', selectedJobIds.has(j.id));
    if (check) {
      check.classList.toggle('bg-violet-600', selectedJobIds.has(j.id));
      check.classList.toggle('border-violet-600', selectedJobIds.has(j.id));
      check.innerHTML = selectedJobIds.has(j.id)
        ? '<svg class="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>'
        : '';
    }
  });
  updateBulkPanel();
  if (toAdd.length === 50) showToast('50 jobs selected (batch limit)', 'info');
}

function deselectAll() {
  selectedJobIds.clear();
  document.querySelectorAll('.job-card').forEach(c => c.classList.remove('selected'));
  document.querySelectorAll('[id^="check-"]').forEach(c => { c.classList.remove('bg-violet-600','border-violet-600'); c.innerHTML = ''; });
  updateBulkPanel();
}

function updateBulkPanel() {
  const panel = document.getElementById('bulk-panel');
  const countEl = document.getElementById('selected-count');
  if (!panel) return;
  const n = selectedJobIds.size;
  panel.classList.toggle('hidden', n === 0);
  if (countEl) countEl.textContent = `${n} selected`;
}

// ─── Filter ───────────────────────────────────────────────────────────────────
function filterJobs(type) {
  document.querySelectorAll('.filter-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.filter === type);
  });
  if (type === 'all') {
    filteredJobs = [...allJobs];
  } else if (type === 'remote') {
    filteredJobs = allJobs.filter(j => j.remote);
  } else if (type === 'high') {
    filteredJobs = allJobs.filter(j => j.match_score >= 60);
  }
  renderJobs(filteredJobs);
}

// ─── Cover Letter ─────────────────────────────────────────────────────────────
async function openCoverLetter(jobId) {
  const job = allJobs.find(j => j.id === jobId);
  if (!job) return;
  currentCLJobId = jobId;
  currentCLJob = job;

  const modal = document.getElementById('cl-modal');
  const titleEl = document.getElementById('cl-modal-title');
  const compEl = document.getElementById('cl-modal-company');
  const textarea = document.getElementById('cl-text');
  const loadingEl = document.getElementById('cl-loading');

  if (titleEl) titleEl.textContent = job.title;
  if (compEl) compEl.textContent = job.company + (job.location ? ` · ${job.location}` : '');
  if (modal) modal.classList.remove('hidden');
  if (textarea) textarea.value = '';
  if (loadingEl) loadingEl.classList.remove('hidden');

  const regenBtn = document.getElementById('cl-regen-btn');
  if (regenBtn) regenBtn.onclick = () => generateCL(jobId, job);

  await generateCL(jobId, job);
}

async function generateCL(jobId, job) {
  const textarea = document.getElementById('cl-text');
  const loadingEl = document.getElementById('cl-loading');

  if (loadingEl) loadingEl.classList.remove('hidden');
  if (textarea) textarea.value = '';

  try {
    const res = await fetch('/api/generate-cover-letter', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, job }),
    });
    const data = await res.json();
    if (textarea) textarea.value = data.cover_letter || '';
  } catch (e) {
    showToast('Failed to generate cover letter', 'error');
  } finally {
    if (loadingEl) loadingEl.classList.add('hidden');
  }
}

function closeCLModal() {
  const modal = document.getElementById('cl-modal');
  if (modal) modal.classList.add('hidden');
  currentCLJobId = null;
  currentCLJob = null;
}

function copyToClipboard() {
  const textarea = document.getElementById('cl-text');
  if (!textarea) return;
  navigator.clipboard.writeText(textarea.value).then(() => {
    showToast('Copied to clipboard', 'success');
  });
}

async function applyWithCoverLetter() {
  if (!currentCLJob) return;
  const textarea = document.getElementById('cl-text');
  const cl = textarea?.value || '';

  const jobWithCL = { ...currentCLJob, cover_letter: cl };
  closeCLModal();

  try {
    const res = await fetch('/api/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jobs: [jobWithCL] }),
    });
    const data = await res.json();
    if (data.applied_count > 0) {
      showToast(`Applied to ${currentCLJob?.company || 'company'}!`, 'success');
      updateProgressBar(data.today_total);
      if (currentCLJob?.url) {
        setTimeout(() => window.open(currentCLJob.url, '_blank'), 500);
      }
    } else {
      showToast('Already applied today', 'info');
    }
  } catch (e) {
    showToast('Apply failed', 'error');
  }
}

// ─── Bulk Apply ───────────────────────────────────────────────────────────────
async function bulkApply() {
  if (selectedJobIds.size === 0) return;
  const selected = allJobs.filter(j => selectedJobIds.has(j.id));
  const btn = document.getElementById('bulk-apply-btn');
  const progressEl = document.getElementById('bulk-progress');
  const progressBar = document.getElementById('bulk-progress-bar');
  const progressText = document.getElementById('bulk-progress-text');

  if (btn) btn.disabled = true;
  if (progressEl) progressEl.classList.remove('hidden');

  let applied = 0;
  const total = selected.length;
  const BATCH = 5;

  showToast(`Generating cover letters for ${total} jobs…`, 'info', 5000);

  // Generate cover letters in batches
  const jobsWithCL = [];
  for (let i = 0; i < selected.length; i += BATCH) {
    const batch = selected.slice(i, i + BATCH);
    const withCL = await Promise.all(batch.map(async job => {
      try {
        const res = await fetch('/api/generate-cover-letter', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ job_id: job.id, job }),
        });
        const data = await res.json();
        return { ...job, cover_letter: data.cover_letter || '' };
      } catch {
        return { ...job, cover_letter: '' };
      }
    }));
    jobsWithCL.push(...withCL);

    // Apply this batch
    try {
      const res = await fetch('/api/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jobs: withCL }),
      });
      const data = await res.json();
      applied += data.applied_count || 0;
      updateProgressBar(data.today_total);
    } catch {}

    const pct = Math.round(((i + batch.length) / total) * 100);
    if (progressBar) progressBar.style.width = pct + '%';
    if (progressText) progressText.textContent = `${Math.min(i + BATCH, total)} / ${total}`;

    // Rate limit: 5 per 12 seconds = 25/min, safe margin under 5/min per job
    if (i + BATCH < total) await sleep(RATE_LIMIT_MS);
  }

  if (btn) btn.disabled = false;
  setTimeout(() => { if (progressEl) progressEl.classList.add('hidden'); }, 2000);

  showToast(`Bulk apply done! ${applied} new applications sent.`, 'success', 5000);
  deselectAll();
}

// ─── Email Apply ─────────────────────────────────────────────────────────────
async function checkEmailStatus() {
  try {
    const res = await fetch('/api/email-status');
    const data = await res.json();
    emailConfigured = data.configured;
  } catch (_) {}
}

async function openEmailModal(jobId) {
  const job = allJobs.find(j => j.id === jobId);
  if (!job || !job.email_apply) return;
  currentEmailJob = job;

  const modal = document.getElementById('email-modal');
  const compEl = document.getElementById('email-modal-company');
  const toEl = document.getElementById('email-to');
  const subjectEl = document.getElementById('email-subject');
  const clEl = document.getElementById('email-cover-letter');
  const warning = document.getElementById('smtp-warning');
  const loading = document.getElementById('email-cl-loading');
  const regenBtn = document.getElementById('email-regen-btn');

  if (compEl) compEl.textContent = `${job.title} · ${job.company}`;
  if (toEl) toEl.value = job.email_apply;
  if (subjectEl) subjectEl.value = `Application for ${job.title} at ${job.company}`;
  if (warning) warning.classList.toggle('hidden', emailConfigured);
  if (modal) modal.classList.remove('hidden');
  if (clEl) clEl.value = '';

  if (regenBtn) regenBtn.onclick = () => generateEmailCL(job);

  await generateEmailCL(job);
}

async function generateEmailCL(job) {
  const loading = document.getElementById('email-cl-loading');
  const clEl = document.getElementById('email-cover-letter');
  if (loading) loading.classList.remove('hidden');
  if (clEl) clEl.classList.add('hidden');

  try {
    const res = await fetch('/api/generate-cover-letter', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: job.id, job }),
    });
    const data = await res.json();
    if (clEl) clEl.value = data.cover_letter || '';
  } catch (e) {
    if (clEl) clEl.value = '';
    showToast('Failed to generate cover letter', 'error');
  } finally {
    if (loading) loading.classList.add('hidden');
    if (clEl) clEl.classList.remove('hidden');
  }
}

function closeEmailModal() {
  const modal = document.getElementById('email-modal');
  if (modal) modal.classList.add('hidden');
  currentEmailJob = null;
}

async function sendEmailApplication() {
  if (!currentEmailJob) return;
  const clEl = document.getElementById('email-cover-letter');
  const btn = document.getElementById('email-send-btn');
  const cover_letter = clEl?.value || '';

  if (btn) { btn.disabled = true; btn.textContent = 'Sending…'; }

  try {
    const res = await fetch('/api/send-email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        to_email: currentEmailJob.email_apply,
        job_id: currentEmailJob.id,
        job_title: currentEmailJob.title,
        company: currentEmailJob.company,
        cover_letter,
      }),
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Email sent to ${currentEmailJob.company}!`, 'success');
      updateProgressBar(data.today_total);
      closeEmailModal();
    } else {
      showToast(data.error || 'Failed to send email', 'error', 6000);
    }
  } catch (e) {
    showToast('Failed to send email', 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg> Send Application'; }
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initUpload();
  initSearch();
  loadCurrentResume();
  refreshStats();
  checkEmailStatus();

  // Close modals on backdrop click
  document.getElementById('cl-modal')?.addEventListener('click', e => {
    if (e.target.id === 'cl-modal') closeCLModal();
  });
  document.getElementById('email-modal')?.addEventListener('click', e => {
    if (e.target.id === 'email-modal') closeEmailModal();
  });
});
