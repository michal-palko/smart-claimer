const form = document.getElementById('entryForm');
const alertBox = document.getElementById('alertBox');
const entriesList = document.getElementById('entriesList');
const editModalEl = document.getElementById('editModal');
const editModal = new bootstrap.Modal(editModalEl, {
    backdrop: true,
    keyboard: true,
    focus: true
});
const editForm = document.getElementById('editForm');

// Set default date to today
function setTodayDate(input) {
    const today = new Date().toISOString().slice(0, 10);
    input.value = today;
}
setTodayDate(document.getElementById('datum'));

// Make date picker appear on click and focus
const datumInput = document.getElementById('datum');
datumInput.addEventListener('click', function(e) {
    // Check if the click was on the calendar icon or anywhere in the field
    this.showPicker();
});
datumInput.addEventListener('focus', function() {
    this.showPicker();
});

// Allow typing and pasting in date field - remove showPicker on input to prevent interference
datumInput.addEventListener('input', function() {
    // Allow normal typing/pasting without triggering picker
});

// Also trigger picker when clicking on the calendar icon specifically
datumInput.addEventListener('mousedown', function(e) {
    // Small delay to ensure the picker shows even when clicking the calendar icon
    setTimeout(() => {
        if (document.activeElement === this) {
            this.showPicker();
        }
    }, 10);
});

function formatTime(h, m) {
    return `${h}h ${m.toString().padStart(2, '0')}m`;
}

function sumEntries(entries) {
    let totalMin = entries.reduce((acc, e) => acc + e.hodiny * 60 + e.minuty, 0);
    return { h: Math.floor(totalMin / 60), m: totalMin % 60 };
}

// Helper function to preserve scroll position during loadEntries()
async function loadEntriesWithScrollPreservation() {
    // Save current scroll position before reload
    const scrollContainer = document.getElementById('entriesList') || document.documentElement;
    const savedScrollTop = scrollContainer.scrollTop;
    
    await loadEntries();
    
    // Restore scroll position after DOM update
    requestAnimationFrame(() => {
        scrollContainer.scrollTop = savedScrollTop;
    });
}

