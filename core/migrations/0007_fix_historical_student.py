# 0007_fix_historical_student.py
# NOTE: This migration is now a no-op because 0006 was corrected to handle
# all historical model updates. Keeping this file for migration chain integrity.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_convert_countries_to_model"),
    ]

    operations = [
        # All fixes previously here are now handled in 0006
        # This migration is kept to maintain the migration chain
    ]
