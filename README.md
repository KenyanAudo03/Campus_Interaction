# Kenyan Universities Interaction Platform

## 🎯 Overview
A comprehensive platform connecting Kenyan university students through live messaging, forums, events, and resource sharing.

## 🛠️ Tech Stack
- Frontend: Django Templating
- Backend: Django
- Database: SQLite
- API: REST

## 🚀 Quick Setup

1. Clone & setup virtual environment

```bash
git clone https://github.com/KenyanAudo03/Campus_Interaction.git
cd Campus_Interaction
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

2. Install Requirements

```bash
pip install -r requirements.txt
```

3. Initialize Database

```bash
python manage.py makemigrations
python manage.py makemigrations profiles
python manage.py migrate
mkdir static staticfiles media
mkdir media/profile_pics
cp static/images/default-avatar.png media/profile_pics/default.png
```

4. Start Server

```bash
python manage.py runserver
```

