import random
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import PureWindowsPath
from typing import Iterable

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from .models import Batch, Customer, Media, MediaMetadata, MediaTag, Project, ProjectUser, Tag


DEFAULT_PASSWORD = "presentation-demo"

FIRST_NAMES = [
    "Avery",
    "Jordan",
    "Taylor",
    "Morgan",
    "Reese",
    "Casey",
    "Drew",
    "Parker",
    "Quinn",
    "Sawyer",
    "Rowan",
    "Hayden",
]

LAST_NAMES = [
    "Bennett",
    "Reed",
    "Morris",
    "Stone",
    "Carter",
    "Hayes",
    "Turner",
    "Lopez",
    "Price",
    "Brooks",
    "Graham",
    "Perry",
]

LOCATIONS = [
    "Chicago",
    "Dallas",
    "Denver",
    "Atlanta",
    "Seattle",
    "Nashville",
    "Austin",
    "Phoenix",
]

COMPANY_PREFIXES = [
    "North Shore",
    "Atlas",
    "Blue Orbit",
    "Summit",
    "Fieldhouse",
    "Copperline",
    "Lumen",
    "Beacon",
]

COMPANY_SUFFIXES = [
    "Studios",
    "Media",
    "Collective",
    "Creative",
    "Brands",
    "Post",
    "Productions",
]

PROJECT_PREFIXES = [
    "Spring",
    "Launch",
    "Studio",
    "Campaign",
    "Archive",
    "Cutdown",
    "Spotlight",
    "Showcase",
]

PROJECT_FOCUSES = [
    "Warehouse",
    "Lake",
    "Retail",
    "Campus",
    "Product",
    "Conference",
    "Interview",
    "Recruiting",
    "Safety",
    "Brand",
]

PROJECT_SUFFIXES = [
    "Refresh",
    "Push",
    "Library",
    "Series",
    "Rollout",
    "Package",
    "Delivery",
    "Highlights",
]

DEFAULT_TAGS = [
    "warehouse",
    "interview",
    "hero",
    "social",
    "cutdown",
    "approved",
    "review",
    "camera-a",
    "camera-b",
    "drone",
    "broll",
    "graphics",
    "retouch",
    "color",
    "day-one",
    "launch",
    "thumbnail",
    "stills",
    "audio",
    "voiceover",
    "subtitles",
    "outdoor",
    "indoors",
    "product",
    "sizzle",
    "finals",
    "archived",
    "marketing",
]

VIDEO_EXTENSIONS = ["mp4", "mov", "mxf"]
IMAGE_EXTENSIONS = ["jpg", "png", "tif", "webp"]
AUDIO_EXTENSIONS = ["wav", "mp3", "aac"]

VIDEO_STEMS = [
    "hero-cut",
    "social-teaser",
    "interview-master",
    "drone-pass",
    "broll-select",
    "rough-cut",
    "final-delivery",
]

IMAGE_STEMS = [
    "key-art",
    "thumbnail-set",
    "behind-scenes",
    "poster-frame",
    "still-select",
]

AUDIO_STEMS = [
    "voiceover",
    "music-bed",
    "mixdown",
    "radio-cut",
]

VIDEO_PROFILES = [
    {"width": 3840, "height": 2160, "aspect_ratio": "16:9", "frame_rate": Decimal("23.976"), "codec": "prores", "color_space": "Rec.709"},
    {"width": 1920, "height": 1080, "aspect_ratio": "16:9", "frame_rate": Decimal("29.970"), "codec": "h264", "color_space": "Rec.709"},
    {"width": 1920, "height": 1080, "aspect_ratio": "16:9", "frame_rate": Decimal("59.940"), "codec": "hevc", "color_space": "Rec.2020"},
    {"width": 1080, "height": 1920, "aspect_ratio": "9:16", "frame_rate": Decimal("30.000"), "codec": "h264", "color_space": "Rec.709"},
]

IMAGE_PROFILES = [
    {"width": 6000, "height": 4000, "aspect_ratio": "3:2", "codec": "jpeg", "color_space": "sRGB"},
    {"width": 3840, "height": 2160, "aspect_ratio": "16:9", "codec": "png", "color_space": "Display P3"},
    {"width": 2400, "height": 3000, "aspect_ratio": "4:5", "codec": "tiff", "color_space": "Adobe RGB"},
]

AUDIO_PROFILES = [
    {"codec": "pcm_s24le"},
    {"codec": "aac"},
    {"codec": "mp3"},
]

SAFE_ROOTS = [
    PureWindowsPath(r"D:\PresentationAssets"),
    PureWindowsPath(r"E:\DemoMediaVault"),
    PureWindowsPath(r"\\NAS-DEMO\ingest"),
]


