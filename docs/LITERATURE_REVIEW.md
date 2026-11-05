# Literature Review: University Course Timetabling

## Related work

University course timetabling combines course times, rooms, instructors, and student requirements under institution-specific hard and soft constraints. Chen et al. survey the range of university course timetabling approaches and highlight the diversity of formulations, benchmark datasets, and real-world requirements [1]. Bashab et al. likewise review constraints, optimization methodologies, benchmarks, and open issues across university timetabling [11]. Together, these surveys caution that results on one formulation or dataset do not automatically transfer to another institution's scheduling rules.

Mathematical programming has been used to represent detailed university policies and resource limits. Daskalaki et al. formulate a real university case as a 0–1 integer program with operational rules and preferences [8]. Algethami and Laesanklang model faculty-course assignment constraints as part of course timetabling [2]. Mallari et al. study coursework calendars and student and instructor workload through a multi-objective mixed-integer linear program [6]. Xue et al. present a demand-driven planning and instructor-assignment decision-support model that decomposes the broader planning problem into stages [12]. These studies establish a strong basis for explicit constraint modeling and staged planning.

Metaheuristic approaches address the same combinatorial search problem through different tradeoffs. Sarra et al. combine graph coloring with a Grey Wolf Optimizer for university course timetabling [3]. Akkan et al. use a hybrid multi-objective genetic algorithm to balance timetable penalty and robustness to later changes [7]. Akkan, Gülcü, and Kuş study minimum-penalty perturbations under multiple disruptions [4]. These works make timetable quality and change resilience relevant evaluation dimensions, alongside basic feasibility.

Two recent studies are particularly close to the NEXUS project. Lohkare et al. compare constraint programming using OR-Tools CP-SAT with a genetic algorithm for automated university timetable generation, including visiting-faculty availability and workload considerations [5]. Affrina Prince et al. describe an adaptive genetic-algorithm timetable generator for NEP 2020 multidisciplinary learning models [10]. Consequently, NEXUS should not claim that it is the first CP-SAT timetable generator or the first timetable system addressing NEP 2020. A defensible contribution needs to be stated more narrowly and supported with a direct experimental comparison against relevant approaches.

Abou Kasm et al. study examination timetabling, where student conflict windows and venue capacity are modeled [9]. Examination scheduling is related to course timetabling, but it is a distinct problem: its results should be used as adjacent background rather than direct evidence for course timetable methods.

## Positioning of NEXUS

The NEXUS implementation uses a two-stage CP-SAT workflow: Stage A schedules sections, rooms, and faculty; Stage B assigns student course selections to the resulting section timetable. Its intended distinguishing constraint set includes automatic student-day session categories based on required class duration, morning and afternoon limits, extended-day lunch protection, and a maximum student waiting gap. It also provides a dashboard diagnostics view for partial schedules and unplaced selections. These details may support a focused contribution around constraint integration and transparent diagnosis of incomplete allocations, but they do not establish novelty by themselves.

The current workbook evaluation must be described with its data limitations. Workbook-created student rows are representative cohort records rather than actual individual enrolments, some capacities are estimates, and missing availability values are not confirmed availability. A paper should report these limitations, compare against a clearly defined baseline on identical instances, include multiple runs or explain solver determinism, and report both feasibility and unplaced demand. The recent workbook run is an implementation result, not sufficient evidence of general performance or superiority.

## Citation and submission notes

- Reference [5] is a direct CP-SAT-versus-genetic-algorithm comparison; discuss it and differentiate datasets, constraints, and experimental design before making novelty claims.
- Reference [10] directly concerns NEP 2020 multidisciplinary timetable generation; compare its formulation, data, and reported metrics with NEXUS.
- Reference [9] concerns examination timetabling, so identify it as related but distinct.
- The supplied citation list labels reference [11] as 2022, but the publisher record and DOI-indexed metadata identify it as a 2023 publication. The reference below uses 2023; confirm the required citation style before submission.
- This short review is a starting draft. A conference paper should expand the search, read the full relevant papers, and cite claims close to the sources that support them.

## References

