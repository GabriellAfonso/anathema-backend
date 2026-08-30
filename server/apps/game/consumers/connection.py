from .base import BaseConsumer


class ConnectionConsumer(BaseConsumer):
    group_prefix = "connection"
    location = "global"

    async def on_connect(self) -> None:
        await self.channel_layer.group_add(
            "online_players",
            self.channel_name,
        )

        # await self.set_heartbeat()
        await self.send_event(type='Evento de teste', payload={})

    async def on_disconnect(self, code: int) -> None:
        await self.channel_layer.group_discard(
            "online_players",
            self.channel_name,
        )

    # ---------- Handlers ----------

    # async def handle_ping(self, content):
    #     await self.set_heartbeat()

    # async def handle_set_location(self, content):
    #     location = content.get("location")

    #     if not location:
    #         return

    #     self.location = location

    #     cache.set(
    #         f"player_location:{self.user.id}",
    #         location,
    #         timeout=60,
    #     )

    #     await self.send_ok(event="location_updated", location=location)
