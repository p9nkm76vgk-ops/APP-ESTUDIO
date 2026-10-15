// Sistema de Estudio — interfaz (sin dependencias)
const $ = (id) => document.getElementById(id);
const STEPS = ["recibido", "extrayendo", "clasificando", "generando", "calidad", "exportando", "guardado"];
const STEP_LABEL = { recibido: "Recibido", extrayendo: "Leyendo", clasificando: "Clasificando", generando: "Generando",
  calidad: "Control de calidad", exportando: "Exportando", guardado: "Guardado" };
const ST_LABEL = { ok: "Correcto", aviso: "Revisar", no_verificable: "Revisión manual" };

let state = { subjects: [], types: {}, filter: "", file: null, doc: null, lastUpload: null };

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  let data = {};
  try { data = await res.json(); } catch (_) { /* sin cuerpo */ }
  if (!res.ok) throw new Error(data.error || `Error ${res.status}`);
  return data;
}
const post = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const subj = (id) => state.subjects.find((s) => s.id === id) || { name: id, primary: "#999" };

function toast(msg, error = false) {
  const t = $("docToast");
  t.textContent = msg; t.classList.toggle("error", error); t.classList.remove("hidden");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add("hidden"), 6000);
}

// ---------------------------------------------------------------- arranque
async function init() {
  const st = await api("/api/status");
  const chip = $("modeChip");
  chip.textContent = st.usa_ia ? `IA: ${st.modelo}` : "Modo sin IA (borrador)";
  chip.classList.toggle("warn", !st.usa_ia);
  chip.title = st.usa_ia ? "Se envía el texto del documento a la API de Anthropic." :
    "Sin clave de API: se genera un borrador extractivo. Ver README para activar la IA.";
  await loadSubjects();
  await loadDocs();
}

async function loadSubjects() {
  const data = await api("/api/subjects");
  state.subjects = data.subjects; state.types = data.output_types;
  $("subjectNav").innerHTML = state.subjects.map((s) =>
    `<button class="nav-item" data-subject="${s.id}"><span class="dot" style="background:${s.primary}"></span>${esc(s.name)}<span class="count">${s.count || ""}</span></button>`).join("");
  $("countAll").textContent = state.subjects.reduce((a, s) => a + s.count, 0) || "";
  const opts = state.subjects.map((s) => `<option value="${s.id}">${esc(s.name)}</option>`).join("");
  $("subjectSelect").innerHTML = `<option value="">Detectar automáticamente</option>${opts}`;
  $("moveSelect").innerHTML = opts;
  $("kindSelect").innerHTML = Object.entries(state.types).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  document.querySelectorAll(".nav-item[data-subject]").forEach((b) => b.onclick = () => selectSubject(b.dataset.subject, b));
}

function selectSubject(id, btn) {
  state.filter = id;
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  $("historyCard").classList.add("hidden"); $("listCard").classList.remove("hidden");
  $("listTitle").textContent = id ? subj(id).name : "Documentos";
  if (id) $("subjectSelect").value = id;
  $("sidebar").classList.remove("open");
  loadDocs();
}

async function loadDocs() {
  const q = state.filter ? `?subject=${state.filter}` : "";
  const { documents } = await api(`/api/documents${q}`);
  $("docList").innerHTML = documents.length ? documents.map((d) => {
    const s = subj(d.subject);
    const badge = d.status === "definitivo" ? `<span class="badge definitivo">Definitivo</span>` :
      `<span class="badge ${d.quality_summary}">${d.quality_summary === "ok" ? "Borrador · calidad OK" : "Borrador · revisar"}</span>`;
    return `<button class="doc-item" data-id="${d.id}"><span class="bar" style="background:${s.primary}"></span>
      <span><span class="title">${esc(d.topic)}</span><br><span class="sub">${esc(s.name)} · ${esc(d.kind_label || d.kind)} · v${d.version} · ${new Date(d.updated).toLocaleDateString("es-ES")}</span></span>${badge}</button>`;
  }).join("") : `<p class="muted">Todavía no hay documentos${state.filter ? " en esta asignatura" : ""}.</p>`;
  document.querySelectorAll(".doc-item").forEach((b) => b.onclick = () => openDoc(b.dataset.id));
}

// ---------------------------------------------------------------- subida
const drop = $("drop");
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); });
$("fileInput").onchange = (e) => e.target.files[0] && setFile(e.target.files[0]);
function setFile(f) { state.file = f; $("fileName").textContent = f.name; $("processBtn").disabled = false; }

$("processBtn").onclick = () => upload(false);

