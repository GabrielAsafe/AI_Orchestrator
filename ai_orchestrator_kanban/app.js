const STORAGE_KEY = "ai-orchestrator-kanban-v1";
const state = { data: null, selectedTaskId: null };

const el = (id) => document.getElementById(id);
const board = el("board");
const cardTemplate = el("cardTemplate");
const dialog = el("taskDialog");

async function loadInitialData(forceRemote = false) {
  if (!forceRemote) {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try { return JSON.parse(saved); } catch (_) { /* fall through */ }
    }
  }
  const response = await fetch("tasks.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`Não foi possível carregar tasks.json (${response.status}).`);
  return await response.json();
}

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.data));
}

function taskMap() {
  return new Map(state.data.tasks.map(t => [t.id, t]));
}

function dependencyInfo(task) {
  const map = taskMap();
  const dependencies = task.depends_on || [];
  const open = dependencies.filter(id => map.get(id)?.status !== "done");
  return { total: dependencies.length, open };
}

function isEligible(task) {
  return task.status === "backlog" && dependencyInfo(task).open.length === 0;
}

function filteredTasks() {
  const q = el("searchInput").value.trim().toLowerCase();
  const milestone = el("milestoneFilter").value;
  const area = el("areaFilter").value;
  const priority = el("priorityFilter").value;
  const hideDone = el("hideDone").checked;

  return state.data.tasks.filter(task => {
    if (hideDone && task.status === "done") return false;
    if (milestone && task.milestone !== milestone) return false;
    if (area && task.area !== area) return false;
    if (priority && task.priority !== priority) return false;
    if (!q) return true;
    const haystack = [
      task.id, task.title, task.description, task.area, task.milestone,
      task.kind, task.priority, ...(task.tags || [])
    ].join(" ").toLowerCase();
    return haystack.includes(q);
  });
}

function moveTask(taskId, status) {
  const task = state.data.tasks.find(t => t.id === taskId);
  if (!task || !state.data.columns.some(c => c.id === status)) return;
  task.status = status;
  persist();
  render();
}

function moveRelative(taskId, delta) {
  const task = state.data.tasks.find(t => t.id === taskId);
  const columns = state.data.columns;
  const index = columns.findIndex(c => c.id === task.status);
  const next = Math.min(columns.length - 1, Math.max(0, index + delta));
  moveTask(taskId, columns[next].id);
}

function cardFor(task) {
  const node = cardTemplate.content.firstElementChild.cloneNode(true);
  node.dataset.taskId = task.id;
  node.querySelector(".task-id").textContent = task.id;
  node.querySelector(".priority").textContent = task.priority;
  node.querySelector(".priority").dataset.priority = task.priority;
  node.querySelector(".card-title").textContent = task.title;
  node.querySelector(".card-desc").textContent = task.description;

  const chips = node.querySelector(".chips");
  [task.milestone, task.area, task.kind].forEach(value => {
    const span = document.createElement("span");
    span.className = "chip";
    span.textContent = value;
    chips.appendChild(span);
  });

  const dep = dependencyInfo(task);
  const depLine = node.querySelector(".dependency-line");
  if (!dep.total) {
    depLine.textContent = "Sem dependências";
    depLine.classList.add("ready");
  } else if (dep.open.length === 0) {
    depLine.textContent = `✓ ${dep.total} dependência(s) concluída(s)`;
    depLine.classList.add("ready");
  } else {
    depLine.textContent = `${dep.open.length}/${dep.total} dependência(s) aberta(s)`;
    depLine.classList.add("blocked");
  }

  node.querySelector(".details-btn").addEventListener("click", () => openDetails(task.id));
  node.querySelector(".prev-btn").addEventListener("click", () => moveRelative(task.id, -1));
  node.querySelector(".next-btn").addEventListener("click", () => moveRelative(task.id, 1));

  const idx = state.data.columns.findIndex(c => c.id === task.status);
  node.querySelector(".prev-btn").disabled = idx <= 0;
  node.querySelector(".next-btn").disabled = idx >= state.data.columns.length - 1;

  node.addEventListener("dragstart", ev => {
    node.classList.add("dragging");
    ev.dataTransfer.setData("text/plain", task.id);
    ev.dataTransfer.effectAllowed = "move";
  });
  node.addEventListener("dragend", () => node.classList.remove("dragging"));
  return node;
}

function render() {
  if (!state.data) return;
  board.innerHTML = "";
  const visible = filteredTasks();

  state.data.columns.forEach(column => {
    const section = document.createElement("section");
    section.className = "column";
    section.dataset.status = column.id;

    const head = document.createElement("div");
    head.className = "column-head";
    const title = document.createElement("h2");
    title.textContent = column.title;
    const count = document.createElement("span");
    count.className = "count";
    count.textContent = visible.filter(t => t.status === column.id).length;
    head.append(title, count);

    const body = document.createElement("div");
    body.className = "column-body";
    const items = visible.filter(t => t.status === column.id);
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = column.description || "Sem tarefas";
      body.appendChild(empty);
    } else {
      items.forEach(task => body.appendChild(cardFor(task)));
    }

    for (const target of [section, body]) {
      target.addEventListener("dragover", ev => { ev.preventDefault(); section.classList.add("drag-over"); });
      target.addEventListener("dragleave", ev => {
        if (!section.contains(ev.relatedTarget)) section.classList.remove("drag-over");
      });
      target.addEventListener("drop", ev => {
        ev.preventDefault();
        section.classList.remove("drag-over");
        const taskId = ev.dataTransfer.getData("text/plain");
        moveTask(taskId, column.id);
      });
    }

    section.append(head, body);
    board.appendChild(section);
  });

  const done = state.data.tasks.filter(t => t.status === "done").length;
  const active = state.data.tasks.filter(t => ["developing","testing"].includes(t.status)).length;
  const ready = state.data.tasks.filter(isEligible).length;
  el("summary").textContent = `${state.data.tasks.length} tarefas · ${done} done · ${active} em curso · ${ready} backlog elegíveis`;
}

