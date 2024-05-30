# Managing an instance

## Basic concepts

An instance can cope with multiple question sets. These are called
Marking Sessions. Within a Marking Session are Sections which split the
questions up into logical groups. You need at least one Section.

By default there are three Response Types, which are the stages of
marking: First Mark, Right of Reply and Audit. A Marking Session will
have a current response type.

You will also need at least one Question Group which is used to connect
Authories with questions. QuestionGroups belong to at least one Marking
Session.

Questions have Options which are the possible responses allowed.

When a user answers a question a Response is created that is linked to
the Question and the Authority.

Users have a Marker which controls which stage they are marking. For the
Right of Reply the Marker can also assign a User to an Authority which
will mean they can see all responses for that Authority.

Finally, Users are Assigned to Sections and Authoriries for a Marking
Session. This controls which questions they see when the log in and is
used for the First Mark and Audit stages.

## Initial Setup

The first thing you need to do is to create a Marking Session and
Sections. There is a `set_up_session` management command that will do
this for you:

```
./manage.py set_up_session --session "Session Name" --sections
sections.csv
```

`sections.csv` should contain a single column, "Title" with one section
name per row and be located in `data/`.

You will need to create a Question Group in the django admin and
associate it with the Marking Session you created.

Finally in the admin you will need to mark the session as active.

## Importing Questions

There is an `import_questions` management command for importing
questions. It takes questions from an excel file, the format of which is
documented in [DATA.md](https://github.com/mysociety/ceuk-marking/blob/main/DATA.md).

## Setting up Authorities

This almost certainly will require a custom management command. There
are examples for creating UK councils and UK MPs already.

## Setting up Volunteers

The front end has a bulk upload page for volunteers. This gets data from
an excel sheet, again documented in [DATA.md](https://github.com/mysociety/ceuk-marking/blob/main/DATA.md). It will create users and
assignments. You can set the stage and the number of assignments per
user. It will error if it cannot make assignments for all the users in
the sheet or for all the Authorities in the database. You can override
this and make what assignments it can by checking "Always Assign".

Once a volunteer has been created then you can edit their assignments
by clicking edit from the volunteers list.

You can change the stage they are assigned to by clicking their
Name/Email on the same screen.

Currently the only way to add a volunteer is in the django admin. You
will need to add a user and the associated Marker with the correct
Marking Session for them to show up on the volunteers page.

### Exporting marks

Once the process is complete the `export_marks` command will generate a
set of CSV files with the final marks.

### Mark weighting

The database only holds the per question marks. All generating of final
marks etc is done by the `export_marks` command.

The final marks use a weighted mark where the possible maximum score is
based on the weighting as follows:

 * low - 1 mark
 * medium - 2 marks
 * high - 3 marks

The score is then calculated thus:

    ( score / max score ) * weighted maximum

Some questions are negatively marked in which case no weighting is
applied. Likewise for unweighted questions.

Sections are also weighted when calculating the final total. The section
weightings are currenty hard coded into the scoring code. Section
weightings are dependent on the council group. Section weightings are
applied to the weighted section totals.

It is the weighted percentages that are displayed on the Scorecards
site.
