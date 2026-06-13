// Trainer QR-code generator for /team (generator.html).
// Loaded as a CLASSIC script (not type="module") so the inline on* handlers
// in the markup resolve to these top-level functions. Do not convert to a module.

  // Derive from the current origin so new QR codes point at this site's canonical
  // check-in landing (served at "/"), e.g. https://workato-training.vercel.app/
  var CHECKIN_BASE_URL = window.location.origin + "/";
  var LOGO_ICON_SRC    = "data:image/png;base64,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";

  var SURVEYS = [
    { value: "https://workato.qualtrics.com/jfe/form/SV_ePbryYXIurQPztY", label: "Standard | Post-Training Survey" },
    { value: "https://workato.qualtrics.com/jfe/form/SV_beaIryPcJ6eQezA", label: "Agentic | Post-Training Survey" },
    { value: "https://workato.qualtrics.com/jfe/form/SV_e4nM23fn6HvOQEC", label: "MCP | Post-Training Survey" }
  ];

  var dateCount   = 0;
  var qualtricsOn = false;
  var SESSIONS    = [];   // [{key,name}] loaded from /api/sessions
  var CURRICULA   = [];   // [{label,name}] loaded from /api/curricula
  var comboShown  = [];   // sessions currently rendered in the dropdown (post-filter)
  var comboIdx    = -1;   // index into comboShown for keyboard highlight

  window.onload = function() {
    // Stay unlocked across reloads within the same browser session.
    if (sessionStorage.getItem("trainerOk") === "1") unlockUI();
    addDate(new Date().toISOString().split("T")[0]);
  };

  function unlockUI() {
    document.getElementById("gate").style.display = "none";
    document.getElementById("trainerPanel").style.display = "";
    loadSessions();
    loadCurricula();
  }

  // Populate the Session combobox from /api/sessions. Token-gated when signing
  // is configured (open in demo mode). Covers both fresh login and the
  // reload-with-trainerOk path, since unlockUI() runs in each.
  function loadSessions() {
    var search = document.getElementById("sessionSearch");
    clearSession();
    SESSIONS = [];
    search.disabled = true;
    search.placeholder = "Loading sessions…";
    fetch("/api/sessions", { headers: { "X-Trainer-Token": sessionStorage.getItem("trainerToken") || "" } })
    .then(function(res) {
      return res.json().catch(function(){ return {}; }).then(function(j){ return { status: res.status, body: j }; });
    })
    .then(function(r) {
      if (r.status === 401) {
        lock("Your trainer session expired — please sign in again.");
        return;
      }
      var sessions = (r.body && Array.isArray(r.body.sessions)) ? r.body.sessions : null;
      if (!sessions) {
        search.disabled = true;
        search.placeholder = "Couldn't load — refresh to retry";
        onInput();
        return;
      }
      SESSIONS = sessions;
      search.disabled = false;
      search.placeholder = "Search by name or ID…";
      onInput();
    })
    .catch(function() {
      search.disabled = true;
      search.placeholder = "Couldn't load — refresh to retry";
      onInput();
    });
  }

  // Load the curriculum checkboxes from /api/curricula. Mirrors loadSessions():
  // same X-Trainer-Token header and 401 -> lock() handling. Covers both fresh
  // login and the reload-with-trainerOk path, since unlockUI() runs in each.
  function loadCurricula() {
    renderCurriculaNote("Loading curricula…");
    fetch("/api/curricula", { headers: { "X-Trainer-Token": sessionStorage.getItem("trainerToken") || "" } })
      .then(function(res){ return res.json().catch(function(){return{};}).then(function(j){return {status:res.status, body:j};}); })
      .then(function(r){
        if (r.status === 401) { lock("Your trainer session expired — please sign in again."); return; }
        CURRICULA = (r.body && Array.isArray(r.body.curricula)) ? r.body.curricula : [];
        renderCurricula();
        onInput();
      })
      .catch(function(){ renderCurricula(true); });   // true = show error note
  }

  // Clear everything we previously injected into #curriculumChecks (every child
  // except the untouched "Other" row) and return that row as the insert anchor.
  function clearInjectedCurricula() {
    var box      = document.getElementById("curriculumChecks");
    var other    = box.querySelector("input[value='__other__']");
    var anchor   = other ? other.closest(".check-opt") : null;
    var children = box.children;
    for (var i = children.length - 1; i >= 0; i--) {
      if (children[i] !== anchor) box.removeChild(children[i]);
    }
    return anchor;
  }

  // Show a .combo-msg note (loading / error) above the Other row.
  function renderCurriculaNote(text) {
    var anchor = clearInjectedCurricula();
    var msg = document.createElement("div");
    msg.className = "combo-msg";
    msg.textContent = text;
    document.getElementById("curriculumChecks").insertBefore(msg, anchor);
  }

  // Render one .check-opt per curriculum into #curriculumChecks, inserted before
  // the (untouched) "Other" row. Reproduces the previously-hardcoded markup so
  // the look and the URL params (value = name, data-label = "Label (NAME)") are
  // unchanged. Clears any previously-injected rows first so re-renders are clean.
  function renderCurricula(failed) {
    if (failed) { renderCurriculaNote("Couldn't load — refresh to retry"); return; }
    var box    = document.getElementById("curriculumChecks");
    var anchor = clearInjectedCurricula();

    for (var c = 0; c < CURRICULA.length; c++) {
      var label = CURRICULA[c].label;
      var name  = CURRICULA[c].name;
      var code  = name.toUpperCase();
      var opt   = document.createElement("label");
      opt.className = "check-opt";
      opt.innerHTML =
        "<input type='checkbox' value='" + esc(name) + "'"
        + " data-label='" + esc(label + " (" + code + ")") + "'"
        + " onchange='onCheckChange(this)'/>"
        + "<span>" + esc(label) + " <strong>(" + esc(code) + ")</strong></span>";
      box.insertBefore(opt, anchor);
    }
  }

  // ---- Session combobox: a text input that filters SESSIONS into a dropdown.
  // The chosen key/name live on the hidden #session input so getKey()/
  // getSessionName() keep their contract (value = key, dataset.name = name).
  function clearSession() {
    var hidden = document.getElementById("session");
    hidden.value = "";
    hidden.removeAttribute("data-name");
  }

  function renderSessionList(query) {
    var q    = (query || "").trim().toLowerCase();
    var list = document.getElementById("sessionList");
    comboShown = SESSIONS.filter(function(s) {
      return !q || s.name.toLowerCase().indexOf(q) !== -1 || s.key.toLowerCase().indexOf(q) !== -1;
    });
    comboIdx = -1;
    if (!comboShown.length) {
      list.innerHTML = '<div class="combo-msg">' + (SESSIONS.length ? "No matches" : "No sessions available") + "</div>";
      return;
    }
    var html = "";
    for (var i = 0; i < comboShown.length; i++) {
      html += '<div class="combo-opt" role="option" data-i="' + i + '">'
            +   '<span class="opt-id">' + esc(comboShown[i].key) + '</span>'
            +   '<span class="opt-name">' + esc(comboShown[i].name) + '</span>'
            + '</div>';
    }
    list.innerHTML = html;
    // mousedown (not click) so selection runs before the input's blur closes the list.
    var opts = list.querySelectorAll(".combo-opt");
    for (var k = 0; k < opts.length; k++) {
      opts[k].addEventListener("mousedown", function(e) {
        e.preventDefault(); // keep focus on the input
        selectSession(parseInt(this.getAttribute("data-i"), 10));
      });
    }
  }

  function openSessionList() {
    if (document.getElementById("sessionSearch").disabled) return;
    renderSessionList("");                       // focus shows the full list
    document.getElementById("sessionSearch").select();
    setListOpen(true);
  }

  function filterSessions() {
    // Typing invalidates any prior pick until a new one is chosen.
    clearSession();
    renderSessionList(document.getElementById("sessionSearch").value);
    setListOpen(true);
    onInput();
  }

  function selectSession(i) {
    var s = comboShown[i];
    if (!s) return;
    var hidden = document.getElementById("session");
    hidden.value = s.key;
    hidden.setAttribute("data-name", s.name);
    document.getElementById("sessionSearch").value = s.key + " | " + s.name;
    setListOpen(false);
    onInput();
  }

  function setListOpen(open) {
    var list = document.getElementById("sessionList");
    list.className = open ? "combo-list open" : "combo-list";
    document.getElementById("sessionSearch").setAttribute("aria-expanded", open ? "true" : "false");
    if (!open) highlight(-1);
  }

  function closeSessionList() { setListOpen(false); }
  // Delay so a click on an option (mousedown) lands before blur hides the list.
  function closeSessionListSoon() { setTimeout(closeSessionList, 150); }

  function highlight(idx) {
    var opts = document.getElementById("sessionList").querySelectorAll(".combo-opt");
    for (var i = 0; i < opts.length; i++) {
      opts[i].className = (i === idx) ? "combo-opt active" : "combo-opt";
    }
    comboIdx = idx;
    if (idx >= 0 && opts[idx]) opts[idx].scrollIntoView({ block: "nearest" });
  }

  function sessionKeydown(e) {
    var open = document.getElementById("sessionList").className.indexOf("open") !== -1;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) { openSessionList(); return; }
      if (comboShown.length) highlight((comboIdx + 1) % comboShown.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (comboShown.length) highlight((comboIdx - 1 + comboShown.length) % comboShown.length);
    } else if (e.key === "Enter") {
      if (open && comboShown.length) {
        e.preventDefault();
        selectSession(comboIdx >= 0 ? comboIdx : 0);  // Enter picks the highlighted (or first) match
      }
    } else if (e.key === "Escape") {
      setListOpen(false);
    }
  }

  // Re-lock when the trainer token is rejected (e.g. expired mid-session).
  function lock(message) {
    sessionStorage.removeItem("trainerOk");
    sessionStorage.removeItem("trainerToken");
    document.getElementById("trainerPanel").style.display = "none";
    document.getElementById("gate").style.display = "";
    var input = document.getElementById("trainerPassword");
    input.value = "";
    var hint = document.getElementById("gateHint");
    hint.textContent = message || "Please sign in again.";
    hint.style.color = "var(--danger)";
    input.focus();
  }

  function unlock() {
    var input = document.getElementById("trainerPassword");
    var hint  = document.getElementById("gateHint");
    var btn   = document.getElementById("unlockBtn");
    var pw    = input.value;
    if (!pw) {
      hint.textContent = "Please enter the trainer password.";
      hint.style.color = "var(--danger)";
      return;
    }
    btn.disabled = true;
    // Only the pass/fail comes back — the password is verified server-side.
    fetch("/api/trainer-login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw })
    })
    .then(function(res) { return res.json().catch(function() { return {}; }); })
    .then(function(data) {
      btn.disabled = false;
      if (data && data.ok) {
        sessionStorage.setItem("trainerOk", "1");
        sessionStorage.setItem("trainerToken", data.token || "");
        unlockUI();
      } else {
        hint.textContent = "Incorrect password. Please try again.";
        hint.style.color = "var(--danger)";
        input.value = "";
        input.focus();
      }
    })
    .catch(function() {
      btn.disabled = false;
      hint.textContent = "Could not verify. Please try again.";
      hint.style.color = "var(--danger)";
    });
  }

  function addDate(defaultVal) {
    dateCount++;
    var id  = "date_" + dateCount;
    var row = document.createElement("div");
    row.className = "date-row";
    row.id = "row_" + id;
    var inp     = document.createElement("input");
    inp.type    = "date";
    inp.id      = id;
    inp.value   = defaultVal || "";
    inp.oninput = onInput;
    var btn       = document.createElement("button");
    btn.className = "btn-remove";
    btn.title     = "Remove";
    btn.innerHTML = "x";
    btn.onclick   = function() { row.remove(); updateRemoveBtns(); onInput(); };
    row.appendChild(inp);
    row.appendChild(btn);
    document.getElementById("dateList").appendChild(row);
    updateRemoveBtns();
    onInput();
  }

  function updateRemoveBtns() {
    var btns = document.querySelectorAll(".btn-remove");
    for (var i = 0; i < btns.length; i++) {
      btns[i].disabled = btns.length === 1;
    }
  }

  function getDates() {
    var inputs = document.querySelectorAll(".date-row input[type=date]");
    var out    = [];
    for (var i = 0; i < inputs.length; i++) {
      if (inputs[i].value) out.push(inputs[i].value);
    }
    return out;
  }

  function getKey() {
    return document.getElementById("session").value;
  }

  function getSessionName() {
    return document.getElementById("session").getAttribute("data-name") || "";
  }

  function onCheckChange(cb) {
    cb.closest(".check-opt").className = cb.checked ? "check-opt selected" : "check-opt";
    onInput();
  }

  function onOtherChange(cb) {
    cb.closest(".check-opt").className = cb.checked ? "check-opt selected" : "check-opt";
    var inp = document.getElementById("curriculumOther");
    if (cb.checked) {
      inp.className = "curriculum-other show";
      inp.focus();
    } else {
      inp.className = "curriculum-other";
      inp.value     = "";
    }
    onInput();
  }

  function getCurriculumParam() {
    var boxes = document.querySelectorAll(".curriculum-checks input[type=checkbox]:checked");
    var parts = [];
    for (var i = 0; i < boxes.length; i++) {
      var val = boxes[i].value;
      if (val === "__other__") {
        var custom = document.getElementById("curriculumOther").value.trim();
        if (custom) parts.push(encodeURIComponent(custom.toLowerCase()));
      } else {
        parts.push(val);
      }
    }
    return parts.join("+");
  }

  function getCurriculumLabel() {
    var boxes  = document.querySelectorAll(".curriculum-checks input[type=checkbox]:checked");
    var labels = [];
    for (var i = 0; i < boxes.length; i++) {
      var val = boxes[i].value;
      if (val === "__other__") {
        var custom = document.getElementById("curriculumOther").value.trim();
        if (custom) labels.push(custom);
      } else {
        labels.push(boxes[i].getAttribute("data-label"));
      }
    }
    return labels.join(", ");
  }

  function toggleQualtrics() {
    qualtricsOn = !qualtricsOn;
    document.getElementById("qualtricsChk").className   = qualtricsOn ? "chk on" : "chk";
    document.getElementById("qualtricsRow").className   = qualtricsOn ? "toggle-row active" : "toggle-row";
    document.getElementById("qualtricsPanel").className = qualtricsOn ? "qualtrics-panel show" : "qualtrics-panel";
    onInput();
  }

  // Build one survey <select> per session date into #surveyAssignments,
  // preserving prior picks keyed by the raw YYYY-MM-DD date string so that
  // adding/removing/reordering dates keeps each day's choice attached to its
  // date. Guarded by a date signature so it only rebuilds when the date set
  // actually changes — otherwise a survey <select> firing onInput() would
  // clobber the pick the trainer just made.
  function renderSurveyAssignments() {
    var box   = document.getElementById("surveyAssignments");
    var dates = getDates();
    var sig   = dates.join(",");
    if (box.dataset.sig === sig && box.children.length) return; // dates unchanged

    var prev = {};                              // preserve current picks by date
    var rows = box.querySelectorAll(".survey-assign-row");
    for (var r = 0; r < rows.length; r++) prev[rows[r].dataset.date] = rows[r].querySelector("select").value;

    box.innerHTML = "";
    for (var i = 0; i < dates.length; i++) {
      var d = dates[i];
      var row = document.createElement("div");
      row.className = "survey-assign-row";
      row.dataset.date = d;

      var label = document.createElement("div");
      label.className = "survey-assign-label";
      label.innerHTML = "<span class='sa-day'>Day " + (i + 1) + "</span>"
                      + "<span class='sa-date'>" + esc(fmtDisplay(d)) + "</span>";

      var sel = document.createElement("select");
      sel.className = "survey-select";
      sel.onchange  = onInput;
      var opts = "<option value=''>Select a survey…</option>";
      for (var s = 0; s < SURVEYS.length; s++)
        opts += "<option value='" + esc(SURVEYS[s].value) + "'>" + esc(SURVEYS[s].label) + "</option>";
      sel.innerHTML = opts;
      if (prev[d]) sel.value = prev[d];

      row.appendChild(label);
      row.appendChild(sel);
      box.appendChild(row);
    }
    box.dataset.sig = sig;
  }

  // Map of raw YYYY-MM-DD date string -> chosen survey URL (blank if unset),
  // in the same order as getDates().
  function getSurveyByDate() {
    var out  = {};
    var rows = document.querySelectorAll("#surveyAssignments .survey-assign-row");
    for (var i = 0; i < rows.length; i++) {
      out[rows[i].dataset.date] = rows[i].querySelector("select").value;
    }
    return out;
  }

  // True only when every session date has a non-empty survey pick.
  function allDaysHaveSurvey() {
    var dates = getDates();
    if (!dates.length) return false;
    var map = getSurveyByDate();
    for (var i = 0; i < dates.length; i++) {
      if (!map[dates[i]]) return false;
    }
    return true;
  }

  function onInput() {
    var key        = getKey();
    var sname      = getSessionName();
    var curriculum = getCurriculumParam();
    var dates      = getDates();
    if (qualtricsOn) renderSurveyAssignments();
    var surveyOk   = !qualtricsOn || allDaysHaveSurvey();
    var otherBox   = document.querySelector(".curriculum-checks input[value='__other__']");
    var otherOk    = !otherBox || !otherBox.checked || document.getElementById("curriculumOther").value.trim();
    var valid      = key && sname && curriculum && otherOk && dates.length > 0 && surveyOk;
    var btn        = document.getElementById("generateBtn");
    btn.disabled   = !valid;
    if (valid) {
      var n     = dates.length;
      var types = qualtricsOn ? 2 : 1;
      var total = n * types;
      btn.textContent = "Generate " + total + " QR Code" + (total > 1 ? "s" : "");
    } else {
      btn.textContent = "Generate QR Codes";
    }
  }

  function fmt(d) { var p = d.split("-"); return p[1]+"-"+p[2]+"-"+p[0]; }
  function fmtDisplay(d) {
    var p = d.split("-");
    var m = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return m[parseInt(p[1],10)-1]+" "+parseInt(p[2],10)+", "+p[0];
  }
  function esc(s) {
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }
  function slug(s) { return encodeURIComponent(s.toLowerCase().trim()); }

  function switchTab(type) {
    document.getElementById("tabCheckin").className   = type==="checkin" ? "qr-tab active" : "qr-tab";
    document.getElementById("tabSurvey").className    = type==="survey"  ? "qr-tab active" : "qr-tab";
    document.getElementById("groupCheckin").className = type==="checkin" ? "qr-group active" : "qr-group";
    document.getElementById("groupSurvey").className  = type==="survey"  ? "qr-group active" : "qr-group";
  }

  function generateAll() {
    var key   = getKey();
    var dates = getDates();

    // Ask the server to sign each check-in session first — only a signed link
    // is honored at check-in, so guessed/edited URLs won't work.
    var items = [];
    for (var i = 0; i < dates.length; i++) {
      items.push({ key: key, session_date: fmt(dates[i]) });
    }

    var btn = document.getElementById("generateBtn");
    btn.disabled = true;

    fetch("/api/sign", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: sessionStorage.getItem("trainerToken") || "", items: items })
    })
    .then(function(res) {
      return res.json().catch(function(){ return {}; }).then(function(j){ return { status: res.status, body: j }; });
    })
    .then(function(r) {
      btn.disabled = false;
      if (r.status === 401) {
        lock("Your trainer session expired — please sign in again.");
        return;
      }
      if (!r.body || !r.body.ok) {
        return; // unexpected; leave UI as-is
      }
      var sigByDate = {};
      var out = r.body.items || [];
      for (var k = 0; k < out.length; k++) sigByDate[out[k].session_date] = out[k].sig;
      renderAll(sigByDate);
    })
    .catch(function() {
      btn.disabled = false;
    });
  }

  function renderAll(sigByDate) {
    var key        = getKey();
    var sname      = getSessionName();
    var cParam     = getCurriculumParam();
    var cLabel     = getCurriculumLabel();
    var dates        = getDates();
    var surveyByDate = qualtricsOn ? getSurveyByDate() : null;

    document.getElementById("gridCheckin").innerHTML = "";
    document.getElementById("gridSurvey").innerHTML  = "";

    for (var i = 0; i < dates.length; i++) {
      var date    = fmt(dates[i]);
      var display = fmtDisplay(dates[i]);
      var sig     = sigByDate[date];
      var ciUrl   = CHECKIN_BASE_URL+"?key="+encodeURIComponent(key)+"&session_date="+encodeURIComponent(date)
                    + (sig ? "&sig="+encodeURIComponent(sig) : "");
      buildCard("gridCheckin","ci_"+i, i, key, sname, cLabel, display, date, ciUrl);
    }

    if (qualtricsOn) {
      for (var j = 0; j < dates.length; j++) {
        var raw  = dates[j];
        var base = surveyByDate[raw];
        if (!base) continue;                       // safety; validation prevents this
        var date2    = fmt(raw);
        var display2 = fmtDisplay(raw);
        var svUrl    = base
          +"?training_name="+cParam
          +"&session_date=" +encodeURIComponent(date2)
          +"&session_name=" +slug(sname)
          +"&key="          +encodeURIComponent(key);
        buildCard("gridSurvey","sv_"+j, j, key, sname, cLabel, display2, date2, svUrl);
      }
    }

    var tabs = document.getElementById("qrTabs");
    tabs.style.display = qualtricsOn ? "flex" : "none";
    if (qualtricsOn) switchTab("checkin");

    var total = dates.length * (qualtricsOn ? 2 : 1);
    document.getElementById("sectionTitle").textContent =
      key+" - "+total+" QR Code"+(total>1?"s":"");

    var sec = document.getElementById("qrSection");
    sec.className = "qr-section show";
    setTimeout(function() { sec.scrollIntoView({behavior:"smooth",block:"start"}); }, 100);
  }

  function buildCard(gridId, qrId, dayIdx, key, sname, cLabel, dateDisplay, dateParam, url) {
    var item = document.createElement("div"); item.className = "qr-item";
    var top  = document.createElement("div"); top.className  = "qr-item-top";
    var body = document.createElement("div"); body.className = "qr-item-body";
    var day  = document.createElement("div"); day.className  = "qr-item-day";
    day.textContent = "Day "+(dayIdx+1);

    var wrap    = document.createElement("div"); wrap.className = "qr-wrap";
    var canvas  = document.createElement("canvas");
    canvas.id   = qrId;
    canvas.style.cssText = "width:200px;height:200px;display:block;border-radius:4px;";
    canvas.width  = 400;
    canvas.height = 400;
    wrap.appendChild(canvas);

    var meta = document.createElement("div"); meta.className = "qr-meta";
    meta.innerHTML =
      "<div class='qr-meta-row'><span class='qr-meta-label'>Key</span><span class='qr-meta-val'> "+esc(key)+"</span></div>"+
      "<div class='qr-meta-row'><span class='qr-meta-label'>Session</span><span class='qr-meta-val'>"+esc(sname)+"</span></div>"+
      "<div class='qr-meta-row'><span class='qr-meta-label'>Curriculum</span><span class='qr-meta-val'>"+esc(cLabel)+"</span></div>"+
      "<div class='qr-meta-row'><span class='qr-meta-label'>Date</span><span class='qr-meta-val'>"+esc(dateDisplay)+"</span></div>";

    body.appendChild(day);
    body.appendChild(wrap);
    body.appendChild(meta);

    var footer  = document.createElement("div"); footer.className = "qr-item-footer";
    var urlDiv  = document.createElement("div"); urlDiv.className  = "qr-url";
    var urlLink = document.createElement("a");
    urlLink.href        = url;
    urlLink.target      = "_blank";
    urlLink.rel         = "noopener";
    urlLink.textContent = url;
    urlDiv.appendChild(urlLink);
    footer.appendChild(urlDiv);

    var dlBtn = document.createElement("button"); dlBtn.className = "btn-dl";
    dlBtn.textContent = "Download";
    (function(id,k,dp){ dlBtn.onclick = function(){ downloadSingle(id,k,dp); }; })(qrId,key,dateParam);
    footer.appendChild(dlBtn);

    item.appendChild(top);
    item.appendChild(body);
    item.appendChild(footer);
    document.getElementById(gridId).appendChild(item);

    // Render the QR straight into the card canvas at high res, then composite
    // the logo on top. node-qrcode encodes long URLs at the highest correction
    // level (H) reliably — survey URLs embed the full session name and can be
    // long, which the previous library choked on and left the canvas blank.
    var target = document.getElementById(qrId);
    if (target) {
      QRCode.toCanvas(target, url, {
        width: 400,
        margin: 1,
        errorCorrectionLevel: "H",
        color: { dark: "#111010", light: "#ffffff" }
      }, function(err){
        if (err) { console.error("QR render failed for " + qrId, err); return; }
        // toCanvas overwrites the element's inline size; restore the 200px
        // display footprint (the 400px backing store is kept for crisp prints
        // and downloads).
        target.style.cssText = "width:200px;height:200px;display:block;border-radius:4px;";
        compositeLogoOnCanvas(target.getContext("2d"), target);
      });
    }
  }

  function compositeLogoOnCanvas(ctx, canvas) {
    var icon = new Image();
    icon.onload = function() {
      var size  = canvas.width;
      var box   = Math.round(size * 0.18);
      var pad   = Math.round(box * 0.12);
      var bx    = Math.round((size - box) / 2);
      var by    = Math.round((size - box) / 2);
      // White square backing
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(bx - pad, by - pad, box + pad*2, box + pad*2);
      // Draw logo preserving natural ratio
      var natW  = icon.naturalWidth  || box;
      var natH  = icon.naturalHeight || box;
      var scale = Math.min(box / natW, box / natH);
      var dw    = Math.round(natW * scale);
      var dh    = Math.round(natH * scale);
      var dx    = bx + Math.round((box - dw) / 2);
      var dy    = by + Math.round((box - dh) / 2);
      ctx.drawImage(icon, dx, dy, dw, dh);
    };
    icon.src = LOGO_ICON_SRC;
  }

  function downloadSingle(qrId, key, date) {
    var canvas = document.getElementById(qrId);
    if (!canvas || canvas.tagName !== "CANVAS") return;
    var suffix   = qrId.indexOf("sv") === 0 ? "survey" : "checkin";
    var filename = "qr_class"+key.replace(/[^a-zA-Z0-9-]/g,"_")+"_"+date+"_"+suffix+".png";
    var link     = document.createElement("a");
    link.download = filename;
    link.href     = canvas.toDataURL("image/png");
    link.click();
  }

  function downloadAll() {
    var key   = getKey();
    var dates = getDates();
    var delay = 0;
    for (var i = 0; i < dates.length; i++) {
      (function(idx,d){
        setTimeout(function(){ downloadSingle("ci_"+idx, key, fmt(d)); }, delay);
        delay += 400;
        if (qualtricsOn) {
          setTimeout(function(){ downloadSingle("sv_"+idx, key, fmt(d)); }, delay);
          delay += 400;
        }
      })(i, dates[i]);
    }
  }
