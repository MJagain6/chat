const $ = (id) => document.getElementById(id);

const nodes = {
  serviceChip: $("service-chip"),
  metricService: $("metric-service"),
  metricPort: $("metric-port"),
  metricModels: $("metric-models"),
  metricAuths: $("metric-auths"),
  healthHint: $("health-hint"),
  output: $("ops-output"),
  accounts: $("accounts-grid"),
  models: $("models-grid"),
  localConfig: $("local-config"),
  activeConfig: $("active-config"),
  logs: $("logs-box"),
  authFiles: $("auth-files"),
  authReplace: $("auth-replace"),
  toast: $("toast"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  if (!response.ok) {
    const message = payload.error || payload.message || `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  return payload;
}

function setOutput(text) {
  nodes.output.textContent = text || "";
}

function showToast(message, isError = false) {
  nodes.toast.textContent = message;
  nodes.toast.style.borderColor = isError ? "rgba(255,94,94,0.66)" : "rgba(97,224,200,0.55)";
  nodes.toast.classList.add("show");
  setTimeout(() => nodes.toast.classList.remove("show"), 2100);
}

function classifyServiceChip(health) {
  const serviceState = String(health?.service?.status || "").toLowerCase();
  const listening = Boolean(health?.listening);
  const hasModels = Number(health?.models?.count || 0) > 0;
  const serviceReady = ["started", "running", "active"].includes(serviceState);
  if (serviceReady && listening && hasModels) {
    return { text: "ONLINE", className: "status-chip ok" };
  }
  if (serviceReady) {
    return { text: "DEGRADED", className: "status-chip warn" };
  }
  return { text: "OFFLINE", className: "status-chip bad" };
}

function renderHealth(health) {
  const serviceState = health?.service?.status || "unknown";
  const listening = health?.listening ? "YES" : "NO";
  const modelCount = Number(health?.models?.count || 0);
  const authCount = Number(health?.accounts?.count || 0);
  const checkedAt = health?.now ? new Date(health.now).toLocaleString() : "-";
  nodes.metricService.textContent = serviceState;
  nodes.metricPort.textContent = listening;
  nodes.metricModels.textContent = String(modelCount);
  nodes.metricAuths.textContent = String(authCount);
  nodes.healthHint.textContent = `最近检查：${checkedAt}`;
  const chip = classifyServiceChip(health);
  nodes.serviceChip.textContent = chip.text;
  nodes.serviceChip.className = chip.className;
}

function tokenPill(label, ok) {
  const cls = ok ? "token-pill ok" : "token-pill no";
  return `<span class="${cls}">${label}:${ok ? "Y" : "N"}</span>`;
}

function renderAccounts(payload) {
  const accounts = Array.isArray(payload?.accounts) ? payload.accounts : [];
  if (!accounts.length) {
    nodes.accounts.innerHTML = `<div class="account-card">未发现账号。</div>`;
    return;
  }
  nodes.accounts.innerHTML = accounts
    .map((acc) => {
      if (acc.error) {
        return `
          <article class="account-card">
            <div class="account-top">
              <div>
                <div class="account-file">${acc.label || "unknown"}</div>
                <div class="account-mail">读取失败</div>
              </div>
            </div>
            <div class="account-meta"><div>${acc.error}</div></div>
          </article>
        `;
      }
      return `
        <article class="account-card">
          <div class="account-top">
            <div>
              <div class="account-file">${acc.label || "-"}</div>
              <div class="account-mail">${acc.source || "-"}</div>
            </div>
            <div class="account-file">status: ${acc.last_status ?? "-"}</div>
          </div>
          <div class="account-meta">
            <div>account: ${acc.account_id || "-"}</div>
            <div>refresh: ${acc.last_refresh || "-"}</div>
            <div>failures: ${acc.failures || 0}</div>
            <div>cooldown: ${acc.cooldown_remaining || 0}s</div>
          </div>
          ${tokenPill("access", Boolean(acc.has_access_token))}
          ${tokenPill("refresh", Boolean(acc.has_refresh_token))}
          ${tokenPill("id", Boolean(acc.has_id_token))}
        </article>
      `;
    })
    .join("");
}

function renderModels(payload) {
  const ids = Array.isArray(payload?.ids) ? payload.ids : [];
  if (!ids.length) {
    nodes.models.innerHTML = `<span class="model-chip">暂无模型数据</span>`;
    return;
  }
  nodes.models.innerHTML = ids.map((id) => `<span class="model-chip">${id}</span>`).join("");
}

function renderConfig(payload) {
  nodes.localConfig.textContent = payload?.localConfig || "读取失败";
  nodes.activeConfig.textContent = payload?.activeConfig || "读取失败";
}

function renderLogs(payload) {
  nodes.logs.textContent = payload?.text || "读取失败";
}

async function refreshHealth() {
  const health = await api("/api/health");
  renderHealth(health);
  if (health?.models?.error) {
    setOutput(`模型检查失败: ${health.models.error}`);
  }
}

async function refreshAccounts() {
  const payload = await api("/api/accounts");
  renderAccounts(payload);
}

async function refreshModels() {
  const payload = await api("/api/models");
  renderModels(payload);
}

async function refreshConfig() {
  const payload = await api("/api/config");
  renderConfig(payload);
}

async function refreshLogs() {
  const payload = await api("/api/logs?lines=180");
  renderLogs(payload);
}

async function refreshAll() {
  const tasks = [refreshHealth(), refreshAccounts(), refreshModels(), refreshConfig(), refreshLogs()];
  const results = await Promise.allSettled(tasks);
  const rejected = results.filter((item) => item.status === "rejected");
  if (rejected.length) {
    const message = rejected[0]?.reason?.message || "部分刷新失败";
    showToast(message, true);
  }
}

async function runSync() {
  try {
    const payload = await api("/api/actions/sync", { method: "POST" });
    setOutput((payload.stdout || "").trim() || "sync done");
    if (payload.health) {
      renderHealth(payload.health);
    }
    await refreshAccounts();
    showToast("账号同步完成");
  } catch (error) {
    setOutput(String(error.message || error));
    showToast("同步失败", true);
  }
}

async function runServiceAction(action) {
  try {
    const payload = await api("/api/actions/service", {
      method: "POST",
      body: JSON.stringify({ action }),
    });
    const report = [`[service ${action}]`, String(payload.stdout || "").trim(), String(payload.stderr || "").trim()]
      .filter(Boolean)
      .join("\n");
    setOutput(report || `${action} done`);
    if (payload.health) {
      renderHealth(payload.health);
    }
    await refreshModels();
    showToast(`服务操作完成: ${action}`);
  } catch (error) {
    setOutput(String(error.message || error));
    showToast(`服务操作失败: ${action}`, true);
  }
}

async function uploadAuthFiles() {
  const fileInput = nodes.authFiles;
  if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
    showToast("Please select one or more auth.json files", true);
    return;
  }

  const formData = new FormData();
  Array.from(fileInput.files).forEach((file) => formData.append("files", file));
  formData.append("replace", nodes.authReplace?.checked ? "1" : "0");

  try {
    const response = await fetch("/api/actions/upload_auths", {
      method: "POST",
      body: formData,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = payload.error || payload.message || `${response.status} ${response.statusText}`;
      throw new Error(message);
    }

    const lines = [
      `[upload] uploaded=${payload.uploaded || 0}`,
      ...(Array.isArray(payload.written) ? payload.written : []),
      ...(Array.isArray(payload.errors) && payload.errors.length ? ["errors:", ...payload.errors] : []),
    ];
    setOutput(lines.join("\n"));
    fileInput.value = "";
    await refreshAll();
    showToast("Credentials uploaded");
  } catch (error) {
    setOutput(String(error.message || error));
    showToast("Upload failed", true);
  }
}

function bindActions() {
  $("btn-refresh").addEventListener("click", async () => {
    await refreshAll();
    showToast("刷新完成");
  });
  $("btn-sync").addEventListener("click", runSync);
  $("btn-restart").addEventListener("click", () => runServiceAction("restart"));
  $("btn-start").addEventListener("click", () => runServiceAction("start"));
  $("btn-stop").addEventListener("click", () => runServiceAction("stop"));
  $("btn-models").addEventListener("click", refreshModels);
  $("btn-logs").addEventListener("click", refreshLogs);
  $("btn-config").addEventListener("click", refreshConfig);
  const uploadBtn = $("btn-upload-auth");
  if (uploadBtn) {
    uploadBtn.addEventListener("click", uploadAuthFiles);
  }
}

bindActions();
refreshAll();
setInterval(refreshHealth, 15000);
