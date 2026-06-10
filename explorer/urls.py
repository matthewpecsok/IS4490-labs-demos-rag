from django.urls import path

from . import views


app_name = "explorer"

urlpatterns = [
    path("", views.index, name="index"),
    path("search/", views.search, name="search"),
    path("assignment/", views.assignment, name="assignment"),
    path(
        "assignment/evaluate/",
        views.evaluate_assignment,
        name="evaluate_assignment",
    ),
]
