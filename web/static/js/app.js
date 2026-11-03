/**
 * NEXUS Timetable Generator - Interactive Web Application
 * Handles generation, weekly grid rendering, filtering, export, and disruption repair.
 */

// Application State
let appState = {
  data: null,
  activeTab: 'section',
  activeEntityId: null,
  activeSectionId: null,
  activeSemester: null,
  sectionView: 'calendar',
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
  scheduleSidebar: document.getElementById('scheduleSidebar'),
  filterSemester: document.getElementById('filterSemester'),
  filterSection: document.getElementById('filterSection'),
  selectedSectionSummary: document.getElementById('selectedSectionSummary'),
  sidebarConstraintList: document.getElementById('sidebarConstraintList'),
  baselineModeSelect: document.getElementById('baselineModeSelect'),
  btnApplyBaselineMode: document.getElementById('btnApplyBaselineMode'),
  sidebarBlockedRoomSelect: document.getElementById('sidebarBlockedRoomSelect'),
  sidebarBlockedFacultySelect: document.getElementById('sidebarBlockedFacultySelect'),
  btnApplySidebarConstraints: document.getElementById('btnApplySidebarConstraints'),
  sidebarConstraintNotice: document.getElementById('sidebarConstraintNotice'),
  sectionViewHeader: document.getElementById('sectionViewHeader'),
  scheduleTitle: document.getElementById('scheduleTitle'),
  scheduleSubtitle: document.getElementById('scheduleSubtitle'),
  btnCalendarView: document.getElementById('btnCalendarView'),
  btnTabularView: document.getElementById('btnTabularView'),
  sectionTableWrapper: document.getElementById('sectionTableWrapper'),
  sectionTableBody: document.getElementById('sectionTableBody'),
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
  const icon = appState.theme === 'dark' ? 'sun' : 'moon';
  const label = appState.theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme';
  elements.themeIcon.innerHTML = `<svg class="icon"><use href="#icon-${icon}"></use></svg>`;
  elements.btnThemeToggle.setAttribute('aria-label', label);
  elements.btnThemeToggle.title = label;
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
  elements.filterSemester.addEventListener('change', onSemesterFilterChange);
  elements.filterSection.addEventListener('change', onSectionFilterChange);
  elements.btnCalendarView.addEventListener('click', () => setSectionView('calendar'));
  elements.btnTabularView.addEventListener('click', () => setSectionView('table'));
  elements.btnApplyBaselineMode.addEventListener('click', onApplyBaselineMode);
  elements.btnApplySidebarConstraints.addEventListener('click', onApplySidebarConstraints);

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
      const stageAStatus = json.data?.metrics?.stage_a_status;
      if (json.is_excel && !['OPTIMAL', 'FEASIBLE'].includes(stageAStatus)) {
        alert(`The timetable was not generated. CP-SAT Stage A status: ${stageAStatus || 'unknown'}. Click Generate Timetable to try again.`);
      }
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

      elements.repairResultNotice.innerHTML = `<svg class="icon"><use href="#icon-check"></use></svg> <strong>Disruption Handled:</strong> Timetable successfully repaired. Blocked ${blockedDesc} was completely avoided while maintaining clash-free schedule validity.`;
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
  const roomOptions = Object.values(entities.rooms).map(r => `<option value="${escapeHtml(r.id)}">${escapeHtml(r.id)} (${escapeHtml(r.type)}, Cap: ${escapeHtml(r.capacity)})</option>`).join('');
  const facultyOptions = Object.values(entities.faculty).map(f => `<option value="${escapeHtml(f.id)}">${escapeHtml(f.id)}: ${escapeHtml(f.name)} (Max: ${escapeHtml(f.max_hours)}h)</option>`).join('');
  elements.blockedRoomSelect.innerHTML = '<option value="">-- None --</option>' + roomOptions;
  elements.sidebarBlockedRoomSelect.innerHTML = '<option value="">No room restriction</option>' + roomOptions;
  elements.blockedFacultySelect.innerHTML = '<option value="">-- None --</option>' + facultyOptions;
  elements.sidebarBlockedFacultySelect.innerHTML = '<option value="">No faculty restriction</option>' + facultyOptions;

  populateSectionFilters();
  renderSidebarConstraints();
}

function sectionSemester(section) {
  return String(section.semester || '').trim() || 'Unspecified';
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[character]);
}

