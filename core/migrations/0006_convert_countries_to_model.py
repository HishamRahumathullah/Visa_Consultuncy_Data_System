# Generated manually - Convert country fields to use Country model (SQLite-safe)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_student_nationality(apps, schema_editor):
    """Migrate existing Student.nationality (CharField) to ForeignKey(Country)."""
    Student = apps.get_model("core", "Student")
    Country = apps.get_model("core", "Country")

    for student in Student.objects.all():
        if student._old_nationality:
            try:
                country = Country.objects.get(
                    name__iexact=student._old_nationality.strip()
                )
            except Country.DoesNotExist:
                country, _ = Country.objects.get_or_create(
                    name=student._old_nationality.strip(),
                    defaults={"code": "", "is_active": True},
                )
            student.nationality = country
            student.save(update_fields=["nationality"])


def migrate_university_country(apps, schema_editor):
    """Migrate existing University.country (CharField) to ForeignKey(Country)."""
    University = apps.get_model("core", "University")
    Country = apps.get_model("core", "Country")

    for university in University.objects.all():
        if university._old_country:
            try:
                country = Country.objects.get(
                    name__iexact=university._old_country.strip()
                )
            except Country.DoesNotExist:
                country, _ = Country.objects.get_or_create(
                    name=university._old_country.strip(),
                    defaults={"code": "", "is_active": True},
                )
            university.country = country
            university.save(update_fields=["country"])


def migrate_student_preferred_countries(apps, schema_editor):
    """Migrate existing Student.preferred_countries (JSONField) to ManyToMany(Country)."""
    Student = apps.get_model("core", "Student")
    Country = apps.get_model("core", "Country")

    for student in Student.objects.all():
        if student._old_preferred_countries:
            country_names = student._old_preferred_countries
            if isinstance(country_names, str):
                import json

                try:
                    country_names = json.loads(country_names)
                except json.JSONDecodeError:
                    country_names = [country_names]

            if isinstance(country_names, list):
                for name in country_names:
                    try:
                        country = Country.objects.get(name__iexact=str(name).strip())
                        student.preferred_countries.add(country)
                    except Country.DoesNotExist:
                        country, _ = Country.objects.get_or_create(
                            name=str(name).strip(),
                            defaults={"code": "", "is_active": True},
                        )
                        student.preferred_countries.add(country)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_country_and_populate"),
    ]

    operations = [
        # Step 0: Drop problematic indexes first (SQLite-safe)
        migrations.RemoveIndex(
            model_name="university",
            name="core_univer_country_4c3a85_idx",
        ),
        migrations.RemoveIndex(
            model_name="student",
            name="core_studen_nationa_a978fd_idx",
        ),
        # Step 1: Rename old fields to preserve data
        migrations.RenameField(
            model_name="student",
            old_name="nationality",
            new_name="_old_nationality",
        ),
        migrations.RenameField(
            model_name="university",
            old_name="country",
            new_name="_old_country",
        ),
        # Step 2: Rename old JSON field BEFORE adding ManyToMany with same name
        migrations.RenameField(
            model_name="student",
            old_name="preferred_countries",
            new_name="_old_preferred_countries",
        ),
        # Step 3: Add new ForeignKey fields
        migrations.AddField(
            model_name="student",
            name="nationality",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="students_nationality",
                to="core.country",
            ),
        ),
        migrations.AddField(
            model_name="university",
            name="country",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="universities",
                to="core.country",
            ),
        ),
        # Step 4: Add ManyToMany for preferred_countries (now safe, old field renamed)
        migrations.AddField(
            model_name="student",
            name="preferred_countries",
            field=models.ManyToManyField(
                blank=True,
                related_name="students_preferred",
                to="core.country",
            ),
        ),
        # Step 5: Add JSON backup field
        migrations.AddField(
            model_name="student",
            name="_preferred_countries_json",
            field=models.JSONField(blank=True, default=list),
        ),
        # Step 6: Add data_source choices to University
        migrations.AlterField(
            model_name="university",
            name="data_source",
            field=models.CharField(
                choices=[
                    ("manual", "Manual Entry"),
                    ("ai_scraped", "AI Scraped"),
                    ("import", "Bulk Import"),
                ],
                default="manual",
                max_length=50,
            ),
        ),
        # Step 7: Update HistoricalStudent - rename old nationality field
        migrations.RenameField(
            model_name="historicalstudent",
            old_name="nationality",
            new_name="_old_nationality",
        ),
        # Step 8: Update HistoricalUniversity - rename old country field
        migrations.RenameField(
            model_name="historicaluniversity",
            old_name="country",
            new_name="_old_country",
        ),
        # Step 9: Add nationality FK to HistoricalStudent
        migrations.AddField(
            model_name="historicalstudent",
            name="nationality",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="core.country",
            ),
        ),
        # Step 10: Add country FK to HistoricalUniversity
        migrations.AddField(
            model_name="historicaluniversity",
            name="country",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="core.country",
            ),
        ),
        # Step 11: Add _preferred_countries_json to HistoricalStudent
        migrations.AddField(
            model_name="historicalstudent",
            name="_preferred_countries_json",
            field=models.JSONField(blank=True, default=list),
        ),
        # Step 12: Run data migration
        migrations.RunPython(migrate_student_nationality, migrations.RunPython.noop),
        migrations.RunPython(migrate_university_country, migrations.RunPython.noop),
        migrations.RunPython(
            migrate_student_preferred_countries, migrations.RunPython.noop
        ),
        # Step 13: Remove old fields
        migrations.RemoveField(
            model_name="student",
            name="_old_nationality",
        ),
        migrations.RemoveField(
            model_name="university",
            name="_old_country",
        ),
        migrations.RemoveField(
            model_name="student",
            name="_old_preferred_countries",
        ),
        # Step 14: Remove old fields from historical models
        migrations.RemoveField(
            model_name="historicalstudent",
            name="_old_nationality",
        ),
        migrations.RemoveField(
            model_name="historicaluniversity",
            name="_old_country",
        ),
        # Step 15: Recreate indexes with new field names
        migrations.AddIndex(
            model_name="student",
            index=models.Index(
                fields=["nationality"], name="core_studen_nationa_a978fd_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="university",
            index=models.Index(
                fields=["country", "is_active"], name="core_univer_country_4c3a85_idx"
            ),
        ),
    ]
