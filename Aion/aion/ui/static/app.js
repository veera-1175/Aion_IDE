/**
 * AION — Cursor / VS Code workbench replica
 */
const LS_WORKSPACE = "AION_workspace";
const LS_RECENT_PROJECTS = "AION_recent_projects";
const LS_IDE_VERSION = "AION_ide_v33";
const LS_EXEC_ARCHIVE = "AION_exec_archive";
const LS_SETTINGS = "af_settings";
const LS_AGENT_MODE = "AION_agent_mode";
const LS_TASK_MODE = "AION_task_mode";
const LS_PENDING_WORKSPACE = "aion_pending_workspace";

const state = {
  workspaceRoot: "",
  projectName: "",
  projectPath: "",
  allFiles: [],
  openTabs: [],
  activeTab: null,
  tabContents: {},
  dirty: new Set(),
  monacoReady: false,
  useFallback: false,
  editor: null,
  diffEditor: null,
  models: {},
  running: false,
  abortController: null,
  lastFileChanges: [],
  fileCount: 0,
  attached: [],
  bottomPanelOpen: false,
  paletteOpen: false,
  _monacoProvidersReady: false,
  contextPath: null,
  activePanel: "output",
  runJobId: null,
  runPollTimer: null,
  problemCount: 0,
  treeScope: "full",
  createBasePath: "",
  inlineCreate: null,
  runningMetaTimer: null,
  terminalPollTimer: null,
  userMessages: [],
  editingMessageId: null,
  agentRunMode: "agent",
  taskMode: "auto",
  mentionIndex: 0,
  mentionItems: [],
  fileNavHistory: [],
  fileNavIndex: -1,
  skipNavPush: false,
  sidebarCollapsed: false,
  auxCollapsed: false,
  execSessions: [],
  activeExecId: null,
  auxView: "chat",
  historySearch: "",
  agentsSidebarSearch: "",
  agentsSidebarFilter: "all",
  agentsWorkspaceMenuOpen: false,
  agentsWorkspaceSearch: "",
  agentsRunOn: "local",
};

const LANG_MAP = {
  py: "python", js: "javascript", ts: "typescript", html: "html", css: "css",
  json: "json", md: "markdown", yaml: "yaml", yml: "yaml", sh: "shell", env: "ini",
};

function iconForFile(path) {
  const ext = (path.split(".").pop() || "").toLowerCase();
  if (ext === "py") return "codicon-file-code";
  if (ext === "html") return "codicon-file-code";
  if (ext === "css") return "codicon-file-code";
  if (ext === "js") return "codicon-file-code";
  if (ext === "md") return "codicon-markdown";
  if (ext === "json") return "codicon-json";
  return "codicon-file";
}

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function qs(name, value) {
  return value ? `&${name}=${encodeURIComponent(value)}` : "";
}

function langForPath(path) {
  return LANG_MAP[(path.split(".").pop() || "").toLowerCase()] || "plaintext";
}

function langLabel(id) {
  const m = { python: "Python", javascript: "JavaScript", html: "HTML", css: "CSS", plaintext: "Plain Text" };
  return m[id] || id;
}

let workspaceIssues = [];
let markerDebounce = null;

function applyEditorMarkers(issues) {
  if (!state.monacoReady || !state.editor || typeof monaco === "undefined") return;
  const model = state.editor.getModel();
  if (!model) return;
  const rel = normalizePath(state.activeTab);
  const rows = (issues || []).filter(i => normalizePath(i.path) === rel);
  const markers = rows.map(i => {
    const line = Math.max(1, i.line || 1);
    const col = Math.max(1, i.column || 1);
    let sev = monaco.MarkerSeverity.Error;
    if (i.severity === "warning") sev = monaco.MarkerSeverity.Warning;
    else if (i.severity === "info") sev = monaco.MarkerSeverity.Info;
    return {
      severity: sev,
      message: i.message || "Issue",
      startLineNumber: line,
      startColumn: col,
      endLineNumber: line,
      endColumn: Math.min(model.getLineMaxColumn(line), col + 120),
    };
  });
  monaco.editor.setModelMarkers(model, "aion", markers);
}

function scheduleMarkerRefresh() {
  clearTimeout(markerDebounce);
  markerDebounce = setTimeout(async () => {
    await refreshDiagnostics();
    applyEditorMarkers(workspaceIssues);
  }, 700);
}

function completionKindMonaco(kind) {
  const m = {
    function: monaco.languages.CompletionItemKind.Function,
    class: monaco.languages.CompletionItemKind.Class,
    file: monaco.languages.CompletionItemKind.File,
    keyword: monaco.languages.CompletionItemKind.Keyword,
  };
  return m[kind] || monaco.languages.CompletionItemKind.Text;
}

function registerMonacoProviders() {
  if (typeof monaco === "undefined" || state._monacoProvidersReady) return;
  state._monacoProvidersReady = true;

  monaco.languages.registerHoverProvider(
    ["python", "javascript", "typescript", "html", "css", "json", "markdown", "plaintext"],
    {
      provideHover: async (model, position) => {
        if (!state.workspaceRoot || !state.activeTab) return null;
        try {
          const data = await api(
            `/ide/lsp/hover?path=${encodeURIComponent(state.activeTab)}&line=${position.lineNumber}`
            + `&output_dir=${encodeURIComponent(state.workspaceRoot)}${qs("project", state.projectName)}`
          );
          if (!data.contents) return null;
          return { contents: [{ value: data.contents }] };
        } catch {
          return null;
        }
      },
    }
  );

  const langs = ["python", "javascript", "typescript", "html", "css", "json", "markdown", "plaintext"];
  monaco.languages.registerCompletionItemProvider(langs, {
    triggerCharacters: ".@",
    provideCompletionItems: async (model, position) => {
      if (!state.workspaceRoot || !state.activeTab) return { suggestions: [] };
      const prefix = model.getValueInRange({
        startLineNumber: Math.max(1, position.lineNumber - 12),
        startColumn: 1,
        endLineNumber: position.lineNumber,
        endColumn: position.column,
      });
      try {
        const data = await api(
          `/ide/lsp/completions?path=${encodeURIComponent(state.activeTab)}`
          + `&line=${position.lineNumber}&column=${position.column}`
          + `&prefix=${encodeURIComponent(prefix)}`
          + `&output_dir=${encodeURIComponent(state.workspaceRoot)}${qs("project", state.projectName)}`
        );
        const word = model.getWordUntilPosition(position);
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: word.startColumn,
          endColumn: word.endColumn,
        };
        const suggestions = (data.completions || []).map((item, i) => ({
          label: item.label,
          kind: completionKindMonaco(item.kind),
          insertText: item.insertText || item.label,
          detail: item.detail || "",
          range,
          sortText: "a" + String(i).padStart(4, "0"),
        }));
        return { suggestions };
      } catch {
        return { suggestions: [] };
      }
    },
  });

  monaco.languages.registerCompletionItemProvider(langs, {
    triggerCharacters: [" ", "(", "\n"],
    provideCompletionItems: async (model, position) => {
      if (!state.workspaceRoot || !state.activeTab || !loadSettings().tab_completion) return { suggestions: [] };
      const prefix = model.getValueInRange({
        startLineNumber: Math.max(1, position.lineNumber - 15),
        startColumn: 1,
        endLineNumber: position.lineNumber,
        endColumn: position.column,
      });
      if (prefix.trim().length < 8) return { suggestions: [] };
      try {
        const data = await api("/ai/complete", {
          method: "POST",
          body: JSON.stringify({
            output_dir: state.workspaceRoot,
            path: state.activeTab,
            prefix,
            suffix: model.getValueInRange({
              startLineNumber: position.lineNumber,
              startColumn: position.column,
              endLineNumber: Math.min(model.getLineCount(), position.lineNumber + 3),
              endColumn: model.getLineMaxColumn(Math.min(model.getLineCount(), position.lineNumber + 3)),
            }),
            language: langForPath(state.activeTab),
          }),
        });
        const word = model.getWordUntilPosition(position);
        return {
          suggestions: (data.suggestions || []).map((item, i) => ({
            label: "✨ " + (item.display || "AI complete"),
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: item.text,
            range: {
              startLineNumber: position.lineNumber,
              endLineNumber: position.lineNumber,
              startColumn: word.startColumn,
              endColumn: position.column,
            },
            sortText: "z" + String(i).padStart(4, "0"),
          })),
        };
      } catch {
        return { suggestions: [] };
      }
    },
  });
}

function normalizePath(p) {
  return String(p || "").replace(/\\/g, "/").replace(/^\/+/, "");
}

/** Match tab path to real workspace file (e.g. index.html → generated_app/index.html). */
function resolveFilePath(path) {
  const norm = normalizePath(path);
  if (!norm) return norm;
  const files = state.allFiles || [];
  if (files.includes(norm)) return norm;
  const base = norm.split("/").pop();
  const matches = files.filter(f => f === norm || f.endsWith("/" + norm) || f.split("/").pop() === base);
  if (matches.length === 1) return matches[0];
  if (matches.length > 1) {
    const scoped = matches.find(f => state.projectName && f.startsWith(`${state.projectName}/`));
    return scoped || matches.find(f => f.includes("/")) || matches[0];
  }
  return norm;
}

function getEditorValue() {
  if (state.useFallback) return document.getElementById("codeFallback")?.value ?? "";
  return state.editor?.getValue() ?? "";
}

function setEditorBuffer(text) {
  if (state.useFallback) {
    const el = document.getElementById("codeFallback");
    if (el) el.value = text;
    return;
  }
  const model = state.editor?.getModel();
  if (model && model.getValue() !== text) model.setValue(text);
}

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts, signal: opts.signal });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

function $(id) {
  return document.getElementById(id);
}

function setText(id, text) {
  const el = $(id);
  if (el) el.textContent = text;
}

function setStatus(msg) {
  setText("statusText", msg);
}

function setComposerStatus(text) {
  setText("composerStatus", text);
}

function renderAttachChips() {
  const box = document.getElementById("attachChips");
  if (!box) return;
  box.innerHTML = "";
  for (const a of state.attached) {
    const chip = document.createElement("span");
    chip.className = "attach-chip";
    const icon = a.kind === "image"
      ? `<img class="attach-thumb" src="${a.preview || ""}" alt="" />`
      : `<i class="codicon codicon-file"></i>`;
    chip.innerHTML = `${icon} ${escapeHtml(a.path)} <button type="button" aria-label="Remove">×</button>`;
    chip.querySelector("button").onclick = () => {
      state.attached = state.attached.filter(x => x.path !== a.path);
      renderAttachChips();
    };
    box.appendChild(chip);
  }
  box.classList.toggle("hidden", !state.attached.length);
}

function addAttachment(path, content, opts = {}) {
  const rel = path.replace(/\\/g, "/");
  state.attached = state.attached.filter(a => a.path !== rel);
  state.attached.push({
    path: rel,
    content: (content || "").slice(0, 12000),
    kind: opts.kind || "text",
    preview: opts.preview || "",
  });
  renderAttachChips();
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = reject;
    r.readAsDataURL(file);
  });
}

async function attachLocalFile(file) {
  const name = (file.webkitRelativePath || file.name).replace(/\\/g, "/");
  const ext = (name.includes(".") ? "." + name.split(".").pop() : "").toLowerCase();
  if (IMAGE_EXTS.has(ext)) {
    if (file.size > 4_000_000) {
      setStatus(`Image too large: ${name} (max 4MB)`);
      return;
    }
    const dataUrl = await readFileAsDataUrl(file);
    addAttachment(name, `[Image attached: ${name}]`, { kind: "image", preview: dataUrl });
    const ta = $("followUp");
    if (ta && !ta.value.includes(`@${name}`)) {
      ta.value = (ta.value + ` @${name} `).trim() + " ";
    }
    return;
  }
  if (!TEXT_EXTS.has(ext)) {
    setStatus(`Unsupported file type: ${ext || name}`);
    return;
  }
  if (file.size > 800_000) {
    setStatus(`File too large: ${name}`);
    return;
  }
  addAttachment(name, await readFileAsText(file), { kind: "text" });
  const ta = $("followUp");
  if (ta && !ta.value.includes(`@${name}`)) {
    ta.value = (ta.value + ` @${name} `).trim() + " ";
  }
}

function inferProjectForAgent(description = "") {
  const mention = String(description).match(/@([^\s,]+)/);
  if (mention) {
    const p = normalizePath(mention[1]);
    if (p.includes("/")) return p.split("/")[0];
    if (p) return p;
  }
  if (state.activeTab) {
    const n = normalizePath(state.activeTab);
    if (n.includes("/")) return n.split("/")[0];
  }
  for (const a of state.attached) {
    const n = normalizePath(a.path);
    if (n.includes("/")) return n.split("/")[0];
  }
  return state.projectName || null;
}

function syncProjectFromActiveFile() {
  const p = inferProjectForAgent();
  if (!p || !state.workspaceRoot) return;
  state.projectName = p;
  const root = state.workspaceRoot.replace(/\\/g, "/").replace(/\/$/, "");
  state.projectPath = `${root}/${p}`;
  updateTitlebar();
  detectProject();
}

function buildAgentPrompt(description) {
  let desc = description.trim();
  if (state.attached.length) {
    desc += "\n\n--- Referenced files (user attached) ---\n";
    for (const a of state.attached) {
      if (a.kind === "image") {
        desc += `\n### ${a.path} (image)\nUser attached a screenshot/image. Use it as visual context for layout/branding if relevant.\n`;
      } else {
        desc += `\n### ${a.path}\n\`\`\`\n${a.content}\n\`\`\`\n`;
      }
    }
  }
  return desc;
}

function layoutEditor() {
  const box = document.querySelector(".editor-instance");
  const host = document.getElementById("monacoHost");
  const fallback = document.getElementById("codeFallback");
  if (box) {
    const h = Math.max(box.clientHeight, 120);
    const w = Math.max(box.clientWidth, 200);
    if (host && !state.useFallback) {
      host.style.width = `${w}px`;
      host.style.height = `${h}px`;
    }
    if (fallback && state.useFallback) {
      fallback.style.width = `${w}px`;
      fallback.style.height = `${h}px`;
    }
  }
  if (state.editor && !state.useFallback) {
    requestAnimationFrame(() => {
      state.editor.layout();
      state.editor.focus();
    });
  } else if (state.useFallback) {
    document.getElementById("codeFallback")?.focus();
  }
}

function loadRecentProjects() {
  try {
    const raw = localStorage.getItem(LS_RECENT_PROJECTS);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list.filter(p => typeof p === "string" && p.trim()) : [];
  } catch {
    return [];
  }
}

function pushRecentProject(path) {
  if (!path?.trim()) return;
  const norm = path.trim();
  const list = [norm, ...loadRecentProjects().filter(p => p !== norm)].slice(0, 12);
  localStorage.setItem(LS_RECENT_PROJECTS, JSON.stringify(list));
  renderLandingRecent();
}

function renderLandingRecent() {
  const list = $("landingRecentList");
  const viewAll = $("landingViewAll");
  if (!list) return;
  const recent = loadRecentProjects();
  list.innerHTML = "";
  if (viewAll) {
    viewAll.textContent = `View all (${recent.length})`;
    viewAll.classList.toggle("hidden", recent.length < 4);
  }
  if (!recent.length) {
    list.innerHTML = '<p class="landing-recent-empty">No recent projects yet</p>';
    return;
  }
  for (const path of recent.slice(0, 6)) {
    const name = path.split(/[/\\]/).pop() || path;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "landing-recent-item";
    btn.innerHTML = `<span>${escapeHtml(name.toUpperCase())}</span><i class="codicon codicon-chevron-right"></i>`;
    btn.title = path;
    btn.onclick = () => openPathOnServer(path).catch(e => alert(e.message));
    list.appendChild(btn);
  }
}

function showLanding(show) {
  $("landingPage")?.classList.toggle("hidden", !show);
  $("workbench")?.classList.toggle("hidden", show);
  document.body.classList.toggle("landing-mode", show);
  if (show) {
    renderLandingRecent();
    showWelcome(false);
  }
}

function updateHomeView() {
  showLanding(!state.workspaceRoot);
  if (state.workspaceRoot) {
    showWelcome(state.openTabs.length === 0);
  }
}

function showWelcome(show) {
  const welcome = document.getElementById("welcomeEditor");
  const host = document.getElementById("monacoHost");
  const fallback = document.getElementById("codeFallback");
  if (!welcome || !host) return;
  if ($("landingPage") && !$("landingPage").classList.contains("hidden")) {
    welcome.classList.add("hidden");
    return;
  }
  welcome.classList.toggle("hidden", !show);
  if (show) {
    host.style.display = "none";
    fallback?.classList.add("hidden");
  } else {
    if (state.useFallback) {
      host.style.display = "none";
      fallback?.classList.remove("hidden");
    } else {
      host.style.display = "block";
      host.style.visibility = "visible";
      fallback?.classList.add("hidden");
    }
    layoutEditor();
  }
}

function persistWorkspace() {
  if (state.workspaceRoot) localStorage.setItem(LS_WORKSPACE, state.workspaceRoot);
}

function closeWorkspace() {
  state.workspaceRoot = "";
  state.projectName = "";
  state.projectPath = "";
  state.openTabs = [];
  state.activeTab = null;
  localStorage.removeItem(LS_WORKSPACE);
  updateTitlebarProject();
  updateHomeView();
  refreshFileTree();
  setStatus("Ready");
}

function goToLanding() {
  if (document.body.classList.contains("agents-only")) return;
  closeWorkspace();
  renderLandingRecent();
}

function workspaceDisplayName() {
  if (!state.workspaceRoot) return "Aion_IDE";
  const label = state.projectName || state.workspaceRoot.split(/[/\\]/).pop() || "Project";
  return String(label).toUpperCase();
}

function titlebarDisplayName() {
  if (!state.workspaceRoot) return "";
  return state.workspaceRoot.split(/[/\\]/).pop() || state.projectName || "Project";
}

function updateTitlebarProject() {
  const tp = $("titlebarProject");
  if (!tp) return;
  const name = titlebarDisplayName();
  tp.textContent = name;
  tp.title = state.workspaceRoot || "";
}

async function detectProject() {
  if (!state.workspaceRoot) return;
  const display = workspaceDisplayName();
  const branch = $("statusBranch");
  if (branch) branch.innerHTML = `<i class="codicon codicon-repo"></i> ${escapeHtml(display)}`;
  updateTitlebarProject();
}

function updateStatusBar() {
  setText("statusLang", state.activeTab ? langLabel(langForPath(state.activeTab)) : "Plain Text");
  document.title = state.activeTab
    ? `${state.activeTab.split("/").pop()} — AION`
    : "AION";
  if (state.useFallback) {
    const fb = $("codeFallback");
    if (fb && state.activeTab) {
      const val = fb.value;
      const lines = val.split("\n");
      const last = lines[lines.length - 1] || "";
      setText("statusPos", `Ln ${lines.length}, Col ${last.length + 1}`);
    }
  } else if (state.editor?.getPosition()) {
    const p = state.editor.getPosition();
    setText("statusPos", `Ln ${p.lineNumber}, Col ${p.column}`);
  }
  const eol = state.activeTab && state.tabContents[state.activeTab]?.includes("\r\n") ? "CRLF" : "LF";
  setText("statusEol", eol);
  setText("toolbarPath", state.activeTab || "");
}

