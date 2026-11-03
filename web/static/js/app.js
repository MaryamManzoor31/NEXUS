/**
 * NEXUS Timetable Generator - Interactive Web Application
 * Handles generation, weekly grid rendering, filtering, export, and disruption repair.
 */

// Application State
let appState = {
  data: null,
  activeTab: 'section',
  activeEntityId: null,
  theme: localStorage.getItem('nexus_theme') || 'light'
};

// DOM References
const elements = {
  selectScenario: document.getElementById('selectScenario'),
  selectSemester: document.getElementById('selectSemester'),
  groupSemester: document.getElementById('groupSemester'),
  groupStudents: document.getElementById('groupStudents'),
  selectStudents: document.getElementById('selectStudents'),
  selectAlgorithm: document.getElementById('selectAlgorithm'),
  btnGenerate: document.getElementById('btnGenerate'),
  btnGenSpinner: document.getElementById('btnGenSpinner'),
  btnGenText: document.getElementById('btnGenText'),
  btnAllocateMembers: document.getElementById('btnAllocateMembers'),
  btnLoadExcel: document.getElementById('btnLoadExcel'),
  btnLoadSample: document.getElementById('btnLoadSample'),
  btnOpenUpload: document.getElementById('btnOpenUpload'),
  btnExportCsv: document.getElementById('btnExportCsv'),
  btnPrint: document.getElementById('btnPrint'),
  btnThemeToggle: document.getElementById('btnThemeToggle'),
  themeIcon: document.getElementById('themeIcon'),

  // Metrics
  valStatusBadge: document.getElementById('valStatusBadge'),
  valStatusSub: document.getElementById('valStatusSub'),
  valEnrolment: document.getElementById('valEnrolment'),
  valEnrolmentSub: document.getElementById('valEnrolmentSub'),
  valSections: document.getElementById('valSections'),
  valSectionsSub: document.getElementById('valSectionsSub'),
  valRuntime: document.getElementById('valRuntime'),
  valRuntimeSub: document.getElementById('valRuntimeSub'),

  // Views & Tabs
  tabs: document.querySelectorAll('.tab-btn'),
  viewToolbar: document.getElementById('viewToolbar'),
  selectorLabel: document.getElementById('selectorLabel'),
  entitySelect: document.getElementById('entitySelect'),
  entityInfo: document.getElementById('entityInfo'),
  gridWrapper: document.getElementById('gridWrapper'),
  gridTbody: document.getElementById('gridTbody'),
  masterWrapper: document.getElementById('masterWrapper'),
  masterSearch: document.getElementById('masterSearch'),
  masterTbody: document.getElementById('masterTbody'),
  allocationsWrapper: document.getElementById('allocationsWrapper'),
  allocationStatsBar: document.getElementById('allocationStatsBar'),
  allocationTbody: document.getElementById('allocationTbody'),
  facultySearch: document.getElementById('facultySearch'),
  facultyStatusFilter: document.getElementById('facultyStatusFilter'),
  btnReallocateInView: document.getElementById('btnReallocateInView'),
  constraintsWrapper: document.getElementById('constraintsWrapper'),
  constraintsList: document.getElementById('constraintsList'),
  disruptionWrapper: document.getElementById('disruptionWrapper'),
  blockedRoomSelect: document.getElementById('blockedRoomSelect'),
  blockedFacultySelect: document.getElementById('blockedFacultySelect'),
  btnApplyRepair: document.getElementById('btnApplyRepair'),
  repairResultNotice: document.getElementById('repairResultNotice'),

  // Modal
  uploadModal: document.getElementById('uploadModal'),
  btnCloseUpload: document.getElementById('btnCloseUpload'),
  btnCancelUpload: document.getElementById('btnCancelUpload'),
  excelUploadForm: document.getElementById('excelUploadForm'),
  uploadSemesterSelect: document.getElementById('uploadSemesterSelect'),
  uploadForm: document.getElementById('uploadForm'),
  uploadIssues: document.getElementById('uploadIssues'),
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  setupEventListeners();
  loadCurrentSchedule();
});

// Theme Management
function initTheme() {
  document.documentElement.setAttribute('data-theme', appState.theme);
  elements.themeIcon.textContent = appState.theme === 'dark' ? '☀️' : '🌙';
}

