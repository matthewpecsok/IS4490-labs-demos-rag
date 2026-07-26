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
    path("vectordb/", views.vectordb, name="vectordb"),
    path("vectordb/build/", views.build_vector_index, name="vectordb_build"),
    path("vectordb/search/", views.vectordb_search, name="vectordb_search"),
    path("classify/", views.classify, name="classify"),
    path("classify/run/", views.classify_candidate, name="classify_candidate"),
    path("classify/query/", views.query_classifications, name="query_classifications"),
    path("experiment/", views.experiment, name="experiment"),
    path(
        "experiment/run-cell/",
        views.experiment_run_cell,
        name="experiment_run_cell",
    ),
]
