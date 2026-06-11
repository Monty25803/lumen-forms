# Neon's Form

A lightweight Google Forms–like application built with Django. Create forms, collect responses, and view results with a neon-themed UI.

## Features

- **Create forms** via Django admin with multiple question types:
  - Short text
  - Long text (paragraph)
  - Single choice (radio)
  - Multiple choice (checkbox)
  - Dropdown
- **Fill out forms** with a clean, neon-styled interface
- **View responses** in a staff-only table view
- **No authentication required** for form submission (ideal for surveys and feedback)

## Requirements

- Python 3.10+ (3.12+ recommended)
- Django 6.x

## Setup

1. Create a virtual environment (recommended):
   ```bash
   py -3 -m venv venv
   venv\Scripts\activate   # Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run migrations:
   ```bash
   py -3 manage.py migrate
   ```

4. Create a superuser for the admin:
   ```bash
   py -3 manage.py createsuperuser
   ```

5. Start the development server:
   ```bash
   py -3 manage.py runserver
   ```

6. Open http://127.0.0.1:8000/ in your browser.

## Usage

1. Go to http://127.0.0.1:8000/admin/ and log in.
2. Create a **Form** with a title and optional description.
3. Add **Questions** to the form (with **Options** for radio/checkbox/dropdown types).
4. Visit the home page to see your forms and share links for others to fill out.
5. Log in as a staff user to use **View responses** and see submitted answers.

## Project Structure

```
Neon_Form/
├── neon_form/          # Project settings
├── forms_app/          # Main forms application
├── templates/          # HTML templates
├── static/css/         # Neon-themed styles
├── manage.py
└── requirements.txt
```
# Neon_Form
