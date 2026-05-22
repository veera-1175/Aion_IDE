const API = "";

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

let network = null;

const GRAPH_OPTIONS = {
  physics: {
    enabled: true,
    stabilization: { iterations: 100, fit: true },
    barnesHut: {
      gravitationalConstant: -3000,
      springLength: 120,
      avoidOverlap: 0.2,
    },
  },
  interaction: { hover: true, zoomView: true, dragView: true },
  nodes: {
    font: { color: "#e6edf3", size: 13, face: "Segoe UI" },
    shape: "dot",
    size: 16,
    borderWidth: 2,
  },
  edges: {
    font: { color: "#8b949e", size: 10, align: "middle" },
    smooth: { type: "continuous" },
  },
  layout: { improvedLayout: true },
};

async function loadStats() {
  const s = await api("/stats");
  document.getElementById("statsBar").innerHTML = `
    <span>Memories: <strong>${s.total_memories}</strong></span>
    <span>Graph: <strong>${s.graph_nodes}</strong> nodes / <strong>${s.graph_edges}</strong> edges</span>
    <span>Compression: <strong>${s.estimated_compression_ratio}x</strong></span>
    <span>Agent: <strong>${s.agent_id}</strong></span>
  `;
}

async function loadMemories() {
  const list = await api("/memories?limit=30");
  const el = document.getElementById("memoriesList");
  el.innerHTML = list.map(m => `
    <div class="memory-card">
      <span class="cat ${m.category}">${m.category}</span>
      <span class="imp">imp ${m.importance.toFixed(2)}</span>
      <div>${escapeHtml(m.summary)}</div>
      <div class="imp">${m.concepts.slice(0, 4).join(" · ")}</div>
    </div>
  `).join("") || "<p class='hint'>No memories yet. Use the chat.</p>";
}

function buildGraphData(data, center = null) {
  const rawNodes = data.nodes || [];
  const nodeList = rawNodes.length && typeof rawNodes[0] === "object"
    ? rawNodes
    : rawNodes.map(id => ({ id, label: id }));

  const nodes = new vis.DataSet(
    nodeList.map(n => ({
      id: n.id || n.label || n,
      label: n.label || n.id || String(n),
      color: (n.id || n) === center ? "#a371f7" : "#58a6ff",
    }))
  );

  const edges = new vis.DataSet(
    (data.edges || []).map(e => ({
      from: e.from || e.source,
      to: e.to || e.target,
      label: e.relation || "",
      arrows: "to",
      color: { color: "#484f58" },
    }))
  );

  return { nodes, edges };
}

async function loadGraph(center = null) {
  const data = center
    ? await api(`/graph/${encodeURIComponent(center)}`)
    : await api("/graph");

  const container = document.getElementById("graphNetwork");
  const { nodes, edges } = buildGraphData(data, center);

  if (network) {
    network.destroy();
    network = null;
  }

  if (nodes.length === 0) {
    container.innerHTML = "<p class='hint graph-empty'>No graph nodes yet. Add memories via chat.</p>";
    return;
  }

  container.innerHTML = "";
  network = new vis.Network(container, { nodes, edges }, GRAPH_OPTIONS);
  network.once("stabilizationIterationsDone", () => network.fit({ animation: true }));
  network.setOptions({ physics: { enabled: true } });
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function addMessage(text, type) {
  const el = document.getElementById("chatMessages");
  const div = document.createElement("div");
  div.className = `msg ${type}`;
  div.textContent = text;
  el.appendChild(div);
  el.scrollTop = el.scrollHeight;
}

document.getElementById("chatForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("chatInput");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  addMessage(text, "user");

  try {
    const chat = await api("/chat", {
      method: "POST",
      body: JSON.stringify({ query: text, limit: 5, mode: "hybrid" }),
    });

    if (chat.stored) {
      addMessage(`Stored: ${chat.stored.summary}`, "system");
    }
    addMessage(`Recalled ${chat.recalled} related memories.`, "system");

    if (chat.memory_context && chat.memory_context !== "No prior memory.") {
      addMessage("Recall:\n" + chat.memory_context.replace(/^- /gm, "• "), "recall");
    } else if (!chat.stored) {
      addMessage("Could not store (low importance). Try a longer message.", "system");
    }

    await loadStats();
    await loadMemories();
    await loadGraph();
  } catch (err) {
    addMessage("Error: " + err.message, "system");
  }
});

document.getElementById("btnRefresh").addEventListener("click", () => loadGraph());
document.getElementById("btnExplore").addEventListener("click", () => {
  const c = document.getElementById("conceptSearch").value.trim();
  if (c) loadGraph(c);
});

document.getElementById("btnForget").addEventListener("click", async () => {
  const r = await api("/forget", { method: "POST" });
  showOutput(r);
  await loadStats();
  await loadMemories();
  await loadGraph();
});

document.getElementById("btnCompare").addEventListener("click", async () => {
  const r = await api("/compare", {
    method: "POST",
    body: JSON.stringify({
      texts: [
        "User asked about Redis caching",
        "User asked about async workers",
        "User asked about FastAPI scaling",
        "User deployed Redis in production",
        "User struggled with worker bottlenecks",
      ],
    }),
  });
  showOutput(r);
  await loadMemories();
  await loadGraph();
});

function showOutput(obj) {
  const box = document.getElementById("outputBox");
  box.textContent = JSON.stringify(obj, null, 2);
  box.classList.add("visible");
}

loadStats();
loadMemories();
loadGraph();