@dataclass
class ExistingPatterns:
    tag_names: list[str]
    project_terms: list[str]
    extension_weights: dict[str, int]
    codec_weights: dict[str, int]


@dataclass
class SeedStats:
    users_created: int = 0
    projects_created: int = 0
    customers_created: int = 0
    project_users_created: int = 0
    tags_created: int = 0
    batches_created: int = 0
    media_created: int = 0
    metadata_created: int = 0
    media_tag_links_created: int = 0
    sampled_existing_tags: int = 0
    sampled_existing_media: int = 0
    sampled_existing_projects: int = 0
    unassigned_media_created: int = 0
    active_batch_count: int = 0
    demo_usernames: list[str] | None = None

    def as_dict(self):
        return {
            "users_created": self.users_created,
            "projects_created": self.projects_created,
            "customers_created": self.customers_created,
            "project_users_created": self.project_users_created,
            "tags_created": self.tags_created,
            "batches_created": self.batches_created,
            "media_created": self.media_created,
            "metadata_created": self.metadata_created,
            "media_tag_links_created": self.media_tag_links_created,
            "sampled_existing_tags": self.sampled_existing_tags,
            "sampled_existing_media": self.sampled_existing_media,
            "sampled_existing_projects": self.sampled_existing_projects,
            "unassigned_media_created": self.unassigned_media_created,
            "active_batch_count": self.active_batch_count,
            "demo_usernames": self.demo_usernames or [],
        }


def _weighted_choice(rng: random.Random, weights: dict[str, int], fallback: list[str]) -> str:
    if weights:
        keys = list(weights.keys())
        return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]
    return rng.choice(fallback)


def _tokenize_names(values: Iterable[str], minimum_length: int = 4) -> list[str]:
    tokens: list[str] = []
    for value in values:
        for raw in slugify(value).split("-"):
            token = raw.strip().lower()
            if len(token) >= minimum_length and token not in {"project", "media", "demo", "test"}:
                tokens.append(token)
    return sorted(set(tokens))


def collect_existing_patterns() -> ExistingPatterns:
    extension_counts: Counter[str] = Counter()
    codec_counts: Counter[str] = Counter()

    tag_names = [name for name in Tag.objects.values_list("name", flat=True) if name]
    project_terms = _tokenize_names(Project.objects.values_list("name", flat=True))

    for file_name, file_path in Media.objects.values_list("file_name", "file_path"):
        source = (file_name or file_path or "").lower().rsplit(".", 1)
        if len(source) == 2 and source[1]:
            extension_counts[source[1]] += 1

    for codec in MediaMetadata.objects.exclude(codec="").values_list("codec", flat=True):
        codec_counts[str(codec).lower()] += 1

    return ExistingPatterns(
        tag_names=sorted(set(tag_names)),
        project_terms=project_terms,
        extension_weights=dict(extension_counts),
        codec_weights=dict(codec_counts),
    )


def _make_username(index: int) -> str:
    return f"demo_user_{index:02d}"


def _build_company_name(rng: random.Random) -> str:
    return f"{rng.choice(COMPANY_PREFIXES)} {rng.choice(COMPANY_SUFFIXES)}"


def _build_project_name(rng: random.Random, project_terms: list[str], index: int) -> str:
    term_pool = PROJECT_FOCUSES + project_terms
    return f"{rng.choice(PROJECT_PREFIXES)} {rng.choice(term_pool).title()} {rng.choice(PROJECT_SUFFIXES)} {index}"


def _safe_tag_pool(existing: ExistingPatterns) -> list[str]:
    pooled = set(DEFAULT_TAGS)
    for tag in existing.tag_names:
        slug = slugify(tag).replace("-", "_")
        if slug and len(slug) <= 24:
            pooled.add(slug.replace("_", "-"))
    return sorted(pooled)


def _choose_extension_for_type(rng: random.Random, media_type: str, existing: ExistingPatterns) -> str:
    allowed = {
        "video": VIDEO_EXTENSIONS,
        "image": IMAGE_EXTENSIONS,
        "audio": AUDIO_EXTENSIONS,
    }[media_type]
    weights = {ext: existing.extension_weights.get(ext, 0) for ext in allowed if existing.extension_weights.get(ext, 0)}
    return _weighted_choice(rng, weights, allowed)


def _sample_media_type(rng: random.Random) -> str:
    return rng.choices(["video", "image", "audio"], weights=[60, 30, 10], k=1)[0]