function entryCard(entry) {
    // Only allow edit/delete for own entries
    const isOwn = entry.autor === form.autor.value.trim();
    const canEdit = isOwn;
    const isSubmitted = entry.metaapp_vykaz_id != null;
    return `<div class="card entry-card shadow-sm ${isSubmitted ? 'border-success border-2' : ''}" style="${isSubmitted ? 'box-shadow: 0 0 10px rgba(25, 135, 84, 0.3) !important;' : ''}" data-id="${entry.id}">
        <div class="card-body position-relative" style="min-height: 200px; padding-bottom: 48px;">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <div class="d-flex align-items-center">
                    <span class="badge bg-primary">${entry.uloha}</span>
                    ${entry.uloha_name ? `<span style='font-weight:400;color:#444;margin-left:8px;'>${entry.uloha_name}</span>` : ''}
                </div>
                <span class="d-flex align-items-center">
                  <i class="bi bi-pencil-square edit-btn${canEdit ? '' : ' disabled'}" title="Upraviť"${canEdit ? ` onclick=\"editEntry(${entry.id})\"` : ''}></i>
                  <i class="bi bi-files duplicate-btn ms-2" title="Duplikovať" onclick="duplicateEntry(${entry.id})"></i>
                  <i class="bi bi-x-circle-fill delete-btn ms-2${canEdit ? '' : ' disabled'}" title="Vymazať"${canEdit ? ` onclick=\"deleteEntry(${entry.id})\"` : ''}></i>
                </span>
            </div>
            <div class="mb-1"><strong>Autor:</strong> ${entry.autor}</div>
            <div class="mb-1"><strong>Čas:</strong> ${formatTime(entry.hodiny, entry.minuty)}</div>
            <div class="mb-1"><strong>Dátum:</strong> ${entry.datum}</div>
            ${entry.jira ? `<div class=\"mb-1\"><strong>JIRA:</strong> <span style=\\"color:#0d6efd;\\">${entry.jira}</span>${entry.jira_name ? ` – <span style='font-weight:400;color:#444;'>${entry.jira_name}</span>` : ''}</div>` : ''}
            ${entry.popis ? `<div class=\"mb-1\"><strong>Popis:</strong> ${entry.popis}</div>` : ''}
            <div class="position-absolute start-0 bottom-0 p-2 text-secondary small">
                <i class="bi bi-clock me-1"></i>${new Date(entry.created_at).toLocaleString()}
            </div>
            ${!isSubmitted ? `<div class="position-absolute end-0 bottom-0 p-2">
                <i class="bi bi-cloud-arrow-up-fill text-primary fs-4" style="cursor:pointer;" title="Nahodiť do MetaAppu" onclick="submitToMetaApp(${entry.id})"></i>
            </div>` : ''}
        </div>
    </div>`;
}

function groupBy(arr, keyFn) {
    return arr.reduce((acc, item) => {
        const key = keyFn(item);
        if (!acc[key]) acc[key] = [];
        acc[key].push(item);
        return acc;
    }, {});
}

function getWeekKey(dateStr) {
    const date = new Date(dateStr);
    // Get Monday of the week (ISO week date)
    const day = date.getDay();
    const monday = new Date(date);
    monday.setDate(date.getDate() - (day === 0 ? 6 : day - 1)); // Adjust for Sunday = 0
    return monday.toISOString().slice(0, 10); // Return YYYY-MM-DD of Monday
}

function formatWeekRange(mondayStr) {
    const monday = new Date(mondayStr);
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    
    const options = { day: 'numeric', month: 'short' };
    const mondayFormatted = monday.toLocaleDateString('sk-SK', options);
    const sundayFormatted = sunday.toLocaleDateString('sk-SK', options);
    
    return `${mondayFormatted} - ${sundayFormatted}`;
}

function renderEntriesGrouped(data) {
    if (!data.length) return '<div class="text-center text-muted py-4">Žiadne záznamy</div>';
    // Group by month (YYYY-MM)
    const byMonth = groupBy(data, e => e.datum.slice(0, 7));
    let html = '';
    Object.keys(byMonth).sort((a, b) => b.localeCompare(a)).forEach(month => {
        const monthEntries = byMonth[month];
        const monthSum = sumEntries(monthEntries);
        html += `<div class="month-group">
            <div class="month-header">${month} <span class="month-total-row">&mdash; Mesiac: <span class="badge bg-info">${formatTime(monthSum.h, monthSum.m)}</span></span></div>`;
        
        // Group by week within month
        const byWeek = groupBy(monthEntries, e => getWeekKey(e.datum));
        Object.keys(byWeek).sort((a, b) => b.localeCompare(a)).forEach(weekMonday => {
            const weekEntries = byWeek[weekMonday];
            const weekSum = sumEntries(weekEntries);
            const weekRange = formatWeekRange(weekMonday);
            
            html += `<div class="week-group">
                <div class="week-header">${weekRange} <span class="week-total-row">&mdash; Týždeň: <span class="badge bg-info">${formatTime(weekSum.h, weekSum.m)}</span></span></div>`;
            
            // Group by day within week
            const byDay = groupBy(weekEntries, e => e.datum);
            Object.keys(byDay).sort((a, b) => b.localeCompare(a)).forEach(day => {
                const dayEntries = byDay[day];
                const daySum = sumEntries(dayEntries);
                html += `<div class="date-group">
                    <div class="date-header">${day} <span class="date-total-row">&mdash; Deň: <span class="badge bg-info">${formatTime(daySum.h, daySum.m)}</span></span></div>
                    ${dayEntries.map(entryCard).join('')}
                </div>`;
            });
            html += `</div>`;
        });
        html += `</div>`;
    });
    return html;
}

let allEntries = [];
let filteredEntries = [];
let searchValue = '';
let showAllEntries = false;

function normalize(str) {
    return (str || '').toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '');
}

function getSuggestions(entries, value) {
    if (!value) return getAllSuggestions(entries);
    value = normalize(value);
    const ulohaSet = new Set(), jiraSet = new Set(), autorSet = new Set();
    entries.forEach(e => {
        if (e.uloha && normalize(e.uloha).includes(value)) ulohaSet.add(e.uloha);
        if (e.jira && normalize(e.jira).includes(value)) jiraSet.add(e.jira);
        if (e.autor && normalize(e.autor).includes(value)) autorSet.add(e.autor);
    });
    return [
        ...Array.from(ulohaSet).map(u => ({ type: 'uloha', value: u })),
        ...Array.from(jiraSet).map(j => ({ type: 'jira', value: j })),
        ...Array.from(autorSet).map(a => ({ type: 'autor', value: a }))
    ];
}
function getAllSuggestions(entries) {
    const ulohaSet = new Set(), jiraSet = new Set(), autorSet = new Set();
    entries.forEach(e => {
        if (e.uloha) ulohaSet.add(e.uloha);
        if (e.jira) jiraSet.add(e.jira);
        if (e.autor) autorSet.add(e.autor);
    });
    return [
        ...Array.from(ulohaSet).map(u => ({ type: 'uloha', value: u })),
        ...Array.from(jiraSet).map(j => ({ type: 'jira', value: j })),
        ...Array.from(autorSet).map(a => ({ type: 'autor', value: a }))
    ];
}
function renderSuggestions(suggestions) {
    if (!suggestions.length) return '<div class="search-suggestion text-muted">Žiadne návrhy</div>';
    return suggestions.map(s => `<div class="search-suggestion" data-type="${s.type}" data-value="${s.value}"><span class="badge ${s.type === 'uloha' ? 'bg-primary' : s.type === 'autor' ? 'bg-secondary' : 'bg-warning text-dark'} me-2">${s.type === 'uloha' ? 'Úloha' : s.type === 'autor' ? 'Autor' : 'JIRA'}</span>${s.value}</div>`).join('');
}
function filterEntries(entries, value) {
    if (!value) return entries;
    value = normalize(value);
    return entries.filter(e =>
        normalize(e.uloha).includes(value) ||
        normalize(e.jira).includes(value) ||
        normalize(e.popis).includes(value) ||
        normalize(e.autor).includes(value)
    );
}
function updateSearchSuggestions() {
    const bar = document.getElementById('searchBar');
    const sugg = document.getElementById('searchSuggestions');
    const val = bar.value.trim();
    const suggestions = getSuggestions(allEntries, val);
    sugg.innerHTML = renderSuggestions(suggestions);
    // Only show if focused
    if (document.activeElement === bar && suggestions.length) {
        sugg.style.display = 'block';
    } else {
        sugg.style.display = 'none';
    }
}
function hideSuggestions() {
    setTimeout(() => { document.getElementById('searchSuggestions').style.display = 'none'; }, 150);
}
function showSuggestions() {
    updateSearchSuggestions();
    document.getElementById('searchSuggestions').style.display = 'block';
}
function attachSearchBarEvents() {
    const bar = document.getElementById('searchBar');
    const sugg = document.getElementById('searchSuggestions');
    const clearBtn = document.getElementById('searchClearBtn');
    
    function updateClearButtonVisibility() {
        clearBtn.style.display = bar.value ? 'block' : 'none';
    }
    
    bar.addEventListener('input', function() {
        searchValue = this.value;
        filteredEntries = filterEntries(allEntries, searchValue);
        entriesList.innerHTML = renderEntriesGrouped(filteredEntries);
        updateSearchSuggestions();
        updateClearButtonVisibility();
    });
    
    clearBtn.addEventListener('mousedown', function(e) {
        e.preventDefault();
        bar.value = '';
        searchValue = '';
        filteredEntries = filterEntries(allEntries, '');
        entriesList.innerHTML = renderEntriesGrouped(filteredEntries);
        updateSearchSuggestions();
        updateClearButtonVisibility();
        bar.focus();
    });
    
    bar.addEventListener('focus', function() {
        showSuggestions();
    });
    bar.addEventListener('blur', function() {
        hideSuggestions();
    });
    sugg.addEventListener('mousedown', function(e) {
        if (e.target.classList.contains('search-suggestion')) {
            bar.value = e.target.getAttribute('data-value');
            searchValue = bar.value;
            filteredEntries = filterEntries(allEntries, searchValue);
            entriesList.innerHTML = renderEntriesGrouped(filteredEntries);
            updateSearchSuggestions();
            updateClearButtonVisibility(); // Add this line to update clear button when suggestion is selected
            bar.focus();
        }
    });
}

async function loadEntries() {
    entriesList.innerHTML = '<div class="text-center text-muted py-4">Načítavam...</div>';
    try {
        let url = '/time-entries';
        if (!showAllEntries) {
            url += `?autor=${encodeURIComponent(form.autor.value.trim())}`;
        }
        const resp = await fetch(url);
        if (!resp.ok) throw new Error('Chyba načítania');
        const data = await resp.json();
        allEntries = data;
        // --- Filter by author on frontend as well, for safety ---
        let entriesToRender = allEntries;
        if (!showAllEntries) {
            const currentAuthor = form.autor.value.trim();
            entriesToRender = allEntries.filter(e => e.autor === currentAuthor);
        }
        filteredEntries = filterEntries(entriesToRender, searchValue);
        entriesList.innerHTML = renderEntriesGrouped(filteredEntries);
        updateSearchSuggestions();
    } catch (err) {
        entriesList.innerHTML = '<div class="text-danger">Chyba načítania záznamov</div>';
    }
}

document.getElementById('showAllEntriesSwitch').addEventListener('change', function() {
    showAllEntries = this.checked;
    loadEntries();
});

window.deleteEntry = async function(id) {
    const entry = allEntries.find(e => e.id === id);
    if (!entry) return;
    if (showAllEntries && entry.autor !== form.autor.value.trim()) {
        alert('Nemôžete vymazávať záznamy iných autorov!');
        return;
    }
    if (!confirm('Naozaj chcete záznam vymazať?')) return;
    try {
        const resp = await fetch(`/time-entries/${id}`, { method: 'DELETE' });
        if (resp.ok) {
            await loadEntriesWithScrollPreservation();
        } else {
            alert('Chyba pri mazaní záznamu.');
        }
    } catch (err) {
        alert('Chyba spojenia so serverom.');
    }
}

window.duplicateEntry = function(id) {
    const entry = allEntries.find(e => e.id === id);
    if (!entry) return;
    document.getElementById('editId').value = '';
    document.getElementById('editUloha').value = entry.uloha;
    document.getElementById('editDatum').value = entry.datum;
    document.getElementById('editHodiny').value = entry.hodiny;
    document.getElementById('editMinuty').value = entry.minuty;
    document.getElementById('editJira').value = entry.jira || '';
    document.getElementById('editPopis').value = entry.popis || '';
    // Set author to current author (from form.autor)
    // (No author field in modal, but will use form.autor on submit)
    autoExpandTextarea(document.getElementById('editPopis'));
    updateCounter('editPopis', 'editPopisCounter');
    document.getElementById('editModalLabel').textContent = 'Duplikovať záznam';
    editModal.show();
    editForm.setAttribute('data-duplicate', 'true');
}

window.editEntry = function(id) {
    const entry = allEntries.find(e => e.id === id);
    if (!entry) return;
    if (showAllEntries && entry.autor !== form.autor.value.trim()) {
        alert('Nemôžete upraviť záznamy iných autorov!');
        return;
    }
    document.getElementById('editId').value = entry.id;
    document.getElementById('editUloha').value = entry.uloha;
    document.getElementById('editDatum').value = entry.datum;
    document.getElementById('editHodiny').value = entry.hodiny;
    document.getElementById('editMinuty').value = entry.minuty;
    document.getElementById('editJira').value = entry.jira || '';
    document.getElementById('editPopis').value = entry.popis || '';
    autoExpandTextarea(document.getElementById('editPopis'));
    updateCounter('editPopis', 'editPopisCounter');
    document.getElementById('editModalLabel').textContent = 'Upraviť záznam';
    editModal.show();
    editForm.removeAttribute('data-duplicate');
}

editForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const isDuplicate = editForm.getAttribute('data-duplicate') === 'true';
    const id = document.getElementById('editId').value;
    const ulohaCode = document.getElementById('editUloha').value.trim();
    const jiraCode = document.getElementById('editJira').value.trim();
    
    // JIRA/Úloha validation: require Úloha only if JIRA is missing or invalid
    if (!jiraCode && !ulohaCode) {
        window.alert('Vyplňte buď JIRA kľúč alebo Úlohu.');
        return;
    }
    
    // Get JIRA metadata from cache or API
    let issues = await fetchJiraIssues(form.autor.value.trim());
    let jiraIssue = jiraCode ? issues.find(i => i.key === jiraCode) : null;
    let ulohaIssue = ulohaCode ? issues.find(i => i.key === ulohaCode) : null;
    
    // If we didn't find the issues in cache, force a fresh fetch from API
    if ((!jiraIssue && jiraCode) || (!ulohaIssue && ulohaCode)) {
        // Clear cache to force refresh
        jiraIssuesCache = [];
        jiraIssuesLoadedFor = '';
        issues = await fetchJiraIssues(form.autor.value.trim());
        jiraIssue = jiraCode ? issues.find(i => i.key === jiraCode) : null;
        ulohaIssue = ulohaCode ? issues.find(i => i.key === ulohaCode) : null;
    }
    
    // If JIRA is provided but not found, try to validate it with broader search
    let jiraValidated = false;
    let jiraIssueFromBroaderSearch = null;
    if (jiraCode) {
        if (jiraIssue) {
            jiraValidated = true;
        } else {
            // Try to validate JIRA key with broader search
            try {
                const resp = await fetch(`/api/validate-jira?key=${encodeURIComponent(jiraCode)}`);
                if (resp.ok) {
                    const result = await resp.json();
                    jiraValidated = result.valid;
                    if (result.valid && result.issue) {
                        jiraIssueFromBroaderSearch = result.issue;
                    }
                }
            } catch (e) {
                console.warn('Could not validate JIRA key:', e);
            }
        }
    }
    
    // Validation logic: 
    // - If JIRA is provided and valid, allow submission (no Úloha required)
    // - If JIRA is missing or invalid, require Úloha
    if (jiraCode && !jiraValidated && !ulohaCode) {
        window.alert('JIRA kľúč "' + jiraCode + '" nebol nájdený. Vyplňte prosím Úlohu alebo opravte JIRA kľúč.');
        return;
    }
    
    if (!jiraCode && !ulohaCode) {
        window.alert('Vyplňte buď JIRA kľúč alebo Úlohu.');
        return;
    }
    
    console.log('Edit form - Found issues:', { 
        jira: { key: jiraCode, issue: jiraIssue || jiraIssueFromBroaderSearch }, 
        uloha: { key: ulohaCode, issue: ulohaIssue }
    });

    // Use either the cached JIRA issue or the one from broader search
    const effectiveJiraIssue = jiraIssue || jiraIssueFromBroaderSearch;

    const data = {
        uloha: ulohaCode || (effectiveJiraIssue && effectiveJiraIssue.parent_key ? effectiveJiraIssue.parent_key : ''),
        datum: document.getElementById('editDatum').value,
        hodiny: parseInt(document.getElementById('editHodiny').value, 10),
        minuty: parseInt(document.getElementById('editMinuty').value, 10),
        jira: jiraCode || undefined,
        popis: document.getElementById('editPopis').value || undefined,
        // Add metadata fields:
        jira_name: effectiveJiraIssue ? effectiveJiraIssue.summary : undefined,
        uloha_name: effectiveJiraIssue ? effectiveJiraIssue.parent_summary : (ulohaIssue ? ulohaIssue.summary : undefined),
        // Always include autor field, whether editing or duplicating
        autor: form.autor.value.trim()
    };
    
    // Date validation/confirmation for edit/duplicate
    const today = new Date();
    const entered = new Date(data.datum);
    const priorMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    const thisMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    if (entered > today) {
        if (!confirm('Zadaný dátum je v budúcnosti. Naozaj chcete pokračovať?'))
            return;
    }
    if (!(entered >= priorMonth && entered <= today)) {
        if (!confirm('Dátum nie je z tohto ani predchádzajúceho mesiaca. Naozaj chcete pokračovať?'))
            return;
    }

    try {
        let resp;
        if (isDuplicate) {
            resp = await fetch('/time-entries', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        } else {
            resp = await fetch(`/time-entries/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }

        if (resp.ok) {
            editModal.hide();
            await loadEntriesWithScrollPreservation();
        } else {
            let errMsg = 'Chyba pri ukladaní.';
            try {
                const contentType = resp.headers.get('content-type') || '';
                if (contentType.includes('application/json')) {
                    const err = await resp.json();
                    if (err && typeof err === 'object' && typeof err.detail === 'string') {
                        errMsg = err.detail;
                    } else if (typeof err === 'string') {
                        errMsg = err;
                    }
                } else {
                    const text = await resp.text();
                    if (text && typeof text === 'string') {
                        errMsg = text;
                    }
                }
            } catch (e) {
                // ignore parse errors, use default errMsg
            }
            alert(errMsg);
        }
    } catch (err) {
        alert('Chyba spojenia so serverom. ' + (err.message || ''));
    }
    editForm.removeAttribute('data-duplicate');
});

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    alertBox.style.display = 'none';
    // --- Hodiny/Minuty validation ---
    let hodinyVal = form.hodiny.value.trim();
    let minutyVal = form.minuty.value.trim();
    if (hodinyVal === '') hodinyVal = '0';
    if (minutyVal === '') minutyVal = '0';
    const hodiny = parseInt(hodinyVal, 10) || 0;
    const minuty = parseInt(minutyVal, 10) || 0;
    // --- Hodiny/Minuty validation: if both are zero, show only alert, no error message below form ---
    if ((hodiny === 0 && minuty === 0)) {
        window.alert('Vyplňte aspoň hodiny alebo minúty (nemôžu byť obe nula alebo prázdne).');
        alertBox.style.display = 'none'; // Hide any previous error
        alertBox.textContent = '';
        return;
    }
    // --- Popis (description) required validation removed: now handled natively by required attribute ---
    
    const ulohaCode = form.uloha.dataset.code || form.uloha.value.split(':')[0].trim();
    const jiraCode = form.jira.dataset.code || form.jira.value.split(':')[0].trim();
    
    // JIRA/Úloha validation: require Úloha only if JIRA is missing or invalid
    if (!jiraCode && !ulohaCode) {
        window.alert('Vyplňte buď JIRA kľúč alebo Úlohu.');
        return;
    }
    
    // Get JIRA metadata from cache
    const issues = await fetchJiraIssues(form.autor.value.trim());
    const jiraIssue = issues.find(i => i.key === jiraCode);
    const ulohaIssue = issues.find(i => i.key === ulohaCode);
    
    // If JIRA is provided but not found, try to fetch it from the general API
    let jiraValidated = false;
    let jiraIssueFromBroaderSearch = null;
    if (jiraCode) {
        if (jiraIssue) {
            jiraValidated = true;
        } else {
            // Try to validate JIRA key with broader search
            try {
                const resp = await fetch(`/api/validate-jira?key=${encodeURIComponent(jiraCode)}`);
                if (resp.ok) {
                    const result = await resp.json();
                    jiraValidated = result.valid;
                    if (result.valid && result.issue) {
                        jiraIssueFromBroaderSearch = result.issue;
                    }
                }
            } catch (e) {
                console.warn('Could not validate JIRA key:', e);
            }
        }
    }
    
    // Validation logic: 
    // - If JIRA is provided and valid, allow submission (no Úloha required)
    // - If JIRA is missing or invalid, require Úloha
    if (jiraCode && !jiraValidated && !ulohaCode) {
        window.alert('JIRA kľúč "' + jiraCode + '" nebol nájdený. Vyplňte prosím Úlohu alebo opravte JIRA kľúč.');
        return;
    }
    
    if (!jiraCode && !ulohaCode) {
        window.alert('Vyplňte buď JIRA kľúč alebo Úlohu.');
        return;
    }
    
    console.log('Create form - Found issues:', { 
        jira: { key: jiraCode, issue: jiraIssue || jiraIssueFromBroaderSearch }, 
        uloha: { key: ulohaCode, issue: ulohaIssue }
    });

    // Use either the cached JIRA issue or the one from broader search
    const effectiveJiraIssue = jiraIssue || jiraIssueFromBroaderSearch;

    const data = {
        uloha: ulohaCode || (effectiveJiraIssue && effectiveJiraIssue.parent_key ? effectiveJiraIssue.parent_key : ''),
        datum: form.datum.value,
        hodiny: hodiny,
        minuty: minuty,
        jira: jiraCode || undefined,
        popis: form.popis.value || undefined,
        autor: form.autor.value.trim(),
        // If we have a JIRA issue, use its summary for jira_name
        jira_name: effectiveJiraIssue ? effectiveJiraIssue.summary : undefined,
        // For uloha_name:
        // 1. If we have a JIRA issue, use its parent_summary
        // 2. Otherwise, if we have an Úloha issue, use its own summary
        uloha_name: effectiveJiraIssue ? effectiveJiraIssue.parent_summary : (ulohaIssue ? ulohaIssue.summary : undefined)
    };
    // Date validation/confirmation
    const today = new Date();
    const entered = new Date(data.datum);
    const priorMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    const thisMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    if (entered > today) {
        if (!confirm('Zadaný dátum je v budúcnosti. Naozaj chcete pokračovať?')) return;
    }
    if (!(entered >= priorMonth && entered <= today)) {
        if (!confirm('Dátum nie je z tohto ani predchádzajúceho mesiaca. Naozaj chcete pokračovať?')) return;
    }

    // --- Duration measuring ---
    const t0 = performance.now();
    let t1, t2, t3;
    try {
        t1 = performance.now();
        window.logPerf = true; // force global flag for debugging
        if (window.logPerf) {
            window.console.log('[PERF] Submitting form data:', data);
        }
        const resp = await fetch('/time-entries', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        t2 = performance.now();
        if (window.logPerf) {
            window.console.log('[PERF] POST /time-entries finished. Duration:', (t2 - t1).toFixed(1), 'ms');
        }
        if (resp.ok) {
            alertBox.className = 'alert alert-success';
            alertBox.textContent = 'Záznam bol úspešne uložený!';
            alertBox.style.display = 'block';
            setTimeout(() => { alertBox.style.display = 'none'; }, 4000);
            form.reset();
            form.autor.value = topAutorInput.value;
            setTodayDate(form.datum);
            form.hodiny.value = '0';
            form.minuty.value = '0';
            form.uloha.value = '';
            form.uloha.dataset.code = '';
            form.jira.value = '';
            form.jira.dataset.code = '';
            if (typeof updateJiraSuggestionsByUloha === 'function') {
                updateJiraSuggestionsByUloha();
            } else if (form.jira && form.jira._suggBox) {
                form.jira._suggBox.innerHTML = '';
                form.jira._suggBox.style.display = 'none';
            }
            setTimeout(async () => {
                const tLoadStart = performance.now();
                if (window.logPerf) window.console.log('[PERF] Starting entries reload...');
                await loadEntriesWithScrollPreservation();
                const tLoadEnd = performance.now();
                t3 = tLoadEnd;
                if (window.logPerf) {
                    window.console.log('[PERF] Entries reload finished. Duration:', (tLoadEnd - tLoadStart).toFixed(1), 'ms');
                    window.console.log('[PERF] Total submit-to-entries duration:', (tLoadEnd - t0).toFixed(1), 'ms');
                }
            }, 0);
        } else {
            let errMsg = 'Chyba pri ukladaní.';
            try {
                const contentType = resp.headers.get('content-type') || '';
                if (contentType.includes('application/json')) {
                    const err = await resp.json();
                    if (err && typeof err === 'object' && typeof err.detail === 'string') {
                        errMsg = err.detail;
                    } else if (typeof err === 'string') {
                        errMsg = err;
                    }
                } else {
                    const text = await resp.text();
                    if (text && typeof text === 'string') {
                        errMsg = text;
                    }
                }
            } catch (e) {
                // ignore parse errors, use default errMsg
            }
            alert(errMsg);
        }
    } catch (err) {
        alert('Chyba spojenia so serverom. ' + (err.message || ''));
    }
});

