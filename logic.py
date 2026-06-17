from .models import Student, University, MatchResult
from django.db import models, connection
from decimal import Decimal


def q2(val):
    return Decimal(str(val)).quantize(Decimal("0.00"))


CONVERSION_TABLE = {
    ("India", "10.0"): lambda g: q2(g / 10 * 4),
    ("India", "100.0"): lambda g: q2(g / 100 * 4),
    ("UK", "4.0"): lambda g: q2(g),
    ("USA", "4.0"): lambda g: q2(g),
    ("Germany", "5.0"): lambda g: q2(5 - g),
    ("Australia", "7.0"): lambda g: q2(g / 7 * 4),
    ("Canada", "4.0"): lambda g: q2(g),
    ("Pakistan", "4.0"): lambda g: q2(g),
    ("Nigeria", "5.0"): lambda g: q2(g / 5 * 4),
    ("Bangladesh", "4.0"): lambda g: q2(g),
}


def normalize_gpa(student):
    nationality_name = student.nationality.name if student.nationality else ""
    key = (nationality_name, str(float(student.gpa_scale)))
    if key in CONVERSION_TABLE:
        return CONVERSION_TABLE[key](float(student.gpa))
    return None


def get_eligible_programs(student):
    if not student.ielts_overall or not student.normalized_gpa_4:
        return University.objects.none()

    if connection.vendor == "sqlite":
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

    if student.max_budget_usd:
        qs = qs.filter(tuition_usd__lte=student.max_budget_usd)

    qs = qs.filter(
        models.Q(min_gpa_4__isnull=True)
        | models.Q(min_gpa_4__lte=student.normalized_gpa_4)
    )

    return qs


def calculate_preference_score(student, university):
    score = 0
    breakdown = {}

    student_country_names = set(
        student.preferred_countries.values_list("name", flat=True)
    )
    country_score = (
        30
        if university.country and university.country.name in student_country_names
        else 0
    )
    score += country_score
    breakdown["country_match"] = country_score

    if student.max_budget_usd:
        ratio = university.tuition_usd / student.max_budget_usd
        if ratio <= 0.7:
            budget_score = 20
        elif ratio <= 0.85:
            budget_score = 16
        elif ratio <= 1.0:
            budget_score = 12
        else:
            budget_score = 0
    else:
        budget_score = 12
    score += budget_score
    breakdown["budget_fit"] = budget_score

    if student.scholarship_priority >= 4:
        scholarship_score = 20 if university.scholarship_available else 5
    elif student.scholarship_priority >= 2:
        scholarship_score = 15 if university.scholarship_available else 10
    else:
        scholarship_score = 10
    score += scholarship_score
    breakdown["scholarship_alignment"] = scholarship_score

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
            ranking_score = 14
    else:
        ranking_score = 12
    score += ranking_score
    breakdown["ranking_alignment"] = ranking_score

    intake_score = (
        10 if student.preferred_intake_month in university.intake_months else 0
    )
    score += intake_score
    breakdown["intake_match"] = intake_score

    return {
        "total_score": score,
        "breakdown": breakdown,
    }


def generate_matches(student):
    eligible = get_eligible_programs(student)
    existing = {m.university_id: m for m in MatchResult.objects.filter(student=student)}

    to_create = []
    to_update = []
    still_eligible_ids = set()

    for uni in eligible:
        score_data = calculate_preference_score(student, uni)

        # FIX: Removed redundant eligibility checks that were dead code.
        # get_eligible_programs() already filters by IELTS and GPA.
        is_eligible = True
        ineligible_reasons = []

        if uni.id in existing:
            match = existing[uni.id]
            match.is_eligible = is_eligible
            match.ineligible_reasons = ineligible_reasons
            match.preference_score = score_data["total_score"]
            match.score_breakdown = score_data["breakdown"]
            match.is_active = True
            to_update.append(match)
        else:
            to_create.append(
                MatchResult(
                    student=student,
                    university=uni,
                    is_eligible=is_eligible,
                    ineligible_reasons=ineligible_reasons,
                    preference_score=score_data["total_score"],
                    score_breakdown=score_data["breakdown"],
                    is_active=True,
                )
            )

        still_eligible_ids.add(uni.id)

    if to_create:
        MatchResult.objects.bulk_create(to_create, ignore_conflicts=True)
    if to_update:
        MatchResult.objects.bulk_update(
            to_update,
            [
                "is_eligible",
                "ineligible_reasons",
                "preference_score",
                "score_breakdown",
                "is_active",
            ],
        )

    stale_ids = set(existing.keys()) - still_eligible_ids
    if stale_ids:
        MatchResult.objects.filter(
            student=student,
            university_id__in=stale_ids,
        ).update(is_active=False)
