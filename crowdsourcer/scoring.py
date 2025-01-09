from collections import defaultdict
from copy import deepcopy
from functools import cache

from django.db.models import Count, Max, OuterRef, Q, Subquery, Sum

from crowdsourcer.models import (
    MarkingSession,
    Option,
    PublicAuthority,
    Question,
    QuestionGroup,
    Response,
    ResponseType,
    Section,
    SessionConfig,
)

NEW_COUNCILS = [
    "Cumberland Council",
    "Westmorland and Furness Council",
    "North Yorkshire Council",
    "Somerset Council",
]


def get_scoring_config(marking_session, name):
    conf = SessionConfig.get_config(marking_session, name)
    if conf is None:
        conf = {}

    return conf


@cache
def get_exceptions(marking_session):
    exceptions = get_scoring_config(marking_session, "exceptions")
    exceptions = update_with_housing_exceptions(exceptions, marking_session)
    return exceptions


@cache
def get_score_exceptions(marking_session):
    return get_scoring_config(marking_session, "score_exceptions")


@cache
def get_weightings(marking_session):
    return get_scoring_config(marking_session, "score_weightings")


def clear_exception_cache():
    get_exceptions.cache_clear()
    get_score_exceptions.cache_clear()
    get_weightings.cache_clear()


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


def get_section_maxes(scoring, session):
    section_maxes = defaultdict(dict)
    section_weighted_maxes = defaultdict(dict)
    group_totals = defaultdict(int)
    q_maxes = defaultdict(int)
    q_weighted_maxes = defaultdict(int)
    negative_q = defaultdict(int)
    score_exceptions = get_score_exceptions(session)

    for section in Section.objects.filter(marking_session=session):
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
                    score_exceptions.get(section.title, None) is not None
                    and score_exceptions[section.title].get(q_number, None) is not None
                ):
                    m["highest"] = score_exceptions[section.title][q_number][
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


def q_is_exception(q, section, group, country, council, session):
    config_exceptions = get_exceptions(session)
    all_exceptions = []
    try:
        exceptions = config_exceptions[section][group][country]
        all_exceptions = all_exceptions + exceptions
    except KeyError:
        pass

    try:
        exceptions = config_exceptions[section][council.type]
        all_exceptions = all_exceptions + exceptions
    except KeyError:
        pass

    try:
        exceptions = config_exceptions[section][council.name]
        all_exceptions = all_exceptions + exceptions
    except KeyError:
        pass

    if q in all_exceptions:
        return True
    return False


def update_with_housing_exceptions(exceptions, session):
    rt = ResponseType.objects.get(type="Audit")
    try:
        q = Question.objects.get(
            number=3,
            section__title="Buildings & Heating",
            section__marking_session=session,
        )
    except Question.DoesNotExist:
        return exceptions

    try:
        o = Option.objects.get(
            question=q,
            description="Council does not own or manage any council homes",
        )
    except Option.DoesNotExist:
        return exceptions

    housing_responses = Response.objects.filter(
        question=q,
        option=o,
        response_type=rt,
    )

    for e in housing_responses:
        exceptions["Buildings & Heating"][e.authority.name] = ["3", "4"]

    return exceptions


def get_maxes_for_council(scoring, group, country, council, session):
    maxes = deepcopy(scoring["section_maxes"])
    weighted_maxes = deepcopy(scoring["section_weighted_maxes"])
    config_exceptions = get_exceptions(session)
    for section in maxes.keys():
        all_exceptions = []
        try:
            exceptions = config_exceptions[section][group][country]
            all_exceptions = all_exceptions + exceptions
        except KeyError:
            pass

        try:
            exceptions = config_exceptions[section][council.type]
            all_exceptions = all_exceptions + exceptions
        except KeyError:
            pass

        try:
            exceptions = config_exceptions[section][council.name]
            all_exceptions = all_exceptions + exceptions
        except KeyError:
            pass

        for q in all_exceptions:
            try:
                maxes[section][group] -= scoring["q_maxes"][section][q]
                weighted_maxes[section][group] -= scoring["q_section_weighted_maxes"][
                    section
                ][q]
            except KeyError:
                print(f"no question found for exception {section}, {q}")

    return maxes, weighted_maxes


def get_blank_section_scores(session):
    raw_scores = defaultdict(dict)
    weighted = defaultdict(dict)

    non_ca_sections = {
        x: 0
        for x in Section.objects.exclude(title__contains="(CA)")
        .filter(marking_session=session)
        .values_list("title", flat=True)
    }
    ca_sections = {
        x: 0
        for x in Section.objects.filter(
            title__contains="(CA)", marking_session=session
        ).values_list("title", flat=True)
    }

    for council in PublicAuthority.objects.filter(
        marking_session=session,
        questiongroup__marking_session=session,
        do_not_mark=False,
    ).all():
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


def get_section_scores(scoring, session):
    raw_scores, weighted = get_blank_section_scores(session)

    score_exceptions = get_score_exceptions(session)

    for section in Section.objects.filter(marking_session=session):
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
                session,
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
                score_exceptions.get(section.title, None) is not None
                and score_exceptions[section.title].get(q, None) is not None
            ):
                if q_score >= score_exceptions[section.title][q]["points_for_max"]:
                    q_score = score_exceptions[section.title][q]["max_score"]
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


