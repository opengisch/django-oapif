# API documentation

::: django_oapif.api.OAPIF
    options:
        members: [register]


::: django_oapif.permissions
    options:
        members:
            - BasePermission
            - IsAuthenticated
            - IsAdminUser
            - IsAuthenticatedOrReadOnly
            - DjangoModelPermissions
            - DjangoModelPermissionsOrAnonReadOnly
