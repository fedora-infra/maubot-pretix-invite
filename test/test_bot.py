import unittest
import json
from event_helper import Room, FilterConditions, EventRooms



class TestRoom(unittest.TestCase):

    def test_init_one_arg(self):
        self.assertIsNotNone(Room("matrix id"))

    def test_init_two_arg(self):
        self.assertIsNotNone(Room("identifier", FilterConditions("3", "4")))
        self.assertIsNotNone(Room("identifier", condition=FilterConditions("3", "4")))

    def test_can_add_to_set(self):
        testset = set()
        rm = Room("identifier", FilterConditions("3", "4"))
        
        self.assertEqual(len(testset), 0)
        testset.add(rm)
        self.assertEqual(len(testset), 1)



class TestEventRooms(unittest.TestCase):

    def setUp(self):
        self.mapping = EventRooms()

    def test_add(self):
        self.assertEqual(self.mapping.rooms_by_event("a", "b"), set())
        rm = Room("c")
        self.mapping.add_object("a", "b", rm)

        self.assertEqual(self.mapping.rooms_by_event("a", "b"), set([rm]))

    def test_add_with_filters(self):
        self.assertEqual(self.mapping.rooms_by_event("a", "b"), set())
        rm = Room("c", FilterConditions("x", "y"))
        self.mapping.add_object("a", "b", rm)

        self.assertEqual(self.mapping.rooms_by_event("a", "b"), set([rm]))

        self.assertEqual(self.mapping.rooms_by_ticket_variant("a", "b", "x", "y"), list([rm]))

    def test_filter_retrieval_type_mismatch(self):
        self.assertEqual(self.mapping.rooms_by_event("a", "b"), set())
        rm = Room("c", FilterConditions("1", "2"))
        self.mapping.add_object("a", "b", rm)

        self.assertEqual(self.mapping.rooms_by_event("a", "b"), set([rm]))

        self.assertEqual(self.mapping.rooms_by_ticket_variant("a", "b", 1, 2), list([rm]))



if __name__ == '__main__':
    unittest.main()