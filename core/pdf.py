from fpdf import FPDF
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import Student

class StudentProfilePDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Student Profile - Visa Consultancy', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

@login_required
def generate_student_pdf(request, student_id):
    student = get_object_or_404(Student, id=student_id)

    # Permission check: consultant sees own students, manager/admin sees all
    if not request.user.groups.filter(name__in=['manager', 'admin']).exists():
        if student.assigned_consultant != request.user:
            raise PermissionDenied("You can only access profiles for your assigned students.")

    pdf = StudentProfilePDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)

    data = [
        ('Full Name', student.full_name),
        ('Email', student.email),
        ('Phone', student.phone),
        ('Nationality', student.nationality),
        ('Qualification', student.highest_qualification),
        ('Institution', student.institution_name),
        ('GPA', f"{student.gpa} / {student.gpa_scale} (Normalized: {student.normalized_gpa_4})"),
        ('IELTS Overall', str(student.ielts_overall)),
        ('Preferred Intake', student.preferred_intake_display),
        ('Stage', student.get_stage_display()),
    ]

    for label, value in data:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(50, 10, f"{label}:", 0, 0)
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, str(value), 0, 1)

    response = HttpResponse(pdf.output(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="student_{student.id}.pdf"'
    return response
