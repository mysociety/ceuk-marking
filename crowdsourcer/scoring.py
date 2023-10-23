from collections import defaultdict
from copy import deepcopy

from django.db.models import Count, Max, OuterRef, Q, Subquery, Sum

from crowdsourcer.models import (
    Option,
    PublicAuthority,
    Question,
    QuestionGroup,
    Response,
    ResponseType,
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

EXCEPTIONS = {
    "Transport": {
        "Single Tier": {
            "scotland": ["6", "8b"],
            "wales": ["6", "8b"],
        },
        "LBO": ["6"],
        "Greater London Authority": ["6"],
    },
    "Biodiversity": {
        "Single Tier": {
            "scotland": ["4"],
            "wales": ["4"],
        }
    },
    "Buildings & Heating": {
        "Single Tier": {
            "scotland": ["8"],
        },
        "Northern Ireland": {
            "northern ireland": ["8"],
        },
    },
    "Waste Reduction & Food": {
        "CTY": ["1b"],
    },
}

SCORE_EXCEPTIONS = {
    "Waste Reduction & Food": {
        "2": {
            "max_score": 1,
            "points_for_max": 2,
        }
    }
}

NEW_COUNCILS = [
    "Cumberland Council",
    "Westmorland and Furness Council",
    "North Yorkshire Council",
    "Somerset Council",
]


def number_and_part(number=None, number_part=None):
    if number_part is not None:
        return f"{number}{number_part}"
    return f"{number}"


def weighting_to_points(weighting="low", max_points=0):
    weighting = weighting.lower()
    if weighting == "unweighted" and max_points != 0:
        return max_points

    points = 1
    if weighting == "medium":
        points = 2
    elif weighting == "high":
        points = 3

    return points


def get_section_maxes(scoring):
    section_maxes = defaultdict(dict)
    section_weighted_maxes = defaultdict(dict)
    group_totals = defaultdict(int)
    q_maxes = defaultdict(int)
    q_weighted_maxes = defaultdict(int)
    negative_q = defaultdict(int)

    for section in Section.objects.all():
        q_section_maxes = {}
        q_section_weighted_maxes = {}
        q_section_negatives = {}
        for group in QuestionGroup.objects.all():
            questions = Question.objects.filter(
                section=section, questiongroup=group
            ).exclude(question_type="negative")

            maxes = (
                Option.objects.filter(
                    question__in=questions,
                    question__question_type__in=["yes_no", "select_one", "tiered"],
                )
                .select_related("question")
                .values("question__pk", "question__number", "question__number_part")
                .annotate(highest=Max("score"))
            )
            totals = (
                Option.objects.filter(question__in=questions)
                .exclude(
                    question__question_type__in=[
                        "yes_no",
                        "select_one",
                        "tiered",
                        "negative",
                    ]
                )
                .select_related("question")
                .values("question__pk", "question__number", "question__number_part")
                .annotate(highest=Sum("score"))
            )
            negatives = Question.objects.filter(
                section=section, questiongroup=group
            ).filter(question_type="negative")

            max_score = 0
            for m in maxes:
                q_section_maxes[
                    number_and_part(m["question__number"], m["question__number_part"])
                ] = m["highest"]
                max_score += m["highest"]

            for m in totals:
                q_number = number_and_part(
                    m["question__number"], m["question__number_part"]
                )
                if (
                    SCORE_EXCEPTIONS.get(section.title, None) is not None
                    and SCORE_EXCEPTIONS[section.title].get(q_number, None) is not None
                ):
                    m["highest"] = SCORE_EXCEPTIONS[section.title][q_number][
                        "max_score"
                    ]
                q_section_maxes[q_number] = m["highest"]
                max_score += m["highest"]

            # this stops lookup errors later on
            for q in negatives:
                q_section_negatives[q.number_and_part] = 1
                q_section_maxes[q.number_and_part] = 0

            weighted_max = 0
            for q in questions:
                q_max = weighting_to_points(q.weighting)
                if q.weighting == "unweighted":
                    q_max = q_section_maxes[q.number_and_part]
                q_section_weighted_maxes[q.number_and_part] = q_max
                weighted_max += q_max

            section_maxes[section.title][group.description] = max_score
            section_weighted_maxes[section.title][group.description] = weighted_max
            group_totals[group.description] += max_score
            q_weighted_maxes[section.title] = deepcopy(q_section_weighted_maxes)
            q_maxes[section.title] = deepcopy(q_section_maxes)
            negative_q[section.title] = deepcopy(q_section_negatives)

    scoring["section_maxes"] = section_maxes
    scoring["group_maxes"] = group_totals
    scoring["q_maxes"] = q_maxes
    scoring["section_weighted_maxes"] = section_weighted_maxes
    scoring["q_section_weighted_maxes"] = q_weighted_maxes
    scoring["negative_q"] = negative_q


def q_is_exception(q, section, group, country, council):
    all_exceptions = []
    try:
        exceptions = EXCEPTIONS[section][group][country]
        all_exceptions = all_exceptions + exceptions
    except KeyError:
        pass

    try:
        exceptions = EXCEPTIONS[section][council.type]
        all_exceptions = all_exceptions + exceptions
    except KeyError:
        pass

    try:
        exceptions = EXCEPTIONS[section][council.name]
        all_exceptions = all_exceptions + exceptions
    except KeyError:
        pass

    if q in all_exceptions:
        return True
    return False


def get_maxes_for_council(scoring, group, country, council):
    maxes = deepcopy(scoring["section_maxes"])
    weighted_maxes = deepcopy(scoring["section_weighted_maxes"])
    for section in maxes.keys():
        all_exceptions = []
        try:
            exceptions = EXCEPTIONS[section][group][country]
            all_exceptions = all_exceptions + exceptions
        except KeyError:
            pass

        try:
            exceptions = EXCEPTIONS[section][council.type]
            all_exceptions = all_exceptions + exceptions
        except KeyError:
            pass

        try:
            exceptions = EXCEPTIONS[section][council.name]
            all_exceptions = all_exceptions + exceptions
        except KeyError:
            pass

        for q in all_exceptions:
            maxes[section][group] -= scoring["q_maxes"][section][q]
            weighted_maxes[section][group] -= scoring["q_section_weighted_maxes"][
                section
            ][q]

    return maxes, weighted_maxes


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
    if weighting == "unweighted":
        return score

    percentage = score / max_score

    return percentage * weighting_to_points(weighting)


def get_section_scores(scoring):
    raw_scores, weighted = get_blank_section_scores()

    for section in Section.objects.all():
        options = (
            Response.objects.filter(
                response_type__type="Audit",
                question__section=section,
                authority__do_not_mark=False,
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

        scores = (
            options.select_related("questions")
            .annotate(score=Sum("score"))
            .values(
                "points",
                "score",
                "authority__name",
                "question__number",
                "question__number_part",
                "question__weighting",
            )
        )

        for score in scores:
            # skip qs in sections that are not for that council
            if weighted[score["authority__name"]].get(section.title, None) is None:
                continue

            if score["authority__name"] in NEW_COUNCILS:
                score["score"] = 0
                score["points"] = 0

            q = number_and_part(
                score["question__number"], score["question__number_part"]
            )
            q_max = scoring["q_maxes"][section.title][q]

            if q_is_exception(
                q,
                section.title,
                scoring["council_groups"][score["authority__name"]],
                scoring["council_countries"][score["authority__name"]],
                scoring["councils"][score["authority__name"]],
            ):
                print(f"exception: {q}")
                continue

            if score["score"] is None:
                print(
                    "score is None:",
                    score["authority__name"],
                    section.title,
                    q,
                    score["score"],
                    q_max,
                )
                continue
            if scoring["negative_q"][section.title].get(q, None) is None and (
                q_max is None or q_max == 0
            ):
                print(
                    "Max score is None or 0:",
                    score["authority__name"],
                    section.title,
                    q,
                    score["score"],
                    q_max,
                )
                continue

            q_score = score["score"]
            if scoring["negative_q"][section.title].get(q, None) is not None:
                if score["points"] is not None:
                    q_score = score["points"]
                else:
                    q_score = 0
            if (
                SCORE_EXCEPTIONS.get(section.title, None) is not None
                and SCORE_EXCEPTIONS[section.title].get(q, None) is not None
            ):
                if q_score >= SCORE_EXCEPTIONS[section.title][q]["points_for_max"]:
                    q_score = SCORE_EXCEPTIONS[section.title][q]["max_score"]
                else:
                    q_score = 0

            raw_scores[score["authority__name"]][section.title] += q_score

            if scoring["negative_q"][section.title].get(q, None) is None:
                weighted_score = get_weighted_question_score(
                    q_score, q_max, score["question__weighting"]
                )
            else:
                weighted_score = q_score
            weighted[score["authority__name"]][section.title] += weighted_score

    scoring["raw_scores"] = raw_scores
    scoring["weighted_scores"] = weighted


def calculate_council_totals(scoring):
    section_totals = defaultdict(dict)
    totals = {}
    scoring["council_maxes"] = {}

    for council, raw in scoring["raw_scores"].items():
        total = 0
        weighted_total = 0
        council_group = scoring["council_groups"][council]

        council_max, council_weighted_max = get_maxes_for_council(
            scoring,
            scoring["council_groups"][council],
            scoring["council_countries"][council],
            scoring["councils"][council],
        )
        scoring["council_maxes"][council] = {
            "raw": deepcopy(council_max),
            "weighted": deepcopy(council_weighted_max),
        }

        for section, score in raw.items():
            total += score

            if score > 0 and council_max[section][council_group] == 0:
                raise ZeroDivisionError(
                    f"Division by zero when calculating percentage score for {council}, {section}, {council_group}"
                )
            elif score == 0 and council_max[section][council_group] == 0:
                percentage_score = 0
                weighted_score = 0
                unweighted_percentage = 0
            else:
                percentage_score = score / council_max[section][council_group]

                weighted_score = (
                    scoring["weighted_scores"][council][section]
                    / council_weighted_max[section][council_group]
                ) * SECTION_WEIGHTINGS[section][council_group]
                weighted_score = round(weighted_score, 2)

                unweighted_percentage = (
                    scoring["weighted_scores"][council][section]
                    / council_weighted_max[section][council_group]
                )

            section_totals[council][section] = {
                "raw": score,
                "raw_percent": round(percentage_score, 2),
                "raw_weighted": round(scoring["weighted_scores"][council][section], 2),
                "unweighted_percentage": round(unweighted_percentage, 2),
                "weighted": weighted_score,
            }

            weighted_total += weighted_score

        totals[council] = {
            "raw_total": total,
            "percent_total": round(total / scoring["group_maxes"][council_group], 2),
            "weighted_total": round(weighted_total, 2),
        }

    scoring["council_totals"] = totals
    scoring["section_totals"] = section_totals


def get_scoring_object():
    scoring = {}

    council_gss_map, groups, countries, types, control = PublicAuthority.maps()
    scoring["council_gss_map"] = council_gss_map
    scoring["council_groups"] = groups
    scoring["council_countries"] = countries
    scoring["council_type"] = types
    scoring["council_control"] = control
    scoring["councils"] = {}
    for council in PublicAuthority.objects.all():
        scoring["councils"][council.name] = council

    get_section_maxes(scoring)
    get_section_scores(scoring)
    calculate_council_totals(scoring)

    return scoring


def get_duplicate_responses(response_type="Audit"):
    responses = (
        Response.objects.filter(
            response_type__type=response_type,
        )
        .values("question_id", "authority_id")
        .annotate(answer_count=Count("id"))
        .filter(answer_count__gte=2)
    )

    return responses


def get_exact_duplicates(duplicates, response_type="Audit"):
    rt = ResponseType.objects.get(type="Audit")

    potentials = {}
    for d in duplicates:
        rs = Response.objects.filter(
            question_id=d["question_id"],
            authority_id=d["authority_id"],
            response_type=rt,
        ).select_related("question", "authority")

        for r in rs:
            if potentials.get(r.authority.name, None) is None:
                potentials[r.authority.name] = {}

            if (
                potentials[r.authority.name].get(r.question.number_and_part, None)
                is None
            ):
                potentials[r.authority.name][r.question.number_and_part] = []

            potentials[r.authority.name][r.question.number_and_part].append(r)

    dupes = []
    for authority, questions in potentials.items():
        for question, responses in questions.items():
            diff = False
            first = responses[0]
            first_multi = sorted([o.pk for o in first.multi_option.all()])
            for response in responses:
                for prop in [
                    "evidence",
                    "public_notes",
                    "page_number",
                    "private_notes",
                    "agree_with_response",
                    "foi_answer_in_ror",
                ]:
                    if getattr(response, prop) != getattr(first, prop):
                        diff = True

                if response.option is None and first.option is not None:
                    diff = True
                elif response.option is not None and first.option is None:
                    diff = True
                elif (
                    response.option is not None
                    and first.option is not None
                    and response.option.id != first.option.id
                ):
                    diff = True

                multi = sorted([o.pk for o in response.multi_option.all()])
                if multi != first_multi:
                    diff = True

            if not diff:
                dupes.append(responses[1:])

    return dupes


def get_response_data(
    response, include_private=False, include_name=True, process_links=False
):
    score = 0
    answer = ""

    if response.multi_count > 0:
        descs = []
        for opt in response.multi_option.all():
            descs.append(opt.description)
            score += opt.score
        answer = ",".join(descs)
    elif response.option is not None:
        score = response.option.score
        answer = response.option.description
    else:
        score = "-"

    section = response.question.section
    q = response.question.number_and_part
    if (
        SCORE_EXCEPTIONS.get(section.title, None) is not None
        and SCORE_EXCEPTIONS[section.title].get(q, None) is not None
    ):
        if score >= SCORE_EXCEPTIONS[section.title][q]["points_for_max"]:
            score = SCORE_EXCEPTIONS[section.title][q]["max_score"]
        else:
            score = 0

    if response.question.question_type == "negative":
        score = response.points

    links = response.public_notes
    if process_links:
        links = "\n".join(response.evidence_links)

    if include_name:
        data = [response.authority.name]
    else:
        data = []
    data += [
        answer,
        score,
        links,
        response.page_number,
        response.evidence,
    ]

    if include_private:
        data.append(response.private_notes)

    return data


def get_all_question_data(scoring, response_type="Audit"):
    rt = ResponseType.objects.get(type=response_type)
    responses = (
        Response.objects.filter(response_type=rt)
        .annotate(multi_count=Count("multi_option__pk"))
        .order_by(
            "authority__name",
            "question__section__title",
            "question__number",
            "question__number_part",
        )
        .select_related("question", "question__section", "authority")
    )

    answers = [
        [
            "council name",
            "local-authority-type-code",
            "local-authority-gss-code",
            "section",
            "question-number",
            "question-weighting",
            "max_score",
            "answer",
            "score",
            "evidence",
            "page_number",
            "public_notes",
            "weighted_score",
            "max_weighted_score",
            "negatively_marked",
        ]
    ]
    for response in responses:
        q_data = get_response_data(response, include_name=False, process_links=True)

        section = response.question.section.title
        q_number = response.question.number_and_part
        max_score = scoring["q_maxes"][section][q_number]

        data = [
            response.authority.name,
            response.authority.type,
            response.authority.unique_id,
            response.question.section.title,
            response.question.number_and_part,
            response.question.weighting,
            max_score,
            *q_data,
        ]

        if response.question.question_type != "negative":
            negative = "No"
            max_weighted = scoring["q_section_weighted_maxes"][section][q_number]
            if q_data[1] == "-":
                weighted_score = ("-",)
            else:
                weighted_score = get_weighted_question_score(
                    q_data[1], max_score, response.question.weighting
                )
                weighted_score = round(weighted_score, 2)
        else:
            negative = "Yes"
            max_weighted = 0
            weighted_score = q_data[1]

        data += [weighted_score, max_weighted, negative]

        answers.append(data)

    return answers
