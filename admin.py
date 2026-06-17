from django.contrib import admin
from django.urls import path, reverse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import format_html
from django.contrib import messages
from django import forms
from simple_history.admin import SimpleHistoryAdmin
from .models import Student, University, MatchResult, Document, DocumentUpload, Country
from .logic import generate_matches
from .ai_parser import (
    process_document_upload,
    create_student_from_extracted,
    scrape_university_website,
)


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "university_count", "student_count")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    actions = ["activate_countries", "deactivate_countries"]

    def university_count(self, obj):
        return obj.universities.count()

    university_count.short_description = "Universities"

    def student_count(self, obj):
        return obj.students_nationality.count()

    student_count.short_description = "Students (Nationality)"

    def activate_countries(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"Activated {queryset.count()} countries.")

    activate_countries.short_description = "Activate selected countries"

    def deactivate_countries(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {queryset.count()} countries.")

    deactivate_countries.short_description = "Deactivate selected countries"


@admin.register(Student)
class StudentAdmin(SimpleHistoryAdmin):
    list_display = (
        "full_name",
        "email",
        "stage",
        "assigned_consultant",
        "nationality_display",
        "pdf_link",
    )
    list_filter = ("stage", "assigned_consultant", "nationality", "preferred_countries")
    search_fields = ("full_name", "email")
    filter_horizontal = ("preferred_countries",)
    actions = ["trigger_matching"]

    fieldsets = (
        (
            "Personal Information",
            {"fields": ("full_name", "email", "phone", "nationality")},
        ),
        (
            "Academic Information",
            {
                "fields": (
                    "highest_qualification",
                    "institution_name",
                    "graduation_year",
                    "gpa",
                    "gpa_scale",
                    "normalized_gpa_4",
                    "backlogs",
                    "gap_years",
                )
            },
        ),
        (
            "English Proficiency",
            {
                "fields": (
                    "ielts_overall",
                    "ielts_listening",
                    "ielts_reading",
                    "ielts_writing",
                    "ielts_speaking",
                    "ielts_trf_number",
                    "ielts_test_date",
                )
            },
        ),
        (
            "Financial Information",
            {"fields": ("available_funds_usd", "funds_held_days", "max_budget_usd")},
        ),
        (
            "Preferences",
            {
                "fields": (
                    "preferred_countries",
                    "preferred_intake_month",
                    "preferred_intake_year",
                    "scholarship_priority",
                    "ranking_priority",
                )
            },
        ),
        ("Pipeline", {"fields": ("stage", "assigned_consultant")}),
        (
            "Consent",
            {
                "fields": (
                    "consent_storage",
                    "consent_matching",
                    "consent_communication",
                    "consent_documents",
                    "consent_timestamp",
                    "consent_ip",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def nationality_display(self, obj):
        return obj.nationality.name if obj.nationality else "—"

    nationality_display.short_description = "Nationality"

    def pdf_link(self, obj):
        url = reverse("generate_student_pdf", args=[obj.id])
        return format_html('<a href="{}" target="_blank">PDF</a>', url)

    pdf_link.short_description = "Profile PDF"

    def trigger_matching(self, request, queryset):
        for student in queryset:
            generate_matches(student)
        self.message_user(
            request, f"Matching engine triggered for {queryset.count()} students."
        )

    trigger_matching.short_description = "Run matching engine"


# --- Form for AI-powered university addition ---
class AddUniversityViaAIForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        label="University Name",
        widget=forms.TextInput(attrs={"placeholder": "e.g., University of Birmingham"}),
    )
    website = forms.URLField(
        label="Website URL",
        widget=forms.URLInput(attrs={"placeholder": "https://www.example.edu/program"}),
    )
    country = forms.ModelChoiceField(
        queryset=Country.objects.filter(is_active=True),
        required=False,
        label="Country (optional)",
    )
    city = forms.CharField(
        max_length=100,
        required=False,
        label="City (optional)",
        widget=forms.TextInput(attrs={"placeholder": "e.g., London"}),
    )


@admin.register(University)
class UniversityAdmin(SimpleHistoryAdmin):
    list_display = (
        "name",
        "country_display",
        "program_name",
        "tuition_usd",
        "freshness_badge",
        "data_source",
    )
    list_filter = (
        "country",
        "degree_level",
        "is_active",
        "data_source",
        "scholarship_available",
    )
    search_fields = ("name", "program_name", "city")
    actions = ["scrape_university_data", "mark_as_verified"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "country", "city", "website")}),
        (
            "Program Details",
            {
                "fields": (
                    "program_name",
                    "degree_level",
                    "duration_months",
                    "tuition_usd",
                    "intake_months",
                )
            },
        ),
        (
            "Requirements",
            {
                "fields": (
                    "min_ielts",
                    "min_gpa_4",
                    "accepts_backlogs",
                    "max_gap_years",
                    "requires_gre",
                    "requires_work_exp",
                    "work_exp_months",
                )
            },
        ),
        (
            "Financial",
            {
                "fields": (
                    "min_funds_usd",
                    "funds_held_days_required",
                    "scholarship_available",
                )
            },
        ),
        ("Ranking & Accreditation", {"fields": ("ranking_qs", "accreditation")}),
        (
            "Data Management",
            {"fields": ("last_verified_date", "data_source", "is_active")},
        ),
    )

    def country_display(self, obj):
        return obj.country.name if obj.country else "—"

    country_display.short_description = "Country"
    country_display.admin_order_field = "country__name"

    def freshness_badge(self, obj):
        status, age = obj.data_freshness
        if status == "stale":
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ Stale ({} days)</span>',
                age,
            )
        return format_html('<span style="color: green;">✓ Fresh</span>')

    freshness_badge.short_description = "Data Freshness"

    # --- Custom URLs for the two buttons ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "add-via-ai/",
                self.admin_site.admin_view(self.add_via_ai_view),
                name="university_add_via_ai",
            ),
            path(
                "<int:university_id>/scrape/",
                self.admin_site.admin_view(self.scrape_single_view),
                name="university_scrape",
            ),
        ]
        return custom_urls + urls

    # --- View: Add University via AI ---
    def add_via_ai_view(self, request):
        """Show form for adding university via AI scraping."""
        if request.method == "POST":
            form = AddUniversityViaAIForm(request.POST)
            if form.is_valid():
                name = form.cleaned_data["name"]
                website = form.cleaned_data["website"]
                country = form.cleaned_data["country"]
                city = form.cleaned_data["city"] or "TBD"

                # Create minimal university record
                from django.utils import timezone

                university = University.objects.create(
                    name=name,
                    website=website,
                    country=country,
                    city=city,
                    program_name="TBD",
                    degree_level="Master",
                    duration_months=12,
                    tuition_usd=0,
                    intake_months=[],
                    min_ielts=6.0,
                    min_funds_usd=0,
                    last_verified_date=timezone.now().date(),
                    data_source="ai_scraped",
                )

                # Now scrape the website
                try:
                    updated_fields = scrape_university_website(university)
                    messages.success(
                        request,
                        f"✅ University created and scraped successfully! "
                        f"Updated fields: {', '.join(updated_fields) if updated_fields else 'None extracted'}",
                    )
                    return redirect("admin:core_university_change", university.id)

                except Exception as e:
                    messages.warning(
                        request,
                        f"⚠️ University created but scraping failed: {str(e)}. "
                        f"You can edit manually or try scraping again later.",
                    )
                    return redirect("admin:core_university_change", university.id)
        else:
            form = AddUniversityViaAIForm()

        context = {
            "form": form,
            "title": "Add University via AI",
            "opts": self.model._meta,
            "has_view_permission": self.has_view_permission(request),
        }
        return render(request, "admin/core/university/add_via_ai.html", context)

    # --- View: Scrape existing university ---
    def scrape_single_view(self, request, university_id):
        """Handle scrape button click from change form."""
        university = get_object_or_404(University, pk=university_id)

        if not university.website:
            messages.error(request, "University has no website URL.")
            return redirect("admin:core_university_change", university_id)

        try:
            updated_fields = scrape_university_website(university)
            if updated_fields:
                messages.success(
                    request,
                    f"✅ Scraped successfully! Updated: {', '.join(updated_fields)}",
                )
            else:
                messages.warning(
                    request, "Scraping completed but no new data was extracted."
                )
        except Exception as e:
            messages.error(request, f"❌ Scraping failed: {str(e)}")

        return redirect("admin:core_university_change", university_id)

    def scrape_university_data(self, request, queryset):
        """Bulk action for scraping multiple universities."""
        success = 0
        failed = 0
        for uni in queryset:
            try:
                updated_fields = scrape_university_website(uni)
                success += 1
                self.message_user(
                    request,
                    f"Updated {uni.name}: {', '.join(updated_fields)}",
                    level="SUCCESS",
                )
            except Exception as e:
                failed += 1
                self.message_user(request, f"Failed {uni.name}: {e}", level="ERROR")

        self.message_user(
            request, f"Scraping complete: {success} succeeded, {failed} failed."
        )

    scrape_university_data.short_description = "AI: Scrape website data"

    def mark_as_verified(self, request, queryset):
        from django.utils import timezone

        queryset.update(last_verified_date=timezone.now().date(), data_source="manual")
        self.message_user(
            request, f"Marked {queryset.count()} universities as verified."
        )

    mark_as_verified.short_description = "Mark as manually verified"


