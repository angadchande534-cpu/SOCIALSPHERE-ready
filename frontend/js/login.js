// Optional external login handler. The current login.html uses the same logic inline.
const form = document.getElementById("loginForm");
if (form) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const identifier = document.getElementById("identifier")?.value.trim();
    const password = document.getElementById("password")?.value || "";
    const message = document.getElementById("loginMessage") || document.getElementById("message");

    try {
      const data = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({identifier, password}),
      });
      saveAuthToken(data.access_token);
      localStorage.setItem(SAVED_LOGIN_KEY, identifier);
      if (message) message.textContent = "Login successful";
      window.location.replace("/feed");
    } catch (error) {
      if (message) message.textContent = error.message;
    }
  });
}
