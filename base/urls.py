from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_home, name="dashboard_home"),
    path("dashboard/", views.dashboard_home, name="dashboard_home"),
    path("tags/", views.dashboard_tags, name="tags"),
    path("dashboard/clients/", views.dashboard_clients, name="dashboard_clients"),
    path("dashboard/clients/<int:client_id>/", views.dashboard_client_detail, name="dashboard_client_detail"),
    path("dashboard/projects/", views.dashboard_projects, name="dashboard_projects"),
    path("dashboard/projects/<int:project_id>/", views.dashboard_project_detail, name="dashboard_project_detail"),
    path("dashboard/tags/", views.dashboard_tags, name="dashboard_tags"),
    path("dashboard/media/", views.dashboard_media, name="dashboard_media"),
    path("dashboard/media/<int:media_id>/", views.dashboard_media_detail, name="dashboard_media_detail"),
    path("dashboard/batch/<int:batch_id>/", views.dashboard_batch_detail, name="dashboard_batch_detail"),
    path("dashboard/batch/<int:batch_id>/assign-project/", views.dashboard_batch_assign_project, name="dashboard_batch_assign_project"),
]

# API Stuff
urlpatterns += [
    path("api/batches/ensure/", views.api_batches_ensure, name="api_batches_ensure"),
    path("api/batches/<int:batch_id>/", views.api_batch_detail, name="api_batch_detail"),
    path("api/media_files/", views.api_media_files, name="api_media_files"),
    path("api/media/metadata/probe/", views.api_media_metadata_probe, name="api_media_metadata_probe"),
    path("api/media/metadata/save/", views.api_media_metadata_save, name="api_media_metadata_save"),
    # path("api/tags/suggest/", views.api_tags_suggest, name="api_tags_suggest"),
]
