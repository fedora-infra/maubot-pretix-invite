from typing import List


class EventRooms:

    def rooms_by_event(self, organizer:str, event:str) -> set:
        """return the set the rooms mapped to a given event

        Args:
            organizer (str): the identifier of the organizer of the event
            event (str): the identifier of the event

        Returns:
            set: the set of rooms mapped to the given organizer and event
        """
        raise NotImplementedError()

    def add(self, organizer:str, event:str, room_id:str):
        """map a new room to an event

        Args:
            organizer (str): the identifier of the organizer of the event
            event (str): the identifier of the event
            room_id (str): the room identifier to map to the event
        """
        raise NotImplementedError()

    def remove(self, organizer:str, event:str, room_id:str):
        """safely check for and remove a specific room from an event

        Args:
            organizer (str): the identifier of the organizer of the event
            event (str): the identifier of the event
            room_id (str): the room identifier to remove, if it is present
        """
        raise NotImplementedError()

    def room_is_mapped(self, room:str) -> bool:
        """check if a room is mapped to an event

        Args:
            room (str):the room identifier to check

        Returns:
            bool: True if the room is mapped, False otherwise
        """
        raise NotImplementedError()

    def events_for_room(self, room:str) -> List[str]:
        """return a list of events that a room is mapped to in "organizer/event" format

        Args:
            room (str): the id of the room to return events for

        Returns:
            List[str]: the list of events the room is part of in "organizer/event" string format
        """
        raise NotImplementedError()

    def purge_room(self, room:str):
        """remove a room from all events it is mapped to
        
        Args:
            room (str): the room identifier to purge from all events
        """
        raise NotImplementedError()


class EventRoomsMemory(EventRooms):
    _mapping: dict = {}

    def rooms_by_event(self, organizer:str, event:str) -> set:
        if self._mapping.get(organizer) is None:
            return set()
        
        if self._mapping[organizer].get(event) is None:
            return set()
        
        return self._mapping[organizer].get(event)
    
    def add(self, organizer:str, event:str, room_id:str):
        if self._mapping.get(organizer) is None:
            self._mapping[organizer] = {} 
        
        if self._mapping[organizer].get(event) is None:
            self._mapping[organizer][event] = set()
        
        self._mapping[organizer][event].add(room_id)

    def remove(self, organizer:str, event:str, room_id:str):
        if room_id in self.rooms_by_event(organizer,event):
            self._mapping[organizer][event].remove(room_id)


    def room_is_mapped(self, room:str) -> bool:
        return len(self.events_for_room(room)) > 0

    def events_for_room(self, room:str) -> List[str]:
        events = []
        for organizer in self._mapping:
            for event in self._mapping[organizer]:
                if room in self._mapping[organizer][event]:
                    events.append(f"{organizer}/{event}")
        return events
    
    def purge_room(self, room:str):
        for organizer in self._mapping:
            for event in self._mapping[organizer]:
                if room in event:
                    self._mapping[organizer][event].remove(room)


class EventRoomsDB(EventRooms):

    def __init__(self, database, tablename="event_rooms"):
        self.database = database
        self._table_name = tablename

    async def rooms_by_event(self, organizer:str, event:str) -> set:
        q = f"SELECT room FROM {self._table_name} WHERE organizer=$1 AND event=$2"
        row = await self.database.fetch(q, organizer, event)
        if len(rows) == 0:
            return set()
        else:
            return set([row["room"] for row in rows])

    async def add(self, organizer:str, event:str, room_id:str):
        q = f"""
            INSERT INTO {self._table_name} (organizer, event, room) VALUES ($1, $2, $3)
        """
        # ON CONFLICT (key) DO UPDATE SET value=excluded.value, creator=excluded.creator
        await self.database.execute(q, organizer, event, room_id)

    async def remove(self, organizer:str, event:str, room_id:str):
        q = f"DROP * FROM {self._table_name} WHERE organizer=$1 AND event=$2 AND room=$3"
        await self.database.execute(q, organizer, event, room)

    async def room_is_mapped(self, room:str) -> bool:
        q = f"SELECT COUNT(*) FROM {self._table_name} WHERE room=$1"
        row = await self.database.fetchrow(q, room)
        if row:
            return row[0] > 0
        else:
            return False

    async def events_for_room(self, room:str) -> List[str]:
        q = f"SELECT organizer, event, room FROM {self._table_name} WHERE room=$1"
        row = await self.database.fetch(q, room)
        if len(rows) == 0:
            return []
        else:
            return list([f"{row['organizer']}/{row['event']}" for row in rows])

    async def purge_room(self, room:str):
        q = f"DROP * FROM {self._table_name} WHERE room=$1"
        await self.database.execute(q, room)