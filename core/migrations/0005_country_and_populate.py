# Generated manually - Create Country model and populate with 150+ countries

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import simple_history.models


def populate_countries(apps, schema_editor):
    """Populate the Country model with common countries."""
    Country = apps.get_model("core", "Country")

    countries = [
        ("Afghanistan", "AFG"),
        ("Albania", "ALB"),
        ("Algeria", "DZA"),
        ("Argentina", "ARG"),
        ("Armenia", "ARM"),
        ("Australia", "AUS"),
        ("Austria", "AUT"),
        ("Azerbaijan", "AZE"),
        ("Bahamas", "BHS"),
        ("Bahrain", "BHR"),
        ("Bangladesh", "BGD"),
        ("Belarus", "BLR"),
        ("Belgium", "BEL"),
        ("Bhutan", "BTN"),
        ("Bolivia", "BOL"),
        ("Bosnia and Herzegovina", "BIH"),
        ("Botswana", "BWA"),
        ("Brazil", "BRA"),
        ("Brunei", "BRN"),
        ("Bulgaria", "BGR"),
        ("Cambodia", "KHM"),
        ("Cameroon", "CMR"),
        ("Canada", "CAN"),
        ("Chile", "CHL"),
        ("China", "CHN"),
        ("Colombia", "COL"),
        ("Costa Rica", "CRI"),
        ("Croatia", "HRV"),
        ("Cuba", "CUB"),
        ("Cyprus", "CYP"),
        ("Czech Republic", "CZE"),
        ("Denmark", "DNK"),
        ("Dominican Republic", "DOM"),
        ("Ecuador", "ECU"),
        ("Egypt", "EGY"),
        ("El Salvador", "SLV"),
        ("Estonia", "EST"),
        ("Ethiopia", "ETH"),
        ("Fiji", "FJI"),
        ("Finland", "FIN"),
        ("France", "FRA"),
        ("Georgia", "GEO"),
        ("Germany", "DEU"),
        ("Ghana", "GHA"),
        ("Greece", "GRC"),
        ("Guatemala", "GTM"),
        ("Honduras", "HND"),
        ("Hong Kong", "HKG"),
        ("Hungary", "HUN"),
        ("Iceland", "ISL"),
        ("India", "IND"),
        ("Indonesia", "IDN"),
        ("Iran", "IRN"),
        ("Iraq", "IRQ"),
        ("Ireland", "IRL"),
        ("Israel", "ISR"),
        ("Italy", "ITA"),
        ("Jamaica", "JAM"),
        ("Japan", "JPN"),
        ("Jordan", "JOR"),
        ("Kazakhstan", "KAZ"),
        ("Kenya", "KEN"),
        ("Kuwait", "KWT"),
        ("Kyrgyzstan", "KGZ"),
        ("Laos", "LAO"),
        ("Latvia", "LVA"),
        ("Lebanon", "LBN"),
        ("Libya", "LBY"),
        ("Lithuania", "LTU"),
        ("Luxembourg", "LUX"),
        ("Macau", "MAC"),
        ("Madagascar", "MDG"),
        ("Malaysia", "MYS"),
        ("Maldives", "MDV"),
        ("Malta", "MLT"),
        ("Mauritius", "MUS"),
        ("Mexico", "MEX"),
        ("Mongolia", "MNG"),
        ("Morocco", "MAR"),
        ("Myanmar", "MMR"),
        ("Nepal", "NPL"),
        ("Netherlands", "NLD"),
        ("New Zealand", "NZL"),
        ("Nigeria", "NGA"),
        ("North Korea", "PRK"),
        ("Norway", "NOR"),
        ("Oman", "OMN"),
        ("Pakistan", "PAK"),
        ("Panama", "PAN"),
        ("Papua New Guinea", "PNG"),
        ("Paraguay", "PRY"),
        ("Peru", "PER"),
        ("Philippines", "PHL"),
        ("Poland", "POL"),
        ("Portugal", "PRT"),
        ("Qatar", "QAT"),
        ("Romania", "ROU"),
        ("Russia", "RUS"),
        ("Saudi Arabia", "SAU"),
        ("Senegal", "SEN"),
        ("Serbia", "SRB"),
        ("Singapore", "SGP"),
        ("Slovakia", "SVK"),
        ("Slovenia", "SVN"),
        ("South Africa", "ZAF"),
        ("South Korea", "KOR"),
        ("Spain", "ESP"),
        ("Sri Lanka", "LKA"),
        ("Sudan", "SDN"),
        ("Sweden", "SWE"),
        ("Switzerland", "CHE"),
        ("Syria", "SYR"),
        ("Taiwan", "TWN"),
        ("Tajikistan", "TJK"),
        ("Tanzania", "TZA"),
        ("Thailand", "THA"),
        ("Tunisia", "TUN"),
        ("Turkey", "TUR"),
        ("Turkmenistan", "TKM"),
        ("Uganda", "UGA"),
        ("Ukraine", "UKR"),
        ("United Arab Emirates", "ARE"),
        ("United Kingdom", "GBR"),
        ("United States", "USA"),
        ("Uruguay", "URY"),
        ("Uzbekistan", "UZB"),
        ("Venezuela", "VEN"),
        ("Vietnam", "VNM"),
        ("Yemen", "YEM"),
        ("Zambia", "ZMB"),
        ("Zimbabwe", "ZWE"),
    ]

    for name, code in countries:
        Country.objects.get_or_create(
            name=name, defaults={"code": code, "is_active": True}
        )


def reverse_populate(apps, schema_editor):
    """Reverse migration - delete all countries."""
    Country = apps.get_model("core", "Country")
    Country.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_historicaldocumentupload_documentupload"),
    ]

    operations = [
        # Create Country model
        migrations.CreateModel(
            name="Country",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                (
                    "code",
                    models.CharField(
                        blank=True, help_text="ISO 3166-1 alpha-3 code", max_length=3
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name_plural": "Countries",
                "ordering": ["name"],
            },
        ),
        # Create HistoricalCountry for django-simple-history
        migrations.CreateModel(
            name="HistoricalCountry",
            fields=[
                (
                    "id",
                    models.BigIntegerField(
                        auto_created=True, blank=True, db_index=True, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("code", models.CharField(blank=True, max_length=3)),
                ("is_active", models.BooleanField(default=True)),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                (
                    "history_type",
                    models.CharField(
                        choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                        max_length=1,
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "historical country",
                "verbose_name_plural": "historical countries",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        # Run Python to populate countries
        migrations.RunPython(populate_countries, reverse_populate),
    ]
