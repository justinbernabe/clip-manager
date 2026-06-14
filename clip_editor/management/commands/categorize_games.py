"""Assign each clip to a game Category, best-effort from the filename/path.

    python manage.py categorize_games

Re-runnable (M2M add is idempotent). The scheduled process_new_clips task does
this for new clips automatically.
"""

from django.core.management.base import BaseCommand

from files.models import Media

from ...ingest import detect_game


class Command(BaseCommand):
    help = "Categorize clips by game (from the filename)."

    def handle(self, *args, **opts):
        from files.models import Category
        from users.models import User

        owner = User.objects.filter(is_superuser=True).order_by("id").first()
        cats = {}
        assigned = skipped = 0
        qs = (Media.objects.filter(media_type="video")
              .exclude(media_file="").exclude(media_file__isnull=True))
        for media in qs.iterator():
            game = detect_game(media.media_file.name or "")
            if not game:
                skipped += 1
                continue
            if game not in cats:
                cats[game], _ = Category.objects.get_or_create(title=game, defaults={"user": owner})
            media.category.add(cats[game])
            assigned += 1
        self.stdout.write(self.style.SUCCESS(
            f"assigned {assigned}, skipped {skipped} (no game in name)."))
