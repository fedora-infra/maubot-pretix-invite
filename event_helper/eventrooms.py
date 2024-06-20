
class EventRooms:

    def rooms_by_event(self, organizer:str, event:str):
        raise NotImplementedError()

    def add(self, organizer:str, event:str, room_id:str):
        raise NotImplementedError()

    def remove(self, organizer:str, event:str, room_id:str):
        raise NotImplementedError()

    def room_is_mapped(self, room:str):
        raise NotImplementedError()

    def events_for_room(self, room:str):
        """return a list of events that a room is mapped to in "organizer/event" format

        Args:
            room (str): the id of the room to return events for

        Returns:
            List[str]: the list of events the room is part of in "organizer/event" string format
        """
        raise NotImplementedError()

    def purge_room(self, room):
        """remove a room from all events it is mapped to
        """
        raise NotImplementedError()


class EventRoomsMemory(EventRooms):
    _mapping: dict = {}

    def rooms_by_event(self, organizer:str, event:str):
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


    def room_is_mapped(self, room:str):
        return len(self.events_for_room(room)) > 0

    def events_for_room(self, room:str):
        events = []
        for organizer in self._mapping:
            for event in self._mapping[organizer]:
                if room in self._mapping[organizer][event]:
                    events.append(f"{organizer}/{event}")
        return events
    
    def purge_room(self, room):
        for organizer in self._mapping:
            for event in self._mapping[organizer]:
                if room in event:
                    self._mapping[organizer][event].remove(room)