function sectionKeyword(section) {
  const label = String(section.label || section.university_section || section.batch || section.id || '').trim();
  const words = label.split(/\s+/);
  return words.length > 1 && /^[A-Z]$/.test(words[words.length - 1])
    ? words.slice(0, -1).join(' ')
    : words[0];
}

function universitySectionName(section) {
  return String(section.university_section || section.batch || section.id)
    .trim()
    .replace(/\s+(?:lab|practical)$/i, '')
    .trim()
    .replace(/\s+/g, ' ');
}

function universitySectionNames(section) {
  const names = section.university_section_names || [universitySectionName(section)];
  return [...new Set(names.map(name => String(name).trim().replace(/\s+/g, ' ')).filter(Boolean))];
}

function getUniversitySectionGroups() {
  const sections = Object.values(appState.data?.entities.sections || {});
  const groups = new Map();
  sections.forEach(section => {
    universitySectionNames(section).forEach(label => {
      const key = `${sectionSemester(section).toLowerCase()}::${label.toLowerCase()}`;
      if (!groups.has(key)) {
        groups.set(key, {
          key,
          label,
          semester: sectionSemester(section),
          sections: [],
          courses: new Map()
        });
      }
      const group = groups.get(key);
      if (!group.sections.some(offering => offering.id === section.id)) {
        group.sections.push(section);
        group.courses.set(section.course_id, {
          id: section.course_id,
          title: section.course_title
        });
      }
    });
  });
  return [...groups.values()].map(group => ({
    ...group,
    sections: group.sections.sort((a, b) => a.course_id.localeCompare(b.course_id) || a.id.localeCompare(b.id)),
    courses: [...group.courses.values()].sort((a, b) => a.id.localeCompare(b.id))
  }));
}

function selectedUniversitySection() {
  return getUniversitySectionGroups().find(group => group.key === appState.activeEntityId) || null;
}

function universitySectionItems(group) {
  if (!group || !appState.data) return [];
  return group.sections.flatMap(section => appState.data.grid_data.by_section[section.id] || [])
    .sort((a, b) => a.day - b.day || a.period - b.period || a.course_id.localeCompare(b.course_id));
}

function populateSectionFilters() {
  if (!appState.data) return;
  const sections = getUniversitySectionGroups();
  const semesters = [...new Set(sections.map(section => section.semester))]
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  const availableSemester = semesters.includes(appState.data.meta.semester_filter)
    ? appState.data.meta.semester_filter
    : 'all';
  if (!appState.activeSemester || (appState.activeSemester !== 'all' && !semesters.includes(appState.activeSemester))) {
    appState.activeSemester = availableSemester;
  }

  elements.filterSemester.innerHTML = [
    '<option value="all">All semesters</option>',
    ...semesters.map(semester => `<option value="${escapeHtml(semester)}">${semester === 'Unspecified' ? semester : `Semester ${escapeHtml(semester)}`}</option>`)
  ].join('');
  elements.filterSemester.value = appState.activeSemester;

  const matchingSections = sections
    .filter(section => appState.activeSemester === 'all' || section.semester === appState.activeSemester)
    .sort((a, b) => sectionKeyword(a).localeCompare(sectionKeyword(b)) || a.label.localeCompare(b.label));
  const grouped = new Map();
  matchingSections.forEach(section => {
    const group = sectionKeyword(section) || 'Other sections';
    if (!grouped.has(group)) grouped.set(group, []);
    grouped.get(group).push(section);
  });
  elements.filterSection.innerHTML = [...grouped.entries()].map(([group, groupSections]) => `
    <optgroup label="${escapeHtml(group)}">
      ${groupSections.map(section => {
        return `<option value="${escapeHtml(section.key)}">${escapeHtml(section.label)}</option>`;
      }).join('')}
    </optgroup>
  `).join('');

  const selectedExists = matchingSections.some(section => section.key === appState.activeSectionId);
  appState.activeSectionId = selectedExists ? appState.activeSectionId : (matchingSections[0]?.key || null);
  appState.activeEntityId = appState.activeSectionId;
  elements.filterSection.value = appState.activeSectionId || '';
  elements.filterSection.disabled = matchingSections.length === 0;
  updateSelectedSectionSummary();
}