form.addEventListener('reset', function() {
    form.hodiny.value = '0';
    form.minuty.value = '0';
    autoExpandTextarea(document.getElementById('popis'));
    updateCounter('popis', 'popisCounter');
});

document.getElementById('exportExcelBtn').addEventListener('click', function() {
    if (!allEntries.length) {
        alert('Nie sú žiadne záznamy na export.');
        return;
    }
    const data = allEntries.map(e => ({
        ID: e.id,
        Úloha: e.uloha,
        Autor: e.autor,
        Dátum: e.datum,
        Hodiny: e.hodiny,
        Minúty: e.minuty,
        JIRA: e.jira,
        Popis: e.popis,
        "Vytvorené": new Date(e.created_at).toLocaleString()
    }));
    const ws = XLSX.utils.json_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Vykazy');
    XLSX.writeFile(wb, 'vykazy.xlsx');
});

document.getElementById('importFromMetaAppBtn').addEventListener('click', async function() {
    const currentAutor = form.autor.value.trim();
    if (!currentAutor) {
        showAlert('Najprv zadajte autora.', 'warning');
        return;
    }

    if (!confirm(`Naozaj chcete importovať záznamy z MetaApp pre autora "${currentAutor}"?\n\nExistujúce záznamy s rovnakým vykaz_id nebudú prepísané.`)) {
        return;
    }

    try {
        this.disabled = true;
        this.innerHTML = '<i class="bi bi-hourglass-split"></i> Importujem...';
        
        const response = await fetch('/import-from-metaapp', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ autor: currentAutor })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || 'Chyba pri importe');
        }

        showAlert(`Import dokončený. Importované: ${result.imported_count} záznamov, Preskočené: ${result.skipped_count} záznamov.`, 'success');
        
        // Refresh the entries list
        await loadEntriesWithScrollPreservation();
        
    } catch (error) {
        console.error('Import error:', error);
        showAlert('Chyba pri importe z MetaApp: ' + error.message, 'danger');
    } finally {
        this.disabled = false;
        this.innerHTML = '<i class="bi bi-download"></i> Import z MetaApp';
    }
});

