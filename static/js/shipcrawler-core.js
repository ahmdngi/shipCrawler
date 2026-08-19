/* Shipcrawler Core v7.2+ — Phase-streaming, real-time terminal feed, animated report */
const ShipcrawlerCore = (() => {
  let currentMode = 'vessel';
  let currentReport = null;
  let phaseCount = 0;
  let _activeSSE = null;
  let _activeTaskId = null;

  const els = {};

  function id(name) { return document.getElementById(name); }

  function init() {
    els.input = id('search-input');
    els.btn = id('search-btn');
    els.feed = id('terminal-feed');
    els.targetDisp = id('target-display');
    els.reportSection = id('report-section');
    els.reportEl = id('report-section');
    els.reportTs = id('report-ts');
    els.modeLabel = id('mode-label');
    els.contextInput = id('context-input');
    els.contextContainer = id('context-container');
    els.finalSummary = id('final-summary');
    els.feedBody = id('feed-body');

    if (!els.btn || !els.input) {
      console.error('ShipcrawlerCore: missing required elements');
      return;
    }

    // Mode toggle
    document.querySelectorAll('.mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentMode = btn.dataset.mode;
        els.input.placeholder = currentMode === 'vessel'
          ? 'e.g. vessel name or MMSI'
          : 'e.g. person name';
        if (els.contextContainer) {
          els.contextContainer.style.display = currentMode === 'person' ? 'flex' : 'none';
        }
        if (els.reportEl) els.reportEl.classList.remove('visible');
      });
    });

    // Profile → model sync
    var profileSelect = document.getElementById('profile-select');
    if (profileSelect) {
      profileSelect.addEventListener('change', loadProfileModels);
    }
    loadProfileModels();

    els.btn.addEventListener('click', doSearch);
    els.input.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
    els.input.focus();

    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var isPerson = btn.closest('#person-panels') !== null;
        switchTab(btn.dataset.tab, isPerson);
      });
    });

    // Restore sidebar state + load history — both panels default to closed
    var sidebarOpen = localStorage.getItem('shipcrawler-sidebar-open') === 'true';
    if (!sidebarOpen) { document.getElementById('sidebar').classList.add('closed'); document.body.classList.add('sidebar-closed'); document.getElementById('sidebar-toggle').textContent = '▶'; }
    // Right panel removed — report files now show as tabs in the terminal
    // Ensure overlay hidden on load (panels closed by default)
    var overlay = document.getElementById('sidebar-overlay');
    if (overlay) overlay.classList.remove('active');
    loadHistory();

    // Live timer tick every second
    setInterval(function() {
      var timers = document.querySelectorAll('.phase-timer');
      for (var i = 0; i < timers.length; i++) {
        var t = timers[i];
        var elapsed = Math.floor((Date.now() - parseInt(t.dataset.start)) / 1000);
        var mins = Math.floor(elapsed / 60);
        var secs = elapsed % 60;
        t.textContent = mins > 0 ? ' ' + mins + 'm ' + secs + 's' : ' ' + secs + 's';
      }
    }, 1000);

    // Auto-scroll for terminal feed
    initAutoScroll();

    // Reconnect to running task on page refresh
    var savedTaskId = localStorage.getItem('shipcrawler-active-task');
    if (savedTaskId) {
      fetch('/api/status/' + savedTaskId)
        .then(function(r) { return r.json(); })
        .then(function(st) {
          if (st.status === 'running' || st.status === 'queued') {
            _activeTaskId = savedTaskId;
            if (els.btn) els.btn.textContent = 'Investigating...';
            _activeSSE = ShipcrawlerSSE.connect(savedTaskId, {
              onPhaseStart: onPhaseStart,
              onStructuredOutput: onStructuredOutput,
              onPhaseOutput: onPhaseOutput,
              onPhaseComplete: onPhaseComplete,
              onPhaseError: onPhaseError,
              onReportComplete: onReportComplete,
              onQueued: onQueued,
              onDone: onDone,
              onError: onError,
            });
            startPollFallback(savedTaskId);
          } else {
            localStorage.removeItem('shipcrawler-active-task');
          }
        })
        .catch(function() {
          localStorage.removeItem('shipcrawler-active-task');
        });
    }
  }

  // ── Terminal Feed ──────────────────────────────────────────
  function showFeed() {
    if (!els.feed) return;
    els.feed.style.display = 'block';
    els.feed.scrollTop = 0;
    // Remove any phase lines that were appended outside feed-body
    els.feed.querySelectorAll('.phase-line').forEach(el => el.remove());
    // Clear terminal body and set prompt
    const body = document.getElementById('feed-body');
    if (body) body.innerHTML = '<div class="terminal-prompt">$ <span class="prompt-cursor">▊</span></div>';
    if (els.finalSummary) els.finalSummary.style.display = 'none';
  }

  function hideFeed() {
    if (els.feed) els.feed.style.display = 'none';
  }

  function addPhaseLine(data, type) {
    if (!els.feed) return;
    const line = document.createElement('div');
    line.className = 'phase-line phase-' + type;

    // Remove the static $ prompt once real content starts
    const prompt = els.feedBody && els.feedBody.querySelector('.terminal-prompt');
    if (prompt) prompt.remove();

    const badge = document.createElement('span');
    badge.className = 'phase-badge';
    const phaseName = data.name || 'Phase ' + data.phase;
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
      content.appendChild(document.createTextNode(' '));
      const nameSpan = document.createElement('strong');
      nameSpan.textContent = phaseName;
      content.appendChild(nameSpan);
      const timer = document.createElement('span');
      timer.className = 'phase-timer';
      timer.dataset.start = Date.now();
      timer.textContent = ' 0s';
      content.appendChild(timer);
    } else if (type === 'complete') {
      content.innerHTML = '✅ <strong>' + escapeHtml(phaseName) + '</strong> — ' + escapeHtml((data.summary || 'Complete').substring(0, 150)) + ' <span class="phase-duration">(' + (data.duration || '?') + 's)</span>';
    } else if (type === 'error') {
      content.innerHTML = '❌ <strong>' + escapeHtml(phaseName) + '</strong> — ' + escapeHtml(data.error || data.summary || 'Error');
    }

    line.appendChild(content);
    els.feedBody.appendChild(line);
    if (els.feedBody) els.feedBody.scrollTop = els.feedBody.scrollHeight;
  }

  function addProgressLine(phase, text) {
    if (!els.feed) return;
    const line = document.createElement('div');
    line.className = 'phase-line phase-progress';
    line.innerHTML = '<span class="phase-indent"></span><span class="phase-content" style="font-size:0.75rem;">' + escapeHtml(text) + '</span>';
    els.feedBody.appendChild(line);
    if (els.feedBody) els.feedBody.scrollTop = els.feedBody.scrollHeight;
  }

  const PHASE_COLORS = {
    'Equasis': '#4895ef', 'Identity': '#4895ef',
    'Target': '#4cc9f0', 'Attack': '#f72585',
    'Vulnerability': '#e63946', 'Threat': '#ff9e00',
    'Report': '#06d6a0', 'Social': '#9b5de5', 'Research': '#00bbf9',
  };

  function phaseColor(name) {
    for (const [key, color] of Object.entries(PHASE_COLORS)) {
      if (name.toLowerCase().includes(key.toLowerCase())) return color;
    }
    return '#6c8a94';
  }

  // ── SSE Callbacks ──────────────────────────────────────────
  function onPhaseStart(data) {
    // Remove queued indicator once work starts
    if (_queuedLine) { _queuedLine.remove(); _queuedLine = null; }
    if (els.btn) els.btn.textContent = 'Running...';
    addPhaseLine(data, 'start');
    phaseCount++;
  }

  // ── Structured Output (new clean stream) ──────────────────
  function onStructuredOutput(data) {
    var eventType = data.structured_type || data.event_type || 'status';
    var icon = data.icon || '';
    var message = (data.message || '').trim();
    if (!message) return;
    if (!els.feed) return;

    // Remove static $ prompt once real content starts
    var prompt = els.feedBody && els.feedBody.querySelector('.terminal-prompt');
    if (prompt) prompt.remove();

    var lineEl = document.createElement('div');
    lineEl.className = 'phase-line structured-event structured-' + eventType;

    var iconSpan = document.createElement('span');
    iconSpan.className = 'struct-icon';
    iconSpan.textContent = icon;

    var msgSpan = document.createElement('span');
    msgSpan.className = 'struct-message';
    msgSpan.textContent = message;

    lineEl.appendChild(iconSpan);
    lineEl.appendChild(msgSpan);
    els.feedBody.appendChild(lineEl);
    autoScroll();
  }

  // ── Legacy raw output (keep for backward compat, deprioritized) ──
  function onPhaseOutput(data) {
    var line = (data.line || '').trim();
    if (!line || line.length <= 3) return;
    if (!els.feed) return;

    var prompt = els.feedBody && els.feedBody.querySelector('.terminal-prompt');
    if (prompt) prompt.remove();

    var lineEl = document.createElement('div');
    lineEl.className = 'phase-line phase-output-legacy';
    lineEl.innerHTML = '<span class="phase-indent"></span><span class="phase-content" style="font-size:0.72rem;color:#666;">' + escapeHtml(line) + '</span>';
    els.feedBody.appendChild(lineEl);
    autoScroll();
  }

  var _userScrolled = false;
  function initAutoScroll() {
    if (!els.feedBody) return;
    els.feedBody.addEventListener('scroll', function() {
      var threshold = 50;
      var atBottom = els.feedBody.scrollHeight - els.feedBody.scrollTop - els.feedBody.clientHeight < threshold;
      _userScrolled = !atBottom;
    });
  }
  function autoScroll() {
    if (!els.feedBody || _userScrolled) return;
    els.feedBody.scrollTop = els.feedBody.scrollHeight;
  }

  function toolColorMap(tool) {
    var map = {
      'WEB_SEARCH': '#06d6a0', 'WEB_EXTRACT': '#06d6a0',
      'EQUASIS': '#4895ef', 'EQUASIS-CLI': '#4895ef',
      'SHODAN': '#f72585',
      'BROWSER_NAVIGATE': '#9b5de5', 'BROWSER': '#9b5de5',
      'READ': '#00bbf9', 'WRITE': '#00bbf9',
      'SEARCH': '#06d6a0', 'EXTRACT': '#06d6a0',
      'CODE': '#e63946', 'TODO': '#ff9e00',
    };
    return map[tool] || '#6c8a94';
  }

  function onPhaseComplete(data) {
    if (!els.feed) return;
    var starts = els.feed.querySelectorAll('.phase-line.phase-start');
    var lastStart = starts.length > 0 ? starts[starts.length - 1] : null;
    if (lastStart && lastStart.classList.contains('phase-start')) {
      var badge = lastStart.querySelector('.phase-badge');
      var color = badge ? badge.style.backgroundColor : '';
      lastStart.className = 'phase-line phase-complete';
      var shortName = (data.name || '').split(' — ')[0].trim().toUpperCase();
      lastStart.innerHTML =
        '<span class="phase-badge" style="background-color:' + color + '">' + escapeHtml(shortName) + '</span>' +
        '<span class="phase-content">✅ <strong>' + escapeHtml(data.name || '') + '</strong> — ' + escapeHtml((data.summary || '').substring(0, 150)) + ' <span class="phase-duration">(' + (data.duration || '?') + 's)</span></span>';
    } else {
      addPhaseLine(data, 'complete');
    }
    els.feedBody.scrollTop = els.feedBody.scrollHeight;
  }

  function onPhaseError(data) { addPhaseLine(data, 'error'); }

  function onReportComplete(data) {
    if (els.finalSummary) {
      els.finalSummary.style.display = 'flex';
      var sp = id('summary-phases'); if (sp) sp.textContent = phaseCount;
      var sd = id('summary-duration'); if (sd) sd.textContent = data.duration_total ? Math.round(data.duration_total / 60) + 'm' : '?';
      var sf = id('summary-files'); if (sf) sf.textContent = (data.files || []).length;
      renderToolCounts(data);
    }
  }

  function renderToolCounts(data) {
    // Render tool call stats from report data
    var el = id('summary-tools');
    if (el) el.textContent = data && data.stats ? data.stats.tool_calls || 0 : '—';
    var srcEl = id('summary-sources');
    if (srcEl) srcEl.textContent = data && data.stats ? data.stats.sources || 0 : '—';
    var srchEl = id('summary-searches');
    if (srchEl) srchEl.textContent = data && data.stats ? data.stats.searches || 0 : '—';
    var shodanEl = id('summary-shodan');
    if (shodanEl) shodanEl.textContent = data && data.stats ? data.stats.shodan || 0 : '—';
    var modelEl = id('summary-model');
    if (modelEl) {
      var m = data && data.model;
      modelEl.textContent = m ? m : '—';
    }
  }

  function updateSummaryBar(data) {
    if (!els.finalSummary) return;
    els.finalSummary.style.display = 'flex';
    var sp = id('summary-phases');
    var phaseCount = data.phase_files ? data.phase_files.length : (data.phase_contents ? Object.keys(data.phase_contents).length : 0);
    // Fallback: if no phase files, count report files as phases
    if (phaseCount === 0 && data.report_files) {
      phaseCount = Object.keys(data.report_files).length;
    }
    if (sp) sp.textContent = phaseCount;
    var sd = id('summary-duration');
    if (sd) sd.textContent = data.duration_total ? Math.round(data.duration_total / 60) + 'm' : 'N/A';
    var sf = id('summary-files');
    if (sf) sf.textContent = data.report_files ? Object.keys(data.report_files).length : '0';
  }

  function onDone(data) {
    localStorage.removeItem('shipcrawler-active-task');
    _activeTaskId = null;
    _activeSSE = null;
    // Show completion indicator in terminal
    if (els.feedBody) {
      var line = document.createElement('div');
      line.className = 'phase-line phase-complete';
      line.innerHTML = '<span class="phase-badge" style="background-color:#3fb950">DONE</span><span class="phase-content">✅ Scan complete — loading report...</span>';
      els.feedBody.appendChild(line);
      if (!_userScrolled) els.feedBody.scrollTop = els.feedBody.scrollHeight;
    }
    if (els.btn) { els.btn.disabled = false; els.btn.textContent = 'Search'; }
    loadReport(data.task_id);
  }

  function onError(msg) {
    if (!els.feed) return;
    var line = document.createElement('div');
    line.className = 'phase-line phase-error';
    line.innerHTML = '<span class="phase-badge" style="background-color:#e63946">ERROR</span><span class="phase-content">❌ ' + escapeHtml(msg) + '</span>';
    els.feedBody.appendChild(line);
    if (els.btn) { els.btn.disabled = false; els.btn.textContent = 'Search'; }
  }

  // ── Queued state ──────────────────────────────────────────
  var _queuedLine = null;
  function onQueued(data) {
    if (!els.feed) return;
    var pos = data.position + 1;
    var total = data.total;
    var msg = '⏳ In queue (position ' + pos + ' of ' + total + ')';
    if (!_queuedLine) {
      _queuedLine = document.createElement('div');
      _queuedLine.className = 'phase-line';
      _queuedLine.innerHTML = '<span class="phase-badge" style="background-color:var(--color-badge-queue)">QUEUED</span><span class="phase-content">' + msg + '</span>';
      els.feedBody.appendChild(_queuedLine);
      els.feedBody.scrollTop = els.feedBody.scrollHeight;
    } else {
      _queuedLine.querySelector('.phase-content').textContent = msg;
    }
    // Clear placeholder cursor/prompt
    var prompt = els.feedBody.querySelector('.terminal-prompt');
    if (prompt) prompt.style.display = 'none';
  }

  // ── Search ──────────────────────────────────────────────────
  async function doSearch() {
    var query = els.input ? els.input.value.trim() : '';
    if (!query) return;

    if (els.btn) { els.btn.disabled = true; els.btn.textContent = 'Starting...'; }
    if (els.reportEl) els.reportEl.classList.remove('visible');
    if (els.targetDisp) els.targetDisp.textContent = query;
    _currentQuery = query;
    phaseCount = 0;
    // Hide hero, show terminal
    var hero = document.getElementById('search-section');
    if (hero) hero.style.display = 'none';
    showFeed();
    if (els.feed) els.feed.scrollIntoView({ behavior:'smooth', block:'start' });

      try {
        var modelSelect = document.getElementById('model-select');
        var model = modelSelect ? modelSelect.value : 'deepseek-v4-flash';
        var provider = modelSelect && modelSelect.options[modelSelect.selectedIndex]
          ? modelSelect.options[modelSelect.selectedIndex].getAttribute('data-provider') || null
          : null;
        var profileSelect = document.getElementById('profile-select');
        var profile = profileSelect ? profileSelect.value || null : null;

        var resp = await fetch('/api/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: query,
            mode: currentMode,
            context: els.contextInput ? els.contextInput.value.trim() : '',
            model: model,
            provider: provider,
            profile: profile,
          }),
        });

      if (!resp.ok) {
        var err = await resp.json().catch(function() { return {}; });
        throw new Error(err.error || 'HTTP ' + resp.status);
      }

      var data = await resp.json();
      if (els.btn) els.btn.textContent = 'Investigating...';

      // Connect SSE for real-time streaming
      _activeTaskId = data.task_id;
      localStorage.setItem('shipcrawler-active-task', data.task_id);
      _activeSSE = ShipcrawlerSSE.connect(data.task_id, {
        onPhaseStart: onPhaseStart,
        onStructuredOutput: onStructuredOutput,
        onPhaseOutput: onPhaseOutput,
        onPhaseComplete: onPhaseComplete,
        onPhaseError: onPhaseError,
        onReportComplete: onReportComplete,
        onQueued: onQueued,
        onDone: onDone,
        onError: onError,
      });

      // Also poll for completion as fallback
      startPollFallback(data.task_id);

    } catch (err) {
      console.error('Search failed:', err.message);
      onError(err.message);
      if (els.btn) { els.btn.disabled = false; els.btn.textContent = 'Search'; }
    }
  }

  // ── Fallback Poll ───────────────────────────────────────────
  var _pollInterval = null;
  var _currentQuery = '';
  function startPollFallback(taskId) {
    var polls = 0;
    var maxPolls = 600;
    _pollInterval = setInterval(async function() {
      polls++;
      try {
        var r = await fetch('/api/status/' + taskId);
        var st = await r.json();
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
    fetch('/api/report/' + taskId)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        currentReport = data;
        if (els.btn) { els.btn.disabled = false; els.btn.textContent = 'Search'; }
        if (els.input) els.input.value = '';
        setTimeout(function() {
          displayReport(data);
        }, 300);
      })
      .catch(function(err) {
        onError('Failed to load report: ' + err.message);
      });
  }

  // ── Tab Switching ──────────────────────────────────────────
  function switchTab(tabName, isPerson) {
    var prefix = isPerson ? 'tab-p-' : 'tab-';
    var tabBar = isPerson ? id('tab-bar-person') : id('tab-bar');

    // Update tab buttons
    if (tabBar) {
      var btns = tabBar.querySelectorAll('.tab-btn');
      for (var i = 0; i < btns.length; i++) {
        btns[i].classList.toggle('active', btns[i].dataset.tab === tabName);
      }
    }

    // Update panels
    var panels = document.querySelectorAll(isPerson ? '#person-panels .tab-panel' : '#report-section > .tab-panel');
    for (var i = 0; i < panels.length; i++) {
      panels[i].classList.toggle('active', panels[i].id === prefix + tabName);
    }
  }

  // ── Display Report (Tabbed) ──────────────────────────────
  function displayReport(data) {
    var mode = data.mode || currentMode || 'vessel';
    if (els.finalSummary) els.finalSummary.style.display = 'flex';
    if (els.reportEl) els.reportEl.classList.add('visible');
    if (els.reportTs) els.reportTs.textContent = new Date().toLocaleString();

    if (mode === 'person' || data.mode === 'person') {
      document.getElementById('person-panels').style.display = 'block';
      if (els.modeLabel) els.modeLabel.textContent = 'Mode: Person OSINT (Phase Agent)';
      renderPersonReport(data);
      switchTab('overview', true);
    } else {
      document.getElementById('person-panels').style.display = 'none';
      if (els.modeLabel) els.modeLabel.textContent = 'Mode: Vessel OSINT (AI Agent)';
      renderVesselReport(data);
      switchTab('overview', false);
    }
    setTimeout(ShipcrawlerUI.animateCards, 100);
  }

  function renderVesselReport(data) {
    // Overview tab
    var vi = data.vessel_identity || {};
    ShipcrawlerUI.renderGrid('vessel-fields', {
      'Name': vi.Name || vi.name, 'MMSI': vi.MMSI || vi.mmsi,
      'IMO': vi.IMO || vi.imo, 'Flag': vi.Flag || vi.flag, 'Type': vi.Type || vi.type,
    });
    var cs = data.current_status || {};
    ShipcrawlerUI.renderStatusGrid('status-fields', {
      'Status': cs.Status || cs.status, 'Speed': cs.Speed || cs.speed,
      'Destination': cs.Destination || cs.destination,
    });
    ShipcrawlerUI.renderPortCalls(data.port_calls || []);
    var an = data.analysis || {};
    ShipcrawlerUI.renderAnalysis({
      risk_tier: an.risk_tier || 'LOW', confidence: 'MEDIUM',
      notes: ['Report generated by phase-based Hermes agent'],
    });

    // Technical tab
    ShipcrawlerUI.renderShodan(data.shodan || {});
    ShipcrawlerUI.renderVuln(data.vulnerability || data.vuln_assessment || {});

    // Red Team tab
    ShipcrawlerUI.renderRedTeam(data.red_team_playbook || {});

    // Detection tab
    ShipcrawlerUI.renderDetection(data.detection_rules || {});

    // Assessment tab
    var conf = data.confidence_assessment || {};
    ShipcrawlerUI.renderConfidenceAssessment(conf);
    ShipcrawlerUI.renderRisk({
      risk_tier: an.risk_tier || 'LOW',
      overall: conf.overall || 'MEDIUM',
    });
  }

  function renderPersonReport(data) {
    // Overview tab
    var pid = data.person_identity || {};
    ShipcrawlerUI.renderGrid('person-fields', {
      'Name': pid.Name || pid.name, 'Location': pid.Location || pid.location,
      'Role': pid.Role || pid.role, 'Emails': pid.Emails || pid.emails ? (pid.Emails || []).join(', ') : null,
    });
    ShipcrawlerUI.renderPersonAnalysis({
      exposure_score: (data.digital_footprint || []).length * 5,
      confidence: (data.confidence_assessment || {}).overall || 'MEDIUM',
      risk_tier: 'MEDIUM',
      notes: ['Phase-based Hermes agent research', (data.digital_footprint || []).length + ' data points'],
      recommendations: ['Review the full markdown report for details'],
    });

    // Research tab
    var ri = data.research_impact || {};
    ShipcrawlerUI.renderResearchImpact({
      total_publications: ri.total_publications || ri.total_citations || 0,
      citation_metrics: {
        total_citations: typeof ri.total_citations === 'number' ? ri.total_citations : 0,
        h_index: ri.h_index || 0, i10_index: ri.i10_index || 0,
        top_publications: ri.top_publications || [],
      },
      publications_by_year: ri.publications_by_year || {},
      coauthor_count: (data.coauthors || []).length,
    });
    if (ri.top_publications && ri.top_publications.length) ShipcrawlerUI.renderPublications(ri.top_publications);
    if (data.coauthors && data.coauthors.length) ShipcrawlerUI.renderCoauthors(data.coauthors);

    // Social tab
    if (data.digital_footprint && data.digital_footprint.length) {
      ShipcrawlerUI.renderSocialMedia(data.digital_footprint);
      ShipcrawlerUI.renderDigitalFootprint(data.digital_footprint, []);
    }

    // Timeline tab
    if (data.education && data.education.length) {
      ShipcrawlerUI.renderProfessionalHistory(data.education.map(function(e) { return { role: '', company: e, period: '' }; }));
    }
    if (data.professional_history && data.professional_history.length) {
      ShipcrawlerUI.renderProfessionalHistory(data.professional_history);
    }
    ShipcrawlerUI.renderAffiliationTimeline(data.affiliation_timeline || {});

    // Vectors tab
    ShipcrawlerUI.renderTargetingScenarios(data.targeting_scenarios || {});
  }

  function exportReport(fmt) {
    if (!currentReport) return;
    var dataStr = fmt === 'json' ? JSON.stringify(currentReport, null, 2) : reportToText(currentReport);
    var mime = fmt === 'json' ? 'application/json' : 'text/plain';
    var blob = new Blob([dataStr], { type: mime });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'shipcrawler-' + Date.now() + '.' + fmt;
    a.click();
    URL.revokeObjectURL(url);
  }

  function reportToText(report) {
    var lines = [];
    lines.push('='.repeat(60));
    lines.push('  SHIPCRAWLER V5 REPORT');
    lines.push('='.repeat(60));
    lines.push('Generated: ' + new Date().toLocaleString());
    lines.push('');
    Object.entries(report).forEach(function(_ref) {
      var k = _ref[0], v = _ref[1];
      if (typeof v !== 'object') lines.push(k + ': ' + v);
    });
    lines.push('');
    lines.push('-'.repeat(60));
    return lines.join('\n');
  }

  function escapeHtml(s) {
    if (typeof s !== 'string') return String(s || '');
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  // ── Sidebar History ──────────────────────────────────────
  function goHome() {
    // Show hero, scroll to top of panel
    var hero = document.getElementById('search-section');
    if (hero) hero.style.display = '';
    var panel = document.querySelector('.panel');
    if (panel) panel.scrollTop = 0;
    window.scrollTo({ top: 0, behavior: 'smooth' });
    // Reset terminal to welcome message
    var feed = document.getElementById('feed-body');
    if (feed) feed.innerHTML = '<div class="terminal-prompt"><div style="color:var(--color-accent);font-weight:600;">$ shipcrawler --status</div><div style="margin-top:0.5rem;font-size:0.82rem;line-height:1.6;">ShipCrawler OSINT v7.4 — Maritime vessel reconnaissance</div><div style="margin-top:0.3rem;font-size:0.82rem;color:var(--color-ink-3);">No active investigation. Enter a vessel name, IMO, or MMSI to begin.</div><div style="margin-top:0.3rem;font-size:0.82rem;color:var(--color-ink-3);">Past investigations are available in the left sidebar.</div><div style="margin-top:0.5rem;color:var(--color-accent);">$ <span class="prompt-cursor">▊</span></div></div>';
    // Hide report section, summary, file tabs
    var rs = document.getElementById('report-section');
    if (rs) rs.classList.remove('visible');
    var fs = document.getElementById('final-summary');
    if (fs) fs.style.display = 'none';
    var ft = document.getElementById('report-file-tabs');
    if (ft) { ft.style.display = 'none'; ft.innerHTML = ''; }
    var vh = document.getElementById('vessel-header');
    if (vh) { vh.style.display = 'none'; vh.innerHTML = ''; }
  }

  function toggleSidebar() {
    var sb = document.getElementById('sidebar');
    var isClosed = sb.classList.toggle('closed');
    document.body.classList.toggle('sidebar-closed', isClosed);
    localStorage.setItem('shipcrawler-sidebar-open', String(!isClosed));
    document.getElementById('sidebar-toggle').textContent = isClosed ? '▶' : '◀';
    // Toggle mobile overlay
    var overlay = document.getElementById('sidebar-overlay');
    if (overlay) overlay.classList.toggle('active', !isClosed);
  }

  function saveToHistory(entry) {
    var tasks = JSON.parse(localStorage.getItem('shipcrawler-history') || '[]');
    for (var i = 0; i < tasks.length; i++) {
      if (tasks[i].task_id === entry.task_id) { tasks[i] = entry; localStorage.setItem('shipcrawler-history', JSON.stringify(tasks)); renderHistory(tasks); return; }
    }
    tasks.unshift(entry);
    if (tasks.length > 50) tasks.pop();
    localStorage.setItem('shipcrawler-history', JSON.stringify(tasks));
    renderHistory(tasks);
  }

  function loadHistory() {
    // Fetch history from API as source of truth, fall back to localStorage cache
    fetch('/api/history')
      .then(function(r) { return r.json(); })
      .then(function(reports) {
        if (reports && reports.length > 0) {
          localStorage.setItem('shipcrawler-history', JSON.stringify(reports));
          localStorage.setItem('shipcrawler-history-ts', String(Date.now()));
          renderHistory(reports);
          // Don't auto-load the latest report — keep a clean landing page
        } else {
          var list = document.getElementById('sidebar-list');
          if (list) list.innerHTML = '<div class="run-empty">No searches yet</div>';
        }
      })
      .catch(function() {
        // API failed — fall back to localStorage cache
        var stored = localStorage.getItem('shipcrawler-history');
        if (stored) {
          try {
            var tasks = JSON.parse(stored);
            if (tasks.length > 0) { renderHistory(tasks); return; }
          } catch(e) {}
        }
        var list = document.getElementById('sidebar-list');
        if (list) list.innerHTML = '<div class="run-empty">Could not load history</div>';
      });
  }

  function autoLoadLatest(tasks) {
    if (window._autoLoaded) return;
    window._autoLoaded = true;
    loadFromHistory(tasks[0].task_id);
  }

  function renderHistory(tasks) {
    var list = document.getElementById('sidebar-list');
    if (!list) return;
    if (!tasks || tasks.length === 0) { list.innerHTML = '<div class=\"run-empty\">No searches yet</div>'; return; }
    var html = '';
    for (var i = 0; i < tasks.length; i++) {
      var t = tasks[i];
      var timeStr = new Date(t.timestamp || Date.now()).toLocaleString();
      var icon = t.mode === 'person' ? '👤' : '🚢';
      var active = (t.task_id === (currentReport && currentReport.task_id)) ? ' active' : '';
      // Meta line: model + date/time — no redundant mode icon (already on name line)
      var metaParts = [];
      if (t.model) metaParts.push(t.model);
      metaParts.push(timeStr);
      var metaHtml = '<span>' + metaParts.join(' · ') + '</span>';
      html += '<div class="run-item' + active + '" data-task-id="' + t.task_id + '">' +
        '<button class="sidebar-delete" data-task-id="' + t.task_id + '" data-name="' + escapeHtml(t.name || 'Unknown') + '" title="Delete report">🗑</button>' +
        '<div class="name">' + icon + ' ' + escapeHtml(t.name || 'Unknown') + '</div>' +
        '<div class="date">' + metaHtml + '</div></div>';
    }
    list.innerHTML = html;
    var items = list.querySelectorAll('.run-item');
    for (var i = 0; i < items.length; i++) {
      items[i].addEventListener('click', function(e) {
        if (e.target.classList.contains('sidebar-delete')) return;
        loadFromHistory(this.dataset.taskId);
      });
    }
    // Wire delete buttons
    var dels = list.querySelectorAll('.sidebar-delete');
    for (var i = 0; i < dels.length; i++) {
      dels[i].addEventListener('click', function(e) {
        e.stopPropagation();
        var taskId = this.dataset.taskId;
        var name = this.dataset.name || taskId;
        if (!confirm('Delete report "' + name + '"?')) return;
        fetch('/api/report/' + taskId, { method: 'DELETE' })
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (data.status === 'deleted') {
              loadHistory();
            } else {
              alert('Delete failed: ' + (data.error || 'unknown'));
            }
          })
          .catch(function(err) { alert('Delete error: ' + err.message); });
      });
    }
  }

  function loadFromHistory(taskId) {
    // If a live task is running, show a banner but keep SSE alive
    if (_activeTaskId && _activeSSE && taskId !== _activeTaskId) {
      var indicator = document.getElementById('live-task-indicator');
      if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'live-task-indicator';
        indicator.className = 'live-task-indicator';
        indicator.innerHTML = '🔵 Task still running — <a href="#" id="live-task-switch" style="color:var(--color-accent);text-decoration:underline;">Switch back</a>';
        document.getElementById('sidebar').appendChild(indicator);
        document.getElementById('live-task-switch').addEventListener('click', function(e) {
          e.preventDefault();
          loadFromHistory(_activeTaskId);
          var ind = document.getElementById('live-task-indicator');
          if (ind) ind.remove();
        });
      }
    }
    var entry = null;
    var tasks = JSON.parse(localStorage.getItem('shipcrawler-history') || '[]');
    for (var i = 0; i < tasks.length; i++) {
      if (tasks[i].task_id === taskId) { entry = tasks[i]; break; }
    }

    function doLoad(url) {
      fetch(url)
        .then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(function(data) {
          currentReport = data;
          if (data.report_dir) {
            var parts = data.report_dir.replace(/\/+$/, '').split('/');
            data.task_id = parts[parts.length - 1];
          }
          // Hide hero, show report + terminal
          var hero = document.getElementById('search-section');
          if (hero) hero.style.display = 'none';
          if (els.feed) els.feed.style.display = 'block';
          if (els.reportSection) els.reportSection.classList.add('visible');
          if (els.reportTs) els.reportTs.textContent = new Date().toLocaleString();
          displayReport(data);
          updateSummaryBar(data);
          renderToolCounts(data);
          var stored = localStorage.getItem('shipcrawler-history');
          renderHistory(stored ? JSON.parse(stored) : []);
          populateRightPanel(data);
          setTimeout(function() { showExecSummary(data); }, 100);
          // Scroll terminal into view
          if (els.feed) els.feed.scrollIntoView({ behavior:'smooth', block:'start' });
        })
        .catch(function(err) {
          onError('Could not load report: ' + err.message);
        });
    }

    if (entry && entry.name) {
      // Use task_id (full directory name with date) for precise lookup
      doLoad('/api/report/by-name/' + encodeURIComponent(taskId));
    } else if (entry) {
      // No name saved — try deriving from the task's report directory
      doLoad('/api/report/by-name/' + encodeURIComponent(taskId));
    } else {
      onError('Report not found in history');
    }
  }

  function showVesselHeader(data) {
    var hdr = document.getElementById('vessel-header');
    if (!hdr) return;
    // Get vessel name + exec summary from report
    var reportText = '';
    if (data.report_files && data.report_files['analyst-report.md']) {
      reportText = data.report_files['analyst-report.md'];
    } else if (data.phase_contents) {
      for (var k in data.phase_contents) {
        if (k.indexOf('analyst') >= 0) { reportText = data.phase_contents[k]; break; }
      }
    }
    if (!reportText) { hdr.style.display = 'none'; return; }

    // Vessel name from H1
    var nameMatch = reportText.match(/^#\s*(.+?)(?:\n|$)/m);
    var vesselName = nameMatch ? nameMatch[1].trim() : (data.vessel && data.vessel.name || data.task_id || 'Vessel');

    // Exec summary
    var m = reportText.match(/##\s*\d*\.?\s*(?:EXECUTIVE\s*)?SUMMARY\s*\n([\s\S]*?)(?:\n##|\n---|\n\*\*Overall)/i);
    var summary = m ? m[1].trim().split('\n\n')[0].trim().replace(/\*\*/g,'').replace(/\[.*?\]/g,'').substring(0,400) : '';

    // Warning badges
    var warnings = [];
    if (/shadow\s*fleet|dark\s*fleet/i.test(reportText)) warnings.push('🔴 SHADOW FLEET');
    if (/sanctioned|sanctions/i.test(reportText)) warnings.push('🟡 SANCTIONED');
    if (/AIS\s*shutdown|AIS\s*dark|AIS\s*off/i.test(reportText)) warnings.push('🟠 AIS DARK');
    if (/kinetic|drone|attack|strike/i.test(reportText)) warnings.push('💥 KINETIC THREAT');
    if (/casualty|repairing/i.test(reportText)) warnings.push('⚠️ IN CASUALTY');

    var border = warnings.length ? 'var(--color-red,#e34)' : 'var(--color-green,#3fb950)';
    var html = '<div style="font-weight:600;color:var(--color-accent);font-size:0.92rem;">' + escapeHtml(vesselName) + '</div>';
    if (warnings.length) {
      html += '<div style="margin-top:0.3rem;">' + warnings.map(function(w) {
        return '<span style="background:rgba(228,51,68,0.15);color:#e34;padding:0.15rem 0.5rem;border-radius:3px;font-size:0.7rem;margin-right:0.3rem;">' + w + '</span>';
      }).join('') + '</div>';
    }
    if (summary) {
      html += '<div style="margin-top:0.3rem;color:var(--color-ink-2);font-size:0.78rem;line-height:1.5;border-left:3px solid ' + border + ';padding-left:0.5rem;">' + escapeHtml(summary) + (summary.length >= 400 ? '...' : '') + '</div>';
    }
    hdr.innerHTML = html;
    hdr.style.display = 'block';
  }

  function showExecSummary(data) {
    // Show vessel name + exec summary header above terminal
    showVesselHeader(data);
    // Replay SSE progress log into terminal
    var taskId = data.task_id || '';
    if (!taskId || !els.feedBody) return;

    // Clear terminal and show replay header
    els.feedBody.innerHTML = '<div class="terminal-prompt" style="color:var(--color-accent);font-weight:600;">$ shipcrawler --replay ' + escapeHtml(taskId) + '</div>';

    fetch('/api/progress/' + taskId)
      .then(function(r) { return r.ok ? r.json() : []; })
      .then(function(events) {
        if (!events.length) {
          els.feedBody.innerHTML += '<div style="color:var(--color-ink-3);margin-top:0.5rem;font-size:0.82rem;">No progress log found for this run.</div>';
          return;
        }
        events.forEach(function(ev) {
          if (ev.event === 'phase_start') {
            onPhaseStart(ev);
          } else if (ev.event === 'structured_output') {
            onStructuredOutput(ev);
          } else if (ev.event === 'phase_complete') {
            var starts = els.feed.querySelectorAll('.phase-line.phase-start');
            if (starts.length) {
              var last = starts[starts.length - 1];
              last.className = 'phase-line phase-complete';
              var badge = last.querySelector('.phase-badge');
              if (badge) badge.textContent = '✓';
              var spinner = last.querySelector('.spinner');
              if (spinner) spinner.textContent = '✓';
            }
          }
        });
        if (els.feedBody) els.feedBody.scrollTop = els.feedBody.scrollHeight;
      })
      .catch(function() {
        els.feedBody.innerHTML += '<div style="color:var(--color-ink-3);margin-top:0.5rem;font-size:0.82rem;">No progress log found for this run.</div>';
      });
  }

  // Override loadReport to also save to history
  var _origLoadReport = loadReport;
  loadReport = function(taskId) {
    fetch('/api/report/' + taskId)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.report_dir) {
          var parts = data.report_dir.replace(/\/+$/, '').split('/');
          data.task_id = parts[parts.length - 1];
        }
        currentReport = data;
        saveToHistory({ task_id: data.task_id, name: _currentQuery || data.task_id.replace('-report', '').replace(/-/g, ' '), mode: currentMode, timestamp: Date.now() });
        if (els.btn) { els.btn.disabled = false; els.btn.textContent = 'Search'; }
        if (els.input) els.input.value = '';
        // Hide hero, scroll to terminal
        var hero = document.getElementById('search-section');
        if (hero) hero.style.display = 'none';
        setTimeout(function() {
          displayReport(data);
          populateRightPanel(data);
          setTimeout(function() { showExecSummary(data); }, 100);
          if (els.feed) els.feed.scrollIntoView({ behavior:'smooth', block:'start' });
        }, 300);
      })
      .catch(function(err) { onError('Failed to load report: ' + err.message); });
  };

  // Right panel removed — report file tabs are now in the terminal

  function populateRightPanel(data) {
    // Try report_files first (clean report files from API), then phase_contents
    var files = {};
    if (data.report_files && Object.keys(data.report_files).length > 0) {
      files = data.report_files;
    } else if (data.phase_contents) {
      files = data.phase_contents;
    }

    // Show only the clean report files, not raw-output.md
    var reportFiles = {};
    var niceNames = {
      'analyst-report.md': '📋 Analyst Report',
      'red-team-playbook.md': '⚔️ Red Team Playbook',
      'indicators-and-detection.md': '🔍 Detection Rules',
    };
    for (var key in files) {
      if (key === 'raw-output' || key === 'raw-output.md' || key === 'agent.log') continue;
      var matched = false;
      for (var nice in niceNames) {
        if (key === nice || key.replace(/\.[^/.]+$/, '') === nice.replace(/\.[^/.]+$/, '') || key === nice.replace('.md', '')) {
          reportFiles[key] = { label: niceNames[nice], content: files[key] };
          matched = true;
          break;
        }
      }
      if (!matched) {
        reportFiles[key] = { label: key.replace(/^phase-\d+-/, '').replace(/-/g, ' ').substring(0, 30), content: files[key] };
      }
    }

    // Fallback: if no structured report files found, show what we have
    var keys = Object.keys(reportFiles);
    if (keys.length === 0) {
      keys = Object.keys(files);
      for (var i = 0; i < keys.length; i++) {
        if (keys[i] === 'raw-output.md' || keys[i] === 'agent.log') continue;
        reportFiles[keys[i]] = { label: keys[i].replace(/^phase-\d+-/, '').replace(/-/g, ' ').substring(0, 30), content: files[keys[i]] };
      }
    }
    keys = Object.keys(reportFiles);
    if (keys.length === 0) {
      keys = ['analyst-report'];
      reportFiles['analyst-report'] = { label: '📋 Analyst Report', content: data.content || 'No content' };
    }

    // Populate report file tabs in the terminal (like sirb)
    var tabBar = document.getElementById('report-file-tabs');
    if (tabBar && keys.length > 0) {
      var tabHtml = '<button class="report-file-tab active" data-mode="terminal">📡 Terminal</button>';
      for (var j = 0; j < keys.length; j++) {
        tabHtml += '<button class="report-file-tab" data-key="' + keys[j] + '">' + reportFiles[keys[j]].label + '</button>';
      }
      tabBar.innerHTML = tabHtml;
      tabBar.style.display = 'flex';
      // Store content map for tab clicks
      window._reportFileContent = {};
      for (var k = 0; k < keys.length; k++) {
        window._reportFileContent[keys[k]] = reportFiles[keys[k]].content || '';
      }
      // Reset terminal view: clear stale report markdown from previous run.
      // The Terminal tab is active by default, so feed-body must show the
      // terminal prompt, not the previous run's rendered report content.
      window._cachedFeedHtml = null;
      var feedBody = document.getElementById('feed-body');
      if (feedBody) {
        feedBody.innerHTML = '<div class="terminal-prompt">$ <span class="prompt-cursor">▊</span></div>';
      }
      // Wire tab clicks
      tabBar.querySelectorAll('.report-file-tab').forEach(function(btn) {
        btn.addEventListener('click', function() {
          tabBar.querySelectorAll('.report-file-tab').forEach(function(b) { b.classList.remove('active'); });
          this.classList.add('active');
          var mode = this.dataset.mode;
          var key = this.dataset.key;
          var feedBody = document.getElementById('feed-body');
          if (mode === 'terminal') {
            if (window._cachedFeedHtml) {
              feedBody.innerHTML = window._cachedFeedHtml;
            } else {
              feedBody.innerHTML = '<div class="terminal-prompt">$ <span class="prompt-cursor">▊</span></div>';
            }
          } else if (key && window._reportFileContent[key]) {
            if (!window._cachedFeedHtml) window._cachedFeedHtml = feedBody.innerHTML;
            if (typeof marked !== 'undefined') {
              feedBody.innerHTML = '<div class="md-content" style="padding:0.5rem;">' + marked.parse(window._reportFileContent[key]) + '</div>';
            } else {
              feedBody.textContent = window._reportFileContent[key];
            }
            feedBody.scrollTop = 0;
          }
        });
      });
    }
  }

  function showPhaseModal(name, content) {
    var existing = document.getElementById('phase-modal');
    if (existing) existing.remove();
    var modal = document.createElement('div');
    modal.id = 'phase-modal';
    modal.className = 'modal-overlay visible';
    modal.style.cssText = 'z-index:300;';
    modal.innerHTML = '<div class="modal-content" style="max-width:1200px;max-height:85vh;">' +
      '<button class="close-btn" onclick="this.parentElement.parentElement.remove()">✕</button>' +
      '<h3 style="color:var(--color-accent);margin-bottom:0.5rem;">📄 ' + escapeHtml(name) + '</h3>' +
      '<div class="md-content" style="background:var(--color-paper-3);padding:1rem;border-radius:6px;overflow:auto;max-height:65vh;"></div></div>';
    // Close on click outside content
    modal.addEventListener('click', function(e) { if (e.target === modal) modal.remove(); });
    document.body.appendChild(modal);

    // Render markdown with marked
    var body = modal.querySelector('.md-content');
    if (typeof marked !== 'undefined') {
      body.innerHTML = marked.parse(content || '');
    } else {
      body.textContent = content || '';
    }
  }

  function renderMarkdown(md) {
    if (!md) return '';
    var html = md
      // Escape HTML tags first
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      // Horizontal rules
      .replace(/^---$/gm, '<hr>')
      // Headings (h1-h4)
      .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
      .replace(/^### (.+)$/gm, '<h3>$1</h3>')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/^# (.+)$/gm, '<h1>$1</h1>')
      // Blockquotes
      .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
      // Inline code
      .replace(/`([^`]+)`/g, '<code style="background:rgba(80,250,123,0.1);padding:0.1rem 0.3rem;border-radius:3px;font-size:0.78rem;">$1</code>')
      // Bold and italic
      .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      // Links
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color:var(--color-accent);">$1</a>');

    // Process tables on the escaped-but-not-yet-paragraphed text
    var lines = html.split('\n');
    var inTable = false, tableStarted = false;
    for (var li = 0; li < lines.length; li++) {
      var l = lines[li];
      var isSep = /^\|[-| :]+\|$/.test(l);
      var isRow = /^\|.+\|$/.test(l);
      if (isRow && !inTable) {
        var nextLine = lines[li + 1] || '';
        if (/^\|[-| :]+\|$/.test(nextLine)) {
          inTable = true; tableStarted = true;
          lines[li] = l.replace(/^\|(.+)\|$/, '<table class="rt"><thead><tr>$1</tr></thead>');
          continue;
        }
      }
      if (isSep && inTable && tableStarted) {
        lines[li] = '<tbody>';
        tableStarted = false;
        continue;
      }
      if (isRow && inTable) {
        lines[li] = l.replace(/^\|(.+)\|$/, function(m, c) {
          var cells = c.split('|').filter(function(x) { return x.trim(); });
          return '<tr>' + cells.map(function(x) { return '<td>' + x.trim() + '</td>'; }).join('') + '</tr>';
        });
        continue;
      }
      if (!isRow && !isSep && inTable) {
        lines[li] = '</tbody></table>\n' + l;
        inTable = false;
      }
    }
    html = lines.join('\n');

    // Lists, paragraphs, line breaks (on full html including table tags)
    html = html
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      .replace(/^\d+\.\s(.+)$/gm, '<li>$1</li>')
      .replace(/((<li>.*<\/li>\n?)+)/g, '<ul style="padding-left:1.5rem;margin:0.5rem 0;">$1</ul>')
      .replace(/\n\n/g, '</p><p style="margin:0.5rem 0;">')
      .replace(/\n/g, '<br>');

    // Style table cells
    html = html.replace(/<td>/g, '<td style="padding:0.3rem 0.5rem;border-bottom:1px solid rgba(53,90,102,0.2);">');

    return '<p style="margin:0.5rem 0;">' + html + '</p>';
  }

  // ─── Dynamic model list per profile ──────────────────────────────

  async function loadProfileModels() {
    var sel = document.getElementById('profile-select');
    var modelSel = document.getElementById('model-select');
    if (!modelSel) return;
    var profile = sel ? sel.value : '';

    // Clear current options
    modelSel.innerHTML = '<option value="">Loading...</option>';
    modelSel.disabled = true;

    try {
      var resp = await fetch('/api/profiles/models', { signal: AbortSignal.timeout(5000) });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      var allModels = await resp.json();
      var models = allModels[profile] || allModels[''] || [];

      modelSel.innerHTML = '';
      models.forEach(function(m) {
        var opt = document.createElement('option');
        opt.value = m.value;
        opt.setAttribute('data-provider', m.provider || '');
        opt.textContent = m.label;
        modelSel.appendChild(opt);
      });
      modelSel.disabled = false;
    } catch (e) {
      modelSel.innerHTML = '<option value="">Error loading models</option>';
      modelSel.disabled = true;
      console.error('loadProfileModels:', e);
    }
  }

  return {
    init: init, doSearch: doSearch, exportReport: exportReport,
    toggleSidebar: toggleSidebar, goHome: goHome,
    getCurrentMode: function() { return currentMode; },
    getCurrentReport: function() { return currentReport; },
    escapeHtml: escapeHtml,
  };
})();
