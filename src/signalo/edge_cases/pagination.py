from django_oapif.pagination import OapifPagination


class HighlyPaginatedPagination(OapifPagination):
    max_limit = 2
