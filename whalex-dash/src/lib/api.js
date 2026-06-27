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

export const signals = {
  all:     () => api.get("/api/signals/all"),
  history: () => api.get("/api/signals/history"),
};

export const subscription = {
  status:  () => api.get("/api/subscription/status"),
  upgrade: (b) => api.post("/api/subscription/upgrade", b),
};