@admin.register(MatchResult)
class MatchResultAdmin(SimpleHistoryAdmin):
    list_display = (
        "student",
        "university",
        "preference_score",
        "is_eligible",
        "consultant_shortlisted",
    )
    list_filter = ("is_eligible", "consultant_shortlisted", "is_active")
    raw_id_fields = ("student", "university")


@admin.register(Document)
class DocumentAdmin(SimpleHistoryAdmin):
    list_display = ("student", "doc_type", "review_status", "uploaded_at", "view_link")
    list_filter = ("doc_type", "review_status")
    raw_id_fields = ("student",)

    def view_link(self, obj):
        if obj.file:
            url = reverse("serve_document", args=[obj.id])
            return format_html('<a href="{}" target="_blank">View</a>', url)
        return "No file"

    view_link.short_description = "File"


@admin.register(DocumentUpload)
class DocumentUploadAdmin(SimpleHistoryAdmin):
    list_display = (
        "doc_type",
        "status",
        "uploaded_by",
        "uploaded_at",
        "parsed_student_link",
        "extracted_summary",
    )
    list_filter = ("status", "doc_type", "uploaded_at")
    readonly_fields = ("extracted_data_pretty", "processing_error", "parsed_student")
    actions = ["process_documents", "confirm_and_create_students"]

    def extracted_summary(self, obj):
        data = obj.extracted_data or {}
        if not isinstance(data, dict):
            return "—"
        if data:
            name = data.get("full_name", "N/A")
            gpa = data.get("gpa", "N/A")
            ielts = data.get("ielts_overall", "N/A")
            nationality = data.get("nationality", "N/A")
            return f"{name} | {nationality} | GPA: {gpa} | IELTS: {ielts}"
        return "—"

    extracted_summary.short_description = "Extracted Data"

    def extracted_data_pretty(self, obj):
        import json

        data = obj.extracted_data or {}
        if not isinstance(data, dict):
            data = {}
        return format_html(
            "<pre>{}</pre>",
            json.dumps(data, indent=2, ensure_ascii=False),
        )

    extracted_data_pretty.short_description = "Extracted Data (JSON)"

    def parsed_student_link(self, obj):
        if obj.parsed_student:
            url = reverse("admin:core_student_change", args=[obj.parsed_student.id])
            return format_html('<a href="{}">{}</a>', url, obj.parsed_student.full_name)
        return "—"

    parsed_student_link.short_description = "Created Student"

    def process_documents(self, request, queryset):
        processed = 0
        failed = 0

        for upload in queryset.filter(status="pending"):
            try:
                process_document_upload(upload)
                processed += 1
            except Exception as e:
                failed += 1
                self.message_user(request, f"Failed {upload}: {e}", level="ERROR")

        self.message_user(
            request,
            f'Processed: {processed}, Failed: {failed}. Review "Ready for Review" items.',
        )

    process_documents.short_description = "AI: Extract data from documents"

    def confirm_and_create_students(self, request, queryset):
        created = 0

        for upload in queryset.filter(status="review"):
            try:
                create_student_from_extracted(upload)
                created += 1
            except Exception as e:
                self.message_user(request, f"Failed {upload}: {e}", level="ERROR")

        self.message_user(request, f"Created {created} students.")

    confirm_and_create_students.short_description = "Confirm & create students"
