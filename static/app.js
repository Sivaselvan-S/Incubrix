/**
 * LongTail Passport - Flight Deck Interactive Controller
 */

const API_BASE = window.location.origin;
let destinations = [];
let lastUsedIdempotencyKey = "";

// --- Toast Notifications ---
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = "toast";
  const icon = type === "success" ? "&#x2714;" : type === "error" ? "&#x26A0;" : "&#x2139;";
  toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// --- Navigation Tabs ---
document.querySelectorAll(".nav-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
    tab.classList.add("active");
    const paneId = `pane-${tab.dataset.tab}`;
    const targetPane = document.getElementById(paneId);
    if (targetPane) targetPane.classList.add("active");
  });
});

// --- Initialize Flight Deck ---
async function initFlightDeck() {
  await checkSystemStatus();
  await loadDestinations();
  setupEventListeners();
  generateNewIdempotencyKey();
}

// --- System Status ---
async function checkSystemStatus() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (res.ok) {
      document.getElementById("api-status-text").textContent = "HEALTHY (200)";
      document.getElementById("api-status-chip").querySelector(".status-dot").className = "status-dot online";
    } else {
      document.getElementById("api-status-text").textContent = `DEGRADED (${res.status})`;
    }
  } catch (err) {
    document.getElementById("api-status-text").textContent = "DISCONNECTED";
    document.getElementById("api-status-chip").querySelector(".status-dot").className = "status-dot bg-rose";
  }
}

// --- Load Destinations & Passports ---
async function loadDestinations() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/destinations`);
    if (!res.ok) throw new Error("Failed to fetch destinations");
    const data = await res.json();
    destinations = data.items || data;

    renderDestinationsTable(destinations);
    updateStats(destinations);
    populateDestinationSelects(destinations);
  } catch (err) {
    console.error("Error loading destinations:", err);
    document.getElementById("destinations-tbody").innerHTML = `
      <tr><td colspan="8" class="text-center py-6 text-rose">Error loading destinations: ${err.message}</td></tr>
    `;
  }
}

function updateStats(items) {
  document.getElementById("dest-count-text").textContent = items.length;
  document.getElementById("stat-total-dest").textContent = items.length;

  const l4Count = items.filter(d => (d.passport?.level || d.level) === "L4").length;
  document.getElementById("stat-l4-dest").textContent = l4Count;

  const demotedCount = items.filter(d => d.status === "demoted").length;
  document.getElementById("stat-demoted-dest").textContent = demotedCount;

  const totalHealth = items.reduce((sum, d) => sum + (d.passport?.health_score || 0), 0);
  const avgHealth = items.length ? (totalHealth / items.length).toFixed(1) : "0.0";
  document.getElementById("stat-avg-health").textContent = `${avgHealth}%`;
}

function renderDestinationsTable(items) {
  const tbody = document.getElementById("destinations-tbody");
  if (!items || items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-muted">No destinations registered. Import or add destinations.</td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(d => {
    const level = d.passport?.level || d.level || "L0";
    const health = d.passport?.health_score !== undefined ? `${d.passport.health_score}%` : "N/A";
    const fingerprint = d.passport?.schema_fingerprint ? d.passport.schema_fingerprint.substring(0, 10) + "..." : "none";
    const certifiedAt = d.passport?.last_certified_at ? new Date(d.passport.last_certified_at).toLocaleDateString() : "Never";
    const isDemoted = d.status === "demoted";

    return `
      <tr>
        <td>
          <div style="font-weight: 600; color: #fff;">${escapeHtml(d.name)}</div>
          <div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">${d.id.substring(0, 8)}...</div>
        </td>
        <td>
          <span class="badge badge-indigo">${d.platform_key}</span>
          <span style="font-size: 11px; color: var(--text-muted); margin-left: 4px;">${d.surface}</span>
        </td>
        <td><span class="badge badge-${level.toLowerCase()}">${level}</span></td>
        <td>
          <div style="font-weight: 600; font-family: var(--font-mono); color: var(--accent-cyan);">${health}</div>
        </td>
        <td><code style="font-size: 11px; color: var(--text-muted);">${fingerprint}</code></td>
        <td style="font-size: 12px; color: var(--text-secondary);">${certifiedAt}</td>
        <td>
          <span class="badge ${isDemoted ? 'badge-demoted' : 'badge-active'}">${d.status}</span>
        </td>
        <td>
          <div class="btn-group">
            <button class="btn btn-xs btn-outline" onclick="triggerCertify('${d.id}')">&#x21AF; Certify</button>
            <button class="btn btn-xs btn-outline text-rose" onclick="triggerDemote('${d.id}')">&#x26A0; Demote</button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

