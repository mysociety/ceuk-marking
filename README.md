# CEUK scorecards marking tool

This is a tool for crowdsourcing data, initially designed for gathering
data about local authority climate actions for https://councilclimatescorecards.uk/

## Development install

You will need [Docker](https://docs.docker.com/desktop/) installed.

Clone the repository:

    git clone git@github.com:mysociety/ceuk-marking.git
    cd ceuk-marking

Create and edit a .env file using `.env-example` file and then
update `SECRET_KEY` and `MAPIT_API_KEY`. You can get the latter from https://mapit.mysociety.org/account/signup/

### Running Docker manually (recommended)

Start the Docker environment:

    docker-compose up

Docker-compose will automatically install dependencies and start the development web server at <https://localhost:8000> when the container is started.

(If Python complains about missing libraries, chances are the Python requirements have changed since your Docker image was last built. You can rebuild it with, eg: `docker-compose build web`.)

### Data import

If you’re running Docker manually (recommended) you will need to enter a Bash shell inside the container, in order to run any of the data import commands:

    docker-compose exec web bash

If you’re running Docker via Visual Studio Code, instead, you’ll want to run the commands via the built-in terminal.

You will likely want to create a Django superuser, by running this inside the container:

    script/createsuperuser

The superuser will be created with the details specified in the `DJANGO_SUPERUSER_*` environment variables. [Read more about how Docker handles environment variables](https://docs.docker.com/compose/envvars-precedence/).

Currently the `create_initial_data` management command relies on data
that is no longer freely available (see issue #128) but normally running
this would populate the list of councils and categories.

Then the `import_questions` management command will import the list of
questions and assign them to the relevant councils. The questions data
should be downloaded as an Excel sheet from the Google sheet populated
by CEUK.

Details on file strucures can be found in DATA.md

### Data structure

See the separate ARCHITECTURE.md file for full details on the underlying
architecture. For admin purposes the following should suffice.

As a brief overview of the operation volunteers are usually assigned to
mark the questions in a section for a set of councils. Councils can then
respond to the marking by agreeing or disagreeing with the mark, and
then a final set of volunteers can then audit the initial responses and
council feedback to provide a final mark. The audit volunteers are again
assigned a section and a set of councils within that section.

The set of questions displayed for a council in a section depends on the
council type to allow for not all councils having the same
responsibilities and hence not all questions applying to all councils.

Questions also have a type so not all questions are visible to
volunteers - e.g. questions that use data from national statistics.
These are instead filled in by management commands.

In more detail Questions are split into Sections, and are also part of
QuestionGroups. The QuestionGroup controls which councils the question
applies to.

Councils are also assigned a QuestionGroup which again controls which
questions apply to a Council.

There are Responses which are associated with a ResponseType such as
Audit.

Volunteers are assigned to a council and a section with Assignements.
This can be done in bulk using management commands or in the django
admin. An assigment has a ResponseType as well as a Section and Council.

There is also a Marker object associated with a Volunteer which
determines what stage they are marking (e.g. Audit)

### Setting up a volunteer in the django admin

In the django admin add a user. Then create a Marker associated with
that user and assign a ResponseType.

For each council you want to user to mark you can then create an
Assignment setting the user, section, council and response type.

If you create an assignment with only a user, section and response type
the user will be assigned to all councils in that section.

The full set of steps are:

 * Create the user
 * Create a Marker for the user and set the Response Type to the
     relevant one. You can ignore the Authority.
 * Create an Assignment and set the User, Section, Authority and
     Response Type. You can ignore the Question.

Once the user has been set up they can set a password by visiting the
django password reset page.

For initial volunteer setup there is an `import_volunteers` management
command. This will take a list of volunteers and assign each of them a
set number of councils in the section they are assigned until the
councils have run out. If there are more volunteers than assignments
then some volunteers will not be assigned. The number of councils to
assign is currently hard coded in the script.

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

### Running the tests

First start the Docker environment:

    docker-compose up

Then run the tests from inside or outside the docker container:

    script/test

The first time you run `script/test`, it will ask whether you want the tests to run natively or inside the docker container. Type `docker` to run them inside the docker container. Your preference will be saved to `.env` for future runs.
