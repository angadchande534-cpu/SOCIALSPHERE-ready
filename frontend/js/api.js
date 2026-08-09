// SocialSphere frontend helper.
// Login is saved on this device until the user presses Logout or the account token is revoked.
const API_BASE = window.location.origin;
const AUTH_TOKEN_KEY = "socialsphere_token";
const LEGACY_TOKEN_KEYS = ["token", "access_token"];
const SAVED_LOGIN_KEY = "socialsphere_saved_login";
const LAST_REFRESH_KEY = "socialsphere_last_token_refresh";
let sessionRefreshPromise = null;

function token() {
  let current = localStorage.getItem(AUTH_TOKEN_KEY);
  if (current) return current;

  // Older project versions sometimes stored the token only for one browser tab.
  // Migrate that token into localStorage so the login remains saved.
  current = sessionStorage.getItem(AUTH_TOKEN_KEY);
  if (current) {
    localStorage.setItem(AUTH_TOKEN_KEY, current);
    sessionStorage.removeItem(AUTH_TOKEN_KEY);
    return current;
  }

  for (const key of LEGACY_TOKEN_KEYS) {
    const legacy = localStorage.getItem(key) || sessionStorage.getItem(key);
    if (legacy) {
      localStorage.setItem(AUTH_TOKEN_KEY, legacy);
      localStorage.removeItem(key);
      sessionStorage.removeItem(key);
      return legacy;
    }
  }
  return null;
}

function saveAuthToken(accessToken) {
  clearAuthToken();
  localStorage.setItem(AUTH_TOKEN_KEY, accessToken);
  localStorage.setItem(LAST_REFRESH_KEY, String(Date.now()));
}

function clearAuthToken() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  sessionStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(LAST_REFRESH_KEY);
  sessionStorage.removeItem(LAST_REFRESH_KEY);
  LEGACY_TOKEN_KEYS.forEach((key) => {
    localStorage.removeItem(key);
    sessionStorage.removeItem(key);
  });
}

function authHeaders(json = true) {
  const headers = {};
  const accessToken = token();
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

function errorMessage(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || "Invalid value").join("; ");
  }
  return "Request failed";
}

function safeNextPath() {
  const value = `${window.location.pathname}${window.location.search}`;
  if (!value.startsWith("/") || value.startsWith("//")) return "/feed";
  return value;
}

function loginPage() {
  return `/login?next=${encodeURIComponent(safeNextPath())}`;
}

async function api(path, options = {}) {
  const isForm = typeof FormData !== "undefined" && options.body instanceof FormData;
  options.headers = {
    ...authHeaders(!isForm),
    ...(options.headers || {}),
  };

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch (_error) {
    throw new Error("Cannot connect to the backend. Start FastAPI and refresh the page.");
  }

  
const rawText = await response.text();

let data = {};

try {
    data = rawText ? JSON.parse(rawText) : {};
} catch (error) {
    console.error("API returned NON-JSON:", {
        path: path,
        status: response.status,
        body: rawText
    });

    throw new Error(
        `Server returned non-JSON (${response.status}): ${rawText.slice(0, 200)}`
    );
}


if (!response.ok) {

    const isLoginAction =
        path.includes("/api/auth/login") ||
        path.includes("/api/auth/signup");

    const alreadyOnLogin =
        window.location.pathname.startsWith("/login");


    if (response.status === 401 && !isLoginAction) {

        clearAuthToken();

        if (!alreadyOnLogin) {
            window.location.replace(loginPage());
        }
    }


    throw new Error(
        errorMessage(data.detail || `Request failed (${response.status})`)
    );
}


return data;
}

function jwtPayload(accessToken) {
  try {
    const part = accessToken.split(".")[1];
    const normalized = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
    return JSON.parse(atob(padded));
  } catch (_error) {
    return null;
  }
}

function sessionNeedsRefresh() {
  const accessToken = token();
  if (!accessToken) return false;

  const payload = jwtPayload(accessToken);
  const expiresAt = Number(payload?.exp || 0) * 1000;
  const lastRefresh = Number(localStorage.getItem(LAST_REFRESH_KEY) || 0);
  const thirtyDays = 30 * 24 * 60 * 60 * 1000;
  const sevenDays = 7 * 24 * 60 * 60 * 1000;

  return !expiresAt || expiresAt - Date.now() < thirtyDays || Date.now() - lastRefresh > sevenDays;
}

