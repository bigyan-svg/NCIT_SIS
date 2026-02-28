-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Feb 03, 2026 at 06:49 PM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `ncit_sis`
--

-- --------------------------------------------------------

--
-- Table structure for table `attendance`
--

CREATE TABLE `attendance` (
  `attendance_id` int(11) NOT NULL,
  `course_id` int(11) DEFAULT NULL,
  `student_id` int(11) DEFAULT NULL,
  `attendance_date` date DEFAULT NULL,
  `status` enum('Present','Absent') DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `attendance`
--

INSERT INTO `attendance` (`attendance_id`, `course_id`, `student_id`, `attendance_date`, `status`) VALUES
(4, 5, 19, '2026-01-28', 'Present');

-- --------------------------------------------------------

--
-- Table structure for table `book_categories`
--

CREATE TABLE `book_categories` (
  `category_id` int(11) NOT NULL,
  `name` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `book_categories`
--

INSERT INTO `book_categories` (`category_id`, `name`) VALUES
(1, 'BE-Computer');

-- --------------------------------------------------------

--
-- Table structure for table `borrows`
--

CREATE TABLE `borrows` (
  `borrow_id` int(11) NOT NULL,
  `book_id` int(11) NOT NULL,
  `student_id` int(11) NOT NULL,
  `borrow_date` date NOT NULL,
  `due_date` date NOT NULL,
  `return_date` date DEFAULT NULL,
  `fine` decimal(10,2) DEFAULT 0.00
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `borrows`
--

INSERT INTO `borrows` (`borrow_id`, `book_id`, `student_id`, `borrow_date`, `due_date`, `return_date`, `fine`) VALUES
(2, 2, 19, '2026-01-29', '2026-02-12', NULL, 0.00);

-- --------------------------------------------------------

--
-- Table structure for table `courses`
--

CREATE TABLE `courses` (
  `course_id` int(11) NOT NULL,
  `course_name` varchar(100) NOT NULL,
  `course_code` varchar(20) NOT NULL,
  `dept_id` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `courses`
--

INSERT INTO `courses` (`course_id`, `course_name`, `course_code`, `dept_id`) VALUES
(5, 'Database Management System', 'DB101', 3);

-- --------------------------------------------------------

--
-- Table structure for table `departments`
--

CREATE TABLE `departments` (
  `dept_id` int(11) NOT NULL,
  `dept_name` varchar(100) NOT NULL,
  `hod_name` varchar(100) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `departments`
--

INSERT INTO `departments` (`dept_id`, `dept_name`, `hod_name`) VALUES
(3, 'BE-Computer', 'Amit Shrivastava'),
(4, 'BCA', 'Shivahari Acharya');

-- --------------------------------------------------------

--
-- Table structure for table `exam_schedule`
--

CREATE TABLE `exam_schedule` (
  `exam_id` int(11) NOT NULL,
  `course_id` int(11) DEFAULT NULL,
  `exam_date` date DEFAULT NULL,
  `start_time` time DEFAULT NULL,
  `room_no` varchar(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `exam_schedule`
--

INSERT INTO `exam_schedule` (`exam_id`, `course_id`, `exam_date`, `start_time`, `room_no`) VALUES
(3, 5, '2026-01-31', '11:00:00', 'E-Block Room No.123');

-- --------------------------------------------------------

--
-- Table structure for table `fees`
--

CREATE TABLE `fees` (
  `fee_id` int(11) NOT NULL,
  `student_id` int(11) DEFAULT NULL,
  `amount` decimal(10,2) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  `status` enum('Paid','Pending') DEFAULT 'Pending'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `fees`
--

INSERT INTO `fees` (`fee_id`, `student_id`, `amount`, `description`, `status`) VALUES
(5, 19, 26100.00, 'total fees of 4 years computer engineering course', 'Paid');

-- --------------------------------------------------------

--
-- Table structure for table `library_books`
--

CREATE TABLE `library_books` (
  `book_id` int(11) NOT NULL,
  `title` varchar(255) NOT NULL,
  `author` varchar(255) NOT NULL,
  `category_id` int(11) DEFAULT NULL,
  `isbn` varchar(50) DEFAULT NULL,
  `copies_total` int(11) DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `library_books`
--

INSERT INTO `library_books` (`book_id`, `title`, `author`, `category_id`, `isbn`, `copies_total`) VALUES
(2, 'Database Management System', 'Balaguruswamy', 1, '1234353', 100);

-- --------------------------------------------------------

--
-- Table structure for table `notices`
--

CREATE TABLE `notices` (
  `notice_id` int(11) NOT NULL,
  `title` varchar(200) DEFAULT NULL,
  `content` text DEFAULT NULL,
  `target_role` enum('all','student','teacher') DEFAULT 'all',
  `date_posted` datetime DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `notices`
--

INSERT INTO `notices` (`notice_id`, `title`, `content`, `target_role`, `date_posted`) VALUES
(4, 'DBMS exam notice', 'Date:  2026-01-31	     Time: 11:00:00	Course: Database Management System	  Room: E-Block Room No.123	\r\n', 'all', '2026-01-28 22:29:28');

-- --------------------------------------------------------

--
-- Table structure for table `student_enrollments`
--

CREATE TABLE `student_enrollments` (
  `enrollment_id` int(11) NOT NULL,
  `student_id` int(11) DEFAULT NULL,
  `course_id` int(11) DEFAULT NULL,
  `date_enrolled` date DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `student_enrollments`
--

INSERT INTO `student_enrollments` (`enrollment_id`, `student_id`, `course_id`, `date_enrolled`) VALUES
(7, 19, 5, '2026-01-28');

-- --------------------------------------------------------

--
-- Table structure for table `student_results`
--

CREATE TABLE `student_results` (
  `result_id` int(11) NOT NULL,
  `student_id` int(11) DEFAULT NULL,
  `course_id` int(11) DEFAULT NULL,
  `teacher_id` int(11) DEFAULT NULL,
  `marks_obtained` decimal(5,2) DEFAULT NULL,
  `grade` varchar(5) DEFAULT NULL,
  `full_marks` decimal(5,2) DEFAULT 100.00,
  `gpa` decimal(3,2) DEFAULT 0.00,
  `exam_type` varchar(50) DEFAULT 'Final',
  `academic_year` smallint(5) unsigned NOT NULL DEFAULT 2026
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `student_results`
--

INSERT INTO `student_results` (`result_id`, `student_id`, `course_id`, `teacher_id`, `marks_obtained`, `grade`, `full_marks`, `gpa`, `exam_type`, `academic_year`) VALUES
(5, 19, 5, NULL, 64.00, 'A', 70.00, 4.00, 'Unit Test 1', 2026);

-- --------------------------------------------------------

--
-- Table structure for table `teacher_courses`
--

CREATE TABLE `teacher_courses` (
  `assign_id` int(11) NOT NULL,
  `teacher_id` int(11) DEFAULT NULL,
  `course_id` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `teacher_courses`
--

INSERT INTO `teacher_courses` (`assign_id`, `teacher_id`, `course_id`) VALUES
(5, 20, 5);

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `user_id` int(11) NOT NULL,
  `roll_no` varchar(50) DEFAULT NULL,
  `contact_no` varchar(20) DEFAULT NULL,
  `gender` varchar(10) DEFAULT NULL,
  `address` text DEFAULT NULL,
  `profile_photo` varchar(255) DEFAULT NULL,
  `full_name` varchar(100) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password` varchar(255) NOT NULL,
  `role` enum('admin','teacher','student') NOT NULL,
  `dept_id` int(11) DEFAULT NULL,
  `semester` varchar(20) DEFAULT NULL,
  `date_of_birth` date DEFAULT NULL,
  `enroll_date` date DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`user_id`, `roll_no`, `contact_no`, `gender`, `address`, `profile_photo`, `full_name`, `email`, `password`, `role`, `dept_id`, `semester`, `date_of_birth`, `enroll_date`) VALUES
(1, NULL, '9769927110', 'male', 'Lalitpur', NULL, 'System Admin', 'admin@ncit.edu.np', '123456', 'admin', NULL, NULL, NULL, NULL),
(19, '241325', '983456789', 'Male', 'Jadibuti,Kathmandu', NULL, 'Prajjwal Babu Bastola', 'prajjwal@ncit.edu.np', '123456', 'student', 3, '3rd', '2005-05-10', '2026-01-28'),
(20, NULL, '9860606023', 'Male', 'Kathmandu,Nepal', NULL, 'Simanta Kasaju', 'simanta@ncit.edu.np', '123456', 'teacher', 3, NULL, NULL, NULL),
(21, '241306', '9769927110', 'Male', 'Lalitpur', NULL, 'Bigyan Sanjyal', 'bigyan@ncit.edu.np', '123456', 'student', 3, '3rd', '2004-11-02', '2026-02-03');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `attendance`
--
ALTER TABLE `attendance`
  ADD PRIMARY KEY (`attendance_id`),
  ADD KEY `course_id` (`course_id`),
  ADD KEY `student_id` (`student_id`);

--
-- Indexes for table `book_categories`
--
ALTER TABLE `book_categories`
  ADD PRIMARY KEY (`category_id`),
  ADD UNIQUE KEY `name` (`name`);

--
-- Indexes for table `borrows`
--
ALTER TABLE `borrows`
  ADD PRIMARY KEY (`borrow_id`),
  ADD KEY `book_id` (`book_id`),
  ADD KEY `student_id` (`student_id`);

--
-- Indexes for table `courses`
--
ALTER TABLE `courses`
  ADD PRIMARY KEY (`course_id`),
  ADD UNIQUE KEY `course_code` (`course_code`),
  ADD KEY `dept_id` (`dept_id`);

--
-- Indexes for table `departments`
--
ALTER TABLE `departments`
  ADD PRIMARY KEY (`dept_id`);

--
-- Indexes for table `exam_schedule`
--
ALTER TABLE `exam_schedule`
  ADD PRIMARY KEY (`exam_id`),
  ADD KEY `course_id` (`course_id`);

--
-- Indexes for table `fees`
--
ALTER TABLE `fees`
  ADD PRIMARY KEY (`fee_id`),
  ADD KEY `student_id` (`student_id`);

--
-- Indexes for table `library_books`
--
ALTER TABLE `library_books`
  ADD PRIMARY KEY (`book_id`),
  ADD UNIQUE KEY `isbn` (`isbn`),
  ADD KEY `category_id` (`category_id`);

--
-- Indexes for table `notices`
--
ALTER TABLE `notices`
  ADD PRIMARY KEY (`notice_id`);

--
-- Indexes for table `student_enrollments`
--
ALTER TABLE `student_enrollments`
  ADD PRIMARY KEY (`enrollment_id`),
  ADD KEY `student_id` (`student_id`),
  ADD KEY `course_id` (`course_id`);

--
-- Indexes for table `student_results`
--
ALTER TABLE `student_results`
  ADD PRIMARY KEY (`result_id`),
  ADD KEY `student_id` (`student_id`),
  ADD KEY `course_id` (`course_id`),
  ADD KEY `teacher_id` (`teacher_id`),
  ADD KEY `idx_student_results_year` (`academic_year`);

--
-- Indexes for table `teacher_courses`
--
ALTER TABLE `teacher_courses`
  ADD PRIMARY KEY (`assign_id`),
  ADD KEY `teacher_id` (`teacher_id`),
  ADD KEY `course_id` (`course_id`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`user_id`),
  ADD UNIQUE KEY `email` (`email`),
  ADD UNIQUE KEY `roll_no` (`roll_no`),
  ADD KEY `dept_id` (`dept_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `attendance`
--
ALTER TABLE `attendance`
  MODIFY `attendance_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `book_categories`
--
ALTER TABLE `book_categories`
  MODIFY `category_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `borrows`
--
ALTER TABLE `borrows`
  MODIFY `borrow_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- AUTO_INCREMENT for table `courses`
--
ALTER TABLE `courses`
  MODIFY `course_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT for table `departments`
--
ALTER TABLE `departments`
  MODIFY `dept_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `exam_schedule`
--
ALTER TABLE `exam_schedule`
  MODIFY `exam_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `fees`
--
ALTER TABLE `fees`
  MODIFY `fee_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT for table `library_books`
--
ALTER TABLE `library_books`
  MODIFY `book_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- AUTO_INCREMENT for table `notices`
--
ALTER TABLE `notices`
  MODIFY `notice_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `student_enrollments`
--
ALTER TABLE `student_enrollments`
  MODIFY `enrollment_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=8;

--
-- AUTO_INCREMENT for table `student_results`
--
ALTER TABLE `student_results`
  MODIFY `result_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT for table `teacher_courses`
--
ALTER TABLE `teacher_courses`
  MODIFY `assign_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `user_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=22;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `attendance`
--
ALTER TABLE `attendance`
  ADD CONSTRAINT `attendance_ibfk_1` FOREIGN KEY (`course_id`) REFERENCES `courses` (`course_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `attendance_ibfk_2` FOREIGN KEY (`student_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE;

--
-- Constraints for table `borrows`
--
ALTER TABLE `borrows`
  ADD CONSTRAINT `borrows_ibfk_1` FOREIGN KEY (`book_id`) REFERENCES `library_books` (`book_id`),
  ADD CONSTRAINT `borrows_ibfk_2` FOREIGN KEY (`student_id`) REFERENCES `users` (`user_id`);

--
-- Constraints for table `courses`
--
ALTER TABLE `courses`
  ADD CONSTRAINT `courses_ibfk_1` FOREIGN KEY (`dept_id`) REFERENCES `departments` (`dept_id`) ON DELETE CASCADE;

--
-- Constraints for table `exam_schedule`
--
ALTER TABLE `exam_schedule`
  ADD CONSTRAINT `exam_schedule_ibfk_1` FOREIGN KEY (`course_id`) REFERENCES `courses` (`course_id`) ON DELETE CASCADE;

--
-- Constraints for table `fees`
--
ALTER TABLE `fees`
  ADD CONSTRAINT `fees_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE;

--
-- Constraints for table `library_books`
--
ALTER TABLE `library_books`
  ADD CONSTRAINT `library_books_ibfk_1` FOREIGN KEY (`category_id`) REFERENCES `book_categories` (`category_id`);

--
-- Constraints for table `student_enrollments`
--
ALTER TABLE `student_enrollments`
  ADD CONSTRAINT `student_enrollments_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `student_enrollments_ibfk_2` FOREIGN KEY (`course_id`) REFERENCES `courses` (`course_id`) ON DELETE CASCADE;

--
-- Constraints for table `student_results`
--
ALTER TABLE `student_results`
  ADD CONSTRAINT `student_results_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `student_results_ibfk_2` FOREIGN KEY (`course_id`) REFERENCES `courses` (`course_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `student_results_ibfk_3` FOREIGN KEY (`teacher_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL;

--
-- Constraints for table `teacher_courses`
--
ALTER TABLE `teacher_courses`
  ADD CONSTRAINT `teacher_courses_ibfk_1` FOREIGN KEY (`teacher_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `teacher_courses_ibfk_2` FOREIGN KEY (`course_id`) REFERENCES `courses` (`course_id`) ON DELETE CASCADE;

--
-- Constraints for table `users`
--
ALTER TABLE `users`
  ADD CONSTRAINT `users_ibfk_1` FOREIGN KEY (`dept_id`) REFERENCES `departments` (`dept_id`) ON DELETE SET NULL;

-- --------------------------------------------------------
-- DOMAIN & CONSTRAINT HARDENING
-- --------------------------------------------------------

-- Normalize existing seed/sample values before stricter constraints
UPDATE `users`
SET
  `full_name` = TRIM(`full_name`),
  `email` = LOWER(TRIM(`email`));

UPDATE `users` SET `roll_no` = NULL WHERE `roll_no` IS NOT NULL AND TRIM(`roll_no`) = '';
UPDATE `users` SET `contact_no` = NULL WHERE `contact_no` IS NOT NULL AND TRIM(`contact_no`) = '';
UPDATE `users` SET `semester` = NULL WHERE `semester` IS NOT NULL AND TRIM(`semester`) = '';

UPDATE `users`
SET `gender` = CASE
  WHEN LOWER(TRIM(`gender`)) = 'male' THEN 'Male'
  WHEN LOWER(TRIM(`gender`)) = 'female' THEN 'Female'
  WHEN LOWER(TRIM(`gender`)) = 'other' THEN 'Other'
  ELSE NULL
END
WHERE `gender` IS NOT NULL;

ALTER TABLE `attendance`
  MODIFY `course_id` int(11) NOT NULL,
  MODIFY `student_id` int(11) NOT NULL,
  MODIFY `attendance_date` date NOT NULL,
  MODIFY `status` enum('Present','Absent') NOT NULL,
  ADD UNIQUE KEY `uq_attendance_course_student_day` (`course_id`,`student_id`,`attendance_date`),
  ADD CONSTRAINT `chk_attendance_ids` CHECK (`course_id` > 0 AND `student_id` > 0);

ALTER TABLE `book_categories`
  ADD CONSTRAINT `chk_book_categories_name`
  CHECK (TRIM(`name`) <> '' AND `name` REGEXP '^[A-Za-z][A-Za-z0-9 &/.-]*$');

ALTER TABLE `borrows`
  MODIFY `fine` decimal(10,2) NOT NULL DEFAULT 0.00,
  ADD CONSTRAINT `chk_borrows_ids` CHECK (`book_id` > 0 AND `student_id` > 0),
  ADD CONSTRAINT `chk_borrows_dates`
  CHECK (`due_date` >= `borrow_date` AND (`return_date` IS NULL OR `return_date` >= `borrow_date`)),
  ADD CONSTRAINT `chk_borrows_fine` CHECK (`fine` >= 0);

ALTER TABLE `courses`
  MODIFY `dept_id` int(11) NOT NULL,
  ADD UNIQUE KEY `uq_courses_dept_name` (`dept_id`,`course_name`),
  ADD CONSTRAINT `chk_courses_name`
  CHECK (TRIM(`course_name`) <> '' AND `course_name` REGEXP '^[A-Za-z0-9][A-Za-z0-9 &().,/+-]*$'),
  ADD CONSTRAINT `chk_courses_code`
  CHECK (`course_code` REGEXP '^[A-Z0-9][A-Z0-9-]{1,19}$');

ALTER TABLE `departments`
  ADD UNIQUE KEY `uq_departments_name` (`dept_name`),
  ADD CONSTRAINT `chk_departments_name`
  CHECK (TRIM(`dept_name`) <> '' AND `dept_name` REGEXP '^[A-Za-z][A-Za-z0-9 &/.-]*$'),
  ADD CONSTRAINT `chk_departments_hod`
  CHECK (`hod_name` IS NULL OR (TRIM(`hod_name`) <> '' AND `hod_name` REGEXP '^[A-Za-z][A-Za-z .''-]*$'));

ALTER TABLE `exam_schedule`
  MODIFY `course_id` int(11) NOT NULL,
  MODIFY `exam_date` date NOT NULL,
  MODIFY `start_time` time NOT NULL,
  MODIFY `room_no` varchar(50) NOT NULL,
  ADD UNIQUE KEY `uq_exam_schedule_slot` (`course_id`,`exam_date`,`start_time`),
  ADD CONSTRAINT `chk_exam_room`
  CHECK (TRIM(`room_no`) <> '' AND `room_no` REGEXP '^[A-Za-z0-9][A-Za-z0-9 .,#/-]*$');

ALTER TABLE `fees`
  MODIFY `student_id` int(11) NOT NULL,
  MODIFY `amount` decimal(10,2) NOT NULL,
  MODIFY `description` varchar(255) NOT NULL,
  MODIFY `status` enum('Paid','Pending') NOT NULL DEFAULT 'Pending',
  ADD CONSTRAINT `chk_fees_amount` CHECK (`amount` >= 0),
  ADD CONSTRAINT `chk_fees_description` CHECK (TRIM(`description`) <> '');

ALTER TABLE `library_books`
  MODIFY `category_id` int(11) NOT NULL,
  MODIFY `isbn` varchar(50) NOT NULL,
  MODIFY `copies_total` int(11) NOT NULL DEFAULT 1,
  ADD CONSTRAINT `chk_library_title` CHECK (TRIM(`title`) <> ''),
  ADD CONSTRAINT `chk_library_author`
  CHECK (TRIM(`author`) <> '' AND `author` REGEXP '^[A-Za-z][A-Za-z .,''-]*$'),
  ADD CONSTRAINT `chk_library_isbn` CHECK (`isbn` REGEXP '^[0-9Xx-]{7,20}$'),
  ADD CONSTRAINT `chk_library_copies` CHECK (`copies_total` >= 1);

ALTER TABLE `notices`
  MODIFY `title` varchar(200) NOT NULL,
  MODIFY `content` text NOT NULL,
  MODIFY `target_role` enum('all','student','teacher') NOT NULL DEFAULT 'all',
  MODIFY `date_posted` datetime NOT NULL DEFAULT current_timestamp(),
  ADD CONSTRAINT `chk_notices_title` CHECK (TRIM(`title`) <> ''),
  ADD CONSTRAINT `chk_notices_content` CHECK (TRIM(`content`) <> '');

ALTER TABLE `student_enrollments`
  MODIFY `student_id` int(11) NOT NULL,
  MODIFY `course_id` int(11) NOT NULL,
  MODIFY `date_enrolled` date NOT NULL,
  ADD UNIQUE KEY `uq_student_enrollment` (`student_id`,`course_id`),
  ADD CONSTRAINT `chk_student_enrollment_ids` CHECK (`student_id` > 0 AND `course_id` > 0);

ALTER TABLE `student_results`
  MODIFY `student_id` int(11) NOT NULL,
  MODIFY `course_id` int(11) NOT NULL,
  MODIFY `teacher_id` int(11) DEFAULT NULL,
  MODIFY `marks_obtained` decimal(6,2) NOT NULL,
  MODIFY `grade` varchar(5) NOT NULL,
  MODIFY `full_marks` decimal(6,2) NOT NULL DEFAULT 100.00,
  MODIFY `gpa` decimal(3,2) NOT NULL DEFAULT 0.00,
  MODIFY `exam_type` varchar(50) NOT NULL DEFAULT 'Final',
  MODIFY `academic_year` smallint(5) unsigned NOT NULL DEFAULT 2026,
  ADD UNIQUE KEY `uq_student_result_exam_year` (`student_id`,`course_id`,`exam_type`,`academic_year`),
  ADD CONSTRAINT `chk_results_marks`
  CHECK (`marks_obtained` >= 0 AND `full_marks` > 0 AND `marks_obtained` <= `full_marks`),
  ADD CONSTRAINT `chk_results_gpa` CHECK (`gpa` >= 0 AND `gpa` <= 4.00),
  ADD CONSTRAINT `chk_results_grade` CHECK (`grade` IN ('A','A-','B+','B','B-','C+','C','C-','D+','D','F')),
  ADD CONSTRAINT `chk_results_exam_type` CHECK (TRIM(`exam_type`) <> ''),
  ADD CONSTRAINT `chk_results_academic_year` CHECK (`academic_year` >= 2000 AND `academic_year` <= 2100);

ALTER TABLE `teacher_courses`
  MODIFY `teacher_id` int(11) NOT NULL,
  MODIFY `course_id` int(11) NOT NULL,
  ADD UNIQUE KEY `uq_teacher_course` (`teacher_id`,`course_id`),
  ADD CONSTRAINT `chk_teacher_course_ids` CHECK (`teacher_id` > 0 AND `course_id` > 0);

ALTER TABLE `users`
  MODIFY `roll_no` varchar(50) DEFAULT NULL,
  MODIFY `contact_no` varchar(20) DEFAULT NULL,
  MODIFY `gender` varchar(10) DEFAULT NULL,
  MODIFY `full_name` varchar(100) NOT NULL,
  MODIFY `email` varchar(100) NOT NULL,
  MODIFY `semester` varchar(20) DEFAULT NULL,
  MODIFY `date_of_birth` date DEFAULT NULL,
  ADD CONSTRAINT `chk_users_full_name`
  CHECK (TRIM(`full_name`) <> '' AND `full_name` REGEXP '^[A-Za-z][A-Za-z .''-]*$'),
  ADD CONSTRAINT `chk_users_email`
  CHECK (`email` REGEXP '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+[.][A-Za-z]{2,}$'),
  ADD CONSTRAINT `chk_users_password` CHECK (CHAR_LENGTH(`password`) >= 6),
  ADD CONSTRAINT `chk_users_roll_no`
  CHECK (`roll_no` IS NULL OR `roll_no` REGEXP '^[A-Za-z0-9-]{2,50}$'),
  ADD CONSTRAINT `chk_users_contact`
  CHECK (`contact_no` IS NULL OR `contact_no` REGEXP '^[0-9+ -]{7,20}$'),
  ADD CONSTRAINT `chk_users_gender`
  CHECK (`gender` IS NULL OR `gender` IN ('Male','Female','Other')),
  ADD CONSTRAINT `chk_users_semester`
  CHECK (`semester` IS NULL OR `semester` IN ('1st','2nd','3rd','4th','5th','6th','7th','8th')),
  ADD CONSTRAINT `chk_users_dob_range`
  CHECK (`date_of_birth` IS NULL OR (`date_of_birth` >= '1900-01-01' AND (`enroll_date` IS NULL OR `date_of_birth` <= `enroll_date`))),
  ADD CONSTRAINT `chk_users_student_required_fields`
  CHECK (
    `role` <> 'student'
    OR (`roll_no` IS NOT NULL AND `semester` IS NOT NULL AND `date_of_birth` IS NOT NULL AND `enroll_date` IS NOT NULL)
  );

-- --------------------------------------------------------
-- BCNF-ORIENTED DOMAIN NORMALIZATION
-- --------------------------------------------------------

ALTER TABLE `courses`
  ADD COLUMN IF NOT EXISTS `credit_hour` decimal(4,2) NOT NULL DEFAULT 3.00 AFTER `course_code`;

CREATE TABLE IF NOT EXISTS `teacher_assignments` (
  `assignment_id` int(11) NOT NULL AUTO_INCREMENT,
  `course_id` int(11) NOT NULL,
  `teacher_id` int(11) NOT NULL,
  `title` varchar(200) NOT NULL,
  `notice` text DEFAULT NULL,
  `description` text DEFAULT NULL,
  `due_date` date DEFAULT NULL,
  `due_time` time DEFAULT NULL,
  `attachment_path` varchar(255) DEFAULT NULL,
  `attachment_name` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`assignment_id`),
  KEY `idx_teacher_assignments_course` (`course_id`),
  KEY `idx_teacher_assignments_teacher` (`teacher_id`),
  CONSTRAINT `fk_teacher_assignments_course` FOREIGN KEY (`course_id`) REFERENCES `courses` (`course_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_teacher_assignments_teacher` FOREIGN KEY (`teacher_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS `assignment_submissions` (
  `submission_id` int(11) NOT NULL AUTO_INCREMENT,
  `assignment_id` int(11) NOT NULL,
  `student_id` int(11) NOT NULL,
  `status` enum('not_submitted','turned_in','submitted') NOT NULL DEFAULT 'not_submitted',
  `submission_path` varchar(255) DEFAULT NULL,
  `submission_name` varchar(255) DEFAULT NULL,
  `submitted_at` datetime DEFAULT NULL,
  `is_late` tinyint(1) NOT NULL DEFAULT 0,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`submission_id`),
  UNIQUE KEY `uq_assignment_student` (`assignment_id`,`student_id`),
  KEY `idx_assignment_submissions_student` (`student_id`),
  CONSTRAINT `fk_assignment_submissions_assignment` FOREIGN KEY (`assignment_id`) REFERENCES `teacher_assignments` (`assignment_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_assignment_submissions_student` FOREIGN KEY (`student_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS `assignment_comments` (
  `comment_id` int(11) NOT NULL AUTO_INCREMENT,
  `submission_id` int(11) NOT NULL,
  `sender_id` int(11) NOT NULL,
  `sender_role` enum('teacher','student') NOT NULL,
  `comment_text` text NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`comment_id`),
  KEY `idx_assignment_comments_submission` (`submission_id`),
  KEY `idx_assignment_comments_sender` (`sender_id`),
  CONSTRAINT `fk_assignment_comments_submission` FOREIGN KEY (`submission_id`) REFERENCES `assignment_submissions` (`submission_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_assignment_comments_sender` FOREIGN KEY (`sender_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS `password_reset_otps` (
  `otp_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `delivery_channel` varchar(20) NOT NULL,
  `destination` varchar(150) NOT NULL,
  `otp_hash` varchar(255) NOT NULL,
  `expires_at` datetime NOT NULL,
  `attempts` int(11) NOT NULL DEFAULT 0,
  `verified_at` datetime DEFAULT NULL,
  `used_at` datetime DEFAULT NULL,
  `sent_at` datetime NOT NULL DEFAULT current_timestamp(),
  `request_ip` varchar(45) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`otp_id`),
  KEY `idx_password_reset_user` (`user_id`),
  KEY `idx_password_reset_destination` (`destination`),
  KEY `idx_password_reset_ip_sent` (`request_ip`,`sent_at`),
  KEY `idx_password_reset_user_sent` (`user_id`,`sent_at`),
  CONSTRAINT `fk_password_reset_otps_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS `ref_user_roles` (
  `role_code` varchar(20) NOT NULL,
  PRIMARY KEY (`role_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS `ref_genders` (
  `gender_code` varchar(10) NOT NULL,
  PRIMARY KEY (`gender_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS `ref_semesters` (
  `semester_code` varchar(20) NOT NULL,
  PRIMARY KEY (`semester_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS `ref_notice_targets` (
  `target_code` varchar(20) NOT NULL,
  PRIMARY KEY (`target_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS `ref_fee_statuses` (
  `status_code` varchar(20) NOT NULL,
  PRIMARY KEY (`status_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS `ref_attendance_statuses` (
  `status_code` varchar(20) NOT NULL,
  PRIMARY KEY (`status_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS `ref_exam_types` (
  `exam_type_code` varchar(50) NOT NULL,
  PRIMARY KEY (`exam_type_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT IGNORE INTO `ref_user_roles` (`role_code`) VALUES
('admin'), ('teacher'), ('student');

INSERT IGNORE INTO `ref_genders` (`gender_code`) VALUES
('Male'), ('Female'), ('Other');

INSERT IGNORE INTO `ref_semesters` (`semester_code`) VALUES
('1st'), ('2nd'), ('3rd'), ('4th'), ('5th'), ('6th'), ('7th'), ('8th');

INSERT IGNORE INTO `ref_notice_targets` (`target_code`) VALUES
('all'), ('student'), ('teacher');

INSERT IGNORE INTO `ref_fee_statuses` (`status_code`) VALUES
('Paid'), ('Pending');

INSERT IGNORE INTO `ref_attendance_statuses` (`status_code`) VALUES
('Present'), ('Absent');

INSERT IGNORE INTO `ref_exam_types` (`exam_type_code`) VALUES
('Unit Test 1'), ('Unit Test 2'), ('Mid Term'), ('Pre Board'), ('Final'), ('Assignment');

INSERT IGNORE INTO `ref_exam_types` (`exam_type_code`)
SELECT DISTINCT `exam_type`
FROM `student_results`
WHERE `exam_type` IS NOT NULL AND TRIM(`exam_type`) <> '';

ALTER TABLE `users`
  MODIFY `role` varchar(20) NOT NULL,
  MODIFY `gender` varchar(10) DEFAULT NULL,
  MODIFY `semester` varchar(20) DEFAULT NULL;

ALTER TABLE `notices`
  MODIFY `target_role` varchar(20) NOT NULL DEFAULT 'all';

ALTER TABLE `fees`
  MODIFY `status` varchar(20) NOT NULL DEFAULT 'Pending';

ALTER TABLE `attendance`
  MODIFY `status` varchar(20) NOT NULL;

ALTER TABLE `student_results`
  MODIFY `exam_type` varchar(50) NOT NULL DEFAULT 'Final';

ALTER TABLE `users`
  ADD CONSTRAINT `fk_users_role_domain` FOREIGN KEY (`role`) REFERENCES `ref_user_roles` (`role_code`) ON UPDATE CASCADE ON DELETE RESTRICT,
  ADD CONSTRAINT `fk_users_gender_domain` FOREIGN KEY (`gender`) REFERENCES `ref_genders` (`gender_code`) ON UPDATE CASCADE ON DELETE SET NULL,
  ADD CONSTRAINT `fk_users_semester_domain` FOREIGN KEY (`semester`) REFERENCES `ref_semesters` (`semester_code`) ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE `notices`
  ADD CONSTRAINT `fk_notices_target_domain` FOREIGN KEY (`target_role`) REFERENCES `ref_notice_targets` (`target_code`) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE `fees`
  ADD CONSTRAINT `fk_fees_status_domain` FOREIGN KEY (`status`) REFERENCES `ref_fee_statuses` (`status_code`) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE `attendance`
  ADD CONSTRAINT `fk_attendance_status_domain` FOREIGN KEY (`status`) REFERENCES `ref_attendance_statuses` (`status_code`) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE `student_results`
  ADD CONSTRAINT `fk_results_exam_type_domain` FOREIGN KEY (`exam_type`) REFERENCES `ref_exam_types` (`exam_type_code`) ON UPDATE CASCADE ON DELETE RESTRICT;

DROP TRIGGER IF EXISTS `trg_student_results_before_insert`;
DROP TRIGGER IF EXISTS `trg_student_results_before_update`;

DELIMITER $$
CREATE TRIGGER `trg_student_results_before_insert`
BEFORE INSERT ON `student_results`
FOR EACH ROW
BEGIN
  DECLARE pct DECIMAL(8,4);

  IF NEW.`full_marks` IS NULL OR NEW.`full_marks` <= 0 THEN
    SET NEW.`full_marks` = 100.00;
  END IF;
  IF NEW.`marks_obtained` IS NULL OR NEW.`marks_obtained` < 0 THEN
    SET NEW.`marks_obtained` = 0.00;
  END IF;
  IF NEW.`marks_obtained` > NEW.`full_marks` THEN
    SET NEW.`marks_obtained` = NEW.`full_marks`;
  END IF;

  SET pct = (NEW.`marks_obtained` / NEW.`full_marks`) * 100;

  IF pct >= 90 THEN SET NEW.`grade` = 'A'; SET NEW.`gpa` = 4.0;
  ELSEIF pct >= 85 THEN SET NEW.`grade` = 'A-'; SET NEW.`gpa` = 3.7;
  ELSEIF pct >= 80 THEN SET NEW.`grade` = 'B+'; SET NEW.`gpa` = 3.3;
  ELSEIF pct >= 75 THEN SET NEW.`grade` = 'B'; SET NEW.`gpa` = 3.0;
  ELSEIF pct >= 70 THEN SET NEW.`grade` = 'B-'; SET NEW.`gpa` = 2.7;
  ELSEIF pct >= 65 THEN SET NEW.`grade` = 'C+'; SET NEW.`gpa` = 2.3;
  ELSEIF pct >= 60 THEN SET NEW.`grade` = 'C'; SET NEW.`gpa` = 2.0;
  ELSEIF pct >= 55 THEN SET NEW.`grade` = 'C-'; SET NEW.`gpa` = 1.7;
  ELSEIF pct >= 50 THEN SET NEW.`grade` = 'D+'; SET NEW.`gpa` = 1.3;
  ELSEIF pct >= 45 THEN SET NEW.`grade` = 'D'; SET NEW.`gpa` = 1.0;
  ELSE SET NEW.`grade` = 'F'; SET NEW.`gpa` = 0.0;
  END IF;
END$$

CREATE TRIGGER `trg_student_results_before_update`
BEFORE UPDATE ON `student_results`
FOR EACH ROW
BEGIN
  DECLARE pct DECIMAL(8,4);

  IF NEW.`full_marks` IS NULL OR NEW.`full_marks` <= 0 THEN
    SET NEW.`full_marks` = 100.00;
  END IF;
  IF NEW.`marks_obtained` IS NULL OR NEW.`marks_obtained` < 0 THEN
    SET NEW.`marks_obtained` = 0.00;
  END IF;
  IF NEW.`marks_obtained` > NEW.`full_marks` THEN
    SET NEW.`marks_obtained` = NEW.`full_marks`;
  END IF;

  SET pct = (NEW.`marks_obtained` / NEW.`full_marks`) * 100;

  IF pct >= 90 THEN SET NEW.`grade` = 'A'; SET NEW.`gpa` = 4.0;
  ELSEIF pct >= 85 THEN SET NEW.`grade` = 'A-'; SET NEW.`gpa` = 3.7;
  ELSEIF pct >= 80 THEN SET NEW.`grade` = 'B+'; SET NEW.`gpa` = 3.3;
  ELSEIF pct >= 75 THEN SET NEW.`grade` = 'B'; SET NEW.`gpa` = 3.0;
  ELSEIF pct >= 70 THEN SET NEW.`grade` = 'B-'; SET NEW.`gpa` = 2.7;
  ELSEIF pct >= 65 THEN SET NEW.`grade` = 'C+'; SET NEW.`gpa` = 2.3;
  ELSEIF pct >= 60 THEN SET NEW.`grade` = 'C'; SET NEW.`gpa` = 2.0;
  ELSEIF pct >= 55 THEN SET NEW.`grade` = 'C-'; SET NEW.`gpa` = 1.7;
  ELSEIF pct >= 50 THEN SET NEW.`grade` = 'D+'; SET NEW.`gpa` = 1.3;
  ELSEIF pct >= 45 THEN SET NEW.`grade` = 'D'; SET NEW.`gpa` = 1.0;
  ELSE SET NEW.`grade` = 'F'; SET NEW.`gpa` = 0.0;
  END IF;
END$$
DELIMITER ;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