function truncateWorkspaceLabel(name, max = 20) {
  if (!name) return "Open Folder";
  return name.length > max ? name.slice(0, max) + "…" : name;
}

function updateWorkspaceHeader() {
  const el = document.getElementById("workspaceFolderName");
  if (!el) return;
  if (!state.workspaceRoot) {
    el.textContent = "Open Folder";
    el.title = "";
    return;
  }
  const name = state.workspaceRoot.split(/[/\\]/).pop() || state.workspaceRoot;
  el.textContent = truncateWorkspaceLabel(name.toUpperCase());
  el.title = state.workspaceRoot;
}

function buildTree(paths) {
  const root = { children: {}, files: [] };
  for (const p of paths) {
    const norm = p.replace(/\\/g, "/");
    const segs = norm.split("/");
    let node = root;
    for (let i = 0; i < segs.length; i++) {
      if (i === segs.length - 1) node.files.push({ name: segs[i], path: norm });
      else {
        if (!node.children[segs[i]]) node.children[segs[i]] = { children: {}, files: [] };
        node = node.children[segs[i]];
      }
    }
  }
  return root;
}

function renderTreeNode(node, depth, container, parentPath = "") {
  for (const folder of Object.keys(node.children).sort()) {
    const child = node.children[folder];
    const folderPath = parentPath ? `${parentPath}/${folder}` : folder;
    const row = document.createElement("div");
    row.className = "tree-node folder";
    row.dataset.path = folderPath;
    row.style.paddingLeft = `${4 + depth * 12}px`;
    row.innerHTML = `<i class="codicon codicon-chevron-down codicon-chevron"></i><i class="codicon codicon-folder-opened"></i><span class="name">${escapeHtml(folder)}</span>`;
    const wrap = document.createElement("div");
    row.onclick = e => {
      e.stopPropagation();
      state.createBasePath = folderPath;
      document.querySelectorAll(".tree-node.folder.selected").forEach(n => n.classList.remove("selected"));
      row.classList.add("selected");
      const open = wrap.style.display !== "none";
      wrap.style.display = open ? "none" : "block";
      row.querySelector(".codicon-chevron").className = `codicon codicon-chevron-${open ? "right" : "down"} codicon-chevron`;
      row.querySelector(".codicon-folder, .codicon-folder-opened")?.classList.toggle("codicon-folder-opened", !open);
      row.querySelector(".codicon-folder, .codicon-folder-opened")?.classList.toggle("codicon-folder", open);
    };
    container.appendChild(row);
    container.appendChild(wrap);
    renderTreeNode(child, depth + 1, wrap, folderPath);
  }
  for (const f of [...node.files].sort((a, b) => a.name.localeCompare(b.name))) {
    const row = document.createElement("div");
    row.className = "tree-node file";
    row.dataset.path = f.path;
    if (f.path === state.activeTab) row.classList.add("active");
    row.style.paddingLeft = `${22 + depth * 12}px`;
    row.innerHTML = `<i class="codicon codicon-chevron" style="visibility:hidden"></i><i class="codicon ${iconForFile(f.path)}"></i><span class="name">${escapeHtml(f.name)}</span>`;
    row.draggable = true;
    row.ondragstart = ev => {
      ev.dataTransfer.setData("application/x-AION-path", f.path);
      ev.dataTransfer.setData("text/plain", `@${f.path}`);
    };
    row.onclick = () => {
      const slash = f.path.lastIndexOf("/");
      state.createBasePath = slash >= 0 ? f.path.slice(0, slash) : "";
      document.querySelectorAll(".tree-node.folder.selected").forEach(n => n.classList.remove("selected"));
      openFile(f.path);
    };
    container.appendChild(row);
  }
}

function cancelInlineCreate() {
  document.querySelector("#fileTree .tree-node.inline-create")?.remove();
  state.inlineCreate = null;
}

/** @param {string|null} basePath null = use selected folder in tree; "" = workspace root */
function showInlineCreate(type, basePath = null) {
  if (!state.workspaceRoot) return pickFolder();
  cancelInlineCreate();
  const raw = basePath !== null ? basePath : (state.createBasePath || "");
  const base = raw.replace(/\\/g, "/").replace(/\/$/, "");
  state.inlineCreate = { type, basePath: base };

  const tree = document.getElementById("fileTree");
  const empty = tree.querySelector(".tree-empty");
  if (empty) empty.remove();

  const depth = base ? base.split("/").length : 0;
  const row = document.createElement("div");
  row.className = `tree-node inline-create ${type === "folder" ? "folder" : "file"}`;
  row.style.paddingLeft = type === "folder" ? `${4 + depth * 12}px` : `${22 + depth * 12}px`;
  const icon = type === "folder" ? "codicon-folder" : "codicon-new-file";
  const prefix = base ? `${base}/` : "";
  row.innerHTML = `
    <i class="codicon codicon-chevron" style="visibility:hidden"></i>
    <i class="codicon ${icon}"></i>
    ${base ? `<span class="tree-inline-prefix">${escapeHtml(prefix)}</span>` : ""}
    <input type="text" class="tree-inline-input" autocomplete="off" spellcheck="false" aria-label="${type === "folder" ? "New folder name" : "New file name"}" />
  `;

  let parentContainer = tree;
  if (base) {
    const folderRow = tree.querySelector(`.tree-node.folder[data-path="${CSS.escape(base)}"]`);
    if (folderRow?.nextElementSibling) {
      const wrap = folderRow.nextElementSibling;
      wrap.style.display = "block";
      const chev = folderRow.querySelector(".codicon-chevron");
      if (chev) chev.className = "codicon codicon-chevron-down codicon-chevron";
      parentContainer = wrap;
    }
  }
  parentContainer.insertBefore(row, parentContainer.firstChild);

  const input = row.querySelector(".tree-inline-input");
  input.focus();
  input.onkeydown = async e => {
    if (e.key === "Escape") {
      e.preventDefault();
      cancelInlineCreate();
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      await commitInlineCreate(input.value.trim());
    }
  };
  input.onblur = () => {
    setTimeout(() => {
      if (state.inlineCreate && document.activeElement?.closest?.(".inline-create")) return;
      cancelInlineCreate();
    }, 120);
  };
}

async function commitInlineCreate(name) {
  if (!state.inlineCreate) return;
  const { type, basePath } = state.inlineCreate;
  if (!name) {
    cancelInlineCreate();
    return;
  }
  cancelInlineCreate();
  const rel = basePath ? `${basePath}/${name}` : name;
  const norm = rel.replace(/\\/g, "/").replace(/\/+/g, "/");
  try {
    const apiPath = type === "folder" ? `${norm}/.keep` : norm;
    await api("/workspace/new-file", {
      method: "POST",
      body: JSON.stringify({ output_dir: state.workspaceRoot, path: apiPath, content: "" }),
    });
    await refreshFileTree(state.projectName);
    if (type === "file") await openFile(norm);
    else setStatus(`Created folder ${norm}`);
  } catch (e) {
    setStatus(e.message);
    showInlineCreate(type, basePath);
    const input = document.querySelector("#fileTree .tree-inline-input");
    if (input) {
      input.value = name;
      input.focus();
    }
  }
}

function updateTitlebar() {
  updateTitlebarProject();
  const branch = $("statusBranch");
  if (branch && state.workspaceRoot) {
    branch.innerHTML = `<i class="codicon codicon-repo"></i> ${escapeHtml(workspaceDisplayName())}`;
  }
}

function updateBreadcrumbs() {
  const bc = document.getElementById("breadcrumbs");
  bc.innerHTML = "";
  if (!state.activeTab) return;
  const parts = state.activeTab.replace(/\\/g, "/").split("/");
  parts.forEach((seg, i) => {
    if (i > 0) {
      const sep = document.createElement("span");
      sep.className = "breadcrumb-sep";
      sep.textContent = " › ";
      bc.appendChild(sep);
    }
    const span = document.createElement("span");
    span.className = "breadcrumb-seg";
    span.textContent = seg;
    const sub = parts.slice(0, i + 1).join("/");
    span.onclick = () => {
      if (i < parts.length - 1) return;
      openFile(sub);
    };
    bc.appendChild(span);
  });
}

async function loadProjectList() {
  const sel = document.getElementById("projectSelect");
  if (!state.workspaceRoot) {
    sel.innerHTML = "";
    return;
  }
  const projects = await api(`/workspace/projects?output_dir=${encodeURIComponent(state.workspaceRoot)}`);
  sel.innerHTML = "";
  const optRoot = document.createElement("option");
  optRoot.value = "";
  optRoot.textContent = `(workspace) ${state.workspaceRoot.split(/[/\\]/).pop()}`;
  sel.appendChild(optRoot);
  for (const p of projects) {
    const o = document.createElement("option");
    o.value = p.name;
    o.textContent = p.name;
    if (p.name === state.projectName) o.selected = true;
    sel.appendChild(o);
  }
}

async function setWorkspace(path) {
  state.workspaceRoot = path;
  state.projectName = "";
  state.treeScope = "full";
  persistWorkspace();
  pushRecentProject(path);
  showLanding(false);
  const name = path.split(/[/\\]/).pop();
  updateWorkspaceHeader();
  updateTitlebar();
  try {
    await loadProjectList();
    const sel = document.getElementById("projectSelect");
    if (sel) sel.value = "";
    await refreshFileTree();
    await detectProject();
    await refreshDiagnostics();
    updateHomeView();
    setStatus(`Opened ${name}`);
    appendOutput(`Workspace: ${path}`, "terminal");
    updateAgentsWorkspaceLabel();
    renderAgentsWorkspaceMenu();
    renderAgentsSidebar();
  } catch (e) {
    setStatus(e.message);
    updateHomeView();
  }
}

async function landingCloneRepo() {
  const url = prompt("Repository URL (https://github.com/user/repo.git)");
  if (!url?.trim()) return;
  const base = state.suggestedWorkspace || loadRecentProjects()[0]?.replace(/[/\\][^/\\]+$/, "") || "";
  const name = url.trim().split("/").pop()?.replace(/\.git$/i, "") || "cloned-repo";
  const dest = base ? `${base.replace(/[/\\]$/, "")}/${name}` : name;
  setStatus("Cloning repository…");
  try {
    await api("/terminal/run", {
      method: "POST",
      body: JSON.stringify({
        output_dir: base || ".",
        command: `git clone ${JSON.stringify(url.trim())} ${JSON.stringify(dest)}`,
        cwd: base || undefined,
      }),
    });
    await openPathOnServer(dest);
  } catch (e) {
    const manual = prompt("Clone failed. Paste local folder path to open:", dest);
    if (manual?.trim()) await openPathOnServer(manual.trim());
    else alert(e.message || "Clone failed");
  }
}

function landingConnectSsh() {
  const msg =
    "Remote via SSH lets you work on a project on another computer (cloud VM, lab server, etc.), " +
    "similar to VS Code Remote SSH.\n\n" +
    "Enter SSH login (example: you@my-server.com). AION will open the Agents Window — " +
    "use Terminal (Ctrl+`) to run ssh, or ask the AI for remote setup help.\n\n" +
    "Full one-click remote folder mount is planned for a future update.";
  const host = prompt(msg + "\n\nSSH host (user@hostname):");
  if (!host?.trim()) return;
  setStatus(`SSH remote: ${host.trim()} — use Terminal or AI chat`);
  popoutAgentsWindow();
}

function initLandingPage() {
  $("landingOpenProject")?.addEventListener("click", pickFolder);
  $("landingCloneRepo")?.addEventListener("click", () => landingCloneRepo());
  $("landingConnectSsh")?.addEventListener("click", landingConnectSsh);
  $("landingSettings")?.addEventListener("click", openSettingsPanel);
  $("landingPro")?.addEventListener("click", () => setStatus("AION Pro — multi-agent pipeline enabled"));
  $("landingAgentsPill")?.addEventListener("click", popoutAgentsWindow);
  $("landingViewAll")?.addEventListener("click", () => {
    const recent = loadRecentProjects();
    if (recent[0]) openPathOnServer(recent[0]).catch(e => alert(e.message));
  });
  renderLandingRecent();
}

const TEXT_EXTS = new Set([
  ".py", ".html", ".css", ".js", ".ts", ".tsx", ".json", ".md", ".txt",
  ".yaml", ".yml", ".env", ".toml", ".sh", ".xml", ".ini", ".cfg",
]);
const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"]);

async function openPathOnServer(path) {
  const data = await api("/workspace/open-path", {
    method: "POST",
    body: JSON.stringify({ path: path.trim() }),
  });
  await setWorkspace(data.path);
  if (data.files?.length) {
    const py = data.files.find(f => f.endsWith("main.py")) || data.files.find(f => f.endsWith(".py"));
    if (py) await openFile(py);
  }
}

async function importDroppedFiles(filesMap, folderName) {
  setStatus("Importing dropped files…");
  const data = await api("/workspace/import", {
    method: "POST",
    body: JSON.stringify({ folder_name: folderName, files: filesMap }),
  });
  await setWorkspace(data.path);
  setStatus(`Imported ${data.files_written} files → ${data.project}`);
  const first = data.files?.find(f => f.endsWith("main.py")) || data.files?.[0];
  if (first) await openFile(first);
}

async function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = reject;
    r.readAsText(file);
  });
}

async function walkDirectoryHandle(dirHandle, base = "") {
  const files = {};
  let count = 0;
  const maxFiles = 150;
  for await (const [name, handle] of dirHandle.entries()) {
    if (count >= maxFiles) break;
    const rel = base ? `${base}/${name}` : name;
    if (handle.kind === "directory") {
      if (name.startsWith(".") || name === "node_modules" || name === "__pycache__" || name === ".venv") continue;
      const sub = await walkDirectoryHandle(handle, rel);
      Object.assign(files, sub);
      count += Object.keys(sub).length;
    } else if (handle.kind === "file") {
      const ext = (name.includes(".") ? "." + name.split(".").pop() : "").toLowerCase();
      if (!TEXT_EXTS.has(ext)) continue;
      try {
        const file = await handle.getFile();
        if (file.size > 800_000) continue;
        files[rel.replace(/\\/g, "/")] = await readFileAsText(file);
        count++;
      } catch { /* skip */ }
    }
  }
  return files;
}

async function walkFileTreeEntry(entry, base = "") {
  const files = {};
  if (entry.isFile) {
    const name = entry.name;
    const ext = (name.includes(".") ? "." + name.split(".").pop() : "").toLowerCase();
    if (!TEXT_EXTS.has(ext)) return files;
    const file = await new Promise((res, rej) => entry.file(res, rej));
    if (file.size > 800_000) return files;
    const rel = (base ? `${base}/` : "") + name;
    files[rel.replace(/\\/g, "/")] = await readFileAsText(file);
    return files;
  }
  if (entry.isDirectory) {
    const reader = entry.createReader();
    const entries = await new Promise((res, rej) => {
      const all = [];
      const read = () => {
        reader.readEntries(batch => {
          if (!batch.length) res(all);
          else { all.push(...batch); read(); }
        }, rej);
      };
      read();
    });
    for (const child of entries) {
      if (child.name.startsWith(".") || child.name === "node_modules") continue;
      Object.assign(files, await walkFileTreeEntry(child, base ? `${base}/${entry.name}` : entry.name));
    }
  }
  return files;
}

async function attachDroppedFiles(e) {
  e.preventDefault();
  e.stopPropagation();
  hideDropOverlay();
  const treePath = e.dataTransfer?.getData("application/x-AION-path");
  if (treePath && state.workspaceRoot) {
    try {
      const data = await api(
        `/workspace/file?path=${encodeURIComponent(treePath)}&output_dir=${encodeURIComponent(state.workspaceRoot)}`
      );
      addAttachment(treePath, data.content);
      document.getElementById("followUp").value =
        (document.getElementById("followUp").value + ` @${treePath} `).trim() + " ";
      document.getElementById("followUp").focus();
      setStatus(`Attached ${treePath}`);
      return;
    } catch (_) {}
  }
  const fileList = e.dataTransfer?.files;
  if (!fileList?.length) return;

  for (const file of fileList) {
    await attachLocalFile(file);
  }
  document.getElementById("followUp")?.focus();
  setStatus(`Attached ${state.attached.length} file(s) — Agent will use as context`);
}

async function handleDropEvent(e) {
  if (e.dataTransfer?.files?.length) return attachDroppedFiles(e);
  hideDropOverlay();
}

function showDropOverlay(active) {
  const el = document.getElementById("dropOverlay");
  el.classList.remove("hidden");
  el.classList.toggle("visible", true);
  el.classList.toggle("drag-active", active);
  document.body.classList.toggle("is-dragging", active);
}

function hideDropOverlay() {
  const el = document.getElementById("dropOverlay");
  el.classList.remove("visible", "drag-active");
  el.classList.add("hidden");
  document.body.classList.remove("is-dragging");
}

function initDragDrop() {
  let dragDepth = 0;
  const zones = [
    document.body,
    document.getElementById("workbench"),
    document.getElementById("chatDropZone"),
    document.getElementById("followUp"),
    document.getElementById("auxiliaryBar"),
  ];

  const onDragEnter = e => {
    if (!e.dataTransfer?.types?.includes("Files")) return;
    e.preventDefault();
    dragDepth++;
    showDropOverlay(true);
  };
  const onDragLeave = e => {
    if (!e.dataTransfer?.types?.includes("Files")) return;
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) hideDropOverlay();
  };
  const onDragOver = e => {
    if (e.dataTransfer?.types?.includes("Files")) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    }
  };
  const onDrop = e => {
    dragDepth = 0;
    if (e.dataTransfer?.types?.includes("Files")) handleDropEvent(e);
  };

  for (const z of zones) {
    if (!z) continue;
    z.addEventListener("dragenter", onDragEnter);
    z.addEventListener("dragleave", onDragLeave);
    z.addEventListener("dragover", onDragOver);
    z.addEventListener("drop", onDrop);
  }
}

async function pickFolder() {
  /* Cursor-style: open folder on disk (not copy into workspace/) */
  try {
    const data = await api("/pick-folder");
    if (!data.cancelled && data.path) {
      await setWorkspace(data.path);
      return;
    }
    if (!data.cancelled) return;
  } catch {
    /* tk unavailable — fall through */
  }
  const pasted = document.getElementById("pathPaste")?.value?.trim();
  if (pasted) {
    await openPathOnServer(pasted);
    return;
  }
  document.getElementById("pathPaste")?.focus();
  setStatus("Paste a folder path and press Open (like Cursor Open Folder)");
}

async function loadStats() {
  try {
    const h = await api("/health");
    const m = h.noesis || {};
    const llm = h.llm || {};
    state.suggestedWorkspace = h.suggested_workspace || h.default_workspace;
    state.apiPort = h.api_port || location.port || "8090";
    state.llmModel = llm.model || "auto";
    const stats = document.getElementById("stats");
    if (stats) stats.textContent = `Mem ${m.total_memories || 0} · ${llm.provider || "?"}`;
  } catch (e) {
    setStatus("API: " + e.message);
  }
}

function showPanel(name) {
  state.activePanel = name;
  document.querySelectorAll(".panel-tab").forEach(t => {
    t.classList.toggle("active", t.dataset.panel === name);
  });
  document.getElementById("panelTerminal").classList.toggle("hidden", name !== "terminal");
  document.getElementById("panelOutput").classList.toggle("hidden", name !== "output");
  document.getElementById("panelProblems").classList.toggle("hidden", name !== "problems");
  toggleBottomPanel(true);
}

