# SchoolFix — Student Voice Portal

A school reporting and communication platform that allows students to report problems, attach evidence, track reports, and communicate with school administrators.

SchoolFix is designed to make school issue reporting more organised, transparent, and easier to manage.

---

## ✨ Features

### 👨‍🎓 Student Features

- Student registration and login
- Secure student accounts
- Submit school issue reports
- Add descriptions and locations to reports
- Upload photo evidence
- View personal reports
- Track report status
- Continue conversations on reports
- Change account password
- Access helpful student websites

### 🛡️ Admin Features

- Admin dashboard
- View and manage reports
- Respond to student reports
- Update report status
- Refer reports
- Take back referred reports
- Mark inappropriate/unreasonable reports
- Delete reports
- View analytics
- Manage student accounts
- Change user roles
- Reset user passwords
- Review administrator applications

### 👑 Main Admin Features

Main Admins have additional management and security controls.

- Full user management
- Admin management
- Database management panel
- Security dashboard
- Security logs
- Admin application approval/rejection
- Role management
- Password reset controls
- Report management
- Main administrator access controls

---

## 🎨 User Interface

SchoolFix uses a clean school-focused interface with:

- Blue and white visual design
- Responsive layout
- Student-friendly navigation
- Animated UI elements
- School branding
- Custom resource cards
- Dashboard cards
- Responsive mobile layout
- SchoolFix demonstration video

The project also includes a school background/logo and custom CSS animations.

---

## 🌐 Helpful Student Websites

SchoolFix provides quick access to useful student resources:

### NCERT Helper

https://ncerthelper.ai.studio/

NCERT study support and learning resources.

### SST Padho

https://sstpadho.netlify.app/

Social Studies learning resources.

### FocusGrid

https://focusgrid-for-students.onrender.com/

Student productivity and focus tools.

### SchoolFix

https://vaibhave-29.github.io/SchoolFix/

Additional student school tools.

---

## 🏗️ Technology Stack

### Backend

- Python
- Flask
- Gunicorn

### Database

- Supabase
- PostgreSQL

### Frontend

- HTML
- CSS
- Jinja2 templates
- JavaScript

### Deployment

- Render
- GitHub

---

## 📁 Project Structure

```text
Voice4Students/
│
├── app.py
├── database.py
├── schema.sql
├── render.yaml
├── requirements.txt
├── .gitignore
│
├── static/
│   ├── bg_image.png
│   ├── school-bg.png
│   │
│   ├── style.css
│   │
│   └── videos/
│       └── schoolfix.mp4
│
└── templates/
    ├── admin_applications.html
    ├── analytics.html
    ├── apply_admin.html
    ├── base.html
    ├── change_password.html
    ├── dashboard.html
    ├── database.html
    ├── error.html
    ├── home.html
    ├── login.html
    ├── register.html
    ├── report_detail.html
    ├── reports.html
    ├── security.html
    ├── submit_report.html
    └── users.html
