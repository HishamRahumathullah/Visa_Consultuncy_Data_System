from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.postgres.indexes import GinIndex
from simple_history.models import HistoricalRecords

MONTH_CHOICES = [
    ("January", "January"),
    ("February", "February"),
    ("March", "March"),
    ("April", "April"),
    ("May", "May"),
    ("June", "June"),
    ("July", "July"),
    ("August", "August"),
    ("September", "September"),
    ("October", "October"),
    ("November", "November"),
    ("December", "December"),
]


class Country(models.Model):
    """Master list of countries for selection across the system."""

    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(
        max_length=3, blank=True, help_text="ISO 3166-1 alpha-3 code"
    )
    is_active = models.BooleanField(default=True)

    # FIX: Removed HistoricalRecords from Country to avoid migration chain breakage.
    # Country is a reference table; changes are rare and can be tracked via
    # admin LogEntry if needed. This prevents the HistoricalCountry/HistoricalStudent
    # circular migration dependency issue.

    class Meta:
        verbose_name_plural = "Countries"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Student(models.Model):
    full_name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    nationality = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students_nationality",
        help_text="Student's nationality",
    )

    highest_qualification = models.CharField(max_length=100)
    institution_name = models.CharField(max_length=200)
    graduation_year = models.PositiveSmallIntegerField()

    gpa = models.DecimalField(max_digits=4, decimal_places=2)
    gpa_scale = models.DecimalField(max_digits=3, decimal_places=1, default=4.0)
    normalized_gpa_4 = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True
    )

    backlogs = models.PositiveSmallIntegerField(default=0)
    gap_years = models.PositiveSmallIntegerField(default=0)

    # FIX: max_digits=3 for IELTS to safely handle edge cases
    ielts_overall = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True
    )
    ielts_listening = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True
    )
    ielts_reading = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True
    )
    ielts_writing = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True
    )
    ielts_speaking = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True
    )
    ielts_trf_number = models.CharField(max_length=20, blank=True)
    ielts_test_date = models.DateField(null=True, blank=True)

    available_funds_usd = models.PositiveIntegerField(null=True, blank=True)
    funds_held_days = models.PositiveSmallIntegerField(null=True, blank=True)

    preferred_countries = models.ManyToManyField(
        Country,
        related_name="students_preferred",
        blank=True,
        help_text="Select countries where the student wants to study",
    )

    _preferred_countries_json = models.JSONField(
        default=list,
        blank=True,
        editable=False,
        help_text="Internal: JSON backup of preferred countries",
    )

    preferred_intake_month = models.CharField(max_length=20, choices=MONTH_CHOICES)
    preferred_intake_year = models.PositiveSmallIntegerField()

    max_budget_usd = models.PositiveIntegerField(null=True, blank=True)
    scholarship_priority = models.PositiveSmallIntegerField(default=3)
    ranking_priority = models.PositiveSmallIntegerField(default=3)

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

    consent_storage = models.BooleanField(default=False)
    consent_matching = models.BooleanField(default=False)
    consent_communication = models.BooleanField(default=False)
    consent_documents = models.BooleanField(default=False)
    consent_timestamp = models.DateTimeField(null=True, blank=True)
    consent_ip = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    assigned_consultant = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    # FIX: Track ManyToManyField changes in history using m2m_fields
    history = HistoricalRecords(m2m_fields=[preferred_countries])

    class Meta:
        indexes = [
            models.Index(fields=["stage", "assigned_consultant"]),
            models.Index(fields=["preferred_intake_month", "preferred_intake_year"]),
            models.Index(fields=["nationality"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.nationality})"

    def clean(self):
        if self.ielts_overall and self.ielts_overall < 4.0:
            raise ValidationError(
                "IELTS overall score seems unusually low. Please verify."
            )
        if self.ielts_overall and self.ielts_overall > 9.0:
            raise ValidationError("IELTS overall cannot exceed 9.0.")
        if self.gpa and self.gpa_scale and self.gpa > self.gpa_scale:
            raise ValidationError("GPA cannot exceed the scale maximum.")
        if self.funds_held_days and self.funds_held_days > 999:
            raise ValidationError("Funds held days seems incorrect. Please verify.")

    def save(self, *args, **kwargs):
        self.clean()
        # FIX: Lazy import to break circular dependency between models.py and logic.py
        from .logic import normalize_gpa

        if self.normalized_gpa_4 is None:
            self.normalized_gpa_4 = normalize_gpa(self)
        super().save(*args, **kwargs)

    @property
    def preferred_intake_display(self):
        return f"{self.preferred_intake_month} {self.preferred_intake_year}"

    @property
    def preferred_countries_list(self):
        """Return list of country names for compatibility with old code."""
        return list(
            self.preferred_countries.filter(is_active=True).values_list(
                "name", flat=True
            )
        )


class University(models.Model):
    name = models.CharField(max_length=200)
    # FIX: Changed from PROTECT to SET_NULL with null=True, blank=True
    country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="universities",
        help_text="Select the country where the university is located",
    )
    city = models.CharField(max_length=100)
    website = models.URLField()

    program_name = models.CharField(max_length=200)
    degree_level = models.CharField(max_length=50)
    duration_months = models.PositiveSmallIntegerField()
    tuition_usd = models.PositiveIntegerField()
    intake_months = models.JSONField(default=list)

    min_ielts = models.DecimalField(max_digits=3, decimal_places=1, default=6.0)
    min_gpa_4 = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True
    )
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

    DATA_SOURCES = [
        ("manual", "Manual Entry"),
        ("ai_scraped", "AI Scraped"),
        ("import", "Bulk Import"),
    ]
    data_source = models.CharField(
        max_length=50, choices=DATA_SOURCES, default="manual"
    )

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
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="matches"
    )
    university = models.ForeignKey(University, on_delete=models.CASCADE)

    is_eligible = models.BooleanField()
    ineligible_reasons = models.JSONField(default=list)
    preference_score = models.PositiveSmallIntegerField(default=0)
    score_breakdown = models.JSONField(default=dict)

    consultant_shortlisted = models.BooleanField(null=True, blank=True)
    consultant_rejected = models.BooleanField(null=True, blank=True)
    consultant_notes = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
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


