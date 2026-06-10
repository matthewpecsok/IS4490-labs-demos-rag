import json
from unittest.mock import patch

import numpy as np
from django.test import SimpleTestCase
from django.urls import reverse

from .resume_data import RESUME_TEXT
from .services import chunk_text, search_chunks


class FakeEmbeddingModel:
    def encode(self, texts, **kwargs):
        vectors = {
            "logistics": [1.0, 0.0],
            "shipping operations": [0.9, 0.1],
            "healthcare scheduling": [0.1, 0.9],
        }
        return np.array([vectors[text] for text in texts])


class ChunkTextTests(SimpleTestCase):
    def test_chunks_use_expected_overlap(self):
        chunks = chunk_text("one two three four five six seven", 4, 2)

        self.assertEqual(
            [chunk["text"] for chunk in chunks],
            ["one two three four", "three four five six", "five six seven"],
        )
        self.assertEqual(chunks[1]["overlap_count"], 2)
        self.assertEqual(chunks[2]["end_word"], 7)

    def test_overlap_must_be_smaller_than_chunk(self):
        with self.assertRaises(ValueError):
            chunk_text("one two three", 2, 2)

    def test_search_ranks_by_cosine_similarity(self):
        results = search_chunks(
            query="logistics",
            text="shipping operations healthcare scheduling",
            chunk_size=2,
            overlap=0,
            top_k=1,
            model=FakeEmbeddingModel(),
        )

        self.assertEqual(results[0]["text"], "shipping operations")
        self.assertEqual(results[0]["rank"], 1)


class ExplorerViewTests(SimpleTestCase):
    def test_index_renders_resume_and_controls(self):
        response = self.client.get(reverse("explorer:index"))

        self.assertContains(response, "Chunk Lab")
        self.assertContains(response, "JORDAN LEE", html=False)
        self.assertContains(response, str(len(RESUME_TEXT.split())))

    def test_search_rejects_overlap_equal_to_chunk_size(self):
        response = self.client.post(
            reverse("explorer:search"),
            data=json.dumps(
                {
                    "query": "analytics",
                    "chunk_size": 40,
                    "overlap": 40,
                    "top_k": 3,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    @patch("explorer.views.search_chunks")
    def test_search_returns_ranked_results(self, mocked_search):
        mocked_search.return_value = [
            {
                "id": 2,
                "text": "A matching passage",
                "start_word": 21,
                "end_word": 30,
                "word_count": 10,
                "overlap_count": 2,
                "rank": 1,
                "score": 0.8123,
            }
        ]

        response = self.client.post(
            reverse("explorer:search"),
            data=json.dumps(
                {
                    "query": "process automation",
                    "chunk_size": 80,
                    "overlap": 20,
                    "top_k": 3,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["id"], 2)
