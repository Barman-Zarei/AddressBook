from django.db.models import Q
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Contact
from .serializers import ContactSerializer


class ContactViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for contacts, always scoped to request.user.
    GET    /api/contacts/           -> list
    POST   /api/contacts/           -> create
    GET    /api/contacts/{id}/      -> retrieve
    PUT    /api/contacts/{id}/      -> update
    DELETE /api/contacts/{id}/      -> delete
    GET    /api/contacts/search/?q= -> search by name/phone/email
    """
    serializer_class = ContactSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Contact.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=False, methods=["get"])
    def search(self, request):
        query = request.query_params.get("q", "").strip()
        qs = self.get_queryset()
        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(phone__icontains=query)
                | Q(email__icontains=query)
            )
        return Response(self.get_serializer(qs, many=True).data)
