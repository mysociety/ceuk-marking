## The scoring process

At the moment this is written with the CEUK Council Action Scorecards in
mind but is reasonably configurable so should work for anything else.

### Overview

The basic structure of the scoring is that for each question there are a
possible set of responses which can have points assigned to them. Scores
for each section and then summed up, and then the section totals are
used to calculate an overall score, which is expressed as both a total
score and a percentage of the total.

It can probably be as simple as that however there are a number of ways
to make it more complicated.

There are various configuration options that are stored in the database
as JSON in the SessionConfig model. At the moment you can change these
by adding them in the django admin.

### Question Weighting

All questions have a raw value and a weighted value. The raw value is a
plain points score whereas the weighted score is one of High, Medium or
Low which correspond to 3, 2 and 1 points. The final weighted score for
a question is then


```
    ( question score / question max score ) * weighted points
```

A question can be unweighted in which case the weighted score is just the
score.

### Section Scores

The following scores are available for a section:

* raw - the total raw marks scored
* raw_percent - the percentage of the total raw marks available scored
* raw_weighted - the total weighted marks scored
* unweighted_percentage - the percentage of the total weighted marks
    scored
* weighted percentage - the above with the section weighting applied

Section maximums are always calculated per council as there are various
exceptions detail below which means not all questions apply to all
councils, even within a question grouping.

### Section Weighting

Each section has a weighting which controls how much of the final mark
it contributes. This is controlled by the `score_weightings` session
config. You assign a weighting for each section and within each section
for each question grouping. The weightings are expressed as a decimal
percentage and the weightings across all sections for each question
group should total to 1. As an example:

```json
{
    "Transport": {
        "County": 0.4,
        "District": 0.35
    },
    "Governance": {
        "County": 0.1,
        "District": 0.20
    },
    "Collaboration": {
        "County": 0.5,
        "District": 0.45
    }
}

```

The final weighted section score is then:

```
    ( weighted_score / weighted_total ) * section_weighting
```

### Overall Score

Several overall scores are calculated:

* raw total - total number of unweighted points scored
* precentage total - the above as a percentage of total points available
* weighted total - the sum of the weighted section scores

It is the latter that is used on the Scorecards website to show the
overall score of a council.

### Exceptions

There are a range of exceptions that can be used to handle questions
that are not universally applicable within a question group.

Exceptions are always a list of questions where the scores for those
should not be included in either the total for a section or the maximum
total.

These are also stored in the SessionConfig model in the `exceptions`
key. An example of the `exceptions` key is:

```json
{
    "Transport": {
        "County": {
            "scotland": ["6", "8b"],
        },
        "CTY": ["1b"]
        "Greater London Authority": ["6"]
    },
    "Governance": {
        "District": {
            "wales": ["4"]
        }
    },
    "answer_exceptions": {
        "Transport": [
            {
                "question_number": 2,
                "answer": "Council runs own school buses",
                "ignore": ["2", "3"]
            }
        ]
    }
}

```

#### Per Country

This allows questions to be exluded for councils from a particular
country within a section and question group.

In the example above this will exclude question 4 for Welsh councils in
the District question group in the Governance section. Similarly
questions 6 and 8b for scottish councils in the County group in
Transport.

#### Per Council type

This allows questions to be excluded for councils of a particular type
within a section.

In the example above councils with a type of `CTY` will have question 1b
excluded in the Transport section.

#### Per Council

This allows questions to be excluded for individual councils within a
section.

In the example above the Greater London Authority will have question 6
excluded in the Transport section.

#### Per Answer

This allows questions to be excluded based on the answer to a question
within a section.

The example above will exclude Transport questions 2 and 3 for all councils
that have "Council runs own school buses" as the answer to question 2.


