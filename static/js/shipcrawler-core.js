/* Shipcrawler Core v5 — Phase-streaming, real-time terminal feed, animated report */
const ShipcrawlerCore = (() => {
  let currentMode = 'vessel';
  let currentReport = null;
  let phaseCount = 0;

  const PHASE_COLORS = {
    'Equasis': '#4895ef',
    'Identity': '#4895ef',
    'Target': '#4cc9f0',
    'Attack': '#f72585',
    'Vulnerability': '#e63946',
    'Threat': '#ff9e00',
    'Report': '#06d6a0',
    'Social': '#9b5de5',
    'Research': '#00bbf9',
  };

  const els = {};

  function init() {
    els.input = document.getElementById('search-input');
    els.btn = document.getElementById('search-btn');
    els.feed = document.getElementById('terminal-feed');
    els.statusBar = document.getElementById('phase-status-bar');
    els.targetDisp = document.getElementById('target-display');
    els.reportEl = document.getElementById('report-container');
    els.reportTs = document.getElementById('report-ts');
    els.modeLabel = document.getElementById('mode-label');
    els.vesselCards = document.getElementById('vessel-cards');
    els.personCards = document.getElementById('person-cards');
    els.contextInput = document.getElementById('context-input');
    els.contextContainer = document.getElementById('context-container');
    els.finalSummary = document.getElementById('final-summary');
    els.searchSection = document.getElementById('search-section');

    // Mode toggle
    document.querySelectorAll('.mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentMode = btn.dataset.mode;
        els.input.placeholder = currentMode === 'vessel'
          ? 'e.g. vessel name or MMSI'
          : 'e.g. person name';
        els.contextContainer.style.display = currentMode === 'person' ? 'flex' : 'none';
        els.reportEl.classList.remove('visible');
      });
    });

    els.btn.addEventListener('click', doSearch);
    els.input.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
    els.input.focus();
  }

  // ── Phase Badge Color ──────────────────────────────────────
  function phaseColor(name) {
    for (const [key, color] of Object.entries(PHASE_COLORS)) {
      if (name.toLowerCase().includes(key.toLowerCase())) return color;
    }
    return '#6c8a94'; // default gray
  }

  // ── Terminal Feed ──────────────────────────────────────────
  function showFeed() {
    els.feed.style.display = 'block';
    els.feed.innerHTML = '';
    els.finalSummary.style.display = 'none';
  }

  function hideFeed() {
    els.feed.style.display = 'none';
  }

  function addPhaseLine(data, type) {
    const line = document.createElement('div');
    line.className = `phase-line phase-${type}`;

    const badge = document.createElement('span');
    badge.className = 'phase-badge';
    const phaseName = data.name || `Phase ${data.phase}`;
    const shortName = phaseName.split(' — ')[0] || phaseName;
    badge.textContent = shortName.replace(/[—–-].*/, '').trim().toUpperCase();
    badge.style.backgroundColor = phaseColor(shortName);
    line.appendChild(badge);

    const content = document.createElement('span');
    content.className = 'phase-content';

    if (type === 'start') {
      const spinner = document.createElement('span');
      spinner.className = 'spinner';
      spinner.textContent = '⏳';
      content.appendChild(spinner);
      content.appendChild(document.createTextNode(' Running...'));
    } else if (type === 'complete') {
      content.innerHTML = `✅ <strong>${escapeHtml(phaseName)}</strong> — ${escapeHtml(data.summary || 'Complete')} <span class="phase-duration">(${data.duration || '?'}s)</span>`;
    } else if (type === 'error') {
      content.innerHTML = `❌ <strong>${escapeHtml(phaseName)}</strong> — ${escapeHtml(data.error || data.summary || 'Error')}`;
    }

    line.appendChild(content);
    els.feed.appendChild(line);

    // Auto-scroll to bottom
    els.feed.scrollTop = els.feed.scrollHeight;
  }

  function addProgressLine(phase, text) {
    const line = document.createElement('div');
    line.className = 'phase-line phase-progress';
    line.innerHTML = `<span class="phase-indent"></span><span class="phase-content" style="color:var(--color-ink-2);font-size:0.75rem;">${escapeHtml(text)}</span>`;
    els.feed.appendChild(line);
    els.feed.scrollTop = els.feed.scrollHeight;
  }

  // ── SSE Callbacks ──────────────────────────────────────────

  function onPhaseStart(data) {
    addPhaseLine(data, 'start');
    phaseCount++;
  }

  function onPhaseOutput(data) {
    const line = (data.line || '').trim();
    if (line && line.length > 5) {
      addProgressLine(data.phase, line.substring(0, 200));
    }
  }

  function onPhaseComplete(data) {
    // Update the last "starting" line to completed
    const lines = els.feed.querySelectorAll('.phase-line');
    const lastStart = lines[lines.length - 1];
    if (lastStart && lastStart.classList.contains('phase-start')) {
      // Replace the start line with complete
      const badge = lastStart.querySelector('.phase-badge');
      const color = badge ? badge.style.backgroundColor : '';
      lastStart.className = 'phase-line phase-complete';
      const shortName = (data.name || `Phase ${data.phase}`).split(' — ')[0].trim().toUpperCase();
      lastStart.innerHTML = `
        <span class="phase-badge" style="background-color:${color}">${escapeHtml(shortName)}</span>
        <span class="phase-content">✅ <strong>${escapeHtml(data.name || '')}</strong> — ${escapeHtml((data.summary || 'Completed').substring(0, 150))} <span class="phase-duration">(${data.duration || '?'}s)</span></span>
      `;
    } else {
      addPhaseLine(data, 'complete');
    }
    els.feed.scrollTop = els.feed.scrollHeight;
  }

  function onPhaseError(data) {
    addPhaseLine(data, 'error');
  }

  function onReportComplete(data) {
    hideFeed();
    els.finalSummary.style.display = 'flex';
    document.getElementById('summary-phases').textContent = phaseCount;
    document.getElementById('summary-duration').textContent = data.duration_total ? data.duration_total + 's' : '?';
    document.getElementById('summary-files').textContent = (data.files || []).length;
  }

  function onDone(data) {
    // Report is ready — load it
    loadReport(data.task_id);
  }

  function onError(msg) {
    const line = document.createElement('div');
    line.className = 'phase-line phase-error';
    line.innerHTML = `<span class="phase-badge" style="background-color:#e63946">ERROR</span><span class="phase-content">❌ ${escapeHtml(msg)}</span>`;
    els.feed.appendChild(line);
    els.btn.disabled = false;
    els.btn.textContent = 'Search';
  }

  // ── Search ──────────────────────────────────────────────────
  async function doSearch() {
    const query = els.input.value.trim();
    if (!query) return;

    els.btn.disabled = true;
    els.btn.textContent = 'Starting...';
    els.reportEl.classList.remove('visible');
    els.vesselCards.style.display = 'none';
    els.personCards.style.display = 'none';
    els.targetDisp.textContent = query;
    phaseCount = 0;
    showFeed();

    try {
      const resp = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: query,
          mode: currentMode,
          context: els.contextInput ? els.contextInput.value.trim() : '',
        }),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${resp.status}`);
      }

      const { task_id } = await resp.json();
      els.btn.textContent = 'Investigating...';

      // Connect SSE for real-time streaming
      ShipcrawlerSSE.connect(task_id, {
        onPhaseStart,
        onPhaseOutput,
        onPhaseComplete,
        onPhaseError,
        onReportComplete,
        onDone,
        onError,
      });

      // Also poll for completion as fallback
      startPollFallback(task_id);

    } catch (err) {
      onError(err.message);
    }
  }

  // ── Fallback Poll (if SSE fails, still get results) ────────
  let _pollInterval = null;
  function startPollFallback(taskId) {
    let polls = 0;
    const maxPolls = 600; // 10 min
    _pollInterval = setInterval(async () => {
      polls++;
      try {
        const r = await fetch(`/api/status/${taskId}`);
        const st = await r.json();
        if (st.status === 'done') {
          clearInterval(_pollInterval);
          loadReport(taskId);
        } else if (st.status === 'error' || polls >= maxPolls) {
          clearInterval(_pollInterval);
        }
      } catch (e) { /* keep polling */ }
    }, 2000);
  }

  // ── Load Report ──────────────────────────────────────────────
  function loadReport(taskId) {
    ShipcrawlerSSE.loadReport(taskId, {
      onReportData: (data) => {
        currentReport = data;
        els.btn.disabled = false;
        els.btn.textContent = 'Search';
        els.input.value = '';

        // Transition: fade out feed, show summary, then render cards
        setTimeout(() => {
          hideFeed();
          displayReport(data);
        }, 300);
      },
      onError,
    });
  }

  // ── Display Report ──────────────────────────────────────────
  function displayReport(data) {
    const mode = data.mode || currentMode || 'vessel';

    // Show the final summary
    els.finalSummary.style.display = 'flex';

    els.reportEl.classList.add('visible');
    els.reportTs.textContent = new Date().toLocaleString();

    if (mode === 'person' || data.mode === 'person') {
      renderPersonReport(data);
    } else {
      renderVesselReport(data);
    }

    // Animate cards in
    setTimeout(ShipcrawlerUI.animateCards, 100);
  }

  function renderVesselReport(data) {
    els.vesselCards.style.display = 'block';
    els.personCards.style.display = 'none';
    els.modeLabel.textContent = 'Mode: Vessel OSINT (Phase Agent)';

    const vi = data.vessel_identity || {};
    ShipcrawlerUI.renderGrid('vessel-fields', {
      'Name': vi.Name || vi.name,
      'MMSI': vi.MMSI || vi.mmsi,
      'IMO': vi.IMO || vi.imo,
      'Flag': vi.Flag || vi.flag,
      'Type': vi.Type || vi.type,
    });

    const cs = data.current_status || {};
    ShipcrawlerUI.renderStatusGrid('status-fields', {
      'Status': cs.Status || cs.status,
      'Speed': cs.Speed || cs.speed,
      'Destination': cs.Destination || cs.destination,
    });

    ShipcrawlerUI.renderPortCalls(data.port_calls || []);
    ShipcrawlerUI.renderShodan(data.shodan || {});
    ShipcrawlerUI.renderRedTeam(data.red_team_playbook || {});
    ShipcrawlerUI.renderDetection(data.detection_rules || {});

    const an = data.analysis || {};
    ShipcrawlerUI.renderAnalysis({
      risk_tier: an.risk_tier || 'LOW',
      confidence: 'MEDIUM',
      notes: ['Report generated by phase-based Hermes agent'],
    });
  }

  function renderPersonReport(data) {
    els.vesselCards.style.display = 'none';
    els.personCards.style.display = 'block';
    els.modeLabel.textContent = 'Mode: Person OSINT (Phase Agent)';

    const pid = data.person_identity || {};
    ShipcrawlerUI.renderGrid('person-fields', {
      'Name': pid.Name || pid.name,
      'Location': pid.Location || pid.location,
      'Role': pid.Role || pid.role,
      'Emails': pid.Emails || pid.emails ? (pid.Emails || []).join(', ') : null,
    });

    if (data.education && data.education.length) {
      document.querySelector('[data-card="p-professional"]').style.display = 'block';
      ShipcrawlerUI.renderProfessionalHistory(
        data.education.map(e => ({ role: '', company: e, period: '' }))
      );
    }

    if (data.professional_history && data.professional_history.length) {
      document.querySelector('[data-card="p-professional"]').style.display = 'block';
      ShipcrawlerUI.renderProfessionalHistory(data.professional_history);
    }

    if (data.digital_footprint && data.digital_footprint.length) {
      ShipcrawlerUI.renderSocialMedia(data.digital_footprint);
      ShipcrawlerUI.renderDigitalFootprint(data.digital_footprint, []);
    }

    const ri = data.research_impact || {};
    ShipcrawlerUI.renderResearchImpact({
      total_publications: ri.total_publications || ri.total_citations || 0,
      citation_metrics: {
        total_citations: typeof ri.total_citations === 'number' ? ri.total_citations : 0,
        h_index: ri.h_index || 0,
        i10_index: ri.i10_index || 0,
        top_publications: ri.top_publications || [],
      },
      publications_by_year: ri.publications_by_year || {},
      coauthor_count: (data.coauthors || []).length,
    });

    if (ri.top_publications && ri.top_publications.length) {
      ShipcrawlerUI.renderPublications(ri.top_publications);
    }

    if (data.coauthors && data.coauthors.length) {
      ShipcrawlerUI.renderCoauthors(data.coauthors);
    }

    const conf = data.confidence_assessment || {};
    ShipcrawlerUI.renderConfidenceAssessment(conf);

    const ts = data.targeting_scenarios || {};
    ShipcrawlerUI.renderTargetingScenarios(ts);

    ShipcrawlerUI.renderPersonAnalysis({
      exposure_score: (data.digital_footprint || []).length * 5,
      confidence: conf.overall || 'MEDIUM',
      risk_tier: (ts.vectors || []).length >= 3 ? 'HIGH' : 'MEDIUM',
      notes: [
        `Phase-based Hermes agent research`,
        `${(data.digital_footprint || []).length} data points`,
        `${(data.coauthors || []).length} co-authors identified`,
      ],
      recommendations: ['Review the full markdown report for details'],
    });
  }

  // ── Export ──────────────────────────────────────────────────
  function exportReport(fmt) {
    if (!currentReport) return;
    const dataStr = fmt === 'json'
      ? JSON.stringify(currentReport, null, 2)
      : reportToText(currentReport);
    const mime = fmt === 'json' ? 'application/json' : 'text/plain';
    const blob = new Blob([dataStr], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `shipcrawler-${Date.now()}.${fmt}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function reportToText(report) {
    const lines = [];
    lines.push('='.repeat(60));
    lines.push('  SHIPCRAWLER V5 REPORT');
    lines.push('='.repeat(60));
    lines.push(`Generated: ${new Date().toLocaleString()}`);
    lines.push('');
    Object.entries(report).forEach(([k, v]) => {
      if (typeof v !== 'object') lines.push(`${k}: ${v}`);
    });
    lines.push('');
    lines.push('-'.repeat(60));
    return lines.join('\n');
  }

  function escapeHtml(s) {
    if (typeof s !== 'string') return String(s || '');
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  return {
    init, doSearch, exportReport,
    getCurrentMode: () => currentMode,
    getCurrentReport: () => currentReport,
    esc: escapeHtml,
  };
})();
