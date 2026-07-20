/** CSRF helper for fetch() JSON / DELETE APIs. */
(function () {
  function getCookie(name) {
    var m = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return m ? decodeURIComponent(m[2]) : "";
  }
  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return (meta && meta.getAttribute("content")) || getCookie("csrftoken") || "";
  }
  var _fetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    init = init || {};
    var method = (init.method || "GET").toUpperCase();
    if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
      init.headers = init.headers || {};
      if (init.headers instanceof Headers) {
        if (!init.headers.has("X-CSRFToken")) {
          init.headers.set("X-CSRFToken", csrfToken());
        }
      } else {
        if (!init.headers["X-CSRFToken"] && !init.headers["x-csrftoken"]) {
          init.headers["X-CSRFToken"] = csrfToken();
        }
      }
      init.credentials = init.credentials || "same-origin";
    }
    return _fetch(input, init);
  };
})();
