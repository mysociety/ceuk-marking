from collections import defaultdict

import pandas as pd

from crowdsourcer.models import Assigned, PublicAuthority, Section


def check_bulk_assignments(df, rt, ms, num_assignments, always_assign=False):
    errors = []

    section_names = pd.unique(df["Assigned Section"])
    for section in section_names:
        try:
            Section.objects.get(title=section, marking_session=ms)
        except Section.DoesNotExist:
            errors.append(f"Cannot assign to section '{section}', it does not exist.")

    # need to correct this before we can do any further processing because otherwise
    # the assigment maths will be off
    if errors:
        return errors

    if not always_assign:
        max_assignments = {}
        sections = Section.objects.filter(marking_session=ms)
        for section in sections:
            assigned = Assigned.objects.filter(
                marking_session=ms,
                section=section,
                response_type=rt,
            ).values("authority")
            max_assignments[section.title] = (
                PublicAuthority.objects.exclude(id__in=assigned)
                .filter(questiongroup__marking_session=ms)
                .count()
            )

        section_assignments = defaultdict(list)
        users_assigned = Assigned.objects.filter(
            marking_session=ms, response_type=rt
        ).values_list("user__email", flat=True)
        for _, row in df.iterrows():
            if row["Email"] in users_assigned:
                continue

            section_assignments[row["Assigned Section"]].append(
                {
                    "first_name": row["First Name"],
                    "last_name": row["Last Name"],
                    "email": row["Email"],
                }
            )

        if not section_assignments.keys():
            errors.append(
                "No assignments will be made, all volunteers must already have assignments."
            )

        for section, volunteers in section_assignments.items():
            required_volunteer_assignments = len(volunteers) * num_assignments

            if required_volunteer_assignments > max_assignments[section]:
                assignments_required = max_assignments[section] / len(volunteers)
                errors.append(
                    f"Too many volunteers for {section}, not all volunteers will get assignments. Need {assignments_required} per volunteer."
                )

            num_assignments_required = max_assignments[section] / num_assignments
            if num_assignments_required > len(volunteers):
                volunteers_required = (
                    max_assignments[section] - len(volunteers)
                ) / num_assignments
                errors.append(
                    f"Not enough volunteers for {section}, not all entities will have volunteers - {volunteers_required} more volunteers needed."
                )

    return errors
