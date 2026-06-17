from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Student, University, MatchResult, Country, Document
from .logic import normalize_gpa, generate_matches, calculate_preference_score
from .ai_parser import get_or_create_country, resolve_countries
from decimal import Decimal
import datetime


class CountryModelTest(TestCase):
    def setUp(self):
        self.uk, _ = Country.objects.get_or_create(
            name="United Kingdom", defaults={"code": "GBR"}
        )
        self.usa, _ = Country.objects.get_or_create(
            name="United States", defaults={"code": "USA"}
        )
        self.canada, _ = Country.objects.get_or_create(
            name="Canada", defaults={"code": "CAN"}
        )
        self.india, _ = Country.objects.get_or_create(
            name="India", defaults={"code": "IND"}
        )

    def test_country_creation(self):
        self.assertEqual(self.uk.name, "United Kingdom")
        self.assertEqual(self.uk.code, "GBR")

    def test_get_or_create_country_exact(self):
        country = get_or_create_country("United Kingdom")
        self.assertEqual(country, self.uk)

    def test_get_or_create_country_alias(self):
        country = get_or_create_country("UK")
        self.assertEqual(country, self.uk)

    def test_get_or_create_country_case_insensitive(self):
        country = get_or_create_country("united kingdom")
        self.assertEqual(country, self.uk)

    def test_get_or_create_country_new(self):
        country = get_or_create_country("Australia")
        self.assertEqual(country.name, "Australia")

    def test_resolve_countries_list(self):
        countries = resolve_countries(["UK", "USA", "Canada"])
        self.assertEqual(len(countries), 3)
        self.assertIn(self.uk, countries)
        self.assertIn(self.usa, countries)

    def test_resolve_countries_string(self):
        countries = resolve_countries("UK, USA, Canada")
        self.assertEqual(len(countries), 3)


class GPANormalizationTest(TestCase):
    def setUp(self):
        self.india, _ = Country.objects.get_or_create(
            name="India", defaults={"code": "IND"}
        )
        self.germany, _ = Country.objects.get_or_create(
            name="Germany", defaults={"code": "DEU"}
        )

    def test_india_10_scale(self):
        student = Student(
            nationality=self.india, gpa=Decimal("8.0"), gpa_scale=Decimal("10.0")
        )
        self.assertEqual(normalize_gpa(student), Decimal("3.20"))

    def test_india_100_scale(self):
        student = Student(
            nationality=self.india, gpa=Decimal("75.0"), gpa_scale=Decimal("100.0")
        )
        self.assertEqual(normalize_gpa(student), Decimal("3.00"))

    def test_germany_reverse_scale(self):
        student = Student(
            nationality=self.germany, gpa=Decimal("1.0"), gpa_scale=Decimal("5.0")
        )
        self.assertEqual(normalize_gpa(student), Decimal("4.00"))
        student.gpa = Decimal("2.0")
        self.assertEqual(normalize_gpa(student), Decimal("3.00"))

    def test_unsupported_scale(self):
        unknown, _ = Country.objects.get_or_create(
            name="Unknown", defaults={"code": "UNK"}
        )
        student = Student(
            nationality=unknown, gpa=Decimal("3.0"), gpa_scale=Decimal("4.0")
        )
        self.assertIsNone(normalize_gpa(student))


class MatchingEngineTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testconsultant")
        self.uk, _ = Country.objects.get_or_create(
            name="United Kingdom", defaults={"code": "GBR"}
        )
        self.india, _ = Country.objects.get_or_create(
            name="India", defaults={"code": "IND"}
        )

        self.uni = University.objects.create(
            name="Test Uni",
            country=self.uk,
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
            last_verified_date=datetime.date.today(),
        )

        self.student = Student.objects.create(
            full_name="John Doe",
            email="john@example.com",
            nationality=self.india,
            highest_qualification="Bachelor",
            institution_name="IIT",
            graduation_year=2023,
            gpa=Decimal("8.0"),
            gpa_scale=Decimal("10.0"),
            ielts_overall=Decimal("7.0"),
            preferred_intake_month="September",
            preferred_intake_year=2025,
            max_budget_usd=30000,
            assigned_consultant=self.user,
        )
        self.student.preferred_countries.add(self.uk)

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
        match = MatchResult.objects.filter(
            student=self.student, university=self.uni, is_active=True
        ).first()
        self.assertIsNone(match)

    def test_budget_filter(self):
        self.student.max_budget_usd = 15000
        self.student.save()
        generate_matches(self.student)
        match = MatchResult.objects.filter(
            student=self.student, university=self.uni, is_active=True
        ).first()
        self.assertIsNone(match)

    def test_consultant_decision_preserved(self):
        generate_matches(self.student)
        match = MatchResult.objects.get(student=self.student, university=self.uni)
        match.consultant_shortlisted = True
        match.consultant_notes = "Strong candidate"
        match.save()

        generate_matches(self.student)
        match.refresh_from_db()
        self.assertTrue(match.consultant_shortlisted)
        self.assertEqual(match.consultant_notes, "Strong candidate")


class DocumentPermissionTest(TestCase):
    def setUp(self):
        self.india, _ = Country.objects.get_or_create(
            name="India", defaults={"code": "IND"}
        )
        self.consultant_a = User.objects.create_user(username="consultant_a")
        self.consultant_b = User.objects.create_user(username="consultant_b")
        self.manager = User.objects.create_user(username="manager")
        manager_group, _ = Group.objects.get_or_create(name="manager")
        self.manager.groups.add(manager_group)

        # FIX: Added all required Student fields that are NOT NULL in the model
        self.student_a = Student.objects.create(
            full_name="Student A",
            email="student_a@example.com",
            nationality=self.india,
            assigned_consultant=self.consultant_a,
            highest_qualification="Bachelor",
            institution_name="Test University",
            graduation_year=2023,
            gpa=Decimal("3.5"),
            preferred_intake_month="September",
            preferred_intake_year=2025,
        )
        self.student_b = Student.objects.create(
            full_name="Student B",
            email="student_b@example.com",
            nationality=self.india,
            assigned_consultant=self.consultant_b,
            highest_qualification="Bachelor",
            institution_name="Test University",
            graduation_year=2023,
            gpa=Decimal("3.5"),
            preferred_intake_month="September",
            preferred_intake_year=2025,
        )

        self.doc_a = Document.objects.create(
            student=self.student_a,
            doc_type="passport",
            file=SimpleUploadedFile("passport_a.pdf", b"fake pdf content"),
        )
        self.doc_b = Document.objects.create(
            student=self.student_b,
            doc_type="passport",
            file=SimpleUploadedFile("passport_b.pdf", b"fake pdf content"),
        )

        self.client_a = Client()
        self.client_a.force_login(self.consultant_a)
        self.client_b = Client()
        self.client_b.force_login(self.consultant_b)
        self.client_mgr = Client()
        self.client_mgr.force_login(self.manager)

    def test_consultant_sees_own_student_documents(self):
        response = self.client_a.get(f"/documents/serve/{self.doc_a.id}/")
        self.assertIn(response.status_code, [200, 302])
        self.assertIn("X-Accel-Redirect", response)

    def test_consultant_blocked_from_other_student_documents(self):
        response = self.client_a.get(f"/documents/serve/{self.doc_b.id}/")
        self.assertEqual(response.status_code, 403)

    def test_manager_can_access_all_documents(self):
        response = self.client_mgr.get(f"/documents/serve/{self.doc_b.id}/")
        self.assertIn(response.status_code, [200, 302])
        self.assertIn("X-Accel-Redirect", response)

    def test_unauthenticated_blocked(self):
        anonymous_client = Client()
        response = anonymous_client.get(f"/documents/serve/{self.doc_a.id}/")
        self.assertIn(response.status_code, [302, 403])