async function upload(force) {
  if (!state.file) return;
  const fd = new FormData();
  fd.append("file", state.file);
  fd.append("subject", $("subjectSelect").value);
  fd.append("kind", $("kindSelect").value);
  fd.append("extra", $("extra").value);
  if (force) fd.append("force", "1");
  $("processBtn").disabled = true;
  showJob({ step: "recibido", status: "en_curso", message: "", warnings: [] });
  try {
    const job = await api("/api/process", { method: "POST", body: fd });
    poll(job.id);
  } catch (e) {
    showJob({ step: "recibido", status: "error", message: e.message, warnings: [] });
    $("processBtn").disabled = false;
  }
}

async function poll(id) {
  try {
    const job = await api(`/api/jobs/${id}`);
    showJob(job);
    if (job.status === "en_curso") return setTimeout(() => poll(id), 1200);
    $("processBtn").disabled = !state.file;
    if (job.status === "completado") { await loadSubjects(); await loadDocs(); openDoc(job.document_id); }
  } catch (e) {
    showJob({ step: "recibido", status: "error", message: `Se ha perdido la conexión con la app: ${e.message}`, warnings: [] });
  }
}

function showJob(job) {
  $("jobCard").classList.remove("hidden");
  const titles = { en_curso: "Procesando…", completado: "Listo", error: "No se ha podido completar",
    necesita_confirmacion: "Confirma la asignatura", duplicado: "Ya existe" };
  $("jobTitle").textContent = titles[job.status] || "Procesando";
  const idx = STEPS.indexOf(job.step);
  $("steps").innerHTML = STEPS.map((s, i) => `<li class="${i < idx || job.status === "completado" ? "done" : i === idx ? "now" : ""}">${STEP_LABEL[s]}</li>`).join("");
  $("jobMsg").textContent = job.message || "";
  $("jobWarnings").innerHTML = (job.warnings || []).map((w) => `<li>${esc(w)}</li>`).join("");
  const a = $("jobActions"); a.innerHTML = "";
  if (job.status === "error") {
    a.innerHTML = `<button class="btn" id="retryBtn">Reintentar</button>`;
    $("retryBtn").onclick = () => upload(false);
  } else if (job.status === "duplicado") {
    a.innerHTML = `<button class="btn primary" id="openDup">Abrir el existente</button><button class="btn" id="forceBtn">Generar una versión nueva</button>`;
    $("openDup").onclick = () => openDoc(job.document_id);
    $("forceBtn").onclick = () => upload(true);
  } else if (job.status === "necesita_confirmacion") {
    const c = job.classification || {};
    const scores = Object.entries(c.puntuaciones || {}).map(([k, v]) => `${esc(subj(k).name)}: ${v}`).join(" · ");
    a.innerHTML = `<div style="width:100%"><p class="muted">Propuesta: <strong>${esc(c.asignatura ? subj(c.asignatura).name : "ninguna")}</strong> (confianza ${c.confianza}). ${scores}</p>
      <div class="row"><label>Asignatura<select id="confirmSubject">${state.subjects.map((s) => `<option value="${s.id}" ${s.id === c.asignatura ? "selected" : ""}>${esc(s.name)}</option>`).join("")}</select></label>
      <label>Tema<input id="confirmTopic" value="${esc(c.tema || "")}"></label></div>
      <button class="primary" id="confirmBtn">Confirmar y generar</button></div>`;
    $("confirmBtn").onclick = async () => {
      try {
        await post(`/api/jobs/${job.id}/confirm`, { subject: $("confirmSubject").value, topic: $("confirmTopic").value });
        poll(job.id);
      } catch (e) { $("jobMsg").textContent = e.message; }
    };
  }
}

// ---------------------------------------------------------------- documento
async function openDoc(id) {
  const d = await api(`/api/documents/${id}`);
  state.doc = d;
  const m = d.meta, s = subj(m.subject);
  $("docCard").classList.remove("hidden");
  $("docSubject").textContent = s.name; $("docSubject").style.color = s.primary;
  $("docTitle").textContent = m.topic;
  $("docMeta").textContent = `${m.kind_label || m.kind} · versión ${m.version} · ${m.status} · ${m.provider === "offline" ? "sin IA" : m.model} · fuente: ${m.source_filename}`;
  $("pdfBtn").href = `/api/documents/${id}/file.pdf`;
  $("pdfView").href = `/api/documents/${id}/file.pdf?inline=1`;
  $("previewFrame").src = `/api/documents/${id}/file.html?t=${Date.now()}`;
  $("editor").value = d.markdown;
  $("sectionSelect").innerHTML = d.sections.map((h) => `<option>${esc(h)}</option>`).join("");
  $("moveSelect").value = m.subject;
  $("qualityList").innerHTML = (m.quality || []).map((c) =>
    `<div class="check-item"><span class="st-${c.status}">${ST_LABEL[c.status] || c.status}</span><span><strong>${esc(c.name)}</strong><br>${esc(c.detail)}</span></div>`).join("");
  $("verifyResult").innerHTML = "";
  $("gnName").textContent = d.goodnotes.nombre;
  $("gnSteps").innerHTML = d.goodnotes.pasos.map((p) => `<li>${esc(p)}</li>`).join("");
  $("approveBtn").disabled = m.status === "definitivo";
  showTab("preview");
  $("docCard").scrollIntoView({ behavior: "smooth" });
}

