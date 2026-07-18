// ════════════════════════════════════════════════════════════
//  عميل API مركزي (API Client)
//  كل نداء للباك-إند يمرّ من هنا. التوكن يُضاف تلقائياً.
// ════════════════════════════════════════════════════════════

const TOKEN_KEY = "whalex_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}
export function setToken(t) {
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = null;
  try { data = await res.json(); } catch { /* قد لا يكون JSON */ }

  if (!res.ok) {
    let msg = data?.detail || data?.error || `خطأ ${res.status}`;
    // 422: detail قد يكون مصفوفة أخطاء أو كائن
    if (Array.isArray(msg)) msg = msg.map((e) => e?.msg || JSON.stringify(e)).join(" · ");
    else if (typeof msg === "object") msg = msg?.msg || JSON.stringify(msg);
    throw new Error(String(msg));
  }
  return data;
}

export const api = {
  get:  (p)    => request("GET", p),
  post: (p, b) => request("POST", p, b),
  put:  (p, b) => request("PUT", p, b),
  del:  (p)    => request("DELETE", p),
};

// ─── نداءات جاهزة (مختصرات) ───
export const auth = {
  login:    (username, password) => api.post("/api/auth/login", { username, password }),
  register: (username, password, email) => api.post("/api/auth/register", { username, password, email }),
  forgot:   (username) => api.post("/api/auth/forgot", { username }),
  resetPassword: (username, code, new_password) => api.post("/api/auth/reset-password", { username, code, new_password }),
  linkCode: () => api.post("/api/auth/link-code", {}),
  linkStatus: (username) => api.post("/api/auth/link-status", { username }),
};

export const binance = {
  status:     ()     => api.get("/api/binance/status"),
  connect:    (b)    => api.post("/api/binance/connect", b),
  disconnect: ()     => api.del("/api/binance/disconnect"),
  test:       (b)    => api.post("/api/binance/test", b),
  balance:    ()     => api.get("/api/binance/balance"),
  positions:  ()     => api.get("/api/binance/positions"),
  autoTrade:  (b)    => api.post("/api/binance/auto-trade", b),
  settings:   ()     => api.get("/api/binance/settings"),
};

export const push = {
  publicKey: () => api.get("/api/push/public-key"),
  subscribe: (subscription) => api.post("/api/push/subscribe", { subscription }),
  unsubscribe: (subscription) => api.post("/api/push/unsubscribe", { subscription }),
};

export const livePositions = {
  radar:   () => api.get("/api/live/radar-positions"),
  binance: () => api.get("/api/live/binance-positions"),
  close:   (symbol) => api.post("/api/binance/manual/close", { symbol }),
};

export const signals = {
  all:     () => api.get("/api/signals/all"),
  history:   (m = "futures") => api.get(`/api/signals/history?market=${m}`),
  monthly: () => api.get("/api/signals/monthly"),
};

export const subscription = {
  plans:   () => api.get("/api/subscription/plans"),
  stats:   () => api.get("/api/subscription/stats"),
  status:  () => api.get("/api/subscription/status"),
  upgrade: (b) => api.post("/api/subscription/upgrade", b),
};
