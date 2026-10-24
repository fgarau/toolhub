const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const EXAMPLES = [
  { label: "Offline collaboration", brief: "Collaborative note-taking app that must work offline and sync edits when users reconnect", constraints: { category: "realtime" } },
  { label: "Python background jobs", brief: "Run scheduled background jobs and retries for a Python web app sending emails and reports", constraints: { category: "queue", languages: ["Python"] } },
  { label: "B2B login", brief: "Login for a B2B SaaS with organisations, SSO for enterprise customers and MFA", constraints: { category: "auth" } },
  { label: "RAG search", brief: "Semantic search over product documentation with embeddings and retrieval-augmented answers", constraints: { category: "database" } },
];
let options = null;
let last = null;

function chip(name, value, checked) {
  return `<label><input type="checkbox" name="${name}" value="${esc(value)}" ${checked ? "checked" : ""}>${esc(value)}</label>`;
}

function renderCapabilities(selected = []) {
  const cat = $("category").value;
  const caps = cat ? options.capabilities[cat] : [...new Set(Object.values(options.capabilities).flat())].sort();
  $("capabilities").innerHTML = caps.map((c) => chip("capabilities", c, selected.includes(c))).join("");
}

function readConstraints() {
  const checked = (name) => [...document.querySelectorAll(`input[name=${name}]:checked`)].map((i) => i.value);
  return {
    category: $("category").value || null,
    languages: checked("languages"),
    hosting: document.querySelector("input[name=hosting]:checked").value,
    open_source_only: $("open_source_only").checked,
    max_ops: $("max_ops").value || null,
    capabilities: checked("capabilities"),
  };
}

function applyConstraints(c) {
  $("category").value = c.category || "";
  document.querySelectorAll("input[name=languages]").forEach((i) => (i.checked = (c.languages || []).includes(i.value)));
  document.querySelector(`input[name=hosting][value="${c.hosting || "any"}"]`).checked = true;
  $("open_source_only").checked = !!c.open_source_only;
  $("max_ops").value = c.max_ops || "";
  renderCapabilities(c.capabilities || []);
}

async function init() {
  const res = await fetch("/api/options");
  if (!res.ok) {
    setStatus((await res.json()).detail || "Could not load options", true);
    return;
  }
  options = await res.json();
  $("category").innerHTML += options.categories.map((c) => `<option>${esc(c)}</option>`).join("");
  $("max_ops").innerHTML += options.ops_levels.map((o) => `<option>${esc(o)}</option>`).join("");
  $("hosting").innerHTML = options.hosting.map((h, i) => `<label><input type="radio" name="hosting" value="${h}" ${i === 0 ? "checked" : ""}> ${h}</label>`).join("");
  $("languages").innerHTML = options.languages.map((l) => chip("languages", l, false)).join("");
  renderCapabilities();
  $("examples").innerHTML = "Try: " + EXAMPLES.map((e, i) => `<button type="button" data-i="${i}">${esc(e.label)}</button>`).join("");
  $("footer").textContent = `${options.tool_count} curated tools in MongoDB Atlas · embeddings: ${options.embeddings === "auto" ? "Atlas Automated Embedding (Voyage AI)" : "local hash fallback"}`;
}

function setStatus(text, error = false) {
  $("status").textContent = text;
  $("status").className = error ? "error" : "";
}

function renderResult(r) {
  const t = r.tool;
  const ranks = Object.entries(r.pipeline_ranks).map(([k, v]) => `<span class="tag plain">${esc(k)} #${v}</span>`).join("");
  return `<article class="card">
    <h3><span class="rank">#${r.rank}</span>${esc(t.name)}</h3>
    <div class="meta">${esc(t.category)} · ${esc(t.licence)} · ${esc(t.deployment.join(", "))} · ops: ${esc(t.ops_overhead)}</div>
    <div class="score"><span class="bar"><span style="width:${r.fit_score}%"></span></span>fit ${r.fit_score} ${ranks}</div>
    <div>${r.matched_constraints.map((m) => `<span class="tag">✓ ${esc(m)}</span>`).join("")}
         ${r.brief_evidence.map((m) => `<span class="tag plain">${esc(m)}</span>`).join("")}</div>
    <p>${esc(r.rationale)}</p>
    <strong>Trade-offs</strong><ul>${t.tradeoffs.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    <p class="caveat">Avoid if ${esc(t.avoid_if)}</p>
    <div class="meta">Evidence: ${t.sources.map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a>`).join(" · ")} · reviewed ${esc(t.last_reviewed_at)}</div>
  </article>`;
}

function renderChanges(changes) {
  if (!changes) return ($("changes").hidden = true);
  const items = changes.items.length
    ? changes.items.map((i) => {
        const pos = i.change === "new" ? `→ #${i.after}` : i.after ? `#${i.before} → #${i.after}` : `#${i.before} → out`;
        return `<li class="change-${i.change}"><strong>${esc(i.name)}</strong> ${pos}: ${esc(i.reason)}</li>`;
      }).join("")
    : "<li>The ranking did not change.</li>";
  $("changes").innerHTML = `<h2>What changed</h2>
    <p>${changes.constraint_changes.length ? changes.constraint_changes.map(esc).join("; ") : "Same constraints"}</p><ul>${items}</ul>`;
  $("changes").hidden = false;
}

function renderExcluded(excluded) {
  if (!excluded.length) return ($("excluded").hidden = true);
  $("excluded").innerHTML = `<h2>Strong candidates excluded by your constraints</h2><ul>${excluded
    .map((e) => `<li><strong>${esc(e.tool.name)}</strong> (would rank #${e.rank_without_constraints}) ${e.reasons.map((r) => `<span class="tag bad">${esc(r)}</span>`).join("")}</li>`)
    .join("")}</ul>`;
  $("excluded").hidden = false;
}

async function submit(event) {
  event.preventDefault();
  const brief = $("brief").value.trim();
  const constraints = readConstraints();
  const sameBrief = last && last.brief === brief;
  const body = { brief, constraints, previous: sameBrief ? { constraints: last.constraints, ranking: last.ranking } : null };
  setStatus("Searching…");
  $("submit").disabled = true;
  try {
    const res = await fetch("/api/recommend", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await res.json();
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
    last = { brief, constraints: data.constraints, ranking: data.results.map((r) => r.tool.slug) };
    renderChanges(data.changes);
    $("results").innerHTML = data.results.length ? data.results.map(renderResult).join("") : `<article class="card">No tool satisfies every constraint. Try relaxing one.</article>`;
    renderExcluded(data.excluded);
    $("pipeline").textContent = JSON.stringify(data.retrieval.pipeline, null, 2);
    $("query").hidden = false;
    setStatus(`${data.results.length} results · change a constraint and press Recommend to see what moves`);
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    $("submit").disabled = false;
  }
}

$("form").addEventListener("submit", submit);
$("category").addEventListener("change", () => renderCapabilities(readConstraints().capabilities));
$("examples").addEventListener("click", (e) => {
  const ex = EXAMPLES[e.target.dataset.i];
  if (!ex) return;
  $("brief").value = ex.brief;
  applyConstraints(ex.constraints);
});
$("reset").addEventListener("click", () => {
  last = null;
  $("brief").value = "";
  applyConstraints({});
  ["changes", "excluded", "query"].forEach((id) => ($(id).hidden = true));
  $("results").innerHTML = "";
  setStatus("");
});
init();
