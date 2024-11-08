import unittest
import json
from event_helper import Room, FilterConditions



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


if __name__ == '__main__':
    unittest.main()