function appendOutput(text, panel = "output") {
  const el = panel === "terminal" ? document.getElementById("terminalOutput") : document.getElementById("runOutput");
  if (!el) return;
  el.textContent += text + (text.endsWith("\n") ? "" : "\n");
  el.scrollTop = el.scrollHeight;
}

async function refreshDiagnostics() {
  if (!state.workspaceRoot) return;
  try {
    const data = await api(
      `/workspace/diagnostics?output_dir=${encodeURIComponent(state.workspaceRoot)}${qs("project", state.projectName)}`
    );
    workspaceIssues = data.issues || [];
    state.problemCount = data.errors || 0;
    const errEl = $("statusErrors");
    const errCount = data.errors ?? 0;
    if (errEl) errEl.innerHTML = `<i class="codicon codicon-error"></i> ${errCount}`;
    const warnEl = $("statusWarnings");
    const warnCount = data.warnings ?? 0;
    if (warnEl) warnEl.innerHTML = `<i class="codicon codicon-warning"></i> ${warnCount}`;
    const list = $("problemsList");
    if (!list) return;
    list.innerHTML = "";
    for (const issue of workspaceIssues) {
      const row = document.createElement("div");
      const isWarn = issue.severity === "warning";
      row.className = "problem-row" + (isWarn ? " problem-warn" : "");
      const icon = isWarn ? "codicon-warning" : "codicon-error";
      row.innerHTML = `<i class="codicon ${icon}"></i><span class="msg">${escapeHtml(issue.path)}:${issue.line} — ${escapeHtml(issue.message)}</span>`;
      row.onclick = () => openFile(issue.path, issue.line);
      list.appendChild(row);
    }
    if (!workspaceIssues.length) {
      list.innerHTML = '<div class="tree-empty">No problems detected</div>';
    }
    applyEditorMarkers(workspaceIssues);
  } catch { /* ignore */ }
}

async function pollRunJobs() {
  try {
    const st = await api("/run/status");
    const running = (st.jobs || []).filter(j => j.running);
    const badge = $("bgTerminalBadge");
    const count = $("bgTerminalCount");
    if (badge && count) {
      if (running.length) {
        badge.classList.remove("hidden");
        count.textContent = String(running.length);
      } else {
        badge.classList.add("hidden");
      }
    }
    if (state.runJobId) {
      const out = await api(`/run/output/${state.runJobId}`);
      const box = document.getElementById("runOutput");
      if (out.output) box.textContent = out.output;
      if (!out.running) {
        appendOutput(`\n[exit ${out.exit_code}]`);
        state.runJobId = null;
        setStatus(`Finished (exit ${out.exit_code})`);
      }
    }
  } catch { /* ignore */ }
}

function willOpenInBrowser(activeFile, files) {
  if (activeFile?.toLowerCase().endsWith(".html")) return true;
  const prefix = state.projectName ? `${state.projectName}/` : "";
  return (files || state.allFiles || []).some(
    f => f === `${prefix}index.html`.replace(/\/+/g, "/") || f.endsWith("/index.html")
  );
}

/** Open preview tab immediately (avoids popup blockers), then navigate when server is ready. */
function previewUrlFromResponse(data) {
  if (data?.url) return data.url;
  const port = state.apiPort || location.port || "8090";
  return `http://${location.hostname || "127.0.0.1"}:${port}/preview/`;
}

async function autoOpenPreview(url, previewWin, ready = true) {
  const target = url || previewUrlFromResponse({});
  if (!ready) {
    appendOutput("Preview failed. Restart AION (aion serve) and press F5 again.");
    if (previewWin && !previewWin.closed) previewWin.close();
    return;
  }
  try {
    const check = await fetch(`${target}index.html`);
    if (!check.ok) throw new Error(`Preview returned ${check.status}`);
  } catch (e) {
    appendOutput(`Preview check failed: ${e.message}. Restart: aion serve`);
    return;
  }
  if (previewWin && !previewWin.closed) {
    previewWin.location.href = target;
  } else {
    window.open(target, "AION_preview");
  }
  appendOutput(`Opened ${target}`);
  setStatus(`Preview: ${target}`);
}

async function runCurrentFile() {
  if (!state.workspaceRoot) return pickFolder();
  if (!state.activeTab) return alert("Open a file to run (e.g. main.py)");
  await saveActiveFile().catch(() => {});
  if (loadSettings().openOutput !== false) showPanel("output");
  const isWeb = state.activeTab.toLowerCase().endsWith(".html");
  const previewWin = isWeb ? window.open("about:blank", "AION_preview") : null;
  appendOutput(`▶ Run ${state.activeTab}`);
  try {
    const data = await api("/run/file", {
      method: "POST",
      body: JSON.stringify({
        output_dir: state.workspaceRoot,
        file_path: state.activeTab,
        background: isWeb,
      }),
    });
    if (data.url) autoOpenPreview(data.url, previewWin, data.ready !== false);
    if (data.background && data.job_id) {
      state.runJobId = data.job_id;
      appendOutput(`Server: ${data.command}${data.port ? ` (port ${data.port})` : ""}`);
    } else {
      appendOutput(data.output || "(done)");
      setStatus(`exit ${data.exit_code}`);
    }
    await pollRunJobs();
  } catch (e) {
    if (previewWin && !previewWin.closed) previewWin.close();
    appendOutput(`Error: ${e.message}`);
  }
}

async function runProject() {
  if (!state.workspaceRoot) return pickFolder();
  await saveActiveFile().catch(() => {});
  if (loadSettings().openOutput !== false) showPanel("output");
  const isWeb = willOpenInBrowser(state.activeTab, state.allFiles);
  const previewWin = isWeb ? window.open("about:blank", "AION_preview") : null;
  appendOutput("▶ Run Project…");
  try {
    const data = await api("/run/project", {
      method: "POST",
      body: JSON.stringify({
        output_dir: state.workspaceRoot,
        project: state.projectName || null,
        active_file: state.activeTab,
        background: true,
      }),
    });
    appendOutput(`${data.label}\n$ ${data.command}`);
    if (data.url) autoOpenPreview(data.url, previewWin, data.ready !== false);
    if (!data.ready && data.url) appendOutput(data.output || "Server not ready.");
    if (data.job_id) {
      state.runJobId = data.job_id;
      if (!data.url) setStatus("Running…");
    }
    if (data.output) appendOutput(data.output);
    await pollRunJobs();
  } catch (e) {
    if (previewWin && !previewWin.closed) previewWin.close();
    appendOutput(`Error: ${e.message}`);
    alert(e.message);
  }
}

async function stopRun() {
  await api("/run/stop", { method: "POST", body: JSON.stringify({}) });
  state.runJobId = null;
  appendOutput("[stopped]");
  await pollRunJobs();
}

async function refreshFileTree(projectHint, retried = false) {
  cancelInlineCreate();
  const tree = document.getElementById("fileTree");
  tree.innerHTML = "";

  if (!state.workspaceRoot) {
    updateWorkspaceHeader();
    tree.innerHTML = '<div class="tree-empty">Open a folder to explore</div>';
    updateHomeView();
    setComposerStatus("");
    return;
  }

  const sel = document.getElementById("projectSelect");
  try {
    const hint = typeof projectHint === "string" ? projectHint : undefined;
    const filter = hint !== undefined ? hint : (sel?.value || "");
    const scope = filter ? "project" : "full";
    const data = await api(
      `/workspace/files?output_dir=${encodeURIComponent(state.workspaceRoot)}&scope=${scope}${qs("project", filter || null)}${qs("active_file", state.activeTab)}`
    );
    if (filter) {
      state.projectName = data.project;
      state.projectPath = data.path;
    } else {
      state.projectName = "";
      state.projectPath = state.workspaceRoot;
    }
    state.allFiles = data.files || [];
    state.fileCount = state.allFiles.length;
    setComposerStatus(`${state.fileCount} Files`);
    if (sel && projectHint !== undefined) sel.value = projectHint;
    updateWorkspaceHeader();

    if (!data.files?.length) {
      tree.innerHTML = '<div class="tree-empty">Empty folder</div>';
      return;
    }
    renderTreeNode(buildTree(data.files), 0, tree, "");
  } catch (e) {
    if (!retried && (sel?.value || state.projectName)) {
      if (sel) sel.value = "";
      state.projectName = "";
      state.projectPath = state.workspaceRoot;
      return refreshFileTree("", true);
    }
    tree.innerHTML = `<div class="tree-empty tree-error">${escapeHtml(e.message)}<br><button type="button" class="tree-retry-btn" id="btnTreeRetry">Retry</button></div>`;
    document.getElementById("btnTreeRetry")?.addEventListener("click", () => refreshFileTree(""));
    setStatus(e.message);
  }
}

function renderTabs() {
  const bar = document.getElementById("tabBar");
  bar.innerHTML = "";
  if (!state.openTabs.length) {
    updateHomeView();
    return;
  }
  showWelcome(false);
  for (const path of state.openTabs) {
    const tab = document.createElement("div");
    tab.dataset.path = path;
    tab.className = "tab" + (path === state.activeTab ? " active" : "") + (state.dirty.has(path) ? " dirty" : "");
    tab.innerHTML = `
      <i class="codicon ${iconForFile(path)}"></i>
      <span class="tab-label">${escapeHtml(path.split("/").pop())}</span>
      <span class="tab-close"><i class="codicon codicon-close"></i></span>`;
    tab.onclick = e => {
      if (e.target.closest(".tab-close")) closeTab(path);
      else void switchTab(path);
    };
    bar.appendChild(tab);
  }
}

function closeTab(path) {
  state.openTabs = state.openTabs.filter(p => p !== path);
  delete state.tabContents[path];
  state.dirty.delete(path);
  if (state.models[path]) { state.models[path].dispose(); delete state.models[path]; }
  if (state.activeTab === path) {
    const next = state.openTabs.at(-1);
    if (next) void switchTab(next);
    else {
      state.activeTab = null;
      updateHomeView();
    }
  }
  renderTabs();
}

async function loadFileContent(path) {
  const norm = resolveFilePath(path);
  if (!state.workspaceRoot) return { path: norm, content: "" };
  const data = await api(
    `/workspace/file?path=${encodeURIComponent(norm)}&output_dir=${encodeURIComponent(state.workspaceRoot)}`
  );
  const content = data.content ?? "";
  state.tabContents[norm] = content;
  return { path: norm, content };
}

async function switchTab(path) {
  if (!state.monacoReady) return;
  const norm = resolveFilePath(path);
  let content = state.tabContents[norm];
  if ((content === undefined || content === "") && state.workspaceRoot) {
    try {
      const loaded = await loadFileContent(norm);
      content = loaded.content;
      if (loaded.path !== norm && state.openTabs.includes(path) && !state.openTabs.includes(loaded.path)) {
        state.openTabs = state.openTabs.map(p => (p === path ? loaded.path : p));
        if (state.activeTab === path) state.activeTab = loaded.path;
      }
    } catch (e) {
      setStatus(e.message);
      content = content ?? "";
    }
  }
  const active = resolveFilePath(state.openTabs.includes(norm) ? norm : path);
  state.activeTab = active;
  showWelcome(false);
  setEditorBuffer(content ?? "");
  if (!state.useFallback && state.editor) {
    const lang = langForPath(active);
    let model = state.models[active];
    if (model) {
      if (model.getValue() !== (content ?? "")) model.setValue(content ?? "");
      if (model.getLanguageId() !== lang) monaco.editor.setModelLanguage(model, lang);
    } else {
      model = monaco.editor.createModel(content ?? "", lang);
      state.models[active] = model;
    }
    state.editor.setModel(model);
  }
  renderTabs();
  document.querySelectorAll(".tree-node.file").forEach(n =>
    n.classList.toggle("active", n.dataset.path === active)
  );
  syncProjectFromActiveFile();
  updateBreadcrumbs();
  updateStatusBar();
  detectProject().catch(() => {});
  layoutEditor();
  applyEditorMarkers(workspaceIssues);
}

async function openFile(path, revealLine) {
  if (!state.workspaceRoot) return pickFolder();
  try {
    const { path: norm, content } = await loadFileContent(path);
    if (!state.openTabs.includes(norm)) state.openTabs.push(norm);
    state.tabContents[norm] = content;
    pushFileNav(norm);
    renderTabs();
    if (state.monacoReady) {
      await switchTab(norm);
      if (revealLine && state.editor) {
        const line = Math.max(1, Number(revealLine) || 1);
        state.editor.revealLineInCenter(line);
        state.editor.setPosition({ lineNumber: line, column: 1 });
        state.editor.focus();
      }
    } else {
      state.activeTab = norm;
      syncProjectFromActiveFile();
    }
  } catch (e) {
    setStatus(`Cannot open ${normalizePath(path)}: ${e.message}`);
  }
}

async function saveActiveFile() {
  if (!state.activeTab || !state.workspaceRoot) return;
  const content = getEditorValue();
  await api("/workspace/file", {
    method: "PUT",
    body: JSON.stringify({ output_dir: state.workspaceRoot, path: state.activeTab, content }),
  });
  state.tabContents[state.activeTab] = content;
  state.dirty.delete(state.activeTab);
  renderTabs();
  setStatus(`Saved ${state.activeTab}`);
}

/* Composer */
function scrollComposer() {
  const feed = document.getElementById("composerFeed");
  if (!feed) return;
  feed.scrollTop = feed.scrollHeight;
  saveActiveSessionFeed();
}

function removeUserMessage(id) {
  state.userMessages = state.userMessages.filter(m => m.id !== id);
  document.querySelector(`.msg-user-wrap[data-msg-id="${id}"]`)?.remove();
}

function addUserMessage(text, attachSnapshot = null) {
  const id = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const attachments = attachSnapshot || state.attached.map(a => ({ ...a }));
  state.userMessages.push({ id, text, attachments });

  const wrap = document.createElement("div");
  wrap.className = "msg-user-wrap";
  wrap.dataset.msgId = id;

  const toolbar = document.createElement("div");
  toolbar.className = "msg-user-toolbar";
  toolbar.innerHTML = `
    <button type="button" title="Edit prompt" data-action="edit"><i class="codicon codicon-edit"></i></button>
    <button type="button" title="Copy" data-action="copy"><i class="codicon codicon-copy"></i></button>
    <button type="button" title="Resend" data-action="resend"><i class="codicon codicon-debug-restart"></i></button>`;
  toolbar.querySelector('[data-action="edit"]').onclick = e => {
    e.stopPropagation();
    editUserMessage(id);
  };
  toolbar.querySelector('[data-action="copy"]').onclick = e => {
    e.stopPropagation();
    navigator.clipboard?.writeText(text);
    setStatus("Copied to clipboard");
  };
  toolbar.querySelector('[data-action="resend"]').onclick = e => {
    e.stopPropagation();
    if (!state.running) runPipeline(text);
  };

  const body = document.createElement("div");
  body.className = "msg-user-body";
  body.textContent = text;

  wrap.appendChild(toolbar);
  wrap.appendChild(body);

  if (attachments.length) {
    const att = document.createElement("div");
    att.className = "msg-user-attachments";
    for (const a of attachments) {
      if (a.kind === "image" && a.preview) {
        const img = document.createElement("img");
        img.className = "msg-user-attach-thumb";
        img.src = a.preview;
        img.alt = a.path;
        att.appendChild(img);
      } else {
        const tag = document.createElement("span");
        tag.className = "attach-chip";
        tag.innerHTML = `<i class="codicon codicon-file"></i> ${escapeHtml(a.path)}`;
        att.appendChild(tag);
      }
    }
    wrap.appendChild(att);
  }

  document.getElementById("composerFeed").appendChild(wrap);
  scrollComposer();
  updateAgentsHomeMode();
}

function editUserMessage(id) {
  const msg = state.userMessages.find(m => m.id === id);
  if (!msg || state.running) return;
  state.editingMessageId = id;
  const ta = $("followUp");
  if (ta) {
    ta.value = msg.text;
    ta.focus();
  }
  state.attached = msg.attachments.map(a => ({ ...a }));
  renderAttachChips();
  removeUserMessage(id);
  showWelcome(false);
  setStatus("Editing message — change text and send again");
}

function addThought(seconds = 1) {
  const el = document.createElement("div");
  el.className = "msg-thought";
  el.textContent = `Thought for ${seconds}s`;
  document.getElementById("composerFeed").appendChild(el);
  scrollComposer();
}

function addAgentLine(role, summary, isFail = false) {
  const el = document.createElement("div");
  el.className = "msg-agent" + (isFail ? " fail" : "");
  el.innerHTML = `<strong>${escapeHtml(role)}</strong> — ${escapeHtml(summary)}`;
  document.getElementById("composerFeed").appendChild(el);
  scrollComposer();
}

function formatSummaryMarkdown(text) {
  const lines = String(text || "").split("\n");
  const out = [];
  for (const line of lines) {
    const t = line.trimEnd();
    if (!t) {
      out.push("<br>");
      continue;
    }
    if (t.startsWith("## ")) {
      out.push(`<h3 class="summary-h">${escapeHtml(t.slice(3))}</h3>`);
    } else if (t.startsWith("### ")) {
      out.push(`<h4 class="summary-h">${escapeHtml(t.slice(4))}</h4>`);
    } else if (t.startsWith("- ")) {
      let body = escapeHtml(t.slice(2));
      body = body.replace(/`([^`]+)`/g, "<code>$1</code>");
      body = body.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      out.push(`<div class="summary-li">• ${body}</div>`);
    } else {
      let body = escapeHtml(t);
      body = body.replace(/`([^`]+)`/g, "<code>$1</code>");
      body = body.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      out.push(`<p class="summary-p">${body}</p>`);
    }
  }
  return out.join("");
}

function addSummaryMessage(text) {
  const feed = document.getElementById("composerFeed");
  const wrap = document.createElement("div");
  wrap.className = "msg-summary";
  wrap.innerHTML = `
    <div class="summary-header"><i class="codicon codicon-sparkle"></i> Summary</div>
    <div class="summary-body">${formatSummaryMarkdown(text)}</div>`;
  feed.appendChild(wrap);
  scrollComposer();
  updateActiveExecTab({ running: false, title: "Done" });
}

function renderDiffLines(lines) {
  return lines.map(line => {
    let cls = "ctx";
    if (line.startsWith("+") && !line.startsWith("+++")) cls = "add";
    else if (line.startsWith("-") && !line.startsWith("---")) cls = "del";
    else if (line.startsWith("@@") || line.startsWith("---") || line.startsWith("+++")) cls = "hdr";
    return `<div class="diff-line ${cls}">${escapeHtml(line)}</div>`;
  }).join("");
}

function buildDiffFromBeforeAfter(before, after) {
  const bl = before.split("\n");
  const al = after.split("\n");
  const out = [];
  let i = 0, j = 0;
  while (i < bl.length || j < al.length) {
    if (i < bl.length && j < al.length && bl[i] === al[j]) { out.push(` ${bl[i]}`); i++; j++; }
    else if (j < al.length && (i >= bl.length || bl[i] !== al[j])) { out.push(`+${al[j]}`); j++; }
    else if (i < bl.length) { out.push(`-${bl[i]}`); i++; }
  }
  return out.slice(0, 80);
}

