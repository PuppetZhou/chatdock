"use strict";
const $ = (id) => document.getElementById(id);
const words = {
  workspaces: ["工作空间", "Workspaces"],
  local: ["本地会话 · 数据留在本机", "Local sessions · Private by default"],
  sessions: ["会话中心", "Session hub"],
  subtitle: [
    "找到上下文，继续你的工作。",
    "Find your context. Pick up where you left off.",
  ],
  refresh: ["刷新", "Refresh"],
  total: ["全部会话", "Sessions"],
  live: ["活动后端", "Live backends"],
  memory: ["后端内存 · RSS", "Backend memory · RSS"],
  spaces: ["工作目录", "Workspaces"],
  all: ["全部状态", "All states"],
  active: ["有后台进程", "Has backend"],
  history: ["历史 / 未关联", "History / Unlinked"],
  detail: ["会话详情", "Session details"],
  footnote: [
    "资源按 PID 统计 · 持锁不代表正在生成",
    "Resources per PID · Locked does not mean generating",
  ],
  theme: ["配色", "Theme"],
  font: ["字体", "Font"],
  edit: ["名称与标签", "Name & tags"],
  name: ["会话名称", "Session name"],
  tags: ["标签（逗号分隔）", "Tags (comma separated)"],
  cancel: ["取消", "Cancel"],
  save: ["保存", "Save"],
  stop: ["关闭后端", "Stop backend"],
  impact: [
    "将向整个进程发送 SIGTERM，影响以下会话及同进程的其他任务。",
    "Send SIGTERM to the entire backend, affecting these sessions and other tasks in the same process.",
  ],
  allspaces: ["全部工作空间", "All workspaces"],
  allagents: ["所有 Agent", "All Agents"],
  allclients: ["所有客户端", "All clients"],
  search: ["搜索会话、路径或标签", "Search sessions, paths or tags"],
  foldersearch: ["筛选目录", "Filter workspaces"],
  empty: ["没有匹配的会话", "No matching sessions"],
  pick: ["选择会话查看详情", "Select a session to inspect"],
  threads: ["线程", "Threads"],
  path: ["工作目录", "Working directory"],
  id: ["会话 ID", "Session ID"],
  client: ["客户端", "Client"],
  status: ["后台状态", "Backend state"],
  unknown: ["未知", "Unknown"],
  locked: ["持锁", "Locked"],
  process: ["进程", "Process"],
  shared: [
    "同 PID 共享资源，不是单条会话独占。",
    "Resources are shared by all sessions on this PID.",
  ],
  copy: ["复制 ID", "Copy ID"],
  copied: ["已复制", "Copied"],
  rename: [
    "名称同步到 Codex；标签仅保存在 ChatDock。",
    "Names sync to Codex; tags stay in ChatDock.",
  ],
  readonly: [
    "该 Agent 暂不支持原生重命名，可编辑标签。",
    "Native rename is unavailable for this Agent; tags are editable.",
  ],
  pid: ["输入 PID 确认：", "Type the PID to confirm: "],
  updated: ["已更新", "Updated"],
  saved: ["已保存", "Saved"],
  sent: ["已发送终止请求", "Termination requested"],
  fontnote: [
    "字体需已在本机安装，否则使用系统字体。",
    "Fonts must be installed locally; otherwise the system font is used.",
  ],
};
const readPref = (key, fallback) => {
  try {
    return localStorage.getItem("chatdock-" + key) || fallback;
  } catch {
    return fallback;
  }
};
let language = readPref("language", "zh"),
  rows = [],
  selected = null,
  directory = "",
  busy = false,
  plan = null,
  editing = null;
