import json
from unittest.mock import patch

import numpy as np
from django.test import SimpleTestCase
from django.urls import reverse

from .help_center_data import ASSIGNMENT_QUESTIONS, HELP_CENTER_DOCUMENTS
from .resume_data import RESUME_TEXT
from .services import (
    calculate_retrieval_metrics,
    chunk_documents,
    chunk_text,
    search_chunks,
)


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


class HelpCenterDataTests(SimpleTestCase):
    def test_corpus_has_twenty_documents_and_one_gold_document_per_question(self):
        self.assertEqual(len(HELP_CENTER_DOCUMENTS), 20)

        for question_key in ASSIGNMENT_QUESTIONS:
            gold_documents = [
                document_id
                for document_id, document in HELP_CENTER_DOCUMENTS.items()
                if question_key in document["relevant_for"]
            ]
            self.assertEqual(len(gold_documents), 1)

    def test_document_chunks_retain_source_metadata(self):
        documents = {
            "HC-TEST": {
                "title": "Test article",
                "content": "one two three four five",
                "relevant_for": (),
            }
        }

        chunks = chunk_documents(documents, chunk_size=3, overlap=1)

        self.assertEqual(chunks[0]["id"], "HC-TEST:0")
        self.assertEqual(chunks[0]["document_id"], "HC-TEST")
        self.assertEqual(chunks[0]["document_title"], "Test article")
        self.assertEqual(chunks[1]["text"], "three four five")

    def test_retrieval_metrics_use_chunk_precision_and_document_recall(self):
        results = [
            {"document_id": "HC-001"},
            {"document_id": "HC-008"},
            {"document_id": "HC-001"},
            {"document_id": "HC-004"},
        ]

        metrics = calculate_retrieval_metrics(results, {"HC-001"})

        self.assertEqual(metrics["precision_at_k"], 0.5)
        self.assertEqual(metrics["recall_at_k"], 1.0)
        self.assertEqual(metrics["relevant_chunks_retrieved"], 2)


class AssignmentViewTests(SimpleTestCase):
    def test_assignment_page_renders_questions_and_document_count(self):
        response = self.client.get(reverse("explorer:assignment"))

        self.assertContains(response, "Help Center Retrieval Lab")
        self.assertContains(response, "20 help documents")
        self.assertContains(
            response,
            ASSIGNMENT_QUESTIONS["forgot_password"]["question"],
        )

    def test_evaluation_rejects_unknown_question(self):
        response = self.client.post(
            reverse("explorer:evaluate_assignment"),
            data=json.dumps(
                {
                    "question_key": "unknown",
                    "chunk_size": 80,
                    "overlap": 20,
                    "top_k": 3,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    @patch("explorer.views.generate_local_answer")
    @patch("explorer.views.retrieve_help_center")
    def test_evaluation_returns_metrics_results_and_local_answer(
        self,
        mocked_retrieve,
        mocked_generate,
    ):
        mocked_retrieve.return_value = {
            "results": [
                {
                    "id": "HC-001:0",
                    "document_id": "HC-001",
                    "document_title": "Change your password while signed in",
                    "text": "Open Security and choose Change password.",
                    "start_word": 1,
                    "end_word": 7,
                    "word_count": 7,
                    "overlap_count": 0,
                    "rank": 1,
                    "score": 0.91,
                    "is_relevant": True,
                }
            ],
            "metrics": {
                "precision_at_k": 1.0,
                "recall_at_k": 1.0,
                "relevant_chunks_retrieved": 1,
                "gold_documents_retrieved": 1,
                "gold_document_count": 1,
            },
            "gold_document_ids": ["HC-001"],
            "total_chunks": 20,
        }
        mocked_generate.return_value = {
            "available": True,
            "answer": "Open Security and select Change password. [HC-001]",
            "model": "test-model",
            "message": "",
        }

        response = self.client.post(
            reverse("explorer:evaluate_assignment"),
            data=json.dumps(
                {
                    "question_key": "change_password",
                    "chunk_size": 80,
                    "overlap": 20,
                    "top_k": 3,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["retrieval"]["metrics"]["precision_at_k"],
            1.0,
        )
        self.assertTrue(response.json()["llm"]["available"])
        mocked_generate.assert_called_once()
