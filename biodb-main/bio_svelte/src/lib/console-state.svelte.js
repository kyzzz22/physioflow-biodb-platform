/**
 * BioDB Console 共享状态 + API（Svelte 迁移版）
 * - 长期 token → sensor_read / event / admin JWT 获取
 * - sensor 数据读回 / 导出 / 特征 / 质量
 * - 实验注册表 / 事件 CRUD
 * 所有 API 均经 nginx 同源代理（/auth、/sensor、/event、/experiment）。
 */

const STORAGE_KEY = "biodb_svelte_console_cfg";

function loadCfg() {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch (e) {
    return {};
  }
}

export const consoleState = $state({
  cfg: loadCfg(),
  status: "",
  statusType: "info",
  experimentsCache: [],
  /** 概览发现的实验卡片（用于点击跳转数据浏览） */
  overviewCards: [],
  /** 数据浏览的当前结果（供各视图复用） */
  browseResult: null,
  exportResult: null,
  /** 跳转到数据浏览的种子（{exp, pid, ts}，ts 变化触发） */
  browseSeed: { exp: "", pid: "", ts: 0 },
});

export function saveCfg() {
  if (typeof window !== "undefined") {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(consoleState.cfg));
  }
}

export function hasCreds() {
  return !!(consoleState.cfg.user_id && consoleState.cfg.token);
}

export function status(msg, type = "info") {
  consoleState.status = msg;
  consoleState.statusType = type;
}

/* ---------- 基础工具 ---------- */

export function api(method, path, body, jwt) {
  const headers = { "Content-Type": "application/json" };
  if (jwt) headers.Authorization = "Bearer " + jwt;
  return fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  }).then(async (resp) => {
    let data = {};
    try {
      data = await resp.json();
    } catch (e) {
      /* noop */
    }
    if (!resp.ok) throw new Error(data.message || data.detail || `HTTP ${resp.status}`);
    return data;
  });
}

/** 本地时间(datetime-local) → UTC ISO */
export function toUtc(v) {
  return v ? new Date(v).toISOString() : "";
}

export function fmtLocal(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d) ? String(iso) : d.toLocaleString();
}

export function fmtUTC(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d) ? String(iso) : d.toISOString().replace("T", " ").slice(0, 19) + "Z";
}

