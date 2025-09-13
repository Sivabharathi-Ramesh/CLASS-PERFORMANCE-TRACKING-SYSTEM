# CLASS-PERFORMANCE-TRACKING-SYSTEM


A comprehensive web application built with Flask to manage student attendance and homework for a college course. This system provides separate modules with distinct themes and functionalities for both teachers and students.

## ✨ Features

### Attendance Module (Green Theme)
- **Store Attendance**: Mark daily attendance for each student (Present, Absent Informed, Absent Uninformed).
- **View Records**: Filter and view attendance records for any specific day, month, or year.
- **Individual Reports**: Generate detailed attendance reports for a single student, including total days present and attendance percentage.

### Homework Module (Yellow Theme)
- **Manage Assignments**: A teacher/admin portal to create, edit, and delete homework assignments with due dates and descriptions.
- **Student Status Tracking**: A student-facing page where each student can view assignments and mark them as 'Completed'.
- **Live CodeWars Progress**: A dedicated page that uses the official CodeWars API to fetch and display the real-time progress (honor, rank, completed kata) of every student in the class.

### General
- **Modular Design**: Separate, themeable sections for different functionalities.
- **Responsive Layout**: The user interface is designed to work on both desktop and mobile devices.
- **Ready for Deployment**: Configured for easy deployment on cloud platforms like Render.

## 🛠️ Technologies Used

- **Backend**: Python, Flask
- **Frontend**: HTML, CSS, JavaScript
- **Database**: SQLite
- **API Integration**: CodeWars API (`requests`)
- **Deployment**: Gunicorn, Render

## 🚀 Setup and Installation

To run this project on your local machine, follow these steps:

**1. Prerequisites:**
   - Git
   - Python 3.x

**2. Clone the Repository:**
   ```bash
   git clone <your-repository-url>
   cd student-attendance-system
