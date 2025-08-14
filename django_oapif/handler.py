from django.db import models


class QueryHandler:
    def __init__(self, model: models.Model):
        self.model = model

    def get_queryset(self, request):
        return self.model._default_manager.get_queryset()

    def save_model(self, request, obj, change: bool):
        """
        Given a model instance save it to the database.
        """
        obj.save()

    def delete_model(self, request, obj):
        """
        Given a model instance delete it from the database.
        """
        obj.delete()
