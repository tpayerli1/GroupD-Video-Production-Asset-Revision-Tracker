from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_home, name="dashboard_home"),
    path("dashboard/", views.dashboard_home, name="dashboard_home"),
    path("dashboard/batch/<int:batch_id>/", views.dashboard_batch_detail, name="dashboard_batch_detail"),
    path("dashboard/batch/<int:batch_id>/assign-project/", views.dashboard_batch_assign_project, name="dashboard_batch_assign_project"),
]

# API Stuff
urlpatterns += [
    path("api/batches/ensure/", views.api_batches_ensure, name="api_batches_ensure"),
    path("api/batches/<int:batch_id>/", views.api_batch_detail, name="api_batch_detail"),
    path("api/media_files/", views.api_media_files, name="api_media_files"),
    path("api/media/metadata/probe/", views.api_media_metadata_probe, name="api_media_metadata_probe"),
    # path("api/tags/suggest/", views.api_tags_suggest, name="api_tags_suggest"),
]