function autoExpandTextarea(textarea) {
    textarea.style.height = 'auto';
    const maxHeight = parseFloat(getComputedStyle(textarea).lineHeight) * 50 + 8;
    textarea.style.height = Math.min(textarea.scrollHeight, maxHeight) + 'px';
}

function updateCounter(id, counterId) {
    const ta = document.getElementById(id);
    const counter = document.getElementById(counterId);
    counter.textContent = ta.value.length;
}
['popis', 'editPopis'].forEach((id, i) => {
    const ta = document.getElementById(id);
    const counterId = id === 'popis' ? 'popisCounter' : 'editPopisCounter';
    if (ta) {
        ta.addEventListener('input', function() {
            autoExpandTextarea(this);
            updateCounter(id, counterId);
        });
        // Initial sizing and counter
        autoExpandTextarea(ta);
        updateCounter(id, counterId);
    }
});

form.addEventListener('reset', function() {
    form.hodiny.value = '0';
    form.minuty.value = '0';
    autoExpandTextarea(document.getElementById('popis'));
    updateCounter('popis', 'popisCounter');
});

function parseTimeInput(str) {
    str = (str || '').toLowerCase().replace(/\s+/g, '');
    let h = '', m = '';
    // Try to match both hours and minutes in any order
    let match = str.match(/^(?:(\d+)\s*(?:h|hod))?\s*(?:(\d+)\s*min)?$/);
    if (match && (match[1] || match[2])) {
        h = match[1] || '';
        m = match[2] || '';
    } else if ((match = str.match(/^(\d+)\s*(?:h|hod)$/))) {
        h = match[1];
        m = '';
    } else if ((match = str.match(/^(\d+)\s*min$/))) {
        h = '';
        m = match[1];
    } else if (/^\d+$/.test(str)) {
        m = str;
    }
    // If minutes >= 60, convert
    if (m !== '' && !isNaN(m) && parseInt(m, 10) >= 60) {
        h = (parseInt(h || '0', 10) + Math.floor(parseInt(m, 10) / 60)).toString();
        m = (parseInt(m, 10) % 60).toString();
    }
    return { h, m };
}
function handleSmartTimeInput(e) {
    const val = e.target.value;
    if (!val) return;
    let parsed = parseTimeInput(val);
    if (parsed.h !== '' || parsed.m !== '') {
        form.hodiny.value = parsed.h;
        form.minuty.value = parsed.m;
    }
}
form.hodiny.addEventListener('blur', function(e) {
    const val = e.target.value;
    if (!val) return;
    if (/^\d+\.\d+$/.test(val)) {
        const floatVal = parseFloat(val);
        const h = Math.floor(floatVal);
        const m = Math.round((floatVal - h) * 60);
        form.hodiny.value = h;
        form.minuty.value = m;
    }
});
document.getElementById('editHodiny').addEventListener('blur', function(e) {
    const val = e.target.value;
    if (!val) return;
    if (/^\d+\.\d+$/.test(val)) {
        const floatVal = parseFloat(val);
        const h = Math.floor(floatVal);
        const m = Math.round((floatVal - h) * 60);
        document.getElementById('editHodiny').value = h;
        document.getElementById('editMinuty').value = m;
    }
});

