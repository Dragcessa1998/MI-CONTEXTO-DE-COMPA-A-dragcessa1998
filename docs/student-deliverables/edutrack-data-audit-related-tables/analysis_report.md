# EduTrack Data Audit — Related Tables

## Schema and relationships

`students (1) ——< enrollments >—— (1) courses`. `enrollments.student_id` references
`students.id` and `enrollments.course_id` references `courses.id`. Therefore students
and courses are related many-to-many through enrollments.

The results below were obtained by loading `edutrack_v2.sql` into SQLite for a
deterministic local audit. The same SQL is PostgreSQL/Supabase compatible.

## Q1 — Every enrollment

16 rows are returned. The query exposes the student name, course title and completion
percentage for every enrollment. It confirms that every enrollment joins to both parent
tables.

## Q2 — Students who passed a course

| Student | Email | Course |
|---|---|---|
| Emily Watson | emily.watson@student.edutrack.com | Intro to Python |
| Klaus Weber | klaus.weber@student.edutrack.com | Data Analysis with SQL |
| Klaus Weber | klaus.weber@student.edutrack.com | Intro to Python |
| Marco Rossi | marco.rossi@student.edutrack.com | Advanced Python |
| Marco Rossi | marco.rossi@student.edutrack.com | Intro to Python |
| Priya Sharma | priya.sharma@student.edutrack.com | Digital Marketing 101 |

## Q3 — Average completion by instructor

| Instructor | Average completion |
|---|---:|
| Marta López | 66.14% |
| Carlos Vega | 40.00% |
| Lucia Prades | 36.50% |
| Pending assignment | 0.00% |

## Q4 — Students with no enrollments

`Giulia Romano (id 8)` is the only student without an enrollment.

## Q5 — Courses with no enrollments

`Email Campaigns (id 7, Marketing)` is the only course without an enrollment.

## Q6 — Students enrolled in more than one course

| Student | Course count |
|---|---:|
| Emily Watson | 3 |
| Lucia Fernandes | 3 |
| Klaus Weber | 2 |
| Marco Rossi | 2 |
| Yuki Nakamura | 2 |
| Pierre Dubois | 2 |
| Priya Sharma | 2 |

## Q7 — Revenue by category using current course price

The calculation sums `courses.monthly_fee` once per enrollment, as requested.

| Category | Total revenue |
|---|---:|
| Programming | 409.93 |
| Data | 179.97 |
| Design | 169.96 |
| Marketing | 59.98 |

## Q8 — Students currently enrolled per instructor

| Instructor | Distinct students |
|---|---:|
| Marta López | 6 |
| Carlos Vega | 3 |
| Lucia Prades | 2 |
| Pending assignment | 2 |

## Q9 — Orphaned student references

Zero rows. Every `enrollments.student_id` matches an existing `students.id`.

## Q10 — Orphaned course references

Zero rows. Every `enrollments.course_id` matches an existing `courses.id`.

## Audit conclusion

The normalized dataset contains 8 students, 7 courses and 16 enrollments. Foreign-key
integrity is clean. One student and one course are unused and are candidates for the
operations team to review. Revenue and completion metrics are calculated through
explicit joins, with no subqueries.
