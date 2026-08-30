"""Stand-ins for the user JWTAuthMiddleware puts on the scope.

The consumers only read `is_authenticated` and `pk`, so the websocket tests
stay off the database.
"""


class FakePlayerUser:
    is_authenticated = True

    def __init__(self, user_id: int) -> None:
        self.pk = user_id


class FakeAnonymousUser:
    is_authenticated = False
