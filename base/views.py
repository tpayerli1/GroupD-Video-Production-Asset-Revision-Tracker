import json
import os
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count

from .models import *


def dashboard_home(request):
    batches = (
        Batch.objects
        .annotate(media_count=Count("media"))
        .order_by("-created_at")
    )
    return render(request, "base/dashboard_home.html", {"batches": batches})

def dashboard_batch_detail(request, batch_id):
    # Annotate batch with media count
    batch = get_object_or_404(
        Batch.objects.annotate(media_count=Count("media")),
        id=batch_id
    )

    # Fetch media for this batch, order by creation date
    media = batch.media.order_by("-created_at")  # Ensure Media model has created_at

    # Fetch all projects, ordered by Project_Name
    projects = Project.objects.order_by("Project_Name")

    return render(
        request,
        "base/dashboard_batch_detail.html",
        {
            "batch": batch,
            "media": media,
            "projects": projects,
        },
    )

def dashboard_batch_assign_project(request, batch_id):
    if request.method != "POST":
        return redirect("dashboard_batch_detail", batch_id=batch_id)

    batch = get_object_or_404(Batch, id=batch_id)

    project_id = request.POST.get("project_id") or ""
    new_project_name = (request.POST.get("new_project_name") or "").strip()

    project = None
    if new_project_name:
        project = Project.objects.create(name=new_project_name)
    elif project_id.isdigit():
        project = Project.objects.filter(id=int(project_id)).first()

    if project:
        Media.objects.filter(batch=batch).update(project=project)

    return redirect("dashboard_batch_detail", batch_id=batch_id)



# API STUFF

def _json(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return {}


def _parse_tags(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        parts = raw
    else:
        parts = str(raw).split(",")
    cleaned = []
    for t in parts:
        t = (t or "").strip()
        if t:
            cleaned.append(t.lower())
    seen = set()
    out = []
    for t in cleaned:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


@csrf_exempt
def api_batches_ensure(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    data = _json(request)
    reset = bool(data.get("reset"))

    if reset:
        batch_id = data.get("batch_id")
        if batch_id:
            Batch.objects.filter(id=batch_id, closed_at__isnull=True).update(closed_at=timezone.now())

        b = Batch.objects.create()
        return JsonResponse({"batch_id": b.id})

    # normal "give me a fresh batch id"
    b = Batch.objects.create()
    return JsonResponse({"batch_id": b.id})


@csrf_exempt
def api_batch_detail(request, batch_id: int):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    b = Batch.objects.prefetch_related("media").filter(id=batch_id).first()
    if not b:
        return JsonResponse({"detail": "Not found"}, status=404)

    media = b.media.order_by("-created_at").values("id", "File_Name", "File_Path", "created_at")

    return JsonResponse(
        {
            "id": b.id,
            "created_at": b.created_at,
            "closed_at": b.closed_at,
            "count": b.media.count(),
            "media": list(media),
        }
    )

@csrf_exempt
def api_media_files(request):
    print("\n========== api_media_files ==========")

    if request.method != "POST":
        print("❌ Invalid method:", request.method)
        return HttpResponseNotAllowed(["POST"])

    data = _json(request)
    print("📦 Incoming payload:", data)

    batch_id = data.get("batch_id")
    if not batch_id:
        print("❌ Missing batch_id")
        return JsonResponse({"detail": "batch_id required"}, status=400)

    batch = Batch.objects.filter(id=batch_id).first()
    if not batch:
        print("❌ Batch not found:", batch_id)
        return JsonResponse({"detail": "Batch not found"}, status=404)

    print("✅ Using batch:", batch.id)

    paths = data.get("paths") or []
    if not isinstance(paths, list):
        print("❌ paths not list:", paths)
        return JsonResponse({"detail": "paths must be a list"}, status=400)

    print(f"📁 Received {len(paths)} paths")

    tag_names = _parse_tags(data.get("tags"))
    print("🏷 Parsed tags:", tag_names)

    tags = []
    if tag_names:
        print("🏷 Creating/fetching tags...")
        # Use a default user for tag creation
        default_user = User.objects.first()
        if not default_user:
            return JsonResponse({"detail": "No user exists to assign tags"}, status=500)

        for name in tag_names:
            t, created = Tag.objects.get_or_create(User_ID=default_user, Tag_Name=name)
            if created:
                print("  + Created tag:", name)
            tags.append(t)

    created_count = 0
    updated_count = 0
    tag_links_created = 0

    print("🚀 Processing files...")

    for p in paths:
        if not p:
            continue

        p = str(p)[:256]
        File_Name = os.path.basename(p.rstrip("\\/"))[:90]

        print("→ Processing:", p)

        obj, was_created = Media.objects.get_or_create(
            File_Path=p,
            defaults={
                "File_Name": File_Name,
                "batch": batch,
            },
        )

        if was_created:
            created_count += 1
            print("   + Created media record")
        else:
            changed = False
            if obj.batch_id != batch.id:
                obj.batch = batch
                changed = True
            if obj.File_Name != File_Name:
                obj.File_Name = File_Name
                changed = True
            if changed:
                obj.save(update_fields=["batch", "File_Name"])
                print("     ✓ Saved updates")
            updated_count += 1

        if tags:
            for t in tags:
                _, mt_created = MediaTag.objects.get_or_create(Media_ID=obj, Tag_ID=t)
                if mt_created:
                    tag_links_created += 1
                    print("     + Linked tag:", t.Tag_Name)

    print("✅ Done")
    print("   Created:", created_count)
    print("   Updated:", updated_count)
    print("   Tag links:", tag_links_created)
    print("=====================================\n")

    return JsonResponse(
        {
            "batch_id": batch.id,
            "received": len(paths),
            "created": created_count,
            "updated": updated_count,
            "tag_links_created": tag_links_created,
            "tags": tag_names,
        }
    )