async function refreshStoredSession() {
  if (!token()) return false;
  if (!sessionNeedsRefresh()) return true;
  if (sessionRefreshPromise) return sessionRefreshPromise;

  sessionRefreshPromise = (async () => {
    try {
      const data = await api("/api/auth/refresh", {method: "POST"});
      saveAuthToken(data.access_token);
      return true;
    } catch (_error) {
      return false;
    } finally {
      sessionRefreshPromise = null;
    }
  })();

  return sessionRefreshPromise;
}

async function ensureAuthenticated() {
  if (!token()) {
    window.location.replace(loginPage());
    return null;
  }

  await refreshStoredSession();
  try {
    return await api("/api/auth/me");
  } catch (_error) {
    return null;
  }
}

function backendPage(path) {
  window.location.href = `${API_BASE}${path}`;
}

function fileUrl(path, name = "User") {
  if (path) return path.startsWith("http") ? path : `${API_BASE}${path}`;

  const initials =
    String(name || "User")
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0] || "")
      .join("")
      .toUpperCase() || "U";

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#8c5cff"/><stop offset="1" stop-color="#41c7ff"/></linearGradient></defs><rect width="240" height="240" rx="120" fill="url(#g)"/><text x="120" y="137" text-anchor="middle" font-family="Arial" font-size="82" font-weight="700" fill="white">${initials}</text></svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

function escapeHtml(value = "") {
  return String(value).replace(
    /[&<>'"]/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "'": "&#39;",
        '"': "&quot;",
      })[character]
  );
}

function logout() {
  clearAuthToken();
  localStorage.removeItem(SAVED_LOGIN_KEY);
  window.location.replace("/login");
}

function setBadge(selector, count) {
  document.querySelectorAll(selector).forEach((badge) => {
    badge.textContent = count > 99 ? "99+" : String(count);
    badge.classList.toggle("hidden", count === 0);
  });
}

async function refreshNotificationBadge() {
  if (!document.querySelector(".notification-badge") || !token()) return;
  try {
    const result = await api("/api/notifications/unread-count");
    setBadge(".notification-badge", result.unread_count);
  } catch (_error) {}
}

async function refreshMessageBadge() {
  if (!document.querySelector(".message-badge") || !token()) return;
  try {
    const result = await api("/api/messages/unread-count");
    setBadge(".message-badge", result.unread_count);
  } catch (_error) {}
}

async function refreshNavigationBadges() {
  await Promise.all([refreshNotificationBadge(), refreshMessageBadge()]);
}

document.addEventListener("DOMContentLoaded", async () => {
  token();
  if (!token()) return;
  await refreshStoredSession();
  await refreshNavigationBadges();
});

// Keep an active browser session renewed and update unread counts.
window.setInterval(() => {
  if (!token()) return;
  refreshStoredSession();
  refreshNavigationBadges();
}, 60000);

// Lightweight incoming-call listener. WebRTC media itself is peer-to-peer; this socket only carries signaling.
let incomingCallSocket = null;
function initIncomingCallListener() {
  if (!token() || location.pathname === "/call" || incomingCallSocket) return;
  try {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    incomingCallSocket = new WebSocket(`${proto}://${location.host}/ws/calls?token=${encodeURIComponent(token())}`);
    incomingCallSocket.onmessage = (event) => {
      let data; try { data = JSON.parse(event.data); } catch { return; }
      if (data.type !== "offer" || !data.from_user_id) return;
      sessionStorage.setItem("socialsphere_pending_call", JSON.stringify(data));
      const existing = document.getElementById("socialsphereIncomingCall"); if (existing) existing.remove();
      const box = document.createElement("div"); box.id = "socialsphereIncomingCall"; box.className = "incoming";
      const mode = data.call_mode === "audio" ? "voice" : "video";
      box.innerHTML = `<strong>${escapeHtml(data.from_username || "Someone")} is calling</strong><div class="u-muted">Incoming ${mode} call</div><div class="incoming-actions"><button class="u-btn" id="rejectIncoming">Decline</button><button class="u-btn primary" id="acceptIncoming">Accept</button></div>`;
      document.body.appendChild(box);
      document.getElementById("rejectIncoming").onclick = () => { incomingCallSocket?.send(JSON.stringify({type:"hangup",target_user_id:data.from_user_id})); sessionStorage.removeItem("socialsphere_pending_call"); box.remove(); };
      document.getElementById("acceptIncoming").onclick = () => { location.href = `/call?user_id=${data.from_user_id}&mode=${data.call_mode || "video"}&incoming=1`; };
    };
    incomingCallSocket.onclose = () => { incomingCallSocket = null; };
  } catch (_error) {}
}

document.addEventListener("DOMContentLoaded", () => setTimeout(initIncomingCallListener, 300));
