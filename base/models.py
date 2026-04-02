from django.conf import settings
from django.db import models
# import user
from django.contrib.auth import get_user_model


class Project(models.Model):
    name = models.CharField(max_length=90)
    location = models.CharField(max_length=90, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # user <-> project (join table in ERD)
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ProjectUser",
        related_name="projects",
        blank=True,
    )

    def __str__(self):
        return self.name


class ProjectUser(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    # optional “gist” fields you’ll probably want
    role = models.CharField(max_length=50, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "project")

    def __str__(self):
        return f"{self.user} -> {self.project}"


class Customer(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="customers")

    # optional link to users table if you want to associate a customer with a user account
    # linked_user = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)

    company_name = models.CharField(max_length=45, blank=True)
    first_name = models.CharField(max_length=45)
    last_name = models.CharField(max_length=45)

    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    street_num = models.CharField(max_length=10, blank=True)
    street_name = models.CharField(max_length=45, blank=True)
    city = models.CharField(max_length=45, blank=True)
    state = models.CharField(max_length=2, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=45, blank=True)

    def __str__(self):
        label = self.company_name or f"{self.first_name} {self.last_name}"
        return f"{label} ({self.project})"



class Tag(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tags",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=90)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="uniq_tag_user_name"),
        ]

    def __str__(self):
        return self.name



class Batch(models.Model):

    class Meta:
        verbose_name_plural = "Batches"

    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Batch {self.pk}"


class Media(models.Model):

    class Meta:
        verbose_name_plural = "Media Files"

    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="media", null=True, blank=True)

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="media", null=True, blank=True)

    file_name = models.CharField(max_length=90)
    file_path = models.CharField(max_length=256, unique=True)

    tags = models.ManyToManyField(Tag, through="MediaTag", related_name="media", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file_name}"



class MediaTag(models.Model):
    media = models.ForeignKey(Media, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("media", "tag")

    def __str__(self):
        return f"{self.media} + {self.tag}"


class MediaMetadata(models.Model):

    class Meta:
        verbose_name_plural = "Media Metadata"

    # ERD looks 1:1-ish (metadata belongs to media)
    media = models.OneToOneField(Media, on_delete=models.CASCADE, related_name="metadata")

    file_type = models.CharField(max_length=45, blank=True)
    resolution = models.CharField(max_length=45, blank=True)
    file_size = models.FloatField(null=True, blank=True)
    import_date = models.DateField(null=True, blank=True)
    has_color_grade = models.BooleanField(default=False)

    def __str__(self):
        return f"Metadata for {self.media}"