export function toLocalInput(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function cell(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/* ---------- JWT ---------- */

export async function getReadJwt(pid, start, end, experiment) {
  const body = {
    user_id: consoleState.cfg.user_id,
    token: consoleState.cfg.token,
    participant_id: pid,
    start_time: start,
    end_time: end,
  };
  if (experiment) body.experiment_id = experiment;
  const data = await api("POST", "/auth/jwt/sensors/readjwt", body);
  if (!data.jwt) throw new Error("JWT 取得に失敗しました");
  return data.jwt;
}

export async function getEventJwt(pid, start, end, experiment) {
  const body = {
    user_id: consoleState.cfg.user_id,
    token: consoleState.cfg.token,
    participant_id: pid,
    start_time: start,
    end_time: end,
  };
  if (experiment) body.experiment_id = experiment;
  const data = await api("POST", "/auth/jwt/events", body);
  if (!data.jwt) throw new Error("イベント JWT 取得に失敗しました");
  return data.jwt;
}

export async function getAdminJwt() {
  const data = await api("POST", "/auth/jwt/admin", {
    user_id: consoleState.cfg.user_id,
    token: consoleState.cfg.token,
  });
  if (!data.jwt) throw new Error("admin JWT 取得に失敗しました");
  return data.jwt;
}

/* ---------- 传感器数据 ---------- */

/** 读回传感器数据（统一信封：compression/format/data base64） */
export async function readData(jwt, { rows, start_time, end_time, chunk_seconds }) {
  const payload = { compression: "none", format: "json", rows, start_time, end_time };
  if (chunk_seconds) payload.chunk_seconds = chunk_seconds;
  const data = await api("POST", "/sensor/data/read", payload, jwt);
  const jsonStr = atob(data.data);
  return JSON.parse(jsonStr);
}

/** 联合导出（时序+事件+实验元数据） */
export async function exportData(jwt, { rows, start_time, end_time, experiment_id, include_events, include_experiment }) {
  const payload = {
    compression: "none",
    format: "json",
    rows,
    start_time,
    end_time,
    include_events: include_events !== false,
    include_experiment: include_experiment !== false,
  };
  if (experiment_id) payload.experiment_id = experiment_id;
  return api("POST", "/sensor/data/export", payload, jwt);
}

/** 特征统计 */
export async function features(jwt, { rows, start_time, end_time }) {
  const data = await api(
    "POST",
    "/sensor/data/features",
    { compression: "none", format: "json", rows, start_time, end_time },
    jwt
  );
  return data.features;
}

/* ---------- 事件 ---------- */

export async function getEvents(pid, start, end, experiment) {
  const jwt = await getEventJwt(pid, start, end, experiment);
  const q = new URLSearchParams({ role: "participant", start_time: start, end_time: end });
  const data = await api("GET", "/event/events?" + q.toString(), null, jwt);
  let list = data.event_list || data.events || [];
  if (experiment) list = list.filter((e) => (e.experiment_id || "") === experiment);
  return list;
}

/* ---------- 概览：盘点 ---------- */

export async function discover() {
  const defPid = consoleState.cfg.participant_id;
  if (!defPid) throw new Error("設定で participant_id を設定してください");
  const now = new Date();
  const end = now.toISOString();
  const start = new Date(now.getTime() - 7 * 86400000).toISOString();

  // 1) 参与者列表
  const rj = await getReadJwt(defPid, new Date(Date.now() - 86400000).toISOString(), now.toISOString());
  const plist = await api("GET", "/auth/participant", null, rj);
  const raw = plist.participants || plist.list || plist.data || (Array.isArray(plist) ? plist : []);
  let participants = raw.map((p) => p.participant_id || p.user_id || p.id || p.name).filter(Boolean);
  if (!participants.length) participants = [defPid];

  // 2) 每参与者 7 天窗盘点
  const cards = [];
  for (const pid of participants) {
    try {
      const j = await getReadJwt(pid, start, end);
      const res = await readData(j, { rows: ["eda", "ppg"], start_time: start, end_time: end });
      const expMap = {};
      for (const k of Object.keys(res)) {
        if (k === "time") continue;
        const m = k.match(/^(.+?)@(.+)$/);
        const exp = m ? m[2] : "（無ラベル）";
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
      status(`参加者 ${pid} の棚卸しに失敗: ${e.message}`, "err");
    }
  }
  cards.sort((a, b) => String(a.experiment).localeCompare(String(b.experiment)));
  consoleState.overviewCards = cards;
  return cards;
}

/* ---------- 实验注册表 ---------- */

export async function loadExperiments() {
  const pid = consoleState.cfg.participant_id || "000000000000000000000";
  const rj = await getReadJwt(pid, new Date(Date.now() - 60000).toISOString(), new Date().toISOString());
  const data = await api("GET", "/experiments", null, rj);
  const list = data.experiments || data.list || data.data || [];
  consoleState.experimentsCache = list;
  return list;
}

export async function showDict(id) {
  const pid = consoleState.cfg.participant_id || "000000000000000000000";
  const rj = await getReadJwt(pid, new Date(Date.now() - 60000).toISOString(), new Date().toISOString());
  return api("GET", `/experiment/${encodeURIComponent(id)}/dictionary`, null, rj);
}

export async function createExperiment(body) {
  const j = await getAdminJwt();
  return api("POST", "/experiment", body, j);
}

export async function deleteExperiment(id) {
  const j = await getAdminJwt();
  return api("DELETE", "/experiment/" + encodeURIComponent(id), null, j);
}
