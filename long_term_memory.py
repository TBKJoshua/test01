import json
from pathlib import Path
from datetime import datetime

class MemoryEntry:
    def __init__(self, timestamp: str, content: str):
        self.timestamp = timestamp
        self.content = content

class LongTermMemory:
    def __init__(self, file_path: str):
        self.storage_path = None
        self.memories = [] # List of MemoryEntry objects
        self.initialize(file_path)

    def initialize(self, file_path: str):
        self.storage_path = file_path
        self.memories = self._load_from_disk()

    def _load_from_disk(self):
        storage_file = Path(self.storage_path)
        if not storage_file.exists():
            return []

        try:
            raw_json = storage_file.read_text(encoding='utf-8')
            if not raw_json.strip():
                return []
            data = json.loads(raw_json)
            return [MemoryEntry(timestamp=item['timestamp'], content=item['content']) for item in data]
        except json.JSONDecodeError:
            print(f"LTM: Failed to load from disk at {self.storage_path}, file might be corrupted or not valid JSON.")
            return []
        except Exception as e:
            print(f"LTM: An unexpected error occurred while loading from {self.storage_path}: {e}")
            return []

    def _save_to_disk(self):
        storage_file = Path(self.storage_path)
        try:
            storage_file.parent.mkdir(parents=True, exist_ok=True)
            memories_as_dicts = [
                {'timestamp': entry.timestamp, 'content': entry.content}
                for entry in self.memories
            ]
            json_data = json.dumps(memories_as_dicts, indent=4)
            storage_file.write_text(json_data, encoding='utf-8')
        except Exception as e:
            print(f"LTM: An unexpected error occurred while saving to {self.storage_path}: {e}")

    def add_memory(self, text_content: str):
        if not text_content or not text_content.strip():
            return "Error: Memory content cannot be empty."

        trimmed_content = text_content.strip()

        if any(memory.content == trimmed_content for memory in self.memories):
            return "Info: This memory already exists."

        new_entry = MemoryEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            content=trimmed_content
        )
        self.memories.append(new_entry)
        self._save_to_disk()
        return f"✅ Remembered: '{trimmed_content}'"

    def retrieve_relevant_memories(self, query_text: str, max_results: int = 5):
        if not self.memories or not query_text or not query_text.strip():
            return []

        query_words = set(query_text.strip().lower().split())

        scored_memories = []
        for memory_item in self.memories:
            memory_words = set(memory_item.content.lower().split())
            common_words = query_words.intersection(memory_words)
            score = len(common_words)

            if score > 0:
                scored_memories.append({'score': score, 'memory': memory_item})

        # Sort by score in descending order
        scored_memories.sort(key=lambda x: x['score'], reverse=True)

        # Return the 'memory' part of the top max_results
        return [item['memory'] for item in scored_memories[:max_results]]

# (End of class)
