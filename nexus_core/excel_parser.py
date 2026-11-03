"""Native OpenXML (.xlsx) parser for NEXUS.
Parses university allocation spreadsheets (like Course - Faculty Allocation - Jan 2025 onwards)
directly using standard Python zipfile & xml.etree without requiring external packages.
"""
from __future__ import annotations
import os
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from .models import Dataset, Course, Section, Faculty, Room, Student, SessionSpec, CLASS, LAB


MAIN_NS = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL_NS = {'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}


def _extract_shared_strings(z: zipfile.ZipFile) -> list[str]:
    """Extract shared strings from the workbook."""
    shared_strings = []
    if 'xl/sharedStrings.xml' in z.namelist():
        ss_tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in ss_tree.findall('.//ns:si', MAIN_NS):
            text_elems = si.findall('.//ns:t', MAIN_NS)
            shared_strings.append(''.join(t.text or '' for t in text_elems))
    return shared_strings


def _get_sheet_target_map(z: zipfile.ZipFile) -> dict[str, str]:
    """Map sheet names to internal XML file paths."""
    wb_rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    id_to_target = {rel.attrib['Id']: rel.attrib['Target'] for rel in wb_rels}

    wb_tree = ET.fromstring(z.read('xl/workbook.xml'))
    sheet_map = {}
    for sheet in wb_tree.findall('.//ns:sheet', MAIN_NS):
        name = sheet.attrib['name'].strip()
        r_id = sheet.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        if r_id and r_id in id_to_target:
            target = id_to_target[r_id].lstrip('/')
            if not target.startswith('xl/'):
                target = 'xl/' + target
            sheet_map[name] = target
    return sheet_map


def _read_sheet_rows(z: zipfile.ZipFile, target_path: str, shared_strings: list[str]) -> list[dict[str, str]]:
    """Read rows from a worksheet XML file as dict mapping column letters to cell values."""
    if target_path not in z.namelist():
        return []
    sheet_xml = ET.fromstring(z.read(target_path))
    parsed_rows = []
    for row in sheet_xml.findall('.//ns:row', MAIN_NS):
        r_vals = {}
        for c in row.findall('.//ns:c', MAIN_NS):
            ref = c.attrib.get('r', '')
            col = ''.join([ch for ch in ref if ch.isalpha()])
            v = c.find('ns:v', MAIN_NS)
            val = v.text if v is not None else ''
            t = c.attrib.get('t')
            if t == 's' and val and val.isdigit():
                idx = int(val)
                if idx < len(shared_strings):
                    val = shared_strings[idx]
            r_vals[col] = val.strip()
        if any(r_vals.values()):
            parsed_rows.append(r_vals)
    return parsed_rows


def _clean_name(name: str) -> str:
    """Normalize faculty name by removing annotations like room numbers."""
    if not name:
        return ""
    # Remove room hints like '(LT 206 S1)'
    name = re.sub(r'\(.*?\)', '', name)
    name = name.replace('\n', ' ').strip()
    return name


def _is_unassigned_placeholder(name: str) -> bool:
    """Check if faculty name is a placeholder that requires member allocation."""
    if not name:
        return True
    n = name.lower().strip()
    return any(w in n for w in ['new faculty', 'to be', 'tbd', 'not offered', 'guest faculty', 'co-faculty'])


def parse_allocation_workbook(file_source: str | bytes | io.BytesIO, semester_filter: str = "6") -> tuple[Dataset, dict]:
    """Parse real university Excel workbook into canonical NEXUS Dataset.

    Args:
        file_source: Filepath or bytes-like object containing .xlsx file.
        semester_filter: '4', '6', '8', '2', or 'all'. Defaults to '6'.
    Returns:
        (dataset, metadata)
    """
    if isinstance(file_source, (str, os.PathLike)):
        z = zipfile.ZipFile(file_source, 'r')
    else:
        if isinstance(file_source, bytes):
            file_source = io.BytesIO(file_source)
        z = zipfile.ZipFile(file_source, 'r')

    shared_strings = _extract_shared_strings(z)
    sheet_map = _get_sheet_target_map(z)

    # 1. Parse Faculty Sheet
    faculty_dict = {}
    faculty_by_name = {}
    fac_target = sheet_map.get('Faculty') or sheet_map.get('Faculty wise (No.of hours)')
    if fac_target:
        fac_rows = _read_sheet_rows(z, fac_target, shared_strings)
        for r in fac_rows[1:]:
            name = _clean_name(r.get('B', ''))
            desig = r.get('C', '') or r.get('J', '')
            dept = r.get('D', 'CSE')
            max_h_str = r.get('E', '') or r.get('C', '')
            
            if not name or name.lower().startswith('name') or name.lower().startswith('s.no') or 'total' in name.lower():
                continue
                
            # Compute statutory max contact hours by rank
            d_lower = desig.lower()
            if 'professor' in d_lower and 'assistant' not in d_lower and 'associate' not in d_lower:
                default_hours = 12
            elif 'associate' in d_lower:
                default_hours = 14
            else:
                default_hours = 16

            try:
                max_hours = int(float(max_h_str)) if max_h_str else default_hours
            except ValueError:
                max_hours = default_hours

            fac_id = f"FAC_{len(faculty_dict) + 1:03d}"
            f_record = {
                'id': fac_id,
                'name': name,
                'designation': desig or 'Faculty',
                'dept': dept or 'CSE',
                'max_hours': max_hours,
                'qualified': set(),
                'assigned_sections': []
            }
            faculty_dict[fac_id] = f_record
            faculty_by_name[name.lower()] = fac_id

    # 2. Parse Courses and Sections from master sheets (IV-VIII SEM, 6-Course Master, II Semester, etc.)
    master_targets = [
        sheet_map.get('IV- VIII SEM'),
        sheet_map.get('6-Course Master'),
        sheet_map.get('8-course master'),
        sheet_map.get('II Semester')
    ]
    # Filter out None
    master_targets = [t for t in master_targets if t]

    courses_dict = {}
    sections_dict = {}
    pre_assigned_faculty = {}
    unassigned_sections = []
    
    # Track lecture halls and rooms mentioned in sheets and standard campus blocks
    discovered_rooms = set([
        "LT 201", "LT 204", "LT 206", "LT 209", "LT 210", 
        "LT 212", "LT 213", "LT 215", "LT 216", "LT 304", 
        "LT 403", "LT 405", "CS Room"
    ])
    # Add campus block lecture halls
    for fl in [1, 2, 3, 4]:
        for rm in range(1, 9):
            discovered_rooms.add(f"LT {fl:d}0{rm:d}")

    discovered_labs = set([
        f"CS Lab {i:02d}" for i in range(1, 13)
    ])

    for target in master_targets:
        rows = _read_sheet_rows(z, target, shared_strings)
        for r in rows[1:]:
            prog = r.get('C', '')
            sem = r.get('D', '')
            code = r.get('E', '')
            title = r.get('F', '')
            fac_raw = r.get('G', '')
            ctype = r.get('J', 'Core')
            l_str = r.get('L', '0')
            t_str = r.get('M', '0')
            p_str = r.get('N', '0')
            cred_str = r.get('P', '3')
            sec_name = r.get('Q', '')

            # Check semester filter
            if semester_filter and semester_filter.lower() != 'all':
                if sem != semester_filter:
                    continue

            if not code or not title or not sec_name:
                continue

            # Standardize numbers
            try:
                L = int(float(l_str)) if l_str else 0
            except ValueError:
                L = 2
            try:
                T = int(float(t_str)) if t_str else 0
            except ValueError:
                T = 0
            try:
                P = int(float(p_str)) if p_str else 0
            except ValueError:
                P = 0
            try:
                credits = int(float(cred_str)) if cred_str else 3
            except ValueError:
                credits = 3

            # Determine sessions pattern
            is_lab_sec = 'lab' in sec_name.lower() or (P > 0 and 'lab' in sec_name.lower())
            if is_lab_sec:
                # Practical lab session: typically 2 periods in LAB
                sessions = (SessionSpec(duration=2, room_type=LAB),)
            else:
                # Lecture session: e.g. 2 periods in CLASS (or 1 period each)
                # For timetabling in 6 periods/day, contacts are usually 1 or 2 periods
                dur = max(1, min(L, 2)) if L > 0 else 1
                sessions = (SessionSpec(duration=dur, room_type=CLASS),)

            if code not in courses_dict:
                category = "Program Elective" if "elective" in ctype.lower() else "Core"
                courses_dict[code] = Course(
                    id=code,
                    title=title,
                    category=category,
                    credits=credits,
                    sessions=sessions,
                    programme_id=prog,
                    stream=prog,
                    semester=sem,
                    course_type=ctype,
                    department_id="CSE",
                    school_id="SOET",
                )

            # Unique section identifier
            clean_sec_slug = re.sub(r'[^a-zA-Z0-9]', '_', sec_name.strip()).strip('_')
            sec_id = f"{code}_{clean_sec_slug}"

            # Capacity: labs typically 30-40, lectures 60-80
            capacity = 40 if is_lab_sec else 70

            sections_dict[sec_id] = Section(
                id=sec_id,
                course_id=code,
                capacity=capacity,
                programme_id=prog,
                stream=prog,
                semester=sem,
                batch=sec_name,
                department_id="CSE",
                school_id="SOET",
                sessions=sessions,
            )

            # Check faculty assignment
            fac_name = _clean_name(fac_raw)
            if not _is_unassigned_placeholder(fac_name):
                # Search in faculty dict
                fid = faculty_by_name.get(fac_name.lower())
                if not fid:
                    # Register this faculty member if not in faculty sheet
                    fid = f"FAC_{len(faculty_dict) + 1:03d}"
                    faculty_dict[fid] = {
                        'id': fid,
                        'name': fac_name,
                        'designation': r.get('H', 'Assistant Professor') or 'Assistant Professor',
                        'dept': 'CSE',
                        'max_hours': 16,
                        'qualified': set(),
                        'assigned_sections': []
                    }
                    faculty_by_name[fac_name.lower()] = fid
                
                faculty_dict[fid]['qualified'].add(code)
                faculty_dict[fid]['assigned_sections'].append(sec_id)
                pre_assigned_faculty[sec_id] = fid
            else:
                unassigned_sections.append(sec_id)

    # 3. Create Canonical Faculty Objects
    final_faculty = {}
    for fid, f in faculty_dict.items():
        # Ensure faculty is qualified for courses they are assigned to
        qual = frozenset(f['qualified']) if f['qualified'] else frozenset(courses_dict.keys())
        final_faculty[fid] = Faculty(
            id=fid,
            name=f['name'],
            qualified=qual,
            max_hours=f['max_hours'],
            unavailable=frozenset(),
            department_id=f.get('dept', '') or '',
            designation=f.get('designation', '') or '',
            school_id="SOET",
        )

    # 4. Create Room Objects
    final_rooms = {}
    for r_name in sorted(discovered_rooms):
        rid = re.sub(r'\s+', '_', r_name.strip())
        final_rooms[rid] = Room(
            id=rid,
            type=CLASS,
            capacity=80,
            unavailable=frozenset()
        )
    for l_name in sorted(discovered_labs):
        lid = re.sub(r'\s+', '_', l_name.strip())
        final_rooms[lid] = Room(
            id=lid,
            type=LAB,
            capacity=80,
            unavailable=frozenset()
        )

    # 5. Build Cohort Students to enforce clash-free cohort scheduling (H3)
    # Group sections by common class cohort (e.g., 'AIML_A', 'CS_B', 'CSE_Gen_A')
    cohort_sections = defaultdict(list)
    for sid, sec in sections_dict.items():
        cohort_names = [
            re.sub(
                r"\s+", " ",
                re.sub(r"\s+(?:lab|practical)$", "", name.strip(), flags=re.IGNORECASE).strip()
            )
            for name in sec.batch.split(",")
        ] if sec.batch.strip() else [sid]
        for cohort_name in filter(None, cohort_names):
            cohort_key = (sec.semester, cohort_name.casefold())
            cohort_sections[cohort_key].append((cohort_name, sec.course_id))

    final_students = {}
    st_counter = 1
    for (semester, _), offerings in cohort_sections.items():
        cohort_name = offerings[0][0]
        unique_courses = tuple(dict.fromkeys(course_id for _, course_id in offerings))
        # Create a representative student cohort for each group
        for _ in range(2):  # 2 representative students per cohort for constraint H3
            stid = f"STU_{st_counter:03d}_{semester}_{cohort_name}"
            final_students[stid] = Student(
                id=stid,
                programme=cohort_name,
                selections=unique_courses
            )
            st_counter += 1

    ds_name = f"univ_jan2025_sem_{semester_filter}"
    dataset = Dataset(
        name=ds_name,
        courses=courses_dict,
        sections=sections_dict,
        faculty=final_faculty,
        rooms=final_rooms,
        students=final_students,
        synthetic=False,
        meta={
            "source_file": "Course - Faculty Allocation - Jan 2025 onwards (30-11-24)(1).xlsx",
            "semester_filter": semester_filter,
            "total_pre_assigned": len(pre_assigned_faculty),
            "total_unassigned": len(unassigned_sections)
        }
    )

    metadata = {
        "total_pre_assigned": len(pre_assigned_faculty),
        "total_unassigned": len(unassigned_sections),
        "pre_assigned_faculty": pre_assigned_faculty,
        "unassigned_sections": unassigned_sections,
        "raw_faculty_info": faculty_dict,
        "discovered_rooms": sorted(list(discovered_rooms)),
        "discovered_labs": sorted(list(discovered_labs)),
    }

    return dataset, metadata
