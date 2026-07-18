/**
 * Paint playbook hits into the document pane (PactPilot DocumentPane idea).
 * Uses start/end offsets when available; falls back to clause_excerpt search.
 */
(function () {
  var root = document.getElementById("doc-highlight-root");
  if (!root) return;

  var findings = [];
  var dataEl = document.getElementById("rg-highlight-data");
  if (dataEl) {
    try {
      findings = JSON.parse(dataEl.textContent || "[]");
    } catch (e) {
      findings = [];
    }
  }

  var rawText = "";
  var textEl = document.getElementById("rg-doc-text");
  if (textEl) {
    try {
      rawText = JSON.parse(textEl.textContent || '""');
    } catch (e) {
      rawText = root.textContent || "";
    }
  } else {
    rawText = root.textContent || "";
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function severityClass(s) {
    s = (s || "medium").toLowerCase();
    if (s === "high") return "high";
    if (s === "low") return "low";
    return "medium";
  }

  function ranges() {
    var out = [];
    var len = rawText.length;
    findings.forEach(function (f) {
      var start = f.start | 0;
      var end = f.end | 0;
      if (end > start && start < len) {
        out.push({
          id: f.id,
          start: Math.max(0, start),
          end: Math.min(len, end),
          severity: severityClass(f.severity),
        });
        return;
      }
      var excerpt = (f.excerpt || "").trim();
      if (!excerpt) return;
      var idx = rawText.indexOf(excerpt);
      if (idx < 0 && excerpt.length > 40) {
        var slice = excerpt.slice(0, 40);
        idx = rawText.indexOf(slice);
        if (idx >= 0) excerpt = rawText.slice(idx, idx + Math.min(excerpt.length, 280));
      }
      if (idx < 0) return;
      out.push({
        id: f.id,
        start: idx,
        end: idx + excerpt.length,
        severity: severityClass(f.severity),
      });
    });
    out.sort(function (a, b) {
      return a.start - b.start || b.end - a.end;
    });
    var cleaned = [];
    var cursor = 0;
    out.forEach(function (r) {
      if (r.start < cursor) return;
      cleaned.push(r);
      cursor = r.end;
    });
    return cleaned;
  }

  function render() {
    var rs = ranges();
    var html = "";
    var i = 0;
    rs.forEach(function (r) {
      if (r.start > i) html += escapeHtml(rawText.slice(i, r.start));
      html +=
        '<mark class="clause-mark ' +
        r.severity +
        '" id="mark-' +
        escapeHtml(r.id) +
        '" data-finding="' +
        escapeHtml(r.id) +
        '">' +
        escapeHtml(rawText.slice(r.start, r.end)) +
        "</mark>";
      i = r.end;
    });
    if (i < rawText.length) html += escapeHtml(rawText.slice(i));
    var trunc = root.getAttribute("data-truncated") === "1";
    if (trunc) html += "\n\n… (truncated)";
    root.innerHTML = html || escapeHtml(rawText);
  }

  function selectFinding(id) {
    document.querySelectorAll(".clause-mark.active").forEach(function (el) {
      el.classList.remove("active");
    });
    document.querySelectorAll(".finding.active").forEach(function (el) {
      el.classList.remove("active");
    });
    var mark = document.getElementById("mark-" + id);
    var card = document.querySelector('.finding[data-finding-id="' + id + '"]');
    if (mark) {
      mark.classList.add("active");
      mark.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    if (card) card.classList.add("active");
  }

  render();

  root.addEventListener("click", function (ev) {
    var mark = ev.target.closest(".clause-mark");
    if (!mark) return;
    selectFinding(mark.getAttribute("data-finding"));
  });

  document.querySelectorAll(".finding[data-finding-id]").forEach(function (card) {
    card.addEventListener("click", function (ev) {
      if (ev.target.closest("a, button")) return;
      selectFinding(card.getAttribute("data-finding-id"));
    });
  });
})();
