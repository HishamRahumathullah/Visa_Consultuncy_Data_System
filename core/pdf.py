from fpdf import FPDF
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import Student
import fpdf


# Get fpdf2's built-in font directory
FONT_DIR = fpdf.FPDF_FONT_DIR


class StudentProfilePDF(FPDF):
    def header(self):
        self.set_font("DejaVu", "B", 15)
        self.cell(0, 10, "Student Profile - Visa Consultancy", 0, 1, "C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")


@login_required
def generate_student_pdf(request, student_id):
    student = get_object_or_404(Student, id=student_id)

    # Permission check: consultant sees own students, manager/admin sees all
    if not request.user.groups.filter(name__in=["manager", "admin"]).exists():
        if student.assigned_consultant != request.user:
            raise PermissionDenied(
                "You can only access profiles for your assigned students."
            )

    pdf = StudentProfilePDF()

    # Add Unicode-supporting fonts from fpdf2's built-in directory
    pdf.add_font("DejaVu", "", f"{FONT_DIR}/DejaVuSans.ttf", uni=True)
    pdf.add_font("DejaVu", "B", f"{FONT_DIR}/DejaVuSans-Bold.ttf", uni=True)
    pdf.add_font("DejaVu", "I", f"{FONT_DIR}/DejaVuSans-Oblique.ttf", uni=True)

    pdf.add_page()
    pdf.set_font("DejaVu", "", 12)

    data = [
        ("Full Name", student.full_name),
        ("Email", student.email),
        ("Phone", student.phone),
        ("Nationality", student.nationality),
        ("Qualification", student.highest_qualification),
        ("Institution", student.institution_name),
        (
            "GPA",
            f"{student.gpa} / {student.gpa_scale} (Normalized: {student.normalized_gpa_4})",
        ),
        (
            "IELTS Overall",
            str(student.ielts_overall) if student.ielts_overall else "N/A",
        ),
        ("Preferred Intake", student.preferred_intake_display),
        ("Stage", student.get_stage_display()),
        (
            "Assigned Consultant",
            str(student.assigned_consultant)
            if student.assigned_consultant
            else "Unassigned",
        ),
    ]

    for label, value in data:
        pdf.set_font("DejaVu", "B", 12)
        pdf.cell(50, 10, f"{label}:", 0, 0)
        pdf.set_font("DejaVu", "", 12)
        pdf.cell(0, 10, str(value), 0, 1)

    response = HttpResponse(pdf.output(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="student_{student.id}.pdf"'
    return response