# FIX: Removed redundant "uploads/" prefix from document_path
def document_path(instance, filename):
    return f"{instance.student.id}/{instance.doc_type}/{filename}"


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

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="documents"
    )
    doc_type = models.CharField(max_length=20, choices=DOC_TYPES)
    file = models.FileField(upload_to=document_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    REVIEW_CHOICES = [
        ("pending", "Pending Review"),
        ("verified", "Verified Authentic"),
        ("suspicious", "Suspicious — Request Original"),
        ("rejected", "Rejected"),
    ]
    review_status = models.CharField(
        max_length=20, choices=REVIEW_CHOICES, default="pending"
    )
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

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
        if self.file:
            self.file_size_kb = self.file.size // 1024
            self.file_extension = (
                self.file.name.split(".")[-1].lower() if "." in self.file.name else ""
            )
        super().save(*args, **kwargs)


class DocumentUpload(models.Model):
    """Raw document uploaded for AI parsing before creating Student."""

    DOC_TYPES = [
        ("passport", "Passport"),
        ("transcript", "Academic Transcript"),
        ("ielts", "IELTS Scorecard"),
        ("combined", "Combined Documents"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending Processing"),
        ("processing", "Processing"),
        ("review", "Ready for Review"),
        ("confirmed", "Confirmed & Imported"),
        ("failed", "Processing Failed"),
    ]

    doc_type = models.CharField(max_length=20, choices=DOC_TYPES)
    file = models.FileField(upload_to="document_uploads/%Y/%m/%d/")
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    extracted_data = models.JSONField(default=dict, blank=True)
    parsed_student = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_uploads",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    processing_error = models.TextField(blank=True)

    history = HistoricalRecords()

    class Meta:
        indexes = [
            models.Index(fields=["status", "doc_type"]),
            models.Index(fields=["uploaded_by", "status"]),
        ]

    def __str__(self):
        return f"{self.get_doc_type_display()} - {self.status}"
