"""Stand-in for `PlayerSettings` that fails the last insert of a signup.

Lets the rollback test break the player creation halfway through, after
the profile and the stats rows already exist.
"""

from typing import NoReturn

from django.db import DatabaseError


class FailingPlayerSettings:
    class objects:
        @staticmethod
        def create(**kwargs: object) -> NoReturn:
            raise DatabaseError(f"settings insert failed for {kwargs}")