const AUTHOR = form.autor.value;

async function fetchTemplates() {
    const autor = form.autor.value.trim();
    const resp = await fetch(`/templates?autor=${encodeURIComponent(autor)}`);
    if (!resp.ok) return [];
    return await resp.json();
}
async function saveTemplateToDB(template) {
    const resp = await fetch('/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(template)
    });
    return resp.ok;
}
async function deleteTemplateFromDB(id) {
    const autor = form.autor.value.trim();
    const resp = await fetch(`/templates/${id}?autor=${encodeURIComponent(autor)}`, { method: 'DELETE' });
    return resp.ok;
}
function colorForUloha(uloha) {
    const colors = ['bg-primary','bg-success','bg-warning text-dark','bg-info','bg-danger','bg-secondary','bg-dark'];
    if (!uloha) return 'bg-secondary';
    let hash = 0;
    for (let i = 0; i < uloha.length; i++) hash = uloha.charCodeAt(i) + ((hash << 5) - hash);
    return colors[Math.abs(hash) % colors.length];
}
// --- Render template dropdown with delete option ---
let currentTemplates = [];
async function renderTemplateDropdown() {
    const dropdown = document.getElementById('templateDropdown');
    const author = form.autor.value.trim();
    currentTemplates = await fetchTemplates();
    if (!dropdown) return;
    if (!currentTemplates.length) {
        dropdown.innerHTML = '<li><span class="dropdown-item text-muted">Žiadne šablóny</span></li>';
        return;
    }
    dropdown.innerHTML = currentTemplates.map((t, i) =>
        `<li class="d-flex align-items-center justify-content-between px-2">
            <a class="dropdown-item flex-grow-1 d-flex align-items-center" href="#" data-idx="${i}">
                <span class="badge ${colorForUloha(t.uloha)} me-2">${t.uloha || 'Šablóna'}</span>
                <span>${t.name}</span>
            </a>
            <button class="btn btn-link btn-sm text-danger ms-2 delete-template-btn" data-id="${t.id}" title="Vymazať šablónu"><i class="bi bi-trash"></i></button>
        </li>`
    ).join('');
}
// Save template to DB

document.getElementById('saveTemplateBtn').addEventListener('click', async function() {
    const uloha = form.uloha.value.trim();
    const autor = form.autor.value.trim();
    const hodiny = form.hodiny.value.trim();
    const minuty = form.minuty.value.trim();
    const jira = form.jira.value.trim();
    const popis = form.popis.value.trim();
    if (!uloha && !jira && !popis) {
        alert('Vyplňte aspoň Úlohu, JIRA alebo Popis pre uloženie šablóny.');
        return;
    }
    const name = prompt('Zadajte názov šablóny:');
    if (!name) return;
    const template = { name, uloha, autor, hodiny, minuty, jira, popis };
    const ok = await saveTemplateToDB(template);
    if (ok) {
        await renderTemplateDropdown();
        document.getElementById('useTemplateBtn').click(); // open dropdown after save
    } else {
        alert('Chyba pri ukladaní šablóny.');
    }
});
// Show dropdown on button click

document.getElementById('useTemplateBtn').addEventListener('click', renderTemplateDropdown);
// Handle template selection and delete

document.getElementById('templateDropdown').addEventListener('click', async function(e) {
    if (e.target.closest('a[data-idx]')) {
        const idx = e.target.closest('a[data-idx]').getAttribute('data-idx');
        const t = currentTemplates[idx];
        if (!t) return;
        form.uloha.value = t.uloha;
        form.autor.value = t.autor;
        form.hodiny.value = t.hodiny;
        form.minuty.value = t.minuty;
        form.jira.value = t.jira;
        form.popis.value = t.popis;
        autoExpandTextarea(form.popis);
        updateCounter('popis', 'popisCounter');
    } else if (e.target.closest('.delete-template-btn')) {
        const id = e.target.closest('.delete-template-btn').getAttribute('data-id');
        const t = currentTemplates.find(t => t.id == id);
        if (!t) return;
        if (confirm(`Naozaj chcete vymazať šablónu "${t.name}"?`)) {
            const ok = await deleteTemplateFromDB(id);
            if (ok) {
                await renderTemplateDropdown();
            } else {
                alert('Chyba pri mazaní šablóny.');
            }
        }
    }
});
// Clear form button

document.getElementById('clearFormBtn').addEventListener('click', function() {
    form.reset();
    form.autor.value = topAutorInput.value;
    setTodayDate(form.datum);
    form.hodiny.value = '0';
    form.minuty.value = '0';
    // Clear the dataset codes to ensure JIRA dropdown shows all options
    form.uloha.dataset.code = '';
    form.jira.dataset.code = '';
    autoExpandTextarea(form.popis);
    updateCounter('popis', 'popisCounter');
});

// Autor input at top - syncs with form and reloads entries/templates
const topAutorInput = document.getElementById('topAutorInput');
topAutorInput.addEventListener('input', async function() {
    form.autor.value = this.value;
    // Clear both caches when author changes
    metaappTasksCache = [];
    metaappTasksLoadedFor = '';
    jiraIssuesCache = [];
    jiraIssuesLoadedFor = '';
    loadEntries();
    renderTemplateDropdown();
    // Pre-load JIRA issues for the new author
    const author = this.value.trim();
    if (author) await fetchJiraIssues(author);
});
// Keep form.autor in sync with topAutorInput on change
form.autor.addEventListener('input', async function() {
    topAutorInput.value = this.value;
    // Clear both caches when author changes
    metaappTasksCache = [];
    metaappTasksLoadedFor = '';
    jiraIssuesCache = [];
    jiraIssuesLoadedFor = '';
    loadEntries();
    renderTemplateDropdown();
    // Pre-load JIRA issues for the new author
    const author = this.value.trim();
    if (author) await fetchJiraIssues(author);
});
// On page load, sync form.autor with top input
form.autor.value = topAutorInput.value;

// --- JIRA Autocomplete ---
let jiraIssuesCache = [];
let jiraIssuesLoadedFor = '';
let jiraLoading = false;
let jiraError = null;

// --- MetaApp Tasks Cache ---
let metaappTasksCache = [];
let metaappTasksLoadedFor = '';
let metaappTasksLoading = false;
let metaappTasksError = null;

async function fetchMetaAppTasks(author) {
    if (!author) {
        console.log('[MetaApp Cache] No author provided, skipping fetch.');
        return [];
    }
    
    // Check in-memory cache first
    if (metaappTasksLoadedFor === author && metaappTasksCache.length) {
        console.log('[MetaApp Cache] Using in-memory cache:', {
            author,
            taskCount: metaappTasksCache.length,
            source: 'memory-cache'
        });
        return metaappTasksCache;
    }
    
    metaappTasksLoading = true;
    metaappTasksError = null;
    
    try {
        const resp = await fetch(`/metaapp-tasks?autor=${encodeURIComponent(author)}`);
        if (!resp.ok) throw new Error('Chyba načítania MetaApp úloh');
        const data = await resp.json();
        
        metaappTasksCache = data;
        metaappTasksLoadedFor = author;
        metaappTasksLoading = false;
        
        console.log('[MetaApp Cache] Successfully fetched from API:', {
            author,
            taskCount: data.length,
            source: 'api-success'
        });
        
        return data;
    } catch (err) {
        metaappTasksError = err.message || 'Chyba načítania MetaApp úloh';
        metaappTasksCache = [];
        metaappTasksLoading = false;
        
        console.error('[MetaApp Cache] API fetch failed:', {
            author,
            error: metaappTasksError,
            source: 'api-error'
        });
        
        return [];
    }
}

