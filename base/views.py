import json
import os
import subprocess
from decimal import Decimal, InvalidOperation
from datetime import timedelta, datetime
from urllib.parse import urlencode

from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib import messages

from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Q
from django.urls import reverse

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


def _search_terms(query):
    return [term for term in (query or "").split() if term]


def _any_term_query(terms, builder):
    combined = Q()
    for term in terms:
        combined |= builder(term)
    return combined


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


def _batch_assignment_state(data=None):
    source = data or {}
    raw_tags = source.get("tags")
    parsed_tags = _parse_tags(raw_tags)
    return {
        "project_id": (source.get("project_id") or "").strip(),
        "new_project_name": (source.get("new_project_name") or "").strip(),
        "create_client": bool(source.get("create_client")),
        "company_name": (source.get("company_name") or "").strip(),
        "first_name": (source.get("first_name") or "").strip(),
        "last_name": (source.get("last_name") or "").strip(),
        "email": (source.get("email") or "").strip(),
        "phone": (source.get("phone") or "").strip(),
        "tags": parsed_tags,
        "tags_value": ", ".join(parsed_tags),
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


def _base_context(search_state=None):
    return {
        "search_state": search_state or _empty_search_state(),
    }


def _search_dashboard(query, search_state):
    results = {
        "projects": [],
        "tags": [],
        "clients": [],
        "metadata": [],
        "total": 0,
    }

    terms = _search_terms(query)
    if not terms:
        return results

    if search_state["projects"]:
        results["projects"] = list(
            Project.objects.filter(
                _any_term_query(
                    terms,
                    lambda term: (
                        Q(name__icontains=term) |
                        Q(location__icontains=term) |
                        Q(customers__company_name__icontains=term) |
                        Q(customers__first_name__icontains=term) |
                        Q(customers__last_name__icontains=term) |
                        Q(media__file_name__icontains=term) |
                        Q(media__file_path__icontains=term)
                    ),
                )
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
                _any_term_query(
                    terms,
                    lambda term: (
                        Q(name__icontains=term) |
                        Q(media__file_name__icontains=term) |
                        Q(media__file_path__icontains=term)
                    ),
                )
            )
            .annotate(media_total=Count("media", distinct=True))
            .order_by("name")
            .distinct()
        )

    if search_state["clients"]:
        results["clients"] = list(
            Customer.objects.select_related("project").filter(
                _any_term_query(
                    terms,
                    lambda term: (
                        Q(company_name__icontains=term) |
                        Q(first_name__icontains=term) |
                        Q(last_name__icontains=term) |
                        Q(email__icontains=term) |
                        Q(phone__icontains=term) |
                        Q(project__name__icontains=term)
                    ),
                )
            )
            .order_by("company_name", "last_name", "first_name")
            .distinct()
        )

    if search_state["metadata"]:
        results["metadata"] = list(
            Media.objects.select_related("project", "metadata")
            .prefetch_related("tags")
            .filter(
                _any_term_query(
                    terms,
                    lambda term: (
                        Q(file_name__icontains=term) |
                        Q(file_path__icontains=term) |
                        Q(project__name__icontains=term) |
                        Q(tags__name__icontains=term) |
                        Q(metadata__file_type__icontains=term) |
                        Q(metadata__codec__icontains=term) |
                        Q(metadata__color_space__icontains=term) |
                        Q(metadata__aspect_ratio__icontains=term)
                    ),
                )
            )
            .order_by("-created_at")
            .distinct()
        )
        for media in results["metadata"]:
            media.metadata_record = getattr(media, "metadata", None)

    results["total"] = sum(len(results[scope]) for scope in SEARCH_SCOPES)
    return results


def _render_batch_detail(request, batch_id, assignment_form=None, assignment_errors=None, status_code=200):
    batch = get_object_or_404(Batch.objects.annotate(media_count=Count("media")), id=batch_id)
    media = batch.media.prefetch_related("tags").order_by("-created_at")
    projects = Project.objects.order_by("name")
    default_form = assignment_form or _batch_assignment_state()

    if not assignment_form:
        batch_tags = list(
            Tag.objects.filter(media__batch=batch)
            .order_by("name")
            .values_list("name", flat=True)
            .distinct()
        )
        default_form["tags"] = batch_tags
        default_form["tags_value"] = ", ".join(batch_tags)

    return render(
        request,
        "base/dashboard_batch_detail.html",
        {
            "batch": batch,
            "media": media,
            "projects": projects,
            "search_state": _empty_search_state(),
            "assignment_form": default_form,
            "assignment_errors": assignment_errors or [],
        },
        status=status_code,
    )


def _batch_has_unassigned_media(batch_id):
    return Media.objects.filter(batch_id=batch_id, project__isnull=True).exists()


def _resolve_tags_for_user(tag_names, user=None):
    tags = []
    claimed_count = 0

    for name in tag_names:
        tag = None

        if user and getattr(user, "is_authenticated", False):
            tag = Tag.objects.filter(user=user, name=name).first()

        if tag is None:
            tag = Tag.objects.filter(user__isnull=True, name=name).first()
            if tag and user and getattr(user, "is_authenticated", False):
                tag.user = user
                tag.save(update_fields=["user"])
                claimed_count += 1

        if tag is None:
            tag = Tag.objects.create(
                user=user if user and getattr(user, "is_authenticated", False) else None,
                name=name,
            )

        tags.append(tag)

    return tags, claimed_count


def _adopt_loose_tag_for_user(tag, user):
    if tag.user_id is not None:
        return tag, False, 0

    existing_tag = Tag.objects.filter(user=user, name=tag.name).first()
    moved_links = 0

    if existing_tag:
        for media_id in tag.mediatag_set.values_list("media_id", flat=True):
            _, created = MediaTag.objects.get_or_create(media_id=media_id, tag=existing_tag)
            if created:
                moved_links += 1
        tag.delete()
        return existing_tag, True, moved_links

    tag.user = user
    tag.save(update_fields=["user"])
    return tag, True, tag.media.count()


def _project_media_queryset(project, q="", client_id="", tag_id="", search_state=None):
    search_state = search_state or _empty_search_state()
    terms = _search_terms(q)

    media = (
        project.media.select_related("metadata", "batch")
        .prefetch_related("tags")
        .order_by("file_name")
    )

    if terms:
        media = media.filter(
            _any_term_query(
                terms,
                lambda term: (
                    Q(file_name__icontains=term) |
                    Q(file_path__icontains=term) |
                    (Q(tags__name__icontains=term) if search_state["tags"] else Q()) |
                    (
                        Q(metadata__file_type__icontains=term)
                        | Q(metadata__codec__icontains=term)
                        | Q(metadata__color_space__icontains=term)
                        | Q(metadata__aspect_ratio__icontains=term)
                        if search_state["metadata"] else Q()
                    )
                ),
            )
        ).distinct()

    if client_id.isdigit():
        media = media.filter(project__customers__id=int(client_id)).distinct()
    if tag_id.isdigit():
        media = media.filter(tags__id=int(tag_id)).distinct()

    return media


def dashboard_home(request):
    batches = (
        Batch.objects
        .annotate(
            media_count=Count("media", distinct=True),
            unassigned_count=Count("media", filter=Q(media__project__isnull=True), distinct=True),
        )
        .filter(media_count__gt=0, unassigned_count__gt=0)
        .order_by("-created_at")
    )

    return render(
        request,
        "base/dashboard_home.html",
        {
            "batches": batches,
            **_base_context(),
        },
    )

def dashboard_batch_detail(request, batch_id):
    if not _batch_has_unassigned_media(batch_id):
        messages.info(request, f"Batch #{batch_id} is fully assigned and has been removed from the active queue.")
        return redirect("dashboard_home")

    return _render_batch_detail(request, batch_id)


def dashboard_clients(request):
    if request.method == "POST":
        project_id = request.POST.get("project_id") or ""
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()

        if not project_id.isdigit():
            messages.error(request, "Choose a project before creating a client.")
        elif not first_name or not last_name:
            messages.error(request, "Client first and last name are required.")
        else:
            Customer.objects.create(
                project_id=int(project_id),
                company_name=(request.POST.get("company_name") or "").strip(),
                first_name=first_name,
                last_name=last_name,
                email=(request.POST.get("email") or "").strip(),
                phone=(request.POST.get("phone") or "").strip(),
            )
            messages.success(request, "Client created.")
            return redirect("dashboard_clients")

    q = (request.GET.get("q") or "").strip()
    project_id = (request.GET.get("project_id") or "").strip()

    clients = Customer.objects.select_related("project").order_by("project__name", "company_name", "last_name", "first_name")
    terms = _search_terms(q)
    if terms:
        clients = clients.filter(
            _any_term_query(
                terms,
                lambda term: (
                    Q(company_name__icontains=term)
                    | Q(first_name__icontains=term)
                    | Q(last_name__icontains=term)
                    | Q(email__icontains=term)
                    | Q(project__name__icontains=term)
                ),
            )
        )
    if project_id.isdigit():
        clients = clients.filter(project_id=int(project_id))

    return render(
        request,
        "base/dashboard_clients.html",
        {
            "clients": clients,
            "projects": Project.objects.order_by("name"),
            "filters": {"q": q, "project_id": project_id},
            **_base_context(),
        },
    )


def dashboard_projects(request):
    if request.method == "POST":
        project_name = (request.POST.get("name") or "").strip()
        if not project_name:
            messages.error(request, "Project name is required.")
        else:
            project = Project.objects.create(
                name=project_name,
                location=(request.POST.get("location") or "").strip(),
            )
            client_first_name = (request.POST.get("client_first_name") or "").strip()
            client_last_name = (request.POST.get("client_last_name") or "").strip()
            if client_first_name and client_last_name:
                Customer.objects.create(
                    project=project,
                    company_name=(request.POST.get("client_company_name") or "").strip(),
                    first_name=client_first_name,
                    last_name=client_last_name,
                    email=(request.POST.get("client_email") or "").strip(),
                    phone=(request.POST.get("client_phone") or "").strip(),
                )
            messages.success(request, "Project created.")
            return redirect("dashboard_projects")

    q = (request.GET.get("q") or "").strip()
    client_id = (request.GET.get("client_id") or "").strip()

    projects = (
        Project.objects.annotate(
            media_total=Count("media", distinct=True),
            client_total=Count("customers", distinct=True),
        )
        .order_by("name")
    )
    terms = _search_terms(q)
    if terms:
        projects = projects.filter(
            _any_term_query(
                terms,
                lambda term: (
                    Q(name__icontains=term)
                    | Q(location__icontains=term)
                    | Q(customers__company_name__icontains=term)
                    | Q(customers__first_name__icontains=term)
                    | Q(customers__last_name__icontains=term)
                ),
            )
        ).distinct()
    if client_id.isdigit():
        projects = projects.filter(customers__id=int(client_id)).distinct()

    return render(
        request,
        "base/dashboard_projects.html",
        {
            "projects": projects,
            "clients": Customer.objects.select_related("project").order_by("company_name", "last_name", "first_name"),
            "filters": {"q": q, "client_id": client_id},
            **_base_context(),
        },
    )


def dashboard_project_detail(request, project_id):
    project = get_object_or_404(
        Project.objects.annotate(
            media_total=Count("media", distinct=True),
            client_total=Count("customers", distinct=True),
        ),
        id=project_id,
    )

    q = (request.GET.get("q") or "").strip()
    client_id = (request.GET.get("client_id") or "").strip()
    tag_id = (request.GET.get("tag_id") or "").strip()
    search_state = _search_state_from_request(request)
    if request.method == "POST":
        action = request.POST.get("action") or "add_client"

        if action == "apply_tags":
            q = (request.POST.get("q") or "").strip()
            client_id = (request.POST.get("client_id") or "").strip()
            tag_id = (request.POST.get("tag_id") or "").strip()
            search_state = {
                "q": q,
                "projects": False,
                "clients": False,
                "tags": bool(request.POST.get("tags")),
                "metadata": bool(request.POST.get("metadata")),
            }
            tag_names = _parse_tags(request.POST.get("bulk_tags"))
            media = _project_media_queryset(project, q=q, client_id=client_id, tag_id=tag_id, search_state=search_state)

            if not tag_names:
                messages.error(request, "Enter at least one tag to apply to the filtered media.")
            else:
                tags, claimed_tag_count = _resolve_tags_for_user(tag_names, request.user)
                tag_links_created = 0
                matched_count = media.count()
                for media_item in media:
                    for tag in tags:
                        _, link_created = MediaTag.objects.get_or_create(media=media_item, tag=tag)
                        if link_created:
                            tag_links_created += 1

                message = (
                    f'Applied {len(tag_names)} tag{"s" if len(tag_names) != 1 else ""} '
                    f"to {matched_count} filtered media file{'s' if matched_count != 1 else ''}."
                )
                if tag_links_created:
                    message += f" Created {tag_links_created} new tag link{'s' if tag_links_created != 1 else ''}."
                if claimed_tag_count:
                    message += f" Claimed {claimed_tag_count} loose tag{'s' if claimed_tag_count != 1 else ''} for your account."
                messages.success(request, message)
            return_query = urlencode(
                {
                    "q": q,
                    "client_id": client_id,
                    "tag_id": tag_id,
                    **({"tags": "1"} if search_state["tags"] else {}),
                    **({"metadata": "1"} if search_state["metadata"] else {}),
                }
            )
            target = reverse("dashboard_project_detail", args=[project.id])
            return redirect(f"{target}?{return_query}" if return_query else target)

        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()

        if not first_name or not last_name:
            messages.error(request, "Client first and last name are required.")
        else:
            Customer.objects.create(
                project=project,
                company_name=(request.POST.get("company_name") or "").strip(),
                first_name=first_name,
                last_name=last_name,
                email=(request.POST.get("email") or "").strip(),
                phone=(request.POST.get("phone") or "").strip(),
            )
            messages.success(request, "Client added to project.")
            return redirect("dashboard_project_detail", project_id=project.id)

    media = _project_media_queryset(project, q=q, client_id=client_id, tag_id=tag_id, search_state=search_state)

    return render(
        request,
        "base/dashboard_project_detail.html",
        {
            "project": project,
            "clients": project.customers.order_by("company_name", "last_name", "first_name"),
            "media_list": media,
            "media_count": media.count(),
            "tag_options": Tag.objects.filter(media__project=project).order_by("name").distinct(),
            "filters": {"q": q, "client_id": client_id, "tag_id": tag_id},
            **_base_context(search_state),
        },
    )


def dashboard_client_detail(request, client_id):
    client = get_object_or_404(
        Customer.objects.select_related("project").annotate(
            project_media_total=Count("project__media", distinct=True),
            project_tag_total=Count("project__media__tags", distinct=True),
        ),
        id=client_id,
    )

    media_list = (
        client.project.media.select_related("metadata", "batch")
        .prefetch_related("tags")
        .order_by("file_name")
    )

    return render(
        request,
        "base/dashboard_client_detail.html",
        {
            "client": client,
            "project": client.project,
            "media_list": media_list,
            "media_count": media_list.count(),
            "project_clients": client.project.customers.order_by("company_name", "last_name", "first_name"),
            **_base_context(),
        },
    )


def dashboard_tags(request):
    if request.method == "POST":
        action = request.POST.get("action") or "create_tags"

        if action == "adopt_tag":
            if not request.user.is_authenticated:
                messages.error(request, "Sign in before adopting loose tags.")
                return redirect("dashboard_tags")

            tag_id = request.POST.get("tag_id") or ""
            loose_tag = Tag.objects.filter(id=tag_id, user__isnull=True).first()
            if loose_tag is None:
                messages.error(request, "That loose tag is no longer available.")
                return redirect("dashboard_tags")

            adopted_tag, adopted, moved_links = _adopt_loose_tag_for_user(loose_tag, request.user)
            if not adopted:
                messages.error(request, "That tag could not be adopted.")
            else:
                message = f'Adopted "{adopted_tag.name}" for your account.'
                if moved_links:
                    message += f" Preserved {moved_links} media link{'s' if moved_links != 1 else ''}."
                messages.success(request, message)
            return redirect("dashboard_tags")

        tag_names = _parse_tags(request.POST.get("tags"))
        if not tag_names:
            messages.error(request, "Enter at least one tag to create.")
        else:
            tags, claimed_tag_count = _resolve_tags_for_user(tag_names, request.user)
            message = f'Ready to use {len(tags)} tag{"s" if len(tags) != 1 else ""}.'
            if claimed_tag_count:
                message += f" Claimed {claimed_tag_count} loose tag{'s' if claimed_tag_count != 1 else ''} for your account."
            messages.success(request, message)
            return redirect("dashboard_tags")

    q = (request.GET.get("q") or "").strip()
    creator = (request.GET.get("creator") or "").strip()
    project_id = (request.GET.get("project_id") or "").strip()

    tags = (
        Tag.objects.select_related("user")
        .annotate(
            media_total=Count("media", distinct=True),
            project_total=Count("media__project", distinct=True),
            client_total=Count("media__project__customers", distinct=True),
        )
        .prefetch_related("media__project__customers", "media__project")
        .order_by("name")
    )
    terms = _search_terms(q)
    if terms:
        tags = tags.filter(
            _any_term_query(
                terms,
                lambda term: Q(name__icontains=term) | Q(media__file_name__icontains=term),
            )
        ).distinct()
    if creator == "me" and request.user.is_authenticated:
        tags = tags.filter(user=request.user)
    elif creator == "loose":
        tags = tags.filter(user__isnull=True)
    if project_id.isdigit():
        tags = tags.filter(media__project_id=int(project_id)).distinct()

    for tag in tags:
        related_projects = []
        seen_project_ids = set()
        related_clients = []
        seen_client_ids = set()

        for media in tag.media.all():
            project = media.project
            if project and project.id not in seen_project_ids:
                seen_project_ids.add(project.id)
                related_projects.append(project)

            if project:
                for client in project.customers.all():
                    if client.id not in seen_client_ids:
                        seen_client_ids.add(client.id)
                        related_clients.append(client)

        tag.related_projects = related_projects[:3]
        tag.related_clients = related_clients[:4]

    return render(
        request,
        "base/dashboard_tags.html",
        {
            "tags": tags,
            "projects": Project.objects.order_by("name"),
            "filters": {"q": q, "creator": creator, "project_id": project_id},
            **_base_context(),
        },
    )


def dashboard_media(request):
    q = (request.GET.get("q") or "").strip()
    project_id = (request.GET.get("project_id") or "").strip()
    client_id = (request.GET.get("client_id") or "").strip()
    tag_id = (request.GET.get("tag_id") or "").strip()
    search_state = _search_state_from_request(request)

    media = (
        Media.objects.select_related("project", "metadata", "batch")
        .prefetch_related("tags", "project__customers")
        .order_by("project__name", "file_name")
    )

    terms = _search_terms(q)
    if terms:
        media = media.filter(
            _any_term_query(
                terms,
                lambda term: (
                    Q(file_name__icontains=term)
                    | Q(file_path__icontains=term)
                    | ((Q(project__name__icontains=term) | Q(project__location__icontains=term)) if search_state["projects"] else Q())
                    | (
                        (
                            Q(project__customers__company_name__icontains=term)
                            | Q(project__customers__first_name__icontains=term)
                            | Q(project__customers__last_name__icontains=term)
                        ) if search_state["clients"] else Q()
                    )
                    | (Q(tags__name__icontains=term) if search_state["tags"] else Q())
                    | (
                        (
                            Q(metadata__file_type__icontains=term)
                            | Q(metadata__codec__icontains=term)
                            | Q(metadata__color_space__icontains=term)
                            | Q(metadata__aspect_ratio__icontains=term)
                        ) if search_state["metadata"] else Q()
                    )
                ),
            )
        ).distinct()

    if project_id.isdigit():
        media = media.filter(project_id=int(project_id))
    if client_id.isdigit():
        media = media.filter(project__customers__id=int(client_id)).distinct()
    if tag_id.isdigit():
        media = media.filter(tags__id=int(tag_id)).distinct()

    return render(
        request,
        "base/dashboard_media.html",
        {
            "media_list": media,
            "projects": Project.objects.order_by("name"),
            "clients": Customer.objects.select_related("project").order_by("company_name", "last_name", "first_name"),
            "tags": Tag.objects.order_by("name"),
            "filters": {
                "q": q,
                "project_id": project_id,
                "client_id": client_id,
                "tag_id": tag_id,
            },
            **_base_context(search_state),
        },
    )


def dashboard_media_detail(request, media_id):
    media = get_object_or_404(
        Media.objects.select_related("project", "metadata", "batch").prefetch_related("tags", "project__customers"),
        id=media_id,
    )

    if request.method == "POST":
        tag_names = _parse_tags(request.POST.get("tags"))
        if not tag_names:
            messages.error(request, "Enter at least one tag to add to this media.")
        else:
            tags, claimed_tag_count = _resolve_tags_for_user(tag_names, request.user)
            created_links = 0
            for tag in tags:
                _, created = MediaTag.objects.get_or_create(media=media, tag=tag)
                if created:
                    created_links += 1

            message = f'Added {len(tag_names)} tag{"s" if len(tag_names) != 1 else ""} to "{media.file_name}".'
            if created_links:
                message += f" Created {created_links} new tag link{'s' if created_links != 1 else ''}."
            if claimed_tag_count:
                message += f" Claimed {claimed_tag_count} loose tag{'s' if claimed_tag_count != 1 else ''} for your account."
            messages.success(request, message)
            return redirect("dashboard_media_detail", media_id=media.id)

    return render(
        request,
        "base/dashboard_media_detail.html",
        {
            "media": media,
            "project_clients": media.project.customers.order_by("company_name", "last_name", "first_name") if media.project else [],
            **_base_context(),
        },
    )

def dashboard_batch_assign_project(request, batch_id):
    if request.method != "POST":
        return redirect("dashboard_batch_detail", batch_id=batch_id)

    batch = get_object_or_404(Batch, id=batch_id)
    form_state = _batch_assignment_state(request.POST)
    project_id = form_state["project_id"]
    new_project_name = form_state["new_project_name"]
    create_client = form_state["create_client"]
    tag_names = form_state["tags"]
    errors = []

    project = None
    if new_project_name:
        project = Project.objects.create(name=new_project_name)
    elif project_id.isdigit():
        project = Project.objects.filter(id=int(project_id)).first()

    if not project and not tag_names:
        errors.append("Choose an existing project or enter a new project name.")

    if create_client:
        if not new_project_name:
            errors.append("Create a new project to add a client in the same step.")
        if not form_state["first_name"]:
            errors.append("Client first name is required when Create client is enabled.")
        if not form_state["last_name"]:
            errors.append("Client last name is required when Create client is enabled.")

    if errors:
        return _render_batch_detail(
            request,
            batch_id,
            assignment_form=form_state,
            assignment_errors=errors,
            status_code=400,
        )

    if create_client:
        Customer.objects.create(
            project=project,
            company_name=form_state["company_name"],
            first_name=form_state["first_name"],
            last_name=form_state["last_name"],
            email=form_state["email"],
            phone=form_state["phone"],
        )

    media_qs = Media.objects.filter(batch=batch)
    updated_count = 0
    if project:
        updated_count = media_qs.update(project=project)

    tag_links_created = 0
    claimed_tag_count = 0
    if tag_names:
        tags, claimed_tag_count = _resolve_tags_for_user(tag_names, request.user)
        for media in media_qs:
            for tag in tags:
                _, link_created = MediaTag.objects.get_or_create(media=media, tag=tag)
                if link_created:
                    tag_links_created += 1

    message_parts = []
    if project:
        message_parts.append(
            f'Assigned {updated_count} file{"s" if updated_count != 1 else ""} in Batch #{batch.id} to "{project.name}"'
        )
    if tag_names:
        message_parts.append(
            f'added {len(tag_names)} tag{"s" if len(tag_names) != 1 else ""} ({", ".join(tag_names)})'
        )
    if tag_links_created:
        message_parts.append(f"created {tag_links_created} new tag link{'s' if tag_links_created != 1 else ''}")
    if claimed_tag_count:
        message_parts.append(f"claimed {claimed_tag_count} loose tag{'s' if claimed_tag_count != 1 else ''} for your account")

    messages.success(request, ". ".join(message_parts) + ".")

    if project and not _batch_has_unassigned_media(batch.id):
        messages.info(request, f'Batch #{batch.id} is fully assigned and has been removed from the active queue.')
        return redirect("dashboard_home")

    return redirect("dashboard_batch_detail", batch_id=batch_id)



# API STUFF

def _json(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return {}


def _resolve_media_target(media_id=None, file_path=None):
    media = None
    target_file_path = (file_path or "").strip()

    if media_id:
        media = Media.objects.filter(id=media_id).first()
        if media and not target_file_path:
            target_file_path = media.file_path

    if media is None and target_file_path:
        media = Media.objects.filter(file_path=target_file_path).first()

    return media, target_file_path


def _normalize_metadata_payload(raw):
    def to_bool(value):
        if value in (None, ""):
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
            return None
        return bool(value)

    def to_int(value):
        if value in (None, "", "N/A"):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def to_decimal(value):
        if value in (None, "", "N/A"):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    def to_duration(value):
        if value in (None, "", "N/A"):
            return None
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            return None
        if seconds < 0:
            return None
        return timedelta(seconds=seconds)

    imported_at = raw.get("imported_at")
    if imported_at:
        try:
            imported_at = datetime.fromisoformat(str(imported_at))
            if timezone.is_naive(imported_at):
                imported_at = timezone.make_aware(imported_at, timezone.get_current_timezone())
        except (TypeError, ValueError):
            imported_at = timezone.now()
    else:
        imported_at = timezone.now()

    return {
        "file_type": str(raw.get("file_type") or "")[:90],
        "file_size": to_int(raw.get("file_size")),
        "imported_at": imported_at,
        "has_color_grade": bool(raw.get("has_color_grade", False)),
        "hdr": to_bool(raw.get("hdr")),
        "frame_rate": to_decimal(raw.get("frame_rate")),
        "codec": str(raw.get("codec") or "")[:90],
        "duration": to_duration(raw.get("duration")),
        "width": to_int(raw.get("width")),
        "height": to_int(raw.get("height")),
        "aspect_ratio": str(raw.get("aspect_ratio") or "")[:90],
        "color_space": str(raw.get("color_space") or "")[:90],
        "bit_rate": to_int(raw.get("bit_rate")),
    }


def _save_media_metadata(media, metadata_defaults):
    metadata_obj, was_created = MediaMetadata.objects.get_or_create(media=media)
    metadata_obj.file_type = metadata_defaults["file_type"]
    metadata_obj.file_size = metadata_defaults["file_size"]
    metadata_obj.imported_at = metadata_defaults["imported_at"]
    metadata_obj.has_color_grade = metadata_defaults["has_color_grade"]
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
    return metadata_obj, was_created


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

        p = str(p).strip()[:512]
        file_name = os.path.basename(p.rstrip("\\/"))[:255]

        if not p:
            continue

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
        target_media_id = target.get("media_id")
        media, target_file_path = _resolve_media_target(
            media_id=target_media_id,
            file_path=target.get("file_path"),
        )

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
            metadata_defaults["has_color_grade"] = False
            metadata_obj, was_created = _save_media_metadata(media, metadata_defaults)

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


@csrf_exempt
def api_media_metadata_save(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    data = _json(request)
    raw_items = data.get("items")

    if isinstance(raw_items, list):
        items = raw_items
    else:
        items = [data]

    processed = []
    created_count = 0
    updated_count = 0
    missing_count = 0
    error_count = 0

    for item in items:
        media, target_file_path = _resolve_media_target(
            media_id=item.get("media_id"),
            file_path=item.get("file_path"),
        )

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

        raw_metadata = item.get("metadata")
        if not isinstance(raw_metadata, dict):
            error_count += 1
            processed.append(
                {
                    "media_id": media.id,
                    "file_path": target_file_path or media.file_path,
                    "status": "error",
                    "detail": "metadata object required",
                }
            )
            continue

        metadata_defaults = _normalize_metadata_payload(raw_metadata)
        metadata_obj, was_created = _save_media_metadata(media, metadata_defaults)

        if was_created:
            created_count += 1
        else:
            updated_count += 1

        processed.append(
            {
                "media_id": media.id,
                "file_path": target_file_path or media.file_path,
                "status": "created" if was_created else "updated",
                "file_type": metadata_obj.file_type,
                "width": metadata_obj.width,
                "height": metadata_obj.height,
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