function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("hidden", p.id !== `tab-${name}`));
}
document.querySelectorAll(".tab").forEach((t) => t.onclick = () => showTab(t.dataset.tab));
$("closeDoc").onclick = () => $("docCard").classList.add("hidden");

async function act(fn, okMsg) {
  try { const r = await fn(); if (okMsg) toast(okMsg); return r; }
  catch (e) { toast(e.message, true); }
}

$("saveEdit").onclick = () => act(async () => {
  await api(`/api/documents/${state.doc.meta.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ markdown: $("editor").value }) });
  await openDoc(state.doc.meta.id); await loadDocs();
}, "Guardado como nueva versión. El PDF se ha regenerado.");

$("approveBtn").onclick = () => act(async () => { await post(`/api/documents/${state.doc.meta.id}/approve`); await openDoc(state.doc.meta.id); await loadDocs(); }, "Marcado como definitivo.");

$("verifyBtn").onclick = () => act(async () => {
  const v = await post(`/api/documents/${state.doc.meta.id}/verify`);
  const row = (k, label) => `<div class="check-item"><span class="${v[k] ? "st-ok" : "st-aviso"}">${v[k] ? "Sí" : "No"}</span><span>${label}</span></div>`;
  $("verifyResult").innerHTML = `<h3>Comprobación del guardado</h3>${row("markdown_existe", "Documento guardado")}${row("markdown_intacto", "Contenido sin cambios desde el último guardado")}${row("metadatos_existen", "Metadatos guardados")}${row("pdf_existe", "PDF exportado")}${row("original_existe", "Archivo original guardado")}<p class="muted">Carpeta: ${esc(v.carpeta)}</p>`;
  showTab("quality");
  return v;
}, null);

$("regenBtn").onclick = () => act(async () => {
  $("regenBtn").disabled = true; toast("Regenerando la sección…");
  try { await post(`/api/documents/${state.doc.meta.id}/regenerate`, { heading: $("sectionSelect").value, instruction: $("sectionInstr").value }); }
  finally { $("regenBtn").disabled = false; }
  await openDoc(state.doc.meta.id);
}, "Sección regenerada (nueva versión).");

$("moveBtn").onclick = () => act(async () => {
  await post(`/api/documents/${state.doc.meta.id}/reclassify`, { subject: $("moveSelect").value });
  await loadSubjects(); await loadDocs(); await openDoc(state.doc.meta.id);
}, "Documento movido a la nueva asignatura.");

$("correctionBtn").onclick = () => act(async () => {
  await post(`/api/documents/${state.doc.meta.id}/correction`, { text: $("correctionText").value, apply_future: $("correctionFuture").checked });
  $("correctionText").value = "";
}, "Corrección guardada.");

$("deleteBtn").onclick = () => {
  if (!confirm("¿Borrar este documento, sus versiones y sus exportaciones? El archivo original se conserva.")) return;
  act(async () => {
    await api(`/api/documents/${state.doc.meta.id}`, { method: "DELETE" });
    $("docCard").classList.add("hidden"); await loadSubjects(); await loadDocs();
  }, null);
};

$("historyBtn").onclick = async () => {
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
  $("historyBtn").classList.add("active"); $("sidebar").classList.remove("open");
  const { history } = await api("/api/history");
  $("listCard").classList.add("hidden"); $("historyCard").classList.remove("hidden");
  $("historyList").innerHTML = history.length ? history.map((h) => {
    const { fecha, evento, ...rest } = h;
    const info = Object.entries(rest).filter(([k]) => k !== "detalle").map(([k, v]) => `${k}: ${esc(typeof v === "string" ? v : JSON.stringify(v))}`).join(" · ");
    return `<div class="hist"><strong>${esc(evento)}</strong> · <span class="muted">${new Date(fecha).toLocaleString("es-ES")}</span><br>${info}</div>`;
  }).join("") : `<p class="muted">Sin actividad todavía.</p>`;
};

$("menuBtn").onclick = () => $("sidebar").classList.toggle("open");

init().catch((e) => { $("modeChip").textContent = "Error al conectar"; console.error(e); });