[1] M. C. Chen, S. N. Sze, S. L. Goh, N. R. Sabar, and G. Kendall, “A Survey of University Course Timetabling Problem: Perspectives, Trends and Opportunities,” *IEEE Access*, vol. 9, pp. 106515–106529, 2021. [doi:10.1109/ACCESS.2021.3100613](https://doi.org/10.1109/ACCESS.2021.3100613).

[2] H. Algethami and W. Laesanklang, “A Mathematical Model for Course Timetabling Problem With Faculty-Course Assignment Constraints,” *IEEE Access*, vol. 9, pp. 111666–111682, 2021. [doi:10.1109/ACCESS.2021.3103495](https://doi.org/10.1109/ACCESS.2021.3103495).

[3] K. Sarra, Z. Djamel, and M. Smaine, “A Novel Method for Solving the University Course Timetabling Problem Based on the Grey Wolf Optimizer Algorithm,” in *2023 Third International Conference on Theoretical and Applicative Aspects of Computer Science (ICTAACS)*, 2023, pp. 1–8. [doi:10.1109/ICTAACS60400.2023.10449623](https://doi.org/10.1109/ICTAACS60400.2023.10449623).

[4] C. Akkan, A. Gülcü, and Z. Kuş, “Minimum Penalty Perturbation Heuristics for Curriculum-Based Timetables Subject to Multiple Disruptions,” *Computers & Operations Research*, vol. 132, Art. no. 105306, 2021. [doi:10.1016/j.cor.2021.105306](https://doi.org/10.1016/j.cor.2021.105306).

[5] S. Lohkare, S. Salpe, P. Gupta, S. Aote, and T. Shah, “A Comparative Analysis of Constraint Programming and Genetic Algorithms for Automated University Timetable Generation,” in *2025 IEEE Pune Section International Conference (PuneCon)*, 2025, pp. 1–6. [doi:10.1109/PuneCon67554.2025.11379218](https://doi.org/10.1109/PuneCon67554.2025.11379218).

[6] C. B. Mallari, J. L. San Juan, and R. Li, “The University Coursework Timetabling Problem: An Optimization Approach to Synchronizing Course Calendars,” *Computers & Industrial Engineering*, vol. 184, Art. no. 109561, 2023. [doi:10.1016/j.cie.2023.109561](https://doi.org/10.1016/j.cie.2023.109561).

[7] C. Akkan and A. Gülcü, “A Bi-Criteria Hybrid Genetic Algorithm with Robustness Objective for the Course Timetabling Problem,” *Computers & Operations Research*, vol. 90, pp. 22–32, 2018. [doi:10.1016/j.cor.2017.09.007](https://doi.org/10.1016/j.cor.2017.09.007).

[8] S. Daskalaki, T. Birbas, and E. Housos, “An Integer Programming Formulation for a Case Study in University Timetabling,” *European Journal of Operational Research*, vol. 153, no. 1, pp. 117–135, 2004. [doi:10.1016/S0377-2217(03)00103-6](https://doi.org/10.1016/S0377-2217(03)00103-6).

[9] O. Abou Kasm, B. Mohandes, A. Diabat, and S. El Khatib, “Exam Timetabling with Allowable Conflicts Within a Time Window,” *Computers & Industrial Engineering*, vol. 127, pp. 263–273, 2019. [doi:10.1016/j.cie.2018.11.037](https://doi.org/10.1016/j.cie.2018.11.037).

[10] A. Affrina Prince, G. R. Subbiah, and S. V., “Design of a Smart Timetable Generator Using Artificial Intelligence for NEP 2020 Multidisciplinary Learning Models,” *Journal of Information Technology and Digital World*, vol. 8, no. 1, pp. 26–44, 2026. [doi:10.36548/jitdw.2026.1.003](https://doi.org/10.36548/jitdw.2026.1.003).

[11] A. Bashab, A. O. Ibrahim, I. A. T. Hashem, K. Aggarwal, F. Mukhlif, F. A. Ghaleb, and A. Abdelmaboud, “Optimization Techniques in University Timetabling Problem: Constraints, Methodologies, Benchmarks, and Open Issues,” *Computers, Materials & Continua*, vol. 74, no. 3, pp. 6461–6484, 2023. [doi:10.32604/cmc.2023.034051](https://doi.org/10.32604/cmc.2023.034051).

[12] G. Xue, O. F. Offodile, R. Razavi, D.-H. Kwak, and J. Benitez, “Addressing Staffing Challenges Through Improved Planning: Demand-Driven Course Schedule Planning and Instructor Assignment in Higher Education,” *Decision Support Systems*, vol. 187, Art. no. 114345, 2024. [doi:10.1016/j.dss.2024.114345](https://doi.org/10.1016/j.dss.2024.114345).
