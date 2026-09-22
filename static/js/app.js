document.addEventListener('DOMContentLoaded', () => {
    const tabAuditor = document.getElementById('tabAuditor');
    const tabGenerator = document.getElementById('tabGenerator');
    const panelAuditor = document.getElementById('panelAuditor');
    const panelGenerator = document.getElementById('panelGenerator');

    const passwordInput = document.getElementById('passwordInput');
    const charCount = document.getElementById('charCount');
    const btnToggleVis = document.getElementById('btnToggleVis');
    const btnCopyAudit = document.getElementById('btnCopyAudit');
    const btnClearInput = document.getElementById('btnClearInput');

    const ratingLabel = document.getElementById('ratingLabel');
    const ratingSubtitle = document.getElementById('ratingSubtitle');
    const scoreNumber = document.getElementById('scoreNumber');
    const scoreRingVal = document.getElementById('scoreRingVal');
    const mainCard = document.getElementById('mainCard');
    const segments = [0, 1, 2, 3, 4].map(i => document.getElementById('seg' + i));

    const entropyVal = document.getElementById('entropyVal');
    const crackVal = document.getElementById('crackVal');
    const onlineCrackVal = document.getElementById('onlineCrackVal');

    const compLower = document.getElementById('compLower');
    const compUpper = document.getElementById('compUpper');
    const compDigits = document.getElementById('compDigits');
    const compSymbols = document.getElementById('compSymbols');
    const cntLower = document.getElementById('cntLower');
    const cntUpper = document.getElementById('cntUpper');
    const cntDigits = document.getElementById('cntDigits');
    const cntSymbols = document.getElementById('cntSymbols');

    const criteriaPassedCount = document.getElementById('criteriaPassedCount');
    const feedbackList = document.getElementById('feedbackList');

    const btnScanHibp = document.getElementById('btnScanHibp');
    const hibpStatus = document.getElementById('hibpStatus');

    const genPasswordOutput = document.getElementById('genPasswordOutput');
    const genTierBadge = document.getElementById('genTierBadge');
    const btnReroll = document.getElementById('btnReroll');
    const btnCopyGen = document.getElementById('btnCopyGen');
    const btnGenerateNow = document.getElementById('btnGenerateNow');
    const btnAuditGen = document.getElementById('btnAuditGen');

    const lengthSlider = document.getElementById('lengthSlider');
    const lengthDisplay = document.getElementById('lengthDisplay');
    const presetButtons = document.querySelectorAll('.btn-preset');

    const optUpper = document.getElementById('optUpper');
    const optLower = document.getElementById('optLower');
    const optDigits = document.getElementById('optDigits');
    const optSymbols = document.getElementById('optSymbols');
    const optAmbiguous = document.getElementById('optAmbiguous');

    const toast = document.getElementById('toast');

    let debounceTimer = null;
    let toastTimer = null;

    function switchTab(target) {
        if (target === 'auditor') {
            tabAuditor.classList.add('active');
            tabAuditor.setAttribute('aria-selected', 'true');
            tabGenerator.classList.remove('active');
            tabGenerator.setAttribute('aria-selected', 'false');

            panelAuditor.classList.add('active');
            panelGenerator.classList.remove('active');
            passwordInput.focus();
        } else {
            tabGenerator.classList.add('active');
            tabGenerator.setAttribute('aria-selected', 'true');
            tabAuditor.classList.remove('active');
            tabAuditor.setAttribute('aria-selected', 'false');

            panelGenerator.classList.add('active');
            panelAuditor.classList.remove('active');

            if (genPasswordOutput.value === 'Click Generate...') {
                generateSecurePassword();
            }
        }
    }

    tabAuditor.addEventListener('click', () => switchTab('auditor'));
    tabGenerator.addEventListener('click', () => switchTab('generator'));

    passwordInput.addEventListener('input', () => {
        const len = passwordInput.value.length;
        charCount.textContent = `${len} char${len === 1 ? '' : 's'}`;

        hibpStatus.className = 'hibp-output';
        hibpStatus.style.display = 'none';

        clearTimeout(debounceTimer);
        if (!passwordInput.value) {
            resetAuditorView();
            return;
        }
        debounceTimer = setTimeout(auditPassword, 120);
    });

    btnToggleVis.addEventListener('click', () => {
        const isPass = passwordInput.type === 'password';
        passwordInput.type = isPass ? 'text' : 'password';
        btnToggleVis.textContent = isPass ? '🔒' : '👁️';
    });

    btnCopyAudit.addEventListener('click', () => {
        if (!passwordInput.value) {
            showToast('⚠️ No password to copy');
            return;
        }
        navigator.clipboard.writeText(passwordInput.value)
            .then(() => showToast('📋 Copied to clipboard!'))
            .catch(() => showToast('❌ Failed to copy'));
    });

    btnClearInput.addEventListener('click', () => {
        passwordInput.value = '';
        passwordInput.dispatchEvent(new Event('input'));
        passwordInput.focus();
    });

    btnScanHibp.addEventListener('click', scanHibpBreach);

    function auditPassword() {
        const pwd = passwordInput.value;
        if (!pwd) {
            resetAuditorView();
            return;
        }

        fetch('/api/check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: pwd })
        })
        .then(res => res.json())
        .then(data => renderAuditorResults(data))
        .catch(err => console.error('Audit failed:', err));
    }

    function renderAuditorResults(data) {
        ratingLabel.textContent = data.rating;
        ratingLabel.style.color = data.color;
        ratingSubtitle.textContent = data.subtitle;

        const pct = data.score_pct;
        scoreNumber.textContent = `${pct}%`;
        scoreRingVal.setAttribute('stroke-dasharray', `${pct}, 100`);
        scoreRingVal.style.stroke = data.color;

        mainCard.style.boxShadow = `0 25px 70px rgba(0, 0, 0, 0.6), 0 0 40px ${data.glow}`;

        segments.forEach((seg, i) => {
            seg.style.background = i <= data.tier ? data.color : 'var(--surface-3)';
            seg.style.boxShadow = i <= data.tier ? `0 0 10px ${data.color}` : 'none';
        });

        entropyVal.textContent = `${data.entropy} bits`;
        crackVal.textContent = data.crack_time;
        onlineCrackVal.textContent = data.crack_time_online;

        const comp = data.composition;
        const total = comp.length || 1;
        compLower.style.width = `${(comp.lower / total) * 100}%`;
        compUpper.style.width = `${(comp.upper / total) * 100}%`;
        compDigits.style.width = `${(comp.digits / total) * 100}%`;
        compSymbols.style.width = `${(comp.symbols / total) * 100}%`;

        cntLower.textContent = comp.lower;
        cntUpper.textContent = comp.upper;
        cntDigits.textContent = comp.digits;
        cntSymbols.textContent = comp.symbols;

        let passedCount = 0;
        const crit = data.criteria;
        if (crit.len_8) passedCount++;
        if (crit.len_12) passedCount++;
        if (crit.has_lower) passedCount++;
        if (crit.has_upper) passedCount++;
        if (crit.has_digit) passedCount++;
        if (crit.has_special) passedCount++;

        criteriaPassedCount.textContent = `${passedCount} / 6 Passed`;

        updateCritRow('c_len8', crit.len_8);
        updateCritRow('c_len12', crit.len_12);
        updateCritRow('c_lower', crit.has_lower);
        updateCritRow('c_upper', crit.has_upper);
        updateCritRow('c_digit', crit.has_digit);
        updateCritRow('c_special', crit.has_special);

        feedbackList.innerHTML = '';
        if (data.feedback && data.feedback.length > 0) {
            data.feedback.forEach(msg => {
                const li = document.createElement('li');
                li.className = 'feedback-item';
                li.textContent = msg;
                feedbackList.appendChild(li);
            });
        }
    }

    function updateCritRow(id, passed) {
        const row = document.getElementById(id);
        if (!row) return;
        const bullet = row.querySelector('.crit-bullet');
        row.classList.toggle('passed', !!passed);
        if (bullet) {
            bullet.textContent = passed ? '✅' : '⚪';
        }
    }

    function resetAuditorView() {
        ratingLabel.textContent = 'CRITICAL';
        ratingLabel.style.color = 'var(--tier-critical)';
        ratingSubtitle.textContent = 'Enter a password to begin audit';

        scoreNumber.textContent = '0%';
        scoreRingVal.setAttribute('stroke-dasharray', '0, 100');
        scoreRingVal.style.stroke = 'var(--tier-critical)';

        mainCard.style.boxShadow = 'none';
        segments.forEach(seg => {
            seg.style.background = 'var(--surface-3)';
            seg.style.boxShadow = 'none';
        });

        entropyVal.textContent = '0.0 bits';
        crackVal.textContent = 'Instantly';
        onlineCrackVal.textContent = 'Instantly';

        [compLower, compUpper, compDigits, compSymbols].forEach(el => el.style.width = '0%');
        cntLower.textContent = '0';
        cntUpper.textContent = '0';
        cntDigits.textContent = '0';
        cntSymbols.textContent = '0';

        criteriaPassedCount.textContent = '0 / 6 Passed';
        ['c_len8', 'c_len12', 'c_lower', 'c_upper', 'c_digit', 'c_special'].forEach(id => updateCritRow(id, false));
        feedbackList.innerHTML = '<li class="feedback-item">Enter a password above to begin deep analysis.</li>';
    }

    function scanHibpBreach() {
        const pwd = passwordInput.value;
        if (!pwd) {
            showToast('⚠️ Enter a password first');
            return;
        }

        hibpStatus.className = 'hibp-output scanning';
        hibpStatus.style.display = 'block';
        hibpStatus.textContent = '🔍 Querying HIBP database via k-anonymity...';
        btnScanHibp.disabled = true;

        fetch('/api/hibp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: pwd })
        })
        .then(res => res.json())
        .then(data => {
            if (data.breached === true) {
                hibpStatus.className = 'hibp-output breached';
                hibpStatus.textContent = `⚠️ BREACH ALERT: Exposed in ${data.count.toLocaleString()} data breaches! Do NOT use.`;
            } else if (data.breached === false) {
                hibpStatus.className = 'hibp-output safe';
                hibpStatus.textContent = '🛡️ SAFE: No known exposures found in public breaches.';
            } else {
                hibpStatus.className = 'hibp-output';
                hibpStatus.style.display = 'none';
                showToast('Note: ' + (data.error || 'HIBP unreachable'));
            }
        })
        .catch(() => {
            hibpStatus.className = 'hibp-output';
            hibpStatus.style.display = 'none';
            showToast('Scan error: connection failed');
        })
        .finally(() => {
            btnScanHibp.disabled = false;
        });
    }

    lengthSlider.addEventListener('input', () => {
        const val = parseInt(lengthSlider.value, 10);
        lengthDisplay.textContent = val;

        presetButtons.forEach(btn => {
            const btnLen = parseInt(btn.dataset.length, 10);
            btn.classList.toggle('active', btnLen === val);
        });

        generateSecurePassword();
    });

    presetButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const val = parseInt(btn.dataset.length, 10);
            lengthSlider.value = val;
            lengthDisplay.textContent = val;

            presetButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            generateSecurePassword();
        });
    });

    [optUpper, optLower, optDigits, optSymbols, optAmbiguous].forEach(opt => {
        opt.addEventListener('change', generateSecurePassword);
    });

    btnReroll.addEventListener('click', () => {
        btnReroll.style.transform = 'rotate(360deg)';
        setTimeout(() => { btnReroll.style.transform = ''; }, 300);
        generateSecurePassword();
    });

    btnGenerateNow.addEventListener('click', generateSecurePassword);

    btnCopyGen.addEventListener('click', () => {
        const pwd = genPasswordOutput.value;
        if (!pwd || pwd === 'Click Generate...') return;
        navigator.clipboard.writeText(pwd)
            .then(() => showToast('📋 Generated password copied!'))
            .catch(() => showToast('❌ Failed to copy'));
    });

    btnAuditGen.addEventListener('click', () => {
        const pwd = genPasswordOutput.value;
        if (!pwd || pwd === 'Click Generate...') return;
        
        switchTab('auditor');
        passwordInput.value = pwd;
        passwordInput.type = 'text';
        btnToggleVis.textContent = '🔒';
        passwordInput.dispatchEvent(new Event('input'));
        showToast('🔍 Auditing generated password...');
    });

    function generateSecurePassword() {
        let length = parseInt(lengthSlider.value, 10);
        if (isNaN(length) || length < 8) length = 8;
        if (length > 20) length = 20;

        const payload = {
            length: length,
            include_upper: optUpper.checked,
            include_lower: optLower.checked,
            include_digits: optDigits.checked,
            include_symbols: optSymbols.checked,
            exclude_ambiguous: optAmbiguous.checked
        };

        fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            genPasswordOutput.value = data.password;
            if (data.assessment) {
                genTierBadge.textContent = data.assessment.rating;
                genTierBadge.style.color = data.assessment.color;
                genTierBadge.style.borderColor = data.assessment.color;
                genTierBadge.style.background = data.assessment.glow;
            }
        })
        .catch(err => console.error('Generation failed:', err));
    }

    function showToast(msg) {
        toast.textContent = msg;
        toast.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.remove('show'), 2200);
    }
});
