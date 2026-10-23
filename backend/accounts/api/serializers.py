from rest_framework import serializers

from accounts.models import User


class MeSerializer(serializers.ModelSerializer):
    """The logged-in user, as the React app sees them."""

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role"]
        read_only_fields = fields
