# API documentation

::: django_oapif.api.OAPIF
    options:
        members: [register]


::: django_oapif.handler
    options:
        members:
            - OapifCollection
            - AllowAny
            - IsAuthenticated
            - IsAuthenticatedOrReadOnly
            - DjangoModelPermissions
            - DjangoModelPermissionsOrAnonReadOnly