async function fetchJiraIssues(author) {
    if (!author) {
        console.log('[JIRA Cache] No author provided, skipping fetch.');
        return [];
    }
    // Try to load from localStorage first
    const cacheKey = `jiraIssuesCache_${author}`;
    const cacheStr = localStorage.getItem(cacheKey);
    
    // Check in-memory cache first
    if (jiraIssuesLoadedFor === author && jiraIssuesCache.length) {
        console.log('[JIRA Cache] Using in-memory cache:', {
            author,
            issueCount: jiraIssuesCache.length,
            source: 'memory-cache'
        });
        return jiraIssuesCache;
    }
    
    // Try localStorage cache
    if (cacheStr) {
        try {
            const cacheObj = JSON.parse(cacheStr);
            const cacheAge = Date.now() - (cacheObj?.ts || 0);
            const cacheAgeHours = Math.round(cacheAge / (60*60*1000) * 10) / 10;

            // Cache is valid if less than 30 minutes old and has data
            const CACHE_DURATION = 30 * 60 * 1000; // 30 minutes in milliseconds
            if (cacheObj && Array.isArray(cacheObj.data) && cacheObj.ts && cacheAge < CACHE_DURATION) {
                jiraIssuesCache = cacheObj.data;
                jiraIssuesLoadedFor = author;
                jiraLoading = false;
                jiraError = null;
                console.log('[JIRA Cache] Using localStorage cache:', {
                    author,
                    issueCount: cacheObj.data.length,
                    cacheAge: Math.round(cacheAge / (60 * 1000)) + ' minutes',
                    source: 'local-storage'
                });
                return jiraIssuesCache;
            }
            
            // Cache is expired
            console.log('[JIRA Cache] Cache expired:', {
                author,
                cacheAge: cacheAgeHours + ' hours',
                reason: 'age > 30 minutes',
                source: 'expired'
            });
        } catch (e) {
            console.log('[JIRA Cache] Failed to parse localStorage cache:', {
                author,
                error: e.message,
                source: 'parse-error'
            });
        }
    }
    jiraLoading = true;
    jiraError = null;

    // Fetch from API
    const fetchStart = performance.now();
    console.log('[JIRA Cache] Cache miss, fetching from API:', {
        author,
        source: 'api-request'
    });

    try {
        const resp = await fetch(`/jira-issues?autor=${encodeURIComponent(author)}`);
        if (!resp.ok) throw new Error('Chyba načítania JIRA úloh');
        const data = await resp.json();
        const fetchDuration = performance.now() - fetchStart;

        // Update cache
        jiraIssuesCache = data;
        jiraIssuesLoadedFor = author;
        jiraLoading = false;
        
        console.log('[JIRA Cache] Successfully fetched from API:', {
            author,
            issueCount: data.length,
            duration: Math.round(fetchDuration) + 'ms',
            source: 'api-success'
        });

        // Save to localStorage with timestamp
        try {
            localStorage.setItem(cacheKey, JSON.stringify({ data, ts: Date.now() }));
            console.log('[JIRA Cache] Updated localStorage cache');
        } catch (e) {
            console.warn('[JIRA Cache] Failed to update localStorage:', {
                error: e.message,
                source: 'storage-error'
            });
        }
        
        return data;
    } catch (err) {
        jiraError = err.message || 'Chyba načítania JIRA úloh';
        jiraIssuesCache = [];
        jiraLoading = false;
        
        console.error('[JIRA Cache] API fetch failed:', {
            author,
            error: jiraError,
            source: 'api-error'
        });
        
        return [];
    }
}

// --- JIRA parent color coding ---
const jiraParentColors = [
    'bg-primary', 'bg-success', 'bg-warning text-dark', 'bg-info', 'bg-danger', 'bg-secondary', 'bg-dark', 'bg-primary-subtle', 'bg-success-subtle', 'bg-warning-subtle text-dark', 'bg-info-subtle', 'bg-danger-subtle', 'bg-secondary-subtle', 'bg-dark-subtle'
];
function colorForJiraParent(parentKey) {
    if (!parentKey) return 'bg-secondary';
    let hash = 0;
    for (let i = 0; i < parentKey.length; i++) hash = parentKey.charCodeAt(i) + ((hash << 5) - hash);
    return jiraParentColors[Math.abs(hash) % jiraParentColors.length];
}

function renderJiraSuggestions(suggestions) {
    if (jiraLoading) {
        // Show a spinner animation while loading (use Bootstrap spinner and ensure it's visible)
        return '<div class="search-suggestion text-center" style="padding: 1rem 0;"><span class="spinner-border spinner-border-sm text-primary me-2" role="status" aria-hidden="true"></span>Načítavam JIRA úlohy...</div>';
    }
    if (jiraError) return `<div class="search-suggestion text-danger">${jiraError}</div>`;
    if (!suggestions.length) return '<div class="search-suggestion text-muted">Žiadne návrhy</div>';
    return suggestions.map(issue => {
        let parentHtml = '';
        if (issue.parent_key) {
            parentHtml = `<div class=\"jira-parent-info\" style=\"color:#888;font-size:0.95em;margin-top:2px;\"><span class=\"badge bg-light text-dark me-2\">Parent: ${issue.parent_key}</span>${issue.parent_summary || ''}</div>`;
        }
        let badgeStyle = '';
        if (issue.parent_color) {
            badgeStyle = `style=\"background:${issue.parent_color};color:#fff;\"`;
        } else {
            let badgeColor = colorForJiraParent(issue.parent_key);
            badgeStyle = `class=\"badge ${badgeColor} me-2\"`;
        }
        // Show code + summary in dropdown, only code in input
        return `<div class=\"search-suggestion\" data-key=\"${issue.key}\"><span ${badgeStyle}>${issue.key}</span> <span style=\"font-weight:500;\">${issue.summary}</span>${parentHtml}</div>`;
    }).join('');
}

function filterJiraIssues(issues, value) {
    if (!value) {
        // Sort all issues alphabetically by key (case-insensitive)
        return issues.slice().sort((a, b) => a.key.localeCompare(b.key, undefined, {sensitivity: 'base'})).slice(0, 20);
    }
    value = normalize(value);
    return issues.filter(issue =>
        normalize(issue.key).includes(value) ||
        normalize(issue.summary).includes(value) ||
        (issue.parent_key && normalize(issue.parent_key).includes(value)) ||
        (issue.parent_summary && normalize(issue.parent_summary).includes(value))
    ).sort((a, b) => a.key.localeCompare(b.key, undefined, {sensitivity: 'base'})).slice(0, 20);
}