const t = (key) => (words[key] || [key, key])[language === "en" ? 1 : 0];
const node = (tag, text, cls) => {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
};
let token = new URLSearchParams(location.hash.slice(1)).get("token");
try {
  if (token) sessionStorage.setItem("chatdock-token", token);
  else token = sessionStorage.getItem("chatdock-token");
} catch {}
if (location.hash) history.replaceState(null, "", location.pathname);
async function api(path, body) {
  const response = await fetch("/api/" + path, {
    method: body ? "POST" : "GET",
    headers: {
      Authorization: "Bearer " + (token || ""),
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const result = await response.json();
  if (!response.ok) throw Error(result.error || response.statusText);
  return result;
}
const mib = (value) =>
  value == null
    ? "—"
    : value >= 1024 ** 3
      ? (value / 1024 ** 3).toFixed(2) + " GiB"
      : (value / 1024 ** 2).toFixed(1) + " MiB";
const status = (r) =>
  r.lock === "持有写锁" ? t("locked") : r.pid ? t("process") : t("history");
function translated(value) {
  if (language !== "en") return value;
  return (
    {
      "VS Code 插件": "VS Code extension",
      "Cursor 插件": "Cursor extension",
      "终端 CLI": "Terminal CLI",
      "Desktop 后端": "Desktop backend",
      历史记录: "History",
      "CLI/后台进程": "CLI / Background",
      前端未知: "Frontend unknown",
      "后端存活；前端未知": "Backend alive; frontend unknown",
      无写锁: "No write lock",
      运行关联未知: "Process association unknown",
      进程存活: "Process alive",
    }[value] || value
  );
}
function options(id, values, label) {
  const old = $(id).value;
  $(id).replaceChildren(
    new Option(label, ""),
    ...values.map((v) => new Option(translated(v), v)),
  );
  if (values.includes(old)) $(id).value = old;
}
function renderFolders() {
  const counts = new Map();
  for (const r of rows)
    if (r.cwd) counts.set(r.cwd, (counts.get(r.cwd) || 0) + 1);
  const fragment = document.createDocumentFragment();
  const add = (path, count) => {
    const b = node(
      "button",
      undefined,
      "folder" + (directory === path ? " selected" : ""),
    );
    const span = node(
      "span",
      path ? path.split("/").filter(Boolean).pop() : t("allspaces"),
    );
    if (path) span.append(node("small", path));
    b.append(span, node("b", String(count)));
    b.title = path || t("allspaces");
    b.setAttribute("aria-pressed", String(directory === path));
    b.onclick = () => {
      directory = path;
      renderFolders();
      renderList();
    };
    fragment.append(b);
  };
  add("", rows.length);
  const q = $("folder-search").value.toLowerCase();
  [...counts]
    .sort(([a], [b]) => a.localeCompare(b))
    .filter(([path]) => path.toLowerCase().includes(q))
    .forEach(([path, count]) => add(path, count));
  $("folders").replaceChildren(fragment);
}
function matching() {
  const q = $("search").value.trim().toLowerCase();
  return rows.filter(
    (r) =>
      (!directory ||
        r.cwd === directory ||
        r.cwd?.startsWith(directory.replace(/\/$/, "") + "/")) &&
      (!$("agent").value || r.agent === $("agent").value) &&
      (!$("client").value || r.source === $("client").value) &&
      (!$("state").value || Boolean(r.pid) === ($("state").value === "live")) &&
      [r.title, r.id, r.cwd, r.agent, r.source, ...r.tags]
        .join(" ")
        .toLowerCase()
        .includes(q),
  );
}
function renderList() {
  const visible = matching();
  if (!visible.some((r) => r.key === selected))
    selected = visible[0]?.key || null;
  $("scope").textContent = directory || t("allspaces");
  $("count").textContent = String(visible.length);
  const fragment = document.createDocumentFragment();
  for (const r of visible) {
    const b = node(
      "button",
      undefined,
      "session" + (r.key === selected ? " selected" : ""),
    );
    b.setAttribute("aria-pressed", String(r.key === selected));
    b.append(
      node(
        "span",
        r.agent === "Codex" ? "CX" : r.agent.slice(0, 2).toUpperCase(),
        "agent-icon",
      ),
    );
    const info = node("div");
    info.append(
      node("h3", r.title || r.id),
      node("p", r.agent + " · " + translated(r.source)),
      node("p", r.cwd || t("unknown")),
    );
    for (const tag of r.tags) info.append(node("span", tag, "badge"));
    const res = node("div", undefined, "resource");
    res.append(
      node("div", status(r), "state"),
      node("div", mib(r.rss_bytes)),
      node("div", (r.threads ?? "—") + " " + t("threads")),
    );
    b.append(info, res);
    b.onclick = () => {
      selected = r.key;
      renderList();
    };
    fragment.append(b);
  }
  if (!visible.length) fragment.append(node("div", t("empty"), "empty"));
  const scroll = $("sessions").scrollTop;
  $("sessions").replaceChildren(fragment);
  $("sessions").scrollTop = scroll;
  renderDetail();
}
function renderDetail() {
  const root = $("detail");
  root.replaceChildren();
  const r = rows.find((r) => r.key === selected);
  if (!r) {
    root.append(node("p", t("pick"), "muted"));
    return;
  }
  root.append(
    node("div", r.agent + " / " + status(r), "detail-agent"),
    node("h2", r.title || r.id),
  );
  const metrics = node("div", undefined, "metrics");
  for (const [value, label] of [
    [mib(r.rss_bytes), "RSS"],
    [r.threads ?? "—", t("threads")],
  ]) {
    const box = node("div", String(value));
    box.append(node("small", label));
    metrics.append(box);
  }
  root.append(metrics, node("p", t("shared"), "muted"));
  const dl = node("dl");
  for (const [label, value] of [
    [t("path"), r.cwd || t("unknown")],
    [t("id"), r.id],
    [t("client"), translated(r.source)],
    ["PID", r.pid || "—"],
    [t("status"), translated(r.status)],
    [
      language === "en" ? "Known sessions on PID" : "同 PID 已知记录",
      r.pid ? rows.filter((x) => x.pid === r.pid).length : "—",
    ],
  ])
    dl.append(node("dt", label), node("dd", String(value)));
  root.append(dl);
  const edit = node("button", t("edit"), "primary");
  edit.onclick = () => openEditor(r);
  const copy = node("button", t("copy"));
  copy.onclick = async () => {
    try {
      await navigator.clipboard.writeText(r.id);
      copy.textContent = t("copied");
    } catch {
      showError(
        language === "en"
          ? "Select and copy the ID above."
          : "请选中上方 ID 手动复制。",
      );
    }
  };
  const close = node("button", t("stop"), "danger");
  close.disabled = !r.pid;
  close.onclick = () => openClose(r);
  root.append(edit, copy, close);
}
function showError(error) {
  $("status").textContent = error.message || String(error);
  $("status").classList.add("error");
}
async function refresh() {
  if (busy || $("editor").open || $("confirm").open) return;
  busy = true;
  $("refresh").disabled = true;
  try {
    const data = await api("sessions");
    rows = data.rows;
    const pids = new Map(rows.filter((r) => r.pid).map((r) => [r.pid, r]));
    $("total").textContent = rows.length;
    $("live").textContent = pids.size;
    const known = [...pids.values()].filter((r) => r.rss_bytes != null);
    $("memory").textContent = known.length
      ? mib(known.reduce((sum, r) => sum + r.rss_bytes, 0))
      : "—";
    $("spaces").textContent = new Set(
      rows.map((r) => r.cwd).filter(Boolean),
    ).size;
    options(
      "agent",
      [...new Set(rows.map((r) => r.agent))].sort(),
      t("allagents"),
    );
    options(
      "client",
      [...new Set(rows.map((r) => r.source))].sort(),
      t("allclients"),
    );
    renderFolders();
    renderList();
    $("status").classList.remove("error");
    $("status").textContent = data.warnings.length
      ? data.warnings.join(" · ")
      : t("updated") + " " + new Date().toLocaleTimeString();
  } catch (error) {
    showError(error);
  } finally {
    busy = false;
    $("refresh").disabled = false;
  }
}
function openEditor(r) {
  editing = r;
  $("edit-name").value = r.title || "";
  $("edit-name").disabled = !r.can_rename;
  $("edit-tags").value = r.tags.join(", ");
  $("rename-note").textContent = t(r.can_rename ? "rename" : "readonly");
  $("edit-error").textContent = "";
  $("editor").showModal();
}
$("edit-form").onsubmit = async (event) => {
  event.preventDefault();
  $("edit-save").disabled = true;
  try {
    await api("edit", {
      key: editing.key,
      name: $("edit-name").value,
      tags: $("edit-tags")
        .value.split(/[,，]/)
        .map((s) => s.trim())
        .filter(Boolean),
    });
    $("editor").close();
    await refresh();
  } catch (error) {
    $("edit-error").textContent = error.message;
  } finally {
    $("edit-save").disabled = false;
  }
};
async function openClose(r) {
  try {
    plan = await api("close-plan", { key: r.key });
    $("affected").replaceChildren(
      ...plan.affected.map((x) => node("li", (x.title || x.id) + " · " + x.id)),
    );
    $("pid-label").textContent = t("pid") + plan.pid;
    $("confirm-pid").value = "";
    $("close-error").textContent = "";
    $("confirm").showModal();
  } catch (error) {
    showError(error);
  }
}
$("close-form").onsubmit = async (event) => {
  event.preventDefault();
  if ($("confirm-pid").value !== String(plan.pid)) {
    $("close-error").textContent = t("pid") + plan.pid;
    return;
  }
  $("close-submit").disabled = true;
  try {
    await api("close", { plan: plan.plan, pid: $("confirm-pid").value });
    $("confirm").close();
    await refresh();
    $("status").textContent = t("sent");
  } catch (error) {
    $("close-error").textContent = error.message;
  } finally {
    $("close-submit").disabled = false;
  }
};
$("edit-cancel").onclick = () => $("editor").close();
$("close-cancel").onclick = () => $("confirm").close();
for (const id of ["search", "agent", "client", "state"])
  $(id).addEventListener("input", renderList);
$("folder-search").oninput = renderFolders;
$("refresh").onclick = refresh;
function setLanguage() {
  document.documentElement.lang = language === "en" ? "en" : "zh-CN";
  document
    .querySelectorAll("[data-i]")
    .forEach((n) => (n.textContent = t(n.dataset.i)));
  $("search").placeholder = t("search");
  $("folder-search").placeholder = t("foldersearch");
  $("font").title = t("fontnote");
  options(
    "agent",
    [...new Set(rows.map((r) => r.agent))].sort(),
    t("allagents"),
  );
  options(
    "client",
    [...new Set(rows.map((r) => r.source))].sort(),
    t("allclients"),
  );
  renderFolders();
  renderList();
}
for (const id of ["theme", "font", "language"]) {
  const fallback = { theme: "dark", font: "system", language: "zh" }[id];
  const value = readPref(id, fallback);
  $(id).value = [...$(id).options].some((o) => o.value === value)
    ? value
    : fallback;
  if (id !== "language") document.documentElement.dataset[id] = $(id).value;
  $(id).onchange = () => {
    try {
      localStorage.setItem("chatdock-" + id, $(id).value);
    } catch {}
    if (id === "language") {
      language = $(id).value;
      setLanguage();
    } else document.documentElement.dataset[id] = $(id).value;
  };
}
language = $("language").value;
setLanguage();
refresh();
setInterval(() => {
  if (!document.hidden) refresh();
}, 5000);