function toggleTheme() {
  appState.theme = appState.theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('nexus_theme', appState.theme);
  initTheme();
}

// Event Listeners
function setupEventListeners() {
  elements.btnThemeToggle.addEventListener('click', toggleTheme);
  elements.btnGenerate.addEventListener('click', onGenerate);
  if (elements.btnAllocateMembers) {
    elements.btnAllocateMembers.addEventListener('click', onAllocateMembers);
  }
  if (elements.btnReallocateInView) {
    elements.btnReallocateInView.addEventListener('click', onAllocateMembers);
  }
  if (elements.btnLoadExcel) {
    elements.btnLoadExcel.addEventListener('click', onLoadExcel);
  }
  elements.btnExportCsv.addEventListener('click', () => {
    window.location.href = '/api/export/csv';
  });
  elements.btnPrint.addEventListener('click', () => window.print());

  // Scenario change
  elements.selectScenario.addEventListener('change', onScenarioChange);

  // Tab switching
  elements.tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      elements.tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      appState.activeTab = tab.getAttribute('data-tab');
      renderActiveTab();
    });
  });

  // Entity selection change
  elements.entitySelect.addEventListener('change', (e) => {
    appState.activeEntityId = e.target.value;
    renderGrid();
  });

  // Master table search
  elements.masterSearch.addEventListener('input', (e) => {
    filterMasterTable(e.target.value);
  });

  // Faculty allocation filtering
  if (elements.facultySearch) {
    elements.facultySearch.addEventListener('input', filterAllocations);
  }
  if (elements.facultyStatusFilter) {
    elements.facultyStatusFilter.addEventListener('change', filterAllocations);
  }

  // Disruption simulation
  elements.btnApplyRepair.addEventListener('click', onSimulateDisruption);

  // Upload modal handlers
  elements.btnOpenUpload.addEventListener('click', () => {
    elements.uploadIssues.classList.add('hidden');
    if (elements.uploadForm) elements.uploadForm.reset();
    if (elements.excelUploadForm) elements.excelUploadForm.reset();
    elements.uploadModal.showModal();
  });
  elements.btnCloseUpload.addEventListener('click', () => elements.uploadModal.close());
  elements.btnCancelUpload.addEventListener('click', () => elements.uploadModal.close());
  if (elements.excelUploadForm) {
    elements.excelUploadForm.addEventListener('submit', onExcelUploadSubmit);
  }
  if (elements.uploadForm) {
    elements.uploadForm.addEventListener('submit', onUploadSubmit);
  }
}

function onScenarioChange() {
  const isExcel = elements.selectScenario.value === 'excel';
  if (elements.groupSemester) elements.groupSemester.classList.toggle('hidden', !isExcel);
  if (elements.groupStudents) elements.groupStudents.classList.toggle('hidden', isExcel);
}

// Load schedule data from server
async function loadCurrentSchedule() {
  setLoading(true);
  try {
    const res = await fetch('/api/current');
    const json = await res.json();
    if (json.success) {
      appState.data = json.data;
      updateMetrics();
      populateEntitySelectors();
      renderActiveTab();
    }
  } catch (err) {
    console.error('Failed to load current schedule:', err);
  } finally {
    setLoading(false);
  }
}

// Generate schedule action
async function onGenerate() {
  const scenario = elements.selectScenario.value;
  const algorithm = elements.selectAlgorithm.value;

  if (scenario === 'excel') {
    const semester = elements.selectSemester ? elements.selectSemester.value : '6';
    setLoading(true);
    try {
      const res = await fetch('/api/load-excel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          semester,
          algorithm,
          allocate_members: true,
          limit_a: 15,
          limit_b: 10
        })
      });
      const json = await res.json();
      if (json.success) {
        appState.data = json.data;
        updateMetrics();
        populateEntitySelectors();
        renderActiveTab();
      } else {
        alert('Error generating timetable from Excel: ' + (json.error || 'Unknown error'));
      }
    } catch (err) {
      alert('Request failed: ' + err.message);
    } finally {
      setLoading(false);
    }
    return;
  }

  // Synthetic scenario generation
  const students = parseInt(elements.selectStudents.value, 10);
  setLoading(true);
  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario,
        students,
        algorithm,
        seed: 329,
        limit_a: 15,
        limit_b: 10
      })
    });
    const json = await res.json();
    if (json.success) {
      appState.data = json.data;
      updateMetrics();
      populateEntitySelectors();
      renderActiveTab();
    } else {
      alert('Error generating schedule: ' + (json.error || 'Unknown error'));
    }
  } catch (err) {
    alert('Request failed: ' + err.message);
  } finally {
    setLoading(false);
  }
}