function attachUlohaAutocomplete() {
    const ulohaInput = document.getElementById('uloha');
    const clearBtn = document.getElementById('ulohaClearBtn');
    ulohaInput.style.background = '#fff';
    clearBtn.addEventListener('mousedown', function(e) {
        e.preventDefault();
        ulohaInput.value = '';
        ulohaInput.dataset.code = '';
        updateJiraSuggestionsByUloha();
        form.jira.value = '';
        form.jira.dataset.code = '';
        form.jira.disabled = false;
    });
    // Use the .input-clear-wrapper as the parent for the suggestion box
    const wrapper = ulohaInput.closest('.input-clear-wrapper');
    let suggBox = document.createElement('div');
    suggBox.className = 'search-suggestions';
    suggBox.style.display = 'none';
    wrapper.appendChild(suggBox);

    let blurTimeout = null;
    let ulohaCurrentIndex = -1; // Track selected suggestion index

    function getUlohaOptions() {
        // Get unique parent_key values from jiraIssuesCache
        const jiraMap = new Map();
        jiraIssuesCache.forEach(issue => {
            if (issue.parent_key && !jiraMap.has(issue.parent_key)) {
                jiraMap.set(issue.parent_key, issue.parent_summary || '');
            }
        });
        
        // Get JIRA options first
        const jiraOptions = Array.from(jiraMap.entries())
            .map(([code, summary]) => ({ 
                code, 
                summary,
                source: 'jira'
            }));
        
        // Get MetaApp tasks and filter out duplicates with JIRA (remove from MetaApp, not JIRA)
        const metaappOptions = metaappTasksCache
            .filter(task => !jiraMap.has(task.code)) // Remove MetaApp tasks that exist in JIRA
            .map(task => ({
                code: task.code,
                summary: task.summary,
                source: 'metaapp'
            }));
        
        // Combine with JIRA first, then MetaApp, both alphabetically sorted within their groups
        const jiraSorted = jiraOptions.sort((a, b) => a.code.localeCompare(b.code));
        const metaappSorted = metaappOptions.sort((a, b) => a.code.localeCompare(b.code));
        
        return [...jiraSorted, ...metaappSorted];
    }

    function renderUlohaSuggestions(options, value) {
        if (!options.length) return '<div class="search-suggestion text-muted">Žiadne návrhy</div>';
        value = (value || '').toLowerCase();
        return options.filter(({code, summary, source}) => !value || code.toLowerCase().includes(value) || (summary && summary.toLowerCase().includes(value))).map(({code, summary, source}, index) => {
            // Use different badge colors: JIRA = primary (blue), MetaApp = success (green)
            const badgeClass = source === 'jira' ? 'bg-primary' : 'bg-success';
            return `<div class="search-suggestion" data-value="${code}" data-summary="${summary}" data-index="${index}"><span class="badge ${badgeClass} me-2">${code}</span>${summary ? `<span class='text-muted'>${summary}</span>` : ''}</div>`;
        }).join('');
    }

    function updateSuggestions() {
        const val = ulohaInput.value.trim();
        const options = getUlohaOptions();
        suggBox.innerHTML = renderUlohaSuggestions(options, val);
        suggBox.style.display = options.length ? 'block' : 'none';
        ulohaCurrentIndex = -1; // Reset selection
        updateHighlight();
    }

    async function updateSuggestions() {
        // Ensure both JIRA issues and MetaApp tasks are loaded before showing Úloha options
        const author = form.autor.value.trim();
        if (author) {
            // Fetch both in parallel
            const promises = [];
            if (!jiraIssuesCache.length) {
                promises.push(fetchJiraIssues(author));
            }
            if (!metaappTasksCache.length) {
                promises.push(fetchMetaAppTasks(author));
            }
            if (promises.length > 0) {
                await Promise.all(promises);
            }
        }
        const val = ulohaInput.value.trim();
        const options = getUlohaOptions();
        suggBox.innerHTML = renderUlohaSuggestions(options, val);
        suggBox.style.display = options.length ? 'block' : 'none';
        ulohaCurrentIndex = -1; // Reset selection
        updateHighlight();
    }

    function updateHighlight() {
        const suggestions = suggBox.querySelectorAll('.search-suggestion[data-value]');
        console.log('updateHighlight called - suggestions:', suggestions.length, 'ulohaCurrentIndex:', ulohaCurrentIndex);
        suggestions.forEach((el, index) => {
            const isHighlighted = index === ulohaCurrentIndex;
            el.classList.toggle('highlighted', isHighlighted);
            if (isHighlighted) {
                console.log('Highlighting Úloha suggestion:', index, el.textContent);
            }
        });
    }

    function selectSuggestion(index) {
        const suggestions = suggBox.querySelectorAll('.search-suggestion[data-value]');
        if (index >= 0 && index < suggestions.length) {
            const el = suggestions[index];
            const code = el.getAttribute('data-value');
            const summary = el.getAttribute('data-summary') || '';
            ulohaInput.value = summary ? `${code}: ${summary}` : code;
            ulohaInput.dataset.code = code;
            suggBox.style.display = 'none';
            ulohaCurrentIndex = -1;
            // Always allow typing in JIRA field, regardless of Úloha
            form.jira.disabled = false;
            form.jira.removeAttribute('readonly');
            // If current JIRA does not match allowed JIRAs, do not clear it (let user type anything)
            if (typeof updateJiraSuggestionsByUloha === 'function') updateJiraSuggestionsByUloha();
        }
    }

    // Keyboard navigation
    ulohaInput.addEventListener('keydown', function(e) {
        if (suggBox.style.display === 'none') return;
        
        const suggestions = suggBox.querySelectorAll('.search-suggestion[data-value]');
        const maxIndex = suggestions.length - 1;
        
        console.log('Úloha Keyboard event:', e.key, 'suggestions:', suggestions.length, 'currentIndex:', ulohaCurrentIndex);

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                ulohaCurrentIndex = ulohaCurrentIndex < maxIndex ? ulohaCurrentIndex + 1 : 0;
                updateHighlight();
                console.log('ArrowDown - new index:', ulohaCurrentIndex);
                break;
            case 'Tab':
                e.preventDefault();
                ulohaCurrentIndex = ulohaCurrentIndex < maxIndex ? ulohaCurrentIndex + 1 : 0;
                updateHighlight();
                console.log('Tab - new index:', ulohaCurrentIndex);
                break;
            case 'ArrowUp':
                e.preventDefault();
                ulohaCurrentIndex = ulohaCurrentIndex > 0 ? ulohaCurrentIndex - 1 : maxIndex;
                updateHighlight();
                console.log('ArrowUp - new index:', ulohaCurrentIndex);
                break;
            case 'Enter':
                e.preventDefault();
                if (ulohaCurrentIndex >= 0) {
                    selectSuggestion(ulohaCurrentIndex);
                    console.log('Enter - selecting index:', ulohaCurrentIndex);
                }
                break;
            case 'Escape':
                suggBox.style.display = 'none';
                ulohaCurrentIndex = -1;
                console.log('Escape - closing dropdown');
                break;
        }
    });

    ulohaInput.addEventListener('click', updateSuggestions);
    ulohaInput.addEventListener('input', updateSuggestions);
    ulohaInput.addEventListener('blur', function() {
        blurTimeout = setTimeout(() => { 
            suggBox.style.display = 'none';
            ulohaCurrentIndex = -1;
        }, 150);
    });
    suggBox.addEventListener('mousedown', function(e) {
        const el = e.target.closest('.search-suggestion[data-value]');
        if (el) {
            const code = el.getAttribute('data-value');
            const summary = el.getAttribute('data-summary') || '';
            ulohaInput.value = summary ? `${code}: ${summary}` : code;
            ulohaInput.dataset.code = code;
            suggBox.style.display = 'none';
            ulohaCurrentIndex = -1;
            // Always allow typing in JIRA field, regardless of Úloha
            form.jira.disabled = false;
            form.jira.removeAttribute('readonly');
            // If current JIRA does not match allowed JIRAs, do not clear it (let user type anything)
            if (typeof updateJiraSuggestionsByUloha === 'function') updateJiraSuggestionsByUloha();
        }
    });
    ulohaInput.addEventListener('input', updateSuggestions); // Allow typing to filter
}

// Update JIRA suggestions when Úloha field changes
function updateJiraSuggestionsByUloha() {
    // Don't automatically open the dropdown, just update the internal state
    // The dropdown will only open when user clicks or types in the JIRA field
}

// On form reset, always re-enable JIRA field
form.addEventListener('reset', function() {
    form.jira.disabled = false;
    form.hodiny.value = '0';
    form.minuty.value = '0';
    // Clear the dataset codes to ensure dropdowns show all options after reset
    form.uloha.dataset.code = '';
    form.jira.dataset.code = '';
    autoExpandTextarea(document.getElementById('popis'));
    updateCounter('popis', 'popisCounter');
});

