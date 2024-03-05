### System architecture

All the code is in the crowdsourcer app.

Currently the app is structured round the way the CEUK Scorecards
process works.

In general there is one view for each stage of the process
   * first mark
   * right of reply
   * audit

plus one for the stats modules and a base view for code that is common
across views.

In general there is a base view for each page and then a class that
extends that for each response stage.

For each stage there is a page with a User's assignments grouped by
section, one for the specific councils within that section and then a
question page.

A user can answer the same question multiple times and it will update
the data. Previous responses are stored using HistoricalRecords from the
simple_history package which creates a `crowdsourcer_historicalresponse`
table.

Superusers have access to view all stages at all times as well as access
to the stats menu which provides various summary data.

The important models are:

 * PublicAuthority - local authority details
 * Section - question sections
 * Question - Question details
 * Option - Possible answers for a Question
 * Response - Answer for a question
 * Assigned - Volunteer assignments
 * Marker - Extra information about a user

Other important modules are:

 * scoring - contains the code to generate scores
