(function () {
  "use strict";

  const TOKEN_KEY = "lf_token";
  const LOGIN_PATH = "./login.html";
  const HOME_PATH = "./index.html";
  const FILE_API_ORIGIN = "http://127.0.0.1:8000";
  let cachedUser = null;
  let fetchInstalled = false;
  let nativeFetch = null;

  function apiUrl(path) {
    const normalized = path.startsWith("/") ? path : `/${path}`;
    return window.location.protocol === "file:"
      ? `${FILE_API_ORIGIN}${normalized}`
      : normalized;
  }

  function getToken() {
    try {
      return window.localStorage.getItem(TOKEN_KEY) || "";
    } catch {
      return "";
    }
  }

  function setToken(token) {
    try {
      window.localStorage.setItem(TOKEN_KEY, token);
    } catch {}
  }

  function clearToken() {
    try {
      window.localStorage.removeItem(TOKEN_KEY);
    } catch {}
    cachedUser = null;
  }

  function isApiTarget(input) {
    const rawUrl = typeof input === "string" ? input : input?.url || "";
    if (!rawUrl) return false;
    try {
      const target = new URL(rawUrl, window.location.href);
      const localApiOrigin =
        window.location.protocol === "file:"
          ? new URL(FILE_API_ORIGIN).origin
          : window.location.origin;
      return target.origin === localApiOrigin && target.pathname.startsWith("/api/");
    } catch {
      return rawUrl.startsWith("/api/");
    }
  }

  function createAuthedRequest(input, init) {
    const token = getToken();
    if (!token || !isApiTarget(input)) {
      return { input, init };
    }

    const headers = new Headers(
      init?.headers || (input instanceof Request ? input.headers : undefined) || undefined
    );
    if (!headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    if (input instanceof Request) {
      return {
        input: new Request(input, { ...init, headers }),
        init: undefined,
      };
    }

    return {
      input,
      init: { ...(init || {}), headers },
    };
  }

  function installFetchAuth() {
    if (fetchInstalled) return;
    nativeFetch = nativeFetch || window.fetch.bind(window);
    window.fetch = function patchedFetch(input, init) {
      const authed = createAuthedRequest(input, init);
      return nativeFetch(authed.input, authed.init);
    };
    fetchInstalled = true;
  }

  async function apiFetch(input, init) {
    installFetchAuth();
    return window.fetch(input, init);
  }

  function getInitials(name) {
    const words = String(name || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (!words.length) return "LF";
    return words
      .slice(0, 2)
      .map((word) => word[0].toUpperCase())
      .join("");
  }

  function setVisibility(selector, visible) {
    document.querySelectorAll(selector).forEach((node) => {
      node.hidden = !visible;
      node.setAttribute("aria-hidden", String(!visible));
    });
  }

  async function getCurrentUser(force) {
    const token = getToken();
    if (!token) return null;
    if (!force && cachedUser) return cachedUser;

    installFetchAuth();
    try {
      const response = await window.fetch(apiUrl("/api/v1/auth/me"));
      if (!response.ok) {
        if (response.status === 401) clearToken();
        return null;
      }
      cachedUser = await response.json();
      return cachedUser;
    } catch {
      return null;
    }
  }

  function redirectToLogin() {
    window.location.href = LOGIN_PATH;
  }

  function redirectToHome() {
    window.location.href = HOME_PATH;
  }

  async function requireAuth(options) {
    const settings = options || {};
    const user = await getCurrentUser(true);
    if (!user) {
      redirectToLogin();
      return null;
    }
    if (settings.adminOnly && user.role !== "admin") {
      redirectToHome();
      return null;
    }
    return user;
  }

  async function redirectIfAuthenticated() {
    const user = await getCurrentUser(true);
    if (user) {
      redirectToHome();
    }
    return user;
  }

  function applyUserChrome(user, options) {
    const settings = options || {};
    const displayName = String(user?.name || "ผู้ใช้งาน");
    const initials = getInitials(displayName);

    document.querySelectorAll("[data-user-name]").forEach((node) => {
      node.textContent = displayName;
    });
    document.querySelectorAll("[data-user-avatar]").forEach((node) => {
      node.textContent = initials;
      node.setAttribute("aria-label", displayName);
      node.setAttribute("title", displayName);
    });
    document.querySelectorAll("[data-user-role]").forEach((node) => {
      node.textContent = user?.role === "admin" ? "Admin" : "Staff";
    });

    setVisibility("[data-admin-only]", user?.role === "admin");

    if (settings.currentPage) {
      document.querySelectorAll("[data-nav]").forEach((node) => {
        const isCurrent = node.getAttribute("data-nav") === settings.currentPage;
        node.classList.toggle("is-current", isCurrent);
        if (isCurrent) node.setAttribute("aria-current", "page");
        else node.removeAttribute("aria-current");
      });
    }
  }

  function bindLogoutButton(node) {
    if (!node || node.dataset.boundLogout === "true") return;
    node.dataset.boundLogout = "true";
    node.addEventListener("click", () => {
      clearToken();
      redirectToLogin();
    });
  }

  window.LedgerFlowAuth = {
    TOKEN_KEY,
    apiUrl,
    getToken,
    setToken,
    clearToken,
    apiFetch,
    installFetchAuth,
    getCurrentUser,
    requireAuth,
    redirectIfAuthenticated,
    applyUserChrome,
    bindLogoutButton,
    getInitials,
  };
}());
