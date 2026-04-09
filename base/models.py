from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.core.validators import MinValueValidator

# -----------------------------
# CUSTOMER
# -----------------------------
class Customer(models.Model):
    Customer_ID = models.AutoField(primary_key=True)
    Project_ID = models.ForeignKey(
        "Project",
        on_delete=models.CASCADE,
        related_name="customers",
        null=True,  # allow null temporarily to avoid circular FK issues
        blank=True
    )

    Company_Name = models.CharField(max_length=45, blank=True)
    Customer_FN = models.CharField(max_length=45)
    Customer_LN = models.CharField(max_length=45)
    Customer_PhoneNum = models.CharField(max_length=20, unique=True)
    Customer_Email = models.CharField(max_length=45, unique=True)
    Customer_StreetNum = models.CharField(max_length=10)
    Customer_StreetName = models.CharField(max_length=45)
    Customer_City = models.CharField(max_length=45)
    Customer_State = models.CharField(max_length=2, blank=True)
    Customer_ZipCode = models.CharField(max_length=10, blank=True)
    Customer_Country = models.CharField(max_length=45)

    class Meta:
        db_table = "customer"

    def __str__(self):
        return f"{self.Customer_FN} {self.Customer_LN}"


# -----------------------------
# PROJECT
# -----------------------------
class Project(models.Model):
    Project_ID = models.AutoField(primary_key=True)
    Customer_ID = models.ForeignKey(
        Customer,
        on_delete=models.RESTRICT,
        related_name="projects"
    )
    Project_Name = models.CharField(max_length=90, unique=True)
    Project_Location = models.CharField(max_length=90, blank=True)
    Project_Start_Date = models.DateField()
    Project_End_Date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "project"
        

    def __str__(self):
        return self.Project_Name


# -----------------------------
# PROJECT_USER (JOIN TABLE)
# -----------------------------
class ProjectUser(models.Model):
    User_ID = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    Project_ID = models.ForeignKey(Project, on_delete=models.CASCADE)

    class Meta:
        db_table = "project_user"
        constraints = [
            models.UniqueConstraint(fields=["User_ID", "Project_ID"], name="unique_user_project")
        ]

    def __str__(self):
        return f"{self.User_ID} -> {self.Project_ID}"


# -----------------------------
# BATCH
# -----------------------------
class Batch(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Batches"
        db_table = "batch"

    def __str__(self):
        return f"Batch {self.pk}"


# -----------------------------
# MEDIA
# -----------------------------
class Media(models.Model):
    Media_ID = models.AutoField(primary_key=True)
    Project_ID = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="media", null=True, blank=True)
    File_Name = models.CharField(max_length=90, unique=True)
    File_Path = models.CharField(max_length=255, unique=True)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="media", null=True, blank=True)
    tags = models.ManyToManyField("Tag", through="MediaTag", related_name="media")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "media"

    def __str__(self):
        return self.File_Name


# -----------------------------
# MEDIA METADATA
# -----------------------------
class MediaMetadata(models.Model):
    MetaData_ID = models.AutoField(primary_key=True)
    Media_ID = models.OneToOneField(Media, on_delete=models.CASCADE, related_name="metadata")

    File_Type = models.CharField(max_length=45)
    Resolution = models.CharField(max_length=45, blank=True)
    File_Size = models.FloatField(validators=[MinValueValidator(0.0)], null=True, blank=True)
    Import_Date = models.DateField(null=True, blank=True)
    HDR = models.BooleanField()
    Frame_Rate = models.CharField(max_length=45, blank=True)
    Codec = models.CharField(max_length=45, blank=True)
    Duration = models.TimeField()
    Aspect_Ratio = models.CharField(max_length=45, blank=True)
    Color_Space = models.CharField(max_length=45, blank=True)

    class Meta:
        db_table = "metadata"

    def __str__(self):
        return f"Metadata for {self.Media_ID}"


# -----------------------------
# TAGS
# -----------------------------
class Tag(models.Model):
    Tag_ID = models.AutoField(primary_key=True)
    User_ID = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    Tag_Name = models.CharField(max_length=90)

    class Meta:
        db_table = "tags"

    def __str__(self):
        return self.Tag_Name


# -----------------------------
# MEDIA_TAGS (JOIN TABLE)
# -----------------------------
class MediaTag(models.Model):
    Tag_ID = models.ForeignKey(Tag, on_delete=models.CASCADE)
    Media_ID = models.ForeignKey(Media, on_delete=models.CASCADE)

    class Meta:
        db_table = "media_tags"
        constraints = [
            models.UniqueConstraint(fields=["Tag_ID", "Media_ID"], name="unique_tag_media")
        ]

    def __str__(self):
        return f"{self.Tag_ID} -> {self.Media_ID}"
    

# -----------------------------
# USER
# -----------------------------

class User(models.Model):
    User_ID = models.AutoField(primary_key=True)
    User_Name = models.CharField(max_length=45, unique=True)
    User_Password = models.CharField(max_length=255)
    User_FN = models.CharField(max_length=45)
    User_LN = models.CharField(max_length=45)
    User_Email = models.CharField(max_length=45, unique=True)

    class Meta:
        db_table = "user"

    def __str__(self):
        return self.User_Name