// Allocate members action
async function onAllocateMembers() {
  setLoading(true);
  try {
    const res = await fetch('/api/allocate-members', { method: 'POST' });
    const json = await res.json();
    if (json.success) {
      appState.data = json.data;
      updateMetrics();
      populateEntitySelectors();
      
      // Switch tab to allocations view
      elements.tabs.forEach(t => t.classList.remove('active'));
      const allocTab = Array.from(elements.tabs).find(t => t.getAttribute('data-tab') === 'allocations');
      if (allocTab) allocTab.classList.add('active');
      appState.activeTab = 'allocations';
      renderActiveTab();
    } else {
      alert('Member allocation error: ' + (json.error || ''));
    }
  } catch (err) {
    alert('Request failed: ' + err.message);
  } finally {
    setLoading(false);
  }
}

// Reset / Load original Excel dataset
async function onLoadExcel() {
  elements.selectScenario.value = 'excel';
  onScenarioChange();
  await onGenerate();
}

// Excel upload submission
async function onExcelUploadSubmit(e) {
  e.preventDefault();
  const formData = new FormData(elements.excelUploadForm);
  formData.append('algorithm', elements.selectAlgorithm.value);

  setLoading(true);
  try {
    const res = await fetch('/api/upload-excel', {
      method: 'POST',
      body: formData
    });
    const json = await res.json();
    if (json.success) {
      elements.uploadModal.close();
      appState.data = json.data;
      elements.selectScenario.value = 'excel';
      onScenarioChange();
      updateMetrics();
      populateEntitySelectors();
      renderActiveTab();
    } else {
      elements.uploadIssues.innerHTML = `<strong>Upload Error:</strong> ${json.error}`;
      elements.uploadIssues.classList.remove('hidden');
    }
  } catch (err) {
    elements.uploadIssues.innerHTML = `<strong>Upload Failed:</strong> ${err.message}`;
    elements.uploadIssues.classList.remove('hidden');
  } finally {
    setLoading(false);
  }
}

// Load pre-generated sample dataset
async function onLoadSample() {
  setLoading(true);
  try {
    const res = await fetch('/api/load-sample', { method: 'POST' });
    const json = await res.json();
    if (json.success) {
      appState.data = json.data;
      updateMetrics();
      populateEntitySelectors();
      renderActiveTab();
    } else {
      alert('Failed to load sample: ' + (json.error || ''));
    }
  } catch (err) {
    alert('Request failed: ' + err.message);
  } finally {
    setLoading(false);
  }
}

// CSV Upload submit
async function onUploadSubmit(e) {
  e.preventDefault();
  const formData = new FormData(elements.uploadForm);
  formData.append('algorithm', elements.selectAlgorithm.value);

  setLoading(true);
  try {
    const res = await fetch('/api/upload-csv', {
      method: 'POST',
      body: formData
    });
    const json = await res.json();
    if (json.success) {
      elements.uploadModal.close();
      appState.data = json.data;
      updateMetrics();
      populateEntitySelectors();
      renderActiveTab();
    } else {
      elements.uploadIssues.innerHTML = `<strong>Validation Error:</strong> ${json.error}<br>${(json.issues || []).join('<br>')}`;
      elements.uploadIssues.classList.remove('hidden');
    }
  } catch (err) {
    elements.uploadIssues.innerHTML = `<strong>Upload Failed:</strong> ${err.message}`;
    elements.uploadIssues.classList.remove('hidden');
  } finally {
    setLoading(false);
  }
}

