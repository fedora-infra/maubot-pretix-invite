from dataclasses import dataclass, field

@dataclass
class EventRooms:
    _mapping: dict = field(default_factory=lambda: {})

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
        """return a list of events that a room is mapped to in "organizer/event" format

        Args:
            room (str): the id of the room to return events for

        Returns:
            List[str]: the list of events the room is part of
        """
        events = []
        for organizer in self._mapping:
            for event in self._mapping[organizer]:
                if room in self._mapping[organizer][event]:
                    events.append(f"{organizer}/{event}")
        return events
    
    def purge_room(self, room):
        """remove a room from all events it is mapped to
        """
        for organizer in self._mapping:
            for event in self._mapping[organizer]:
                if room in event:
                    self._mapping[organizer][event].remove(room)
