(function () {
  const target = "/dashboard/positions";
  const loginPath = "/login";
  const username = "__FUNDVAL_ADMIN_USERNAME__";
  const password = "__FUNDVAL_ADMIN_PASSWORD__";
  const localUser = { id: "1", username, role: "admin" };

  localStorage.setItem("access_token", "local-auto-login");
  localStorage.setItem("refresh_token", "local-auto-login");
  localStorage.setItem("user", JSON.stringify(localUser));

  function shouldAutoLogin() {
    return location.pathname === loginPath || location.pathname === "/";
  }

  async function autoLogin() {
    if (!shouldAutoLogin()) {
      return;
    }
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (response.ok) {
        const data = await response.json();
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        localStorage.setItem("user", JSON.stringify(data.user || localUser));
      }
    } catch (error) {
      console.warn("FundVal local auto-login failed", error);
    }
    if (location.pathname === loginPath || location.pathname === "/") {
      location.replace(target);
    }
  }

  autoLogin();
})();
