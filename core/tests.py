from django.test import TestCase
from django.contrib.auth.models import User
from .models import Student, University, MatchResult
from .logic import normalize_gpa, generate_matches, calculate_preference_score
from decimal import Decimal
import datetime

class GPANormalizationTest(TestCase):
    def test_india_10_scale(self):
        student = Student(nationality='India', gpa=Decimal('8.0'), gpa_scale=Decimal('10.0'))
        self.assertEqual(normalize_gpa(student), Decimal('3.20'))

    def test_germany_reverse_scale(self):
        # Germany: 1.0 is best, 5.0 is worst.
        # formula: ((5 - g) / 4) * 4 => 5 - g
        # If g=1.0, (4/4)*4 = 4.0
        # If g=2.5, (2.5/4)*4 = 2.5
        student = Student(nationality='Germany', gpa=Decimal('1.0'), gpa_scale=Decimal('5.0'))
        self.assertEqual(normalize_gpa(student), Decimal('4.00'))

        student.gpa = Decimal('2.0')
        self.assertEqual(normalize_gpa(student), Decimal('3.00'))

class MatchingEngineTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testconsultant')
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
            min_ielts=Decimal('6.5'),
            min_gpa_4=Decimal('3.0'),
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
            gpa=Decimal('8.0'),
            gpa_scale=Decimal('10.0'),
            ielts_overall=Decimal('7.0'),
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
        self.assertEqual(match.score_breakdown['country_match'], 30)

    def test_ineligible_ielts(self):
        # We need to make sure the student is still "eligible" to be picked up by the SQL query
        # (which filters by min_ielts in get_eligible_programs)
        # Wait, if get_eligible_programs filters by min_ielts, then generate_matches won't
        # find the university at all if the student's IELTS is too low.
        # Let's adjust the test to expect no active match if the SQL filter excludes it.
        self.student.ielts_overall = Decimal('6.0')
        self.student.save()
        generate_matches(self.student)
        match = MatchResult.objects.filter(student=self.student, university=self.uni, is_active=True).first()
        self.assertIsNone(match)

    def test_budget_filter(self):
        self.student.max_budget_usd = 15000
        self.student.save()
        generate_matches(self.student)
        # Should be marked as inactive or not found if SQL filter excludes it
        # Actually generate_matches uses get_eligible_programs which filters SQL
        # So it should be marked as is_active=False if it was there, or not created.
        match = MatchResult.objects.filter(student=self.student, university=self.uni, is_active=True).first()
        self.assertIsNone(match)
