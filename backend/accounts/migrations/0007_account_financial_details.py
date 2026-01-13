from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_add_enterprise_constraints"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountFinancialDetails",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=__import__("uuid").uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_accounts_accountfinancialdetails_set",
                        to="common.user",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_accounts_accountfinancialdetails_set",
                        to="common.user",
                    ),
                ),
                ("insurance_provider", models.CharField(blank=True, default="", max_length=255)),
                ("policy_number", models.CharField(blank=True, default="", max_length=64)),
                ("coverage_limit", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                (
                    "coverage_currency",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("USD", "USD, Dollar"),
                            ("EUR", "EUR, Euro"),
                            ("GBP", "GBP, Pound"),
                            ("INR", "INR, Rupee"),
                            ("CAD", "CAD, Dollar"),
                            ("AUD", "AUD, Dollar"),
                            ("JPY", "JPY, Yen"),
                            ("CNY", "CNY, Yuan"),
                            ("CHF", "CHF, Franc"),
                            ("SGD", "SGD, Dollar"),
                            ("AED", "AED, Dirham"),
                            ("BRL", "BRL, Real"),
                            ("MXN", "MXN, Peso"),
                        ],
                        help_text="Currency code for coverage_limit",
                        max_length=3,
                        null=True,
                    ),
                ),
                ("policy_effective_date", models.DateField(blank=True, null=True)),
                ("policy_expiration_date", models.DateField(blank=True, null=True)),
                (
                    "billing_currency",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("USD", "USD, Dollar"),
                            ("EUR", "EUR, Euro"),
                            ("GBP", "GBP, Pound"),
                            ("INR", "INR, Rupee"),
                            ("CAD", "CAD, Dollar"),
                            ("AUD", "AUD, Dollar"),
                            ("JPY", "JPY, Yen"),
                            ("CNY", "CNY, Yuan"),
                            ("CHF", "CHF, Franc"),
                            ("SGD", "SGD, Dollar"),
                            ("AED", "AED, Dirham"),
                            ("BRL", "BRL, Real"),
                            ("MXN", "MXN, Peso"),
                        ],
                        help_text="Preferred billing currency for this customer",
                        max_length=3,
                        null=True,
                    ),
                ),
                ("credit_limit", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ("payment_terms_days", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "account",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="financial_details",
                        to="accounts.account",
                    ),
                ),
                (
                    "org",
                    models.ForeignKey(
                        help_text="Organization/tenant scope",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="account_financial_details",
                        to="common.org",
                    ),
                ),
            ],
            options={
                "verbose_name": "Account Financial Details",
                "verbose_name_plural": "Account Financial Details",
                "db_table": "account_financial_details",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="accountfinancialdetails",
            index=models.Index(fields=["org", "-created_at"], name="account_fina_org_id_3b5e5d_idx"),
        ),
        migrations.AddIndex(
            model_name="accountfinancialdetails",
            index=models.Index(fields=["account"], name="account_fina_account_efb0d9_idx"),
        ),
        migrations.AddConstraint(
            model_name="accountfinancialdetails",
            constraint=models.UniqueConstraint(
                fields=("account",), name="unique_financial_details_per_account"
            ),
        ),
        migrations.AddConstraint(
            model_name="accountfinancialdetails",
            constraint=models.CheckConstraint(
                check=models.Q(("coverage_limit__gte", 0), _connector="OR")
                | models.Q(("coverage_limit__isnull", True)),
                name="account_finance_coverage_limit_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="accountfinancialdetails",
            constraint=models.CheckConstraint(
                check=models.Q(("credit_limit__gte", 0), _connector="OR")
                | models.Q(("credit_limit__isnull", True)),
                name="account_finance_credit_limit_non_negative",
            ),
        ),
    ]