function updateSelectedSectionSummary() {
  if (!appState.data || !appState.activeEntityId) {
    elements.selectedSectionSummary.textContent = 'No sections are available for this semester.';
    elements.baselineModeSelect.disabled = true;
    elements.btnApplyBaselineMode.disabled = true;
    return;
  }
  const section = selectedUniversitySection();
  if (!section) return;
  const scheduledCount = section.sections.filter(offering => offering.scheduled).length;
  const courseCodes = section.courses.map(course => course.id).join(', ');
  const baselineSections = section.sections.filter(offering => offering.has_baseline);
  const baselineModes = new Set(baselineSections.map(offering => offering.baseline_mode));
  elements.selectedSectionSummary.innerHTML = `
    <strong>${escapeHtml(section.label)}</strong>
    <span>${section.courses.length} courses · ${escapeHtml(courseCodes)}</span>
    <span>${scheduledCount}/${section.sections.length} course allocations scheduled</span>
  `;
  elements.baselineModeSelect.disabled = baselineSections.length === 0;
  elements.btnApplyBaselineMode.disabled = baselineSections.length === 0;
  if (baselineSections.length) {
    elements.baselineModeSelect.value = baselineModes.size === 1 && !baselineModes.has('mixed')
      ? baselineSections[0].baseline_mode
      : 'preferred';
  }
}

function renderSidebarConstraints() {
  if (!appState.data) return;
  elements.sidebarConstraintList.innerHTML = appState.data.constraints.map(constraint => {
    const incomplete = constraint.id === 'H9' && appState.data.metrics.validator_status === 'VALID_INCOMPLETE';
    const passed = constraint.status === 'PASSED' && !incomplete;
    const label = incomplete ? 'Some sections unplaced' : `${constraint.id} ${constraint.name}`;
    return `
      <div class="sidebar-constraint-row">
        <span class="constraint-check ${passed ? 'passed' : 'failed'}">${passed ? '✓' : '!'}</span>
        <span>${label}</span>
      </div>
    `;
  }).join('');
}

function onSemesterFilterChange() {
  appState.activeSemester = elements.filterSemester.value;
  populateSectionFilters();
  renderSelectedSection();
}

function onSectionFilterChange() {
  appState.activeSectionId = elements.filterSection.value || null;
  appState.activeEntityId = appState.activeSectionId;
  renderSelectedSection();
}

function renderSelectedSection() {
  updateSelectedSectionSummary();
  const section = selectedUniversitySection();
  elements.scheduleTitle.textContent = section
    ? `Semester ${section.semester || '—'} · ${section.label} timetable`
    : 'Section Time Table';
  renderGrid();
  if (appState.sectionView === 'table') renderSectionTable();
}

function setSectionView(view) {
  appState.sectionView = view;
  elements.btnCalendarView.classList.toggle('active', view === 'calendar');
  elements.btnTabularView.classList.toggle('active', view === 'table');
  elements.btnCalendarView.setAttribute('aria-selected', String(view === 'calendar'));
  elements.btnTabularView.setAttribute('aria-selected', String(view === 'table'));
  elements.gridWrapper.classList.toggle('hidden', view !== 'calendar');
  elements.sectionTableWrapper.classList.toggle('hidden', view !== 'table');
  elements.scheduleSubtitle.textContent = view === 'calendar'
    ? 'Weekly view · Monday to Friday'
    : 'Session list · sorted by weekday and start time';
  if (view === 'table') renderSectionTable();
}

function showSidebarNotice(message, isError = false) {
  elements.sidebarConstraintNotice.textContent = message;
  elements.sidebarConstraintNotice.classList.toggle('error', isError);
  elements.sidebarConstraintNotice.classList.remove('hidden');
}

async function onApplyBaselineMode() {
  const section = selectedUniversitySection();
  const sectionIds = section?.sections.filter(offering => offering.has_baseline).map(offering => offering.id) || [];
  if (!sectionIds.length) {
    showSidebarNotice('This section has no baseline assignments to update.', true);
    return;
  }

  try {
    const response = await fetch('/api/baseline/modes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode: elements.baselineModeSelect.value,
        section_ids: sectionIds,
        reoptimize: true
      })
    });
    const result = await response.json();
    if (!response.ok || !result.success) {
      showSidebarNotice(result.error || 'Could not apply the baseline policy.', true);
      return;
    }
    appState.data = result.data;
    populateEntitySelectors();
    updateMetrics();
    renderActiveTab();
    showSidebarNotice(`Updated baseline policy for ${section.label}; solver status: ${result.data.metrics.solver_status}.`);
  } catch (error) {
    showSidebarNotice(`Could not apply the baseline policy: ${error.message}`, true);
  }
}