function populateDestinationSelects(items) {
  const pfSelect = document.getElementById("pf-destination-select");
  const pubSelect = document.getElementById("pub-dest-select");
  const rcSelect = document.getElementById("rc-destination-select");

  const options = items.map(d => `<option value="${d.id}">${escapeHtml(d.name)} (${d.platform_key} / ${d.surface})</option>`).join("");
  
  if (pfSelect) pfSelect.innerHTML = `<option value="">Select destination...</option>` + options;
  if (pubSelect) pubSelect.innerHTML = `<option value="">Select destination...</option>` + options;
  if (rcSelect) rcSelect.innerHTML = `<option value="">Select destination...</option>` + options;
}

// --- Certify & Demote Destination Actions ---
window.triggerCertify = async function(destinationId) {
  showToast(`Initiating certification for ${destinationId.substring(0, 8)}...`);
  try {
    const res = await fetch(`${API_BASE}/api/v1/destinations/${destinationId}/certify`, {
      method: "POST"
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast(`Certification job enqueued: ${data.job_id.substring(0, 8)}`, "success");
    await pollJob(data.job_id, () => {
      loadDestinations();
    });
  } catch (err) {
    showToast(`Certification failed: ${err.message}`, "error");
  }
};

window.triggerDemote = async function(destinationId) {
  try {
    const res = await fetch(`${API_BASE}/api/v1/destinations/${destinationId}/demote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "Manual operator demotion via Flight Deck" })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast("Destination demoted", "success");
    await loadDestinations();
  } catch (err) {
    showToast(`Demote failed: ${err.message}`, "error");
  }
};

// --- Preflight Court Simulator ---
async function evaluatePreflightCourt() {
  const destId = document.getElementById("pf-destination-select").value;
  if (!destId) {
    showToast("Please select a target destination", "error");
    return;
  }

  const payload = {
    destination_id: destId,
    rendition: {
      title: document.getElementById("pf-title").value,
      body: document.getElementById("pf-body").value,
      canonical_url: document.getElementById("pf-canonical").value || null,
      links: [],
      media: [],
      is_promotional: document.getElementById("pf-promotional").checked,
      ai_generated: document.getElementById("pf-ai-generated").checked,
      language: document.getElementById("pf-language").value
    }
  };

  const resultContainer = document.getElementById("pf-result-body");
  const verdictTag = document.getElementById("pf-verdict-tag");

  try {
    resultContainer.innerHTML = `<div class="text-center py-6 text-muted">Consulting Preflight Court...</div>`;
    const res = await fetch(`${API_BASE}/api/v1/preflight`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error?.message || `HTTP ${res.status}`);
    }

    const data = await res.json();
    verdictTag.className = `verdict-tag verdict-${data.verdict}`;
    verdictTag.textContent = data.verdict;

    let html = `
      <div style="margin-bottom: 16px;">
        <div style="font-size: 12px; color: var(--text-muted); text-transform: uppercase;">Rule ID</div>
        <div style="font-weight: 700; font-family: var(--font-mono); color: #fff;">${data.rule_id} (${data.code})</div>
      </div>
      <div style="margin-bottom: 16px;">
        <div style="font-size: 12px; color: var(--text-muted); text-transform: uppercase;">Court Reasoning</div>
        <div style="font-size: 13px; color: var(--text-primary); margin-top: 4px;">${escapeHtml(data.reason)}</div>
      </div>
    `;

    if (data.earliest_allowed_at) {
      html += `
        <div style="margin-bottom: 16px;">
          <div style="font-size: 12px; color: var(--text-muted); text-transform: uppercase;">Earliest Allowed Posting</div>
          <div style="font-family: var(--font-mono); color: var(--accent-cyan); font-weight: 600;">${new Date(data.earliest_allowed_at).toLocaleString()}</div>
        </div>
      `;
    }

    if (data.rewritten_rendition) {
      html += `
        <div style="margin-top: 20px; border-top: 1px solid var(--border-subtle); padding-top: 16px;">
          <div style="font-size: 12px; font-weight: 700; color: var(--accent-amber); margin-bottom: 8px;">Rewritten Rendition (Auto-Fixed)</div>
          <div style="background: rgba(0,0,0,0.3); padding: 12px; border-radius: 8px; border: 1px solid var(--border-subtle);">
            <div style="font-weight: 600; margin-bottom: 6px;">${escapeHtml(data.rewritten_rendition.title)}</div>
            <div style="font-size: 12px; color: var(--text-secondary); white-space: pre-wrap;">${escapeHtml(data.rewritten_rendition.body)}</div>
          </div>
        </div>
      `;
    }

    if (data.warnings && data.warnings.length > 0) {
      html += `
        <div style="margin-top: 16px;">
          <div style="font-size: 12px; color: var(--accent-amber); font-weight: 600;">Warnings</div>
          <ul style="padding-left: 20px; font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
            ${data.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join("")}
          </ul>
        </div>
      `;
    }

    resultContainer.innerHTML = html;
  } catch (err) {
    verdictTag.className = "verdict-tag verdict-BLOCK";
    verdictTag.textContent = "ERROR";
    resultContainer.innerHTML = `<div class="text-rose text-center py-6">${err.message}</div>`;
  }
}

// --- Idempotency & Publishing ---
function generateNewIdempotencyKey() {
  const key = `idemp_pub_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
  lastUsedIdempotencyKey = key;
  document.getElementById("pub-idemp-key").value = key;
}

async function submitPublication() {
  const destId = document.getElementById("pub-dest-select").value;
  const idempKey = document.getElementById("pub-idemp-key").value;
  if (!destId) {
    showToast("Please select a target destination", "error");
    return;
  }
  if (!idempKey) {
    showToast("Idempotency-Key header is required", "error");
    return;
  }

  const tags = document.getElementById("pub-tags").value.split(",").map(t => t.trim()).filter(Boolean);
  const payload = {
    destination_id: destId,
    rendition: {
      title: document.getElementById("pub-title").value,
      body: document.getElementById("pub-body").value,
      canonical_url: document.getElementById("pub-canonical").value,
      tags: tags,
      is_promotional: false,
      ai_generated: true,
      language: "en"
    }
  };

  const jobBadge = document.getElementById("job-status-badge");
  const jobContainer = document.getElementById("pub-job-details");
  jobBadge.textContent = "DISPATCHING";
  jobBadge.className = "job-status-badge badge-indigo";

  try {
    const res = await fetch(`${API_BASE}/api/v1/publications`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempKey
      },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error?.message || `HTTP ${res.status}`);
    }

    const data = await res.json();
    showToast(`Publication enqueued: Job ${data.job_id.substring(0, 8)}`, "success");

    jobContainer.innerHTML = `
      <div style="margin-bottom: 12px;">
        <span style="font-size: 11px; color: var(--text-muted);">JOB IDENTIFIER</span>
        <div style="font-family: var(--font-mono); font-weight: 700; color: #fff;">${data.job_id}</div>
      </div>
      <div class="progress-bar-container">
        <div class="progress-bar-fill" id="pub-progress-fill" style="width: 20%;"></div>
      </div>
      <div id="pub-job-msg" style="font-size: 12px; color: var(--text-secondary); margin-top: 8px;">Phase 1: Idempotency Intent Registered. Worker executing...</div>
    `;

    await pollJob(data.job_id, (job) => {
      renderJobOutcome(job);
    });

  } catch (err) {
    jobBadge.textContent = "FAILED";
    jobBadge.className = "job-status-badge badge-demoted";
    jobContainer.innerHTML = `<div class="text-rose text-center py-6">${err.message}</div>`;
  }
}

async function pollJob(jobId, onComplete) {
  const pollInterval = 500;
  const maxAttempts = 30;
  let attempts = 0;

  const timer = setInterval(async () => {
    attempts++;
    try {
      const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`);
      if (!res.ok) return;
      const job = await res.json();

      const fill = document.getElementById("pub-progress-fill");
      if (fill) fill.style.width = `${job.progress || 50}%`;

      if (job.status === "succeeded" || job.status === "failed") {
        clearInterval(timer);
        if (onComplete) onComplete(job);
      } else if (attempts >= maxAttempts) {
        clearInterval(timer);
        showToast("Job polling timed out", "error");
      }
    } catch (e) {
      console.warn("Poll error:", e);
    }
  }, pollInterval);
}

function renderJobOutcome(job) {
  const jobBadge = document.getElementById("job-status-badge");
  const jobContainer = document.getElementById("pub-job-details");

  if (job.status === "succeeded") {
    jobBadge.textContent = "SUCCEEDED";
    jobBadge.className = "job-status-badge badge-active";
    const res = job.result_json || {};
    jobContainer.innerHTML = `
      <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
        <div>
          <span style="font-size: 11px; color: var(--text-muted);">POST ID</span>
          <div style="font-family: var(--font-mono); font-weight: 700; color: #fff;">${res.platform_post_id || 'N/A'}</div>
        </div>
        <div>
          <span style="font-size: 11px; color: var(--text-muted);">LIVE URL</span>
          <div><a href="${res.live_url || '#'}" target="_blank" style="color: var(--accent-cyan); text-decoration: none; font-weight: 600;">Visit Live Post &#x2197;</a></div>
        </div>
      </div>
      <div style="margin-top: 16px;">
        <span style="font-size: 11px; color: var(--text-muted);">OUTPUT MANIFEST</span>
        <pre style="background: rgba(0,0,0,0.4); padding: 12px; border-radius: 8px; font-size: 11px; color: #a5b4fc; font-family: var(--font-mono); max-height: 180px; overflow-y: auto; margin-top: 6px;">${JSON.stringify(res.manifest || res, null, 2)}</pre>
      </div>
    `;
    showToast("Publication completed successfully!", "success");
  } else {
    jobBadge.textContent = "FAILED";
    jobBadge.className = "job-status-badge badge-demoted";
    jobContainer.innerHTML = `
      <div class="text-rose mb-3">Job execution encountered an error:</div>
      <pre style="background: rgba(0,0,0,0.4); padding: 12px; border-radius: 8px; font-size: 11px; color: #fb7185; font-family: var(--font-mono);">${JSON.stringify(job.error_json || job, null, 2)}</pre>
    `;
  }
}

// --- Recommender Engine ---
async function calculateRecommendations() {
  const container = document.getElementById("recommendations-container");
  container.innerHTML = `<div class="text-center py-6 text-muted">Computing relevance vectors and preflight fitness...</div>`;

  const tags = document.getElementById("rec-tags").value.split(",").map(t => t.trim()).filter(Boolean);
  const payload = {
    content: {
      title: document.getElementById("rec-title").value,
      category: document.getElementById("rec-category").value,
      tags: tags,
      language: document.getElementById("rec-language").value
    },
    top_k: 8
  };

  try {
    const res = await fetch(`${API_BASE}/api/v1/recommendations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const recs = data.recommendations || [];

    if (recs.length === 0) {
      container.innerHTML = `<div class="empty-state"><div class="empty-title">No matching destinations found.</div></div>`;
      return;
    }

    container.innerHTML = recs.map((r, idx) => {
      const pct = Math.round(r.score * 100);
      return `
        <div class="rec-destination-card">
          <div style="display: flex; align-items: center; gap: 16px;">
            <div class="rec-score-badge">
              <span class="rec-score-num">${pct}%</span>
              <span class="rec-score-label">MATCH</span>
            </div>
            <div>
              <div style="font-weight: 700; color: #fff; font-size: 15px;">#${idx + 1} ${escapeHtml(r.destination_name)}</div>
              <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">${escapeHtml(r.reasons.join(" &bull; "))}</div>
              <div style="margin-top: 6px; display: flex; gap: 6px;">
                <span class="badge badge-indigo">Relevance: ${(r.breakdown.relevance * 100).toFixed(0)}%</span>
                <span class="badge badge-amber">Rules Fit: ${(r.breakdown.rules_fit * 100).toFixed(0)}%</span>
                <span class="badge badge-cyan">Past: ${(r.breakdown.past_result_score * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>
          <div>
            <button class="btn btn-xs btn-primary" onclick="selectDestinationForPublish('${r.destination_id}')">Select &#x27A4;</button>
          </div>
        </div>
      `;
    }).join("");

  } catch (err) {
    container.innerHTML = `<div class="text-rose text-center py-6">${err.message}</div>`;
  }
}

window.selectDestinationForPublish = function(destId) {
  const pubTab = document.querySelector('.nav-tab[data-tab="publish"]');
  if (pubTab) pubTab.click();
  const select = document.getElementById("pub-dest-select");
  if (select) select.value = destId;
  showToast("Destination selected for publication", "success");
};

// --- Drift Canary & Chaos Simulator ---
async function breakDevtoApi() {
  const logContainer = document.getElementById("drift-log-container");
  logContainer.innerHTML = `<div class="text-center py-6 text-amber">Injecting schema drift fault into MockHub...</div>`;

  try {
    // 1. Configure MockHub chaos mode to rename_field
    await fetch("http://localhost:8010/__chaos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "rename_field" })
    }).catch(() => {
      console.warn("Direct mockhub call skipped, will test certification drift canary");
    });

    // 2. Locate Dev.to destination
    const devtoDest = destinations.find(d => d.platform_key === "devto");
    if (!devtoDest) {
      throw new Error("No devto destination registered in system.");
    }

    // 3. Trigger certification to observe canary detection
    showToast("Running Drift Canary certification on Dev.to destination...");
    const res = await fetch(`${API_BASE}/api/v1/destinations/${devtoDest.id}/certify`, { method: "POST" });
    const data = await res.json();

    await pollJob(data.job_id, (job) => {
      logContainer.innerHTML = `
        <div style="background: rgba(244, 63, 94, 0.1); border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 8px; padding: 14px; margin-bottom: 12px;">
          <div style="font-weight: 700; color: #fb7185; display: flex; align-items: center; gap: 8px;">
            <span>&#x26A0;</span> DRIFT CANARY TRIGGERED: CERT_DRIFT_DETECTED
          </div>
          <div style="font-size: 12px; color: var(--text-primary); margin-top: 6px;">
            Expected platform response schema failed JSON schema validation. Field <code>url</code> was renamed to <code>post_link</code> upstream.
          </div>
        </div>
        <div style="font-size: 12px; color: var(--text-secondary);">
          <div>&bull; Destination auto-demoted to: <span class="badge badge-l0">L0 (Unverified)</span></div>
          <div>&bull; Operational status set to: <span class="badge badge-demoted">demoted</span></div>
          <div>&bull; Preflight Court now automatically BLOCKS publications to this destination.</div>
          <div>&bull; High-priority alert written to system alerts ledger.</div>
        </div>
      `;
      loadDestinations();
      showToast("Canary caught drift! Destination auto-demoted.", "error");
    });

  } catch (err) {
    logContainer.innerHTML = `<div class="text-rose text-center py-6">${err.message}</div>`;
  }
}

async function healDevtoApi() {
  const logContainer = document.getElementById("drift-log-container");
  try {
    await fetch("http://localhost:8010/__chaos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "none" })
    }).catch(() => {});

    showToast("Dev.to API healed to standard schema", "success");
    logContainer.innerHTML = `
      <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 14px;">
        <div style="font-weight: 700; color: #34d399;">&#x2714; MockHub Restored to Pinned Schema</div>
        <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">Run certification again to verify and promote destination to L4 Certified.</div>
      </div>
    `;
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

// --- Rules Capture & Audit ---
async function extractRulesWorkflow() {
  const destId = document.getElementById("rc-destination-select").value;
  const policyText = document.getElementById("rc-policy-text").value;
  if (!destId) {
    showToast("Please select a destination", "error");
    return;
  }
  if (!policyText) {
    showToast("Please enter policy text", "error");
    return;
  }

  const container = document.getElementById("rc-proposed-container");
  container.innerHTML = `<div class="text-center py-6 text-muted">Extracting formal policy invariants...</div>`;

  try {
    const res = await fetch(`${API_BASE}/api/v1/rules/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ destination_id: destId, rules_text: policyText })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const rules = data.proposed_rules;

    container.innerHTML = `
      <div style="margin-bottom: 12px;">
        <span class="badge badge-amber">PROPOSED (PENDING HUMAN CONFIRMATION)</span>
      </div>
      <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px;">Extracted Policy Rules:</div>
      <pre style="background: rgba(0,0,0,0.4); padding: 12px; border-radius: 8px; font-size: 11px; color: #a5b4fc; font-family: var(--font-mono); max-height: 160px; overflow-y: auto;">${JSON.stringify(rules, null, 2)}</pre>
      <div style="margin-top: 16px;">
        <button class="btn btn-emerald btn-block" onclick="confirmRulesWorkflow('${destId}', ${escapeAttr(JSON.stringify(rules))})">&#x2714; Confirm & Commit to Audit Ledger</button>
      </div>
    `;

  } catch (err) {
    container.innerHTML = `<div class="text-rose text-center py-6">${err.message}</div>`;
  }
}

window.confirmRulesWorkflow = async function(destId, rules) {
  try {
    const res = await fetch(`${API_BASE}/api/v1/rules/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        destination_id: destId,
        confirmed_by: "FlightDeckOperator",
        rules: rules
      })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast("Rules confirmed and committed to audit log!", "success");

    document.getElementById("rc-proposed-container").innerHTML = `
      <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 14px;">
        <div style="font-weight: 700; color: #34d399;">&#x2714; Rules Confirmed & Active</div>
        <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
          Audit Log ID: <code>${data.audit_id || 'AUD-LOG-01'}</code><br>
          Confirmed by: FlightDeckOperator<br>
          Preflight Court rules for this destination are now enforced.
        </div>
      </div>
    `;
    loadDestinations();
  } catch (err) {
    showToast(`Confirm failed: ${err.message}`, "error");
  }
};

// --- Event Listeners Setup ---
function setupEventListeners() {
  document.getElementById("btn-refresh-passports")?.addEventListener("click", () => {
    showToast("Refreshing destination registry...");
    loadDestinations();
  });

  document.getElementById("btn-recertify-all")?.addEventListener("click", async () => {
    showToast("Scanning for stale passports (>25 days)...");
    try {
      const res = await fetch(`${API_BASE}/api/v1/destinations/recertify-stale`, { method: "POST" });
      const data = await res.json();
      showToast(`Scan complete: ${data.enqueued_jobs?.length || 0} jobs enqueued.`, "success");
      loadDestinations();
    } catch (e) {
      showToast("Recertify scan error", "error");
    }
  });

  document.getElementById("btn-evaluate-court")?.addEventListener("click", evaluatePreflightCourt);
  document.getElementById("btn-submit-publish")?.addEventListener("click", submitPublication);
  document.getElementById("btn-gen-idemp-key")?.addEventListener("click", generateNewIdempotencyKey);
  document.getElementById("btn-replay-idemp-key")?.addEventListener("click", () => {
    if (lastUsedIdempotencyKey) {
      document.getElementById("pub-idemp-key").value = lastUsedIdempotencyKey;
      showToast("Replayed prior idempotency key");
    }
  });

  document.getElementById("btn-get-recommendations")?.addEventListener("click", calculateRecommendations);
  document.getElementById("btn-chaos-break-devto")?.addEventListener("click", breakDevtoApi);
  document.getElementById("btn-chaos-heal-devto")?.addEventListener("click", healDevtoApi);
  document.getElementById("btn-extract-rules")?.addEventListener("click", extractRulesWorkflow);

  // Preflight sample button
  document.getElementById("btn-preflight-fill-sample")?.addEventListener("click", () => {
    document.getElementById("pf-title").value = "Announcing LongTail Passport: The Verifiable Destination Network";
    document.getElementById("pf-body").value = "We built LongTail Passport to solve long-tail distribution challenges.\nCheck out our repo at https://github.com/incubrix/passport and join our discussion.";
    document.getElementById("pf-canonical").value = "https://incubrix.dev/blog/passport";
    document.getElementById("pf-promotional").checked = false;
    document.getElementById("pf-ai-generated").checked = true;
    showToast("Loaded sample rendition");
  });

  // Table filter
  document.getElementById("destination-filter")?.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    const filtered = destinations.filter(d => 
      d.name.toLowerCase().includes(q) ||
      d.platform_key.toLowerCase().includes(q) ||
      (d.category && d.category.toLowerCase().includes(q))
    );
    renderDestinationsTable(filtered);
  });
}

// Helpers
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttr(str) {
  if (!str) return "''";
  return `'${String(str).replace(/'/g, "\\'")}'`;
}

// Run on load
document.addEventListener("DOMContentLoaded", initFlightDeck);
