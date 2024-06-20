from mautrix.util.async_db import UpgradeTable, Connection

upgrade_table = UpgradeTable()

@upgrade_table.register(description="Initial revision")
async def upgrade_v1(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE event_rooms (
            organizer TEXT NOT NULL
            event TEXT NOT NULL
            room TEXT NOT NULL
            PRIMARY KEY (organizer, event, room)
        )"""
    )
