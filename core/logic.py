from .models import Student, University, MatchResult
from django.db import models, connection
from decimal import Decimal

def q2(val):
    return Decimal(str(val)).quantize(Decimal('0.00'))

CONVERSION_TABLE = {
    ('India', '10.0'): lambda g: q2(g / 10 * 4),
    ('India', '100.0'): lambda g: q2(g / 100 * 4),
    ('UK', '4.0'): lambda g: q2(g),
    ('USA', '4.0'): lambda g: q2(g),
    ('Germany', '5.0'): lambda g: q2((5 - g) / 4 * 4),  # Reverse scale
    ('Australia', '7.0'): lambda g: q2(g / 7 * 4),
    ('Canada', '4.0'): lambda g: q2(g),
    ('Pakistan', '4.0'): lambda g: q2(g),
    ('Nigeria', '5.0'): lambda g: q2(g / 5 * 4),
    ('Bangladesh', '4.0'): lambda g: q2(g),
}

def normalize_gpa(student):
    key = (student.nationality, str(float(student.gpa_scale)))
    if key in CONVERSION_TABLE:
        return CONVERSION_TABLE[key](float(student.gpa))
    return None  # Manual entry required

def get_eligible_programs(student):
    """Hard eligibility filters — binary yes/no."""
    if not student.ielts_overall or not student.normalized_gpa_4:
        return University.objects.none()

    if connection.vendor == 'sqlite':
        # SQLite doesn't support __contains for JSON lists, use a simple icontains fallback for tests
        qs = University.objects.filter(
            is_active=True,
            min_ielts__lte=student.ielts_overall,
            intake_months__icontains=student.preferred_intake_month,
            max_gap_years__gte=student.gap_years,
        )
    else:
        qs = University.objects.filter(
            is_active=True,
            min_ielts__lte=student.ielts_overall,
            intake_months__contains=[student.preferred_intake_month],
            max_gap_years__gte=student.gap_years,
        )

    if student.backlogs > 0:
        qs = qs.filter(accepts_backlogs=True)

    # Budget filter (if specified)
    if student.max_budget_usd:
        qs = qs.filter(tuition_usd__lte=student.max_budget_usd)

    # GPA filter (using normalized 4.0 scale)
    qs = qs.filter(
        models.Q(min_gpa_4__isnull=True) | models.Q(min_gpa_4__lte=student.normalized_gpa_4)
    )

    return qs

def calculate_preference_score(student, university):
    """Transparent, student-preference-aligned scoring."""
    score = 0
    breakdown = {}

    # Country match (30%) — binary, student knows where they want to go
    if university.country in student.preferred_countries:
        country_score = 30
    else:
        country_score = 0
    score += country_score
    breakdown['country_match'] = country_score

    # Budget fit (20%) — ratio-based, not headroom
    if student.max_budget_usd:
        ratio = university.tuition_usd / student.max_budget_usd
        if ratio <= 0.7:
            budget_score = 20  # Comfortable fit
        elif ratio <= 0.85:
            budget_score = 16
        elif ratio <= 1.0:
            budget_score = 12  # Tight but fits
        else:
            budget_score = 0   # Shouldn't happen due to SQL filter
    else:
        budget_score = 12  # No budget specified, neutral
    score += budget_score
    breakdown['budget_fit'] = budget_score

    # Scholarship alignment (20%) — conditional on student priority
    if student.scholarship_priority >= 4:
        scholarship_score = 20 if university.scholarship_available else 5
    elif student.scholarship_priority >= 2:
        scholarship_score = 15 if university.scholarship_available else 10
    else:
        scholarship_score = 10  # Student doesn't care, neutral
    score += scholarship_score
    breakdown['scholarship_alignment'] = scholarship_score

    # Ranking alignment (20%) — conditional on student priority
    if university.ranking_qs:
        if student.ranking_priority >= 4:
            if university.ranking_qs <= 100:
                ranking_score = 20
            elif university.ranking_qs <= 300:
                ranking_score = 16
            elif university.ranking_qs <= 500:
                ranking_score = 12
            else:
                ranking_score = 8
        elif student.ranking_priority >= 2:
            if university.ranking_qs <= 500:
                ranking_score = 18
            else:
                ranking_score = 12
        else:
            ranking_score = 14  # Neutral
    else:
        ranking_score = 12  # No ranking data
    score += ranking_score
    breakdown['ranking_alignment'] = ranking_score

    # Intake match (10%) — binary, miss it and nothing else matters
    if student.preferred_intake_month in university.intake_months:
        intake_score = 10
    else:
        intake_score = 0  # Shouldn't happen due to SQL filter
    score += intake_score
    breakdown['intake_match'] = intake_score

    return {
        'total_score': score,
        'breakdown': breakdown
    }

def generate_matches(student):
    """
    Generate or update match results.
    PRESERVES consultant decisions across regenerations.
    """
    eligible = get_eligible_programs(student)
    existing = {
        m.university_id: m
        for m in MatchResult.objects.filter(student=student)
    }

    # Track which existing matches are still eligible
    still_eligible_ids = set()

    for uni in eligible:
        score_data = calculate_preference_score(student, uni)
        ineligible_reasons = []

        # Edge case validation
        if student.ielts_overall < uni.min_ielts:
            ineligible_reasons.append(f"IELTS {student.ielts_overall} < required {uni.min_ielts}")
        if student.normalized_gpa_4 and uni.min_gpa_4 and student.normalized_gpa_4 < uni.min_gpa_4:
            ineligible_reasons.append(f"GPA {student.normalized_gpa_4} < required {uni.min_gpa_4}")

        is_eligible = len(ineligible_reasons) == 0

        if uni.id in existing:
            match = existing[uni.id]
            match.is_eligible = is_eligible
            match.ineligible_reasons = ineligible_reasons
            match.preference_score = score_data['total_score'] if is_eligible else 0
            match.score_breakdown = score_data['breakdown'] if is_eligible else {}
            match.is_active = True
            match.save()
        else:
            MatchResult.objects.create(
                student=student,
                university=uni,
                is_eligible=is_eligible,
                ineligible_reasons=ineligible_reasons,
                preference_score=score_data['total_score'] if is_eligible else 0,
                score_breakdown=score_data['breakdown'] if is_eligible else {},
                is_active=True
            )

        still_eligible_ids.add(uni.id)

    # Soft-delete stale matches (no longer eligible)
    stale_ids = set(existing.keys()) - still_eligible_ids
    if stale_ids:
        MatchResult.objects.filter(
            student=student,
            university_id__in=stale_ids
        ).update(is_active=False)
