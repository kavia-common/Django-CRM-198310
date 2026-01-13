from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from activity.models import ActivityLog
from common.models import Org


class Command(BaseCommand):
    help = "Purge ActivityLog entries older than N days (optionally scoped to an org)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            required=True,
            help="Delete logs older than this many days.",
        )
        parser.add_argument(
            "--org-id",
            type=str,
            default=None,
            help="Optional organization UUID. If provided, purge only that org's logs.",
        )
        parser.add_argument(
            "--all-orgs",
            action="store_true",
            help="Purge across all orgs (use with caution).",
        )

    def handle(self, *args, **options):
        days = options["days"]
        org_id = options["org_id"]
        all_orgs = options["all_orgs"]

        if days <= 0:
            raise CommandError("--days must be > 0")

        cutoff = timezone.now() - timedelta(days=days)

        qs = ActivityLog.objects.filter(created_at__lt=cutoff)

        if org_id and all_orgs:
            raise CommandError("Use either --org-id or --all-orgs, not both.")

        if org_id:
            if not Org.objects.filter(id=org_id).exists():
                raise CommandError(f"Org {org_id} not found")
            qs = qs.filter(org_id=org_id)
        elif not all_orgs:
            raise CommandError(
                "Refusing to purge across all orgs without --all-orgs. "
                "Provide --org-id to scope the purge."
            )

        deleted_count, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_count} activity log rows"))
