from django.contrib import admin
from .models import *


# Register your models here.
admin.site.register(Project)
admin.site.register(ProjectUser)
admin.site.register(Customer)
admin.site.register(Tag)
admin.site.register(Media)
admin.site.register(MediaTag)
admin.site.register(MediaMetadata)