def _build_media_name(rng: random.Random, project_name: str, media_type: str, index: int, extension: str) -> str:
    stem_pool = {
        "video": VIDEO_STEMS,
        "image": IMAGE_STEMS,
        "audio": AUDIO_STEMS,
    }[media_type]
    project_slug = slugify(project_name) or "project"
    stem = rng.choice(stem_pool)
    return f"{project_slug}_{stem}_{index:03d}.{extension}"


def _build_file_path(rng: random.Random, project_name: str, file_name: str, created_on: datetime) -> str:
    root = rng.choice(SAFE_ROOTS)
    project_dir = slugify(project_name).replace("-", "_") or "project"
    folder = root / project_dir / str(created_on.year) / f"{created_on.month:02d}-{created_on.day:02d}"
    return str(folder / file_name)


def _timestamp_for_index(base_date: date, index: int, rng: random.Random) -> datetime:
    moment = datetime.combine(base_date + timedelta(days=index % 75), time(hour=8 + (index % 8), minute=rng.randrange(0, 60)))
    return timezone.make_aware(moment, timezone.get_current_timezone())


def _metadata_kwargs(rng: random.Random, media_type: str, existing: ExistingPatterns, imported_at: datetime) -> dict:
    if media_type == "video":
        profile = rng.choice(VIDEO_PROFILES)
        codec = _weighted_choice(rng, existing.codec_weights, [p["codec"] for p in VIDEO_PROFILES])
        duration_seconds = rng.randint(12, 540)
        return {
            "file_type": "video",
            "file_size": rng.randint(50_000_000, 12_000_000_000),
            "imported_at": imported_at,
            "has_color_grade": rng.choice([True, False]),
            "hdr": rng.choice([True, False, None]),
            "frame_rate": profile["frame_rate"],
            "codec": codec,
            "duration": timedelta(seconds=duration_seconds),
            "width": profile["width"],
            "height": profile["height"],
            "aspect_ratio": profile["aspect_ratio"],
            "color_space": profile["color_space"],
            "bit_rate": rng.randint(3_000_000, 75_000_000),
        }

    if media_type == "image":
        profile = rng.choice(IMAGE_PROFILES)
        return {
            "file_type": "image",
            "file_size": rng.randint(800_000, 45_000_000),
            "imported_at": imported_at,
            "has_color_grade": rng.choice([True, False]),
            "hdr": rng.choice([True, False, None]),
            "frame_rate": None,
            "codec": profile["codec"],
            "duration": None,
            "width": profile["width"],
            "height": profile["height"],
            "aspect_ratio": profile["aspect_ratio"],
            "color_space": profile["color_space"],
            "bit_rate": None,
        }

    profile = rng.choice(AUDIO_PROFILES)
    duration_seconds = rng.randint(8, 320)
    return {
        "file_type": "audio",
        "file_size": rng.randint(250_000, 22_000_000),
        "imported_at": imported_at,
        "has_color_grade": False,
        "hdr": None,
        "frame_rate": None,
        "codec": profile["codec"],
        "duration": timedelta(seconds=duration_seconds),
        "width": None,
        "height": None,
        "aspect_ratio": None,
        "color_space": "",
        "bit_rate": rng.randint(128_000, 1_536_000),
    }