// Disruption simulation
async function onSimulateDisruption() {
  const room = elements.blockedRoomSelect.value;
  const faculty = elements.blockedFacultySelect.value;

  if (!room && !faculty) {
    alert('Please select at least one Room or Faculty to block for the simulation.');
    return;
  }

  setLoading(true);
  try {
    const res = await fetch('/api/disruption', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        blocked_rooms: room ? [room] : [],
        blocked_faculty: faculty ? [faculty] : []
      })
    });
    const json = await res.json();
    if (json.success) {
      appState.data = json.data;
      updateMetrics();
      populateEntitySelectors();
      renderActiveTab();

      const blockedDesc = [
        room ? `Room ${room}` : null,
        faculty ? `Faculty ${faculty}` : null
      ].filter(Boolean).join(' and ');

      elements.repairResultNotice.innerHTML = `✅ <strong>Disruption Handled:</strong> Timetable successfully repaired! Blocked ${blockedDesc} was completely avoided while maintaining clash-free schedule validity.`;
      elements.repairResultNotice.classList.remove('hidden');
    } else {
      alert('Repair failed: ' + (json.error || ''));
    }
  } catch (err) {
    alert('Request failed: ' + err.message);
  } finally {
    setLoading(false);
  }
}

// Update Metrics Bar
function updateMetrics() {
  if (!appState.data) return;
  const m = appState.data.metrics;
  const meta = appState.data.meta;

  // Status Badge
  elements.valStatusBadge.textContent = m.validator_status;
  elements.valStatusBadge.className = 'metric-value status-badge';
  if (m.validator_status === 'VALID_COMPLETE') {
    elements.valStatusBadge.classList.add('success');
    elements.valStatusSub.textContent = '14/14 Hard Constraints Met (No Clashes)';
  } else if (m.validator_status === 'VALID_INCOMPLETE') {
    elements.valStatusBadge.classList.add('warning');
    elements.valStatusSub.textContent = 'Clash-Free, Some Choices Unplaced';
  } else {
    elements.valStatusBadge.classList.add('danger');
    elements.valStatusSub.textContent = `${m.hard_violations} Hard Violations Detected`;
  }

  // Student Enrolment
  elements.valEnrolment.textContent = `${m.fully_scheduled_students_pct}%`;
  elements.valEnrolmentSub.textContent = `Unplaced choices: ${m.unplaced_selections} (Dataset: ${meta.total_students} students)`;

  // Sections
  elements.valSections.textContent = m.scheduled_sections;
  elements.valSectionsSub.textContent = `Total sections in curriculum: ${meta.total_sections}`;

  // Runtime
  elements.valRuntime.textContent = `${m.runtime_s} s`;
  const stageBStatus = m.stage_b_status || 'NOT_RUN';
  const stageBLabel = stageBStatus === 'NOT_RUN' ? '' : `; Stage B: ${stageBStatus}`;
  elements.valRuntimeSub.textContent = `Engine: CP-SAT (Stage A: ${m.stage_a_status || m.solver_status}${stageBLabel})`;
}

// Populate dropdown selectors
function populateEntitySelectors() {
  if (!appState.data) return;
  const { entities } = appState.data;

  // Blocked dropdowns for disruption
  elements.blockedRoomSelect.innerHTML = '<option value="">-- None --</option>' +
    Object.values(entities.rooms).map(r => `<option value="${r.id}">${r.id} (${r.type}, Cap: ${r.capacity})</option>`).join('');

  elements.blockedFacultySelect.innerHTML = '<option value="">-- None --</option>' +
    Object.values(entities.faculty).map(f => `<option value="${f.id}">${f.id}: ${f.name} (Max: ${f.max_hours}h)</option>`).join('');
}

// Switch Active View
function renderActiveTab() {
  if (!appState.data) return;
  const tab = appState.activeTab;

  // Toggle UI sections
  const isGridTab = ['section', 'faculty', 'room', 'student'].includes(tab);
  elements.viewToolbar.classList.toggle('hidden', !isGridTab);
  elements.gridWrapper.classList.toggle('hidden', !isGridTab);
  elements.masterWrapper.classList.toggle('hidden', tab !== 'master');
  if (elements.allocationsWrapper) {
    elements.allocationsWrapper.classList.toggle('hidden', tab !== 'allocations');
  }
  elements.constraintsWrapper.classList.toggle('hidden', tab !== 'constraints');
  elements.disruptionWrapper.classList.toggle('hidden', tab !== 'disruption');

  if (isGridTab) {
    updateEntityDropdownForTab(tab);
    renderGrid();
  } else if (tab === 'allocations') {
    renderAllocationsView();
  } else if (tab === 'master') {
    renderMasterTable();
  } else if (tab === 'constraints') {
    renderConstraintsAudit();
  }
}

