### questions.xlsx

This file contains definitions of the questions. It should have one tab
per section with all the questions for that section one per row.

The columns are:

 * question_no - either a number of number followed by letter for multi
     part e,g 1a
 * topic
 * question - question text
 * criteria
 * clarifications
 * how_marked - one of Volunteer Research, National Data, FOI
 * weighting - unweighted, low, medium, high
 * district - Yes if applies to district councils, blank otherwise
 * single_tier
 * county
 * northern_ireland
 * question_type - how the question will be answers (see below)
 * points - number of points question is worth before weighting
 * option_[1-n] - possible option answers for multuple choice questions

#### Question types

 * Y/N - true/false question
 * blank - true/false
 * Tick all that apply - multi select question
 * Tiered answer/multiple choice - multiple choice question

### volunteers.xlsx

This is for bulk assigning volunteers to the first mark. The columns
used are:

 * First name
 * Last name
 * Email
 * Council Area - volunteers own council which they will not be assigned
 * Type of Volunteering - used to determine how many councils to assign
 * Assigned Section - section to assign user to

You can have multiple tabs for different stages but the name of the used
tab is hard coded in the script.
