import pickle

from django.conf import settings
from django.utils.text import slugify

from crowdsourcer.models import (
    Assigned,
    MarkingSession,
    PublicAuthority,
    Question,
    ResponseType,
)


def get_assignment_progress_cache_name(name):
    name = slugify(name)
    file = settings.BASE_DIR / "data" / f"assignment_progress_{name}.pkl"

    return file


def get_cached_assignment_progress(name):
    file = get_assignment_progress_cache_name(name)

    progress = None
    if file.exists():
        with open(file, "rb") as fp:
            progress = pickle.load(fp)

    return progress


def save_cached_assignment_progress(name, progress):
    file = get_assignment_progress_cache_name(name)
    with open(file, "wb") as fp:
        pickle.dump(progress, fp)


def get_assignment_progress(assignments, marking_session, stage):
    current_session = MarkingSession.objects.get(label=marking_session)

    assignments = assignments.distinct(
        "user_id", "section_id", "response_type_id"
    ).select_related("section", "response_type")

    types = Question.VOLUNTEER_TYPES
    if stage == "Audit":
        types = ["volunteer", "national_volunteer", "foi"]

    first_mark = ResponseType.objects.get(type="First Mark")

    progress = []
    question_cache = {}
    for assignment in assignments:
        assignment_user = assignment.user
        if hasattr(assignment_user, "marker"):
            stage = assignment_user.marker.response_type
        else:
            stage = first_mark

        if question_cache.get(assignment.section_id, None) is not None:
            question_list = question_cache[assignment.section_id]
        else:
            questions = Question.objects.filter(
                section=assignment.section, how_marked__in=types
            )
            question_list = list(questions.values_list("id", flat=True))
            question_cache[assignment.section_id] = question_list

        total = 0
        complete = 0
        started = 0

        if assignment.section is not None:
            args = [
                question_list,
                assignment.section.title,
                assignment.user,
                current_session,
            ]
            if assignment.authority_id is not None:
                authorities = Assigned.objects.filter(
                    active=True,
                    user=assignment.user_id,
                    section=assignment.section_id,
                    response_type=stage,
                ).values_list("authority_id", flat=True)
                args.append(authorities)

            # we pass the question list but we want to ignore it because there could be different types of council
            # included in assignments which throws the count off
            response_counts = PublicAuthority.response_counts(
                *args,
                question_types=types,
                response_type=assignment.response_type,
                ignore_question_list=True,
            ).distinct()

            for count in response_counts:
                total += 1
                if count.num_responses is not None and count.num_responses > 0:
                    started += 1
                if count.num_responses == count.num_questions:
                    complete += 1

        if assignment.response_type is None:
            section_link = "home"
        elif assignment.response_type.type == "First Mark":
            section_link = "section_authorities"
        elif assignment.response_type.type == "Right of Reply":
            section_link = "authority_ror_authorities"
        elif assignment.response_type.type == "Audit":
            section_link = "audit_section_authorities"

        progress.append(
            {
                "assignment": assignment,
                "complete": complete,
                "started": started,
                "total": total,
                "section_link": section_link,
            }
        )

    return progress