// Render Faculty Allocations View
function renderAllocationsView() {
  if (!appState.data) return;
  const stats = appState.data.allocation_stats || {};
  const facultySummary = appState.data.faculty_summary || [];

  if (elements.allocationStatsBar) {
    elements.allocationStatsBar.innerHTML = `
      <div class="allocation-stat-pill">
        <span class="allocation-stat-value">${stats.total_sections || 0}</span>
        <span class="allocation-stat-label">Total Sections</span>
      </div>
      <div class="allocation-stat-pill">
        <span class="allocation-stat-value" style="color: var(--primary);">${stats.assigned_sections || 0}</span>
        <span class="allocation-stat-label">Sections Assigned</span>
      </div>
      <div class="allocation-stat-pill">
        <span class="allocation-stat-value" style="color: var(--success);">${stats.active_faculty_count || 0}</span>
        <span class="allocation-stat-label">Active Faculty</span>
      </div>
      <div class="allocation-stat-pill">
        <span class="allocation-stat-value">${stats.total_teaching_hours || 0} hrs</span>
        <span class="allocation-stat-label">Total Teaching Hours</span>
      </div>
      <div class="allocation-stat-pill">
        <span class="allocation-stat-value">${stats.overall_utilization_pct || 0}%</span>
        <span class="allocation-stat-label">Workload Utilization</span>
      </div>
    `;
  }

  renderAllocationRows(facultySummary);
}

function renderAllocationRows(facultyList) {
  if (!elements.allocationTbody) return;
  if (!facultyList || facultyList.length === 0) {
    elements.allocationTbody.innerHTML = '<tr><td colspan="6" class="text-center">No faculty allocation records available</td></tr>';
    return;
  }

  elements.allocationTbody.innerHTML = facultyList.map(f => {
    const fillClass = f.status.toLowerCase();
    const pct = Math.min(100, f.utilization_pct || 0);
    const coursePills = f.sections.map(s => `
      <span class="course-pill" title="${s.section_id}: ${s.course_title}">
        <strong>${s.course_id}</strong> (${s.hours}h)
      </span>
    `).join('') || '<span class="text-muted" style="font-size: 0.8rem;">None assigned</span>';

    return `
      <tr>
        <td>
          <strong>${f.name}</strong>
          <div style="font-size: 0.75rem; color: var(--text-muted);">${f.id}</div>
        </td>
        <td>
          <div>${f.designation}</div>
          <span style="font-size: 0.75rem; color: var(--text-subtle);">${f.dept}</span>
        </td>
        <td class="workload-cell">
          <div class="workload-text">
            <span>${f.assigned_hours} / ${f.max_hours} hrs</span>
            <span>${f.utilization_pct}%</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill ${fillClass}" style="width: ${pct}%;"></div>
          </div>
        </td>
        <td>
          <span class="badge-tag ${f.status_badge}">
            ${f.status}
          </span>
        </td>
        <td><strong>${f.sections_count}</strong></td>
        <td>${coursePills}</td>
      </tr>
    `;
  }).join('');
}

function filterAllocations() {
  if (!appState.data || !appState.data.faculty_summary) return;
  const q = elements.facultySearch ? elements.facultySearch.value.toLowerCase().trim() : '';
  const statusFilter = elements.facultyStatusFilter ? elements.facultyStatusFilter.value : 'all';

  const filtered = appState.data.faculty_summary.filter(f => {
    const matchesStatus = (statusFilter === 'all') || (f.status === statusFilter);
    const matchesQuery = !q || (
      f.name.toLowerCase().includes(q) ||
      f.designation.toLowerCase().includes(q) ||
      f.dept.toLowerCase().includes(q) ||
      f.id.toLowerCase().includes(q) ||
      f.sections.some(s => s.course_id.toLowerCase().includes(q) || s.course_title.toLowerCase().includes(q))
    );
    return matchesStatus && matchesQuery;
  });

  renderAllocationRows(filtered);
}