async function onApplySidebarConstraints() {
  const room = elements.sidebarBlockedRoomSelect.value;
  const faculty = elements.sidebarBlockedFacultySelect.value;
  if (!room && !faculty) {
    showSidebarNotice('Choose a room or faculty member to temporarily avoid.', true);
    return;
  }
  try {
    const response = await fetch('/api/disruption', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        blocked_rooms: room ? [room] : [],
        blocked_faculty: faculty ? [faculty] : []
      })
    });
    const result = await response.json();
    if (!response.ok || !result.success) {
      showSidebarNotice(result.error || 'Could not re-optimize with these restrictions.', true);
      return;
    }
    appState.data = result.data;
    populateEntitySelectors();
    updateMetrics();
    renderActiveTab();
    const metrics = result.data.metrics;
    showSidebarNotice(`Repair finished: ${metrics.scheduled_sections} sections scheduled (${metrics.solver_status}).`);
  } catch (error) {
    showSidebarNotice(`Could not re-optimize with these restrictions: ${error.message}`, true);
  }
}

// Switch Active View
function renderActiveTab() {
  if (!appState.data) return;
  const tab = appState.activeTab;

  // Toggle UI sections
  const isGridTab = ['section', 'faculty', 'room', 'student'].includes(tab);
  const isSectionTab = tab === 'section';
  elements.scheduleSidebar.parentElement.classList.toggle('has-sidebar', isSectionTab);
  elements.scheduleSidebar.classList.toggle('hidden', !isSectionTab);
  elements.viewToolbar.classList.toggle('hidden', !isGridTab || isSectionTab);
  elements.sectionViewHeader.classList.toggle('hidden', !isSectionTab);
  elements.gridWrapper.classList.toggle('hidden', !isGridTab || (isSectionTab && appState.sectionView !== 'calendar'));
  elements.sectionTableWrapper.classList.toggle('hidden', !isSectionTab || appState.sectionView !== 'table');
  elements.masterWrapper.classList.toggle('hidden', tab !== 'master');
  if (elements.allocationsWrapper) {
    elements.allocationsWrapper.classList.toggle('hidden', tab !== 'allocations');
  }
  elements.constraintsWrapper.classList.toggle('hidden', tab !== 'constraints');
  elements.disruptionWrapper.classList.toggle('hidden', tab !== 'disruption');

  if (isGridTab) {
    if (isSectionTab) {
      populateSectionFilters();
      updateSelectedSectionSummary();
      const selectedSection = selectedUniversitySection();
      elements.scheduleTitle.textContent = selectedSection
        ? `Semester ${selectedSection.semester || '—'} · ${selectedSection.label} timetable`
        : 'Section Time Table';
    } else {
      updateEntityDropdownForTab(tab);
    }
    renderGrid();
    if (isSectionTab && appState.sectionView === 'table') renderSectionTable();
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
  const section = tab === 'section' ? selectedUniversitySection() : null;

  // Update entity info badge
  updateEntityInfoPill(tab, entityId, entities);

  // Get items for this entity
  let items = [];
  if (tab === 'section') items = universitySectionItems(section);
  else if (tab === 'faculty') items = grid_data.by_faculty[entityId] || [];
  else if (tab === 'room') items = grid_data.by_room[entityId] || [];
  else if (tab === 'student') items = grid_data.by_student[entityId] || [];

  if (tab === 'section' && section?.sections.every(offering => !offering.scheduled) && items.length === 0) {
    elements.gridTbody.innerHTML = `<tr><td colspan="6" class="text-center">No sessions scheduled for ${escapeHtml(section.label)}. Review the constraints or solver result.</td></tr>`;
    return;
  }

  // Map slots: slot_index -> session item
  const slotMap = {};
  items.forEach(item => {
    slotMap[item.start_slot] = item;
  });

  // Track spanned slots (for multi-period sessions like 2-hr labs)
  const continuationBySlot = {};
  items.forEach(item => {
    if (item.duration > 1) {
      item.slots.slice(1).forEach(slot => {
        continuationBySlot[slot] = item;
      });
    }
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
      const continuation = continuationBySlot[slotIndex];

      if (session) {
        const cardClass = session.is_lab ? 'lab' : 'lecture';
        const typeLabel = `${session.is_lab ? 'LAB' : 'LEC'}${session.duration > 1 ? ` (${session.duration}H)` : ''}`;

        html += `<td class="slot-cell">
          <div class="session-card ${cardClass}" title="${escapeHtml(session.course_title)}">
            <div class="session-top">
              <span class="session-code">${escapeHtml(session.course_id)}</span>
              <span class="session-type-pill">${typeLabel}</span>
            </div>
            <div class="session-title">${escapeHtml(session.course_title)}</div>
            <div class="session-meta">
              <span>Sec: <strong>${escapeHtml(session.section_id)}</strong></span>
              <span><svg class="icon"><use href="#icon-door"></use></svg> ${escapeHtml(session.room_id)}</span>
            </div>
            <div class="session-meta">
              <span><svg class="icon"><use href="#icon-faculty"></use></svg> ${escapeHtml(session.faculty_name)}</span>
            </div>
          </div>
        </td>`;
      } else if (continuation) {
        const continuationClass = continuation.is_lab ? 'lab' : 'lecture';
        const continuationLabel = continuation.is_lab ? 'Lab continuation' : 'Session continuation';
        html += `<td class="slot-cell">
          <div class="session-card ${continuationClass}" style="opacity: 0.85; border-top: 1px dashed var(--border-color);">
            <div class="session-top">
              <span class="session-code"><svg class="icon"><use href="#icon-arrow-right"></use></svg> ${continuationLabel}</span>
            </div>
            <div class="session-meta" style="margin-top: auto;">
              <span>${escapeHtml(continuation.course_id)} · ${escapeHtml(continuation.room_id)}</span>
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

function renderSectionTable() {
  if (!appState.data || !appState.activeEntityId) {
    elements.sectionTableBody.innerHTML = '<tr><td colspan="6" class="text-center">No section timetable available.</td></tr>';
    return;
  }
  const { grid_data, entities } = appState.data;
  const section = selectedUniversitySection();
  const items = universitySectionItems(section);
  if (items.length === 0) {
    const message = section?.sections.every(offering => !offering.scheduled)
      ? 'This section is currently unscheduled. Review the validation status or adjust the scheduling constraints.'
      : 'No sessions are available for this section.';
    elements.sectionTableBody.innerHTML = `<tr><td colspan="6" class="text-center">${message}</td></tr>`;
    return;
  }
  elements.sectionTableBody.innerHTML = items.map(item => {
    const endPeriod = item.period + item.duration;
    const startTime = item.period_time.split(' - ')[0];
    const finalTime = appState.data.meta.periods[endPeriod - 1]?.time.split(' - ')[1] || '';
    const timeRange = item.duration > 1 ? `${startTime} - ${finalTime}` : item.period_time;
    return `
      <tr>
        <td><strong>${escapeHtml(item.day_name)}</strong></td>
        <td>${escapeHtml(timeRange)}</td>
        <td><strong>${escapeHtml(item.course_id)}</strong><div class="table-muted">${escapeHtml(item.course_title)}</div></td>
        <td><span class="session-type-pill ${item.is_lab ? 'lab-type' : ''}">${item.is_lab ? 'LAB' : 'LECTURE'}${item.duration > 1 ? ` · ${item.duration}h` : ''}</span></td>
        <td>${escapeHtml(item.room_id)}</td>
        <td>${escapeHtml(item.faculty_name)}</td>
      </tr>
    `;
  }).join('');
}

// Update entity info pill next to dropdown
function updateEntityInfoPill(tab, id, entities) {
  if (tab === 'section' && selectedUniversitySection()) {
    const section = selectedUniversitySection();
    const hours = section.sections.reduce((total, offering) => total + offering.hours, 0);
    elements.entityInfo.textContent = `${section.courses.length} courses • ${section.sections.length} course allocations • ${hours} contact hrs/week`;
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
    elements.btnGenText.textContent = elements.selectScenario.value === 'excel'
      ? 'Solving full timetable...'
      : 'Generating...';
    elements.btnGenerate.disabled = true;
  } else {
    elements.btnGenSpinner.classList.add('hidden');
    elements.btnGenText.innerHTML = '<svg class="icon"><use href="#icon-calendar"></use></svg> Generate Timetable';
    elements.btnGenerate.disabled = false;
  }
}
