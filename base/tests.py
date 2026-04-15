import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import Batch, Customer, Media, MediaMetadata, Project, Tag


class DashboardSearchTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Lake Campaign", location="Chicago")
        self.customer = Customer.objects.create(
            project=self.project,
            company_name="Lake House Studio",
            first_name="Avery",
            last_name="Stone",
            email="avery@example.com",
        )
        self.batch = Batch.objects.create()
        self.media = Media.objects.create(
            batch=self.batch,
            project=self.project,
            file_name="lake-broll.mp4",
            file_path="C:\\media\\lake-broll.mp4",
        )
        self.tag = Tag.objects.create(name="shoreline")
        self.media.tags.add(self.tag)
        MediaMetadata.objects.create(
            media=self.media,
            file_type="video",
            codec="prores",
            color_space="bt709",
        )

    def test_dashboard_search_defaults_to_all_scopes(self):
        response = self.client.post(reverse("dashboard_home"), {"q": "lake"})

        self.assertEqual(response.status_code, 200)
        search_results = response.context["search_results"]

        self.assertEqual(len(search_results["projects"]), 1)
        self.assertEqual(len(search_results["clients"]), 1)
        self.assertEqual(len(search_results["metadata"]), 1)
        self.assertGreaterEqual(search_results["total"], 3)

    def test_dashboard_search_can_limit_to_tags_only(self):
        response = self.client.post(
            reverse("dashboard_home"),
            {"q": "shore", "tags": "1"},
        )

        self.assertEqual(response.status_code, 200)
        search_results = response.context["search_results"]

        self.assertEqual(len(search_results["tags"]), 1)
        self.assertEqual(len(search_results["projects"]), 0)
        self.assertEqual(len(search_results["clients"]), 0)
        self.assertEqual(len(search_results["metadata"]), 0)


class MediaMetadataProbeApiTests(TestCase):
    def setUp(self):
        self.batch = Batch.objects.create()
        self.media = Media.objects.create(
            batch=self.batch,
            file_name="clip.mov",
            file_path="placeholder",
        )

    @patch("base.views.probe_media_file")
    def test_probe_endpoint_upserts_metadata_for_existing_media(self, mock_probe_media_file):
        with tempfile.NamedTemporaryFile(suffix=".mov") as temp_file:
            self.media.file_path = temp_file.name
            self.media.save(update_fields=["file_path"])

            mock_probe_media_file.return_value = {
                "file_type": "video",
                "file_size": 2048,
                "imported_at": None,
                "hdr": True,
                "frame_rate": 23.976,
                "codec": "prores",
                "duration": timedelta(seconds=12),
                "width": 1920,
                "height": 1080,
                "aspect_ratio": "16:9",
                "color_space": "bt2020nc",
                "bit_rate": 1200000,
            }

            response = self.client.post(
                reverse("api_media_metadata_probe"),
                data={"file_path": temp_file.name},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["created"], 1)
        self.assertEqual(body["errors"], 0)

        metadata = MediaMetadata.objects.get(media=self.media)
        self.assertEqual(metadata.file_type, "video")
        self.assertEqual(metadata.codec, "prores")
        self.assertEqual(metadata.width, 1920)
        self.assertEqual(metadata.height, 1080)

    def test_probe_endpoint_reports_missing_media_records(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3") as temp_file:
            response = self.client.post(
                reverse("api_media_metadata_probe"),
                data={"file_path": temp_file.name},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["missing"], 1)
        self.assertEqual(body["processed"][0]["status"], "missing_media")