function addFileChanges(changes) {
  if (!changes?.length) return;
  state.lastFileChanges = changes;
  document.getElementById("btnReview").disabled = false;
  const feed = document.getElementById("composerFeed");
  const explored = document.createElement("div");
  explored.className = "explored-line";
  explored.textContent = `Explored ${changes.length} file${changes.length > 1 ? "s" : ""}`;
  feed.appendChild(explored);

  const wrap = document.createElement("div");
  wrap.className = "file-changes";
  for (const ch of changes) {
    const pill = document.createElement("button");
    pill.type = "button";
    pill.className = "file-pill";
    pill.innerHTML = `<span class="fname">${escapeHtml(ch.path)}</span><span class="stats">${ch.deletions ? `<span class="del">-${ch.deletions}</span> ` : ""}${ch.additions ? `<span class="add">+${ch.additions}</span>` : ""}</span>`;
    const diffEl = document.createElement("div");
    diffEl.className = "diff-block";
    diffEl.innerHTML = renderDiffLines(ch.diff_lines?.length ? ch.diff_lines : buildDiffFromBeforeAfter(ch.before || "", ch.after || ""));
    pill.onclick = () => { diffEl.classList.toggle("open"); openFile(ch.path); };
    wrap.appendChild(pill);
    wrap.appendChild(diffEl);
  }
  feed.appendChild(wrap);
  scrollComposer();
  updateAgentResultsBar();
  renderAgentFilesList();
  updateActiveExecTab({ fileCount: changes.length });
}

function renderAgentFilesList() {
  const list = $("agentFilesList");
  if (!list) return;
  list.innerHTML = "";
  for (const ch of state.lastFileChanges) {
    const row = document.createElement("div");
    row.className = "agent-file-row";
    row.innerHTML = `<span>${escapeHtml(ch.path)}</span><span class="agent-file-stats">${ch.deletions ? `<span class="del">-${ch.deletions}</span> ` : ""}${ch.additions ? `<span class="add">+${ch.additions}</span>` : ""}</span>`;
    row.onclick = () => { openFile(ch.path); openReview(); };
    list.appendChild(row);
  }
}

function updateAgentResultsBar() {
  const bar = $("agentResultsBar");
  const n = state.lastFileChanges.length;
  if (!bar) return;
  if (n && !state.running) {
    bar.classList.remove("hidden");
    setText("agentFilesCount", `${n} File${n !== 1 ? "s" : ""}`);
    const review = $("btnReview");
    if (review) review.disabled = false;
  } else {
    bar.classList.add("hidden");
    $("agentFilesList")?.classList.add("hidden");
    const toggle = $("btnFilesToggle");
    if (toggle) toggle.setAttribute("aria-expanded", "false");
    const icon = $("filesToggleIcon");
    if (icon) icon.className = "codicon codicon-chevron-right";
  }
}

async function refreshAgentBgTerminals() {
  const wrap = $("agentBgTerminals");
  const list = $("agentBgTerminalList");
  if (!wrap || !list) return;
  try {
    const st = await api("/run/status");
    const jobs = st.jobs || [];
    const running = jobs.filter(j => j.running);
    if (state.running && jobs.length) {
      wrap.classList.remove("hidden");
      setText("bgTerminalCountLabel",
        `${running.length} running · ${jobs.length} terminal${jobs.length !== 1 ? "s" : ""}`);
    } else if (!state.running && !running.length) {
      wrap.classList.add("hidden");
    }
    list.innerHTML = "";
    for (const j of jobs) {
      let out = "";
      try {
        const o = await api(`/run/output/${encodeURIComponent(j.job_id)}`);
        out = o.output || "";
      } catch (_) {
        out = j.command || "";
      }
      const row = document.createElement("div");
      row.className = "bg-terminal-row" + (j.running ? " running" : "");
      row.innerHTML = `
        <div class="bg-term-cmd"><i class="codicon codicon-terminal"></i> ${escapeHtml(j.command || j.job_id)}</div>
        <pre class="bg-term-out">${escapeHtml(out.slice(-1200) || "(no output yet)")}</pre>`;
      list.appendChild(row);
    }
    if (state.running && jobs.length) {
      const term = $("terminalOutput");
      if (term) {
        const lines = jobs.map(j => `$ ${j.command}${j.running ? " (running)" : ""}`);
        term.textContent = lines.join("\n") + "\n\n" + (term.textContent || "").slice(-4000);
        term.scrollTop = term.scrollHeight;
      }
    }
  } catch (_) { /* ignore */ }
}

async function updateRunningMeta() {
  if (!state.running) return;
  const label = $("agentRunningLabel");
  if (!label) return;
  let text = "Agent is working…";
  try {
    const st = await api("/run/status");
    const bg = (st.jobs || []).filter(j => j.running).length;
    if (bg) text += ` · ${bg} background terminal${bg !== 1 ? "s" : ""}`;
  } catch (_) { /* ignore */ }
  label.textContent = text;
  await refreshAgentBgTerminals();
}

function setRunning(on) {
  state.running = on;
  const footer = $("auxFooter");
  const runningBar = $("agentRunningBar");
  const inputBox = $("chatInputBox");
  const resultsBar = $("agentResultsBar");
  const ta = $("followUp");
  const send = $("btnSend");

  footer?.classList.toggle("is-agent-running", on);

  if (on) {
    runningBar?.classList.remove("hidden");
    resultsBar?.classList.add("hidden");
    $("agentFilesList")?.classList.add("hidden");
    inputBox?.classList.add("hidden");
    if (ta) {
      ta.disabled = true;
      ta.setAttribute("readonly", "readonly");
      ta.blur();
    }
    if (send) send.disabled = true;
    $("btnStop")?.removeAttribute("disabled");
    setText("agentRunningLabel", "Agent is working…");
    updateRunningMeta();
    if (loadSettings().openTerminal !== false) openTerminalPanel();
    updateActiveExecTab({ running: true, title: "AION execution" });
    appendOutput("▶ Agent run started…", "terminal");
    if (state.runningMetaTimer) clearInterval(state.runningMetaTimer);
    state.runningMetaTimer = setInterval(updateRunningMeta, 1500);
    if (state.terminalPollTimer) clearInterval(state.terminalPollTimer);
    state.terminalPollTimer = setInterval(() => {
      if (state.running) refreshAgentBgTerminals();
    }, 1500);
    refreshAgentBgTerminals();
  } else {
    runningBar?.classList.add("hidden");
    inputBox?.classList.remove("hidden");
    if (ta) {
      ta.disabled = false;
      ta.removeAttribute("readonly");
    }
    if (send) send.disabled = false;
    $("btnStop")?.setAttribute("disabled", "disabled");
    if (state.runningMetaTimer) {
      clearInterval(state.runningMetaTimer);
      state.runningMetaTimer = null;
    }
    if (state.terminalPollTimer) {
      clearInterval(state.terminalPollTimer);
      state.terminalPollTimer = null;
    }
    refreshAgentBgTerminals();
    updateAgentResultsBar();
    updateActiveExecTab({ running: false, title: "AION execution" });
    if (!state.lastFileChanges.length) ta?.focus();
  }
  const review = $("btnReview");
  if (review) review.disabled = on || !state.lastFileChanges.length;
  updateAgentsHomeMode();
}

async function undoAllChanges() {
  if (!state.lastFileChanges.length || !state.workspaceRoot) return;
  if (!confirm(`Revert ${state.lastFileChanges.length} file(s) to before the agent run?`)) return;
  setStatus("Reverting agent changes…");
  try {
    for (const ch of state.lastFileChanges) {
      await api("/workspace/file", {
        method: "PUT",
        body: JSON.stringify({
          output_dir: state.workspaceRoot,
          path: ch.path,
          content: ch.before ?? "",
        }),
      });
    }
    await refreshFileTree(state.projectName);
    if (state.activeTab) await openFile(state.activeTab);
    state.lastFileChanges = [];
    updateAgentResultsBar();
    $("btnReview")?.setAttribute("disabled", "disabled");
    setStatus("Reverted all agent file changes");
    addAgentLine("undo", "All agent edits reverted");
  } catch (e) {
    setStatus(e.message);
  }
}

function updateChatPlaceholder() {
  const ta = $("followUp");
  if (!ta) return;
  if (state.agentRunMode === "ask") {
    ta.placeholder = "Ask a question — @files for context (no auto edits)";
  } else if (state.agentRunMode === "plan") {
    ta.placeholder = "Describe what to build — Agent will plan steps (no file writes)";
  } else if (state.agentRunMode === "debug") {
    ta.placeholder = "Describe the bug or paste errors — debug-focused help";
  } else if (state.taskMode === "edit") {
    ta.placeholder = "Ask Agent to edit — @path, drop files, images";
  } else if (state.taskMode === "create") {
    ta.placeholder = "Describe a new project to create";
  } else {
    ta.placeholder = "Ask Agent — @file, drop images, Auto picks create/edit";
  }
}

async function runModeChat(description, ctx, mode) {
  const { agentProject } = ctx;
  const contextFiles = [
    ...new Set([
      ...state.attached.map(a => a.path),
      ...(state.activeTab ? [state.activeTab] : []),
    ]),
  ];
  const prefixes = {
    ask: "",
    plan: "Plan mode: produce a clear step-by-step plan only. Do not write or change files.\n\n",
    debug: "Debug mode: analyze errors, root cause, and concrete fixes. Prefer minimal changes.\n\n",
  };
  const labels = { ask: "Ask", plan: "Plan", debug: "Debug" };
  const t0 = Date.now();
  setRunning(true);
  setText("agentRunningLabel", `${labels[mode]}…`);
  updateActiveExecTab({ running: true, title: `${labels[mode]}…` });
  setComposerStatus(`${labels[mode]} mode…`);
  setStatus(`${labels[mode]} mode — chat only, no file writes`);
  state.abortController = new AbortController();
  try {
    const data = await api("/ai/chat", {
      method: "POST",
      signal: state.abortController.signal,
      body: JSON.stringify({
        message: (prefixes[mode] || "") + buildAgentPrompt(description),
        output_dir: state.workspaceRoot,
        project: agentProject,
        active_file: state.activeTab || null,
        context_files: contextFiles,
      }),
    });
    addThought(Math.max(1, Math.round((Date.now() - t0) / 1000)));
    addAgentLine(mode, `${labels[mode]} (no files changed on disk)`, false);
    addSummaryMessage(data.reply || "(empty response)");
    setComposerStatus(labels[mode]);
    setStatus("Ready");
  } catch (e) {
    if (e.name === "AbortError") addAgentLine("Stopped", "Cancelled");
    else addAgentLine("Error", e.message, true);
  } finally {
    setRunning(false);
    state.abortController = null;
    state.attached = [];
    renderAttachChips();
    $("followUp")?.focus();
  }
}

async function runAskChat(description, ctx) {
  return runModeChat(description, ctx, "ask");
}

async function runPipeline(description) {
  if (!description.trim()) return;
  if (!state.workspaceRoot) { alert("Open a folder first (Ctrl+O)"); return pickFolder(); }

  syncProjectFromActiveFile();
  const displayPrompt = description.trim();
  const agentProject = inferProjectForAgent(displayPrompt);
  const attachSnapshot = state.attached.map(a => ({ ...a }));
  addUserMessage(displayPrompt, attachSnapshot);
  const title = $("composerTitle");
  if (title) title.textContent = displayPrompt.slice(0, 48) + (displayPrompt.length > 48 ? "…" : "");

  if (state.agentRunMode === "ask" || state.agentRunMode === "plan" || state.agentRunMode === "debug") {
    $("followUp").value = "";
    return runModeChat(description, { displayPrompt, agentProject, attachSnapshot }, state.agentRunMode);
  }

  const prompt = buildAgentPrompt(description);
  $("followUp").value = "";
  const t0 = Date.now();
  setRunning(true);
  const short = displayPrompt.slice(0, 48) + (displayPrompt.length > 48 ? "…" : "");
  setText("agentRunningLabel", displayPrompt.slice(0, 80) + (displayPrompt.length > 80 ? "…" : ""));
  updateActiveExecTab({ running: true, title: short || "AION execution" });
  setComposerStatus("Agent running…");
  setStatus(`Agent running (${state.taskMode} · Noesis + multi-file)…`);
  state.abortController = new AbortController();

  try {
    const task = await api("/tasks", {
      method: "POST",
      signal: state.abortController.signal,
      body: JSON.stringify({
        description: prompt,
        output_dir: state.workspaceRoot,
        project: agentProject,
        mode: state.taskMode || "auto",
        active_file: state.activeTab || null,
      }),
    });
    addThought(Math.max(1, Math.round((Date.now() - t0) / 1000)));
    if (task.mode) {
      const proj = task.project_name || agentProject || "project";
      addAgentLine(
        "intent",
        task.mode === "edit"
          ? `Editing folder "${proj}" (your open / @ files)`
          : `Creating new project "${proj}"`
      );
    }
    for (const r of task.results || []) {
      if (r.role === "summary") {
        addSummaryMessage(r.metadata?.explanation || r.summary);
        continue;
      }
      addAgentLine(r.role, r.summary, !r.success);
      if (r.role === "memory") document.getElementById("composerTitle").textContent = "Noesis memory";
      if (r.role === "coding" && r.metadata?.file_changes) addFileChanges(r.metadata.file_changes);
    }
    if (task.status === "success" && task.workspace_path) {
      addAgentLine(
        "project",
        `Saved to: ${task.workspace_path} (folder: ${task.project_name || "—"})`,
        false
      );
      if (task.project_name) {
        state.projectName = task.project_name;
        syncProjectFromActiveFile();
      }
    }
    setComposerStatus(`${state.fileCount} Files · ${task.status}`);
    setStatus(`${task.status}`);
    await refreshFileTree(task.project_name);
    state.attached = [];
    renderAttachChips();
    const preview =
      task.project_name
        ? `${task.project_name}/index.html`
        : state.activeTab;
    if (preview && task.status === "success") {
      await openFile(preview);
      switchActivityView("explorer");
    } else if (state.activeTab) await openFile(state.activeTab);
    await loadProjectList();
    updateTitlebar();
    appendTerminal(`Task ${task.status}: ${task.workspace_path || ""}`);
    loadStats();
  } catch (e) {
    if (e.name === "AbortError") addAgentLine("Stopped", "Cancelled");
    else addAgentLine("Error", e.message);
  } finally {
    setRunning(false);
    state.abortController = null;
    $("followUp")?.focus();
  }
}

function openReview() {
  if (!state.lastFileChanges.length) return;
  document.getElementById("reviewOverlay").classList.remove("hidden");
  const list = document.getElementById("reviewFileList");
  list.innerHTML = "";
  state.lastFileChanges.forEach((ch, idx) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "review-file-btn" + (idx === 0 ? " active" : "");
    btn.textContent = `${ch.path} (+${ch.additions || 0}-${ch.deletions || 0})`;
    btn.onclick = () => {
      list.querySelectorAll(".review-file-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      showReviewDiff(ch);
    };
    list.appendChild(btn);
  });
  showReviewDiff(state.lastFileChanges[0]);
}

function showReviewDiff(ch) {
  const host = document.getElementById("reviewDiffHost");
  host.innerHTML = "";
  if (!state.monacoReady) return;
  if (state.diffEditor) state.diffEditor.dispose();
  state.diffEditor = monaco.editor.createDiffEditor(host, {
    theme: "vs-dark", automaticLayout: true, readOnly: true, renderSideBySide: true,
    fontFamily: "Cascadia Code, Consolas, monospace", fontSize: 13,
  });
  state.diffEditor.setModel({
    original: monaco.editor.createModel(ch.before || "", langForPath(ch.path)),
    modified: monaco.editor.createModel(ch.after || "", langForPath(ch.path)),
  });
}

function closeReview() {
  document.getElementById("reviewOverlay").classList.add("hidden");
  if (state.diffEditor) { state.diffEditor.dispose(); state.diffEditor = null; }
}

function initFallbackEditor(reason) {
  const host = document.getElementById("monacoHost");
  const el = document.getElementById("codeFallback");
  if (!el) return;
  state.useFallback = true;
  state.monacoReady = true;
  if (host) host.style.display = "none";
  el.classList.remove("hidden");
  el.oninput = () => {
    if (!state.activeTab) return;
    state.tabContents[state.activeTab] = el.value;
    state.dirty.add(state.activeTab);
    renderTabs();
  };
  if (reason) setStatus(`Editor: ${reason}`);
  if (state.activeTab) void switchTab(state.activeTab);
  else updateHomeView();
  layoutEditor();
}

