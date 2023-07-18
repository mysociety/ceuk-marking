from collections import defaultdict

from django.db.models import Max, OuterRef, Q, Subquery, Sum

from crowdsourcer.models import (
    Option,
    PublicAuthority,
    Question,
    QuestionGroup,
    Response,
    Section,
)

SECTION_WEIGHTINGS = {
    "Buildings & Heating": {
        "Single Tier": 0.20,
        "District": 0.25,
        "County": 0.20,
        "Northern Ireland": 0.20,
    },
    "Transport": {
        "Single Tier": 0.20,
        "District": 0.05,
        "County": 0.30,
        "Northern Ireland": 0.15,
    },
    "Planning & Land Use": {
        "Single Tier": 0.15,
        "District": 0.25,
        "County": 0.05,
        "Northern Ireland": 0.15,
    },
    "Governance & Finance": {
        "Single Tier": 0.15,
        "District": 0.15,
        "County": 0.15,
        "Northern Ireland": 0.20,
    },
    "Biodiversity": {
        "Single Tier": 0.10,
        "District": 0.10,
        "County": 0.10,
        "Northern Ireland": 0.10,
    },
    "Collaboration & Engagement": {
        "Single Tier": 0.10,
        "District": 0.10,
        "County": 0.10,
        "Northern Ireland": 0.10,
    },
    "Waste Reduction & Food": {
        "Single Tier": 0.10,
        "District": 0.10,
        "County": 0.10,
        "Northern Ireland": 0.10,
    },
    "Transport (CA)": {
        "Combined Authority": 0.25,
    },
    "Buildings & Heating & Green Skills (CA)": {
        "Combined Authority": 0.25,
    },
    "Governance & Finance (CA)": {
        "Combined Authority": 0.20,
    },
    "Planning & Biodiversity (CA)": {
        "Combined Authority": 0.10,
    },
    "Collaboration & Engagement (CA)": {
        "Combined Authority": 0.20,
    },
}


def number_and_part(number=None, number_part=None):
    if number_part is not None:
        return f"{number}{number_part}"
    return f"{number}"


def weighting_to_points(weighting="low"):
    weighting = weighting.lower()
    points = 1
    if weighting == "medium":
        points = 2
    elif weighting == "high":
        points = 3

    return points


def get_section_maxes():
    section_maxes = defaultdict(dict)
    section_weighted_maxes = defaultdict(dict)
    group_totals = defaultdict(int)
    q_maxes = defaultdict(int)

    for section in Section.objects.all():
        q_section_maxes = {}
        for group in QuestionGroup.objects.all():
            questions = Question.objects.filter(section=section, questiongroup=group)

            maxes = (
                Option.objects.filter(
                    question__in=questions,
                    question__question_type__in=["yes_no", "select_one"],
                )
                .select_related("question")
                .values("question__pk", "question__number", "question__number_part")
                .annotate(highest=Max("score"))
            )
            totals = (
                Option.objects.filter(question__in=questions)
                .exclude(question__question_type__in=["yes_no", "select_one"])
                .select_related("question")
                .values("question__pk", "question__number", "question__number_part")
                .annotate(highest=Sum("score"))
            )

            max_score = 0
            for m in maxes:
                q_section_maxes[
                    number_and_part(m["question__number"], m["question__number_part"])
                ] = m["highest"]
                max_score += m["highest"]

            for m in totals:
                q_section_maxes[
                    number_and_part(m["question__number"], m["question__number_part"])
                ] = m["highest"]
                max_score += m["highest"]

            weighted_max = 0
            for q in questions:
                weighted_max += weighting_to_points(q.weighting)

            section_maxes[section.title][group.description] = max_score
            section_weighted_maxes[section.title][group.description] = weighted_max
            group_totals[group.description] += max_score
            q_maxes[section.title] = q_section_maxes.copy()

    return section_maxes, group_totals, q_maxes, section_weighted_maxes


def get_blank_section_scores():
    raw_scores = defaultdict(dict)
    weighted = defaultdict(dict)

    non_ca_sections = {
        x: 0
        for x in Section.objects.exclude(title__contains="(CA)").values_list(
            "title", flat=True
        )
    }
    ca_sections = {
        x: 0
        for x in Section.objects.filter(title__contains="(CA)").values_list(
            "title", flat=True
        )
    }

    for council in PublicAuthority.objects.filter(do_not_mark=False).all():
        if council.type == "COMB":
            weighted[council.name] = ca_sections.copy()
            raw_scores[council.name] = ca_sections.copy()
        else:
            weighted[council.name] = non_ca_sections.copy()
            raw_scores[council.name] = non_ca_sections.copy()

    return raw_scores, weighted


def get_weighted_question_score(score, max_score, weighting):
    return (score / max_score) * weighting_to_points(weighting)


def get_section_scores(q_maxes):
    raw_scores, weighted = get_blank_section_scores()

    for section in Section.objects.all():
        options = (
            Response.objects.filter(
                response_type__type="Audit", question__section=section
            )
            .annotate(
                score=Subquery(
                    Option.objects.filter(
                        Q(pk=OuterRef("option")) | Q(pk__in=OuterRef("multi_option"))
                    )
                    .values("question")
                    .annotate(total=Sum("score"))
                    .values("total")
                )
            )
            .select_related("authority")
        )

        totals = options.values("authority__name").annotate(total=Sum("score"))

        for total in totals:
            raw_scores[total["authority__name"]][section.title] = total["total"]

        scores = options.select_related("questions").values(
            "score",
            "authority__name",
            "question__number",
            "question__number_part",
            "question__weighting",
        )

        for score in scores:
            q = number_and_part(
                score["question__number"], score["question__number_part"]
            )
            q_max = q_maxes[section.title][q]
            weighted_score = get_weighted_question_score(
                score["score"], q_max, score["question__weighting"]
            )
            weighted[score["authority__name"]][section.title] += weighted_score

    return raw_scores, weighted


def calculate_council_totals(
    raw_scores, weighted_scores, weighted_maxes, raw_maxes, group_maxes, groups
):
    section_totals = defaultdict(dict)
    totals = {}

    for council, raw in raw_scores.items():
        total = 0
        weighted_total = 0
        council_group = groups[council]

        for section, score in raw.items():
            total += score

            percentage_score = score / raw_maxes[section][council_group]
            weighted_score = (
                weighted_scores[council][section]
                / weighted_maxes[section][council_group]
            ) * SECTION_WEIGHTINGS[section][council_group]

            section_totals[council][section] = {
                "raw": score,
                "raw_percent": percentage_score,
                "weighted": weighted_score,
            }

            weighted_total += weighted_score

        totals[council] = {
            "raw_total": total,
            "percent_total": total / group_maxes[council_group],
            "weighted_total": weighted_total,
        }

    return totals, section_totals