function attachJiraAutocomplete() {
    const jiraInput = document.getElementById('jira');
    const clearBtn = document.getElementById('jiraClearBtn');
    jiraInput.style.background = '#fff';
    clearBtn.addEventListener('mousedown', function(e) {
        e.preventDefault();
        jiraInput.value = '';
        jiraInput.dataset.code = '';
    });
    // Use the .input-clear-wrapper as the parent for the suggestion box
    const wrapper = jiraInput.closest('.input-clear-wrapper');
    let suggBox = document.createElement('div');
    suggBox.className = 'search-suggestions';
    suggBox.style.display = 'none';
    wrapper.appendChild(suggBox);
    jiraInput._suggBox = suggBox;

    let blurTimeout = null;
    let jiraCurrentIndex = -1; // Track selected suggestion index

    function updateJiraHighlight() {
        const suggestions = suggBox.querySelectorAll('.search-suggestion[data-key]');
        console.log('updateJiraHighlight called - suggestions:', suggestions.length, 'jiraCurrentIndex:', jiraCurrentIndex);
        suggestions.forEach((el, index) => {
            const isHighlighted = index === jiraCurrentIndex;
            el.classList.toggle('highlighted', isHighlighted);
            if (isHighlighted) {
                console.log('Highlighting JIRA suggestion:', index, el.textContent);
            }
        });
    }

    function selectJiraSuggestion(index) {
        const suggestions = suggBox.querySelectorAll('.search-suggestion[data-key]');
        if (index >= 0 && index < suggestions.length) {
            const el = suggestions[index];
            const key = el.getAttribute('data-key');
            const issue = jiraIssuesCache.find(issue => issue.key === key);
            jiraInput.value = issue && issue.summary ? `${key}: ${issue.summary}` : key;
            jiraInput.dataset.code = key;
            suggBox.style.display = 'none';
            jiraCurrentIndex = -1;
            // --- Auto-populate Úloha field with parent code ---
            if (issue && issue.parent_key) {
                const parentSummary = issue.parent_summary || '';
                form.uloha.value = parentSummary ? `${issue.parent_key}: ${parentSummary}` : issue.parent_key;
                form.uloha.dataset.code = issue.parent_key;
            } else {
                form.uloha.value = '';
                form.uloha.dataset.code = '';
            }
            if (form.uloha.value) {
                updateJiraSuggestionsByUloha();
            }
        }
    }

    async function updateSuggestions() {
        // Always allow typing and suggestions (never readonly)
        const author = form.autor.value.trim();
        if (!author) return;
        await fetchJiraIssues(author);
        // --- Filter by Úloha if filled ---
        let filtered = jiraIssuesCache;
        const ulohaVal = form.uloha.dataset.code || form.uloha.value.split(':')[0].trim();
        if (ulohaVal) {
            filtered = jiraIssuesCache.filter(issue => issue.parent_key === ulohaVal);
        }
        const val = jiraInput.value.trim();
        const suggestions = filterJiraIssues(filtered, val);
        suggBox.innerHTML = renderJiraSuggestions(suggestions);
        // Show suggestions only if there are actual suggestions, or during loading/error states
        if (jiraLoading || jiraError || suggestions.length > 0) {
            suggBox.style.display = 'block';
        } else {
            suggBox.style.display = 'none';
        }
        jiraCurrentIndex = -1; // Reset selection
        updateJiraHighlight();
    }

    // Keyboard navigation for JIRA
    jiraInput.addEventListener('keydown', function(e) {
        if (suggBox.style.display === 'none') return;
        
        const suggestions = suggBox.querySelectorAll('.search-suggestion[data-key]');
        const maxIndex = suggestions.length - 1;
        
        console.log('JIRA Keyboard event:', e.key, 'suggestions:', suggestions.length, 'currentIndex:', jiraCurrentIndex);

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                jiraCurrentIndex = jiraCurrentIndex < maxIndex ? jiraCurrentIndex + 1 : 0;
                updateJiraHighlight();
                console.log('ArrowDown - new index:', jiraCurrentIndex);
                break;
            case 'Tab':
                e.preventDefault();
                jiraCurrentIndex = jiraCurrentIndex < maxIndex ? jiraCurrentIndex + 1 : 0;
                updateJiraHighlight();
                console.log('Tab - new index:', jiraCurrentIndex);
                break;
            case 'ArrowUp':
                e.preventDefault();
                jiraCurrentIndex = jiraCurrentIndex > 0 ? jiraCurrentIndex - 1 : maxIndex;
                updateJiraHighlight();
                console.log('ArrowUp - new index:', jiraCurrentIndex);
                break;
            case 'Enter':
                e.preventDefault();
                if (jiraCurrentIndex >= 0) {
                    selectJiraSuggestion(jiraCurrentIndex);
                    console.log('Enter - selecting index:', jiraCurrentIndex);
                }
                break;
            case 'Escape':
                suggBox.style.display = 'none';
                jiraCurrentIndex = -1;
                console.log('Escape - closing dropdown');
                break;
        }
    });

    jiraInput.addEventListener('click', async () => { await updateSuggestions(); });
    jiraInput.addEventListener('input', async () => { await updateSuggestions(); });
    jiraInput.addEventListener('blur', function() {
        blurTimeout = setTimeout(() => { 
            suggBox.style.display = 'none';
            jiraCurrentIndex = -1;
        }, 150);
    });
    suggBox.addEventListener('mousedown', function(e) {
        const el = e.target.closest('.search-suggestion[data-key]');
        if (el) {
            const key = el.getAttribute('data-key');
            const issue = jiraIssuesCache.find(issue => issue.key === key);
            jiraInput.value = issue && issue.summary ? `${key}: ${issue.summary}` : key;
            jiraInput.dataset.code = key;
            suggBox.style.display = 'none';
            jiraCurrentIndex = -1;
            // --- Auto-populate Úloha field with parent code ---
            if (issue && issue.parent_key) {
                const parentSummary = issue.parent_summary || '';
                form.uloha.value = parentSummary ? `${issue.parent_key}: ${parentSummary}` : issue.parent_key;
                form.uloha.dataset.code = issue.parent_key;
            } else {
                form.uloha.value = '';
                form.uloha.dataset.code = '';
            }
            // Don't call updateJiraSuggestionsByUloha() here to prevent reopening dropdown
        }
    });
    // Provide a cleanup function to remove autocomplete listeners if needed
    jiraInput._autocompleteCleanup = function() {
        jiraInput.removeEventListener('click', updateSuggestions);
        jiraInput.removeEventListener('blur', blurHandler);
        jiraInput.removeEventListener('input', updateSuggestions);
    };
    function blurHandler() { 
        blurTimeout = setTimeout(() => { 
            suggBox.style.display = 'none';
            jiraCurrentIndex = -1;
        }, 150); 
    }
    jiraInput.addEventListener('blur', blurHandler);
}

// On submit, only send the code part for Úloha and JIRA
// Removed duplicate/old form submit handler to prevent race conditions and spurious error alerts

form.addEventListener('reset', function() {
    form.hodiny.value = '0';
    form.minuty.value = '0';
    autoExpandTextarea(document.getElementById('popis'));
    updateCounter('popis', 'popisCounter');
});

// Add some CSS for clear buttons (ensure vertical centering)
const style = document.createElement('style');
style.innerHTML = `
    .input-clear-btn { top: 50% !important; transform: translateY(-50%) !important; } 
    .input-clear-btn:hover { color: #dc3545 !important; }
    .search-suggestion.highlighted { 
        background-color: #0d6efd !important; 
        color: white !important; 
    }
    .search-suggestion.highlighted .badge { 
        background-color: rgba(255,255,255,0.2) !important; 
        color: white !important; 
    }
    .search-suggestion.highlighted .text-muted { 
        color: rgba(255,255,255,0.8) !important; 
    }
    .search-suggestion.highlighted .jira-parent-info { 
        color: rgba(255,255,255,0.8) !important; 
    }
`;
document.head.appendChild(style);
window.addEventListener('DOMContentLoaded', async () => {
    // Set autor field to topAutorInput value on page load
    form.autor.value = topAutorInput.value;
    form.jira.removeAttribute('readonly'); // Allow typing by default
    form.hodiny.value = '0'; // Default Hodiny to 0
    form.minuty.value = '0'; // Default Minuty to 0
    attachUlohaAutocomplete();
    attachJiraAutocomplete();
    const author = form.autor.value.trim();
    if (author) await fetchJiraIssues(author);
    loadEntries();
    attachSearchBarEvents();
    document.getElementById('searchSuggestions').style.display = 'none';
});

async function submitToMetaApp(entryId) {
    try {
        showAlert('Uploading to MetaApp...', 'info');
        const response = await fetch(`${API_URL}/time-entries/${entryId}/submit-to-metaapp`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to upload entry to MetaApp');
        }

        await loadEntries();
        showAlert('Successfully uploaded to MetaApp!', 'success', 3000);
    } catch (error) {
        console.error('Error uploading to MetaApp:', error);
        showAlert(`Failed to upload to MetaApp: ${error.message}`, 'danger', 5000);
    }
}

window.submitToMetaApp = async function(entryId) {
    const entry = allEntries.find(e => e.id === entryId);
    if (!entry) {
        alert('Záznam sa nenašiel.');
        return;
    }

    if (entry.metaapp_vykaz_id) {
        alert('Tento záznam už bol nahratý do MetaApp.');
        return;
    }


    try {
        const resp = await fetch(`/time-entries/${entryId}/submit-to-metaapp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (resp.ok) {
            await loadEntriesWithScrollPreservation(); // Reload to show updated status
            const alertBox = document.getElementById('alertBox');
            alertBox.className = 'alert alert-success';
            alertBox.textContent = 'Záznam bol úspešne nahratý do MetaApp CRM!';
            alertBox.style.display = 'block';
            setTimeout(() => { alertBox.style.display = 'none'; }, 4000);
        } else {
            let errMsg = 'Chyba pri nahrávaní do MetaApp.';
            try {
                const contentType = resp.headers.get('content-type') || '';
                if (contentType.includes('application/json')) {
                    const err = await resp.json();
                    if (err && typeof err === 'object' && typeof err.detail === 'string') {
                        errMsg = err.detail;
                    } else if (typeof err === 'string') {
                        errMsg = err;
                    }
                } else {
                    const text = await resp.text();
                    if (text && typeof text === 'string') {
                        errMsg = text;
                    }
                }
            } catch (e) {
                // ignore parse errors, use default errMsg
            }
            alert(errMsg);
        }
    } catch (err) {
        alert('Chyba spojenia so serverom.');
        console.error('Error submitting to MetaApp:', err);
    }
};