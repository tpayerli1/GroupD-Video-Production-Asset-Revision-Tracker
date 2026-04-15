import json
import os
import subprocess

from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Q

from .models import *
from .media_probe import probe_media_file

#import prefetch_related, annotate, Count
from django.db.models import Prefetch


SEARCH_SCOPES = ("projects", "tags", "clients", "metadata")


def _empty_search_state():
    return {
        "q": "",
        "projects": True,
        "tags": True,
        "clients": True,
        "metadata": True,
    }


def _search_state_from_request(request):
    source = request.POST if request.method == "POST" else request.GET

    query = (source.get("q") or "").strip()
    selected = {
        scope: bool(source.get(scope))
        for scope in SEARCH_SCOPES
    }

    if not any(selected.values()):
        selected = {scope: True for scope in SEARCH_SCOPES}

    return {"q": query, **selected}


def _search_dashboard(query, search_state):
    results = {
        "projects": [],
        "tags": [],
        "clients": [],
        "metadata": [],
        "total": 0,
    }

    if not query:
        return results

    if search_state["projects"]:
        results["projects"] = list(
            Project.objects.filter(
                Q(name__icontains=query) |
                Q(location__icontains=query) |
                Q(customers__company_name__icontains=query) |
                Q(customers__first_name__icontains=query) |
                Q(customers__last_name__icontains=query) |
                Q(media__file_name__icontains=query) |
                Q(media__file_path__icontains=query)
            )
            .annotate(
                media_total=Count("media", distinct=True),
                client_total=Count("customers", distinct=True),
            )
            .order_by("name")
            .distinct()
        )

    if search_state["tags"]:
        results["tags"] = list(
            Tag.objects.filter(
                Q(name__icontains=query) |
                Q(media__file_name__icontains=query) |
                Q(media__file_path__icontains=query)
            )
            .annotate(media_total=Count("media", distinct=True))
            .order_by("name")
            .distinct()
        )

    if search_state["clients"]:
        results["clients"] = list(
            Customer.objects.select_related("project")
            .filter(
                Q(company_name__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(email__icontains=query) |
                Q(phone__icontains=query) |
                Q(project__name__icontains=query)
            )
            .order_by("company_name", "last_name", "first_name")
            .distinct()
        )

    if search_state["metadata"]:
        results["metadata"] = list(
            Media.objects.select_related("project", "metadata")
            .prefetch_related("tags")
            .filter(
                Q(file_name__icontains=query) |
                Q(file_path__icontains=query) |
                Q(project__name__icontains=query) |
                Q(tags__name__icontains=query) |
                Q(metadata__file_type__icontains=query) |
                Q(metadata__codec__icontains=query) |
                Q(metadata__color_space__icontains=query) |
                Q(metadata__aspect_ratio__icontains=query)
            )
            .order_by("-created_at")
            .distinct()
        )
        for media in results["metadata"]:
            media.metadata_record = getattr(media, "metadata", None)

    results["total"] = sum(len(results[scope]) for scope in SEARCH_SCOPES)
    return results


def dashboard_home(request):
    empty_batch_ids = (
        Batch.objects
        .annotate(media_count=Count("media"))
        .filter(media_count=0)
        .values_list("id", flat=True)
    )
    Batch.objects.filter(id__in=empty_batch_ids).delete()

    search_state = _search_state_from_request(request)
    search_results = _search_dashboard(search_state["q"], search_state)

    batches = (
        Batch.objects
        .annotate(media_count=Count("media"))
        .order_by("-created_at")
    )

    return render(
        request,
        "base/dashboard_home.html",
        {
            "batches": batches,
            "search_state": search_state,
            "search_results": search_results,
        },
    )

def dashboard_batch_detail(request, batch_id):
    batch = get_object_or_404(Batch.objects.annotate(media_count=Count("media")), id=batch_id)
    media = batch.media.order_by("-created_at")
    projects = Project.objects.order_by("name")
    return render(
        request,
        "base/dashboard_batch_detail.html",
        {
            "batch": batch,
            "media": media,
            "projects": projects,
            "search_state": _empty_search_state(),
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

    media = b.media.order_by("-created_at").values("id", "file_name", "file_path", "created_at")

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

    print("🔎 Looking up batch:", batch_id)
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
        for name in tag_names:
            t, created = Tag.objects.get_or_create(user=None, name=name)
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
        file_name = os.path.basename(p.rstrip("\\/"))[:90]

        print("→ Processing:", p)

        obj, was_created = Media.objects.get_or_create(
            file_path=p,
            defaults={
                "file_name": file_name,
                "batch": batch,
            },
        )

        if was_created:
            created_count += 1
            print("   + Created media record")
        else:
            print("   • Media exists — checking updates")

            changed = False

            if obj.batch_id != batch.id:
                print("     → Updating batch")
                obj.batch = batch
                changed = True

            if obj.file_name != file_name:
                print("     → Updating filename")
                obj.file_name = file_name
                changed = True

            if changed:
                obj.save(update_fields=["batch", "file_name"])
                print("     ✓ Saved updates")

            updated_count += 1

        if tags:
            for t in tags:
                _, mt_created = MediaTag.objects.get_or_create(media=obj, tag=t)
                if mt_created:
                    tag_links_created += 1
                    print("     + Linked tag:", t.name)

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


@csrf_exempt
def api_media_metadata_probe(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    data = _json(request)

    targets = []

    paths = data.get("paths")
    if isinstance(paths, list):
        for path in paths:
            if path:
                targets.append({"file_path": str(path)})

    media_id = data.get("media_id")
    file_path = data.get("file_path")

    if media_id:
        targets.append({"media_id": media_id, "file_path": file_path})
    elif file_path:
        targets.append({"file_path": str(file_path)})

    if not targets:
        return JsonResponse({"detail": "file_path, paths, or media_id required"}, status=400)

    ffprobe_path = data.get("ffprobe_path")
    processed = []
    created_count = 0
    updated_count = 0
    missing_count = 0
    error_count = 0

    for target in targets:
        media = None

        target_media_id = target.get("media_id")
        target_file_path = (target.get("file_path") or "").strip()

        if target_media_id:
            media = Media.objects.filter(id=target_media_id).first()
            if media and not target_file_path:
                target_file_path = media.file_path

        if media is None and target_file_path:
            media = Media.objects.filter(file_path=target_file_path).first()

        if media is None:
            missing_count += 1
            processed.append(
                {
                    "file_path": target_file_path,
                    "status": "missing_media",
                    "detail": "No media record matches this path.",
                }
            )
            continue

        if not target_file_path:
            target_file_path = media.file_path

        if not os.path.exists(target_file_path):
            missing_count += 1
            processed.append(
                {
                    "media_id": media.id,
                    "file_path": target_file_path,
                    "status": "missing_file",
                    "detail": "The file does not exist on disk.",
                }
            )
            continue

        try:
            metadata_defaults = probe_media_file(target_file_path, ffprobe_path=ffprobe_path)

            metadata_obj, was_created = MediaMetadata.objects.get_or_create(media=media)
            metadata_obj.file_type = metadata_defaults["file_type"]
            metadata_obj.file_size = metadata_defaults["file_size"]
            metadata_obj.imported_at = metadata_defaults["imported_at"]
            metadata_obj.hdr = metadata_defaults["hdr"]
            metadata_obj.frame_rate = metadata_defaults["frame_rate"]
            metadata_obj.codec = metadata_defaults["codec"]
            metadata_obj.duration = metadata_defaults["duration"]
            metadata_obj.width = metadata_defaults["width"]
            metadata_obj.height = metadata_defaults["height"]
            metadata_obj.aspect_ratio = metadata_defaults["aspect_ratio"]
            metadata_obj.color_space = metadata_defaults["color_space"]
            metadata_obj.bit_rate = metadata_defaults["bit_rate"]
            metadata_obj.save()

            if was_created:
                created_count += 1
            else:
                updated_count += 1

            processed.append(
                {
                    "media_id": media.id,
                    "file_path": target_file_path,
                    "status": "created" if was_created else "updated",
                    "file_type": metadata_obj.file_type,
                }
            )
        except (FileNotFoundError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
            error_count += 1
            processed.append(
                {
                    "media_id": media.id,
                    "file_path": target_file_path,
                    "status": "error",
                    "detail": str(exc),
                }
            )

    return JsonResponse(
        {
            "processed": processed,
            "processed_count": len(processed),
            "created": created_count,
            "updated": updated_count,
            "missing": missing_count,
            "errors": error_count,
        }
    )
