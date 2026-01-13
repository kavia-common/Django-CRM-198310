from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

import re
from decimal import Decimal

from accounts.models import Account, AccountEmail, AccountEmailLog, AccountFinancialDetails
from common.serializer import (
    AttachmentsSerializer,
    OrganizationSerializer,
    ProfileSerializer,
    TagsSerializer,
    TeamsSerializer,
    UserSerializer,
)
from contacts.serializer import ContactSerializer


# Note: Removed unused serializer properties that were computed but never used by frontend:
# - get_team_users, get_team_and_assigned_users, get_assigned_users_not_in_teams
# - created_on_arrow (frontend computes its own humanized timestamps)


class AccountSerializer(serializers.ModelSerializer):
    """Serializer for reading Account data"""

    created_by = UserSerializer()
    org = OrganizationSerializer()
    tags = TagsSerializer(read_only=True, many=True)
    assigned_to = ProfileSerializer(read_only=True, many=True)
    contacts = ContactSerializer(read_only=True, many=True)
    teams = TeamsSerializer(read_only=True, many=True)
    account_attachment = AttachmentsSerializer(read_only=True, many=True)
    country_display = serializers.SerializerMethodField()
    cases = serializers.SerializerMethodField()
    tasks = serializers.SerializerMethodField()
    opportunities = serializers.SerializerMethodField()

    @extend_schema_field(str)
    def get_country_display(self, obj):
        return obj.get_country_display() if obj.country else None

    @extend_schema_field(list)
    def get_cases(self, obj):
        """Return cases linked to this account"""
        return [{"id": str(c.id), "name": c.name} for c in obj.accounts_cases.all()]

    @extend_schema_field(list)
    def get_tasks(self, obj):
        """Return tasks linked to this account"""
        return [{"id": str(t.id), "title": t.title} for t in obj.accounts_tasks.all()]

    @extend_schema_field(list)
    def get_opportunities(self, obj):
        """Return opportunities linked to this account"""
        return [
            {
                "id": str(o.id),
                "name": o.name,
                "stage": o.stage,
                "amount": str(o.amount) if o.amount else "0",
            }
            for o in obj.opportunities.all()
        ]

    class Meta:
        model = Account
        fields = (
            "id",
            # Core Account Information
            "name",
            "email",
            "phone",
            "website",
            # Business Information
            "industry",
            "number_of_employees",
            "annual_revenue",
            "currency",
            # Address
            "address_line",
            "city",
            "state",
            "postcode",
            "country",
            "country_display",
            # Assignment
            "assigned_to",
            "teams",
            "contacts",
            # Tags
            "tags",
            # Notes
            "description",
            # Related
            "account_attachment",
            "cases",
            "tasks",
            "opportunities",
            # System
            "created_by",
            "created_at",
            "is_active",
            "org",
        )


class EmailSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class Meta:
        model = AccountEmail
        fields = (
            "message_subject",
            "message_body",
            "timezone",
            "scheduled_date_time",
            "scheduled_later",
            "created_at",
            "from_email",
            "rendered_message_body",
        )

    def validate_message_body(self, message_body):
        count = 0
        for i in message_body:
            if i == "{":
                count += 1
            elif i == "}":
                count -= 1
            if count < 0:
                raise serializers.ValidationError(
                    "Brackets do not match, Enter valid tags."
                )
        if count != 0:
            raise serializers.ValidationError(
                "Brackets do not match, Enter valid tags."
            )
        return message_body


class EmailLogSerializer(serializers.ModelSerializer):
    email = EmailSerializer()

    class Meta:
        model = AccountEmailLog
        fields = ["email", "contact", "is_sent"]


class AccountWriteSerializer(serializers.ModelSerializer):
    """Serializer for API documentation of Account write operations"""

    class Meta:
        model = Account
        fields = [
            "name",
            "phone",
            "email",
            "website",
            "industry",
            "number_of_employees",
            "annual_revenue",
            "address_line",
            "city",
            "state",
            "postcode",
            "country",
            "description",
        ]


class AccountCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating Account data"""

    def __init__(self, *args, **kwargs):
        request_obj = kwargs.pop("request_obj", None)
        kwargs.pop("account", None)  # Remove unused 'account' parameter passed by views
        super().__init__(*args, **kwargs)
        if request_obj:
            self.org = request_obj.profile.org

    def validate_name(self, name):
        if self.instance:
            if self.instance.name != name:
                if not Account.objects.filter(name__iexact=name, org=self.org).exists():
                    return name
                raise serializers.ValidationError(
                    "Account already exists with this name"
                )
            return name
        if not Account.objects.filter(name__iexact=name, org=self.org).exists():
            return name
        raise serializers.ValidationError("Account already exists with this name")

    class Meta:
        model = Account
        fields = (
            # Core Account Information
            "name",
            "email",
            "phone",
            "website",
            # Business Information
            "industry",
            "number_of_employees",
            "annual_revenue",
            "currency",
            # Address
            "address_line",
            "city",
            "state",
            "postcode",
            "country",
            # Notes
            "description",
            # Status
            "is_active",
        )

    def create(self, validated_data):
        # Default currency from org if not provided and has annual_revenue
        if not validated_data.get("currency") and validated_data.get("annual_revenue"):
            request = self.context.get("request")
            if request and hasattr(request, "profile") and request.profile.org:
                validated_data["currency"] = request.profile.org.default_currency
        return super().create(validated_data)


class AccountDetailEditSwaggerSerializer(serializers.Serializer):
    comment = serializers.CharField()
    account_attachment = serializers.FileField()


class AccountCommentEditSwaggerSerializer(serializers.Serializer):
    comment = serializers.CharField()


class EmailWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountEmail
        fields = (
            "from_email",
            "recipients",
            "message_subject",
            "scheduled_later",
            "timezone",
            "scheduled_date_time",
            "message_body",
        )


class AccountFinancialDetailsReadSerializer(serializers.ModelSerializer):
    """Serializer for reading account financial/insurance details."""

    class Meta:
        model = AccountFinancialDetails
        fields = [
            "insurance_provider",
            "policy_number",
            "coverage_limit",
            "coverage_currency",
            "policy_effective_date",
            "policy_expiration_date",
            "billing_currency",
            "credit_limit",
            "payment_terms_days",
        ]
        read_only_fields = fields


class AccountFinancialDetailsWriteSerializer(serializers.ModelSerializer):
    """
    Serializer for writing account financial/insurance details.

    Validation goals:
    - Policy number must be a reasonable token (letters/digits/-/_), max 64 chars.
    - Monetary amounts must be non-negative with 2 decimals max (DecimalField enforces scale).
    - Currency codes are constrained by choices.
    - policy_expiration_date must not be earlier than policy_effective_date when both provided.
    """

    policy_number = serializers.CharField(
        required=False, allow_blank=True, max_length=64
    )

    class Meta:
        model = AccountFinancialDetails
        fields = [
            "insurance_provider",
            "policy_number",
            "coverage_limit",
            "coverage_currency",
            "policy_effective_date",
            "policy_expiration_date",
            "billing_currency",
            "credit_limit",
            "payment_terms_days",
        ]

    def validate_policy_number(self, value: str) -> str:
        if value in (None, ""):
            return value or ""
        # Accept common policy patterns; disallow whitespace-only and special symbols.
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9\-_]{0,63}$", value):
            raise serializers.ValidationError(
                "Invalid policy_number format. Use letters/digits and optional '-' or '_' only."
            )
        return value

    def validate_coverage_limit(self, value):
        if value is None:
            return value
        if Decimal(value) < 0:
            raise serializers.ValidationError("coverage_limit must be non-negative.")
        return value

    def validate_credit_limit(self, value):
        if value is None:
            return value
        if Decimal(value) < 0:
            raise serializers.ValidationError("credit_limit must be non-negative.")
        return value

    def validate_payment_terms_days(self, value):
        if value is None:
            return value
        if value > 3650:  # 10 years is more than enough for payment terms
            raise serializers.ValidationError("payment_terms_days is unreasonably large.")
        return value

    def validate(self, attrs):
        effective = attrs.get("policy_effective_date") or getattr(
            getattr(self.instance, "policy_effective_date", None), "date", lambda: None
        )()
        expiration = attrs.get("policy_expiration_date") or getattr(
            getattr(self.instance, "policy_expiration_date", None), "date", lambda: None
        )()

        # Since DateField values are python date objects already, we can compare directly.
        if (
            attrs.get("policy_effective_date") is not None
            and attrs.get("policy_expiration_date") is not None
        ):
            effective = attrs.get("policy_effective_date")
            expiration = attrs.get("policy_expiration_date")
        else:
            effective = getattr(self.instance, "policy_effective_date", None) if self.instance else attrs.get("policy_effective_date")
            expiration = getattr(self.instance, "policy_expiration_date", None) if self.instance else attrs.get("policy_expiration_date")

        if effective and expiration and expiration < effective:
            raise serializers.ValidationError(
                {"policy_expiration_date": "Expiration date cannot be earlier than effective date."}
            )
        return attrs
