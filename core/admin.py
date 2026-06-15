from django.contrib import admin
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin
from .models import Student, University, MatchResult, Document
from .logic import generate_matches

@admin.register(Student)
class StudentAdmin(SimpleHistoryAdmin):
    list_display = ('full_name', 'email', 'stage', 'assigned_consultant', 'pdf_link')
    list_filter = ('stage', 'assigned_consultant', 'nationality')
    search_fields = ('full_name', 'email')
    actions = ['trigger_matching']

    def pdf_link(self, obj):
        from django.urls import reverse
        url = reverse('generate_student_pdf', args=[obj.id])
        return format_html('<a href="{}" target="_blank">PDF</a>', url)
    pdf_link.short_description = 'Profile PDF'

    def trigger_matching(self, request, queryset):
        for student in queryset:
            generate_matches(student)
        self.message_user(request, f"Matching engine triggered for {queryset.count()} students.")
    trigger_matching.short_description = "Run matching engine"

@admin.register(University)
class UniversityAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'country', 'program_name', 'tuition_usd', 'freshness_badge')
    list_filter = ('country', 'degree_level', 'is_active')
    search_fields = ('name', 'program_name')

    def freshness_badge(self, obj):
        status, age = obj.data_freshness
        if status == 'stale':
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ Stale ({} days)</span>',
                age
            )
        return format_html('<span style="color: green;">✓ Fresh</span>')
    freshness_badge.short_description = 'Data Freshness'

@admin.register(MatchResult)
class MatchResultAdmin(SimpleHistoryAdmin):
    list_display = ('student', 'university', 'preference_score', 'is_eligible', 'consultant_shortlisted')
    list_filter = ('is_eligible', 'consultant_shortlisted', 'is_active')
    raw_id_fields = ('student', 'university')

@admin.register(Document)
class DocumentAdmin(SimpleHistoryAdmin):
    list_display = ('student', 'doc_type', 'review_status', 'uploaded_at', 'view_link')
    list_filter = ('doc_type', 'review_status')
    raw_id_fields = ('student',)

    def view_link(self, obj):
        if obj.file:
            from django.urls import reverse
            url = reverse('serve_document', args=[obj.id])
            return format_html('<a href="{}" target="_blank">View</a>', url)
        return "No file"
    view_link.short_description = 'File'
