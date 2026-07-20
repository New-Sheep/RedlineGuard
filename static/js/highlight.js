/**
 * Paint playbook hits into the document pane.
 * Prefers start/end offsets; falls back to fuzzy excerpt search.
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
  if (typeof rawText !== "string") rawText = String(rawText || "");

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

  function normalizeWs(s) {
    return String(s || "").replace(/\s+/g, " ").trim();
  }

  /** Find excerpt in rawText; tolerate whitespace drift and ellipsis UI clips. */
  function findExcerpt(excerpt) {
    var ex = (excerpt || "").trim();
    if (!ex) return -1;
    var idx = rawText.indexOf(ex);
    if (idx >= 0) return idx;

    var normRaw = normalizeWs(rawText);
    var normEx = normalizeWs(ex);
    if (normEx.length >= 12) {
      var nIdx = normRaw.indexOf(normEx);
      if (nIdx >= 0) {
        // Map normalized index back approximately via unique slice
        var probe = normEx.slice(0, Math.min(48, normEx.length));
        var p = normalizeWs(rawText).indexOf(probe);
        if (p >= 0) {
          // Walk rawText to find similar start
          var compact = "";
          for (var i = 0; i < rawText.length; i++) {
            var ch = rawText[i];
            if (/\s/.test(ch)) {
              if (compact.length && compact[compact.length - 1] !== " ") compact += " ";
            } else {
              compact += ch;
            }
            if (compact.length >= probe.length && compact.slice(-probe.length) === probe) {
              return Math.max(0, i - probe.length + 1);
            }
          }
        }
      }
    }

    // Progressive shorter probes (skip leading ellipsis junk)
    var cleaned = ex.replace(/^\.{2,}\s*/, "").replace(/\s*\.{2,}$/, "");
    var lengths = [80, 48, 32, 24];
    for (var L = 0; L < lengths.length; L++) {
      var n = lengths[L];
      if (cleaned.length < n) continue;
      var slice = cleaned.slice(0, n);
      idx = rawText.indexOf(slice);
      if (idx >= 0) return idx;
      idx = rawText.toLowerCase().indexOf(slice.toLowerCase());
      if (idx >= 0) return idx;
    }
    return -1;
  }

  function ranges() {
    var out = [];
    var len = rawText.length;
    findings.forEach(function (f) {
      var start = Number(f.start) || 0;
      var end = Number(f.end) || 0;
      if (end > start && start < len && end <= len + 1) {
        out.push({
          id: String(f.id),
          start: Math.max(0, start),
          end: Math.min(len, end),
          severity: severityClass(f.severity),
        });
        return;
      }
      // Offsets point past truncated pane — recover via excerpt
      var excerpt = f.excerpt || "";
      var idx = findExcerpt(excerpt);
      if (idx < 0) return;
      var spanLen = Math.min(
        Math.max((excerpt || "").trim().length, 40),
        Math.max(end - start, 280),
        len - idx
      );
      if (spanLen < 8) spanLen = Math.min(120, len - idx);
      out.push({
        id: String(f.id),
        start: idx,
        end: idx + spanLen,
        severity: severityClass(f.severity),
      });
    });
    out.sort(function (a, b) {
      return a.start - b.start || b.end - a.end;
    });
    var cleaned = [];
    var cursor = 0;
    out.forEach(function (r) {
      var s = Math.max(r.start, cursor);
      if (r.end <= s) return;
      cleaned.push({ id: r.id, start: s, end: r.end, severity: r.severity });
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
    root.setAttribute("data-mark-count", String(rs.length));
  }

  function selectFinding(id) {
    id = String(id || "");
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
    } else if (card) {
      // Still highlight the card so click isn't a no-op
      card.classList.add("pulse-miss");
      setTimeout(function () {
        card.classList.remove("pulse-miss");
      }, 900);
    }
    if (card) card.classList.add("active");
  }

  render();
  // Clean / long docs: start at the top (not the empty schedules at the end)
  try {
    root.scrollTop = 0;
  } catch (e) {}

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