function initMonaco() {
  if (typeof require === "undefined") {
    initFallbackEditor("Monaco loader unavailable — using text editor");
    return;
  }
  const monacoTimeout = setTimeout(() => {
    if (!state.monacoReady) initFallbackEditor("Monaco load timeout — using text editor");
  }, 12000);
  require.config({ paths: { vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs" } });
  require(["vs/editor/editor.main"], () => {
    clearTimeout(monacoTimeout);
    if (state.useFallback) return;
    const host = document.getElementById("monacoHost");
    const box = document.querySelector(".editor-instance");
    if (!host || !box) {
      initFallbackEditor("Editor container missing");
      return;
    }
    host.style.display = "block";
    layoutEditor();
    monaco.editor.setTheme("vs-dark");
    state.editor = monaco.editor.create(host, {
      theme: "vs-dark",
      fontFamily: "Cascadia Code, Consolas, monospace",
      fontSize: 14,
      lineHeight: 21,
      minimap: { enabled: true },
      automaticLayout: false,
      scrollBeyondLastLine: false,
      padding: { top: 8 },
      bracketPairColorization: { enabled: true },
      tabSize: 4,
      wordWrap: "on",
      glyphMargin: true,
      lineNumbers: "on",
      renderWhitespace: "selection",
      renderValidationDecorations: "on",
      quickSuggestions: { other: true, comments: false, strings: true },
      suggestOnTriggerCharacters: true,
      wordBasedSuggestions: "currentDocument",
      parameterHints: { enabled: true },
      hover: { enabled: true, delay: 300 },
      links: true,
      colorDecorators: true,
      folding: true,
      matchBrackets: "always",
      autoClosingBrackets: "always",
      autoClosingQuotes: "always",
      formatOnPaste: true,
      formatOnType: false,
    });
    state.editor.onDidChangeCursorPosition(updateStatusBar);
    state.editor.onDidChangeModelContent(() => {
      if (state.activeTab) {
        state.tabContents[state.activeTab] = state.editor.getValue();
        state.dirty.add(state.activeTab);
        renderTabs();
        scheduleMarkerRefresh();
      }
    });
    registerMonacoProviders();
    state.monacoReady = true;
    const ro = new ResizeObserver(() => layoutEditor());
    const editorBox = document.querySelector(".editor-instance");
    if (editorBox) ro.observe(editorBox);
    if (state.activeTab) void switchTab(state.activeTab);
    else updateHomeView();
    layoutEditor();
  }, err => {
    clearTimeout(monacoTimeout);
    console.error("Monaco failed:", err);
    initFallbackEditor("Monaco failed — using text editor");
  });
}

function switchActivityView(view) {
  document.querySelectorAll(".view-tab[data-view]").forEach(b => {
    b.classList.toggle("active", b.dataset.view === view);
  });
  document.getElementById("sidebarExplorer").classList.toggle("hidden", view !== "explorer");
  document.getElementById("sidebarSearch").classList.toggle("hidden", view !== "search");
  document.getElementById("sidebarRun").classList.toggle("hidden", view !== "run");
  if (view === "search") document.getElementById("searchInput")?.focus();
}

document.querySelectorAll(".view-tab[data-view]").forEach(btn => {
  btn.onclick = () => switchActivityView(btn.dataset.view);
});

function loadSettings() {
  try {
    return JSON.parse(localStorage.getItem(LS_SETTINGS) || "{}");
  } catch {
    return {};
  }
}

function saveSettings(patch) {
  const s = { ...loadSettings(), ...patch };
  localStorage.setItem(LS_SETTINGS, JSON.stringify(s));
  return s;
}

function newExecId() {
  return `exec_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function loadExecArchive() {
  try {
    const raw = localStorage.getItem(LS_EXEC_ARCHIVE);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function persistExecArchive() {
  const entries = state.execSessions.map(s => ({
    id: s.id,
    title: s.title,
    running: !!s.running,
    createdAt: s.createdAt || Date.now(),
    updatedAt: s.updatedAt || s.createdAt || Date.now(),
    fileCount: s.fileCount || 0,
    taskMode: s.taskMode || "auto",
    workspacePath: s.workspacePath || state.workspaceRoot || "",
  }));
  const archive = loadExecArchive();
  const byId = new Map(archive.map(e => [e.id, e]));
  for (const e of entries) {
    const prev = byId.get(e.id) || {};
    byId.set(e.id, { ...prev, ...e, updatedAt: Date.now() });
  }
  const merged = [...byId.values()].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)).slice(0, 80);
  localStorage.setItem(LS_EXEC_ARCHIVE, JSON.stringify(merged));
}

function saveActiveSessionFeed() {
  const id = state.activeExecId;
  if (!id) return;
  const sess = state.execSessions.find(s => s.id === id);
  const feed = $("composerFeed");
  if (sess && feed) {
    sess.feedHtml = feed.innerHTML;
    sess.updatedAt = Date.now();
    sess.taskMode = state.taskMode;
    sess.workspacePath = state.workspaceRoot || sess.workspacePath || "";
  }
  persistExecArchive();
}

function restoreSessionFeed(sess) {
  const feed = $("composerFeed");
  if (!feed || !sess) return;
  feed.innerHTML = sess.feedHtml || "";
  scrollComposer();
  updateAgentsHomeMode();
}

function renderExecTabs() {
  const bar = $("execTabsBar");
  if (!bar) return;
  bar.innerHTML = "";
  for (const sess of state.execSessions) {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "exec-tab" + (sess.id === state.activeExecId ? " active" : "");
    tab.role = "tab";
    tab.dataset.id = sess.id;
    const spin = sess.running
      ? `<i class="codicon codicon-loading codicon-modifier-spin exec-tab-icon"></i>`
      : `<i class="codicon codicon-comment-discussion exec-tab-icon"></i>`;
    tab.innerHTML = `${spin}<span class="exec-tab-label">${escapeHtml(sess.title)}</span>
      <span class="exec-tab-close" role="button" title="Close"><i class="codicon codicon-close"></i></span>`;
    tab.onclick = e => {
      if (e.target.closest(".exec-tab-close")) {
        e.stopPropagation();
        closeExecSession(sess.id);
        return;
      }
      switchExecSession(sess.id);
    };
    bar.appendChild(tab);
  }
  renderAgentsSidebar();
  updateAgentsHomeMode();
}

function createExecSession(title = "New Agent") {
  saveActiveSessionFeed();
  const sess = {
    id: newExecId(),
    title,
    running: false,
    feedHtml: "",
    createdAt: Date.now(),
    updatedAt: Date.now(),
    fileCount: 0,
    taskMode: state.taskMode,
    workspacePath: state.workspaceRoot || "",
  };
  state.execSessions.push(sess);
  state.activeExecId = sess.id;
  restoreSessionFeed(sess);
  renderExecTabs();
  persistExecArchive();
  renderAgentsHistoryPanel();
  return sess;
}

function switchExecSession(id) {
  if (id === state.activeExecId) return;
  saveActiveSessionFeed();
  state.activeExecId = id;
  const sess = state.execSessions.find(s => s.id === id);
  restoreSessionFeed(sess);
  renderExecTabs();
  updateAuxMainVisibility();
  updateAgentsHomeMode();
  if (state.auxView === "history") renderAgentsHistoryPanel();
  if (!state.running && state.auxView === "chat") $("followUp")?.focus();
}

function closeExecSession(id) {
  if (state.execSessions.length <= 1) {
    const feed = $("composerFeed");
    if (feed) feed.innerHTML = "";
    const s = state.execSessions[0];
    if (s) {
      s.feedHtml = "";
      s.title = "AION execution";
      s.running = false;
    }
    renderExecTabs();
    updateAgentsHomeMode();
    return;
  }
  const idx = state.execSessions.findIndex(s => s.id === id);
  if (idx < 0) return;
  state.execSessions.splice(idx, 1);
  if (state.activeExecId === id) {
    const next = state.execSessions[Math.max(0, idx - 1)];
    state.activeExecId = next.id;
    restoreSessionFeed(next);
  }
  renderExecTabs();
  persistExecArchive();
  renderAgentsHistoryPanel();
  updateAgentsHomeMode();
}

function updateActiveExecTab(patch = {}) {
  const sess = state.execSessions.find(s => s.id === state.activeExecId);
  if (!sess) return;
  if (patch.title !== undefined) sess.title = patch.title;
  if (patch.running !== undefined) sess.running = patch.running;
  if (patch.fileCount !== undefined) sess.fileCount = patch.fileCount;
  sess.updatedAt = Date.now();
  renderExecTabs();
  persistExecArchive();
  if (state.auxView === "history") renderAgentsHistoryPanel();
}

function setAuxView(view) {
  state.auxView = view === "history" ? "history" : "chat";
  $("btnExecHistory")?.classList.toggle("active", state.auxView === "history");
  updateAuxMainVisibility();
  updateAgentsHomeMode();
  if (state.auxView === "history") renderAgentsHistoryPanel();
  else if (!state.running) $("followUp")?.focus();
}

function updateAuxMainVisibility() {
  const feed = $("composerFeed");
  const hist = $("agentsHistoryPanel");
  const banner = $("taskModeBanner");
  const hideChatForMode = state.taskMode !== "auto" && state.auxView === "chat";
  const showHistory = state.auxView === "history";

  feed?.classList.toggle("hidden", showHistory || hideChatForMode);
  hist?.classList.toggle("hidden", !showHistory);
  banner?.classList.toggle("hidden", showHistory || !hideChatForMode || state.taskMode === "auto");

  if (banner && hideChatForMode && !showHistory) {
    if (state.taskMode === "create") {
      banner.innerHTML = "<strong>Create mode</strong>Chat hidden — describe a new project in the box below. Agent will scaffold files on disk.";
    } else if (state.taskMode === "edit") {
      banner.innerHTML = "<strong>Edit mode</strong>Chat hidden — ask for changes to your open project. Use @file for context.";
    }
  }
  updateAgentsHomeMode();
}

const TASK_MODE_META = {
  auto: { label: "Auto", icon: "codicon-wand", hint: "Detect create vs edit from your message" },
  edit: { label: "Edit", icon: "codicon-edit", hint: "Always edit the open project folder" },
  create: { label: "Create", icon: "codicon-add", hint: "Always scaffold a new project" },
};

function updateTaskModeUI() {
  const m = TASK_MODE_META[state.taskMode] || TASK_MODE_META.auto;
  setText("taskModeLabel", m.label);
  const icon = $("taskModeIcon");
  if (icon) icon.className = `codicon ${m.icon}`;
}

function applyTaskMode(id) {
  if (!["auto", "edit", "create"].includes(id)) return;
  state.taskMode = id;
  localStorage.setItem(LS_TASK_MODE, id);
  updateTaskModeUI();
  updateChatPlaceholder();
  updateAuxMainVisibility();
  const sess = state.execSessions.find(s => s.id === state.activeExecId);
  if (sess) sess.taskMode = id;
  persistExecArchive();
  const menu = $("taskModeMenu");
  if (menu) {
    menu.querySelectorAll("button[data-mode]").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.mode === id);
    });
    const hint = menu.querySelector(".menu-hint");
    if (hint) hint.textContent = TASK_MODE_META[id]?.hint || "";
  }
}

function historyDayGroup(ts) {
  const d = new Date(ts);
  const now = new Date();
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startYesterday = startToday - 86400000;
  const t = d.getTime();
  if (t >= startToday) return "Today";
  if (t >= startYesterday) return "Yesterday";
  return "Older";
}

function getAllHistoryEntries() {
  const archive = loadExecArchive();
  const live = state.execSessions.map(s => ({
    id: s.id,
    title: s.title,
    running: !!s.running,
    createdAt: s.createdAt,
    updatedAt: s.updatedAt || s.createdAt,
    fileCount: s.fileCount || 0,
    taskMode: s.taskMode || "auto",
  }));
  const byId = new Map();
  for (const e of [...archive, ...live]) {
    const prev = byId.get(e.id);
    if (!prev || (e.updatedAt || 0) >= (prev.updatedAt || 0)) byId.set(e.id, e);
  }
  return [...byId.values()].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
}

function renderAgentsHistoryPanel() {
  const list = $("agentsHistoryList");
  if (!list) return;
  const q = (state.historySearch || $("agentsHistorySearch")?.value || "").trim().toLowerCase();
  let entries = getAllHistoryEntries();
  if (q) entries = entries.filter(e => (e.title || "").toLowerCase().includes(q));

  list.innerHTML = "";
  if (!entries.length) {
    list.innerHTML = `<p class="agents-history-empty">${q ? "No matching sessions." : "No agent sessions yet. Click New Agent or send a message."}</p>`;
    return;
  }

  const groups = new Map();
  for (const e of entries) {
    const g = historyDayGroup(e.updatedAt || e.createdAt);
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(e);
  }
  const order = ["Today", "Yesterday", "Older"];
  for (const gname of order) {
    const items = groups.get(gname);
    if (!items?.length) continue;
    const wrap = document.createElement("div");
    wrap.className = "agents-history-group";
    wrap.innerHTML = `<div class="agents-history-group-title">${escapeHtml(gname)}</div>`;
    for (const e of items) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "agents-history-item" + (e.id === state.activeExecId ? " active" : "");
      const files = e.fileCount ? ` · ${e.fileCount} File${e.fileCount !== 1 ? "s" : ""}` : "";
      const run = e.running ? " · running" : "";
      const mode = e.taskMode && e.taskMode !== "auto" ? ` · ${e.taskMode}` : "";
      btn.innerHTML = `<span class="agents-history-item-title">${escapeHtml(e.title || "Agent session")}</span>
        <span class="agents-history-item-meta">${new Date(e.updatedAt || e.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}${files}${mode}${run}</span>`;
      btn.onclick = () => {
        let sess = state.execSessions.find(s => s.id === e.id);
        if (!sess) {
          sess = {
            id: e.id,
            title: e.title || "Agent session",
            running: false,
            feedHtml: "",
            createdAt: e.createdAt || Date.now(),
            updatedAt: e.updatedAt,
            fileCount: e.fileCount || 0,
            taskMode: e.taskMode || "auto",
          };
          state.execSessions.push(sess);
          renderExecTabs();
        }
        switchExecSession(e.id);
        setAuxView("chat");
      };
      wrap.appendChild(btn);
    }
    list.appendChild(wrap);
  }
}

function initExecSessions() {
  if (state.execSessions.length) return;
  const archive = loadExecArchive();
  if (archive.length) {
    state.execSessions = archive.slice(0, 12).map(e => ({
      id: e.id,
      title: e.title || "Agent session",
      running: false,
      feedHtml: "",
      createdAt: e.createdAt || Date.now(),
      updatedAt: e.updatedAt || e.createdAt,
      fileCount: e.fileCount || 0,
      taskMode: e.taskMode || "auto",
      workspacePath: e.workspacePath || "",
    }));
    state.activeExecId = state.execSessions[0].id;
    restoreSessionFeed(state.execSessions[0]);
    renderExecTabs();
    return;
  }
  const sess = {
    id: newExecId(),
    title: "AION execution",
    running: false,
    feedHtml: $("composerFeed")?.innerHTML || "",
    createdAt: Date.now(),
    updatedAt: Date.now(),
    fileCount: 0,
    taskMode: state.taskMode,
  };
  state.execSessions = [sess];
  state.activeExecId = sess.id;
  renderExecTabs();
}

function toggleAuxiliaryVisible(forceOpen) {
  const panel = $("workbenchPanel");
  const bar = $("auxiliaryBar");
  const resizer = $("auxResizer");
  const hidden = forceOpen === true ? false : forceOpen === false ? true : !state.auxCollapsed;
  state.auxCollapsed = hidden;
  bar?.classList.toggle("collapsed", hidden);
  panel?.classList.toggle("aux-collapsed", hidden);
  resizer?.classList.toggle("hidden", hidden);
  const icon = document.querySelector("#btnToggleAux i");
  if (icon) {
    icon.className = hidden
      ? "codicon codicon-layout-sidebar-right-off"
      : "codicon codicon-layout-sidebar-right";
  }
  $("btnToggleAux")?.setAttribute("title", hidden ? "Show agent panel (Ctrl+J)" : "Hide agent panel (Ctrl+J)");
  if (!hidden) layoutEditor();
  updateAgentsHomeMode();
}

function isComposerFeedEmpty() {
  const feed = $("composerFeed");
  if (!feed) return true;
  return !feed.querySelector(".msg-user-wrap, .msg-agent, .msg-summary, .msg-thought");
}

function isAgentsPanelOpen() {
  const bar = $("auxiliaryBar");
  return bar && !bar.classList.contains("collapsed") && !state.auxCollapsed;
}

function updateAgentsWorkspaceLabel() {
  const label = $("agentsWorkspaceTriggerLabel");
  if (!label) return;
  label.textContent = state.workspaceRoot
    ? (state.workspaceRoot.split(/[/\\]/).pop() || "Project").toUpperCase()
    : "SELECT WORKSPACE";
}

function closeAgentsWorkspaceMenu() {
  state.agentsWorkspaceMenuOpen = false;
  $("agentsWorkspaceMenu")?.classList.add("hidden");
  $("agentsWorkspaceTrigger")?.setAttribute("aria-expanded", "false");
}

function toggleAgentsWorkspaceMenu(forceOpen) {
  const menu = $("agentsWorkspaceMenu");
  const trigger = $("agentsWorkspaceTrigger");
  if (!menu || !trigger) return;
  const open = forceOpen === undefined ? menu.classList.contains("hidden") : !!forceOpen;
  state.agentsWorkspaceMenuOpen = open;
  menu.classList.toggle("hidden", !open);
  trigger.setAttribute("aria-expanded", open ? "true" : "false");
  if (open) {
    renderAgentsWorkspaceMenu();
    $("agentsWorkspaceSearch")?.focus();
  }
}

function renderAgentsWorkspaceMenu() {
  const list = $("agentsWorkspaceRecents");
  if (!list) return;
  const q = ($("agentsWorkspaceSearch")?.value || state.agentsWorkspaceSearch || "").trim().toLowerCase();
  list.innerHTML = "";
  const paths = [];
  if (state.workspaceRoot) paths.push(state.workspaceRoot);
  for (const p of loadRecentProjects()) {
    if (p && !paths.includes(p)) paths.push(p);
  }
  let filtered = paths;
  if (q) {
    filtered = paths.filter(p =>
      p.toLowerCase().includes(q) || (p.split(/[/\\]/).pop() || "").toLowerCase().includes(q),
    );
  }
  if (!filtered.length) {
    const empty = document.createElement("p");
    empty.className = "agents-workspace-empty";
    empty.textContent = q ? "No matching workspaces" : "No recent workspaces";
    list.appendChild(empty);
  } else {
    for (const path of filtered.slice(0, 8)) {
      const name = path.split(/[/\\]/).pop() || path;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "agents-workspace-row" + (path === state.workspaceRoot ? " is-active" : "");
      btn.innerHTML = `<span class="agents-ws-path">${escapeHtml(path)}</span><i class="codicon codicon-check agents-ws-check"></i>`;
      btn.title = path;
      btn.onclick = () => {
        useAgentsWorkspace(path);
      };
      list.appendChild(btn);
    }
  }
  const runLocal = $("agentsRunOnLocal");
  const runCloud = $("agentsRunOnCloud");
  runLocal?.classList.toggle("is-active", state.agentsRunOn === "local");
  runCloud?.classList.toggle("is-active", state.agentsRunOn === "cloud");
}

/** Load a folder for agent create/edit (stays in Agents Window — does not open editor). */
async function useAgentsWorkspace(path) {
  if (!path?.trim()) return;
  closeAgentsWorkspaceMenu();
  try {
    await openPathOnServer(path.trim());
    const norm = path.trim();
    const name = norm.split(/[/\\]/).pop() || norm;
    for (const s of state.execSessions) {
      if (s.id === state.activeExecId) s.workspacePath = norm;
    }
    setStatus(`Workspace ready for agents — create or edit in ${name}`);
    updateAgentsWorkspaceLabel();
    renderAgentsWorkspaceMenu();
    renderAgentsSidebar();
    $("followUp")?.focus();
  } catch (e) {
    alert(e.message);
  }
}

async function agentsPickFolder() {
  closeAgentsWorkspaceMenu();
  try {
    const data = await api("/pick-folder");
    if (!data.cancelled && data.path) {
      await useAgentsWorkspace(data.path);
      return;
    }
    if (!data.cancelled) return;
  } catch {
    /* fall through */
  }
  const pasted = prompt("Folder path for agents to create or edit:");
  if (pasted?.trim()) await useAgentsWorkspace(pasted.trim());
}

function layoutAgentsHomeCompose(home) {
  const wrap = $("chatDropZone");
  const slot = $("agentsHomeCompose");
  const footer = $("auxFooter");
  if (!wrap || !footer) return;
  const inAgentsWindow = document.body.classList.contains("agents-only");
  if (home && inAgentsWindow && slot) {
    slot.appendChild(wrap);
  } else {
    const attach = $("attachChips");
    if (attach && attach.parentElement === footer) footer.insertBefore(wrap, attach);
    else footer.appendChild(wrap);
  }
  wrap.classList.remove("agents-home-moved-out");
}

function updateAgentsHomeMode() {
  const inAgentsWindow = document.body.classList.contains("agents-only");
  const home = inAgentsWindow
    && state.auxView === "chat"
    && isComposerFeedEmpty()
    && !state.running;
  document.body.classList.toggle("agents-home-mode", home);
  document.body.classList.toggle("agents-chat-mode", inAgentsWindow && state.auxView === "chat" && !home);
  const ta = $("followUp");
  if (ta) {
    if (home) ta.placeholder = "Plan, Build, / for commands, @ for context";
    else updateChatPlaceholder();
  }
  const sendIcon = $("btnSend")?.querySelector("i");
  if (sendIcon) {
    sendIcon.className = home ? "codicon codicon-mic" : "codicon codicon-arrow-up";
  }
  const homeView = $("agentsHomeView");
  const homeFooter = $("agentsHomeFooter");
  if (inAgentsWindow) {
    if (homeView) homeView.classList.toggle("hidden", !home);
    if (homeFooter) homeFooter.classList.toggle("hidden", !home);
    layoutAgentsHomeCompose(home);
  } else {
    if (homeView) homeView.classList.add("hidden");
    if (homeFooter) homeFooter.classList.add("hidden");
    layoutAgentsHomeCompose(false);
  }
  if (!home) closeAgentsWorkspaceMenu();
}

function initAgentsWorkspaceHub() {
  if (!$("agentsWorkspaceTrigger")) return;
  updateAgentsWorkspaceLabel();
  $("agentsWorkspaceTrigger")?.addEventListener("click", e => {
    e.stopPropagation();
    toggleAgentsWorkspaceMenu();
  });
  $("agentsWorkspaceSearch")?.addEventListener("input", e => {
    state.agentsWorkspaceSearch = e.target.value;
    renderAgentsWorkspaceMenu();
  });
  $("agentsRunOnLocal")?.addEventListener("click", () => {
    state.agentsRunOn = "local";
    renderAgentsWorkspaceMenu();
  });
  $("agentsRunOnCloud")?.addEventListener("click", () => setStatus("AION Cloud — coming soon"));
  $("agentsWsOpenFolder")?.addEventListener("click", () => agentsPickFolder());
  $("agentsWsConnectSsh")?.addEventListener("click", () => {
    closeAgentsWorkspaceMenu();
    landingConnectSsh();
  });
  document.addEventListener("click", e => {
    if (!state.agentsWorkspaceMenuOpen) return;
    if (e.target.closest(".agents-workspace-hub")) return;
    closeAgentsWorkspaceMenu();
  });
}

/** Open agents UI in the main IDE right panel (Cursor-style, wide). */
function openAgentsPanel() {
  if (document.body.classList.contains("agents-only")) return;
  const panel = $("workbenchPanel");
  const targetW = Math.max(520, Math.min(680, Math.round(window.innerWidth * 0.42)));
  if (panel) panel.style.setProperty("--aux-width", `${targetW}px`);
  toggleAuxiliaryVisible(true);
  setAuxView("chat");
  updateAgentsHomeMode();
  if (!state.execSessions.length) initExecSessions();
  renderAgentsSidebar();
  $("followUp")?.focus();
}

function getAgentsSidebarSessions() {
  let sessions = state.execSessions.length
    ? [...state.execSessions]
    : loadExecArchive().slice(0, 12).map(e => ({
        id: e.id,
        title: e.title || "AION execution",
        workspacePath: e.workspacePath || "",
        updatedAt: e.updatedAt || e.createdAt || 0,
      }));
  const q = (state.agentsSidebarSearch || "").trim().toLowerCase();
  if (q) {
    sessions = sessions.filter(s => (s.title || "AION execution").toLowerCase().includes(q));
  }
  if (state.agentsSidebarFilter === "workspace" && state.workspaceRoot) {
    sessions = sessions.filter(s => !s.workspacePath || s.workspacePath === state.workspaceRoot);
  }
  if (state.agentsSidebarFilter === "recent") {
    sessions = [...sessions]
      .sort((a, b) => (b.updatedAt || b.createdAt || 0) - (a.updatedAt || a.createdAt || 0))
      .slice(0, 8);
  }
  return sessions;
}

function renderAgentsSidebar() {
  const list = $("agentsSidebarList");
  if (!list || !document.body.classList.contains("agents-only")) return;
  list.innerHTML = "";
  const groupName = state.workspaceRoot
    ? (state.workspaceRoot.split(/[/\\]/).pop() || "Project").toUpperCase()
    : "RECENT";
  const wrap = document.createElement("div");
  wrap.className = "agents-sidebar-group";
  const titleEl = document.createElement("button");
  titleEl.type = "button";
  titleEl.className = "agents-sidebar-group-title agents-sidebar-group-title-btn";
  titleEl.textContent = groupName;
  if (state.workspaceRoot) {
    titleEl.title = `Use ${state.workspaceRoot} for agents`;
    titleEl.onclick = () => useAgentsWorkspace(state.workspaceRoot);
  }
  wrap.appendChild(titleEl);
  const sessions = getAgentsSidebarSessions();
  if (!sessions.length) {
    const empty = document.createElement("p");
    empty.className = "agents-sidebar-empty";
    empty.textContent = state.agentsSidebarSearch
      ? "No matching agents"
      : "No agents yet — click New Agent";
    wrap.appendChild(empty);
  } else {
    for (const sess of sessions) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "agents-sidebar-item" + (sess.id === state.activeExecId ? " active" : "");
      btn.textContent = sess.title || "AION execution";
      btn.title = sess.title || "";
      btn.onclick = () => {
        if (!state.execSessions.find(s => s.id === sess.id)) {
          createExecSession(sess.title || "New Agent");
        } else {
          switchExecSession(sess.id);
        }
        setAuxView("chat");
        updateAgentsHomeMode();
      };
      wrap.appendChild(btn);
    }
  }
  list.appendChild(wrap);
  const paths = [];
  if (state.workspaceRoot) paths.push(state.workspaceRoot);
  for (const p of loadRecentProjects()) {
    if (p && !paths.includes(p)) paths.push(p);
  }
  if (paths.length) {
    const g2 = document.createElement("div");
    g2.className = "agents-sidebar-group";
    g2.innerHTML = `<div class="agents-sidebar-group-title">WORKSPACES</div>`;
    for (const path of paths.slice(0, 6)) {
      const name = path.split(/[/\\]/).pop() || path;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "agents-sidebar-item agents-sidebar-workspace-item";
      btn.innerHTML = `<i class="codicon codicon-folder"></i><span>${escapeHtml(name)}</span>`;
      btn.title = `${path} — use for agents`;
      btn.onclick = () => useAgentsWorkspace(path);
      g2.appendChild(btn);
    }
    list.appendChild(g2);
  }
}

function openEditorWindow(workspacePath) {
  let url = `${location.origin}${location.pathname}`.replace(/\?.*$/, "");
  if (workspacePath) {
    const norm = workspacePath.trim();
    localStorage.setItem(LS_PENDING_WORKSPACE, norm);
    pushRecentProject(norm);
    url += `?workspace=${encodeURIComponent(norm)}`;
  }
  const win = window.open(url, "aion_editor");
  if (win) {
    try { win.focus(); } catch (_) { /* blocked */ }
  } else if (workspacePath) {
    alert("Allow popups to open the editor with this workspace.");
  }
}

function setAgentsSidebarFilter(mode) {
  state.agentsSidebarFilter = mode;
  $("agentsSidebarFilterBtn")?.classList.toggle("is-active", mode !== "all");
  renderAgentsSidebar();
}

function toggleAgentsSidebarSearch(forceOpen) {
  const wrap = $("agentsSidebarSearchWrap");
  if (!wrap) return;
  const open = forceOpen === undefined ? wrap.classList.contains("hidden") : !!forceOpen;
  wrap.classList.toggle("hidden", !open);
  $("agentsSidebarSearchBtn")?.classList.toggle("is-active", open);
  if (open) {
    $("agentsSidebarSearchInput")?.focus();
  } else {
    state.agentsSidebarSearch = "";
    const inp = $("agentsSidebarSearchInput");
    if (inp) inp.value = "";
    $("agentsSidebarSearchClear")?.classList.add("hidden");
    renderAgentsSidebar();
  }
}

function showAgentsFilterMenu(anchor) {
  const f = state.agentsSidebarFilter;
  showAuxDropdown(anchor, [
    { label: f === "all" ? "✓ All agents" : "All agents", run: () => setAgentsSidebarFilter("all") },
    { label: f === "workspace" ? "✓ This workspace" : "This workspace", run: () => setAgentsSidebarFilter("workspace"), disabled: !state.workspaceRoot },
    { label: f === "recent" ? "✓ Recent" : "Recent", run: () => setAgentsSidebarFilter("recent") },
  ]);
}

function initAgentsWindow() {
  if (!document.body.classList.contains("agents-only")) return;
  const panel = $("workbenchPanel");
  if (panel) {
    panel.style.removeProperty("--aux-width");
    panel.classList.remove("aux-collapsed", "sidebar-hidden");
  }
  $("auxiliaryBar")?.classList.remove("collapsed");
  state.auxCollapsed = false;
  $("agentsSidebar")?.classList.remove("hidden");
  $("titlebarAgentsWindow")?.classList.add("hidden");
  $("titlebarEditorWindow")?.classList.remove("hidden");
  const edBtn = $("titlebarEditorWindow");
  if (edBtn && !edBtn.dataset.aionBound) {
    edBtn.dataset.aionBound = "1";
    edBtn.addEventListener("click", () => {
      openEditorWindow(state.workspaceRoot || undefined);
    });
  }
  $("agentsSidebarNew")?.addEventListener("click", () => {
    createExecSession("New Agent");
    setAuxView("chat");
    const feed = $("composerFeed");
    if (feed) feed.innerHTML = "";
    updateAgentsHomeMode();
    $("followUp")?.focus();
  });
  $("agentsSidebarMarketplace")?.addEventListener("click", () => setStatus("Marketplace — coming soon"));
  $("agentsOpenWorkspace")?.addEventListener("click", () => {
    if (state.workspaceRoot) useAgentsWorkspace(state.workspaceRoot);
    else agentsPickFolder();
  });
  $("agentsSidebarSettings")?.addEventListener("click", openSettingsPanel);
  $("agentsSidebarSearchBtn")?.addEventListener("click", () => toggleAgentsSidebarSearch());
  $("agentsSidebarFilterBtn")?.addEventListener("click", e => {
    e.stopPropagation();
    showAgentsFilterMenu(e.currentTarget);
  });
  $("agentsSidebarSearchInput")?.addEventListener("input", e => {
    state.agentsSidebarSearch = e.target.value;
    $("agentsSidebarSearchClear")?.classList.toggle("hidden", !e.target.value.trim());
    renderAgentsSidebar();
  });
  $("agentsSidebarSearchClear")?.addEventListener("click", () => {
    const inp = $("agentsSidebarSearchInput");
    if (inp) inp.value = "";
    state.agentsSidebarSearch = "";
    $("agentsSidebarSearchClear")?.classList.add("hidden");
    renderAgentsSidebar();
    inp?.focus();
  });
  $("agentsPlanChip")?.addEventListener("click", () => {
    state.agentRunMode = "plan";
    localStorage.setItem(LS_AGENT_MODE, "plan");
    setText("agentModeLabel", "Plan");
    const icon = $("agentModeIcon");
    if (icon) icon.className = "codicon codicon-tasklist";
    updateChatPlaceholder();
    const ta = $("followUp");
    if (ta) {
      if (!ta.value.trim()) ta.value = "Plan a new idea: ";
      ta.focus();
      ta.setSelectionRange(ta.value.length, ta.value.length);
    }
  });
  document.addEventListener("keydown", e => {
    if (!document.body.classList.contains("agents-only")) return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "n") {
      e.preventDefault();
      $("agentsSidebarNew")?.click();
    }
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "f") {
      e.preventDefault();
      toggleAgentsSidebarSearch(true);
    }
    if (e.key === "Escape" && !$("agentsSidebarSearchWrap")?.classList.contains("hidden")) {
      e.preventDefault();
      toggleAgentsSidebarSearch(false);
    }
    if (e.key === "Escape" && state.agentsWorkspaceMenuOpen) {
      e.preventDefault();
      closeAgentsWorkspaceMenu();
    }
    if (e.key === "Tab" && document.body.classList.contains("agents-home-mode") && !e.shiftKey) {
      const active = document.activeElement;
      if (active?.id === "followUp" || active?.id === "agentsPlanChip") {
        e.preventDefault();
        $("agentsPlanChip")?.click();
      }
    }
  });
  renderAgentsSidebar();
  updateAgentsHomeMode();
  fitAgentsWindowSize();
  requestAnimationFrame(fitAgentsWindowSize);
  window.addEventListener("load", fitAgentsWindowSize);
}

function agentsWindowTargetSize() {
  const availW = window.screen.availWidth;
  const availH = window.screen.availHeight;
  const width = Math.min(1040, Math.max(880, Math.round(availW * 0.62)));
  const height = Math.min(820, Math.max(640, Math.round(availH * 0.68)));
  const left = Math.round(window.screen.availLeft + (availW - width) / 2);
  const top = Math.round(window.screen.availTop + (availH - height) / 2);
  return { width, height, left, top };
}

/** Snap Agents Window to Cursor-style floating size (~62% × 68% of screen). */
function fitAgentsWindowSize() {
  if (!document.body.classList.contains("agents-only")) return;
  const { width, height, left, top } = agentsWindowTargetSize();
  const dw = Math.abs(window.outerWidth - width);
  const dh = Math.abs(window.outerHeight - height);
  if (dw < 48 && dh < 48) return;
  try {
    window.moveTo(left, top);
    window.resizeTo(width, height);
  } catch (_) { /* blocked in some browsers */ }
}

function popoutAgentsWindow() {
  const url = `${location.origin}${location.pathname}?agents=1`;
  const { width, height, left, top } = agentsWindowTargetSize();
  const features = [
    `width=${width}`,
    `height=${height}`,
    `left=${left}`,
    `top=${top}`,
    "menubar=no",
    "toolbar=no",
    "location=no",
    "resizable=yes",
  ].join(",");
  const win = window.open(url, "aion_agents", features);
  if (!win) return;
  const applySize = () => {
    try {
      win.moveTo(left, top);
      win.resizeTo(width, height);
      win.focus();
    } catch (_) { /* blocked in some browsers */ }
  };
  applySize();
  win.addEventListener?.("load", applySize);
  setTimeout(applySize, 120);
  setTimeout(applySize, 400);
}

function showAuxDropdown(anchor, items) {
  const menu = $("auxDropdown");
  if (!menu || !anchor) return;
  menu.innerHTML = "";
  for (const it of items) {
    if (it.sep) {
      const sep = document.createElement("div");
      sep.className = "menu-sep";
      menu.appendChild(sep);
      continue;
    }
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = it.label;
    btn.onclick = () => {
      menu.classList.add("hidden");
      it.run?.();
    };
    menu.appendChild(btn);
  }
  const r = anchor.getBoundingClientRect();
  menu.style.left = `${Math.min(r.left, window.innerWidth - 220)}px`;
  menu.style.top = `${r.bottom + 4}px`;
  menu.classList.remove("hidden");
}

function hideAuxDropdown() {
  $("auxDropdown")?.classList.add("hidden");
  $("execHistoryMenu")?.classList.add("hidden");
}

function showExecHistoryMenu(anchor) {
  const menu = $("execHistoryMenu");
  if (!menu || !anchor) return;
  menu.innerHTML = "";
  const sorted = [...state.execSessions].sort((a, b) => b.createdAt - a.createdAt);
  if (!sorted.length) {
    const p = document.createElement("button");
    p.type = "button";
    p.textContent = "No sessions yet";
    p.disabled = true;
    menu.appendChild(p);
  } else {
    for (const s of sorted) {
      const btn = document.createElement("button");
      btn.type = "button";
      const when = new Date(s.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      btn.textContent = `${s.title} · ${when}${s.running ? " · running" : ""}`;
      btn.onclick = () => {
        menu.classList.add("hidden");
        switchExecSession(s.id);
      };
      menu.appendChild(btn);
    }
  }
  const r = anchor.getBoundingClientRect();
  menu.style.left = `${Math.min(r.right - 220, window.innerWidth - 240)}px`;
  menu.style.top = `${r.bottom + 4}px`;
  menu.classList.remove("hidden");
}

function openSettingsPanel() {
  const s = loadSettings();
  const overlay = $("settingsOverlay");
  if (!overlay) return;
  $("settingsAgentMode").value = s.defaultAgentMode || state.agentRunMode || "agent";
  $("settingsTaskMode").value = s.defaultTaskMode || state.taskMode || "auto";
  $("settingsOpenTerminal").checked = s.openTerminal !== false;
  $("settingsOpenOutput").checked = s.openOutput === true;
  overlay.classList.remove("hidden");
}

function closeSettingsPanel() {
  $("settingsOverlay")?.classList.add("hidden");
  const agent = $("settingsAgentMode")?.value;
  const task = $("settingsTaskMode")?.value;
  if (agent === "agent" || agent === "ask") {
    state.agentRunMode = agent;
    localStorage.setItem(LS_AGENT_MODE, agent);
  }
  if (task === "auto" || task === "edit" || task === "create") {
    state.taskMode = task;
    localStorage.setItem(LS_TASK_MODE, task);
  }
  saveSettings({
    defaultAgentMode: agent,
    defaultTaskMode: task,
    openTerminal: $("settingsOpenTerminal")?.checked !== false,
    openOutput: $("settingsOpenOutput")?.checked === true,
  });
  initChatModeDropdowns();
}

function initAuxChrome() {
  initExecSessions();
  $("btnPopoutAuxRail")?.addEventListener("click", popoutAgentsWindow);
  $("btnHistoryNewAgent")?.addEventListener("click", () => {
    createExecSession("New Agent");
    setAuxView("chat");
    $("followUp")?.focus();
  });
  $("agentsHistorySearch")?.addEventListener("input", e => {
    state.historySearch = e.target.value;
    renderAgentsHistoryPanel();
  });
  $("btnToggleAux")?.addEventListener("click", () => toggleAuxiliaryVisible());
  $("btnToggleAuxRail")?.addEventListener("click", () => toggleAuxiliaryVisible(true));
  $("btnNewExecTab")?.addEventListener("click", () => createExecSession("New Agent"));
  $("btnExecHistory")?.addEventListener("click", e => {
    e.stopPropagation();
    toggleAuxiliaryVisible(true);
    setAuxView(state.auxView === "history" ? "chat" : "history");
  });
  $("btnAuxTabMoreRight")?.addEventListener("click", e => {
    e.stopPropagation();
    showAuxDropdown(e.currentTarget, [
      { label: "Clear chat in this session", run: () => {
        const feed = $("composerFeed");
        if (feed) feed.innerHTML = "";
        saveActiveSessionFeed();
      }},
      { label: "Settings", run: () => openSettingsPanel() },
      { sep: true },
      { label: "Run Project (F5)", run: () => runProject() },
      { label: "Run current file", run: () => runCurrentFile() },
      { label: "Toggle Terminal", run: () => openTerminalPanel() },
      { label: "Toggle Sidebar (Ctrl+B)", run: () => toggleSidebarVisible() },
      { sep: true },
      { label: "Agents Window ↗", run: popoutAgentsWindow },
      { label: "Command Palette", run: () => openCommandPalette() },
    ]);
  });
  $("btnCloseSettings")?.addEventListener("click", closeSettingsPanel);
  $("settingsOverlay")?.addEventListener("click", e => {
    if (e.target.id === "settingsOverlay") closeSettingsPanel();
  });
  document.addEventListener("click", () => hideAuxDropdown());
}

function toggleSidebarVisible(forceOpen) {
  const slot = document.getElementById("sidebarSlot");
  const panel = document.getElementById("workbenchPanel");
  const hidden = forceOpen === true ? false : forceOpen === false ? true : !state.sidebarCollapsed;
  state.sidebarCollapsed = hidden;
  slot?.classList.toggle("collapsed", hidden);
  panel?.classList.toggle("sidebar-hidden", hidden);
  const icon = document.querySelector("#btnToggleSidebar i");
  if (icon) {
    icon.className = hidden ? "codicon codicon-layout-sidebar-left-off" : "codicon codicon-layout-sidebar-left";
  }
  const btn = $("btnToggleSidebar");
  if (btn) btn.title = hidden ? "Show Sidebar (Ctrl+B)" : "Hide Sidebar (Ctrl+B)";
  if (!hidden) layoutEditor();
}

function pushFileNav(path) {
  const norm = normalizePath(path);
  if (!norm || state.skipNavPush) return;
  if (state.fileNavIndex >= 0 && state.fileNavHistory[state.fileNavIndex] === norm) return;
  if (state.fileNavIndex < state.fileNavHistory.length - 1) {
    state.fileNavHistory = state.fileNavHistory.slice(0, state.fileNavIndex + 1);
  }
  state.fileNavHistory.push(norm);
  state.fileNavIndex = state.fileNavHistory.length - 1;
  updateNavButtons();
}

function updateNavButtons() {
  const back = $("btnNavBack");
  const fwd = $("btnNavForward");
  if (back) back.disabled = state.fileNavIndex <= 0;
  if (fwd) fwd.disabled = state.fileNavIndex >= state.fileNavHistory.length - 1;
}

async function navBack() {
  if (state.fileNavIndex <= 0) return;
  state.fileNavIndex--;
  state.skipNavPush = true;
  await openFile(state.fileNavHistory[state.fileNavIndex]);
  state.skipNavPush = false;
  updateNavButtons();
}

async function navForward() {
  if (state.fileNavIndex >= state.fileNavHistory.length - 1) return;
  state.fileNavIndex++;
  state.skipNavPush = true;
  await openFile(state.fileNavHistory[state.fileNavIndex]);
  state.skipNavPush = false;
  updateNavButtons();
}

function toggleBottomPanel(force) {
  const panel = document.getElementById("bottomPanel");
  state.bottomPanelOpen = force !== undefined ? force : !state.bottomPanelOpen;
  panel.classList.toggle("hidden", !state.bottomPanelOpen);
}

function openTerminalPanel() {
  toggleBottomPanel(true);
  showPanel("terminal");
  const input = document.getElementById("terminalInput");
  if (input) setTimeout(() => input.focus(), 50);
}

function appendTerminal(text) {
  const out = document.getElementById("terminalOutput");
  if (!out) return;
  out.textContent += text + (text.endsWith("\n") ? "" : "\n");
  out.scrollTop = out.scrollHeight;
}

async function runTerminalCommand(cmd) {
  const trimmed = (cmd || "").trim();
  if (!trimmed) return;
  if (!state.workspaceRoot) {
    alert("Open a folder first (Ctrl+O)");
    return;
  }
  openTerminalPanel();
  appendTerminal(`$ ${trimmed}`);
  try {
    const data = await api("/terminal/run", {
      method: "POST",
      body: JSON.stringify({
        output_dir: state.workspaceRoot,
        command: trimmed,
        cwd: state.projectPath || state.workspaceRoot,
      }),
    });
    appendTerminal(data.output || "(no output)");
    setStatus(`exit ${data.exit_code}`);
  } catch (e) {
    appendTerminal(e.message);
  }
}

async function runWorkspaceSearch(q) {
  if (!q.trim() || !state.workspaceRoot) return;
  const data = await api(
    `/workspace/search?q=${encodeURIComponent(q)}&output_dir=${encodeURIComponent(state.workspaceRoot)}${qs("project", state.projectName)}`
  );
  const box = document.getElementById("searchResults");
  box.innerHTML = "";
  if (!data.results?.length) {
    box.innerHTML = '<div class="tree-empty">No results</div>';
    return;
  }
  for (const hit of data.results) {
    const row = document.createElement("div");
    row.className = "search-hit";
    row.innerHTML = `<div class="path">${escapeHtml(hit.path)}:${hit.line}</div><div class="meta">${escapeHtml(hit.snippet || "")}</div>`;
    row.onclick = () => { switchActivityView("explorer"); openFile(hit.path); };
    box.appendChild(row);
  }
}

const PALETTE_COMMANDS = [
  { id: "openFolder", label: "File: Open Folder", keys: "Ctrl+O", run: pickFolder },
  { id: "save", label: "File: Save", keys: "Ctrl+S", run: saveActiveFile },
  { id: "run", label: "Run: Start (F5)", keys: "F5", run: () => runProject() },
  { id: "runFile", label: "Run: Current File", run: () => runCurrentFile() },
  { id: "stop", label: "Run: Stop", run: () => stopRun() },
  { id: "newFile", label: "File: New File", run: () => createNewFile() },
  { id: "palette", label: "View: Command Palette", keys: "Ctrl+Shift+P", run: () => openCommandPalette() },
  { id: "toggleSidebar", label: "View: Toggle Sidebar", keys: "Ctrl+B", run: () => toggleSidebarVisible() },
  { id: "toggleAux", label: "View: Toggle Agent Panel", keys: "Ctrl+J", run: () => toggleAuxiliaryVisible() },
  { id: "agentsWindow", label: "View: Agents Window", run: () => popoutAgentsWindow() },
  { id: "settings", label: "View: Settings", keys: "Ctrl+,", run: () => openSettingsPanel() },
  { id: "terminal", label: "View: Terminal", keys: "Ctrl+`", run: () => openTerminalPanel() },
  { id: "output", label: "View: Output", run: () => showPanel("output") },
  { id: "problems", label: "View: Problems", run: () => { showPanel("problems"); refreshDiagnostics(); } },
  { id: "chat", label: "Focus Agent Chat", keys: "Ctrl+L", run: () => { setAuxView("chat"); $("followUp")?.focus(); } },
  { id: "agentHistory", label: "View: Agent History", run: () => { toggleAuxiliaryVisible(true); setAuxView("history"); } },
  { id: "runAgent", label: "Agent: Run", keys: "Enter", run: () => runPipeline(document.getElementById("followUp").value) },
];

let paletteItems = [];
let paletteIndex = 0;
let menubarOpenId = null;

function runEditorAction(actionId) {
  if (state.editor && !state.useFallback) {
    const action = state.editor.getAction(actionId);
    if (action) { action.run(); return true; }
  }
  return false;
}

function closeMenubarMenu() {
  menubarOpenId = null;
  $("menubarMenu")?.classList.add("hidden");
  document.querySelectorAll(".menubar-item.is-open").forEach(b => b.classList.remove("is-open"));
}

function showMenubarMenu(menuId, anchor) {
  const menu = $("menubarMenu");
  const defs = MENUBAR_MENUS[menuId];
  if (!menu || !defs || !anchor) return;
  closeMenubarMenu();
  menubarOpenId = menuId;
  anchor.classList.add("is-open");
  menu.innerHTML = "";
  for (const item of defs) {
    if (item.sep) {
      const sep = document.createElement("div");
      sep.className = "menu-sep";
      menu.appendChild(sep);
      continue;
    }
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = item.label;
    if (item.keys) {
      const kbd = document.createElement("span");
      kbd.className = "menu-keys";
      kbd.textContent = item.keys;
      btn.appendChild(kbd);
    }
    if (item.disabled) btn.disabled = true;
    else btn.onclick = e => {
      e.stopPropagation();
      closeMenubarMenu();
      item.run?.();
    };
    menu.appendChild(btn);
  }
  menu.classList.remove("hidden");
  const r = anchor.getBoundingClientRect();
  menu.style.left = `${Math.max(4, r.left)}px`;
  menu.style.top = `${r.bottom + 2}px`;
}

const MENUBAR_MENUS = {
  file: [
    { label: "Open Folder…", keys: "Ctrl+O", run: pickFolder },
    { sep: true },
    { label: "Save", keys: "Ctrl+S", run: saveActiveFile },
    { sep: true },
    { label: "Close Folder", run: closeWorkspace },
    { label: "New Agents Window", run: popoutAgentsWindow },
    { sep: true },
    { label: "Exit", run: () => window.close() },
  ],
  edit: [
    { label: "Undo", keys: "Ctrl+Z", run: () => runEditorAction("undo") },
    { label: "Redo", keys: "Ctrl+Y", run: () => runEditorAction("redo") },
    { sep: true },
    { label: "Cut", keys: "Ctrl+X", run: () => runEditorAction("editor.action.clipboardCutAction") },
    { label: "Copy", keys: "Ctrl+C", run: () => runEditorAction("editor.action.clipboardCopyAction") },
    { label: "Paste", keys: "Ctrl+V", run: () => runEditorAction("editor.action.clipboardPasteAction") },
    { sep: true },
    { label: "Find", keys: "Ctrl+F", run: () => runEditorAction("actions.find") },
    { label: "Replace", keys: "Ctrl+H", run: () => runEditorAction("editor.action.startFindReplaceAction") },
  ],
  selection: [
    { label: "Select All", keys: "Ctrl+A", run: () => runEditorAction("editor.action.selectAll") },
    { label: "Add Cursor Above", keys: "Ctrl+Alt+↑", disabled: true },
    { label: "Add Cursor Below", keys: "Ctrl+Alt+↓", disabled: true },
  ],
  view: [
    { label: "Command Palette…", keys: "Ctrl+Shift+P", run: openCommandPalette },
    { sep: true },
    { label: "Explorer", keys: "Ctrl+Shift+E", run: () => switchActivityView("explorer") },
    { label: "Search", keys: "Ctrl+Shift+F", run: () => switchActivityView("search") },
    { label: "Run", keys: "Ctrl+Shift+D", run: () => switchActivityView("run") },
    { sep: true },
    { label: "Problems", keys: "Ctrl+Shift+M", run: () => { showPanel("problems"); refreshDiagnostics(); } },
    { label: "Output", keys: "Ctrl+Shift+U", run: () => showPanel("output") },
    { label: "Terminal", keys: "Ctrl+`", run: openTerminalPanel },
    { sep: true },
    { label: "Toggle Sidebar", keys: "Ctrl+B", run: () => toggleSidebarVisible() },
    { label: "Toggle Agent Panel", keys: "Ctrl+J", run: () => toggleAuxiliaryVisible() },
    { label: "Agents Window", run: popoutAgentsWindow },
    { sep: true },
    { label: "Settings", keys: "Ctrl+,", run: openSettingsPanel },
  ],
  go: [
    { label: "Back", keys: "Alt+←", run: navBack },
    { label: "Forward", keys: "Alt+→", run: navForward },
    { label: "Go to File…", keys: "Ctrl+P", run: openCommandPalette },
  ],
  run: [
    { label: "Run Project", keys: "F5", run: runProject },
    { label: "Run File", run: runCurrentFile },
    { sep: true },
    { label: "Stop", run: stopRun },
  ],
  terminal: [
    { label: "New Terminal", keys: "Ctrl+Shift+`", run: openTerminalPanel },
    { label: "Run Task…", keys: "Ctrl+Shift+B", run: runProject },
  ],
  help: [
    { label: "Show All Commands", keys: "Ctrl+Shift+P", run: openCommandPalette },
    { sep: true },
    { label: "Agent History", run: () => { toggleAuxiliaryVisible(true); setAuxView("history"); } },
    { label: "Focus Agent Chat", keys: "Ctrl+L", run: () => { setAuxView("chat"); $("followUp")?.focus(); } },
    { sep: true },
    { label: "About AION", run: () => alert("AION — multi-agent coding IDE") },
  ],
};

function initMenubar() {
  $("titlebarLogo")?.addEventListener("click", goToLanding);
  const menubar = $("menubar");
  const menu = $("menubarMenu");
  if (!menubar || !menu) return;
  menubar.querySelectorAll(".menubar-item").forEach(btn => {
    btn.addEventListener("click", e => {
      e.stopPropagation();
      const id = btn.dataset.menu;
      if (menubarOpenId === id) closeMenubarMenu();
      else showMenubarMenu(id, btn);
    });
  });
  $("titlebarAgentsWindow")?.addEventListener("click", popoutAgentsWindow);
  document.addEventListener("click", e => {
    if (e.target.closest(".menubar-item") || e.target.closest("#menubarMenu")) return;
    closeMenubarMenu();
  });
  window.addEventListener("resize", closeMenubarMenu);
}

function openCommandPalette() {
  state.paletteOpen = true;
  const el = document.getElementById("commandPalette");
  el.classList.remove("hidden");
  const input = document.getElementById("paletteInput");
  input.value = "";
  renderPaletteResults("");
  input.focus();
}

function closeCommandPalette() {
  state.paletteOpen = false;
  document.getElementById("commandPalette").classList.add("hidden");
  paletteItems = [];
  paletteIndex = 0;
}

function runPaletteSelection() {
  const item = paletteItems[paletteIndex];
  if (!item) return;
  closeCommandPalette();
  item.run();
}

function renderPaletteResults(filter) {
  const box = document.getElementById("paletteResults");
  box.innerHTML = "";
  paletteItems = [];
  paletteIndex = 0;
  const f = filter.toLowerCase();
  const cmds = PALETTE_COMMANDS.filter(c => !f || c.label.toLowerCase().includes(f));
  const files = (state.allFiles || []).filter(p => !f || p.toLowerCase().includes(f)).slice(0, 12);

  for (const c of cmds) {
    const row = document.createElement("div");
    row.className = "palette-item";
    row.innerHTML = `<i class="codicon codicon-terminal"></i><span>${escapeHtml(c.label)}</span>${c.keys ? `<kbd>${c.keys}</kbd>` : ""}`;
    const idx = paletteItems.length;
    paletteItems.push({ run: () => c.run() });
    row.onclick = () => { paletteIndex = idx; runPaletteSelection(); };
    box.appendChild(row);
  }
  for (const p of files) {
    const row = document.createElement("div");
    row.className = "palette-item";
    row.innerHTML = `<i class="codicon codicon-file"></i><span>${escapeHtml(p)}</span>`;
    const idx = paletteItems.length;
    paletteItems.push({ run: () => openFile(p) });
    row.onclick = () => { paletteIndex = idx; runPaletteSelection(); };
    box.appendChild(row);
  }
  highlightPaletteRow();
}

function highlightPaletteRow() {
  document.querySelectorAll("#paletteResults .palette-item").forEach((row, i) => {
    row.classList.toggle("active", i === paletteIndex);
  });
}

function createNewFile(atPath = null) {
  showInlineCreate("file", atPath);
}

function createNewFolder(atPath = null) {
  showInlineCreate("folder", atPath);
}

function initResizers() {
  const panel = document.getElementById("workbenchPanel");
  const root = document.documentElement;
  const drag = (resizer, cssVar, min, max, horizontal) => {
    resizer.onmousedown = e => {
      e.preventDefault();
      const start = horizontal ? e.clientX : e.clientY;
      const startSize = parseInt(getComputedStyle(root).getPropertyValue(cssVar)) || (horizontal ? 260 : 420);
      const onMove = ev => {
        const delta = (horizontal ? ev.clientX : ev.clientY) - start;
        const next = Math.min(max, Math.max(min, startSize + (horizontal ? delta : -delta)));
        root.style.setProperty(cssVar, `${next}px`);
      };
      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    };
  };
  drag(document.getElementById("sidebarResizer"), "--sidebar-width", 180, 480, true);
  drag(document.getElementById("auxResizer"), "--aux-width", 280, 720, true);
  document.getElementById("panelResizer").onmousedown = e => {
    e.preventDefault();
    const start = e.clientY;
    const startH = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--panel-height")) || 200;
    const onMove = ev => {
      const h = Math.min(window.innerHeight * 0.5, Math.max(80, startH + (start - ev.clientY)));
      document.documentElement.style.setProperty("--panel-height", `${h}px`);
    };
    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  };
}

function buildMentionItems(query) {
  const q = (query || "").toLowerCase().trim();
  const items = [];
  const folders = new Set();
  for (const f of state.allFiles || []) {
    const norm = f.replace(/\\/g, "/");
    if (norm.includes("/")) folders.add(norm.split("/")[0]);
  }
  if (state.activeTab) {
    items.push({
      type: "file",
      path: state.activeTab,
      label: state.activeTab.split("/").pop(),
      sub: state.activeTab,
      icon: "codicon codicon-file",
      score: 0,
    });
  }
  for (const folder of [...folders].sort()) {
    if (q && !folder.toLowerCase().includes(q)) continue;
    items.push({
      type: "folder",
      path: folder,
      label: folder,
      sub: "Folder",
      icon: "codicon-folder",
      score: 1,
    });
  }
  for (const f of state.allFiles || []) {
    const norm = f.replace(/\\/g, "/");
    if (q && !norm.toLowerCase().includes(q)) continue;
    items.push({
      type: "file",
      path: norm,
      label: norm.split("/").pop(),
      sub: norm,
      icon: iconForFile(norm).replace(/^codicon-/, "codicon codicon-"),
      score: 2,
    });
  }
  const commands = [
    { type: "command", id: "terminal", label: "Terminal", sub: "Open panel", icon: "codicon-terminal", run: () => openTerminalPanel() },
    { type: "command", id: "run", label: "Run Project", sub: "F5", icon: "codicon-play", run: () => runProject() },
    { type: "command", id: "palette", label: "Command Palette", sub: "Ctrl+Shift+P", icon: "codicon-list-selection", run: () => openCommandPalette() },
    { type: "command", id: "open", label: "Open Folder", sub: "Ctrl+O", icon: "codicon-folder-opened", run: () => pickFolder() },
  ];
  for (const c of commands) {
    if (q && !c.label.toLowerCase().includes(q) && !c.id.includes(q)) continue;
    items.push({ ...c, path: c.id, score: 3 });
  }
  return items.slice(0, 12);
}

function renderMentionMenu(items) {
  const menu = $("mentionMenu");
  const ta = $("followUp");
  if (!menu || !ta) return;
  state.mentionItems = items;
  state.mentionIndex = 0;
  if (!items.length) {
    menu.classList.add("hidden");
    return;
  }
  menu.innerHTML = "";
  let lastSection = "";
  for (let i = 0; i < items.length; i++) {
    const it = items[i];
    const sec = it.type === "file" ? "Files" : it.type === "folder" ? "Folders" : "Commands";
    if (sec !== lastSection) {
      const h = document.createElement("div");
      h.className = "mention-section";
      h.textContent = sec;
      menu.appendChild(h);
      lastSection = sec;
    }
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "mention-item" + (i === 0 ? " active" : "");
    btn.dataset.index = String(i);
    const ic = it.icon.startsWith("codicon ") ? it.icon : `codicon codicon-${it.icon}`;
    btn.innerHTML = `<i class="${ic}"></i><span class="mention-label">${escapeHtml(it.label)}</span><span style="color:#666;font-size:11px;margin-left:auto">${escapeHtml(it.sub || "")}</span>`;
    btn.onclick = () => selectMentionItem(i);
    menu.appendChild(btn);
  }
  const rect = ta.getBoundingClientRect();
  menu.style.left = `${Math.min(rect.left, window.innerWidth - 280)}px`;
  menu.style.top = `${Math.max(8, rect.top - Math.min(280, items.length * 32 + 24))}px`;
  menu.classList.remove("hidden");
}

function highlightMentionIndex() {
  document.querySelectorAll("#mentionMenu .mention-item").forEach((el, i) => {
    el.classList.toggle("active", i === state.mentionIndex);
  });
}

async function selectMentionItem(index) {
  const it = state.mentionItems[index];
  const ta = $("followUp");
  const menu = $("mentionMenu");
  if (!it || !ta) return;
  const v = ta.value;
  const at = v.lastIndexOf("@");
  if (at < 0) return;
  if (it.type === "command") {
    ta.value = v.slice(0, at).trimEnd();
    menu?.classList.add("hidden");
    it.run?.();
    ta.focus();
    return;
  }
  const path = it.path;
  ta.value = `${v.slice(0, at)}@${path} `;
  menu?.classList.add("hidden");
  if (it.type === "file" && state.workspaceRoot) {
    try {
      const data = await api(
        `/workspace/file?path=${encodeURIComponent(path)}&output_dir=${encodeURIComponent(state.workspaceRoot)}`
      );
      addAttachment(path, data.content);
    } catch (_) {
      setStatus(`Could not attach ${path}`);
    }
  }
  ta.focus();
}

function initMentions() {
  const ta = $("followUp");
  const menu = $("mentionMenu");
  if (!ta || !menu) return;

  const refresh = () => {
    const v = ta.value;
    const at = v.lastIndexOf("@");
    if (at < 0) {
      menu.classList.add("hidden");
      return;
    }
    const tail = v.slice(at + 1);
    if (tail.includes(" ") || tail.includes("\n")) {
      menu.classList.add("hidden");
      return;
    }
    renderMentionMenu(buildMentionItems(tail));
  };

  ta.addEventListener("input", refresh);
  ta.addEventListener("click", refresh);

  ta.addEventListener("keydown", e => {
    if (menu.classList.contains("hidden")) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      state.mentionIndex = (state.mentionIndex + 1) % state.mentionItems.length;
      highlightMentionIndex();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      state.mentionIndex = (state.mentionIndex - 1 + state.mentionItems.length) % state.mentionItems.length;
      highlightMentionIndex();
    } else if (e.key === "Enter" && state.mentionItems.length) {
      e.preventDefault();
      void selectMentionItem(state.mentionIndex);
    } else if (e.key === "Escape") {
      menu.classList.add("hidden");
    }
  });

  document.addEventListener("click", e => {
    if (!menu.contains(e.target) && e.target !== ta) menu.classList.add("hidden");
  });
}

function closeChatDropdowns() {
  document.querySelectorAll(".chat-dropdown-menu").forEach(m => m.classList.add("hidden"));
  document.querySelectorAll(".mode-dropdown-wrap.is-open").forEach(w => w.classList.remove("is-open"));
}

function positionChatDropdown(menu, anchor) {
  if (!menu || !anchor) return;
  const r = anchor.getBoundingClientRect();
  menu.classList.remove("hidden");
  menu.style.left = `${Math.max(8, r.left)}px`;
  menu.style.bottom = `${window.innerHeight - r.top + 6}px`;
  menu.style.top = "auto";
  menu.style.minWidth = `${Math.max(200, r.width + 20)}px`;
}

function toggleChatDropdown(menu, anchor, wrap) {
  if (!menu || !anchor) return;
  const opening = menu.classList.contains("hidden");
  closeChatDropdowns();
  if (opening) {
    wrap?.classList.add("is-open");
    positionChatDropdown(menu, anchor);
  }
}

function buildDropdownItem(label, icon, active, onClick) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = active ? "active" : "";
  btn.innerHTML = `<i class="codicon ${icon}"></i><span>${escapeHtml(label)}</span><i class="codicon codicon-check menu-check"></i>`;
  btn.onclick = e => {
    e.stopPropagation();
    onClick();
    closeChatDropdowns();
  };
  return btn;
}

let chatDropdownsReady = false;

function initChatModeDropdowns() {
  const agentModes = [
    { id: "agent", label: "Agent", icon: "codicon-infinity" },
    { id: "plan", label: "Plan", icon: "codicon-tasklist" },
    { id: "debug", label: "Debug", icon: "codicon-bug" },
    { id: "ask", label: "Ask", icon: "codicon-comment" },
  ];
  const taskModes = [
    { id: "auto", ...TASK_MODE_META.auto },
    { id: "edit", ...TASK_MODE_META.edit },
    { id: "create", ...TASK_MODE_META.create },
  ];

  const savedAgent = localStorage.getItem(LS_AGENT_MODE);
  const savedTask = localStorage.getItem(LS_TASK_MODE);
  if (agentModes.some(m => m.id === savedAgent)) state.agentRunMode = savedAgent;
  if (["auto", "edit", "create"].includes(savedTask)) state.taskMode = savedTask;

  const agentMenu = $("agentModeMenu");
  const taskMenu = $("taskModeMenu");
  const btnAgent = $("btnAgentMode");
  const btnTask = $("btnTaskMode");
  if (!agentMenu || !taskMenu || !btnAgent || !btnTask) return;

  agentMenu.innerHTML = "";
  taskMenu.innerHTML = "";

  const applyAgentMode = id => {
    state.agentRunMode = id;
    localStorage.setItem(LS_AGENT_MODE, id);
    const m = agentModes.find(x => x.id === id);
    setText("agentModeLabel", m?.label || "Agent");
    const icon = $("agentModeIcon");
    if (icon) icon.className = `codicon ${m?.icon || "codicon-infinity"}`;
    updateChatPlaceholder();
    updateAuxMainVisibility();
    agentMenu.querySelectorAll("button[data-agent]").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.agent === id);
    });
  };

  agentMenu.classList.add("cursor-mode-menu");
  for (const m of agentModes) {
    const btn = buildDropdownItem(m.label, m.icon, state.agentRunMode === m.id, () => applyAgentMode(m.id));
    btn.dataset.agent = m.id;
    agentMenu.appendChild(btn);
  }

  for (const m of taskModes) {
    const btn = buildDropdownItem(m.label, m.icon, state.taskMode === m.id, () => {
      applyTaskMode(m.id);
      if (state.taskMode !== "auto") setAuxView("chat");
    });
    btn.dataset.mode = m.id;
    taskMenu.appendChild(btn);
  }
  taskMenu.classList.add("cursor-mode-menu");
  const taskHint = document.createElement("div");
  taskHint.className = "menu-hint";
  taskHint.textContent = taskModes.find(x => x.id === state.taskMode)?.hint || "";
  taskMenu.appendChild(taskHint);

  applyAgentMode(state.agentRunMode);
  applyTaskMode(state.taskMode);

  if (!chatDropdownsReady) {
    chatDropdownsReady = true;
    btnAgent.addEventListener("click", e => {
      e.preventDefault();
      e.stopPropagation();
      toggleChatDropdown(agentMenu, btnAgent, btnAgent.closest(".mode-dropdown-wrap"));
    });
    btnTask.addEventListener("click", e => {
      e.preventDefault();
      e.stopPropagation();
      toggleChatDropdown(taskMenu, btnTask, $("taskModeWrap"));
    });
    agentMenu.addEventListener("click", e => e.stopPropagation());
    taskMenu.addEventListener("click", e => e.stopPropagation());
    document.addEventListener("click", e => {
      if (e.target.closest(".mode-dropdown-wrap") || e.target.closest(".chat-dropdown-menu")) return;
      closeChatDropdowns();
    });
    window.addEventListener("resize", closeChatDropdowns);
    window.addEventListener("scroll", closeChatDropdowns, true);
  }
}

