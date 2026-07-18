(function () {
  var KEY = "redlineguard-theme";
  var btn = document.getElementById("theme-toggle");
  if (!btn) return;

  function apply(dark) {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem(KEY, dark ? "dark" : "light");
    } catch (e) {}
    btn.setAttribute("aria-pressed", dark ? "true" : "false");
    btn.textContent = dark ? "☀" : "◐";
  }

  apply(document.documentElement.classList.contains("dark"));
  btn.addEventListener("click", function () {
    apply(!document.documentElement.classList.contains("dark"));
  });
})();
