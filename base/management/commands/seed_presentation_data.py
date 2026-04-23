import json

from django.core.management.base import BaseCommand, CommandError

from ...demo_seed import DEFAULT_PASSWORD, run_seed_in_transaction


class Command(BaseCommand):
    help = "Generate presentation-safe demo data for the video asset tracker."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=42, help="Random seed for repeatable demo data.")
        parser.add_argument("--users", type=int, default=6, help="Total users to target after seeding.")
        parser.add_argument("--projects", type=int, default=8, help="Projects to create.")
        parser.add_argument("--media", type=int, default=48, help="Media rows to create.")
        parser.add_argument("--tags", type=int, default=20, help="Tags to create.")
        parser.add_argument("--active-batches", type=int, default=2, help="Open batches with unassigned media.")
        parser.add_argument(
            "--metadata-coverage",
            type=float,
            default=0.8,
            help="Fraction of generated media that should get metadata rows.",
        )
        parser.add_argument(
            "--reuse-existing-patterns",
            action="store_true",
            default=True,
            help="Bias tags, names, extensions, and codecs using data already in the current database.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview the generated counts without saving any records.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the summary as JSON.",
        )

    def handle(self, *args, **options):
        if options["users"] < 1:
            raise CommandError("--users must be at least 1.")
        if options["projects"] < 1:
            raise CommandError("--projects must be at least 1.")
        if options["media"] < 0 or options["tags"] < 0 or options["active_batches"] < 0:
            raise CommandError("--media, --tags, and --active-batches cannot be negative.")
        if not 0 <= options["metadata_coverage"] <= 1:
            raise CommandError("--metadata-coverage must be between 0 and 1.")

        stats = run_seed_in_transaction(
            seed=options["seed"],
            total_users=options["users"],
            total_projects=options["projects"],
            total_media=options["media"],
            total_tags=options["tags"],
            active_batches=options["active_batches"],
            metadata_coverage=options["metadata_coverage"],
            reuse_existing_patterns=options["reuse_existing_patterns"],
            dry_run=options["dry_run"],
        )

        summary = {
            "seed": options["seed"],
            "dry_run": bool(options["dry_run"]),
            "reuse_existing_patterns": bool(options["reuse_existing_patterns"]),
            "default_password_for_new_demo_users": DEFAULT_PASSWORD if stats.demo_usernames else "",
            **stats.as_dict(),
        }

        if options["json"]:
            self.stdout.write(json.dumps(summary, indent=2))
            return

        prefix = "Would create" if options["dry_run"] else "Created"
        self.stdout.write(
            (
                f"{prefix} {summary['projects_created']} projects, {summary['media_created']} media rows, "
                f"{summary['metadata_created']} metadata rows, {summary['tags_created']} tags, "
                f"{summary['customers_created']} clients, and {summary['batches_created']} batches."
            )
        )
        self.stdout.write(
            (
                f"Users created: {summary['users_created']}; project-user links: {summary['project_users_created']}; "
                f"media-tag links: {summary['media_tag_links_created']}."
            )
        )
        self.stdout.write(
            (
                f"Active dashboard batches: {summary['active_batch_count']}; "
                f"unassigned batch media: {summary['unassigned_media_created']}."
            )
        )

        if options["reuse_existing_patterns"]:
            self.stdout.write(
                (
                    f"Sampled existing records before generation: "
                    f"{summary['sampled_existing_projects']} projects, "
                    f"{summary['sampled_existing_media']} media files, "
                    f"{summary['sampled_existing_tags']} tags."
                )
            )

        if stats.demo_usernames:
            self.stdout.write(
                "New demo users: "
                + ", ".join(stats.demo_usernames[:6])
                + f" (password: {DEFAULT_PASSWORD})"
            )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run only. No records were saved."))