function initContextMenu() {
  const menu = document.getElementById("contextMenu");
  document.getElementById("fileTree").addEventListener("contextmenu", e => {
    const node = e.target.closest(".tree-node.file");
    if (!node) return;
    e.preventDefault();
    state.contextPath = node.dataset.path;
    menu.style.left = `${e.clientX}px`;
    menu.style.top = `${e.clientY}px`;
    menu.classList.remove("hidden");
  });
  document.addEventListener("click", () => menu.classList.add("hidden"));
  menu.querySelectorAll("button").forEach(btn => {
    btn.onclick = async () => {
      const a = btn.dataset.action;
      if (a === "newFile") {
        const p = state.contextPath || "";
        const slash = p.lastIndexOf("/");
        createNewFile(slash >= 0 ? p.slice(0, slash) : "");
      }
      if (a === "refresh") await refreshFileTree(state.projectName);
      if (a === "reveal" && state.contextPath) await openFile(state.contextPath);
      menu.classList.add("hidden");
    };
  });
}

document.getElementById("btnOpenFolder").onclick = pickFolder;
$("btnOpenPath")?.addEventListener("click", async () => {
  const p = document.getElementById("pathPaste")?.value?.trim();
  if (!p) return alert("Paste a folder path, e.g. V:\\Aion_IDE\\Aion\\workspace\\calculator");
  try { await openPathOnServer(p); } catch (e) { alert(e.message); }
});
document.getElementById("btnSave").onclick = saveActiveFile;
document.getElementById("btnRefreshTree").onclick = () => refreshFileTree();
document.getElementById("btnCollapseAll").onclick = () => {
  document.querySelectorAll("#fileTree .tree-node.folder + div").forEach(w => { w.style.display = "none"; });
  document.querySelectorAll("#fileTree .tree-node.folder .codicon-chevron").forEach(c => {
    c.className = "codicon codicon-chevron-right codicon-chevron";
  });
};
document.getElementById("btnNewFile").onclick = () => createNewFile("");
document.getElementById("btnNewFolder")?.addEventListener("click", () => createNewFolder(""));
document.getElementById("workspaceRootRow")?.addEventListener("click", e => {
  if (e.target.closest(".explorer-action, .tree-twistie")) return;
  state.createBasePath = "";
  document.querySelectorAll(".tree-node.folder.selected").forEach(n => n.classList.remove("selected"));
  if (state.workspaceRoot) {
    const sel = document.getElementById("projectSelect");
    if (sel) sel.value = "";
    state.projectName = "";
    refreshFileTree("");
  } else {
    pickFolder();
  }
});
document.getElementById("btnToggleSidebar")?.addEventListener("click", () => toggleSidebarVisible());
$("btnNavBack")?.addEventListener("click", () => navBack());
$("btnNavForward")?.addEventListener("click", () => navForward());
document.getElementById("btnRootTwistie")?.addEventListener("click", () => {
  const scroll = document.querySelector(".file-tree-scroll");
  const btn = document.getElementById("btnRootTwistie");
  if (!scroll || !btn) return;
  const open = scroll.style.display !== "none";
  scroll.style.display = open ? "none" : "block";
  btn.querySelector("i").className = open ? "codicon codicon-chevron-right" : "codicon codicon-chevron-down";
});
document.getElementById("btnToggleTerminal").onclick = () => {
  if (state.bottomPanelOpen && state.activePanel === "terminal") toggleBottomPanel(false);
  else openTerminalPanel();
};
document.getElementById("btnClosePanel").onclick = () => toggleBottomPanel(false);
document.getElementById("projectSelect").onchange = async e => {
  const v = e.target.value || "";
  state.projectName = v;
  state.treeScope = v ? "project" : "full";
  await refreshFileTree(v || "");
  updateTitlebar();
  await detectProject();
  await refreshDiagnostics();
};
document.getElementById("btnRunFile").onclick = () => runCurrentFile();
document.getElementById("btnRunProjectBar").onclick = () => runProject();
document.getElementById("btnRunProjectSide").onclick = () => runProject();
document.getElementById("btnRunFileSide").onclick = () => runCurrentFile();
document.getElementById("btnStopRun").onclick = () => stopRun();
$("statusErrors")?.addEventListener("click", () => { showPanel("problems"); refreshDiagnostics(); });
document.querySelectorAll(".panel-tab[data-panel]").forEach(tab => {
  tab.onclick = () => showPanel(tab.dataset.panel);
});
document.getElementById("searchInput").addEventListener("keydown", e => {
  if (e.key === "Enter") runWorkspaceSearch(e.target.value);
});
document.getElementById("searchInput").addEventListener("input", e => {
  if (e.target.value.length >= 2) runWorkspaceSearch(e.target.value);
});
document.getElementById("terminalInput").addEventListener("keydown", e => {
  if (e.key === "Enter") {
    runTerminalCommand(e.target.value);
    e.target.value = "";
  }
});
document.getElementById("paletteInput").addEventListener("input", e => renderPaletteResults(e.target.value));
document.getElementById("paletteInput").addEventListener("keydown", e => {
  if (e.key === "Escape") { closeCommandPalette(); return; }
  if (e.key === "Enter") { e.preventDefault(); runPaletteSelection(); return; }
  if (e.key === "ArrowDown") {
    e.preventDefault();
    paletteIndex = Math.min(paletteIndex + 1, paletteItems.length - 1);
    highlightPaletteRow();
    return;
  }
  if (e.key === "ArrowUp") {
    e.preventDefault();
    paletteIndex = Math.max(paletteIndex - 1, 0);
    highlightPaletteRow();
  }
});
$("statusWarnings")?.addEventListener("click", () => { showPanel("problems"); refreshDiagnostics(); });
$("btnAcceptAll")?.addEventListener("click", () => {
  closeReview();
  setStatus("Changes applied on disk");
});
document.getElementById("statusBranch").onclick = () => document.getElementById("projectSelect").focus();
document.getElementById("btnSend").onclick = () => runPipeline(document.getElementById("followUp").value);
document.getElementById("btnStop").onclick = () => state.abortController?.abort();
document.getElementById("btnReview").onclick = openReview;
document.getElementById("btnCloseReview").onclick = closeReview;
document.getElementById("followUp").addEventListener("keydown", e => {
  if (state.running) {
    e.preventDefault();
    return;
  }
  const menu = $("mentionMenu");
  if (menu && !menu.classList.contains("hidden") && state.mentionItems.length) {
    return;
  }
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    document.getElementById("btnSend").click();
  }
});
$("btnFilesToggle")?.addEventListener("click", () => {
  const list = $("agentFilesList");
  const btn = $("btnFilesToggle");
  if (!list || !btn) return;
  list.classList.toggle("hidden");
  const expanded = !list.classList.contains("hidden");
  btn.setAttribute("aria-expanded", expanded ? "true" : "false");
  const icon = $("filesToggleIcon");
  if (icon) icon.className = expanded ? "codicon codicon-chevron-down" : "codicon codicon-chevron-right";
  if (expanded) renderAgentFilesList();
});
$("btnUndoAll")?.addEventListener("click", () => undoAllChanges());
$("btnAttach")?.addEventListener("click", () => $("chatFileInput")?.click());
$("chatFileInput")?.addEventListener("change", async e => {
  const files = e.target.files;
  if (!files?.length) return;
  for (const file of files) await attachLocalFile(file);
  e.target.value = "";
  $("followUp")?.focus();
  setStatus(`Attached ${state.attached.length} file(s)`);
});
$("btnBgTerminalsToggle")?.addEventListener("click", () => {
  const list = $("agentBgTerminalList");
  const btn = $("btnBgTerminalsToggle");
  if (!list || !btn) return;
  list.classList.toggle("hidden");
  const open = !list.classList.contains("hidden");
  btn.setAttribute("aria-expanded", open ? "true" : "false");
  const chev = $("bgTermChevron");
  if (chev) chev.className = open ? "codicon codicon-chevron-down" : "codicon codicon-chevron-right";
  if (open) refreshAgentBgTerminals();
});

