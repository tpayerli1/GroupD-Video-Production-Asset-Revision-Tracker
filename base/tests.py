import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Batch, Customer, Media, MediaMetadata, MediaTag, Project, ProjectUser, Tag


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

    def test_media_search_defaults_to_all_scopes(self):
        response = self.client.get(
            reverse("dashboard_media"),
            {"q": "lake", "projects": "1", "clients": "1", "tags": "1", "metadata": "1"},
        )

        self.assertEqual(response.status_code, 200)
        media_list = list(response.context["media_list"])

        self.assertEqual(len(media_list), 1)
        self.assertEqual(media_list[0], self.media)

    def test_media_search_can_limit_to_tags_only(self):
        response = self.client.get(
            reverse("dashboard_media"),
            {"q": "shore", "tags": "1"},
        )

        self.assertEqual(response.status_code, 200)
        media_list = list(response.context["media_list"])

        self.assertEqual(len(media_list), 1)
        self.assertEqual(media_list[0], self.media)

    def test_media_search_supports_multiple_space_separated_terms(self):
        response = self.client.get(
            reverse("dashboard_media"),
            {"q": "lake prores", "projects": "1", "clients": "1", "tags": "1", "metadata": "1"},
        )

        self.assertEqual(response.status_code, 200)
        media_list = list(response.context["media_list"])

        self.assertEqual(len(media_list), 1)
        self.assertEqual(media_list[0], self.media)

    def test_media_search_matches_any_space_separated_term(self):
        other_media = Media.objects.create(
            batch=self.batch,
            project=self.project,
            file_name="behind-scenes.jpg",
            file_path="C:\\media\\behind-scenes.jpg",
        )

        response = self.client.get(
            reverse("dashboard_media"),
            {"q": "jpg mp4", "projects": "1", "clients": "1", "tags": "1", "metadata": "1"},
        )

        self.assertEqual(response.status_code, 200)
        media_list = list(response.context["media_list"])

        self.assertEqual({item.id for item in media_list}, {self.media.id, other_media.id})

    def test_media_search_normalizes_dotted_extensions(self):
        other_media = Media.objects.create(
            batch=self.batch,
            project=self.project,
            file_name="behind-scenes.jpg",
            file_path="C:\\media\\behind-scenes.jpg",
        )

        response = self.client.get(
            reverse("dashboard_media"),
            {"q": ".jpg .mp4", "projects": "1", "clients": "1", "tags": "1", "metadata": "1"},
        )

        self.assertEqual(response.status_code, 200)
        media_list = list(response.context["media_list"])

        self.assertEqual({item.id for item in media_list}, {self.media.id, other_media.id})


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

    def test_metadata_save_endpoint_upserts_supplied_metadata(self):
        self.media.file_path = "C:\\media\\clip.mov"
        self.media.save(update_fields=["file_path"])

        response = self.client.post(
            reverse("api_media_metadata_save"),
            data={
                "file_path": self.media.file_path,
                "metadata": {
                    "file_type": "video",
                    "file_size": 4096,
                    "hdr": False,
                    "frame_rate": 29.97,
                    "codec": "h264",
                    "duration": 22.5,
                    "width": 3840,
                    "height": 2160,
                    "aspect_ratio": "16:9",
                    "color_space": "bt709",
                    "bit_rate": 55000000,
                },
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["created"], 1)
        self.assertEqual(body["errors"], 0)

        metadata = MediaMetadata.objects.get(media=self.media)
        self.assertEqual(metadata.file_type, "video")
        self.assertEqual(metadata.codec, "h264")
        self.assertEqual(metadata.width, 3840)
        self.assertEqual(metadata.height, 2160)
        self.assertEqual(int(metadata.bit_rate), 55000000)


class BatchAssignmentTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="editor", password="secret123")
        self.batch = Batch.objects.create()
        self.media = Media.objects.create(
            batch=self.batch,
            file_name="batch-clip.mov",
            file_path="C:\\media\\batch-clip.mov",
        )

    def test_assign_batch_to_existing_project(self):
        project = Project.objects.create(name="Existing Project")

        response = self.client.post(
            reverse("dashboard_batch_assign_project", args=[self.batch.id]),
            {"project_id": str(project.id)},
        )

        self.assertEqual(response.status_code, 302)

        self.media.refresh_from_db()
        self.assertEqual(self.media.project, project)
        self.assertRedirects(response, reverse("dashboard_home"))

    def test_create_project_and_client_together(self):
        response = self.client.post(
            reverse("dashboard_batch_assign_project", args=[self.batch.id]),
            {
                "new_project_name": "Fresh Project",
                "create_client": "1",
                "company_name": "North Shore Studio",
                "first_name": "Avery",
                "last_name": "Stone",
                "email": "avery@example.com",
                "phone": "555-0101",
            },
        )

        self.assertEqual(response.status_code, 302)

        project = Project.objects.get(name="Fresh Project")
        customer = Customer.objects.get(project=project)

        self.media.refresh_from_db()
        self.assertEqual(self.media.project, project)
        self.assertEqual(customer.company_name, "North Shore Studio")
        self.assertEqual(customer.first_name, "Avery")
        self.assertEqual(customer.last_name, "Stone")
        self.assertRedirects(response, reverse("dashboard_home"))

    def test_create_client_requires_new_project_and_names(self):
        response = self.client.post(
            reverse("dashboard_batch_assign_project", args=[self.batch.id]),
            {
                "project_id": "",
                "create_client": "1",
                "company_name": "North Shore Studio",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Create a new project to add a client in the same step.", status_code=400)
        self.assertContains(response, "Client first name is required when Create client is enabled.", status_code=400)
        self.assertContains(response, "Client last name is required when Create client is enabled.", status_code=400)

    def test_can_apply_tags_to_batch_without_project_assignment(self):
        response = self.client.post(
            reverse("dashboard_batch_assign_project", args=[self.batch.id]),
            {"tags": "warehouse, lake, warehouse"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("dashboard_batch_detail", args=[self.batch.id]))
        self.assertEqual(list(self.media.tags.order_by("name").values_list("name", flat=True)), ["lake", "warehouse"])

    def test_batch_detail_shows_existing_batch_tags_in_form(self):
        lake = Tag.objects.create(name="lake")
        warehouse = Tag.objects.create(name="warehouse")
        self.media.tags.add(lake, warehouse)

        response = self.client.get(reverse("dashboard_batch_detail", args=[self.batch.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="lake, warehouse"', html=False)

    def test_tag_only_save_keeps_batch_on_dashboard(self):
        self.client.post(
            reverse("dashboard_batch_assign_project", args=[self.batch.id]),
            {"tags": "warehouse"},
        )

        response = self.client.get(reverse("dashboard_home"))

        self.assertEqual(response.status_code, 200)
        batches = list(response.context["batches"])
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0].id, self.batch.id)

    def test_fully_assigned_batch_disappears_from_dashboard(self):
        project = Project.objects.create(name="Assigned Project")
        self.client.post(
            reverse("dashboard_batch_assign_project", args=[self.batch.id]),
            {"project_id": str(project.id)},
        )

        response = self.client.get(reverse("dashboard_home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["batches"]), [])

    def test_authenticated_user_claims_loose_tag_when_saving_batch(self):
        loose_tag = Tag.objects.create(name="warehouse")
        self.assertIsNone(loose_tag.user)

        self.client.login(username="editor", password="secret123")
        response = self.client.post(
            reverse("dashboard_batch_assign_project", args=[self.batch.id]),
            {"tags": "warehouse"},
        )

        self.assertEqual(response.status_code, 302)

        loose_tag.refresh_from_db()
        self.assertEqual(loose_tag.user, self.user)
        self.assertEqual(list(self.media.tags.values_list("name", flat=True)), ["warehouse"])


class BatchLifecycleTests(TestCase):
    def test_dashboard_home_does_not_delete_empty_batches(self):
        batch = Batch.objects.create()

        response = self.client.get(reverse("dashboard_home"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Batch.objects.filter(id=batch.id).exists())


class DashboardNavigationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="navuser", password="secret123")
        self.project = Project.objects.create(name="Lake Project", location="Chicago")
        self.client_obj = Customer.objects.create(
            project=self.project,
            company_name="Lake House Studio",
            first_name="Avery",
            last_name="Stone",
        )
        self.batch = Batch.objects.create()
        self.media = Media.objects.create(
            batch=self.batch,
            project=self.project,
            file_name="lake-broll.mp4",
            file_path="C:\\media\\lake-broll.mp4",
        )
        self.tag = Tag.objects.create(name="lake")
        self.media.tags.add(self.tag)
        self.other_media = Media.objects.create(
            batch=self.batch,
            project=self.project,
            file_name="warehouse-broll.mp4",
            file_path="C:\\media\\warehouse-broll.mp4",
        )
        self.other_tag = Tag.objects.create(name="warehouse")
        self.other_media.tags.add(self.other_tag)
        MediaMetadata.objects.create(media=self.media, file_type="video", codec="prores")

    def test_dashboard_clients_page_lists_clients(self):
        response = self.client.get(reverse("dashboard_clients"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lake House Studio")

    def test_client_detail_page_shows_project_and_media_links(self):
        response = self.client.get(reverse("dashboard_client_detail", args=[self.client_obj.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lake Project")
        self.assertContains(response, "lake-broll.mp4")

    def test_dashboard_projects_page_can_create_project(self):
        self.client.login(username="navuser", password="secret123")
        response = self.client.post(
            reverse("dashboard_projects"),
            {"name": "Fresh Project", "location": "Joplin"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Project.objects.filter(name="Fresh Project", location="Joplin").exists())
        project = Project.objects.get(name="Fresh Project", location="Joplin")
        self.assertTrue(ProjectUser.objects.filter(project=project, user=self.user).exists())

    def test_dashboard_media_page_filters_by_search_query(self):
        response = self.client.get(
            reverse("dashboard_media"),
            {"q": "lake", "projects": "1", "clients": "1", "tags": "1", "metadata": "1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "lake-broll.mp4")
        self.assertContains(response, "Lake Project")

    def test_project_detail_page_shows_project_media(self):
        response = self.client.get(reverse("dashboard_project_detail", args=[self.project.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lake Project")
        self.assertContains(response, "lake-broll.mp4")

    def test_project_detail_page_can_update_project_editors(self):
        teammate = get_user_model().objects.create_user(username="assistant", password="secret123")

        response = self.client.post(
            reverse("dashboard_project_detail", args=[self.project.id]),
            {
                "action": "update_editors",
                "editor_ids": [str(self.user.id), str(teammate.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            set(ProjectUser.objects.filter(project=self.project).values_list("user__username", flat=True)),
            {"assistant", "navuser"},
        )

    def test_project_detail_page_can_update_project_fields(self):
        response = self.client.post(
            reverse("dashboard_project_detail", args=[self.project.id]),
            {
                "action": "update_project",
                "name": "Updated Lake Project",
                "location": "Tulsa",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Updated Lake Project")
        self.assertEqual(self.project.location, "Tulsa")

    def test_project_detail_page_can_add_client(self):
        response = self.client.post(
            reverse("dashboard_project_detail", args=[self.project.id]),
            {
                "company_name": "Second Client Co",
                "first_name": "Jordan",
                "last_name": "Reed",
                "email": "jordan@example.com",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Customer.objects.filter(
                project=self.project,
                company_name="Second Client Co",
                first_name="Jordan",
                last_name="Reed",
            ).exists()
        )

    def test_project_detail_page_can_bulk_tag_filtered_media(self):
        self.client.login(username="navuser", password="secret123")

        response = self.client.post(
            reverse("dashboard_project_detail", args=[self.project.id]),
            {
                "action": "apply_tags",
                "q": "lake",
                "client_id": "",
                "tag_id": "",
                "tags": "1",
                "metadata": "1",
                "bulk_tags": "favorite",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.media.refresh_from_db()
        self.other_media.refresh_from_db()
        self.assertIn("favorite", list(self.media.tags.values_list("name", flat=True)))
        self.assertNotIn("favorite", list(self.other_media.tags.values_list("name", flat=True)))

    def test_media_detail_page_can_add_tags(self):
        self.client.login(username="navuser", password="secret123")

        response = self.client.post(
            reverse("dashboard_media_detail", args=[self.media.id]),
            {"tags": "hero, homepage"},
        )

        self.assertEqual(response.status_code, 302)
        self.media.refresh_from_db()
        self.assertEqual(
            list(self.media.tags.order_by("name").values_list("name", flat=True)),
            ["hero", "homepage", "lake"],
        )

    def test_tags_page_can_create_tags_from_shared_input(self):
        self.client.login(username="navuser", password="secret123")

        response = self.client.post(
            reverse("dashboard_tags"),
            {"tags": "promo, social"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Tag.objects.filter(user=self.user, name="promo").exists())
        self.assertTrue(Tag.objects.filter(user=self.user, name="social").exists())

    def test_tags_page_links_to_filtered_media(self):
        response = self.client.get(reverse("dashboard_tags"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'{reverse("dashboard_media")}?tag_id={self.tag.id}')
        self.assertContains(response, reverse("dashboard_project_detail", args=[self.project.id]))
        self.assertContains(response, reverse("dashboard_client_detail", args=[self.client_obj.id]))

    def test_tags_page_can_adopt_loose_tag(self):
        self.client.login(username="navuser", password="secret123")
        loose_tag = Tag.objects.create(name="adopt-me")
        self.media.tags.add(loose_tag)

        response = self.client.post(
            reverse("dashboard_tags"),
            {"action": "adopt_tag", "tag_id": str(loose_tag.id)},
        )

        self.assertEqual(response.status_code, 302)
        loose_tag.refresh_from_db()
        self.assertEqual(loose_tag.user, self.user)

    def test_tags_page_merges_loose_tag_into_existing_user_tag(self):
        self.client.login(username="navuser", password="secret123")
        existing_tag = Tag.objects.create(user=self.user, name="merge-me")
        loose_tag = Tag.objects.create(name="merge-me")
        self.other_media.tags.add(loose_tag)

        response = self.client.post(
            reverse("dashboard_tags"),
            {"action": "adopt_tag", "tag_id": str(loose_tag.id)},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Tag.objects.filter(id=loose_tag.id).exists())
        self.assertTrue(MediaTag.objects.filter(media=self.other_media, tag=existing_tag).exists())
