from rest_framework import serializers
from .models import Contact


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "name", "phone", "email", "address", "city", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        """Reject a second contact with the same name + phone for the same user."""
        user = self.context["request"].user
        name = attrs.get("name", getattr(self.instance, "name", None))
        phone = attrs.get("phone", getattr(self.instance, "phone", None))
        duplicates = Contact.objects.filter(owner=user, name=name, phone=phone)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                "You already have a contact with this name and phone number."
            )
        return attrs
