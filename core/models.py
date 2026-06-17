from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.postgres.indexes import GinIndex
from simple_history.models import HistoricalRecords
import json

MONTH_CHOICES = [
    ("January", "January"), ("February", "February"), ("March", "March"),
    ("April", "April"), ("May", "May"), ("June", "June"),
    ("July", "July"), ("August", "August"), ("September", "September"),
    ("October", "October"), ("November", "November"), ("December", "December"),
]


class Student(models.Model):
    # Identity
    full_name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    nationality = models.CharField(max_length=100)

    # Academics
    highest_qualification = models.CharField(max_length=100)
    institution_name = models.CharField(max_length=200)
    graduation_year = models.PositiveSmallIntegerField()

    # GPA with normalization
    gpa = models.DecimalField(max_digits=4, decimal_places=2)
    gpa_scale = models.DecimalField(max_digits=3, decimal_places=1, default=4.0)
    normalized_gpa_4 = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)

    backlogs = models.PositiveSmallIntegerField(default=0)
    gap_years = models.PositiveSmallIntegerField(default=0)

    # Language (manual entry from scorecard)
    ielts_overall = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    ielts_listening = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    ielts_reading = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    ielts_writing = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    ielts_speaking = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    ielts_trf_number = models.CharField(max_length=20, blank=True)
    ielts_test_date = models.DateField(null=True, blank=True)

    # Financial
    available_funds_usd = models.PositiveIntegerField(null=True, blank=True)
    funds_held_days = models.PositiveSmallIntegerField(null=True, blank=True)

    # Preferences (structured, no string parsing)
    preferred_countries = models.JSONField(default=list)
    preferred_intake_month = models.CharField(max_length=20, choices=MONTH_CHOICES)
    preferred_intake_year = models.PositiveSmallIntegerField()

    max_budget_usd = models.PositiveIntegerField(null=True, blank=True)
    scholarship_priority = models.PositiveSmallIntegerField(default=3)
    ranking_priority = models.PositiveSmallIntegerField(default=3)

    # Pipeline
    STAGE_CHOICES = [
        ("lead", "New Lead"),
        ("docs_pending", "Documents Pending"),
        ("profile_ready", "Profile Ready"),
        ("shortlisted", "University Shortlisted"),
        ("applied", "Applications Submitted"),
        ("offer_received", "Offer Received"),
        ("visa_applied", "Visa Applied"),
        ("visa_granted", "Visa Granted"),
        ("visa_refused", "Visa Refused"),
    ]
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default="lead")

    # Consent tracking (GDPR/PDPL)
    consent_storage = models.BooleanField(default=False)
    consent_matching = models.BooleanField(default=False)
    consent_communication = models.BooleanField(default=False)
    consent_documents = models.BooleanField(default=False)
    consent_timestamp = models.DateTimeField(null=True, blank=True)
    consent_ip = models.GenericIPAddressField(null=True, blank=True)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    assigned_consultant = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    history = HistoricalRecords()

    class Meta:
        indexes = [
            models.Index(fields=["stage", "assigned_consultant"]),
            models.Index(fields=["preferred_intake_month", "preferred_intake_year"]),
            models.Index(fields=["nationality"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.nationality})"

    def clean(self):
        # Sanity checks — data quality guards, not business rules
        if self.ielts_overall and self.ielts_overall < 4.0:
            raise ValidationError("IELTS overall score seems unusually low. Please verify.")
        if self.ielts_overall and self.ielts_overall > 9.0:
            raise ValidationError("IELTS overall cannot exceed 9.0.")
        if self.gpa and self.gpa_scale and self.gpa > self.gpa_scale:
            raise ValidationError("GPA cannot exceed the scale maximum.")
        if self.funds_held_days and self.funds_held_days > 999:
            raise ValidationError("Funds held days seems incorrect. Please verify.")

    def save(self, *args, **kwargs):
        self.clean()
        # Auto-normalize GPA
        from .logic import normalize_gpa
        if self.normalized_gpa_4 is None:
            self.normalized_gpa_4 = normalize_gpa(self)
        super().save(*args, **kwargs)

    @property
    def preferred_intake_display(self):
        return f"{self.preferred_intake_month} {self.preferred_intake_year}"


class University(models.Model):
    name = models.CharField(max_length=200)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    website = models.URLField()

    program_name = models.CharField(max_length=200)
    degree_level = models.CharField(max_length=50)
    duration_months = models.PositiveSmallIntegerField()
    tuition_usd = models.PositiveIntegerField()
    intake_months = models.JSONField(default=list)

    min_ielts = models.DecimalField(max_digits=2, decimal_places=1, default=6.0)
    min_gpa_4 = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    scholarship_available = models.BooleanField(default=False)
    accepts_backlogs = models.BooleanField(default=True)
    max_gap_years = models.PositiveSmallIntegerField(default=5)
    requires_gre = models.BooleanField(default=False)
    requires_work_exp = models.BooleanField(default=False)
    work_exp_months = models.PositiveSmallIntegerField(default=0)

    min_funds_usd = models.PositiveIntegerField()
    funds_held_days_required = models.PositiveSmallIntegerField(default=28)

    ranking_qs = models.PositiveIntegerField(null=True, blank=True)
    accreditation = models.CharField(max_length=200, blank=True)
    last_verified_date = models.DateField()
    data_source = models.CharField(max_length=50, default="manual")

    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name_plural = "Universities"
        indexes = [
            models.Index(fields=["country", "is_active"]),
            models.Index(fields=["min_ielts", "tuition_usd"]),
            models.Index(fields=["degree_level"]),
            GinIndex(fields=["intake_months"]),
        ]

    def __str__(self):
        return f"{self.name} — {self.program_name}"

    @property
    def data_freshness(self):
        from django.utils import timezone
        age = (timezone.now().date() - self.last_verified_date).days
        if age > 90:
            return "stale", age
        return "fresh", age


class MatchResult(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="matches")
    university = models.ForeignKey(University, on_delete=models.CASCADE)

    is_eligible = models.BooleanField()
    ineligible_reasons = models.JSONField(default=list)
    preference_score = models.PositiveSmallIntegerField(default=0)
    score_breakdown = models.JSONField(default=dict)

    # Consultant decisions — PRESERVED across regenerations
    consultant_shortlisted = models.BooleanField(null=True, blank=True)
    consultant_rejected = models.BooleanField(null=True, blank=True)
    consultant_notes = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)  # Soft-delete for stale matches
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        unique_together = ["student", "university"]
        indexes = [
            models.Index(fields=["student", "is_active", "preference_score"]),
        ]

    def __str__(self):
        return f"{self.student.full_name} <> {self.university.name}: {self.preference_score}"


