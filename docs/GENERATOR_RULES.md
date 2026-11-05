# GENERATOR_RULES.md - synthetic data (always label as SYNTHETIC)
Code: `nexus_core/data_generator.py`. Seeds used so far: 329. Base size: 500 students, 53 courses, 30 faculty, 20 classrooms + 5 labs.
- Courses: 30 Major (6 per department x CSE, ECE, MECH, BBA, PSY; every 3rd has a 2h lab), 10 Minor, 5 Skill-Based, 4 Ability-Enhancement, 4 Value-Added. Theory pattern 2 x 1h; lab pattern adds 1 x 2h LAB. Credits/contact hours are placeholders - to be replaced from UGC/NEP documents (to verify).
- S1 Traditional: whole department takes the same 6 Major courses. S2 Flexible: 5 Major + 1-2 Minor. S3 Multidisciplinary: 4 Major + 2 Minor + 1 Skill + 1 AEC + 1 VAC. Pool choices follow a popularity skew (weight 1/(rank+1)^0.7).
- Sections: n = ceil(1.1 x demand / min(45, largest compatible room)); capacity = ceil(1.1 x demand / n).
- Faculty: every taught course has >= 2 qualified faculty, each faculty >= 3 courses, max 18 h/week, one afternoon unavailable.
- Rooms: classrooms 40/50/60/80 seats, labs 30/40. Grid: 5 days x 10 teaching sessions = 50 slots from 08:00 to 18:00; Session 8 and Session 10 end at the extended-session cutoffs of 16:00 and 18:00.
- University workbook scheduling assigns one morning or afternoon window per semester. Morning section offerings start at 08:00; afternoon offerings fit within 13:00-18:00. Student sectioning maximizes placed selections and reports remaining conflicts/capacity limitations.
- `unqualified_course=True` removes every qualified faculty for one course (deliberately infeasible fixture).
All rules above are team-designed assumptions, not observed university behaviour.
