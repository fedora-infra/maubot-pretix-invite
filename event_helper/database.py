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

@upgrade_table.register(description="add a table for organizer credentials")
async def upgrade_v2(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE organizer_credentials (
            organizer TEXT NOT NULL PRIMARY KEY
            credential TEXT NOT NULL
        )"""
    )
