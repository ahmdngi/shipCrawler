/* Shipcrawler Core v5 — Phase-streaming, real-time terminal feed, animated report */
const ShipcrawlerCore = (() => {
  let currentMode = 'vessel';
  let currentReport = null;
  let phaseCount = 0;

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

    // Restore sidebar state + load history
    var sidebarOpen = localStorage.getItem('shipcrawler-sidebar-open') !== 'false';
    if (!sidebarOpen) { document.getElementById('sidebar').classList.add('closed'); document.body.classList.add('sidebar-closed'); }
    loadHistory();

    // Auto-load the most recent search from history
    var tasks = JSON.parse(localStorage.getItem('shipcrawler-history') || '[]');
    if (tasks.length > 0) {
      loadFromHistory(tasks[0].task_id);
    }

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
  }

  // ── Terminal Feed ──────────────────────────────────────────
  function showFeed() {
    if (!els.feed) return;
    els.feed.style.display = 'block';
    els.feed.innerHTML = '';
    if (els.finalSummary) els.finalSummary.style.display = 'none';
  }

  function hideFeed() {
    if (els.feed) els.feed.style.display = 'none';
  }

  function addPhaseLine(data, type) {
    if (!els.feed) return;
    const line = document.createElement('div');
    line.className = 'phase-line phase-' + type;

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
    els.feed.appendChild(line);
    els.feed.scrollTop = els.feed.scrollHeight;
  }

  function addProgressLine(phase, text) {
    if (!els.feed) return;
    const line = document.createElement('div');
    line.className = 'phase-line phase-progress';
    line.innerHTML = '<span class="phase-indent"></span><span class="phase-content" style="color:var(--color-ink-2);font-size:0.75rem;">' + escapeHtml(text) + '</span>';
    els.feed.appendChild(line);
    els.feed.scrollTop = els.feed.scrollHeight;
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
  function onPhaseStart(data) { addPhaseLine(data, 'start'); phaseCount++; }
  function onPhaseOutput(data) {
    var line = (data.line || '').trim();
    if (!line || line.length <= 3) return;
    var type = data.line_type || 'output';
    if (!els.feed) return;

    var lineEl = document.createElement('div');
    lineEl.className = 'phase-line phase-' + type;

    if (type === 'tool_start') {
      // Extract tool name from the line
      var tool = 'AGENT';
      var m = line.match(/\[Tool:\s*(\w+)\]/);
      if (m) tool = m[1].toUpperCase();
      var toolColor = toolColorMap(tool);
      lineEl.innerHTML = '<span class="phase-badge" style="background-color:' + toolColor + '">' + tool + '</span>' +
        '<span class="phase-content">' + escapeHtml(line) + '</span>';
    } else if (type === 'tool_error') {
      lineEl.innerHTML = '<span class="phase-badge" style="background-color:#e63946">ERROR</span><span class="phase-content" style="color:var(--color-accent);">' + escapeHtml(line) + '</span>';
    } else if (type === 'tool_detail') {
      lineEl.innerHTML = '<span class="phase-indent"></span><span class="phase-content" style="color:var(--color-ink-2);font-size:0.75rem;">' + escapeHtml(line) + '</span>';
    } else if (type === 'thinking') {
      lineEl.innerHTML = '<span class="phase-indent"></span><span class="phase-content" style="color:var(--color-ink-3);font-size:0.72rem;font-style:italic;">' + escapeHtml(line) + '</span>';
    } else {
      lineEl.innerHTML = '<span class="phase-indent"></span><span class="phase-content" style="color:var(--color-ink);font-size:0.78rem;">' + escapeHtml(line) + '</span>';
    }

    els.feed.appendChild(lineEl);
    els.feed.scrollTop = els.feed.scrollHeight;
  }

  function toolColorMap(tool) {
    var map = {
      'WEB_SEARCH': '#06d6a0', 'WEB_EXTRACT': '#06d6a0',
      'EQUASIS': '#4895ef', 'EQUASIS-CLI': '#4895ef',
      'SHODAN': '#f72585',
      'BROWSER_NAVIGATE': '#9b5de5', 'BROWSER': '#9b5de5',
      'BASH': '#ff9e00', 'TERMINAL': '#ff9e00',
      'READ': '#00bbf9', 'WRITE': '#00bbf9',
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
    els.feed.scrollTop = els.feed.scrollHeight;
  }

  function onPhaseError(data) { addPhaseLine(data, 'error'); }

  function onReportComplete(data) {
    if (els.finalSummary) {
      els.finalSummary.style.display = 'flex';
      var sp = id('summary-phases'); if (sp) sp.textContent = phaseCount;
      var sd = id('summary-duration'); if (sd) sd.textContent = data.duration_total ? data.duration_total + 's' : '?';
      var sf = id('summary-files'); if (sf) sf.textContent = (data.files || []).length;
    }
  }

  function onDone(data) { loadReport(data.task_id); }

  function onError(msg) {
    if (!els.feed) return;
    var line = document.createElement('div');
    line.className = 'phase-line phase-error';
    line.innerHTML = '<span class="phase-badge" style="background-color:#e63946">ERROR</span><span class="phase-content">❌ ' + escapeHtml(msg) + '</span>';
    els.feed.appendChild(line);
    if (els.btn) { els.btn.disabled = false; els.btn.textContent = 'Search'; }
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
    showFeed();

    try {
      var resp = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: query,
          mode: currentMode,
          context: els.contextInput ? els.contextInput.value.trim() : '',
        }),
      });

      if (!resp.ok) {
        var err = await resp.json().catch(function() { return {}; });
        throw new Error(err.error || 'HTTP ' + resp.status);
      }

      var data = await resp.json();
      if (els.btn) els.btn.textContent = 'Investigating...';

      // Connect SSE for real-time streaming
      ShipcrawlerSSE.connect(data.task_id, {
        onPhaseStart: onPhaseStart,
        onPhaseOutput: onPhaseOutput,
        onPhaseComplete: onPhaseComplete,
        onPhaseError: onPhaseError,
        onReportComplete: onReportComplete,
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
  function toggleSidebar() {
    var sb = document.getElementById('sidebar');
    var isClosed = sb.classList.toggle('closed');
    document.body.classList.toggle('sidebar-closed', isClosed);
    localStorage.setItem('shipcrawler-sidebar-open', String(!isClosed));
    document.getElementById('sidebar-toggle').textContent = isClosed ? '▶' : '◀';
  }

  function saveToHistory(entry) {
    var tasks = JSON.parse(localStorage.getItem('shipcrawler-history') || '[]');
    for (var i = 0; i < tasks.length; i++) {
      if (tasks[i].task_id === entry.task_id) { tasks[i] = entry; localStorage.setItem('shipcrawler-history', JSON.stringify(tasks)); renderHistory(); return; }
    }
    tasks.unshift(entry);
    if (tasks.length > 50) tasks.pop();
    localStorage.setItem('shipcrawler-history', JSON.stringify(tasks));
    renderHistory();
  }

  function loadHistory() { renderHistory(); }

  function renderHistory() {
    var list = document.getElementById('sidebar-list');
    if (!list) return;
    var tasks = JSON.parse(localStorage.getItem('shipcrawler-history') || '[]');
    if (tasks.length === 0) { list.innerHTML = '<div class="sidebar-empty">No searches yet</div>'; return; }
    var html = '';
    for (var i = 0; i < tasks.length; i++) {
      var t = tasks[i];
      var timeStr = new Date(t.timestamp || Date.now()).toLocaleString();
      var icon = t.mode === 'person' ? '👤' : '🚢';
      var active = (t.task_id === (currentReport && currentReport.task_id)) ? ' active' : '';
      html += '<div class="sidebar-item' + active + '" data-task-id="' + t.task_id + '">' +
        '<div class="sidebar-item-name">' + icon + ' ' + escapeHtml(t.name || 'Unknown') + '</div>' +
        '<div class="sidebar-item-meta"><span>' + icon + ' ' + (t.mode || 'vessel') + '</span><span>' + timeStr + '</span></div></div>';
    }
    list.innerHTML = html;
    var items = list.querySelectorAll('.sidebar-item');
    for (var i = 0; i < items.length; i++) {
      items[i].addEventListener('click', function() { loadFromHistory(this.dataset.taskId); });
    }
  }

  function loadFromHistory(taskId) {
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
          if (els.reportSection) els.reportSection.classList.add('visible');
          if (els.reportTs) els.reportTs.textContent = new Date().toLocaleString();
          displayReport(data);
          renderHistory();
          populateRightPanel(data);
        })
        .catch(function(err) {
          onError('Could not load report: ' + err.message);
        });
    }

    if (entry && entry.name) {
      doLoad('/api/report/by-name/' + encodeURIComponent(entry.name));
    } else if (entry) {
      // No name saved — try deriving from the task's report directory
      doLoad('/api/report/by-name/' + encodeURIComponent(taskId));
    } else {
      onError('Report not found in history');
    }
  }

  // Override loadReport to also save to history
  var _origLoadReport = loadReport;
  loadReport = function(taskId) {
    fetch('/api/report/' + taskId)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        currentReport = data;
        saveToHistory({ task_id: taskId, name: _currentQuery || taskId, mode: currentMode, timestamp: Date.now() });
        if (els.btn) { els.btn.disabled = false; els.btn.textContent = 'Search'; }
        if (els.input) els.input.value = '';
        setTimeout(function() { displayReport(data); populateRightPanel(data); }, 300);
      })
      .catch(function(err) { onError('Failed to load report: ' + err.message); });
  };

  // ── Right Panel ───────────────────────────────────────────
  function toggleRightPanel() {
    var rp = document.getElementById('right-panel');
    var isClosed = rp.classList.toggle('closed');
    document.body.classList.toggle('right-panel-closed', isClosed);
    localStorage.setItem('shipcrawler-right-panel-open', String(!isClosed));
    document.getElementById('right-panel-toggle').textContent = isClosed ? '▶' : '◀';
  }

  function populateRightPanel(data) {
    var list = document.getElementById('right-panel-list');
    if (!list) return;

    // Try phase_contents first (from API), then content for report files
    var files = {};
    if (data.phase_contents) {
      files = data.phase_contents;
    }

    // Also look for report files in the content (analyst-report, red-team, indicators)
    // Only show the clean report files, not raw phase files
    var reportFiles = {};
    var reportDir = data.report_dir;
    if (reportDir) {
      var niceNames = {
        'analyst-report.md': '📋 Analyst Report',
        'red-team-playbook.md': '⚔️ Red Team Playbook',
        'indicators-and-detection.md': '🔍 Detection Rules',
      };
      // Check if these exist in the phase_contents or we need to derive
      for (var key in files) {
        for (var nice in niceNames) {
          if (key.includes(nice.replace('.md','')) || key.includes('analyst') || key.includes('red-team') || key.includes('indicator')) {
            reportFiles[key] = { label: niceNames[nice] || key, content: files[key] };
          }
        }
      }
    }

    // Fallback: if no structured report files found, show what we have
    var keys = Object.keys(reportFiles);
    if (keys.length === 0) {
      keys = Object.keys(files);
      for (var i = 0; i < keys.length; i++) {
        reportFiles[keys[i]] = { label: keys[i].replace(/^phase-\d+-/, '').replace(/-/g, ' ').substring(0, 30), content: files[keys[i]] };
      }
    }
    if (keys.length === 0) {
      keys = ['analyst-report'];
      reportFiles['analyst-report'] = { label: '📋 Analyst Report', content: data.content || 'No content' };
    }

    var html = '';
    for (var i = 0; i < keys.length; i++) {
      var rf = reportFiles[keys[i]];
      html += '<div class="right-panel-item" data-content="' + escapeHtml(rf.content || rf.label) + '">' + rf.label + '</div>';
    }
    list.innerHTML = html || '<div class="right-panel-empty">No report files</div>';

    var items = list.querySelectorAll('.right-panel-item');
    for (var i = 0; i < items.length; i++) {
      items[i].addEventListener('click', function() {
        list.querySelectorAll('.right-panel-item').forEach(function(el) { el.classList.remove('active'); });
        this.classList.add('active');
        showPhaseModal(this.textContent.trim(), this.dataset.content);
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
    modal.innerHTML = '<div class="modal-content" style="max-width:800px;max-height:85vh;">' +
      '<button class="close-btn" onclick="this.parentElement.parentElement.remove()">✕</button>' +
      '<h3 style="color:var(--color-accent);margin-bottom:0.5rem;">📄 ' + escapeHtml(name) + '</h3>' +
      '<pre style="background:var(--color-paper-3);padding:1rem;border-radius:6px;overflow:auto;max-height:65vh;font-size:0.75rem;line-height:1.4;color:var(--color-ink);white-space:pre-wrap;word-break:break-word;">' + escapeHtml(content) + '</pre></div>';
    document.body.appendChild(modal);
  }

  return {
    init: init, doSearch: doSearch, exportReport: exportReport,
    toggleSidebar: toggleSidebar, toggleRightPanel: toggleRightPanel,
    getCurrentMode: function() { return currentMode; },
    getCurrentReport: function() { return currentReport; },
    escapeHtml: escapeHtml,
  };
})();
