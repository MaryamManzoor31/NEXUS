# NEXUS Timetable Generation Using AI

## Design Project I Report Content Draft

**Course:** E1CSA313 – Design Project I  
**Programme:** Bachelor of Technology  
**Institution:** Alliance University, Alliance School of Advanced Computing  
**Submission:** November 2026  
**Working title:** Confirm the exact approved title with the project mentor before final printing.

> This draft follows the supplied Design Project I report sequence. Bracketed items are placeholders for information or evidence that is not present in the current project workspace. Replace them before submitting. Figure and screenshot boxes are intentional insertion points.

## Cover and title page

**NEXUS: Timetable Generation Using AI**

**A DESIGN PROJECT I (E1CSA313) REPORT**

Submitted by

| Student | Registration number | Signature |
|---|---|---|
| Maryam Manzoor | 2411021060246 | [Sign] |
| N. Nikhila Sai | 2411021060255 | [Sign] |
| Mundla Hema Hasini Reddy | 2411021060288 | [Sign] |
| Lakkireddy Akshaya Reddy | 2411021060334 | [Sign] |

In partial fulfilment of the requirements for the degree of **Bachelor of Technology in [confirm official branch/specialization wording]**

Under the supervision of **Dr. Anupama K. Ingale**  
[Add the mentor's academic designation exactly as required by the department]

**Alliance School of Advanced Computing**  
**Alliance University, Bengaluru**  
**November 2026**

## Certificate

This is to certify that the Design Project I work entitled **“NEXUS: Timetable Generation Using AI”** is the bona fide work carried out by **Maryam Manzoor (2411021060246), N. Nikhila Sai (2411021060255), Mundla Hema Hasini Reddy (2411021060288), and Lakkireddy Akshaya Reddy (2411021060334)** in partial fulfilment of the requirements for the award of the Bachelor of Technology degree in **[official branch/specialization]** during the academic year **2024–2028**.

| Supervisor | Head of Department |
|---|---|
| Dr. Anupama K. Ingale  | [HOD name and signature] |
| **SUPERVISOR**  | **HEAD OF THE DEPARTMENT** |
| [Academic designation]  | [Department] |

**External Examiners**  
1. Name: ____________________ Signature: ____________________  
2. Name: ____________________ Signature: ____________________

## Declaration

We declare that this report, entitled **“NEXUS: Timetable Generation Using AI,”** has been prepared in partial fulfilment of the requirements for the Bachelor of Technology programme in **[official branch/specialization]** under the supervision of **Dr. Anupama K. Ingale**. It describes the work undertaken by our team for Design Project I. To the best of our knowledge, the report presents our implementation and experiments accurately, identifies material limitations, and gives credit to the sources used. This report has not been submitted, in whole or in part, for another academic award.

| Student | Registration number | Signature |
|---|---|---|
| Maryam Manzoor | 2411021060246 | ____________________ |
| N. Nikhila Sai | 2411021060255 | ____________________ |
| Mundla Hema Hasini Reddy | 2411021060288 | ____________________ |
| Lakkireddy Akshaya Reddy | 2411021060334 | ____________________ |

## Acknowledgement

We thank our project supervisor, **Dr. Anupama K. Ingale**, for her guidance and feedback during the development of NEXUS. We also thank **Dr. M. Selvam** and **Dr. Asha Kurian**, Design Project coordinators, and **Dr. R. Rajasekar**, Department Coordinator for Computer Science and Engineering, for their support. We are grateful to the faculty and staff of the Alliance School of Advanced Computing and Alliance University for providing the academic environment and facilities for this work.

We also thank our families and peers for their encouragement.  

**[Confirm names, designations, and acknowledgement wording with the team and mentor.]**

## Abstract

University timetabling requires courses, sections, instructors, rooms, and student course choices to be coordinated while satisfying institutional rules. Multidisciplinary selections make student conflicts harder to resolve because students may follow different course combinations. This project presents NEXUS, a web-based timetable generation and optimization prototype built around Google OR-Tools CP-SAT. It loads an existing university timetable as a baseline, accepts academic allocation data, schedules section time, room, and faculty assignments in Stage A, and allocates student selections to scheduled sections in Stage B. Hard constraints are represented in the solver and checked independently after optimization. These include room and faculty conflicts, student overlap, room and section capacity, faculty qualification and workload, session windows, automatic student-day categories, extended-session lunch protection, cohort-compatible offerings, and a maximum waiting gap between consecutive classes. The application reports partial allocations rather than disguising unplaced sections or student selections.

The packaged January 2025 university workbook was evaluated for Semester 6. It contains 318 sections, 48 representative cohort records, and 374 student course selections; the student records are not actual individual enrolments. In the latest recorded 90-second-budget run, CP-SAT scheduled all 318 sections and placed 336 of 374 selections in 57.687 seconds. Stage A returned FEASIBLE and Stage B returned OPTIMAL for the fixed section timetable. Independent validation reported VALID_INCOMPLETE with zero hard-constraint violations; 38 selections remained unplaced. These results demonstrate a feasible, section-complete schedule for this workbook-derived instance, but do not establish complete student allocation, performance on real enrolment records, or superiority over other methods. The project provides an interactive dashboard, baseline comparison, CSV/JSON export, and a Diagnostics view for incomplete results.

**Keywords:** university timetabling, constraint programming, CP-SAT, student section allocation, multidisciplinary scheduling, timetable validation.

## List of symbols and abbreviations

| Term | Meaning |
|---|---|
| AI | Artificial intelligence |
| API | Application programming interface |
| CP-SAT | Constraint Programming – Satisfiability solver in OR-Tools |
| CSV | Comma-separated values |
| H1–H18 | Hard-constraint identifiers used by the NEXUS model |
| MILP | Mixed-integer linear programming |
| NEP 2020 | National Education Policy 2020 |
| OR-Tools | Google Operations Research Tools |
| UI | User interface |
| UTC | Coordinated Universal Time |

## Contents

**Update page numbers in Word after transferring this content into the supplied template.**

1. Introduction  
2. Literature Review  
3. Identification of the Problem and Project Scope  
4. Proposed Idea and Solution  
5. Objectives  
6. Process and Methodology  
7. Requirements  
8. Novelty of the Proposed Idea  
9. Experimentation  
10. Results and Discussion  
11. Conclusion and Future Directions  
References  
Appendix A: Selected Source Code  
Appendix B: Publication Submission Page  
Appendix C: Plagiarism Report

## List of figures

Update figure numbers and page numbers after adding the actual diagrams and screenshots.

1. NEXUS system overview  
2. NEXUS application architecture  
3. Data import and normalization workflow  
4. Two-stage CP-SAT optimization workflow  
5. Student session-category and allocation workflow  
6. Dashboard baseline view  
7. Optimized timetable dashboard  
8. NEXUS Diagnostics view

## List of tables

Update table numbers and page numbers after final formatting.

1. Literature comparison  
2. Functional and non-functional requirements  
3. Hard constraints implemented in NEXUS  
4. Dataset characteristics  
5. Recorded CP-SAT results

# Chapter 1 – Introduction

## 1.1 Background

A university timetable assigns teaching activities to days and times, rooms, instructors, and student groups. A usable timetable must respect resource limits and avoid conflicts: an instructor or room cannot host two classes at the same time, students cannot attend overlapping selected courses, and rooms must meet class capacity and type requirements. Universities also impose local rules for teaching workload, student cohorts, course offerings, and preferred schedules. These requirements produce a combinatorial optimization problem whose size grows with the number of events, resources, and constraints [6], [7].

Multidisciplinary and elective pathways add another layer. Students from different programmes may select shared courses, while each course may have several sections. A timetable that is valid only at the section level can still be unusable for a student if selected courses overlap or if the student's required classes do not fit the permitted daily session. Timetabling research therefore distinguishes course or curriculum scheduling from post-enrolment student allocation and emphasizes that institutional rules and datasets differ across universities [6], [7].

## 1.2 Project context

NEXUS is a Python and Flask web application that uses OR-Tools CP-SAT as its only active timetable optimization engine. The dashboard first displays the available source baseline. Optimization is initiated by an explicit user action. The system parses an allocation workbook or CSV inputs into a common data model, creates a candidate timetable, checks the output with an independent validator, and reports both placed and unplaced requirements.

In the current code, NEXUS uses two solver stages. Stage A schedules each section's time, room, and faculty. Stage B assigns students to the scheduled sections and chooses compatible per-student day-session categories. Stage B operates on the fixed Stage A result; therefore, a Stage B allocation shortfall does not prove that no alternative Stage A timetable could achieve better student coverage.

## 1.3 Problem statement

The project addresses the following problem: **Given university course, section, faculty, room, baseline timetable, and student course-selection data, construct a timetable that respects institutional hard constraints, preserves applicable baseline assignments, and assigns as many student selections as possible, while clearly reporting any remaining infeasibility or incomplete allocation.**

## 1.4 Project overview

The project integrates workbook/CSV parsing, timetable modeling, two-stage CP-SAT optimization, independent validation, baseline comparison, and a browser-based interface. It is a constraint-based optimization application. The term “AI” in the working project title refers to automated search and optimization; NEXUS does not train a machine-learning model.

## 1.5 Report organization

Chapter 2 reviews relevant research. Chapters 3–5 define the problem, solution, and objectives. Chapter 6 describes the design and solver methodology. Chapter 7 records the software, hardware, and data requirements. Chapters 8–10 discuss contribution, experiments, results, and limitations. Chapter 11 concludes and identifies future work.

**[PLACEHOLDER – Figure 1: NEXUS system overview. Show source workbook/baseline and CSV inputs flowing through parsing, CP-SAT Stage A, CP-SAT Stage B, independent validation, dashboard diagnostics, and export.]**

## 1.6 Importance of the project

Timetable construction is a planning task with several interdependent resources. A change to a single class can affect the instructor's availability, room occupancy, a student's elective combination, and the spacing of the student's other classes. These dependencies make manual correction difficult to audit: an edit that repairs one conflict can create another conflict elsewhere. NEXUS addresses this planning burden by representing the rules explicitly and asking a constraint solver to search for a schedule that satisfies them.

The project also treats the result as something to inspect rather than a single timetable image. A schedule may be feasible yet incomplete, or it may contain violations because the input data and model disagree. The application therefore retains the baseline, reports solver status, validates the returned schedule, and lists unplaced requirements. This distinction is practically useful because it allows an administrator or evaluator to tell a proven complete schedule from a partial result that needs data correction or policy review.

The educational value of the project lies in bringing together data normalization, constraint modelling, optimization, independent validation, and an interactive application. It demonstrates how an operations-research model can be embedded in a software workflow and how assumptions should accompany experimental results. The project does not claim that software can resolve institutional policy questions when the underlying data is incomplete; instead, the diagnostics can help identify which source information needs attention.

## 1.7 Terminology used in this report

The term **section session** means one scheduled meeting of a course section, such as a lecture meeting or laboratory meeting. A section may require more than one session in a week. A **placement** is the selected day and start slot for one session, together with its room; faculty is assigned at the section level in the current model. A **student selection** is one course requirement recorded for a student or representative cohort. A **placed selection** means the student has been assigned to an eligible scheduled section for that course. These terms are kept separate because scheduling all section sessions does not automatically imply that every student selection is assigned.

The solver status **FEASIBLE** means CP-SAT found an assignment satisfying the model constraints before its search ended; it does not mean the solver proved that assignment optimal. **OPTIMAL** means the objective for that particular model and solve stage was proven optimal. Since Stage B optimizes student allocation while the section timetable from Stage A is fixed, its OPTIMAL status is conditional on that timetable and does not imply that all possible timetables have been explored.

# Chapter 2 – Literature Review

## 2.1 Overview

University course timetabling has been studied using mathematical programming, constraint programming, local search, evolutionary algorithms, and hybrid approaches. Chen et al. survey the field and note the diversity of problem formulations and the gap between benchmark methods and local real-world requirements [6]. Bashab et al. review constraints, methods, benchmark practices, and open issues [5]. The literature indicates that an algorithm's results must be interpreted against the exact constraints, data, objective, and runtime used in an experiment.

## 2.2 Paper 1: A Survey of University Course Timetabling Problem

**Reference:** M. C. Chen, S. N. Sze, S. L. Goh, N. R. Sabar, and G. Kendall, “A Survey of University Course Timetabling Problem: Perspectives, Trends and Opportunities,” *IEEE Access*, vol. 9, pp. 106515–106529, 2021 [6].

**Summary:** Chen et al. review university course timetabling formulations and solution methods, including operations-research methods, metaheuristics, hyper-heuristics, and hybrid approaches. The survey discusses hard and soft constraints, benchmark instances, real-world case studies, and the difficulty of transferring a method between institutions with different rules.

**Accomplishments and limitations:** The paper provides a broad taxonomy and identifies methodological trends and research opportunities. Its breadth is useful for positioning a project, but the survey does not validate NEXUS's particular combination of session-category, lunch, and waiting-gap rules. Its conclusions also depend on the studies and benchmark literature available at publication time.

**Relevance to NEXUS:** This work supports treating NEXUS as an institution-specific constrained optimization problem and reporting data provenance, hard constraints, soft objectives, and incomplete results explicitly. It cautions against generalizing performance from one workbook to all universities.

## 2.3 Paper 2: CP-SAT and genetic algorithms for timetable generation

**Reference:** S. Lohkare, S. Salpe, P. Gupta, S. Aote, and T. Shah, “A Comparative Analysis of Constraint Programming and Genetic Algorithms for Automated University Timetable Generation,” in *2025 IEEE Pune Section International Conference (PuneCon)*, 2025, pp. 1–6 [8].

**Summary:** This study compares a CP-SAT-based constraint-programming model with a genetic algorithm on the authors' easy, medium, and deliberately impossible timetable scenarios. The paper describes practical constraints such as visiting-faculty availability and workload balancing. The authors report that CP-SAT performed better on their tested scenarios and could prove infeasibility for their over-constrained case.

**Accomplishments and limitations:** The study directly demonstrates an experimental comparison between CP-SAT and a genetic algorithm for its chosen problem instances. Its results are specific to those instances, constraint definitions, implementation, and runtime settings. They do not establish that CP-SAT will outperform every heuristic on the NEXUS workbook or under all university policies.

**Relevance to NEXUS:** This is the closest solver-method comparison in the supplied list. NEXUS must not claim that it is the first CP-SAT timetable generator. A defensible evaluation should compare NEXUS with a baseline under identical data and hard constraints, report the solver's FEASIBLE/OPTIMAL status accurately, and include incomplete student allocations.

## 2.4 Paper 3: NEP 2020 multidisciplinary timetable generation

**Reference:** A. Affrina Prince, G. R. Subbiah, and S. V., “Design of a Smart Timetable Generator Using Artificial Intelligence for NEP 2020 Multidisciplinary Learning Models,” *Journal of Information Technology and Digital World*, vol. 8, no. 1, pp. 26–44, 2026 [10].

**Summary:** The paper presents an adaptive genetic algorithm for timetabling under NEP 2020 multidisciplinary course structures. It describes machine-learning-based adjustment of genetic-algorithm parameters and reports an evaluation involving three departments, 96 courses, 54 instructors, 24 classrooms, and 40 weekly slots.

**Accomplishments and limitations:** The work explicitly addresses flexible multidisciplinary pathways and reports implementation and experimental metrics. Its approach is an adaptive genetic algorithm with parameter tuning, not the CP-SAT model used by NEXUS. Its reported results are tied to its own implementation and data, and should not be treated as an independent comparison with NEXUS.

**Relevance to NEXUS:** This is a close application-domain precedent. NEXUS cannot claim that NEP 2020 timetable generation or multidisciplinary scheduling is new by itself. A narrower distinction to investigate is the exact hard-constraint combination and student-day allocation logic in the current NEXUS implementation, supported by direct comparison and appropriately sourced enrolment data.

## 2.5 Additional relevant studies

Algethami and Laesanklang formulate course timetabling with faculty-course assignment constraints, reinforcing the need to include instructor qualification, availability, and workload in the scheduling model [4]. Akkan, Gülcü, and Kuş study minimum-penalty timetable changes under disruptions, while Akkan and Gülcü earlier optimize penalty and robustness as two objectives [2], [3]. Their work shows why a repair feature should be evaluated by both feasibility and the amount of disruption to the existing schedule; a successful re-solve alone does not demonstrate minimum-change repair.

Sarra et al. combine graph coloring with a Grey Wolf Optimizer for a university course timetabling case [11]. Mallari et al. model coursework-calendar synchronization and student and instructor workload using multi-objective mixed-integer linear programming [9]. Xue et al. study demand-driven course scheduling and instructor assignment through a decision-support model that decomposes planning tasks [12]. Daskalaki et al. provide a foundational integer-programming case study for university timetabling [7]. Abou Kasm et al. consider exam timetabling with student conflict windows and venue capacity [1]; this is adjacent educational scheduling work, but exam scheduling is not the same problem as course timetabling.

## 2.6 Comparison of selected literature

| Ref. | Study | Method and focus | Relevance and limit for NEXUS |
|---|---|---|---|
| [1] | Abou Kasm et al., 2019 | Integer programming and heuristics for exam scheduling | Adjacent only; examination constraints differ from weekly courses |
| [2] | Akkan and Gülcü, 2018 | Hybrid multi-objective genetic algorithm with robustness | Motivates robustness evaluation; uses curriculum-based benchmark instances |
| [3] | Akkan, Gülcü, and Kuş, 2021 | Minimum-penalty perturbation under multiple disruptions | Relevant to repair; NEXUS repair is not yet established as minimum-change |
| [4] | Algethami and Laesanklang, 2021 | Mathematical course-timetabling model with faculty-course assignments | Supports explicit faculty constraints; different formulation and institution |
| [5] | Bashab et al., 2023 | Review of methods, constraints, benchmarks, and open issues | Helps structure evaluation; a review is not a direct solver comparison |
| [6] | Chen et al., 2021 | Survey of university course-timetabling research | Provides taxonomy and transferability cautions |
| [7] | Daskalaki et al., 2004 | Integer programming case study | Foundational formulation; older and tied to a specific case |
| [8] | Lohkare et al., 2025 | CP-SAT versus genetic algorithm on shared timetable scenarios | Direct solver precedent; results are instance-specific |
| [9] | Mallari et al., 2023 | Multi-objective coursework calendar and workload model | Relevant to workload and calendars; uses MILP and a distinct problem formulation |
| [10] | Affrina Prince et al., 2026 | Adaptive genetic algorithm for NEP 2020 multidisciplinary timetabling | Closest application-domain precedent; different optimization method and experiment |
| [11] | Sarra et al., 2023 | Graph coloring and Grey Wolf Optimizer | Relevant metaheuristic alternative; different model and case study |
| [12] | Xue et al., 2024 | Demand-driven planning and instructor assignment | Relevant staged planning; different objectives and operational setting |

## 2.7 Observations and research gap

The supplied literature establishes that university timetabling, faculty assignment, multidisciplinary timetables, and timetable repair all have prior research. The gap for NEXUS should therefore be framed as a practical implementation and evaluation question, not as an absence of prior work: **How effectively can a two-stage CP-SAT system optimize a provided university timetable and allocate representative student course pathways while enforcing institution-specific session, lunch, and waiting-time rules, and how transparently can it report partial results?**

The project contributes an evaluated prototype for this particular data and constraint set. Whether the constraint combination is novel requires a broader literature search and direct comparison with [8] and [10].

## 2.8 Synthesis of the literature

The reviewed work supports four conclusions relevant to the design of NEXUS. First, university timetabling is not a single standardized problem: the meaning of a feasible schedule depends on each institution's resources, course structure, and policy rules [5], [6]. Second, exact or constraint-based models can express hard restrictions directly, while metaheuristics and hybrid approaches can search effectively in different problem settings [2], [4], [8], [11]. The reported performance of any method remains tied to the formulation and test instance, so a solver comparison must use the same data, constraints, objective, and time budget.

Third, course-level timetabling and student-level allocation are related but distinct. A section timetable may use rooms and faculty without conflict and still leave a student's chosen courses impossible to attend together. Research on demand-driven planning and coursework calendars reinforces that demand, instructor assignments, and calendar structure can be modelled together or decomposed into planning stages [9], [12]. NEXUS uses decomposition: first it schedules sections, then it assigns student selections against the resulting fixed schedule. This reduces model coupling and makes each stage easier to report, but it also creates a limitation: Stage B cannot request a different Stage A timetable when student allocation is poor.

Fourth, robustness and disruptions are meaningful extensions of timetable optimization [2], [3]. NEXUS currently accepts blocked-room and blocked-faculty information in its solver interface, but it does not yet implement a general change-minimizing disruption-repair workflow with scenario history. The distinction prevents the report from overstating the repair capability. Similarly, examination-timetabling findings [1] are useful for the broader educational scheduling context, but exam events differ from recurring weekly course sessions and should not be treated as direct evidence that the same model applies unchanged.

Taken together, the literature motivates a project-specific engineering contribution: integrate section scheduling, student allocation, locally defined daily session rules, validation, and diagnostics around the supplied workbook. It does not establish that this combination is globally novel. A formal novelty claim would require a systematic database search, a documented inclusion protocol, and a controlled comparison with the closest prior work.

# Chapter 3 – Identification of the Problem and Project Scope

## 3.1 Existing problem

Preparing or revising a university timetable requires coordination among courses, sections, faculty, rooms, and student course choices. A change in one assignment can affect shared rooms, instructor schedules, student conflicts, cohort offerings, and daily time limits. A static schedule may also omit the student-level allocation information needed to determine whether each student's chosen courses can be attended.

For the packaged January 2025 workbook, an additional issue is data quality. The project documentation records 123 laboratory-to-classroom room-type mismatches in the source baseline and ten sections without baseline entries. The workbook does not provide authoritative room and section capacities or authoritative unavailability periods; the parser uses estimated capacities and treats empty availability data as unknown. These source limitations make it necessary to separate scheduling-model performance from input-data accuracy.

## 3.2 Problem definition

Given a set of courses and weekly sessions, sections, qualified faculty, rooms, baseline assignments, and student course selections, assign each section a valid time, room, and instructor, then assign students to eligible scheduled sections. Respect all encoded hard constraints. Where a complete result is not possible within the model and run, retain a feasible partial result when available and identify every unplaced section or selection.

## 3.3 Project scope

**Included in the current implementation:**

- Load and display the packaged university baseline.
- Import Excel allocation workbooks and CSV data through project parsers/importers.
- Represent courses, sections, faculty, rooms, students, sessions, and baseline assignments in a common model.
- Use CP-SAT for section placement and student allocation; no Greedy scheduler or Greedy fallback is active.
- Enforce the documented resource, workload, session, cohort, lunch, and waiting-gap constraints in solver models.
- Independently validate generated schedules and report incomplete allocation.
- Compare an optimized timetable against the source baseline.
- Display section, faculty, room, student, and master views; provide Diagnostics and CSV/JSON export.

**Outside the verified scope or limited:**

- The packaged cohort records are not actual student registrations.
- Authoritative room capacity, section capacity, and availability data are not available in the workbook.
- The web application keeps active state in process memory; uploads and runs are cleared on restart.
- SQLite persistence is available to CLI workflows but is not integrated into the web session lifecycle.
- Repair currently supports blocked rooms and faculty; it is not a general disruption history or proven minimum-change repair system.
- Full Excel export is not implemented; CSV and JSON export are available.
- The Diagnostics tab provides solver outcomes and likely resource checks; some student-conflict explanations are classifications from the current schedule rather than proofs of a unique root cause.

## 3.4 Stakeholders and operating assumptions

The primary operator is an academic administrator or timetable coordinator who can provide an allocation workbook, confirm semester scheduling policy, inspect the baseline, and review the solver result. Faculty coordinators may use the output to review teaching loads and resource assignments. Project evaluators can inspect the model, validation report, and experiment record. Students are indirect stakeholders because the student-allocation stage represents their course choices; however, the packaged representative rows do not support publishing individual student schedules.

The operational workflow assumes that the uploaded course/section records are authoritative for which teaching sessions are required, that faculty qualification fields reflect approved teaching assignments, and that room records describe available room types and capacities. Those assumptions are not all supported by the bundled workbook. Until the university supplies a room inventory, verified availability, actual capacities, and actual student registrations, a generated result should be used as a prototype/evaluation artifact rather than as an official timetable for publication.

## 3.5 Constraints and dependencies in the problem

The main entities form a dependency chain. Courses define session patterns and the room type required for each session. Sections reference courses and have enrolment capacities. Faculty members are eligible only for courses in their qualification set and are limited by availability and a weekly teaching-hour ceiling. Rooms must match the session type, provide enough seats for the section, and be available at the selected time. Students select courses and can be assigned only to compatible sections. Baseline assignments add either fixed requirements or preferences. A session choice can therefore be invalid even if its time alone appears free: its room, instructor, enrolled cohort, and student's other classes must all remain compatible.

This dependency explains why the problem is combinatorial. In a simplified model with (S) section sessions, (T) candidate time positions, (R) rooms, and (F) faculty candidates, the raw placement alternatives can grow on the order of (T \times R \times F) per session before constraints remove invalid combinations. Student choices add another set of assignment decisions. The solver does not enumerate every timetable in practice; propagation, presolve, and search guide it through the feasible region. Nonetheless, the number and interaction of decisions affect both runtime and the quality of the incumbent found under a time limit.

# Chapter 4 – Proposed Idea and Solution

NEXUS accepts an existing timetable and academic allocation data, converts them to a consistent internal representation, and lets the user explicitly run CP-SAT optimization. The solver first chooses feasible section placements and then assigns students. The solution is checked independently and shown alongside the original schedule so that incomplete allocation and baseline changes remain visible.

**[PLACEHOLDER – Figure 2: Proposed system architecture. Include the browser UI, Flask API, input parsers, canonical data model, CP-SAT stages, independent validator, metrics/serializer, and CSV/JSON exports. Show SQLite as CLI-only persistence.]**

## 4.1 Data flow

1. Load the packaged workbook/baseline, or import Excel/CSV data.
2. Parse and normalize entity identifiers, course sessions, capacities, resource qualifications, student choices, and baseline assignments.
3. Validate input structure and apply the selected semester/session settings.
4. Run Stage A to place each section's sessions, room, and faculty.
5. Run Stage B to assign student course selections to eligible scheduled sections and choose daily student categories.
6. Independently validate the resulting schedule and calculate metrics and baseline comparison.
7. Display the timetable, solver status, and diagnostics; allow CSV/JSON export.

**[PLACEHOLDER – Figure 3: Data import workflow. Show workbook/CSV input, parsing, schema and dataset checks, canonical Dataset, and baseline attachment.]**

## 4.2 Expected users

The intended users are academic administrators preparing or reviewing timetables, faculty coordinators responsible for course and instructor assignments, and project evaluators examining schedule feasibility. Student-facing individual timetable claims require actual enrolment data, which is not present in the packaged workbook.

## 4.3 Major application modules

The project separates its responsibilities into modules so that import, optimization, validation, and presentation can be reasoned about independently.

| Module or layer | Responsibility | Main project files |
|---|---|---|
| Command-line entry points | Select web, workbook, import, validation, and optimization workflows | `main.py`, `web_app.py` |
| Workbook parser | Read workbook sheets and construct courses, sections, faculty, rooms, and cohort records | `nexus_core/excel_parser.py` |
| CSV importer and input checks | Load canonical files, map columns, attach baselines, and detect malformed references | `nexus_core/importer.py`, `nexus_core/input_validator.py` |
| Canonical models and helpers | Hold normalized entities and common timetable/session calculations | `nexus_core/models.py`, `nexus_core/common.py` |
| CP-SAT engine | Build and solve Stage A and Stage B models | `nexus_core/cpsat.py` |
| Independent validator | Recheck the schedule against dataset rules without trusting the solver status | `nexus_core/validator.py` |
| Metrics and comparison | Summarize solution quality and compare original with optimized assignments | `nexus_core/metrics.py`, `nexus_core/compare.py` |
| Web routes and serialization | Accept user requests and return structured schedule data to the interface | `web/server.py`, `web/serializer.py` |
| Browser interface | Render timetable views, controls, diagnostics, and exports | `web/templates/index.html`, `web/static/` |

The separation is also a validation aid. The parser produces a canonical dataset rather than embedding solver logic in spreadsheet reading. The validator consumes the canonical dataset and resulting schedule as separate inputs, so it can check a result independently of the search model's internal status. The browser is responsible for rendering information, while the CP-SAT model is responsible for enforcing the constraints. A visual label alone does not make a schedule rule hard; the relevant rule must be present in the solver and validator.

## 4.4 User workflow

At startup, the application loads and displays the original baseline when one is available. This choice lets a user inspect existing assignments before deciding whether to run an optimization. The user selects the dataset and semester/session settings and explicitly requests timetable generation. The server then sends the normalized data and settings to the optimization engine. The solver returns stage statuses, schedule assignments, unplaced items, and runtime information. Validation and metrics are computed before the response is serialized for the browser. The user can compare the result with the source baseline, inspect section, faculty, room, or student views, and download CSV/JSON output.

If the solver returns a partial solution, the system preserves that information as partial. The dashboard distinguishes the number of scheduled sections from the number of placed student selections, and Diagnostics exposes unplaced requirements and likely explanations. This workflow is designed to support a review loop: identify data or policy gaps, correct the source or settings, and run again. It does not automatically make ambiguous source mappings authoritative.

# Chapter 5 – Objectives

1. Develop a web application for loading, displaying, and optimizing university timetable data.
2. Model section time, room, and faculty assignments using Google OR-Tools CP-SAT.
3. Assign student course selections to eligible scheduled sections while preventing overlaps and exceeding no section capacity.
4. Enforce institutional hard constraints, including student daily session windows, extended-day lunch protection, and maximum waiting time.
5. Preserve fixed baseline assignments and measure changes from preferred baseline assignments where applicable.
6. Independently validate solver output and distinguish feasible complete, feasible incomplete, and failed runs.
7. Provide diagnostic information and CSV/JSON outputs to support timetable review.
8. Evaluate the implementation on the packaged university workbook and synthetic test instances without claiming performance beyond the available data.

## 5.1 Objective hierarchy

The objectives are organized into three levels. The first level is **validity**: all hard constraints that apply to a placement or student assignment must hold. The second level is **coverage**: where partial scheduling is enabled, the solver should schedule as many section sessions as possible and assign as many student selections as possible. The third level is **quality among feasible schedules**: preserve preferred baseline values, reduce avoidable student conflicts and waiting, balance faculty load, and favor compact or consistent schedules where those preferences are represented.

This hierarchy matters when reading the results. A soft preference can be traded against another preference; a hard constraint cannot. Similarly, a high selection count does not make a schedule valid if it violates a hard rule. The independent validator reports hard violations separately from incompleteness, and the overall status distinguishes an invalid schedule from a valid schedule that simply leaves requirements unplaced.

## 5.2 Measurable project objectives

| Objective | Measurement in the current application | Interpretation |
|---|---|---|
| Schedule sections | Scheduled section sessions / required section sessions | Measures section coverage; a scheduled count alone does not prove student completeness |
| Allocate student choices | Placed selections / total recorded selections | Measures coverage of the supplied student/cohort records; data may be representative rather than individual |
| Maintain hard validity | Validator hard-violation count and status | Zero violations means no violations were found by implemented checks on the supplied data |
| Respect runtime budget | Wall-clock time and per-stage times | Enables a bounded run; a timeout may still return a feasible incumbent |
| Preserve baseline | Count and cost of changed preferred/fixed assignments | Fixed assignments are required; preferred assignments contribute a soft cost |
| Explain incompleteness | Unscheduled sections and unplaced selections with reason labels | Supports diagnosis; labels are not necessarily proofs of unique causes |

The project objective is therefore not one scalar “best timetable” claim. It is a documented trade-off among feasibility, coverage, change from baseline, workload, student convenience, and computational budget. Future evaluations should report these dimensions together rather than only one percentage.

# Chapter 6 – Process and Methodology

## 6.1 User needs and design-thinking inputs

The project brief identifies the needs addressed by NEXUS: avoid faculty and room conflicts, account for student course combinations, accommodate multidisciplinary choices, assign rooms that match type and capacity, respect student time windows, and let administrators inspect the original and optimized schedules. These needs are translated into solver constraints and dashboard views.

**Evidence note:** The current workspace does not contain records of formal user interviews, surveys, or a structured design-thinking workshop. Do not claim that such studies were conducted unless the team has those records. If conducted, insert the participants, questions, dates, and findings here.

## 6.2 Translation of needs into product features

| Need | NEXUS feature |
|---|---|
| View the existing schedule before making changes | Baseline-first dashboard and separate optimized view |
| Prevent room and faculty conflicts | Stage A CP-SAT constraints and validator checks |
| Avoid student clashes and infeasible daily patterns | Stage B CP-SAT student overlap and session constraints |
| Use multidisciplinary course offerings | Cohort-compatible section filtering and cross-program elective handling |
| Understand incomplete results | Solver statuses, unplaced selection details, and Diagnostics tab |
| Keep source timetable available for review | Baseline comparison and fixed/preferred/flexible modes |

## 6.3 Project specifications

### Functional requirements

- Read supported university workbook and CSV input formats.
- Show the existing timetable without automatically invoking optimization.
- Optimize only when the user requests it.
- Enforce section resource rules and student allocation rules in CP-SAT.
- Validate and report the result, including unplaced requirements.
- Export the timetable to CSV/JSON and display it in multiple dashboard views.

### Non-functional requirements

- Preserve the original baseline as a separate schedule.
- Avoid silently presenting infeasible or partial results as complete.
- Keep API operations consistent within the single-process web application.
- Provide sufficiently bounded solver runtime and expose stage status/runtime.
- Use interpretable reports and diagnostics for administrative review.

## 6.4 Solution design and CP-SAT formulation

### Sets, parameters, and decisions

Let `C` denote courses, `Q` sections, `K_q` the required sessions for section `q`, `R` rooms, `F` faculty, `U` students or representative cohort records, and `T` the discrete weekly time grid. For each section session, the input provides a duration, required room type, and section capacity. Faculty qualification, faculty and room unavailability, student course selections, baseline mode, and semester session settings restrict the candidate assignments.

At a high level, Stage A uses binary placement/selection variables to represent whether a section session is active at a candidate start, in a candidate room, with an eligible faculty member. The implementation also uses integer start and day/period variables where needed for time-domain constraints and preferences. Stage B uses binary assignment decisions to represent whether a student is assigned to a section for a selected course, and Boolean or integer auxiliaries to represent the student's day category and selected extended window. The implementation reuses the existing section placement variables/results as fixed inputs to Stage B rather than constructing a second competing section schedule.

The simplified mathematical description below clarifies the intent. It is not a transcription of every internal CP-SAT expression or reification detail; the maintained source code in `nexus_core/cpsat.py` remains authoritative.

### Stage A: section scheduling

Stage A uses CP-SAT decision variables for section placement, start periods, room selection, and faculty selection. Constraints prevent simultaneous use of a room or faculty member, enforce room type and capacity, faculty qualifications and availability, faculty workload, day boundaries, and applicable baseline rules. If `allow_unscheduled` is enabled, placement variables allow a best feasible partial section schedule to be returned with unplaced sections listed. A high placement penalty prioritizes scheduling sections before secondary preferences.

Secondary objectives include reducing conflicts among courses with shared students, balancing maximum faculty load, reducing time gaps, preferring selected start periods, preserving preferred baseline assignments, and reusing rooms for appropriate session sequences. Optional pairwise and consecutive-teaching preferences are omitted for larger instances to bound model-building cost; hard rules remain active.

### Stage B: student allocation and daily categories

Stage B fixes the section times selected by Stage A and creates assignment variables for student-to-section enrolment. It enforces one eligible section per selected course, student non-overlap, section capacity, student cohort/course scope, session compatibility, daily workload categories, lunch protection, and the maximum waiting gap. Its primary objective is to maximize the number of placed student selections, followed by timetable compactness and category consistency preferences.

The student category is selected for each active student-day. Morning and afternoon windows allow no more than five modelled class-period units. A required daily load above five such units requires an extended session. Extended students must have the lunch occupancy condition satisfied. For this workbook implementation, daily workload is calculated from the number of scheduled timetable periods, not by summing each period's exact clock-minute duration. The report therefore describes these as **period-equivalent class-hour units**. Confirm that this matches the institution's intended definition before claiming an exact five-clock-hour limit.

The extended lunch condition is modeled on the adjacent midday periods in the timetable grid. The waiting-time constraint uses actual timetable clock boundaries and limits the gap between consecutive classes to 120 minutes, excluding the protected lunch interval as specified by the model.

For explanation, let `x[u,q,c]` be 1 when student `u` is assigned to section `q` of selected course `c`, and 0 otherwise. Let `a[u,d,s]` indicate a daily session category `s` for student `u` on day `d`, and let `z[u,d]` indicate that the day uses an extended window. At most one selected section may satisfy a student's course choice:

\[
\sum_{q \in Q(c,u)} x_{u,q,c} \le 1,
\]

where `Q(c,u)` is the set of scheduled sections of course `c` that are eligible for student `u`. If the selection is required and a complete allocation is demanded, the corresponding right-hand side becomes equality; in the current partial-allocation workflow, unassigned selections are allowed and reported. The objective rewards each assignment, subject to capacity and compatibility constraints.

For any section session `i` occupying time interval `I_i`, student non-overlap requires that two assigned intervals for the same student not intersect. Section capacity is represented by:

\[
\sum_{u} x_{u,q,c} \le \operatorname{capacity}(q).
\]

These equations express the structure; actual CP-SAT constraints operate on the discrete model and include conditions for section eligibility, sessions, and partial assignments. Student offerings are restricted by available cohort metadata for core courses, while configured minor and elective choices can be matched across programmes.

For daily categories, the intended policy is that required daily workload—not the number of subject names—determines whether the five-hour boundary is crossed. In NEXUS's present implementation, workload uses the count of timetable periods as period-equivalent hour units. Days requiring at most five such units can be assigned an eligible morning or afternoon category. Days requiring more than five units must use an extended category, with the class intervals constrained to the corresponding early or late window. The lunch rule protects an uninterrupted midday break for extended days. Where the model's grid represents each standard period as one hour, a pair of adjacent unoccupied lunch periods supplies the lunch interval; exact clock-time treatment should be confirmed against the institution's actual bell schedule.

For a student with ordered class intervals `i` and `j`, where `j` is the next attended interval after `i`, the waiting constraint is expressed as:

\[
\operatorname{start}(j)-\operatorname{end}(i) \le 120\text{ minutes},
\]

with the model's protected extended lunch condition handled separately. Time before the first class and after the final class is not treated as an inter-class gap. The rule applies to the student's attended intervals; it is not merely a display preference.

### Objective functions and baseline handling

The model combines hard feasibility with weighted optimization preferences. In Stage A, a high penalty for leaving a section unplaced prioritizes section coverage when partial mode is allowed. Other terms represent shared-student course conflict pressure, maximum faculty load, timetable gaps, preferred starts, room continuity, baseline change cost, and other documented soft preferences. For a preferred baseline row, moving the time, changing the room, or changing the assigned faculty may incur separate weighted costs. A fixed baseline row is instead represented as a hard restriction on its applicable fields. A flexible baseline row may be used as a hint without being locked.

In Stage B, the leading objective maximizes the number of assigned selections. Secondary terms can prefer compact student days and consistency with a student's daily category. An optimal Stage B objective is conditional on the placements returned by Stage A: Stage B does not search over a new set of section placements. Therefore, end-to-end joint optimality is not established by the current decomposition.

For larger instances, selected optional objectives are omitted to reduce model-build overhead. In the documented implementation, the consecutive-teaching tie-breaker is omitted for instances above 30 sections; the shared-course-pair objective is also omitted for larger synthetic instances above the documented threshold. The system keeps the corresponding hard constraints active. The room-utilization balancing objective S9 is not implemented. This is a deliberate scope/scale trade-off, and the report does not treat omitted preferences as hard constraints.

### Solver status and partial-solution semantics

CP-SAT may return OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN, or MODEL_INVALID. NEXUS passes those statuses through rather than translating FEASIBLE into optimality. When partial scheduling is allowed, each section can be placed or explicitly listed as unscheduled. Stage B similarly maximizes assignments but can return a valid partial allocation. If the fixed Stage A schedule has no full allocation, the result can still be a valid partial timetable; this is reported as VALID_INCOMPLETE when no hard violations are detected. If all choices cannot fit under the given fixed section timetable, that does not establish infeasibility across every possible Stage A timetable.

### Hard constraints

| ID | Constraint summary |
|---|---|
| H1–H2 | No simultaneous faculty or room assignments |
| H3 | A student cannot attend overlapping selected classes |
| H4–H5 | Room capacity and room type satisfy each section session |
| H6–H7 | Faculty are qualified and faculty/rooms respect recorded unavailability |
| H8–H9 | Sessions fit the week/day; each section is scheduled or explicitly listed as unscheduled |
| H10 | Fixed baseline assignments preserve their time, room, and faculty |
| H11–H12 | At most one section per selected course; section enrolment respects capacity |
| H13–H14 | Blocked resources are avoided during repair; faculty weekly workload is bounded |
| H15 | Required per-day workload determines morning/afternoon/extended category; five-unit cap and extended lunch are enforced |
| H16 | Every student's assigned classes fit the configured semester/session window |
| H17 | Student section offerings follow cohort metadata where provided; minor/elective scope is handled as cross-program where configured |
| H18 | Consecutive student classes have no more than 120 minutes of waiting time, with the protected extended lunch handled separately |

The following interpretation table expands the rule register into operational checks. It should be used together with `docs/CONSTRAINTS.md`, which records the constraint identifiers and implementation/test mapping.

| Constraint group | Solver-stage effect | Validator evidence expected | Important data dependency |
|---|---|---|---|
| Resource non-overlap (H1–H2) | Prevent overlapping use of one faculty member or room | Any shared occupied slot by two sections is a violation | Correct section intervals and unique room/faculty identifiers |
| Room/faculty eligibility (H4–H7) | Restrict candidates by type, capacity, qualification, and availability | Room and faculty attributes are checked against each assignment | Accurate room inventory, capacities, qualifications, and unavailability |
| Baseline policy (H10) | Fixed assignments lock specified schedule fields; preferred ones add change costs | Fixed assignments are checked against the returned placement | Correct baseline mapping and chosen fixed/preferred/flexible mode |
| Student course assignment (H3, H11–H12, H17) | Select eligible section assignments while preventing conflict and over-enrolment | Recompute eligibility, overlap, and enrolment limits | Actual course selections, cohort metadata, and section capacities |
| Student daily pattern (H15–H16) | Restrict assigned classes to the permitted category/window and workload | Check the actual assigned intervals against policy | Period duration and institution-approved session boundaries |
| Student spacing (H18) | Limit consecutive attended-class waiting gap; protect extended lunch | Recompute ordered class times and lunch condition | Accurate start/end clock times and grid-to-clock mapping |
| Completeness (H9 and allocation objective) | Maximize placements when partial mode is enabled | List missing section sessions and unplaced selections | Complete source course/session requirement list |

### Independent validation

The validator is an important part of the solution design. It receives the normalized dataset and schedule, checks structural well-formedness, and recomputes applicable rules such as day boundaries, resource collisions, capacity, room type, faculty qualification, availability, baseline preservation, student assignment, session windows, workload, lunch, and waiting time. It does not simply accept a solver status as proof that the output is correct. Its report includes an overall status, hard violation count, violation breakdown, unscheduled sections, unassigned selections, and missing-information notes.

The three high-level validation outcomes have distinct meanings. **INVALID** means at least one hard rule was violated or the result was malformed. **VALID_INCOMPLETE** means the returned assignments satisfy checked hard rules but one or more required items remain unplaced. **VALID_COMPLETE** means the schedule is valid and complete according to the represented dataset and implemented rules. Even VALID_COMPLETE is bounded by the completeness and correctness of the source data and the rules encoded in software.

## 6.5 Process and design diagrams

**[PLACEHOLDER – Figure 4: End-to-end flowchart. Include load data → validate input → show baseline → user requests optimization → Stage A → Stage B → independent validation → complete/partial/failure decision → diagnostics and export.]**

**[PLACEHOLDER – Figure 5: Student-day category flowchart. Show required daily period-equivalent load ≤5 → morning or afternoon feasible window; >5 → extended early or late window; enforce the permitted window, lunch, overlap, and waiting-gap constraints.]**

**[PLACEHOLDER – Figure 6: Two-stage CP-SAT workflow. Show Stage A section/time/room/faculty variables and Stage B student/section/category variables, with the Stage A schedule passed as fixed input to Stage B.]**

### Implementation sequence

The development process follows a model-driven sequence. First, the team identifies entities and rules from the project requirements and available workbook structure. Second, parsers map workbook or CSV values to canonical records and input checks flag malformed or inconsistent references. Third, the solver creates candidate decisions for section placement and student assignment. Fourth, hard rules constrain feasible assignments while objective terms rank feasible alternatives. Fifth, the returned schedule is independently validated and summarized. Finally, the web layer serializes the results for comparison and inspection.

This sequence supports traceability: a reported constraint should map to a requirement, a solver expression, and a validator check. The constraint register lists tests for many such rules; however, the final report must be based on the current source revision and should include a fresh test-suite record only after the team runs the suite and saves its output. The report draft does not infer a passing test result from the presence of test files.

# Chapter 7 – Requirements

## 7.1 Hardware requirements

NEXUS runs on a general-purpose 64-bit computer with a supported Python installation. CP-SAT search is CPU-intensive, so a multi-core processor and at least 8 GB of RAM are recommended for development-scale workbook instances. **The specific computer model, processor, RAM, and operating-system build used for the recorded runtime were not captured; insert them before comparing runtimes across systems.**

The recommended memory and processor figures above are planning guidance rather than a measured minimum derived from a hardware stress test. A final experimental submission should identify the exact device used, processor model and core count, installed memory, operating system, Python version, OR-Tools version, and solver worker count. Runtime measurements are meaningful only when these conditions and the solver limits are stated. The solver's multi-worker search may also return different incumbents in different runs even with the same random seed.

## 7.2 Software requirements

| Component | Current project information |
|---|---|
| Language/runtime | Python 3.12.6 observed in the current environment; requirements support Python 3.10+ syntax |
| Web backend | Flask 3.1.2 observed in current environment |
| Optimization | Google OR-Tools CP-SAT 9.15.6755 observed in current environment |
| Frontend | HTML, CSS, and JavaScript |
| Data formats | Excel workbook and CSV; CSV/JSON timetable export |
| Persistence | In-memory web state; SQLite available for CLI workflows |
| Dependencies | Flask, OR-Tools, and pytest are listed in `requirements.txt` |
| Development/test commands | `python main.py web`; `python -m pytest -q` |

### Requirements traceability

| Requirement ID | Requirement statement | Implemented evidence | Verification approach |
|---|---|---|---|
| FR-01 | Load the packaged workbook and supported CSV data | Excel parser, CSV importer, canonical models | Import and input-validation scenarios |
| FR-02 | Display the original baseline before optimization | Startup loads baseline without solver call | UI inspection and route behavior |
| FR-03 | Run CP-SAT only after an explicit optimize action | Web optimize endpoint invokes solver workflow | API/UI interaction record |
| FR-04 | Schedule sections with rooms and faculty | Stage A model | Validator plus section-level run output |
| FR-05 | Assign selections without violating student rules | Stage B model | Validator and unplaced-selection report |
| FR-06 | Apply baseline fixed/preferred/flexible modes | Baseline model and Stage A costs | Mode-specific solver/validator cases |
| FR-07 | Show incomplete and failed outcomes distinctly | Status serializer and Diagnostics | Screenshot with VALID_INCOMPLETE and unplaced items |
| FR-08 | Compare and export results | Comparison endpoints and CSV/JSON outputs | Compare result and export file inspection |
| NFR-01 | Keep the original baseline intact | Separate baseline schedule and optimized result | Before/after comparison |
| NFR-02 | Bound computation | Configurable stage limits and total engine cap | Record settings and actual elapsed time |
| NFR-03 | Make validation independent of solver status | Separate `validator.py` pass | Validator report for saved schedule |
| NFR-04 | Avoid overstating uncertain source data | Assumption notes and diagnostics | Review generated report/data metadata |

These rows describe the current functional scope, not a contractual production specification. Features marked limited in Chapter 3 remain limitations even if a related endpoint or data structure exists.

## 7.3 Datasets

The primary input is the packaged **January 2025 University Allocation** workbook and its baseline timetable. The Semester 6 parse used for the recorded experiments produced 318 sections, 48 representative student records, and 374 course selections. Workbook student rows represent cohorts, not actual individual registrations. The workbook does not supply authoritative room/section capacities or all availability data; the parser's capacity estimates and empty availability values must be treated as assumptions or unknowns.

The project also includes a synthetic data generator with scenarios S1, S2, and S3 for repeatable development experiments. A synthetic run is not a substitute for actual enrolment data or an independent baseline comparison.

### Primary workbook and baseline

The packaged workbook is named `Course - Faculty Allocation - Jan 2025 onwards (30-11-24)(1).xlsx`. The parser reads the workbook's sheets through native OpenXML files and normalizes the information into NEXUS entities. The Semester 6 experiment selects the corresponding semester records. The baseline timetable file `experiments/results/timetable_univ_jan2025_sem_6.csv` contains 308 assignments for a dataset with 318 sections, so the baseline does not provide an entry for every section. Documentation records 123 baseline room-type mismatches involving laboratory sessions assigned to classroom-type rooms. Because the source workbook does not contain authoritative room-use mapping, these are unresolved data-quality issues, not grounds to silently change a room's type.

The workbook does not contain an authoritative room inventory with capacities. The current workbook parser estimates 40 seats for laboratory sections and 70 seats for lecture sections and records discovered rooms at 80 seats. It also lacks complete faculty/room unavailability data. A blank availability list means that no unavailable slot was provided to the software; it cannot be interpreted as proof that the resource is available at every time. These assumptions can affect both model feasibility and the reported allocation count.

The parser creates two representative student records for each cohort to model conflicts between typical selections. The 48 records and their 374 selections in the Semester 6 parse are therefore synthetic representatives derived from allocation patterns. They do not reveal the identity or choice set of every enrolled student. A student coverage percentage calculated from them must be labelled as representative-instance coverage, not university-wide individual enrolment coverage.

### Synthetic scenarios

The S1, S2, and S3 scenarios provide generated instances for controlled development and constraint testing. The generator documentation describes S1 as a traditional pathway, S2 as a flexible major/minor pathway, and S3 as multidisciplinary course choices. It creates courses, faculty qualifications, rooms, sections, availability assumptions, and students according to team-designed rules and a seed. Those rules are valuable for repeatability and testing edge cases but are not observed university policy. The generation assumptions—including course patterns, room sizes, student choice distributions, and faculty availability—must be described if synthetic results are included in an academic comparison.

### Data preparation and quality controls

Before interpreting a run, the data should be checked for unique identifiers, valid references between sections and courses, valid faculty-course qualification links, room types, positive capacities and durations, valid day/time values, recognized student selections, and coherent baseline modes. The import layer aims to reject malformed inputs rather than silently invent missing required values. For operational use, the team should additionally maintain a data dictionary with each column's source, unit, authority, and handling of missing values. This is especially important for the number of periods per course, the definition of a class hour, room capacity, and the time represented by each grid slot.

## 7.4 Technologies and tools

- Python for data parsing, validation, solver orchestration, and CLI workflows.
- OR-Tools CP-SAT for section scheduling and student allocation.
- Flask for the web application and API.
- HTML, CSS, and JavaScript for the browser interface.
- Project-specific parsers and canonical data models for Excel/CSV inputs.
- SQLite for optional CLI run persistence; not currently used for web-session persistence.

### Installation and execution

The application can be installed in a Python virtual environment. The project lists dependencies in `requirements.txt`; a typical local sequence is:

```text
python -m venv .venv
python -m pip install -r requirements.txt
python main.py web
```

The default web entry point serves the dashboard at `http://127.0.0.1:5001`. `web_app.py` is an alternate entry point using port 5002. The CLI also exposes workbook and synthetic workflows. Actual run commands and options should be copied from the current `README.md` when producing the final formatted report so they stay aligned with the current branch.

### Deployment and operational limits

The web application's active dataset and run state are stored in memory and protected by a process-local API lock. Restarting the process clears that active state. The CLI supports optional SQLite persistence, but the web workflow does not currently use it as a shared session store. A multi-worker deployment would require shared persistence and coordination rather than relying on process-local memory and locks. For these reasons, the project should be described as a local prototype unless deployment hardening has been completed and verified.

# Chapter 8 – Novelty of the Proposed Idea

The general use of constraint programming, CP-SAT, or genetic algorithms for university timetabling is established in prior work [6], [8]. NEP 2020 multidisciplinary timetable generation has also been studied [10]. Therefore, this project does not claim to invent CP-SAT, to be the first automated timetable system, or to be the first NEP-aligned timetable generator.

The project's potential contribution is the integration of the following features in one prototype for the supplied institutional data:

1. A baseline-first workflow that keeps the original timetable visible and starts optimization only after user action.
2. Two-stage CP-SAT scheduling: section/resource placement followed by student-to-section allocation.
3. Hard per-student daily category and time-window rules, extended-session lunch protection, and a 120-minute waiting-gap rule.
4. Independent validation and explicit reporting of feasible partial allocations, unplaced sections, and unplaced student selections.
5. A web diagnostics view that exposes solver statuses, stage times, and likely resource issues.

These are implementation contributions and potential project-specific novelty, not proof of a new optimization algorithm. A research novelty claim requires a broader literature review and a direct comparison of the exact constraints and workflow against close prior work, especially [8] and [10].

# Chapter 9 – Experimentation

## 9.1 Evaluation questions

1. Can CP-SAT schedule every section while satisfying the encoded resource and baseline constraints for the Semester 6 workbook?
2. How many representative student selections can Stage B place under the encoded session and student constraints?
3. Does the independent validator detect any hard-constraint violations in the returned schedule?
4. How do the results and runtime change under the 30-second and 90-second total budgets?

## 9.2 Experimental dataset and settings

| Setting | Value |
|---|---|
| Source | January 2025 University Allocation workbook with Semester 6 filter |
| Sections | 318 |
| Student records | 48 representative cohort records |
| Student course selections | 374 |
| Semester session mode | Automatic per-student category assignment |
| Solver | OR-Tools CP-SAT |
| 90-second workflow budget | Up to 50 seconds Stage A and 35 seconds Stage B |
| Solver workers | 4 for the packaged Excel workflow |
| Seed | 329 |
| Validation | Independent NEXUS validator |

## 9.3 Procedure

For the two 90-second comparison runs, the workbook was parsed for Semester 6, automatic per-student session mode was applied, and the packaged baseline was attached. CP-SAT then scheduled sections in Stage A and assigned student selections in Stage B. The generated schedule was passed to the independent validator. Solver stage statuses, runtime, scheduled-section count, placed-selection count, unplaced-selection count, and reason classifications were recorded. The separately saved 2026-11-05 audit artifact used the explicit morning semester setting shown in its JSON metadata, so it is identified separately in the result table.

Two 90-second-budget runs were recorded with four workers and seed 329. CP-SAT multi-worker search can be nondeterministic; therefore, these runs are reported separately rather than summarized as a guaranteed single outcome. A previous 30-second-budget run is shown for a practical runtime comparison. It is not a statistical benchmark.

### Run protocol and recorded artifacts

The project stores JSON and CSV outputs beneath `experiments/results/`, including timestamped audit runs. The JSON records the dataset label, solver and validator statuses, scheduled and unplaced counts, runtime, and other metrics. For the reproducible final submission, archive the exact source revision or commit, input workbook and baseline file versions, command or UI settings, random seed, number of workers, per-stage limits, total runtime limit, Python and OR-Tools versions, and generated output files together. If any of these are missing from an earlier experiment, mark that field as not recorded rather than inferring it from a later run.

The saved audit artifact dated 2026-11-05 provides an additional record for the packaged Semester 6 input: 296 of 318 sections were scheduled, 324 of 374 representative selections were placed, runtime was 21.172 seconds, and the validator reported VALID_INCOMPLETE with zero hard violations. Its JSON identifies OR-Tools 9.15.6755. The artifact does not record every execution setting needed for a controlled benchmark; it should be treated as a software run record, not a fully specified experimental replication.

### Evaluation measures

The report uses the following measures:

\[
\text{section coverage} = \frac{\text{scheduled sections}}{\text{required sections}} \times 100\%
\]

\[
\text{selection coverage} = \frac{\text{placed selections}}{\text{recorded selections}} \times 100\%
\]

\[
\text{hard-violation count} = \text{number of validator violations across implemented hard rules}
\]

Runtime is measured in seconds for the full optimization workflow. Stage A and Stage B runtimes should also be reported separately when available because the two stages solve different models. A high section-coverage value measures how many sections received placements; a high selection-coverage value measures how many supplied student records received course assignments. Neither measure alone captures timetable stability, room quality, fairness, or institutional data accuracy.

### Experimental validity considerations

This evaluation is a case study on one semester workbook rather than a benchmark across several universities. It has no experimental control group and no comparison with a second algorithm using exactly the same hard constraints and time budget. Repeated runs are few, so their variation should be reported rather than hidden by selecting the best result. The 48 representative student records are not a random sample of actual registrations, and the room capacity assumptions are not authoritative. The experiment therefore evaluates whether the current software produces a schedule for a workbook-derived model; it does not estimate real student satisfaction, university-wide allocation success, or general solver superiority.

For a stronger evaluation, the team should define a frozen benchmark instance, validate it with the university, run each configuration over multiple seeds, state the solver settings, and compare feasible schedules using the same validator and metrics. Report the distribution of section coverage, selection coverage, hard violations, objective components, and runtime. If the complete-allocation requirement is infeasible for some instances, report those cases and the reason rather than excluding them from the summary.

## 9.4 Visual evidence to insert

**[PLACEHOLDER – Screenshot 1: Original baseline view before optimization. Capture the dataset, semester, and baseline status.]**

**[PLACEHOLDER – Screenshot 2: Optimized timetable summary showing validation status, placed selections, sections scheduled, and solver runtime.]**

**[PLACEHOLDER – Screenshot 3: Diagnostics tab showing solver stages, stage times, unscheduled sections, and unplaced student selection reasons.]**

**[PLACEHOLDER – Screenshot 4: Student timetable view for one representative cohort. Label it as a representative record, not an actual individual student timetable.]**

**[PLACEHOLDER – Figure 7: Experiment setup and evidence chain. Show source workbook and baseline identifiers, selected semester, solver settings, saved JSON/CSV artifacts, and validator output. Do not include unredacted personal student data.]**

# Chapter 10 – Results and Discussion

## 10.1 Recorded results

| Run | Session policy | Total budget | Stage A / B status | Sections scheduled | Student selections placed | Validation | Runtime |
|---|---|---:|---|---:|---:|---|---:|
| Earlier configuration | Not recorded | 30 s | FEASIBLE / OPTIMAL | 297/318 | 322/374 | Validation status not recorded in that run output | 21.156 s |
| 90-second run 1 | Automatic per student | 90 s | FEASIBLE / OPTIMAL | 318/318 | 346/374 | Validation status not recorded in that run output | 57.530 s |
| 90-second run 2 | Automatic per student | 90 s | FEASIBLE / OPTIMAL | 318/318 | 336/374 | VALID_INCOMPLETE; 0 hard violations | 57.687 s |
| Saved audit artifact (2026-11-05) | Morning | Not recorded in artifact | FEASIBLE / OPTIMAL | 296/318 | 324/374 | VALID_INCOMPLETE; 0 hard violations | 21.172 s |

The project also contains a separate synthetic S3 audit artifact with 43 of 43 sections scheduled and 40 of 180 generated selections placed in 15.703 seconds; validation reported VALID_INCOMPLETE with zero hard violations. This generated scenario is a distinct test instance and must not be combined with the university workbook results or interpreted as real enrolment performance.

In the latest recorded run, all sections were scheduled. Stage A returned **FEASIBLE**, which means it found a feasible section schedule but did not prove it was globally optimal. Stage B returned **OPTIMAL** for the fixed Stage A section timetable, with 336 of 374 representative course selections placed. The overall schedule was **VALID_INCOMPLETE** because 38 selections remained unplaced. The independent validator recorded zero hard violations in that returned schedule.

For the latest run, the unplaced-selection diagnostics classified 30 selections as hard-constraint conflicts and 8 as student conflicts. These labels describe the current model's classification and schedule; they are not a proof that each selection is impossible under every alternative section schedule or under corrected source data. The full allocation was infeasible for the chosen Stage A schedule, not necessarily for every possible timetable.

The two 90-second runs placed 346 and 336 selections respectively. This variation is consistent with a multi-worker CP-SAT search and means one run should not be presented as a stable average or guaranteed result. More repeated runs and controlled experiments are needed for comparative claims.

### Coverage calculations

The two 90-second runs each scheduled 318 of 318 sections, corresponding to 100% section coverage for the instance. Their student-selection coverage was approximately 92.5% (346/374) and 89.8% (336/374), respectively. The saved audit artifact scheduled approximately 93.1% of sections (296/318) and placed approximately 86.6% of selections (324/374). The earlier recorded 30-second configuration scheduled approximately 93.4% of sections (297/318) and placed approximately 86.1% of selections (322/374). The calculations describe this workbook-derived representative instance only.

These runs show why section completion and student completion should be reported separately. The first two 90-second runs scheduled every section but still left 28 and 38 selections unplaced, respectively. An all-sections-scheduled result is therefore not equivalent to an all-students-allocated result. Similarly, the solver's Stage B OPTIMAL status means that it proved the maximum assignment objective for the fixed Stage A timetable and specific Stage B model; it does not certify a full allocation if the optimum is partial.

### Interpretation of unplaced selections

For the latest 90-second run, the Diagnostics output classified 30 remaining selections as hard-constraint conflicts and 8 as student conflicts. These labels identify constraints or conflicts implicated by the chosen schedule. They do not prove that those selections are impossible under every different section placement, corrected capacity, alternative room mapping, or corrected source dataset. A full diagnosis should examine each selection against the list of offered sections, the student's other assigned courses, the room and capacity data, and the session-category requirements. The dashboard's reason labels are a useful triage aid, but the report should not present them as a complete unsatisfiable core or an independently proven cause for each unplaced selection.

## 10.2 Discussion

Increasing the Excel workflow budget from 30 to 90 seconds improved the recorded section count from 297 to 318 and increased the student selections placed from 322 to between 336 and 346 in the recorded runs. This demonstrates a practical benefit of allowing more search time for this workbook instance. It does not prove that 90 seconds is optimal or that more time will place every student selection.

The student-allocation gap is materially affected by the input and model. The student rows are representative cohort records, not actual registrations. Room and section capacities are estimates, and empty availability data means unknown rather than confirmed available. The baseline itself contains documented room-type mismatches. In addition, the daily workload calculation currently counts timetable periods as class-hour units. These limitations prevent interpreting the displayed selection percentage as real individual student coverage or as a fully validated university timetable.

The independent validator's zero-violation result is evidence that the latest output satisfies the encoded checks. It does not prove that the dataset is complete, that all institutional rules are represented, or that the model is optimal. The solver's FEASIBLE Stage A status likewise should not be described as an optimal timetable.

### What the results demonstrate

For the recorded Semester 6 experiment, the solver was able to find feasible assignments at a scale of several hundred sections, and the independent validator found no hard violations in the latest fully scheduled 90-second result. The two-stage design separated section resource placement from student course allocation, and the application preserved an explicit account of requirements left unassigned. The result shows that the implemented workflow can process the supplied workbook-derived dataset and generate a reviewable partial or complete section timetable within a bounded runtime.

The results also demonstrate a diagnostic distinction between different failure types. An unscheduled section means the model did not place all sessions for that section in the returned schedule. An unplaced student selection means the course requirement was not assigned to a compatible scheduled section. The first is primarily a section resource/time placement issue; the second can result from a missing offering, a section not placed, capacity, student clashes, cohort incompatibility, session rules, or waiting/lunch rules. Resolving the correct cause requires input review as well as solver output.

### What the results do not demonstrate

The results do not establish that the solver will place all selections for every timetable instance, that no alternative Stage A timetable could improve the allocation, or that the current model is superior to a genetic algorithm, manual scheduling, or another CP-SAT formulation. They do not demonstrate student satisfaction or fairness because no actual student-level cohort dataset and no user study are included. They also do not demonstrate production readiness because persistence, multi-worker coordination, complete authoritative room data, full Excel export, and generalized repair remain limited or absent.

### Threats to validity

**Construct validity:** “Class hours” are represented as period-equivalent units in the daily workload rule, while the intended institutional rule may refer to exact clock hours. If periods differ in length, five units may not equal five hours. The report therefore calls this an implementation limitation and recommends converting all durations to minutes or confirming that each grid period represents one hour.

**Internal validity:** Multi-worker search can produce different incumbents under the same nominal seed. The Stage B model is conditioned on Stage A's schedule, so variation in Stage A placements can affect student allocations. The experiments are not repeated enough to estimate a stable distribution.

**Conclusion validity:** The measured differences between runs are descriptive. No statistical tests or controlled algorithm comparison have been conducted. A higher result in one run is not evidence of general superiority.

**External validity:** Only one university workbook and one semester filter form the primary case study. Local constraints and allocation structures vary widely, so results should not be generalized to other institutions without a new data mapping and evaluation.

**Data validity:** Capacity, availability, room mapping, baseline completeness, and representative-student records are incomplete or estimated. These input limitations can alter feasibility and coverage independently of the optimization algorithm.

**Implementation validity:** The validator checks the constraints represented in the software. It cannot certify requirements that have not been translated into the model or correct erroneous source data. A zero count only applies to the implemented checks and current dataset.

### Results table recommended for the final formatted report

Alongside the solver outcomes, the final report should include a results table with fields for source dataset/version, semester, session mode, number of courses, required section sessions, rooms, faculty, student records, selections, solver version, seed, workers, stage limits, Stage A status/time, Stage B status/time, section coverage, selection coverage, validator status, violation count, and output artifact path. Values absent from a run should be marked “not recorded.” This lets a reader reproduce or audit the result without mistaking an incomplete run for a complete timetable.

# Chapter 11 – Conclusion and Future Directions

NEXUS demonstrates an operational, baseline-first university timetabling prototype using OR-Tools CP-SAT. Its two stages schedule section resources and allocate student selections, while hard constraints and independent validation make conflicts and incomplete results explicit. In the latest recorded Semester 6 run, the system scheduled 318 of 318 sections and placed 336 of 374 representative student selections in 57.687 seconds, with zero validator hard violations and a VALID_INCOMPLETE status.

The result is promising but bounded. The system did not place all student selections; Stage A did not prove optimality; repeated 90-second runs produced different selection counts; and the workbook uses representative cohorts, estimated capacities, incomplete availability data, and a baseline with known room-type mismatches. These facts should remain visible in any project presentation or paper.

## Future work

1. Replace representative cohort records and estimated resource data with authorized, anonymized student enrolments and verified room/faculty inventories.
2. Confirm whether daily limits are defined in clock hours or timetable periods, then model durations in minutes if exact clock-hour enforcement is required.
3. Investigate all unplaced selections and the 123 baseline room-type mismatches with the university's authoritative source data.
4. Run repeated experiments across multiple seeds and budgets; report distributions, not only the best run.
5. Compare CP-SAT against an appropriate baseline on identical data and constraints, including prior CP-SAT and NEP 2020 work.
6. Evaluate minimum-change repair explicitly and expand repair scenarios beyond blocked rooms and faculty.
7. Add persistent web sessions and robust multi-worker coordination if the system is deployed beyond a local prototype.
8. Add full Excel export and refine diagnostics with constraint-level evidence for each unplaced requirement.
9. Run the complete regression suite against the final code revision and record the environment and test output.

## 11.1 Closing statement

NEXUS is a valid Design Project I prototype because it addresses a clearly defined combinatorial scheduling problem, implements a CP-SAT-based solution workflow, encodes and independently checks a documented set of hard constraints, and evaluates its behavior on a university-derived dataset while disclosing incomplete allocations and data assumptions. Its validity is that of an implemented and evaluated project prototype; it is not evidence of a universally optimal solver, a fully operational university deployment, or a novel optimization algorithm. The strongest next step is to validate the source data with the institution and rerun the experiments on actual anonymized student registrations and authoritative room and faculty availability.

# References

The following references are arranged alphabetically by first author to match the supplied report-format instructions; numbered citations are used in the text. Confirm the department's preferred citation ordering before final submission.

[1] O. Abou Kasm, B. Mohandes, A. Diabat, and S. El Khatib, “Exam timetabling with allowable conflicts within a time window,” *Computers & Industrial Engineering*, vol. 127, pp. 263–273, 2019, doi: 10.1016/j.cie.2018.11.037.

[2] C. Akkan and A. Gülcü, “A bi-criteria hybrid genetic algorithm with robustness objective for the course timetabling problem,” *Computers & Operations Research*, vol. 90, pp. 22–32, 2018, doi: 10.1016/j.cor.2017.09.007.

[3] C. Akkan, A. Gülcü, and Z. Kuş, “Minimum penalty perturbation heuristics for curriculum-based timetables subject to multiple disruptions,” *Computers & Operations Research*, vol. 132, Art. no. 105306, 2021, doi: 10.1016/j.cor.2021.105306.

[4] H. Algethami and W. Laesanklang, “A mathematical model for course timetabling problem with faculty-course assignment constraints,” *IEEE Access*, vol. 9, pp. 111666–111682, 2021, doi: 10.1109/ACCESS.2021.3103495.

[5] A. Bashab, A. O. Ibrahim, I. A. T. Hashem, K. Aggarwal, F. Mukhlif, F. A. Ghaleb, and A. Abdelmaboud, “Optimization techniques in university timetabling problem: Constraints, methodologies, benchmarks, and open issues,” *Computers, Materials & Continua*, vol. 74, no. 3, pp. 6461–6484, 2023, doi: 10.32604/cmc.2023.034051.

[6] M. C. Chen, S. N. Sze, S. L. Goh, N. R. Sabar, and G. Kendall, “A survey of university course timetabling problem: Perspectives, trends and opportunities,” *IEEE Access*, vol. 9, pp. 106515–106529, 2021, doi: 10.1109/ACCESS.2021.3100613.

[7] S. Daskalaki, T. Birbas, and E. Housos, “An integer programming formulation for a case study in university timetabling,” *European Journal of Operational Research*, vol. 153, no. 1, pp. 117–135, 2004, doi: 10.1016/S0377-2217(03)00103-6.

[8] S. Lohkare, S. Salpe, P. Gupta, S. Aote, and T. Shah, “A comparative analysis of constraint programming and genetic algorithms for automated university timetable generation,” in *2025 IEEE Pune Section International Conference (PuneCon)*, Pune, India, 2025, pp. 1–6, doi: 10.1109/PuneCon67554.2025.11379218.

[9] C. B. Mallari, J. L. San Juan, and R. Li, “The university coursework timetabling problem: An optimization approach to synchronizing course calendars,” *Computers & Industrial Engineering*, vol. 184, Art. no. 109561, 2023, doi: 10.1016/j.cie.2023.109561.

[10] A. Affrina Prince, G. R. Subbiah, and S. V., “Design of a smart timetable generator using artificial intelligence for NEP 2020 multidisciplinary learning models,” *Journal of Information Technology and Digital World*, vol. 8, no. 1, pp. 26–44, 2026, doi: 10.36548/jitdw.2026.1.003.

[11] K. Sarra, Z. Djamel, and M. Smaine, “A novel method for solving the university course timetabling problem based on the Grey Wolf Optimizer algorithm,” in *2023 Third International Conference on Theoretical and Applicative Aspects of Computer Science (ICTAACS)*, Skikda, Algeria, 2023, pp. 1–8, doi: 10.1109/ICTAACS60400.2023.10449623.

[12] G. Xue, O. F. Offodile, R. Razavi, D.-H. Kwak, and J. Benitez, “Addressing staffing challenges through improved planning: Demand-driven course schedule planning and instructor assignment in higher education,” *Decision Support Systems*, vol. 187, Art. no. 114345, 2024, doi: 10.1016/j.dss.2024.114345.

# Appendix A – Selected Source Code

The report-format document reserves three to five single-spaced pages for selected source code. Insert short, relevant excerpts rather than the entire codebase.

**[PLACEHOLDER – Insert Stage A CP-SAT placement/objective excerpt from `nexus_core/cpsat.py`.]**

**[PLACEHOLDER – Insert Stage B student allocation and category/lunch/wait constraints excerpt from `nexus_core/cpsat.py`.]**

**[PLACEHOLDER – Insert independent validation excerpt from `nexus_core/validator.py`.]**

**[PLACEHOLDER – Insert the data-flow or diagnostics rendering excerpt only if page space permits.]**

# Appendix B – Publication Submission Page

**[PLACEHOLDER – Insert the actual conference/journal submission confirmation or submission-page screenshot. Do not imply acceptance or submission unless it has occurred.]**

Target venue: [Not selected / fill after selection]  
Paper title: [Fill after the paper title is approved]  
Submission date: [Fill if submitted]  
Submission ID: [Fill if assigned]  
Status: [Draft / Submitted / Under review / Accepted – select only the true status]

# Appendix C – Plagiarism Report

**[PLACEHOLDER – Insert the actual report generated by the university-approved plagiarism-checking service. Do not fabricate a similarity score or report.]**