def document_path(instance, filename):
    """Generate upload path for student documents."""
    student_id = instance.student_id or getattr(instance.student, "id", "unknown")
    return f"uploads/{student_id}/{instance.doc_type}/{filename}"


class Document(models.Model):
    DOC_TYPES = [
        ("passport", "Passport"),
        ("transcript", "Academic Transcript"),
        ("ielts", "IELTS Scorecard"),
        ("bank_statement", "Bank Statement"),
        ("sop", "Statement of Purpose"),
        ("lor", "Letter of Recommendation"),
        ("resume", "Resume/CV"),
        ("offer_letter", "University Offer Letter"),
        ("visa_doc", "Visa Document"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=20, choices=DOC_TYPES)
    file = models.FileField(upload_to=document_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Honest review workflow — consultant decides, system tracks
    REVIEW_CHOICES = [
        ("pending", "Pending Review"),
        ("verified", "Verified Authentic"),
        ("suspicious", "Suspicious — Request Original"),
        ("rejected", "Rejected"),
    ]
    review_status = models.CharField(max_length=20, choices=REVIEW_CHOICES, default="pending")
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # Basic metadata (informational only, not security)
    file_size_kb = models.PositiveIntegerField(null=True, blank=True)
    file_extension = models.CharField(max_length=10, blank=True)

    history = HistoricalRecords()

    class Meta:
        indexes = [
            models.Index(fields=["student", "doc_type", "review_status"]),
        ]

    def __str__(self):
        return f"{self.student.full_name} — {self.get_doc_type_display()}"

    def save(self, *args, **kwargs):
        # Auto-populate file metadata
        if self.file:
            self.file_size_kb = self.file.size // 1024
            self.file_extension = self.file.name.split(".")[-1].lower() if "." in self.file.name else ""
        super().save(*args, **kwargs)
