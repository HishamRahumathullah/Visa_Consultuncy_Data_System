from django.test import TestCase
from django.contrib.auth.models import User
from .models import Student, University, MatchResult
from .logic import normalize_gpa, generate_matches, calculate_preference_score
from decimal import Decimal
import datetime


class GPANormalizationTest(TestCase):
    def test_india_10_scale(self):
        student = Student(nationality="India", gpa=Decimal("8.0"), gpa_scale=Decimal("10.0"))
        self.assertEqual(normalize_gpa(student), Decimal("3.20"))

    def test_india_100_scale(self):
        student = Student(nationality="India", gpa=Decimal("75.0"), gpa_scale=Decimal("100.0"))
        self.assertEqual(normalize_gpa(student), Decimal("3.00"))

    def test_germany_reverse_scale(self):
        # Germany: 1.0 is best, 5.0 is worst.
        student = Student(nationality="Germany", gpa=Decimal("1.0"), gpa_scale=Decimal("5.0"))
        self.assertEqual(normalize_gpa(student), Decimal("4.00"))

        student.gpa = Decimal("2.0")
        self.assertEqual(normalize_gpa(student), Decimal("3.00"))

    def test_unsupported_scale(self):
        student = Student(nationality="Unknown", gpa=Decimal("3.0"), gpa_scale=Decimal("4.0"))
        self.assertIsNone(normalize_gpa(student))


class MatchingEngineTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testconsultant")
        self.uni = University.objects.create(
            name="Test Uni",
            country="UK",
            city="London",
            website="http://test.edu",
            program_name="CS",
            degree_level="Master",
            duration_months=12,
            tuition_usd=20000,
            intake_months=["September"],
            min_ielts=Decimal("6.5"),
            min_gpa_4=Decimal("3.0"),
            accepts_backlogs=True,
            max_gap_years=5,
            min_funds_usd=25000,
            last_verified_date=datetime.date.today()
        )

        self.student = Student.objects.create(
            full_name="John Doe",
            email="john@example.com",
            nationality="India",
            highest_qualification="Bachelor",
            institution_name="IIT",
            graduation_year=2023,
            gpa=Decimal("8.0"),
            gpa_scale=Decimal("10.0"),
            ielts_overall=Decimal("7.0"),
            preferred_intake_month="September",
            preferred_intake_year=2025,
            preferred_countries=["UK"],
            max_budget_usd=30000,
            assigned_consultant=self.user
        )

    def test_eligible_match(self):
        generate_matches(self.student)
        match = MatchResult.objects.get(student=self.student, university=self.uni)
        self.assertTrue(match.is_eligible)
        self.assertGreater(match.preference_score, 0)
        self.assertEqual(match.score_breakdown["country_match"], 30)

    def test_ineligible_ielts(self):
        self.student.ielts_overall = Decimal("6.0")
        self.student.save()
        generate_matches(self.student)
        match = MatchResult.objects.filter(student=self.student, university=self.uni, is_active=True).first()
        self.assertIsNone(match)

    def test_budget_filter(self):
        self.student.max_budget_usd = 15000
        self.student.save()
        generate_matches(self.student)
        match = MatchResult.objects.filter(student=self.student, university=self.uni, is_active=True).first()
        self.assertIsNone(match)

    def test_consultant_decision_preserved(self):
        # Create initial match and mark as shortlisted
        generate_matches(self.student)
        match = MatchResult.objects.get(student=self.student, university=self.uni)
        match.consultant_shortlisted = True
        match.consultant_notes = "Strong candidate"
        match.save()

        # Regenerate matches — consultant decision should be preserved
        generate_matches(self.student)
        match.refresh_from_db()
        self.assertTrue(match.consultant_shortlisted)
        self.assertEqual(match.consultant_notes, "Strong candidate")


class DocumentPermissionTest(TestCase):
    def setUp(self):
        self.consultant_a = User.objects.create_user(username="consultant_a")
        self.consultant_b = User.objects.create_user(username="consultant_b")
        self.manager = User.objects.create_user(username="manager")
        self.manager.groups.create(name="manager")

        self.student_a = Student.objects.create(
            full_name="Student A",
            email="student_a@example.com",
            nationality="India",
            assigned_consultant=self.consultant_a
        )
        self.student_b = Student.objects.create(
            full_name="Student B",
            email="student_b@example.com",
            nationality="India",
            assigned_consultant=self.consultant_b
        )

    def test_consultant_sees_own_student_documents(self):
        """Consultant can access documents for their assigned students."""
        # This would need actual file upload testing in integration tests
        pass

    def test_consultant_blocked_from_other_student_documents(self):
        """Consultant cannot access documents for other consultants' students."""
        # This would need actual file upload testing in integration tests
        pass
