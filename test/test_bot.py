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
        self.mapping = EventRooms(persist_filename="rooms_mapping_test.json")

    def test_add(self):
        self.assertEqual(self.mapping.rooms_by_event("a", "b"), set())
        rm = Room("c")
        self.mapping.add_object("a", "b", rm)

        self.assertEqual(self.mapping.rooms_by_event("a", "b"), set([rm]))

    def test_add_nofilter_matches_all_filter_values(self):
        self.assertEqual(self.mapping.rooms_by_event("a", "b"), set())
        rm = Room("c")
        self.mapping.add_object("a", "b", rm)

        self.assertEqual(self.mapping.rooms_by_event("a", "b"), set([rm]))
        self.assertEqual(self.mapping.rooms_by_ticket_variant("a", "b", "x", "y"), list([rm]))



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

    def test_persists_to_file(self):
        self.assertEqual(self.mapping.rooms_by_event("a", "b"), set())
        rm = Room("c")
        self.mapping.add_object("a", "b", rm)

        self.assertEqual(self.mapping.rooms_by_event("a", "b"), set([rm]))

        self.mapping.persist()

        with open("rooms_mapping_test.json", "r") as f:
            data = json.load(f)

        self.assertEqual(data, {"a": {"b": [{"matrix_id": "c", "condition": {'item': None, 'variant': None}}]}})


    def test_persist_restore(self):
        self.assertEqual(self.mapping.rooms_by_event("a", "b"), set())
        rm = Room("c")
        self.mapping.add_object("a", "b", rm)

        self.assertEqual(self.mapping.rooms_by_event("a", "b"), set([rm]))

        self.mapping.persist()

        restored_mapping = EventRooms.from_path(persist_filename="rooms_mapping_test.json")
        self.assertEqual(len(restored_mapping.rooms_by_event("a", "b")), 1)

        self.assertEqual(restored_mapping.rooms_by_event("a", "b"), set([rm]))

    
    def tearDown(self):
        self.mapping.persistfile.unlink()


if __name__ == '__main__':
    unittest.main()