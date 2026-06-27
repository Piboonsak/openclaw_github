(function () {
  "use strict";

  const auth = window.LedgerFlowAuth;

  if (!auth) {
    throw new Error("LedgerFlowAuth is required before main.js");
  }

  async function init() {
    auth.installFetchAuth();
    const user = await auth.requireAuth();
    if (!user) return;

    auth.applyUserChrome(user, { currentPage: "home" });
    auth.bindLogoutButton(document.getElementById("logoutBtn"));

    const progressBar = document.getElementById("progressBar");
    const confidenceValue = document.getElementById("confidenceValue");
    if (progressBar && confidenceValue) {
      const values = [86, 88, 84, 91, 87];
      let index = 0;
      window.setInterval(() => {
        index = (index + 1) % values.length;
        const next = values[index];
        progressBar.style.width = `${next}%`;
        confidenceValue.textContent = `${next}%`;
      }, 2800);
    }
  }

  init().catch(function () {
    auth.clearToken();
    window.location.href = "./login.html";
  });
}());
