/**
 * BioDB Console — 统一管理界面逻辑
 * 复用 bio_util/common.js（Util：readJwt/readData/exportData/features/drawSeriesWithEvents）
 * 所有 API 经 nginx 同源代理（/auth、/sensor、/event）。
 */
"use strict";

const App = {
  cfg: {},
  experimentsCache: [],

  /* ---------- 基础工具 ---------- */
  loadCfg() {
    try { this.cfg = JSON.parse(localStorage.getItem("biodb_console_cfg") || "{}"); }
    catch (e) { this.cfg = {}; }
  },
  saveCfg() {
    localStorage.setItem("biodb_console_cfg", JSON.stringify(this.cfg));
    const ok = !!(this.cfg.user_id && this.cfg.token);
    const el = document.getElementById("conn");
    el.textContent = ok ? "已配置：" + this.cfg.user_id : "未配置凭据";
    el.className = "conn " + (ok ? "ok" : "err");
  },
  status(msg, type = "info") {
    const el = document.getElementById("status");
    el.className = "status " + type;
    el.textContent = msg;
    clearTimeout(this._st);
    this._st = setTimeout(() => (el.textContent = ""), 6000);
  },
  $(id) { return document.getElementById(id); },
  val(id) { return (this.$(id).value || "").trim(); },
  /** 本地时间(datetime-local) → UTC ISO */
  toUtc(v) { return v ? new Date(v).toISOString() : ""; },
  fmtLocal(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return isNaN(d) ? String(iso) : d.toLocaleString();
  },
  fmtUTC(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return isNaN(d) ? String(iso) : d.toISOString().replace("T", " ").slice(0, 19) + "Z";
  },
  async api(method, path, body, jwt) {
    const headers = { "Content-Type": "application/json" };
    if (jwt) headers.Authorization = "Bearer " + jwt;
    const resp = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
    let data = {};
    try { data = await resp.json(); } catch (e) {}
    if (!resp.ok) throw new Error(data.message || data.detail || `HTTP ${resp.status}`);
    return data;
  },

  /* ---------- JWT ---------- */
  async getReadJwt(pid, start, end, experiment) {
    return Util.getReadJwt({
      user_id: this.cfg.user_id, token: this.cfg.token,
      participant_id: pid, start_time: start, end_time: end,
      experiment_id: experiment || undefined,
    });
  },
  async getEventJwt(pid, start, end, experiment) {
    const body = {
      user_id: this.cfg.user_id, token: this.cfg.token,
      participant_id: pid, start_time: start, end_time: end,
    };
    if (experiment) body.experiment_id = experiment;
    const data = await this.api("POST", "/auth/jwt/events", body);
    if (!data.jwt) throw new Error("事件 JWT 获取失败");
    return data.jwt;
  },
  async getEvents(pid, start, end, experiment) {
    const jwt = await this.getEventJwt(pid, start, end, experiment);
    const q = new URLSearchParams({ role: "participant", start_time: start, end_time: end });
    const data = await this.api("GET", "/event/events?" + q.toString(), null, jwt);
    let list = data.event_list || data.events || [];
    if (experiment) list = list.filter((e) => (e.experiment_id || "") === experiment);
    return list;
  },

  /* ---------- 概览：盘点 ---------- */
  async discover() {
    if (!(this.cfg.user_id && this.cfg.token)) {
      this.status("请先在「设置」中配置 user_id + 长期 token", "err");
      document.getElementById("btn-settings").click();
      return;
    }
    const btn = this.$("btn-discover");
    btn.disabled = true;
    this.$("overview-result").innerHTML = '<p class="hint">盘点中…（读取参与者列表 + 每参与者 7 天数据）</p>';
    try {
      // 1) 用默认 participant 获取 read JWT 后拉取参与者列表
      let participants = [];
      const defPid = this.cfg.participant_id;
      if (!defPid) throw new Error("设置中未配置默认 participant_id");
      const rj = await this.getReadJwt(defPid, new Date(Date.now() - 86400000).toISOString(), new Date().toISOString());
      const plist = await this.api("GET", "/auth/participant", null, rj);
      const raw = plist.participants || plist.list || plist.data || (Array.isArray(plist) ? plist : []);
      participants = raw.map((p) => p.participant_id || p.user_id || p.id || p.name).filter(Boolean);
      if (!participants.length) participants = [defPid];

      // 2) 每个参与者：7 天窗 read → 解析 @experiment
      const cards = [];
      const end = new Date().toISOString();
      const start = new Date(Date.now() - 7 * 86400000).toISOString();
      for (const pid of participants) {
        try {
          const j = await this.getReadJwt(pid, start, end);
          const res = await Util.readData(j, { rows: ["eda", "ppg"], start_time: start, end_time: end });
          const expMap = {};
          for (const k of Object.keys(res)) {
            if (k === "time") continue;
            const m = k.match(/^(.+?)@(.+)$/);
            const exp = m ? m[2] : "（无标签）";
            const chan = m ? m[1] : k;
            if (!expMap[exp]) expMap[exp] = { channels: [], points: 0, t0: null, t1: null };
            const arr = res[k] || [];
            expMap[exp].channels.push(chan);
            expMap[exp].points += arr.length;
          }
          const times = res.time || [];
          for (const [exp, info] of Object.entries(expMap)) {
            info.t0 = times.length ? times[0] : null;
            info.t1 = times.length ? times[times.length - 1] : null;
            cards.push({ experiment: exp, participant: pid, ...info });
          }
        } catch (e) {
          this.status(`参与者 ${pid} 盘点失败：${e.message}`, "err");
        }
      }
      cards.sort((a, b) => String(a.experiment).localeCompare(String(b.experiment)));
      this.experimentsCache = cards;
      this.renderDiscover(cards);
      this.status(`盘点完成：${cards.length} 个实验`, "ok");
    } catch (e) {
      this.$("overview-result").innerHTML = `<p class="hint" style="color:var(--danger)">盘点失败：${e.message}</p>`;
      this.status("盘点失败：" + e.message, "err");
    } finally {
      btn.disabled = false;
    }
  },
  renderDiscover(cards) {
    const box = this.$("overview-result");
    if (!cards.length) { box.innerHTML = '<p class="hint">未发现数据。确认时间窗内有数据，或检查凭据权限。</p>'; return; }
    box.innerHTML = cards.map((c) => `
      <div class="experiment-card" data-exp="${c.experiment}" data-pid="${c.participant}">
        <div class="exp-title">${c.experiment}</div>
        <div class="exp-meta">participant: ${c.participant} · 数据: ${c.t0 ? this.fmtUTC(c.t0) + " ~ " + this.fmtUTC(c.t1) : "—"} · 点数合计: ${c.points}</div>
        <div class="exp-chips">${c.channels.map((ch) => `<span class="chip">${ch}</span>`).join("")}</div>
      </div>`).join("");
    box.querySelectorAll(".experiment-card").forEach((el) => {
      el.addEventListener("click", () => {
        this.$("br-exp").value = el.dataset.exp === "（无标签）" ? "" : el.dataset.exp;
        this.$("br-pid").value = el.dataset.pid;
        this.switchView("browse");
        this.setDefaults();
        this.status("已填入实验，点击「读取」查看数据", "info");
      });
    });
  },

  /* ---------- 数据浏览 ---------- */
  setDefaults() {
    const end = new Date();
    const start = new Date(end.getTime() - 3600000);
    this.$("br-start").value = this.toLocalInput(start);
    this.$("br-end").value = this.toLocalInput(end);
    this.$("br-timezone").textContent =
      "存储为 UTC；示例当前窗口 " + this.fmtUTC(start.toISOString()) + " ~ " + this.fmtUTC(end.toISOString());
  },
  toLocalInput(d) {
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
  },
  async browseLoad() {
    const exp = this.val("br-exp");
    const pid = this.val("br-pid");
    const start = this.toUtc(this.val("br-start"));
    const end = this.toUtc(this.val("br-end"));
    const channels = this.val("br-channels").split(",").map((s) => s.trim()).filter(Boolean);
    if (!pid || !start || !end) { this.status("请填写 participant_id 与时间窗", "err"); return; }
    this.status("读取中…", "info");
    try {
      const j = await this.getReadJwt(pid, start, end, exp);
      const res = await Util.readData(j, { rows: channels, start_time: start, end_time: end });
      // 事件叠加（无 experiment 过滤时按时间窗取全部，客户端按实验过滤）
      let events = [];
      try { events = await this.getEvents(pid, start, end, exp || undefined); } catch (e) {}
      Util.drawSeriesWithEvents(this.$("br-canvas"), res, events, {
        channels: Object.keys(res).filter((k) => k !== "time" && (res[k] || []).length),
        title: `${exp || "全部实验"} · ${pid}`,
      });
      this.renderBrowseSummary(res, events, start, end);
      this.status("读取完成", "ok");
    } catch (e) {
      this.status("读取失败：" + e.message, "err");
    }
  },
  renderBrowseSummary(res, events, start, end) {
    const rows = Object.entries(res).filter(([k]) => k !== "time" && (res[k] || []).length);
    const times = res.time || [];
    const html = rows.map(([k, arr]) => {
      const nums = arr.filter((v) => v !== null && v !== undefined);
      const span = times.length >= 2 ? (new Date(times[times.length - 1]) - new Date(times[0])) / 1000 : 0;
      return `<tr><td>${k}</td><td>${arr.length}</td><td>${nums.length ? Math.min(...nums).toFixed(2) : "—"}</td>
        <td>${nums.length ? Math.max(...nums).toFixed(2) : "—"}</td><td>${span ? (arr.length / span).toFixed(1) : "—"} Hz</td></tr>`;
    }).join("");
    this.$("br-summary").innerHTML = `
      <div class="card">
        <h3>摘要 <span class="hint">（本地时间窗 ${this.fmtLocal(start)} ~ ${this.fmtLocal(end)}，UTC ${this.fmtUTC(start)} ~ ${this.fmtUTC(end)}）</span></h3>
        <table><tr><th>通道</th><th>点数</th><th>min</th><th>max</th><th>采样率</th></tr>${html || '<tr><td colspan="5">无数据</td></tr>'}</table>
        <p class="hint">事件 ${events.length} 条${events.length ? "：" + events.map((e) => (e.name || e.event || e.type)).join(", ") : ""}</p>
      </div>`;
  },

  /* ---------- 事件 ---------- */
  async eventsLoad() {
    const exp = this.val("ev-exp");
    const pid = this.val("ev-pid") || this.cfg.participant_id;
    const start = this.toUtc(this.val("ev-start")) || new Date(Date.now() - 86400000).toISOString();
    const end = this.toUtc(this.val("ev-end")) || new Date().toISOString();
    if (!pid) { this.status("请填写 participant_id", "err"); return; }
    try {
      const list = await this.getEvents(pid, start, end, exp || undefined);
      this.$("ev-list").innerHTML = `<div class="card"><h3>事件列表（${list.length}）</h3>
        <table><tr><th>类型</th><th>实验</th><th>开始(本地)</th><th>结束(本地)</th><th>描述</th><th>操作</th></tr>
        ${list.map((e) => `<tr><td>${e.name || e.event || e.type}</td><td>${e.experiment_id || "—"}</td>
          <td>${this.fmtLocal(e.start_time || e.time)}</td><td>${this.fmtLocal(e.end_time)}</td>
          <td>${e.description || e.detail || "—"}</td>
          <td><span class="del" data-id="${e.event_id || e.id}">删除</span></td></tr>`).join("")}
        </table></div>`;
      this.$("ev-list").querySelectorAll(".del").forEach((el) => {
        el.addEventListener("click", () => this.eventDelete(el.dataset.id, pid));
      });
      this.status("事件加载完成", "ok");
    } catch (e) {
      this.status("事件加载失败：" + e.message, "err");
    }
  },
  async eventCreate() {
    const pid = this.val("ev-pid") || this.cfg.participant_id;
    const event = this.val("ev-type");
    const start = this.toUtc(this.val("ev-new-start"));
    const exp = this.val("ev-new-exp");
    if (!pid || !event || !start) { this.status("请填写 participant_id、事件类型与开始时间", "err"); return; }
    try {
      const end = this.toUtc(this.val("ev-new-end"));
      const startMs = new Date(start).getTime();
      const endMs = end ? new Date(end).getTime() : startMs + 1000;
      const endEff = new Date(endMs).toISOString();
      const j = await this.getEventJwt(pid, new Date(startMs - 1000).toISOString(), new Date(endMs + 1000).toISOString(), exp || undefined);
      const body = { user_id: pid, start_time: start, event, end_time: endEff };
      if (exp) body.experiment_id = exp;
      const desc = this.val("ev-new-desc");
      if (desc) body.description = desc;
      await this.api("POST", "/event/events", body, j);
      this.status("事件创建成功", "ok");
      this.eventsLoad();
    } catch (e) {
      this.status("事件创建失败：" + e.message, "err");
    }
  },
  async eventDelete(id, pid) {
    if (!id || !confirm("确认删除该事件？")) return;
    try {
      const j = await this.getEventJwt(pid, "2020-01-01T00:00:00Z", "2035-01-01T00:00:00Z");
      await this.api("DELETE", "/event/events/" + id, null, j);
      this.status("事件已删除", "ok");
      this.eventsLoad();
    } catch (e) {
      this.status("删除失败：" + e.message, "err");
    }
  },

  /* ---------- 实验注册表 ---------- */
  async getAdminJwt() {
    const data = await this.api("POST", "/auth/jwt/admin", {
      user_id: this.cfg.user_id, token: this.cfg.token,
    });
    if (!data.jwt) throw new Error("admin JWT 获取失败");
    return data.jwt;
  },
  async loadExperiments() {
    if (!(this.cfg.user_id && this.cfg.token)) {
      this.status("请先在「设置」中配置 user_id + 长期 token", "err");
      document.getElementById("btn-settings").click();
      return;
    }
    const btn = this.$("exreg-load");
    btn.disabled = true;
    try {
      const pid = this.cfg.participant_id || "000000000000000000000";
      const rj = await this.getReadJwt(pid, new Date(Date.now() - 60000).toISOString(), new Date().toISOString());
      const data = await this.api("GET", "/experiments", null, rj);
      const list = data.experiments || data.list || data.data || [];
      this.renderExperiments(list);
      this.status("实验列表加载完成", "ok");
    } catch (e) {
      this.status("实验列表加载失败：" + e.message, "err");
    } finally {
      btn.disabled = false;
    }
  },
  renderExperiments(list) {
    const box = this.$("exreg-list");
    if (!list.length) { box.innerHTML = '<div class="card"><p class="hint">注册表为空。</p></div>'; return; }
    box.innerHTML = `<div class="card"><h3>实验列表（${list.length}）</h3>
      <table><tr><th>experiment_id</th><th>name</th><th>label</th><th>description</th><th>操作</th></tr>
      ${list.map((e) => `<tr>
        <td>${e.experiment_id || "—"}</td><td>${e.name || "—"}</td><td>${e.label || "—"}</td><td>${e.description || "—"}</td>
        <td><a class="link" data-act="dict" data-id="${e.experiment_id || e.id}">字典</a>
            <span class="del" data-act="del" data-id="${e.experiment_id || e.id}">删除</span></td></tr>`).join("")}
      </table></div>`;
    box.querySelectorAll("a.link").forEach((el) => el.addEventListener("click", () => this.showDict(el.dataset.id)));
    box.querySelectorAll(".del").forEach((el) => el.addEventListener("click", () => this.deleteExperiment(el.dataset.id)));
  },
  async showDict(id) {
    try {
      const pid = this.cfg.participant_id || "000000000000000000000";
      const rj = await this.getReadJwt(pid, new Date(Date.now() - 60000).toISOString(), new Date().toISOString());
      const data = await this.api("GET", `/experiment/${encodeURIComponent(id)}/dictionary`, null, rj);
      this.$("exreg-dict").innerHTML = `<div class="card"><h3>数据字典 · ${id}</h3><pre>${JSON.stringify(data.dictionary || {}, null, 2)}</pre></div>`;
    } catch (e) {
      this.status("字典读取失败：" + e.message, "err");
    }
  },
  async createExperiment() {
    const name = this.val("exreg-name");
    if (!name) { this.status("请填写 name", "err"); return; }
    const body = { name };
    const eid = this.val("exreg-eid");
    const label = this.val("exreg-label");
    const desc = this.val("exreg-desc");
    const dictRaw = this.val("exreg-dict-input");
    if (eid) body.experiment_id = eid;
    if (label) body.label = label;
    if (desc) body.description = desc;
    if (dictRaw) {
      try { body.dictionary = JSON.parse(dictRaw); }
      catch (e) { this.status("数据字典不是合法 JSON", "err"); return; }
    }
    try {
      const j = await this.getAdminJwt();
      const data = await this.api("POST", "/experiment", body, j);
      this.status("实验创建成功：" + (data.experiment && data.experiment.experiment_id || name), "ok");
      this.$("exreg-name").value = ""; this.$("exreg-eid").value = ""; this.$("exreg-label").value = "";
      this.$("exreg-desc").value = ""; this.$("exreg-dict-input").value = "";
      this.loadExperiments();
    } catch (e) {
      this.status("实验创建失败：" + e.message, "err");
    }
  },
  async deleteExperiment(id) {
    if (!id || !confirm("确认删除该实验注册？相关时序列数据不受影响。")) return;
    try {
      const j = await this.getAdminJwt();
      await this.api("DELETE", "/experiment/" + encodeURIComponent(id), null, j);
      this.status("实验已删除", "ok");
      this.loadExperiments();
    } catch (e) {
      this.status("删除失败：" + e.message, "err");
    }
  },

  /* ---------- 分析 ---------- */
  async analysisRun(kind) {
    const pid = this.val("an-pid") || this.cfg.participant_id;
    const exp = this.val("an-exp");
    const start = this.toUtc(this.val("an-start")) || new Date(Date.now() - 3600000).toISOString();
    const end = this.toUtc(this.val("an-end")) || new Date().toISOString();
    const rows = this.val("an-channels").split(",").map((s) => s.trim()).filter(Boolean);
    if (!pid || !rows.length) { this.status("请填写 participant_id 与通道", "err"); return; }
    try {
      const j = await this.getReadJwt(pid, start, end, exp);
      if (kind === "features") {
        const feats = await Util.features(j, { rows, start_time: start, end_time: end });
        this.$("an-result").innerHTML = `<div class="card"><h3>特征统计</h3>${this.renderTable(feats)}</div>`;
      } else {
        const data = await this.api("POST", "/sensor/data/quality", {
          compression: "none", format: "json", rows, start_time: start, end_time: end,
        }, j);
        this.$("an-result").innerHTML = `<div class="card"><h3>质量检查</h3><pre>${JSON.stringify(data, null, 2)}</pre></div>`;
      }
      this.status(kind === "features" ? "特征统计完成" : "质量检查完成", "ok");
    } catch (e) {
      this.status(kind === "features" ? "特征统计失败：" + e.message : "质量检查失败：" + e.message, "err");
    }
  },
  renderTable(obj) {
    if (Array.isArray(obj)) {
      if (!obj.length) return "<p class='hint'>无数据</p>";
      const cols = Object.keys(obj[0] || {});
      return `<table><tr>${cols.map((c) => `<th>${c}</th>`).join("")}</tr>
        ${obj.map((r) => `<tr>${cols.map((c) => `<td>${this.cell(r[c])}</td>`).join("")}</tr>`).join("")}</table>`;
    }
    if (obj && typeof obj === "object") {
      return `<table>${Object.entries(obj).map(([k, v]) => `<tr><th>${k}</th><td>${this.cell(v)}</td></tr>`).join("")}</table>`;
    }
    return `<p>${this.cell(obj)}</p>`;
  },
  cell(v) {
    if (v === null || v === undefined) return "—";
    if (typeof v === "object") return JSON.stringify(v);
    return String(v);
  },

  /* ---------- 导出 ---------- */
  async exportRun() {
    const pid = this.val("ex-pid") || this.cfg.participant_id;
    const exp = this.val("ex-exp");
    const start = this.toUtc(this.val("ex-start")) || new Date(Date.now() - 3600000).toISOString();
    const end = this.toUtc(this.val("ex-end")) || new Date().toISOString();
    const rows = this.val("ex-channels").split(",").map((s) => s.trim()).filter(Boolean);
    if (!pid || !rows.length) { this.status("请填写 participant_id 与通道", "err"); return; }
    try {
      const j = await this.getReadJwt(pid, start, end, exp);
      const res = await Util.exportData(j, { rows, start_time: start, end_time: end, experiment_id: exp || undefined });
      window.__exportData = res;
      const sensor = res.sensor || {};
      const n = Object.keys(sensor).reduce((s, k) => s + (sensor[k] || []).length, 0);
      this.$("ex-result").innerHTML = `<div class="card"><h3>导出摘要</h3>
        <table><tr><th>时序通道</th><th>总点数</th><th>事件</th><th>实验元数据</th></tr>
        <tr><td>${Object.keys(sensor).join(", ") || "—"}</td><td>${n}</td>
        <td>${(res.events || []).length}</td><td>${res.experiment ? this.cell(res.experiment) : "无"}</td></tr></table></div>`;
      this.$("ex-download").disabled = false;
      this.status("导出完成", "ok");
    } catch (e) {
      this.status("导出失败：" + e.message, "err");
    }
  },
  exportDownload() {
    if (!window.__exportData) return;
    const blob = new Blob([JSON.stringify(window.__exportData, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `biodb_export_${this.val("ex-exp") || "all"}_${this.val("ex-pid") || "p"}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  },

  /* ---------- 设置 ---------- */
  openSettings() {
    this.$("set-user").value = this.cfg.user_id || "";
    this.$("set-token").value = this.cfg.token || "";
    this.$("set-pid").value = this.cfg.participant_id || "";
    this.$("settings-modal").classList.remove("hidden");
  },
  saveSettings() {
    this.cfg.user_id = this.val("set-user");
    this.cfg.token = this.val("set-token");
    this.cfg.participant_id = this.val("set-pid");
    this.saveCfg();
    this.$("settings-modal").classList.add("hidden");
    this.status("配置已保存", "ok");
  },
  async testConnection() {
    const user_id = this.val("set-user");
    const token = this.val("set-token");
    const pid = this.val("set-pid");
    if (!user_id || !token || !pid) { this.$("set-result").innerHTML = '<p class="hint" style="color:var(--danger)">请填全 user_id / token / participant_id</p>'; return; }
    this.$("set-result").innerHTML = '<p class="hint">测试中…</p>';
    try {
      const j = await Util.getReadJwt({ user_id, token, participant_id: pid, start_time: new Date(Date.now() - 60000).toISOString(), end_time: new Date().toISOString() });
      this.$("set-result").innerHTML = `<p class="hint" style="color:var(--ok)">连接成功（read JWT 获取正常）</p>`;
      this.status("连接成功", "ok");
    } catch (e) {
      this.$("set-result").innerHTML = `<p class="hint" style="color:var(--danger)">连接失败：${e.message}</p>`;
      this.status("连接失败：" + e.message, "err");
    }
  },

  /* ---------- 视图切换 ---------- */
  switchView(name) {
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + name));
  },

  /* ---------- 初始化 ---------- */
  init() {
    this.loadCfg();
    this.saveCfg();

    document.getElementById("btn-settings").addEventListener("click", () => this.openSettings());
    document.getElementById("set-save").addEventListener("click", () => this.saveSettings());
    document.getElementById("set-test").addEventListener("click", () => this.testConnection());
    document.getElementById("set-close").addEventListener("click", () => this.$("settings-modal").classList.add("hidden"));

    document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => this.switchView(b.dataset.view)));

    this.$("btn-discover").addEventListener("click", () => this.discover());
    this.$("br-load").addEventListener("click", () => this.browseLoad());
    this.$("br-set-defaults").addEventListener("click", () => this.setDefaults());

    this.$("ev-load").addEventListener("click", () => this.eventsLoad());
    this.$("ev-create").addEventListener("click", () => this.eventCreate());
    this.$("exreg-load").addEventListener("click", () => this.loadExperiments());
    this.$("exreg-create").addEventListener("click", () => this.createExperiment());
    this.$("an-features").addEventListener("click", () => this.analysisRun("features"));
    this.$("an-quality").addEventListener("click", () => this.analysisRun("quality"));
    this.$("ex-run").addEventListener("click", () => this.exportRun());
    this.$("ex-download").addEventListener("click", () => this.exportDownload());

    // 概览打开时自动同步 participant 默认值到各视图
    ["ev-pid", "an-pid", "ex-pid"].forEach((id) => {
      this.$(id).addEventListener("focus", () => { if (!this.val(id) && this.cfg.participant_id) this.$(id).value = this.cfg.participant_id; });
    });
    this.setDefaults();
  },
};

document.addEventListener("DOMContentLoaded", () => App.init());
