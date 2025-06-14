# test_long_term_memory.py
import unittest
import os
import json
from pathlib import Path
from datetime import datetime

# Assuming long_term_memory.py is in the same directory or accessible via PYTHONPATH
from long_term_memory import LongTermMemory, MemoryEntry

class TestLongTermMemory(unittest.TestCase):
    TEST_LTM_FILE = "test_ltm.json"

    def setUp(self):
        # Ensure a clean slate for each test
        if Path(self.TEST_LTM_FILE).exists():
            Path(self.TEST_LTM_FILE).unlink()
        self.ltm = LongTermMemory(file_path=self.TEST_LTM_FILE)

    def tearDown(self):
        if Path(self.TEST_LTM_FILE).exists():
            Path(self.TEST_LTM_FILE).unlink()

    def test_01_initialization(self):
        self.assertIsNotNone(self.ltm)
        self.assertEqual(self.ltm.memories, [])
        # self.assertTrue(Path(self.TEST_LTM_FILE).exists(), "LTM file should be created on init if loading (even if empty).")
        # Check if the created file is an empty JSON list if _save_to_disk was called by init indirectly
        # For now, _load_from_disk returns [] if file doesn't exist, and _save_to_disk is not called by init.
        # So the file might not exist yet if no memories are added.
        # Let's verify based on current implementation: _load_from_disk handles non-existent file.
        # _save_to_disk is only called by add_memory.
        # So, after init, file may not exist, which is fine.
        # If we want it to exist, initialize could call _save_to_disk if memories list is empty.
        # For now, we'll test based on current behavior.
        if not self.ltm.memories: # If no memories loaded (expected for new file)
             self.assertFalse(Path(self.TEST_LTM_FILE).exists() and Path(self.TEST_LTM_FILE).read_text() != "[]",
                             "File should not exist or be an empty list if no memories were added/loaded by init.")


    def test_02_add_memory_new(self):
        result = self.ltm.add_memory("First memory content")
        self.assertTrue(result.startswith("✅ Remembered:"))
        self.assertEqual(len(self.ltm.memories), 1)
        self.assertEqual(self.ltm.memories[0].content, "First memory content")
        self.assertTrue(Path(self.TEST_LTM_FILE).exists())

        # Verify persistence by loading into a new LTM instance
        ltm_new = LongTermMemory(file_path=self.TEST_LTM_FILE)
        self.assertEqual(len(ltm_new.memories), 1)
        self.assertEqual(ltm_new.memories[0].content, "First memory content")

    def test_03_add_memory_empty_content(self):
        result = self.ltm.add_memory("   ") # Whitespace only
        self.assertEqual(result, "Error: Memory content cannot be empty.")
        self.assertEqual(len(self.ltm.memories), 0)

        result_none = self.ltm.add_memory(None)
        self.assertEqual(result_none, "Error: Memory content cannot be empty.")
        self.assertEqual(len(self.ltm.memories), 0)


    def test_04_add_memory_duplicate(self):
        self.ltm.add_memory("Unique memory")
        result = self.ltm.add_memory("Unique memory  ") # Test with stripping
        self.assertEqual(result, "Info: This memory already exists.")
        self.assertEqual(len(self.ltm.memories), 1)

    def test_05_retrieve_relevant_memories_simple(self):
        self.ltm.add_memory("The quick brown fox")
        self.ltm.add_memory("A lazy dog jumps")
        self.ltm.add_memory("Another quick example")

        retrieved = self.ltm.retrieve_relevant_memories("quick")
        self.assertEqual(len(retrieved), 2)
        contents = {r.content for r in retrieved}
        self.assertIn("The quick brown fox", contents)
        self.assertIn("Another quick example", contents)

        retrieved_dog = self.ltm.retrieve_relevant_memories("dog")
        self.assertEqual(len(retrieved_dog), 1)
        self.assertEqual(retrieved_dog[0].content, "A lazy dog jumps")

    def test_06_retrieve_relevant_memories_no_match(self):
        self.ltm.add_memory("Content without keywords")
        retrieved = self.ltm.retrieve_relevant_memories("xyz123")
        self.assertEqual(len(retrieved), 0)

    def test_07_retrieve_relevant_memories_empty_query(self):
        self.ltm.add_memory("Some content")
        retrieved = self.ltm.retrieve_relevant_memories("")
        self.assertEqual(len(retrieved), 0)
        retrieved_none = self.ltm.retrieve_relevant_memories(None)
        self.assertEqual(len(retrieved_none), 0)


    def test_08_retrieve_relevant_memories_max_results(self):
        self.ltm.add_memory("Memory one apple")
        self.ltm.add_memory("Memory two apple")
        self.ltm.add_memory("Memory three apple")
        self.ltm.add_memory("Memory four orange")

        retrieved = self.ltm.retrieve_relevant_memories("apple", max_results=2)
        self.assertEqual(len(retrieved), 2)

        retrieved_all = self.ltm.retrieve_relevant_memories("apple", max_results=5)
        self.assertEqual(len(retrieved_all), 3)

    def test_09_retrieve_from_empty_ltm(self):
        # setUp creates a new self.ltm with an empty file
        retrieved = self.ltm.retrieve_relevant_memories("anything")
        self.assertEqual(len(retrieved), 0)

    def test_10_persistence_multiple_adds(self):
        self.ltm.add_memory("Alpha")
        self.ltm.add_memory("Beta")
        self.ltm.add_memory("Gamma")

        # New instance should load these
        ltm_new = LongTermMemory(file_path=self.TEST_LTM_FILE)
        self.assertEqual(len(ltm_new.memories), 3)
        contents = {m.content for m in ltm_new.memories}
        self.assertIn("Alpha", contents)
        self.assertIn("Beta", contents)
        self.assertIn("Gamma", contents)

    def test_11_load_corrupted_json(self):
        # Create a corrupted JSON file
        with open(self.TEST_LTM_FILE, 'w') as f:
            f.write("This is not valid JSON {")

        # Suppress print output during this test for cleaner test logs
        # by redirecting stdout temporarily
        original_stdout = os.sys.stdout
        os.sys.stdout = open(os.devnull, 'w')

        ltm_corrupt = LongTermMemory(file_path=self.TEST_LTM_FILE)

        # Restore stdout
        os.sys.stdout.close()
        os.sys.stdout = original_stdout

        self.assertEqual(len(ltm_corrupt.memories), 0, "Should return empty list for corrupted JSON")


    def test_12_load_empty_file(self):
        # Create an empty file
        Path(self.TEST_LTM_FILE).touch()

        ltm_empty_file = LongTermMemory(file_path=self.TEST_LTM_FILE)
        self.assertEqual(len(ltm_empty_file.memories), 0, "Should return empty list for an empty file")


if __name__ == '__main__':
    unittest.main()
