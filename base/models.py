from django.conf import settings
from django.db import models


class Project(models.Model):
    name = models.CharField(max_length=90)
    location = models.CharField(max_length=90, blank=True)
    start_date = models.DateField(null=True, blank=True, auto_now_add=True)
    

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

    role = models.CharField(max_length=90, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "project")

    def __str__(self):
        return f"{self.user} -> {self.project}"


class Customer(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="customers",
    )

    company_name = models.CharField(max_length=90, blank=True)
    first_name = models.CharField(max_length=90)
    last_name = models.CharField(max_length=90)

    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)


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

    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name="media",
        null=True,
        blank=True,
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="media",
         null=True,
        blank=True,
    )

    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=512, unique=True)

    tags = models.ManyToManyField(
        Tag,
        through="MediaTag",
        related_name="media",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file_name


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

    media = models.OneToOneField(
        Media,
        on_delete=models.CASCADE,
        related_name="metadata",
    )

    file_type = models.CharField(max_length=90, blank=True)

    file_size = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="File size in bytes",
    )

    imported_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this metadata record was imported or created",
    )

    has_color_grade = models.BooleanField(default=False)

    hdr = models.BooleanField(
        null=True,
        blank=True,
        help_text="True/False when known, null when unknown",
    )

    frame_rate = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Frames per second, e.g. 23.976",
    )

    codec = models.CharField(max_length=90, blank=True)

    duration = models.DurationField(
        null=True,
        blank=True,
        help_text="Length of media",
    )

    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)

    aspect_ratio = models.CharField(
        max_length=90,
        null=True,
        blank=True,
        help_text="Optional source-reported aspect ratio",
    )

    color_space = models.CharField(max_length=90, blank=True)

    bit_rate = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Bits per second",
    )

    def __str__(self):
        return f"Metadata for {self.media}"

    @property
    def resolution(self):
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return ""

    @property
    def derived_aspect_ratio(self):
        if self.width and self.height:
            from math import gcd
            divisor = gcd(self.width, self.height)
            return f"{self.width // divisor}:{self.height // divisor}"
        return ""