function fillFilters() {
  el("milestoneFilter").innerHTML = '<option value="">Todos os milestones</option>';
  for (const m of state.data.milestones || []) {
    const option = document.createElement("option");
    option.value = m.id;
    option.textContent = `${m.id} — ${m.title}`;
    el("milestoneFilter").appendChild(option);
  }
  const areas = [...new Set(state.data.tasks.map(t => t.area))].sort();
  el("areaFilter").innerHTML = '<option value="">Todas as áreas</option>';
  for (const area of areas) {
    const option = document.createElement("option");
    option.value = area;
    option.textContent = area;
    el("areaFilter").appendChild(option);
  }

  el("detailStatus").innerHTML = "";
  for (const column of state.data.columns) {
    const option = document.createElement("option");
    option.value = column.id;
    option.textContent = column.title;
    el("detailStatus").appendChild(option);
  }
}

function addListItems(container, values, classResolver = null) {
  container.innerHTML = "";
  if (!values?.length) {
    const li = document.createElement("li");
    li.textContent = "—";
    container.appendChild(li);
    return;
  }
  values.forEach(value => {
    const li = document.createElement("li");
    if (typeof value === "object") {
      li.textContent = value.text ?? JSON.stringify(value);
    } else {
      li.textContent = value;
    }
    if (classResolver) li.className = classResolver(value);
    container.appendChild(li);
  });
}

function openDetails(taskId) {
  const task = state.data.tasks.find(t => t.id === taskId);
  if (!task) return;
  state.selectedTaskId = taskId;
  el("detailMeta").textContent = `${task.id} · ${task.milestone} · ${task.area} · ${task.kind} · ${task.priority}`;
  el("detailTitle").textContent = task.title;
  el("detailDescription").textContent = task.description;
  addListItems(el("detailAcceptance"), task.acceptance_criteria);
  addListItems(el("detailTests"), task.test_plan);
  const map = taskMap();
  addListItems(el("detailDeps"), task.depends_on, depId => map.get(depId)?.status === "done" ? "dep-done" : "dep-open");
  addListItems(el("detailDeliverables"), task.deliverables);
  el("detailStatus").value = task.status;
  el("detailNotes").value = task.notes || "";
  dialog.showModal();
}

function saveDetails() {
  const task = state.data.tasks.find(t => t.id === state.selectedTaskId);
  if (!task) return;
  task.status = el("detailStatus").value;
  task.notes = el("detailNotes").value;
  persist();
  dialog.close();
  render();
}

function promoteEligible() {
  let changed = 0;
  // Repeat because promoting does not complete dependencies; this only moves currently unblocked backlog.
  state.data.tasks.forEach(task => {
    if (isEligible(task)) { task.status = "ready"; changed++; }
  });
  persist();
  render();
  if (!changed) alert("Nenhuma tarefa de Backlog tem todas as dependências em Done neste momento.");
}

function exportJson() {
  const blob = new Blob([JSON.stringify(state.data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  a.href = url;
  a.download = `tasks-kanban-${stamp}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

async function importJson(file) {
  const text = await file.text();
  const data = JSON.parse(text);
  if (!data || !Array.isArray(data.tasks) || !Array.isArray(data.columns)) {
    throw new Error("JSON não contém columns/tasks válidos.");
  }
  const validStatus = new Set(data.columns.map(c => c.id));
  for (const task of data.tasks) {
    if (!task.id || !validStatus.has(task.status)) {
      throw new Error(`Task inválida: ${task.id || "(sem id)"}`);
    }
  }
  state.data = data;
  persist();
  fillFilters();
  render();
}

async function resetFromFile() {
  if (!confirm("Apagar o estado guardado no browser e recarregar tasks.json?")) return;
  localStorage.removeItem(STORAGE_KEY);
  state.data = await loadInitialData(true);
  persist();
  fillFilters();
  render();
}

function bindUI() {
  ["searchInput","milestoneFilter","areaFilter","priorityFilter","hideDone"].forEach(id => {
    el(id).addEventListener(id === "searchInput" ? "input" : "change", render);
  });
  el("saveDetailBtn").addEventListener("click", saveDetails);
  el("promoteReadyBtn").addEventListener("click", promoteEligible);
  el("exportBtn").addEventListener("click", exportJson);
  el("importBtn").addEventListener("click", () => el("importFile").click());
  el("importFile").addEventListener("change", async ev => {
    const file = ev.target.files?.[0];
    if (!file) return;
    try { await importJson(file); } catch (err) { alert(`Falha ao importar: ${err.message}`); }
    ev.target.value = "";
  });
  el("resetBtn").addEventListener("click", () => resetFromFile().catch(showFatalError));
}

function showFatalError(err) {
  board.innerHTML = `<div class="error-banner">
    <strong>Falha ao carregar o board.</strong><br>
    ${String(err.message || err)}<br><br>
    Abra a aplicação através de um servidor HTTP (ex.: <code>./serve.sh</code>) ou use “Importar JSON”.
  </div>`;
}

(async function init() {
  bindUI();
  try {
    state.data = await loadInitialData();
    el("projectSubtitle").textContent = state.data.project?.name || "Plano de implementação";
    fillFilters();
    render();
  } catch (err) {
    showFatalError(err);
  }
})();
