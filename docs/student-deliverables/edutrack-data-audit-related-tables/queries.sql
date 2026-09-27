-- EduTrack Data Audit — all queries intentionally use JOINs and no subqueries.

-- Q1. Every enrollment with student, course and completion.
SELECT s.name AS student_name, c.title AS course_title,
       e.completion_percentage
FROM enrollments AS e
JOIN students AS s ON s.id = e.student_id
JOIN courses AS c ON c.id = e.course_id
ORDER BY s.id, c.id;

-- Q2. Students who passed at least one course.
SELECT s.name, s.email, c.title AS passed_course
FROM enrollments AS e
JOIN students AS s ON s.id = e.student_id
JOIN courses AS c ON c.id = e.course_id
WHERE e.passed = TRUE
ORDER BY s.name, c.title;

-- Q3. Average completion by instructor.
SELECT c.instructor_name,
       ROUND(AVG(e.completion_percentage), 2) AS average_completion_percentage
FROM enrollments AS e
JOIN courses AS c ON c.id = e.course_id
GROUP BY c.instructor_name
ORDER BY average_completion_percentage DESC;

-- Q4. Students with no enrollments (LEFT JOIN).
SELECT s.id, s.name, s.email
FROM students AS s
LEFT JOIN enrollments AS e ON e.student_id = s.id
LEFT JOIN courses AS c ON c.id = e.course_id
WHERE e.id IS NULL;

-- Q5. Courses with no enrollments (LEFT JOIN).
SELECT c.id, c.title, c.category
FROM courses AS c
LEFT JOIN enrollments AS e ON e.course_id = c.id
LEFT JOIN students AS s ON s.id = e.student_id
WHERE e.id IS NULL;

-- Q6. Students enrolled in more than one course.
SELECT s.name, COUNT(DISTINCT c.id) AS course_count
FROM students AS s
JOIN enrollments AS e ON e.student_id = s.id
JOIN courses AS c ON c.id = e.course_id
GROUP BY s.id, s.name
HAVING COUNT(DISTINCT c.id) > 1
ORDER BY course_count DESC, s.name;

-- Q7. Revenue by category using courses.monthly_fee (not historical payment).
SELECT c.category,
       ROUND(SUM(c.monthly_fee), 2) AS total_revenue
FROM courses AS c
JOIN enrollments AS e ON e.course_id = c.id
JOIN students AS s ON s.id = e.student_id
GROUP BY c.category
ORDER BY total_revenue DESC;

-- Q8. Instructor and number of currently enrolled students.
SELECT c.instructor_name,
       COUNT(DISTINCT s.id) AS enrolled_student_count
FROM courses AS c
JOIN enrollments AS e ON e.course_id = c.id
JOIN students AS s ON s.id = e.student_id
GROUP BY c.instructor_name
ORDER BY enrolled_student_count DESC, c.instructor_name;

-- Q9. Orphan enrollments by student (must return zero rows with valid FKs).
SELECT e.id AS enrollment_id, e.student_id
FROM enrollments AS e
LEFT JOIN students AS s ON s.id = e.student_id
LEFT JOIN courses AS c ON c.id = e.course_id
WHERE s.id IS NULL;

-- Q10. Orphan enrollments by course (must return zero rows with valid FKs).
SELECT e.id AS enrollment_id, e.course_id
FROM enrollments AS e
LEFT JOIN courses AS c ON c.id = e.course_id
LEFT JOIN students AS s ON s.id = e.student_id
WHERE c.id IS NULL;