document.addEventListener("keydown", e => {
  if (state.paletteOpen && e.key === "Escape") { closeCommandPalette(); return; }
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "p") {
    e.preventDefault();
    openCommandPalette();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "e") {
    e.preventDefault();
    switchActivityView("explorer");
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "f") {
    e.preventDefault();
    switchActivityView("search");
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key === "`") {
    e.preventDefault();
    if (state.bottomPanelOpen && state.activePanel === "terminal") toggleBottomPanel(false);
    else openTerminalPanel();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && document.activeElement?.id === "followUp") {
    e.preventDefault();
    document.getElementById("btnSend").click();
  }
  if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); saveActiveFile(); }
  if ((e.ctrlKey || e.metaKey) && e.key === "o") { e.preventDefault(); pickFolder(); }
  if ((e.ctrlKey || e.metaKey) && e.key === "l") {
    e.preventDefault();
    toggleAuxiliaryVisible(true);
    setAuxView("chat");
    $("followUp")?.focus();
  }
  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === "b") {
    e.preventDefault();
    toggleSidebarVisible();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === "j") {
    e.preventDefault();
    toggleAuxiliaryVisible();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key === ",") {
    e.preventDefault();
    openSettingsPanel();
    return;
  }
  if (e.key === "F5") {
    e.preventDefault();
    runProject();
  }
});

