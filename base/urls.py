from django.urls import path
from . import views

urlpatterns = [
]

# API Stuff
urlpatterns += [
    path("api/batches/ensure/", views.api_batches_ensure, name="api_batches_ensure"),
    path("api/batches/<int:batch_id>/", views.api_batch_detail, name="api_batch_detail"),
    path("api/media_files/", views.api_media_files, name="api_media_files"),
    # path("api/tags/suggest/", views.api_tags_suggest, name="api_tags_suggest"),
]
