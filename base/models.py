from django.conf import settings
from django.db import models


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
    # ERD ties tags to user
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tags",
    )
    name = models.CharField(max_length=90)

    class Meta:
        unique_together = ("user", "name")

    def __str__(self):
        return self.name


class Media(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="media")

    file_name = models.CharField(max_length=90)
    file_path = models.CharField(max_length=256)

    # ERD has media_tags join table
    tags = models.ManyToManyField(Tag, through="MediaTag", related_name="media", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file_name} ({self.project})"


class MediaTag(models.Model):
    media = models.ForeignKey(Media, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("media", "tag")

    def __str__(self):
        return f"{self.media} + {self.tag}"


class MediaMetadata(models.Model):
    # ERD looks 1:1-ish (metadata belongs to media)
    media = models.OneToOneField(Media, on_delete=models.CASCADE, related_name="metadata")

    file_type = models.CharField(max_length=45, blank=True)
    resolution = models.CharField(max_length=45, blank=True)
    file_size = models.FloatField(null=True, blank=True)
    import_date = models.DateField(null=True, blank=True)
    has_color_grade = models.BooleanField(default=False)

    def __str__(self):
        return f"Metadata for {self.media}"
