/* Shipcrawler UI — All card renderers */

const ShipcrawlerUI = (() => {
  function esc(s) {
    if (typeof s !== 'string') return String(s || '');
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function animateCards() {
    const mode = ShipcrawlerCore.getCurrentMode();
    const cards = document.querySelectorAll(mode === 'vessel'
      ? '#vessel-cards .card' : '#person-cards .card');
    cards.forEach((card, i) => setTimeout(() => card.classList.add('visible'), i * 150));
  }

  // ── Grid Renderers ─────────────────────────────────────────
  function renderGrid(containerId, fields) {
    const c = document.getElementById(containerId);
    if (!c) return;
    c.innerHTML = '';
    for (const [label, value] of Object.entries(fields)) {
      if (value === null || value === undefined || value === '') continue;
      const el = document.createElement('div');
      el.className = 'card-field';
      el.innerHTML = `<span class="label">${esc(label)}</span><span class="value">${esc(value)}</span>`;
      c.appendChild(el);
    }
  }

  function renderStatusGrid(containerId, fields) {
    const c = document.getElementById(containerId);
    if (!c) return;
    c.innerHTML = '';
    const hasData = Object.values(fields).some(v => v !== null && v !== undefined && v !== '');
    if (!hasData) {
      c.innerHTML = '<div style="color:var(--color-ink-2);font-size:0.85rem;padding:0.5rem 0;">No AIS data available — vessel not currently broadcasting or MMSI could not be resolved from name alone.</div>';
      return;
    }
    for (const [label, value] of Object.entries(fields)) {
      if (value === null || value === undefined || value === '') continue;
      const el = document.createElement('div');
      el.className = 'card-field';
      const cls = label === 'Status' ? 'gold' : 'green';
      el.innerHTML = `<span class="label">${esc(label)}</span><span class="value ${cls}">${esc(value)}</span>`;
      c.appendChild(el);
    }
  }

  // ── Port Calls ──────────────────────────────────────────────
  function renderPortCalls(calls) {
    const c = document.getElementById('port-calls-content');
    if (!c) return;
    c.innerHTML = '';
    if (!calls || calls.length === 0) {
      c.innerHTML = '<div style="color:var(--color-ink-2);font-size:0.85rem;">No port call data available.</div>';
      return;
    }
    const table = document.createElement('table');
    table.className = 'port-calls-table';
    table.innerHTML = `<thead><tr><th>Port</th><th>Date</th><th>Duration</th></tr></thead>
      <tbody>${calls.map(call => `<tr><td>${esc(call.port)}</td><td>${esc(call.date)}</td><td>${esc(call.duration)}</td></tr>`).join('')}</tbody>`;
    c.appendChild(table);
  }

  // ── Shodan ──────────────────────────────────────────────────
  function renderShodan(data) {
    const c = document.getElementById('shodan-content');
    if (!c) return;
    c.innerHTML = '';
    const results = data.results || [];
    const summary = data.summary || '';
    const sumEl = document.createElement('div');
    sumEl.className = 'shodan-summary';
    sumEl.textContent = `📡 ${summary}`;
    c.appendChild(sumEl);
    if (results.length === 0) {
      const e = document.createElement('div');
      e.style.cssText = 'color:var(--color-ink-2);font-size:0.85rem;';
      e.textContent = 'No Shodan results — vessel is not exposing internet-facing systems.';
      c.appendChild(e);
      return;
    }
    for (const svc of results) {
      const item = document.createElement('div');
      item.className = 'shodan-item';
      item.innerHTML = `<span class="shodan-ip">${esc(svc.ip)}</span>:<span class="shodan-port">${svc.port}</span>
        <span class="shodan-org">${esc(svc.org || 'unknown')}</span>
        ${svc.hostnames && svc.hostnames.length ? '<br><span style="color:var(--color-ink-2);font-size:0.7rem;">' + svc.hostnames.join(', ') + '</span>' : ''}
        <div class="shodan-data">${esc(svc.data || '')}</div>`;
      c.appendChild(item);
    }
  }

  // ── Red Team ────────────────────────────────────────────────
  function renderRedTeam(pb) {
    const c = document.getElementById('red-team-content');
    if (!c) return;
    c.innerHTML = '';
    if (!pb || !pb.vectors || pb.vectors.length === 0) {
      c.innerHTML = '<div style="color:var(--color-ink-2);font-size:0.85rem;">Red team playbook not available for this vessel type.</div>';
      return;
    }
    const sum = document.createElement('div');
    sum.style.cssText = 'font-size:0.85rem;color:var(--color-ink-2);margin-bottom:1rem;padding:0.5rem 0.75rem;background:rgba(108,138,148,0.08);border-left:3px solid var(--color-ink-3);border-radius:4px;';
    sum.textContent = pb.summary || '';
    if (sum.textContent) c.appendChild(sum);
    for (const vec of pb.vectors) {
      const vc = document.createElement('div');
      vc.className = 'vector-card';
      vc.innerHTML = `<h4>${esc(vec.name)}</h4>
        <div class="meta">
          <span>⚙️ Difficulty: <strong>${esc(vec.difficulty)}</strong></span>
          <span>💰 Cost: <strong>${esc(vec.cost)}</strong></span>
          <span>👁️ Detection: <strong>${esc(vec.detection_prob)}</strong></span>
        </div>`;
      if (vec.equipment && vec.equipment.length) {
        vc.innerHTML += `<div class="section-label">Equipment</div><ul>${vec.equipment.map(e => `<li>${esc(e)}</li>`).join('')}</ul>`;
      }
      if (vec.steps && vec.steps.length) {
        vc.innerHTML += `<div class="section-label">Execution Steps</div><ol>${vec.steps.map(s => `<li>${esc(s)}</li>`).join('')}</ol>`;
      }
      if (vec.detection_points && vec.detection_points.length) {
        vc.innerHTML += `<div class="section-label">M-SOC Detection Points</div>
          <table class="indicator-table">
            <thead><tr><th>Detection Point</th><th>Expected Signal</th><th>Tool</th></tr></thead>
            <tbody>${vec.detection_points.map(dp => `<tr><td>${esc(dp.point)}</td><td>${esc(dp.signal)}</td><td>${esc(dp.tool)}</td></tr>`).join('')}</tbody>
          </table>`;
      }
      c.appendChild(vc);
    }
  }

  // ── Detection Rules ─────────────────────────────────────────
  function renderDetection(dr) {
    const c = document.getElementById('detection-content');
    if (!c) return;
    c.innerHTML = '';
    if (!dr || !dr.indicators) {
      c.innerHTML = '<div style="color:var(--color-ink-2);font-size:0.85rem;">Detection rules not available.</div>';
      return;
    }
    if (dr.indicators && dr.indicators.length) {
      c.innerHTML += `<div class="section-label" style="color:var(--color-accent);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.5rem;">Detection Indicators</div>
        <table class="indicator-table">
          <thead><tr><th>ID</th><th>Type</th><th>Phase</th><th>Priority</th><th>Description</th></tr></thead>
          <tbody>${dr.indicators.map(i => `<tr><td>${esc(i.id)}</td><td>${esc(i.type)}</td><td>${esc(i.phase)}</td><td class="pri-${i.priority}">${esc(i.priority)}</td><td>${esc(i.description)}</td></tr>`).join('')}</tbody>
        </table>`;
    }
    if (dr.elastic_rules && dr.elastic_rules.length) {
      c.innerHTML += `<div class="section-label" style="color:var(--color-accent);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;margin:1rem 0 0.5rem;">Elastic SIEM Rules</div>`;
      for (const r of dr.elastic_rules) {
        c.innerHTML += `<div class="detail-card"><div class="dc-title">${esc(r.name)}</div><div class="dc-meta">Type: ${esc(r.type)}</div><div style="font-size:0.75rem;color:var(--color-ink-2);">${esc(r.query)}${r.condition ? '<br>Condition: ' + esc(r.condition) : ''}</div></div>`;
      }
    }
    if (dr.zeek_scripts && dr.zeek_scripts.length) {
      c.innerHTML += `<div class="section-label" style="color:var(--color-accent);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;margin:1rem 0 0.5rem;">Zeek Scripts</div>`;
      for (const z of dr.zeek_scripts) {
        c.innerHTML += `<div class="detail-card"><div class="dc-title">${esc(z.name)}</div><div style="font-size:0.78rem;color:var(--color-ink-2);">${esc(z.description)}</div></div>`;
      }
    }
    if (dr.runbook) {
      c.innerHTML += `<div class="section-label" style="color:var(--color-accent);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;margin:1rem 0 0.5rem;">M-SOC Runbook</div>`;
      for (const [key, val] of Object.entries(dr.runbook)) {
        c.innerHTML += `<div class="runbook-title">${esc(key)}</div>`;
        if (val.triage) val.triage.forEach(s => { c.innerHTML += `<div class="runbook-step">${esc(s)}</div>`; });
      }
    }
  }

  // ── Analysis ────────────────────────────────────────────────
  function renderAnalysis(analysis) {
    const c = document.getElementById('analysis-content');
    if (!c) return;
    c.innerHTML = '';
    const tier = (analysis.risk_tier || 'LOW').toUpperCase();
    const fields = { 'Home Zone': analysis.home_zone, 'Pattern': analysis.pattern, 'Confidence': analysis.confidence };
    const grid = document.createElement('div');
    grid.className = 'card-grid';
    for (const [label, value] of Object.entries(fields)) {
      if (!value) continue;
      grid.innerHTML += `<div class="card-field"><span class="label">${esc(label)}</span><span class="value">${esc(value)}</span></div>`;
    }
    grid.innerHTML += `<div class="card-field"><span class="label">Risk Tier</span><span class="risk-badge risk-${tier}">${tier}</span></div>`;
    c.appendChild(grid);
    if (analysis.notes && analysis.notes.length) {
      const ul = document.createElement('ul');
      ul.className = 'analysis-notes';
      analysis.notes.forEach(n => { const li = document.createElement('li'); li.textContent = n; ul.appendChild(li); });
      c.appendChild(ul);
    }
  }

  // ── Person Renderers ────────────────────────────────────────
  function renderPersonIdentity(person) {
    if (!person) {
      document.getElementById('person-fields').innerHTML = '<div style="color:var(--color-ink-2);font-size:0.85rem;">No identity data.</div>';
      return;
    }
    renderGrid('person-fields', {
      'Name': person.name,
      'Aliases': person.aliases ? person.aliases.join(', ') : null,
      'Emails': person.emails ? person.emails.join(', ') : null,
      'Phones': person.phones ? person.phones.join(', ') : null,
      'Employer': person.employer,
      'Role': person.role,
      'Location': person.location,
      'Education': person.education ? person.education.join(', ') : null,
    });
  }

  function renderProfessionalHistory(history) {
    const c = document.getElementById('professional-content');
    if (!c) return;
    c.innerHTML = '';
    if (!history || history.length === 0) {
      c.innerHTML = '<div style="color:var(--color-ink-2);font-size:0.85rem;">No professional history data.</div>';
      return;
    }
    for (const h of history) {
      c.innerHTML += `<div class="detail-card"><div class="dc-title">${esc(h.role || '')} @ ${esc(h.company || '')}</div><div class="dc-meta">${esc(h.period || '')}</div><div style="font-size:0.78rem;color:var(--color-ink-2);">${esc(h.description || '')}</div></div>`;
    }
  }

  function renderSocialMedia(social) {
    const c = document.getElementById('social-content');
    if (!c) return;
    c.innerHTML = '';
    if (!social || social.length === 0) {
      c.innerHTML = '<div style="color:var(--color-ink-2);font-size:0.85rem;">No social media profiles identified.</div>';
      return;
    }
    const div = document.createElement('div');
    div.className = 'person-social';
    for (const s of social) {
      const a = document.createElement('a');
      a.href = s.url || '#';
      a.target = '_blank';
      a.innerHTML = `${esc(s.platform)} ${s.handle ? '— ' + esc(s.handle) : ''}`;
      a.title = s.url || '';
      div.appendChild(a);
    }
    c.appendChild(div);
    const list = document.createElement('div');
    list.style.cssText = 'margin-top:0.75rem;font-size:0.78rem;';
    for (const s of social) {
      const row = document.createElement('div');
      row.style.cssText = 'padding:0.3rem 0;border-bottom:1px solid rgba(53,90,102,0.1);word-break:break-all;';
      row.innerHTML = `<span style="color:var(--color-accent-2)">${esc(s.platform)}</span>: <a href="${esc(s.url)}" target="_blank" style="color:var(--color-ink);text-decoration:none;">${esc(s.url)}</a>`;
      list.appendChild(row);
    }
    c.appendChild(list);
  }

  function renderDigitalFootprint(footprint, breaches) {
    const c = document.getElementById('footprint-content');
    if (!c) return;
    c.innerHTML = '';
    if (footprint && footprint.length) {
      c.innerHTML += `<div class="section-label" style="color:var(--color-ink-2);font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.5rem;">Online Presence</div>`;
      for (const f of footprint) {
        c.innerHTML += `<div class="detail-card"><div class="dc-title">${esc(f.source || '')}</div><div style="font-size:0.78rem;color:var(--color-ink-2);">${esc(f.detail || '')}</div></div>`;
      }
    } else {
      c.innerHTML += '<div style="color:var(--color-ink-2);font-size:0.85rem;margin-bottom:0.75rem;">No online footprint data.</div>';
    }
    if (breaches && breaches.length) {
      c.innerHTML += `<div class="section-label" style="color:var(--color-accent);font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;margin:1rem 0 0.5rem;">🚨 Data Breaches</div>`;
      for (const b of breaches) {
        c.innerHTML += `<div class="breach-item">⚠️ ${esc(b.name || '')} — ${esc(b.date || '')}: ${esc(b.data || '')}</div>`;
      }
    }
  }

  function renderPersonAnalysis(analysis) {
    const c = document.getElementById('person-analysis-content');
    if (!c) return;
    c.innerHTML = '';
    if (!analysis) {
      c.innerHTML = '<div style="color:var(--color-ink-2);font-size:0.85rem;">No analysis available.</div>';
      return;
    }
    const tier = (analysis.risk_tier || 'LOW').toUpperCase();
    const grid = document.createElement('div');
    grid.className = 'card-grid';
    grid.innerHTML += `<div class="card-field"><span class="label">Exposure Score</span><span class="value ${analysis.exposure_score >= 30 ? 'gold' : 'green'}">${analysis.exposure_score}/100</span></div>`;
    grid.innerHTML += `<div class="card-field"><span class="label">Confidence</span><span class="value">${esc(analysis.confidence || '')}</span></div>`;
    grid.innerHTML += `<div class="card-field"><span class="label">Risk Tier</span><span class="risk-badge risk-${tier}">${tier}</span></div>`;
    c.appendChild(grid);
    if (analysis.notes && analysis.notes.length) {
      const ul = document.createElement('ul');
      ul.className = 'analysis-notes';
      analysis.notes.forEach(n => { const li = document.createElement('li'); li.textContent = n; ul.appendChild(li); });
      c.appendChild(ul);
    }
    if (analysis.recommendations && analysis.recommendations.length) {
      c.innerHTML += `<div class="section-label" style="color:var(--color-accent);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;margin:1rem 0 0.5rem;">Recommendations</div>`;
      const ul = document.createElement('ul');
      ul.className = 'analysis-notes';
      analysis.recommendations.forEach(n => { const li = document.createElement('li'); li.textContent = n; ul.appendChild(li); });
      c.appendChild(ul);
    }
  }

  // ── Confidence Assessment ────────────────────────────────────
  function renderConfidenceAssessment(confidence) {
    const c = document.getElementById('confidence-content');
    if (!c) return;
    c.innerHTML = '';
    if (!confidence || !confidence.categories) {
      c.innerHTML = '<div style="color:var(--color-ink-2);font-size:0.85rem;">No confidence assessment available.</div>';
      return;
    }
    const overall = (confidence.overall || 'LOW').toUpperCase();
    const grid = document.createElement('div');
    grid.className = 'card-grid';
    grid.innerHTML += `<div class="card-field"><span class="label">Overall</span><span class="risk-badge risk-${overall}">${overall}</span></div>`;
    c.appendChild(grid);

    const table = document.createElement('table');
    table.className = 'indicator-table';
    table.innerHTML = '<thead><tr><th>Category</th><th>Confidence</th></tr></thead><tbody>';
    for (const [cat, val] of Object.entries(confidence.categories)) {
      const valUpper = (val || 'LOW').toUpperCase();
      table.innerHTML += `<tr><td>${esc(cat)}</td><td style="color:${valUpper === 'HIGH' ? 'var(--color-green)' : valUpper === 'MEDIUM' ? 'var(--color-gold)' : 'var(--color-ink-2)'}">${valUpper}</td></tr>`;
    }
    table.innerHTML += '</tbody>';
    c.appendChild(table);
  }

  // ── Affiliation Timeline ──────────────────────────────────────
  function renderAffiliationTimeline(timeline) {
    const c = document.getElementById('affiliation-content');
    if (!c) return;
    c.innerHTML = '';
    if (!timeline) {
      c.innerHTML = '<div style="color:var(--color-ink-2);font-size:0.85rem;">No timeline data.</div>';
      return;
    }
    c.innerHTML += `<div class="section-label" style="color:var(--color-accent);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.5rem;">Current Positions</div>`;
    const currents = timeline.current_positions || [];
    if (currents.length === 0) {
      c.innerHTML += '<div style="color:var(--color-ink-2);font-size:0.85rem;margin-bottom:0.75rem;">No current positions.</div>';
    }
    for (const pos of currents) {
      c.innerHTML += `<div class="detail-card"><div class="dc-title">${esc(pos.role)} @ ${esc(pos.organization)}</div><div class="dc-meta">${esc(pos.period || 'Present')} ${pos.department ? '· ' + esc(pos.department) : ''}</div></div>`;
    }

    const pasts = timeline.past_positions || [];
    if (pasts.length) {
      c.innerHTML += `<div class="section-label" style="color:var(--color-ink-2);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;margin:1rem 0 0.5rem;">Past Positions</div>`;
      for (const pos of pasts) {
        c.innerHTML += `<div class="detail-card"><div class="dc-title">${esc(pos.role)} @ ${esc(pos.organization)}</div><div class="dc-meta">${esc(pos.period)} ${pos.department ? '· ' + esc(pos.department) : ''}</div></div>`;
      }
    }

    if (timeline.education && timeline.education.length) {
      c.innerHTML += `<div class="section-label" style="color:var(--color-ink-2);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;margin:1rem 0 0.5rem;">Education</div>`;
      for (const edu of timeline.education) {
        c.innerHTML += `<div class="detail-card" style="font-size:0.82rem;">${esc(edu)}</div>`;
      }
    }

    if (timeline.geographic_summary) {
      c.innerHTML += `<div style="margin-top:0.75rem;font-size:0.78rem;color:var(--color-ink-2);">📍 Geographic regions: ${esc(timeline.geographic_summary)}</div>`;
    }
  }

  // ── Research Impact ────────────────────────────────────────────
  function renderResearchImpact(impact) {
    const c = document.getElementById('research-impact-content');
    if (!c) return;
    c.innerHTML = '';
    if (!impact || !impact.total_publications) {
      c.innerHTML = '<div style="color:var(--color-ink-2);font-size:0.85rem;">No research impact data.</div>';
      return;
    }
    const cm = impact.citation_metrics || {};
    // Metrics grid
    const grid = document.createElement('div');
    grid.className = 'card-grid';
    grid.innerHTML = `<div class="card-field"><span class="label">Total Publications</span><span class="value">${impact.total_publications}</span></div>`;
    if (cm.total_citations) grid.innerHTML += `<div class="card-field"><span class="label">Total Citations</span><span class="value" style="color:var(--color-green)">${cm.total_citations.toLocaleString()}</span></div>`;
    if (cm.h_index) grid.innerHTML += `<div class="card-field"><span class="label">h-index</span><span class="value" style="color:var(--color-green)">${cm.h_index}</span></div>`;
    if (cm.i10_index) grid.innerHTML += `<div class="card-field"><span class="label">i10-index</span><span class="value" style="color:var(--color-gold)">${cm.i10_index}</span></div>`;
    if (impact.career_span_years) grid.innerHTML += `<div class="card-field"><span class="label">Career Span</span><span class="value">${impact.career_span_years} years (${impact.first_year}–${impact.last_year})</span></div>`;
    if (impact.coauthor_count) grid.innerHTML += `<div class="card-field"><span class="label">Co-authors</span><span class="value">${impact.coauthor_count}+</span></div>`;
    c.appendChild(grid);

    // Publications by year
    const byYear = impact.publications_by_year || {};
    const yearKeys = Object.keys(byYear);
    if (yearKeys.length) {
      c.innerHTML += `<div class="section-label" style="color:var(--color-accent);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;margin:1rem 0 0.5rem;">Publications by Year</div>`;
      const ytable = document.createElement('table');
      ytable.className = 'port-calls-table';
      ytable.innerHTML = '<thead><tr><th>Year</th><th>Papers</th></tr></thead><tbody>';
      for (const yr of yearKeys) {
        ytable.innerHTML += `<tr><td>${esc(yr)}</td><td>${byYear[yr]}</td></tr>`;
      }
      ytable.innerHTML += '</tbody>';
      c.appendChild(ytable);
    }

    // Top publications
    const topPubs = cm.top_publications || impact.top_publications || [];
    if (topPubs.length) {
      c.innerHTML += `<div class="section-label" style="color:var(--color-accent);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;margin:1rem 0 0.5rem;">Most Cited Publications</div>`;
      for (const pub of topPubs.slice(0, 5)) {
        c.innerHTML += `<div class="detail-card"><div class="dc-title">${esc(pub.title)}</div><div class="dc-meta">${pub.citations ? pub.citations + ' citations' : ''} ${pub.year ? '· ' + pub.year : ''}</div></div>`;
      }
    }
  }

  // ── Publications ──────────────────────────────────────────────
  function renderPublications(pubs) {
    const c = document.getElementById('publications-content');
    if (!c) return;
    c.innerHTML = '';
    if (!pubs || pubs.length === 0) {
      c.innerHTML = '<div style="color:var(--color-ink-2);font-size:0.85rem;">No publication data.</div>';
      return;
    }
    c.innerHTML += `<div style="color:var(--color-ink-2);font-size:0.78rem;margin-bottom:0.75rem;">Showing ${pubs.length} publication(s).</div>`;
    const table = document.createElement('table');
    table.className = 'port-calls-table';
    table.innerHTML = '<thead><tr><th>Year</th><th>Title</th><th>Venue</th></tr></thead><tbody>';
    const sorted = [...pubs].sort((a, b) => (b.year || '').localeCompare(a.year || ''));
    for (const pub of sorted.slice(0, 30)) {
      const venue = pub.journal || pub.venue || pub.type || '';
      table.innerHTML += `<tr><td style="white-space:nowrap">${esc(pub.year || '')}</td><td>${esc(pub.title || '').substring(0, 80)}</td><td style="font-size:0.75rem;color:var(--color-ink-2)">${esc(venue).substring(0, 40)}</td></tr>`;
    }
    table.innerHTML += '</tbody>';
    c.appendChild(table);
    if (pubs.length > 30) {
      c.innerHTML += `<div style="margin-top:0.5rem;font-size:0.78rem;color:var(--color-ink-2);">... and ${pubs.length - 30} more.</div>`;
    }
  }

  // ── Co-authors / Collaboration Network ─────────────────────────
  function renderCoauthors(coauthors) {
    const c = document.getElementById('coauthors-content');
    if (!c) return;
    c.innerHTML = '';
    if (!coauthors || coauthors.length === 0) {
      c.innerHTML = '<div style="color:var(--color-ink-2);font-size:0.85rem;">No co-author data extracted.</div>';
      return;
    }
    const sorted = [...coauthors].sort((a, b) => (b.shared_papers || 0) - (a.shared_papers || 0));
    const table = document.createElement('table');
    table.className = 'indicator-table';
    table.innerHTML = '<thead><tr><th>Co-author</th><th>Shared Papers</th></tr></thead><tbody>';
    for (const ca of sorted.slice(0, 15)) {
      table.innerHTML += `<tr><td>${esc(ca.name)}</td><td>${ca.shared_papers || 1}</td></tr>`;
    }
    table.innerHTML += '</tbody>';
    c.appendChild(table);
  }

  function renderTargetingScenarios(ts) {
    const c = document.getElementById('targeting-content');
    if (!c) return;
    c.innerHTML = '';
    if (!ts || !ts.vectors || ts.vectors.length === 0) {
      c.innerHTML = '<div style="color:var(--color-ink-2);font-size:0.85rem;">No targeting scenarios available. Ask the Hermes agent to research and seed attack vectors.</div>';
      return;
    }
    const sum = document.createElement('div');
    sum.style.cssText = 'font-size:0.85rem;color:var(--color-ink-2);margin-bottom:1rem;padding:0.5rem 0.75rem;background:rgba(108,138,148,0.08);border-left:3px solid var(--color-ink-3);border-radius:4px;';
    sum.textContent = ts.summary || '';
    if (sum.textContent) c.appendChild(sum);
    for (const vec of ts.vectors) {
      const vc = document.createElement('div');
      vc.className = 'vector-card';
      vc.innerHTML = `<h4>${esc(vec.name)}</h4><div class="meta"><span>⚙️ Difficulty: <strong>${esc(vec.difficulty)}</strong></span><span>💰 Cost: <strong>${esc(vec.cost)}</strong></span><span>👁️ Detection: <strong>${esc(vec.detection_prob)}</strong></span></div>`;
      if (vec.equipment && vec.equipment.length) {
        vc.innerHTML += `<div class="section-label">Equipment</div><ul>${vec.equipment.map(e => `<li>${esc(e)}</li>`).join('')}</ul>`;
      }
      if (vec.steps && vec.steps.length) {
        vc.innerHTML += `<div class="section-label">Execution Steps</div><ol>${vec.steps.map(s => `<li>${esc(s)}</li>`).join('')}</ol>`;
      }
      if (vec.detection_points && vec.detection_points.length) {
        vc.innerHTML += `<div class="section-label">Detection Points</div><table class="indicator-table"><thead><tr><th>Point</th><th>Expected Signal</th><th>Tool</th></tr></thead><tbody>${vec.detection_points.map(dp => `<tr><td>${esc(dp.point)}</td><td>${esc(dp.signal)}</td><td>${esc(dp.tool)}</td></tr>`).join('')}</tbody></table>`;
      }
      c.appendChild(vc);
    }
  }

  // ── Theme Editor ────────────────────────────────────────────
  function openThemeEditor() {
    const overlay = document.getElementById('theme-editor-overlay');
    if (!overlay) return;
    overlay.classList.add('visible');
    const root = document.documentElement;
    const vars = ['--color-paper', '--color-paper-2', '--color-paper-3', '--color-ink', '--color-ink-2', '--color-ink-3', '--color-accent', '--color-accent-2', '--color-accent-ink', '--color-green', '--color-gold'];
    const container = overlay.querySelector('.theme-fields');
    container.innerHTML = vars.map(v => {
      const val = getComputedStyle(root).getPropertyValue(v).trim();
      const name = v.replace('--color-', '').replace(/-/g, ' ');
      return `<div class="theme-field"><label>${name}</label><input type="text" data-var="${v}" value="${val}"></div>`;
    }).join('');
    container.querySelectorAll('input').forEach(input => {
      input.addEventListener('input', () => {
        document.documentElement.style.setProperty(input.dataset.var, input.value);
      });
    });
  }

  function saveTheme() {
    const vars = ['--color-paper', '--color-paper-2', '--color-paper-3', '--color-ink', '--color-ink-2', '--color-ink-3', '--color-accent', '--color-accent-2', '--color-accent-ink', '--color-green', '--color-gold'];
    const theme = {};
    vars.forEach(v => {
      theme[v] = getComputedStyle(document.documentElement).getPropertyValue(v).trim();
    });
    try {
      localStorage.setItem('shipcrawler-theme', JSON.stringify(theme));
    } catch {}
    document.getElementById('theme-editor-overlay').classList.remove('visible');
  }

  function loadTheme() {
    try {
      const saved = localStorage.getItem('shipcrawler-theme');
      if (saved) {
        const theme = JSON.parse(saved);
        for (const [key, val] of Object.entries(theme)) {
          document.documentElement.style.setProperty(key, val);
        }
      }
    } catch {}
  }

  function closeThemeEditor() {
    loadTheme(); // Revert
    document.getElementById('theme-editor-overlay').classList.remove('visible');
  }

  return {
    animateCards, renderGrid, renderStatusGrid,
    renderPortCalls, renderShodan, renderRedTeam,
    renderDetection, renderAnalysis,
    renderPersonIdentity, renderProfessionalHistory,
    renderSocialMedia, renderDigitalFootprint,
    renderPersonAnalysis, renderTargetingScenarios,
    renderConfidenceAssessment, renderAffiliationTimeline,
    renderResearchImpact, renderPublications, renderCoauthors,
    openThemeEditor, saveTheme, loadTheme, closeThemeEditor,
  };
})();
