"""crowdsourcer URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from crowdsourcer.views import marking, progress, rightofreply

urlpatterns = [
    # admin/utility screens
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("status/", marking.StatusPage.as_view()),
    # home page
    path("", marking.OverviewView.as_view(), name="home"),
    # progess screens
    path("inactive/", progress.InactiveOverview.as_view(), name="inactive"),
    path(
        "authority_progress/",
        progress.AllAuthorityProgressView.as_view(),
        name="all_authority_progress",
    ),
    path(
        "authority_progress/<name>/",
        progress.AuthorityProgressView.as_view(),
        name="authority_progress",
    ),
    path(
        "section_progress/",
        progress.AllSectionProgressView.as_view(),
        name="all_section_progress",
    ),
    path(
        "section_progress/<section_title>/",
        progress.SectionProgressView.as_view(),
        name="section_progress",
    ),
    path(
        "volunteer_progress/<id>/",
        progress.VolunteerProgressView.as_view(),
        name="volunteer_progress",
    ),
    path(
        "authority_assignments/",
        progress.AuthorityAssignmentView.as_view(),
        name="authority_assignments",
    ),
    # marking screens
    path(
        "section/<section_title>/questions/",
        marking.SectionQuestionList.as_view(),
        name="section_questions",
    ),
    path(
        "section/<section_title>/authorities/",
        marking.SectionAuthorityList.as_view(),
        name="section_authorities",
    ),
    path(
        "section/<section_title>/question/<slug:number>/",
        marking.SectionQuestionAuthorityList.as_view(),
        name="section_question_authorities",
    ),
    path(
        "authorities/<name>/section/<section_title>/question/<number>/",
        marking.AuthorityQuestion.as_view(),
        name="authority_question",
    ),
    path(
        "authorities/<name>/section/<section_title>/questions/",
        marking.AuthoritySectionQuestions.as_view(),
        name="authority_question_edit",
    ),
    path(
        "authorities/<name>/section/<section_title>/question/<number>/answer/",
        marking.AuthorityQuestionAnswer.as_view(),
        name="authority_question_answer",
    ),
    path(
        "authorities/<name>/section/<section_title>/question/<number>/edit/",
        marking.AuthorityQuestionEdit.as_view(),
        name="authority_question_edit",
    ),
    path(
        "authorities/<name>/section/<section_title>/question/<number>/view/",
        marking.AuthorityQuestionView.as_view(),
        name="authority_question_view",
    ),
    # right of reply screens
    path(
        "authorities/<name>/ror/sections/",
        rightofreply.AuthorityRORSectionList.as_view(),
        name="authority_ror_sections",
    ),
    path(
        "authorities/<name>/ror/section/<section_title>/questions/",
        rightofreply.AuthorityRORSectionQuestions.as_view(),
        name="authority_ror",
    ),
    # right of reply progress
    path(
        "authority_ror_progress/<name>/",
        progress.AuthorityRoRProgressView.as_view(),
        name="authority_ror_progress",
    ),
]

if settings.DEBUG:  # pragma: no cover
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
