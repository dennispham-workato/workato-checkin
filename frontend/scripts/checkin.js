// Attendee check-in flow for / (index.html).
// Loaded as a CLASSIC script (not type="module") so the inline on* handlers
// in the markup resolve to these top-level functions. Do not convert to a module.

  const params      = new URLSearchParams(window.location.search);
  const sessionKey  = params.get('key')          || '';
  const sessionDate = params.get('session_date') || '';
  const sessionSig  = params.get('sig')          || '';
  const hasSession  = Boolean(sessionKey && sessionDate);

  // Resolved server-side from the key (best-effort). Stays '' if the lookup is
  // unavailable, so the page gracefully falls back to showing the raw code.
  let sessionName = '';

  window.addEventListener('DOMContentLoaded', () => {
    // No QR params → friendly welcome state instead of a usable form.
    if (!hasSession) {
      showWelcome();
      return;
    }

    // Don't flash the form until we know the link is one we minted.
    document.getElementById('formContent').style.display = 'none';

    const q = 'key=' + encodeURIComponent(sessionKey) +
              '&session_date=' + encodeURIComponent(sessionDate) +
              '&sig=' + encodeURIComponent(sessionSig);

    fetch('/api/verify?' + q)
      .then(res => res.json().catch(() => ({})))
      .then(data => {
        // Reject only on an explicit invalid; fail open otherwise (submit re-checks).
        if (data && data.valid === false) { showInvalid(); return; }
        if (data && data.session_name) sessionName = data.session_name;
        setupForm();
      })
      .catch(() => setupForm());
  });

  function setupForm() {
    document.getElementById('formContent').style.display = '';
    document.getElementById('sessionKey').textContent  = sessionName || sessionKey;
    document.getElementById('sessionDate').textContent = sessionDate;
    document.getElementById('sessionBlock').classList.add('visible');

    wireField('firstNameInput', 'firstNameHint', '');
    wireField('lastNameInput',  'lastNameHint',  '');
    wireField('emailInput',     'emailHint',     'Use the email address registered with your training');

    // Auto-focus on desktop, not mobile (avoid keyboard popping up on scan)
    if (window.innerWidth > 480) document.getElementById('firstNameInput').focus();
  }

  // Clear a field's error on input + submit on Enter.
  function wireField(inputId, hintId, defaultText) {
    const input = document.getElementById(inputId);
    const hint  = document.getElementById(hintId);
    input.addEventListener('input', () => {
      input.classList.remove('invalid');
      hint.textContent = defaultText;
      hint.classList.remove('error');
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); submitCheckin(); }
    });
  }

  function fieldError(input, hint, message) {
    input.classList.remove('invalid');
    void input.offsetWidth; // restart the shake animation
    input.classList.add('invalid');
    hint.textContent = message;
    hint.classList.add('error');
    input.focus();
  }

  function showInvalid() {
    document.querySelector('.card-body').classList.add('welcome');
    document.querySelector('.pre-header').textContent = 'Workato Training';
    document.querySelector('h1').textContent          = "This link isn't valid";
    document.querySelector('.subtitle').textContent   = 'Please rescan the QR code from your trainer.';
    document.getElementById('formContent').style.display = 'none';
    document.querySelector('.divider').style.display     = 'none';
  }

  function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }

  function submitCheckin() {
    const btn        = document.getElementById('submitBtn');
    const firstInput = document.getElementById('firstNameInput');
    const lastInput  = document.getElementById('lastNameInput');
    const emailInput = document.getElementById('emailInput');

    const firstName = firstInput.value.trim();
    const lastName  = lastInput.value.trim();
    const email     = emailInput.value.trim().toLowerCase();

    if (!firstName) {
      fieldError(firstInput, document.getElementById('firstNameHint'), 'Please enter your first name.');
      return;
    }
    if (!lastName) {
      fieldError(lastInput, document.getElementById('lastNameHint'), 'Please enter your last name.');
      return;
    }
    if (!email) {
      fieldError(emailInput, document.getElementById('emailHint'), 'Please enter your email address.');
      return;
    }
    if (!isValidEmail(email)) {
      fieldError(emailInput, document.getElementById('emailHint'), 'Please enter a valid email address.');
      return;
    }

    btn.disabled = true;
    btn.classList.add('loading');

    const statusMsg = document.getElementById('statusMsg');
    statusMsg.classList.remove('error');
    statusMsg.style.display = 'none';

    // Submit through our serverless proxy, which forwards to Workato server-side.
    fetch('/api/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ first_name: firstName, last_name: lastName, email: email, key: sessionKey, session_date: sessionDate, sig: sessionSig })
    })
    .then(res => res.json().catch(() => ({})))
    .then(data => {
      if (data && data.status === 'submitted') {
        showSuccess(email);
      } else {
        btn.classList.remove('loading');
        btn.disabled = false;
        statusMsg.textContent = (data && data.message) || "Couldn't save your check-in. Please try again.";
        statusMsg.classList.add('error');
        statusMsg.style.display = 'block';
      }
    })
    .catch(() => {
      btn.classList.remove('loading');
      btn.disabled = false;
      statusMsg.textContent = "Couldn't save your check-in. Please try again.";
      statusMsg.classList.add('error');
      statusMsg.style.display = 'block';
    });
  }

  function showWelcome() {
    document.querySelector('.card-body').classList.add('welcome');
    document.querySelector('.pre-header').textContent = 'Workato Training';
    document.querySelector('h1').textContent          = 'Welcome to your Workato training!';
    document.querySelector('.subtitle').textContent   = "Scan your session's QR code to check in.";
    document.getElementById('formContent').style.display = 'none';
    document.querySelector('.divider').style.display     = 'none';
  }

  function showSuccess(email) {
    document.getElementById('formContent').style.display  = 'none';
    document.getElementById('sessionBlock').style.display = 'none';
    document.getElementById('warningBox').style.display   = 'none';
    document.querySelector('.pre-header').textContent     = 'Training Attendance';
    document.querySelector('h1').textContent              = "You're in!";
    document.querySelector('.subtitle').style.display     = 'none';
    document.querySelector('.divider').style.display      = 'none';
    document.getElementById('successScreen').classList.add('visible');
    document.getElementById('successEmail').textContent   = email;
    document.getElementById('metaKey').textContent        = sessionName || sessionKey || '—';
    document.getElementById('metaDate').textContent       = sessionDate || '—';
  }