def get_section_weighting(section, council_group, session):
    section_weightings = get_weightings(session)

    if (
        section_weightings.get(section, None) is not None
        and section_weightings[section].get(council_group, None) is not None
    ):
        return section_weightings[section][council_group]

    print(f"No weighting for {section} and {council_group}")
    return 0


def calculate_council_totals(scoring, session):
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
            session,
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
                ) * get_section_weighting(section, council_group, session)
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

        percent_total = 0
        if scoring["group_maxes"][council_group] > 0:
            percent_total = round(total / scoring["group_maxes"][council_group], 2)
        totals[council] = {
            "raw_total": total,
            "percent_total": percent_total,
            "weighted_total": round(weighted_total, 2),
        }

    scoring["council_totals"] = totals
    scoring["section_totals"] = section_totals


def get_scoring_object(session):
    scoring = {}

    council_gss_map, groups, countries, types, control = PublicAuthority.maps()
    scoring["council_gss_map"] = council_gss_map
    scoring["council_groups"] = groups
    scoring["council_countries"] = countries
    scoring["council_type"] = types
    scoring["council_control"] = control
    scoring["councils"] = {}
    for council in PublicAuthority.objects.filter(
        marking_session=session, questiongroup__marking_session=session
    ):
        scoring["councils"][council.name] = council

    get_section_maxes(scoring, session)
    get_section_scores(scoring, session)
    calculate_council_totals(scoring, session)

    return scoring


def get_duplicate_responses(session, response_type="Audit"):
    responses = (
        Response.objects.filter(
            response_type__type=response_type,
            question__section__marking_session=session,
        )
        .values("question_id", "authority_id")
        .annotate(answer_count=Count("id"))
        .filter(answer_count__gte=2)
    )

    return responses


def get_exact_duplicates(duplicates, session, response_type="Audit"):
    rt = ResponseType.objects.get(type=response_type)

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
    response,
    include_private=False,
    include_name=True,
    process_links=False,
    marking_session=None,
):
    score = 0
    answer = ""

    if response.multi_count > 0:
        descs = []
        for opt in response.multi_option.all():
            descs.append(opt.description)
            score += opt.score
        answer = "|".join(descs)
    elif response.option is not None:
        score = response.option.score
        answer = response.option.description
    else:
        score = "-"

    section = response.question.section
    q = response.question.number_and_part
    exceptions = get_score_exceptions(marking_session)
    if (
        exceptions.get(section.title, None) is not None
        and exceptions[section.title].get(q, None) is not None
    ):
        if score >= exceptions[section.title][q]["points_for_max"]:
            score = exceptions[section.title][q]["max_score"]
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


def get_all_question_data(scoring, marking_session=None, response_type="Audit"):
    rt = ResponseType.objects.get(type=response_type)
    session = MarkingSession.objects.get(label=marking_session)
    responses = (
        Response.objects.filter(
            response_type=rt, question__section__marking_session=session
        )
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
        section = response.question.section.title
        q_number = response.question.number_and_part
        council = response.authority.name

        if response.authority.do_not_mark:
            continue

        if q_is_exception(
            q_number,
            section,
            scoring["council_groups"][council],
            scoring["council_countries"][council],
            scoring["councils"][council],
            session,
        ):
            continue

        q_data = get_response_data(response, include_name=False, process_links=True)

        try:
            max_score = scoring["q_maxes"][section][q_number]
        except (KeyError, TypeError):
            print(f"No max score found for {section}, {q_number}, setting to 0")
            max_score = 0

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
            try:
                max_weighted = scoring["q_section_weighted_maxes"][section][q_number]
            except (KeyError, TypeError):
                print(f"No section max weighted for {section}, {q_number}")
                max_weighted = 0

            if q_data[1] == "-":
                weighted_score = ("-",)
            else:
                if max_score > 0:
                    weighted_score = get_weighted_question_score(
                        q_data[1], max_score, response.question.weighting
                    )
                    weighted_score = round(weighted_score, 2)
                else:
                    weighted_score = 0
        else:
            negative = "Yes"
            max_weighted = 0
            weighted_score = q_data[1]

        data += [weighted_score, max_weighted, negative]

        answers.append(data)

    return answers