function resolveDefaultWorkspace(saved, suggested) {
  if (!saved) return suggested;
  const s = saved.replace(/\//g, "\\").toLowerCase();
  if (s.endsWith("\\veera_new") || s.includes("\\workspace\\veera")) return suggested;
  return saved;
}

(async function boot() {
  if (new URLSearchParams(location.search).get("agents") === "1") {
    document.documentElement.classList.add("agents-only-root");
    document.body.classList.add("agents-only");
    document.title = "AION — Agents Window";
  }
  if (localStorage.getItem(LS_IDE_VERSION) !== "33") {
    localStorage.setItem(LS_IDE_VERSION, "33");
  }
  initDragDrop();
  initMenubar();
  initLandingPage();
  initAuxChrome();
  initAgentsWorkspaceHub();
  initResizers();
  initContextMenu();
  initMonaco();
  await loadStats();
  const paste = document.getElementById("pathPaste");
  if (paste && state.suggestedWorkspace) {
    paste.placeholder = `Paste path: ${state.suggestedWorkspace}`;
  }
  const saved = localStorage.getItem(LS_WORKSPACE);
  const root = resolveDefaultWorkspace(saved, state.suggestedWorkspace);
  if (!document.body.classList.contains("agents-only")) {
    const params = new URLSearchParams(location.search);
    const wsParam = params.get("workspace");
    const pending = localStorage.getItem(LS_PENDING_WORKSPACE);
    const openPath = wsParam ? decodeURIComponent(wsParam) : pending;
    if (openPath) {
      localStorage.removeItem(LS_PENDING_WORKSPACE);
      try { await openPathOnServer(openPath); } catch (e) { alert(e.message); }
    } else if (root) {
      try { await setWorkspace(root); } catch { localStorage.removeItem(LS_WORKSPACE); }
    }
  }
  if (document.body.classList.contains("agents-only")) {
    showLanding(false);
    if (root) {
      try { await setWorkspace(root); } catch { /* sidebar may show without folder */ }
    }
    initAgentsWindow();
    toggleAuxiliaryVisible(true);
    if (!state.execSessions.length) initExecSessions();
    setAuxView("chat");
    updateAgentsHomeMode();
    fitAgentsWindowSize();
    setTimeout(fitAgentsWindowSize, 200);
  } else {
    updateHomeView();
    if (!state.execSessions.length) initExecSessions();
    toggleAuxiliaryVisible(true);
    setAuxView("chat");
    layoutAgentsHomeCompose(false);
    updateAgentsHomeMode();
  }
  await refreshDiagnostics();
  switchActivityView("explorer");
  initMentions();
  const bootSettings = loadSettings();
  if (["agent", "plan", "debug", "ask"].includes(bootSettings.defaultAgentMode)) {
    state.agentRunMode = bootSettings.defaultAgentMode;
    localStorage.setItem(LS_AGENT_MODE, bootSettings.defaultAgentMode);
  }
  if (["auto", "edit", "create"].includes(bootSettings.defaultTaskMode)) {
    state.taskMode = bootSettings.defaultTaskMode;
    localStorage.setItem(LS_TASK_MODE, bootSettings.defaultTaskMode);
  }
  initChatModeDropdowns();
  setAuxView("chat");
  updateAuxMainVisibility();
  state.runPollTimer = setInterval(pollRunJobs, 2000);
  document.addEventListener("click", e => {
    if (!state.paletteOpen) return;
    const pal = document.getElementById("commandPalette");
    if (pal && !pal.contains(e.target)) closeCommandPalette();
  });
  setStatus("Ready — Ctrl+Shift+P · Ctrl+B sidebar · Ctrl+J agent panel");
  window.AION = {
    state,
    api,
    openFile,
    setWorkspace,
    runPipeline,
    refreshDiagnostics,
    layoutEditor,
  };
})();