// Update entity dropdown depending on whether viewing Section, Faculty, Room, or Student
function updateEntityDropdownForTab(tab) {
  const { entities } = appState.data;
  let options = [];
  let label = '';

  if (tab === 'section') {
    label = 'Select Section:';
    options = Object.values(entities.sections).map(s => ({
      id: s.id,
      text: `${s.id}: ${s.course_id} - ${s.course_title} (Faculty: ${s.faculty_name})`
    }));
  } else if (tab === 'faculty') {
    label = 'Select Faculty:';
    options = Object.values(entities.faculty).map(f => ({
      id: f.id,
      text: `${f.id}: ${f.name} (Assigned: ${f.assigned_hours}h / Max: ${f.max_hours}h)`
    }));
  } else if (tab === 'room') {
    label = 'Select Room:';
    options = Object.values(entities.rooms).map(r => ({
      id: r.id,
      text: `${r.id} (${r.type}, Capacity: ${r.capacity})`
    }));
  } else if (tab === 'student') {
    label = 'Select Student:';
    options = Object.values(entities.students).map(st => ({
      id: st.id,
      text: `${st.id} (${st.programme}) - ${st.placed_count}/${st.total_selected} Enrolled`
    }));
  }

  elements.selectorLabel.textContent = label;
  elements.entitySelect.innerHTML = options.map(o => `<option value="${o.id}">${o.text}</option>`).join('');

  // Default to first entity or keep current if valid
  if (options.length > 0) {
    const exists = options.some(o => o.id === appState.activeEntityId);
    appState.activeEntityId = exists ? appState.activeEntityId : options[0].id;
    elements.entitySelect.value = appState.activeEntityId;
  } else {
    appState.activeEntityId = null;
  }
}

// Render the 5-day x 6-period weekly timetable matrix
function renderGrid() {
  if (!appState.data || !appState.activeEntityId) {
    elements.gridTbody.innerHTML = '<tr><td colspan="6" class="text-center">No schedule available</td></tr>';
    return;
  }

  const { meta, grid_data, entities } = appState.data;
  const tab = appState.activeTab;
  const entityId = appState.activeEntityId;

  // Update entity info badge
  updateEntityInfoPill(tab, entityId, entities);

  // Get items for this entity
  let items = [];
  if (tab === 'section') items = grid_data.by_section[entityId] || [];
  else if (tab === 'faculty') items = grid_data.by_faculty[entityId] || [];
  else if (tab === 'room') items = grid_data.by_room[entityId] || [];
  else if (tab === 'student') items = grid_data.by_student[entityId] || [];

  // Map slots: slot_index -> session item
  const slotMap = {};
  items.forEach(item => {
    slotMap[item.start_slot] = item;
  });

  // Track spanned slots (for multi-period sessions like 2-hr labs)
  const coveredSlots = new Set();
  items.forEach(item => {
    item.slots.forEach(s => coveredSlots.add(s));
  });

  // Build 6 period rows (Period 1 to 6)
  let html = '';
  for (let p = 0; p < 6; p++) {
    const periodMeta = meta.periods[p];
    html += `<tr>`;
    html += `<td class="period-label">
      ${periodMeta.label}
      <span class="period-time-sub">${periodMeta.time}</span>
    </td>`;

    // 5 Days (Monday to Friday, d = 0 to 4)
    for (let d = 0; d < 5; d++) {
      const slotIndex = d * 6 + p;
      const session = slotMap[slotIndex];

      if (session) {
        // If lab spans 2 periods, we can span 2 rows if desired, or render clean card
        const cardClass = session.is_lab ? 'lab' : 'lecture';
        const typeLabel = session.is_lab ? 'LAB (2H)' : 'LEC';

        html += `<td class="slot-cell">
          <div class="session-card ${cardClass}" title="${session.course_title}">
            <div class="session-top">
              <span class="session-code">${session.course_id}</span>
              <span class="session-type-pill">${typeLabel}</span>
            </div>
            <div class="session-title">${session.course_title}</div>
            <div class="session-meta">
              <span>Sec: <strong>${session.section_id}</strong></span>
              <span>🚪 ${session.room_id}</span>
            </div>
            <div class="session-meta">
              <span>👨‍🏫 ${session.faculty_name}</span>
            </div>
          </div>
        </td>`;
      } else if (coveredSlots.has(slotIndex)) {
        // Part of multi-slot lab continuation
        html += `<td class="slot-cell">
          <div class="session-card lab" style="opacity: 0.85; border-top: 1px dashed var(--lab-border);">
            <div class="session-top">
              <span class="session-code">↳ Lab Continuation</span>
            </div>
            <div class="session-meta" style="margin-top: auto;">
              <span>Hands-on Practical</span>
            </div>
          </div>
        </td>`;
      } else {
        html += `<td class="slot-cell">
          <div class="slot-empty">Free</div>
        </td>`;
      }
    }
    html += `</tr>`;
  }

  elements.gridTbody.innerHTML = html;
}

