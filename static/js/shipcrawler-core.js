/* Shipcrawler Core v4 — API client, queue polling, report orchestration */

const ShipcrawlerCore = (() => {
  let currentMode = 'vessel';
  let currentReport = null;

  const els = {};

  function init() {
    els.input = document.getElementById('search-input');
    els.btn = document.getElementById('search-btn');
    els.loader = document.getElementById('terminal-loader');
    els.loaderLines = els.loader.querySelectorAll('.line');
    els.targetDisp = document.getElementById('target-display');
    els.reportEl = document.getElementById('report-container');
    els.reportTs = document.getElementById('report-ts');
    els.modeLabel = document.getElementById('mode-label');
    els.vesselCards = document.getElementById('vessel-cards');
    els.personCards = document.getElementById('person-cards');
    els.contextInput = document.getElementById('context-input');
    els.contextContainer = document.getElementById('context-container');

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

  // ── Terminal Loader ─────────────────────────────────────────
  function resetLoader() {
    els.loaderLines.forEach(el => el.classList.remove('visible', 'done', 'active', 'error'));
  }
  function showLoader() {
    els.loader.style.display = 'block';
    resetLoader();
    setTimeout(() => els.loaderLines[0].classList.add('visible'), 100);
  }
  function advanceLoader(step) {
    for (let i = 0; i < step; i++) {
      els.loaderLines[i].classList.remove('active');
      els.loaderLines[i].classList.add('done');
    }
    if (step < els.loaderLines.length) {
      els.loaderLines[step].classList.add('visible', 'active');
    }
  }
  function completeLoader() {
    els.loaderLines.forEach((el, i) => {
      el.classList.remove('active');
      el.classList.add('done', 'visible');
    });
  }
  function failLoader(msg) {
    els.loaderLines.forEach((el, i) => {
      el.classList.remove('active');
      el.classList.add('done', 'visible');
    });
    const last = els.loaderLines[els.loaderLines.length - 1];
    last.textContent = '  ' + msg;
    last.classList.add('error');
  }

  // ── Search → Queue → Poll ─────────────────────────────────
  async function doSearch() {
    const query = els.input.value.trim();
    if (!query) return;

    els.btn.disabled = true;
    els.btn.textContent = 'Queueing...';
    els.reportEl.classList.remove('visible');
    document.querySelectorAll('.card').forEach(c => c.classList.remove('visible'));
    els.targetDisp.textContent = query;
    showLoader();
    advanceLoader(0);

    try {
      // 1. Submit to queue
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

      const { task_id, mode } = await resp.json();
      els.btn.textContent = 'Queued';
      advanceLoader(1);

      // 2. Poll status
      let pollCount = 0;
      const maxPolls = 300; // 5 minutes at 1s interval
      const poll = setInterval(async () => {
        pollCount++;
        try {
          const sr = await fetch(`/api/status/${task_id}`);
          const st = await sr.json();
          
          if (st.status === 'queued') {
            els.loaderLines[1].textContent = '  Queued — waiting for Hermes worker...';
          } else if (st.status === 'running') {
            els.loaderLines[1].textContent = '  Hermes is researching — this takes 30-60s...';
            advanceLoader(2);
          } else if (st.status === 'done') {
            clearInterval(poll);
            advanceLoader(3);
            els.loaderLines[3].textContent = '  Loading report...';
            els.btn.textContent = 'Loading...';
            
            // 3. Fetch Hermes output
            const rr = await fetch(`/api/report/${task_id}`);
            const result = await rr.json();
            
            completeLoader();
            els.input.value = '';
            setTimeout(() => displayHermesOutput(result, mode), 400);
            els.btn.disabled = false;
            els.btn.textContent = 'Search';
          } else if (st.status === 'error') {
            clearInterval(poll);
            els.vesselCards.style.display = 'none';
            els.personCards.style.display = 'none';
            failLoader('Research failed (exit ' + (st.hermes_exit || '?') + ')');
            els.btn.disabled = false;
            els.btn.textContent = 'Search';
          }
        } catch (e) {
          // Poll error — keep trying
        }

        if (pollCount >= maxPolls) {
          clearInterval(poll);
          failLoader('Timed out waiting for Hermes worker');
          els.btn.disabled = false;
          els.btn.textContent = 'Search';
        }
      }, 1000);

    } catch (err) {
      failLoader(err.message);
      els.btn.disabled = false;
      els.btn.textContent = 'Search';
    }
  }

  // ── Build Report from rendered cards ──────────────────────
  function buildReport(data, mode) {
    currentReport = data;
    els.reportEl.classList.add('visible');
    els.reportTs.textContent = new Date().toLocaleString();

    if (mode === 'person' || data.mode === 'person') {
      els.vesselCards.style.display = 'none';
      els.personCards.style.display = 'block';
      els.modeLabel.textContent = 'Mode: Person OSINT (Hermes-powered)';

      // Person Identity
      const pid = data.person_identity || {};
      ShipcrawlerUI.renderGrid('person-fields', {
        'Name': pid.Name || pid.name,
        'Location': pid.Location || pid.location,
        'Role': pid.Role || pid.role,
        'Emails': pid.Emails || pid.emails ? (pid.Emails || []).join(', ') : null,
      });

      // Education
      if (data.education && data.education.length) {
        document.querySelector('[data-card="p-professional"]').style.display = 'block';
        ShipcrawlerUI.renderProfessionalHistory(
          data.education.map(e => ({ role: '', company: e, period: '' }))
        );
      }

      // Professional history
      if (data.professional_history && data.professional_history.length) {
        document.querySelector('[data-card="p-professional"]').style.display = 'block';
        ShipcrawlerUI.renderProfessionalHistory(data.professional_history);
      }

      // Social media / digital footprint
      if (data.digital_footprint && data.digital_footprint.length) {
        ShipcrawlerUI.renderSocialMedia(data.digital_footprint);
        ShipcrawlerUI.renderDigitalFootprint(data.digital_footprint, []);
      }

      // Research impact
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

      // Publications
      if (ri.top_publications && ri.top_publications.length) {
        ShipcrawlerUI.renderPublications(ri.top_publications);
      }

      // Coauthors
      if (data.coauthors && data.coauthors.length) {
        ShipcrawlerUI.renderCoauthors(data.coauthors);
      }

      // Confidence
      const conf = data.confidence_assessment || {};
      ShipcrawlerUI.renderConfidenceAssessment(conf);

      // Targeting scenarios
      const ts = data.targeting_scenarios || {};
      ShipcrawlerUI.renderTargetingScenarios(ts);

      // Analysis
      ShipcrawlerUI.renderPersonAnalysis({
        exposure_score: (data.digital_footprint || []).length * 5,
        confidence: conf.overall || 'MEDIUM',
        risk_tier: (ts.vectors || []).length >= 3 ? 'HIGH' : 'MEDIUM',
        notes: [
          `Research from Hermes agent`,
          `${(data.digital_footprint || []).length} data points`,
          `${(data.coauthors || []).length} co-authors identified`,
        ],
        recommendations: ['Review the full markdown report for details'],
      });

    } else {
      // Vessel mode
      els.vesselCards.style.display = 'block';
      els.personCards.style.display = 'none';
      els.modeLabel.textContent = 'Mode: Vessel OSINT (Hermes-powered)';

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
        notes: ['Report generated by Hermes agent'],
      });
    }

    setTimeout(ShipcrawlerUI.animateCards, 100);
  }

  // ── Display Hermes Output ──────────────────────────────
  function displayHermesOutput(data, mode) {
    currentReport = data;
    
    // If we have structured data, use the card renderer
    if (data.vessel_identity || data.person_identity) {
      buildReport(data, mode);
      return;
    }
    
    // Fallback: raw text in pre tag
    const content = data.content || 'No output generated.';
    
    // Remove any existing hermes card
    const existing = document.getElementById('hermes-card');
    if (existing) existing.remove();
    
    // Build the card
    const card = document.createElement('div');
    card.id = 'hermes-card';
    card.className = 'card full-width visible';
    card.style.cssText = 'border-color:var(--color-ink-3);margin-top:1rem;';
    card.innerHTML =
      '<div class="card-title"><span>🤖</span> Hermes Research Output</div>' +
      '<pre style="white-space:pre-wrap;font-family:\'Fira Code\',monospace;font-size:0.78rem;line-height:1.5;color:var(--color-ink);padding:1rem;max-height:70vh;overflow-y:auto;background:rgba(0,0,0,0.3);border-radius:6px;">' + esc(content) + '</pre>';
    
    // Replace vessel/person cards with the Hermes card
    els.vesselCards.style.display = 'block';
    els.vesselCards.innerHTML = '';
    els.vesselCards.appendChild(card);
    els.personCards.style.display = 'none';
    els.personCards.innerHTML = '';
    
    // Show the report
    els.reportEl.classList.add('visible');
    els.reportTs.textContent = new Date().toLocaleString();
    els.modeLabel.textContent = 'Mode: ' + (mode === 'person' ? 'Person' : 'Vessel') + ' OSINT (Hermes)';
    
    // Scroll the page to show the card
    setTimeout(() => card.scrollIntoView({ behavior: 'smooth', block: 'start' }), 200);
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
    lines.push('  SHIPCRAWLER V4 REPORT');
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

  function esc(s) {
    if (typeof s !== 'string') return String(s || '');
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  return {
    init, doSearch, buildReport, exportReport,
    getCurrentMode: () => currentMode,
    getCurrentReport: () => currentReport,
    esc,
  };
})();
