# Visa Consultancy Data System

A production-ready data system for visa consultancies to manage students, universities, and the matching/application process.

## Guiding Principle
> Automate only what is cheaper to automate than to do manually.

## Features
- **Structured Data Entry**: Comprehensive models for Students and Universities.
- **Matching Engine**: SQL-based matching with transparent preference scoring.
- **GPA Normalization**: Automatic conversion of various GPA scales (India, UK, Germany, etc.) to a 4.0 scale.
- **Document Management**: Secure upload and metadata tracking for student documents.
- **PDF Generation**: Auto-generated student profile PDFs for offline use.
- **Audit Trails**: Full history tracking for all major models using `django-simple-history`.
- **Security**: Row-level access control and environment-based configuration.

## Tech Stack
- **Backend**: Django (Monolith)
- **Database**: PostgreSQL
- **File Storage**: Local filesystem + Nginx X-Accel-Redirect
- **PDF Generation**: fpdf2
- **Backups**: BorgBackup → Storj

## Setup Instructions

### Prerequisites
- Python 3.12+
- PostgreSQL (or SQLite for development)

### Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variables:
   ```bash
   export DJANGO_SECRET_KEY='your-secret-key'
   export DJANGO_DEBUG='False'
   export DJANGO_ALLOWED_HOSTS='your-domain.com'
   # Database variables
   export DATABASE_URL='postgres://user:password@localhost:5432/db_name'
   ```
4. Run migrations:
   ```bash
   python manage.py migrate
   ```
5. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```
6. Start the server:
   ```bash
   gunicorn visa_consultancy.wsgi:application
   ```

## Infrastructure
- **Nginx**: Configuration provided in `nginx.conf`. Uses `X-Accel-Redirect` for secure file serving.
- **Backups**: `backup.sh` provides a template for twice-daily backups to Storj using BorgBackup.

## Compliance
- **Consent Tracking**: Granular consent fields with timestamp and IP tracking.
- **Data Retention**: Logic for 2-year retention policies as per GDPR/PDPL.
- **Access Control**: Row-level permissions ensuring consultants only see their assigned students.