def seed_presentation_data(
    *,
    seed: int = 42,
    total_users: int = 6,
    total_projects: int = 8,
    total_media: int = 48,
    total_tags: int = 20,
    active_batches: int = 2,
    metadata_coverage: float = 0.8,
    reuse_existing_patterns: bool = True,
) -> SeedStats:
    rng = random.Random(seed)
    existing = collect_existing_patterns() if reuse_existing_patterns else ExistingPatterns([], [], {}, {})
    stats = SeedStats(
        sampled_existing_tags=len(existing.tag_names),
        sampled_existing_media=Media.objects.count() if reuse_existing_patterns else 0,
        sampled_existing_projects=Project.objects.count() if reuse_existing_patterns else 0,
        demo_usernames=[],
    )

    User = get_user_model()
    users = list(User.objects.order_by("id"))
    next_user_index = len(users) + 1
    while len(users) < total_users:
        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)
        username = _make_username(next_user_index)
        user = User.objects.create_user(
            username=username,
            password=DEFAULT_PASSWORD,
            first_name=first_name,
            last_name=last_name,
            email=f"{username}@demo.local",
        )
        users.append(user)
        stats.users_created += 1
        stats.demo_usernames.append(username)
        next_user_index += 1

    projects: list[Project] = []
    project_terms = existing.project_terms[:]
    for index in range(1, total_projects + 1):
        project = Project.objects.create(
            name=_build_project_name(rng, project_terms, index),
            location=rng.choice(LOCATIONS),
        )
        project.start_date = date(2026, 1, 1) + timedelta(days=index * 3)
        project.save(update_fields=["start_date"])
        projects.append(project)
        stats.projects_created += 1

        assigned_users = rng.sample(users, k=min(len(users), rng.randint(1, min(3, len(users)))))
        for position, user in enumerate(assigned_users):
            _, created = ProjectUser.objects.get_or_create(
                project=project,
                user=user,
                defaults={"role": "Owner" if position == 0 else rng.choice(["Editor", "Reviewer", "Producer"])},
            )
            if created:
                stats.project_users_created += 1

        customer_count = rng.randint(1, 3)
        for customer_index in range(customer_count):
            first_name = rng.choice(FIRST_NAMES)
            last_name = rng.choice(LAST_NAMES)
            company_name = _build_company_name(rng)
            customer = Customer.objects.create(
                project=project,
                company_name=company_name,
                first_name=first_name,
                last_name=last_name,
                email=f"{slugify(company_name)}.{customer_index + 1}@example.com",
                phone=f"555-{rng.randint(100, 999):03d}-{rng.randint(1000, 9999):04d}",
            )
            stats.customers_created += 1
            if customer.company_name:
                project_terms.extend(_tokenize_names([customer.company_name], minimum_length=5))

    tag_pool = _safe_tag_pool(existing)
    loose_tag_count = max(1, total_tags // 3)
    loose_names = rng.sample(tag_pool, k=min(len(tag_pool), loose_tag_count))
    created_tags: list[Tag] = []

    for name in loose_names:
        tag = Tag.objects.create(name=name)
        created_tags.append(tag)
        stats.tags_created += 1

    remaining_tag_count = max(0, total_tags - len(loose_names))
    for index in range(remaining_tag_count):
        owner = users[index % len(users)] if users else None
        candidate = tag_pool[index % len(tag_pool)]
        name = f"{candidate}-{(index // max(1, len(tag_pool))) + 1}" if Tag.objects.filter(user=owner, name=candidate).exists() else candidate
        tag = Tag.objects.create(user=owner, name=name)
        created_tags.append(tag)
        stats.tags_created += 1

    open_batches = [Batch.objects.create() for _ in range(active_batches)]
    stats.batches_created += len(open_batches)
    stats.active_batch_count = len(open_batches)

    closed_batch = Batch.objects.create()
    closed_batch.closed_at = timezone.now() - timedelta(days=2)
    closed_batch.save(update_fields=["closed_at"])
    stats.batches_created += 1

    unassigned_target = min(total_media, max(active_batches * 4, total_media // 5))
    used_paths = set(Media.objects.values_list("file_path", flat=True))

    for index in range(1, total_media + 1):
        assigned_to_project = index > unassigned_target or not open_batches
        media_type = _sample_media_type(rng)
        project = rng.choice(projects) if assigned_to_project else None
        batch = None
        if not assigned_to_project:
            batch = open_batches[(index - 1) % len(open_batches)]
        elif rng.random() < 0.35:
            batch = closed_batch

        project_name = project.name if project else "Incoming Batch"
        created_at = _timestamp_for_index(date(2026, 1, 5), index, rng)
        extension = _choose_extension_for_type(rng, media_type, existing)
        file_name = _build_media_name(rng, project_name, media_type, index, extension)
        file_path = _build_file_path(rng, project_name, file_name, created_at)

        while file_path in used_paths:
            file_name = _build_media_name(rng, project_name, media_type, index + rng.randint(100, 999), extension)
            file_path = _build_file_path(rng, project_name, file_name, created_at)
        used_paths.add(file_path)

        media = Media.objects.create(
            batch=batch,
            project=project,
            file_name=file_name,
            file_path=file_path,
        )
        media.created_at = created_at
        media.save(update_fields=["created_at"])
        stats.media_created += 1
        if project is None:
            stats.unassigned_media_created += 1

        if created_tags:
            selected_tags = rng.sample(created_tags, k=min(len(created_tags), rng.randint(2, min(5, len(created_tags)))))
            for tag in selected_tags:
                _, created = MediaTag.objects.get_or_create(media=media, tag=tag)
                if created:
                    stats.media_tag_links_created += 1

        if rng.random() <= metadata_coverage:
            MediaMetadata.objects.create(
                media=media,
                **_metadata_kwargs(rng, media_type, existing, created_at + timedelta(minutes=rng.randint(1, 180))),
            )
            stats.metadata_created += 1

    return stats


class DryRunRollback(Exception):
    pass


def run_seed_in_transaction(**kwargs) -> SeedStats:
    dry_run = kwargs.pop("dry_run", False)
    try:
        with transaction.atomic():
            stats = seed_presentation_data(**kwargs)
            if dry_run:
                raise DryRunRollback()
            return stats
    except DryRunRollback:
        return stats