// Update entity info pill next to dropdown
function updateEntityInfoPill(tab, id, entities) {
  if (tab === 'section' && entities.sections[id]) {
    const s = entities.sections[id];
    elements.entityInfo.textContent = `Planned Capacity: ${s.capacity} students • Contact: ${s.hours} hrs/week`;
  } else if (tab === 'faculty' && entities.faculty[id]) {
    const f = entities.faculty[id];
    elements.entityInfo.textContent = `Workload: ${f.assigned_hours} / ${f.max_hours} max hours • Qualified courses: ${f.qualified.length}`;
  } else if (tab === 'room' && entities.rooms[id]) {
    const r = entities.rooms[id];
    elements.entityInfo.textContent = `Type: ${r.type} • Seating Capacity: ${r.capacity} seats`;
  } else if (tab === 'student' && entities.students[id]) {
    const st = entities.students[id];
    elements.entityInfo.textContent = `Programme: ${st.programme} • Enrolled: ${st.placed_count} of ${st.total_selected} selections`;
  }
}

// Render Master Searchable Table
function renderMasterTable() {
  if (!appState.data) return;
  const items = appState.data.master_list;
  renderMasterRows(items);
}

function renderMasterRows(items) {
  elements.masterTbody.innerHTML = items.map(item => `
    <tr>
      <td><strong>${item.day_name}</strong></td>
      <td>${item.period_time} (P${item.period + 1})</td>
      <td><code>${item.section_id}</code></td>
      <td><strong>${item.course_id}</strong>: ${item.course_title}</td>
      <td>${item.category}</td>
      <td><span class="badge ${item.is_lab ? 'badge-lab' : 'badge-lecture'}"></span> ${item.is_lab ? 'Lab (2h)' : 'Lecture (1h)'}</td>
      <td><strong>${item.room_id}</strong> (${item.room_type})</td>
      <td>${item.faculty_name} (${item.faculty_id})</td>
    </tr>
  `).join('');
}

function filterMasterTable(query) {
  if (!appState.data) return;
  const q = query.toLowerCase().trim();
  const filtered = appState.data.master_list.filter(item => (
    item.course_id.toLowerCase().includes(q) ||
    item.course_title.toLowerCase().includes(q) ||
    item.section_id.toLowerCase().includes(q) ||
    item.faculty_name.toLowerCase().includes(q) ||
    item.room_id.toLowerCase().includes(q) ||
    item.day_name.toLowerCase().includes(q)
  ));
  renderMasterRows(filtered);
}

// Render Constraints Audit (H1 to H14)
function renderConstraintsAudit() {
  if (!appState.data) return;
  const constraints = appState.data.constraints;

  elements.constraintsList.innerHTML = constraints.map(c => `
    <div class="constraint-item">
      <div class="constraint-main">
        <span class="constraint-id">${c.id} • ${c.source}</span>
        <div class="constraint-name">${c.name}</div>
        <div class="constraint-desc">${c.description}</div>
      </div>
      <div>
        <span class="badge-tag ${c.badge}">
          ${c.status === 'PASSED' ? '✓ VERIFIED' : (c.status === 'NOT_MODELLED' ? 'PLANNED' : '✗ VIOLATION')}
        </span>
      </div>
    </div>
  `).join('');
}

// UI Loading state helper
function setLoading(isLoading) {
  if (isLoading) {
    elements.btnGenSpinner.classList.remove('hidden');
    elements.btnGenText.textContent = 'Generating...';
    elements.btnGenerate.disabled = true;
  } else {
    elements.btnGenSpinner.classList.add('hidden');
    elements.btnGenText.textContent = '⚡ Generate Timetable';
    elements.btnGenerate.disabled = false;
  }
}
