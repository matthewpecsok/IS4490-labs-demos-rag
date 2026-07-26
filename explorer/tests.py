import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from . import gemini_classifier, vector_store
from .candidate_data import CANDIDATE_DOCUMENTS, JOB_POSTING_TEXT
from .classification_data import CLASSIFICATION_QUESTIONS
from .ground_truth_data import GROUND_TRUTH
from .help_center_data import ASSIGNMENT_QUESTIONS, HELP_CENTER_DOCUMENTS
from .models import ResumeClassification, question_key_for
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


class FakeVectorModel:
    def __init__(self, vectors):
        self.vectors = vectors

    def encode(self, texts, **kwargs):
        return np.array([self.vectors[text] for text in texts])


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


class CandidateDataTests(SimpleTestCase):
    def test_three_candidate_resumes_are_loaded(self):
        self.assertEqual(len(CANDIDATE_DOCUMENTS), 3)
        for document in CANDIDATE_DOCUMENTS.values():
            self.assertTrue(document["content"])
            self.assertTrue(document["candidate_name"])

    def test_job_posting_is_loaded(self):
        self.assertIn("Chief Technology Officer", JOB_POSTING_TEXT)


class VectorStoreTests(SimpleTestCase):
    DOCUMENTS = {
        "cand-a": {
            "title": "Candidate A",
            "candidate_name": "Candidate A",
            "headline": "Engineer",
            "location": "Remote",
            "content": "alpha beta gamma delta",
        },
        "cand-b": {
            "title": "Candidate B",
            "candidate_name": "Candidate B",
            "headline": "Manager",
            "location": "Remote",
            "content": "epsilon zeta eta theta",
        },
    }
    BUILD_MODEL = FakeVectorModel(
        {
            "alpha beta gamma delta": [1.0, 0.0],
            "epsilon zeta eta theta": [0.0, 1.0],
        }
    )

    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        patcher = patch(
            "explorer.vector_store.DB_PATH",
            Path(self._tempdir.name) / "candidates.sqlite3",
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_status_is_none_before_a_build(self):
        self.assertIsNone(vector_store.get_index_status())

    def test_search_before_build_raises(self):
        with self.assertRaises(LookupError):
            vector_store.search_index("alpha", top_k=1)

    def test_build_writes_one_chunk_per_document(self):
        stats = vector_store.build_index(
            self.DOCUMENTS, chunk_size=4, overlap=0, model=self.BUILD_MODEL
        )

        self.assertEqual(stats["chunk_count"], 2)
        self.assertEqual(stats["document_count"], 2)
        self.assertEqual(stats["dimensions"], 2)
        self.assertTrue(Path(stats["file_path"]).exists())

        status = vector_store.get_index_status()
        self.assertEqual(status["chunk_count"], 2)
        self.assertEqual(status["chunk_size"], 4)

    def test_search_ranks_by_cosine_similarity(self):
        vector_store.build_index(
            self.DOCUMENTS, chunk_size=4, overlap=0, model=self.BUILD_MODEL
        )

        query_model = FakeVectorModel({"find alpha": [1.0, 0.0]})
        results = vector_store.search_index("find alpha", top_k=1, model=query_model)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["document_id"], "cand-a")
        self.assertEqual(results[0]["candidate_name"], "Candidate A")
        self.assertEqual(results[0]["rank"], 1)


class VectorDbViewTests(SimpleTestCase):
    def test_vectordb_page_renders_candidates(self):
        response = self.client.get(reverse("explorer:vectordb"))

        self.assertContains(response, "Candidate Vector DB Lab")
        self.assertContains(response, "Dr. Elena Martinez")

    def test_build_rejects_invalid_overlap(self):
        response = self.client.post(
            reverse("explorer:vectordb_build"),
            data=json.dumps({"chunk_size": 40, "overlap": 40}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_search_rejects_empty_query(self):
        response = self.client.post(
            reverse("explorer:vectordb_search"),
            data=json.dumps({"query": "  ", "top_k": 3}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    @patch("explorer.vector_store.search_index")
    def test_search_returns_conflict_when_index_missing(self, mocked_search):
        mocked_search.side_effect = LookupError("The vector database has not been built yet.")

        response = self.client.post(
            reverse("explorer:vectordb_search"),
            data=json.dumps({"query": "engineering leadership", "top_k": 3}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)

    @patch("explorer.vector_store.build_index")
    def test_build_returns_stats_from_vector_store(self, mocked_build):
        mocked_build.return_value = {
            "chunk_size": 80,
            "overlap": 20,
            "model_name": "test-model",
            "dimensions": 384,
            "chunk_count": 12,
            "document_count": 3,
            "built_at": 0.0,
            "file_path": "/tmp/candidates.sqlite3",
            "file_size_bytes": 4096,
            "chunks_per_document": [],
        }

        response = self.client.post(
            reverse("explorer:vectordb_build"),
            data=json.dumps({"chunk_size": 80, "overlap": 20}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["chunk_count"], 12)
        mocked_build.assert_called_once_with(CANDIDATE_DOCUMENTS, 80, 20)


class QuestionKeyTests(SimpleTestCase):
    def test_rubric_key_passes_through(self):
        self.assertEqual(question_key_for("healthcare_hipaa", "ignored"), "healthcare_hipaa")

    def test_custom_key_is_stable_hash(self):
        first = question_key_for("custom", "Has this candidate led a rebrand?")
        second = question_key_for("custom", "  HAS THIS CANDIDATE LED A REBRAND?  ")

        self.assertTrue(first.startswith("custom:"))
        self.assertEqual(first, second)


class GeminiClassifierTests(SimpleTestCase):
    def test_no_chunks_returns_unavailable(self):
        result = gemini_classifier.classify_chunks("Jordan Lee", "Has AI experience?", [])

        self.assertFalse(result["available"])
        self.assertIn("No resume chunks", result["message"])
        self.assertEqual(result["latency_ms"], 0)

    def test_missing_api_key_degrades_gracefully(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GOOGLE_API_KEY", None)
            os.environ.pop("GEMINI_API_KEY", None)
            self.assertFalse(gemini_classifier.is_configured())

            result = gemini_classifier.classify_chunks(
                "Jordan Lee",
                "Has AI experience?",
                [{"rank": 1, "score": 0.5, "text": "Worked with AI."}],
            )

        self.assertFalse(result["available"])
        self.assertIn("GOOGLE_API_KEY", result["message"])
        self.assertIsNone(result["usage"])
        self.assertGreaterEqual(result["latency_ms"], 0)

    @patch("explorer.gemini_classifier.requests.post")
    def test_classify_chunks_returns_token_usage(self, mocked_post):
        mocked_post.return_value.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": '{"answer": true, "evidence": "Led AI projects."}'}
                        ]
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 120,
                "candidatesTokenCount": 15,
                "thoughtsTokenCount": 40,
                "totalTokenCount": 175,
            },
        }
        mocked_post.return_value.raise_for_status.return_value = None

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            result = gemini_classifier.classify_chunks(
                "Jordan Lee",
                "Has AI experience?",
                [{"rank": 1, "score": 0.5, "text": "Worked with AI."}],
            )

        self.assertTrue(result["available"])
        self.assertEqual(
            result["usage"],
            {
                "prompt_tokens": 120,
                "output_tokens": 15,
                "thinking_tokens": 40,
                "total_tokens": 175,
            },
        )
        self.assertGreaterEqual(result["latency_ms"], 0)


class ClassificationPipelineViewTests(TestCase):
    def test_classify_page_renders_rubric_and_candidates(self):
        response = self.client.get(reverse("explorer:classify"))

        self.assertContains(response, "Resume Screening Pipeline")
        self.assertContains(response, "Dr. Elena Martinez")
        self.assertContains(response, CLASSIFICATION_QUESTIONS["healthcare_hipaa"]["label"])

    def test_run_rejects_unknown_candidate(self):
        response = self.client.post(
            reverse("explorer:classify_candidate"),
            data=json.dumps(
                {
                    "candidate_id": "not-a-real-candidate",
                    "question_key": "healthcare_hipaa",
                    "chunk_size": 100,
                    "overlap": 20,
                    "top_k": 4,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_run_rejects_custom_question_without_text(self):
        response = self.client.post(
            reverse("explorer:classify_candidate"),
            data=json.dumps(
                {
                    "candidate_id": "elena-martinez",
                    "question_key": "custom",
                    "question_text": "",
                    "chunk_size": 100,
                    "overlap": 20,
                    "top_k": 4,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    @patch("explorer.views.gemini_classifier.classify_chunks")
    @patch("explorer.views.search_chunks")
    def test_run_stores_result_when_gemini_available(self, mocked_search, mocked_classify):
        mocked_search.return_value = [
            {
                "id": 0,
                "text": "Led HIPAA-regulated engineering teams.",
                "start_word": 1,
                "end_word": 6,
                "word_count": 6,
                "overlap_count": 0,
                "rank": 1,
                "score": 0.87,
            }
        ]
        mocked_classify.return_value = {
            "available": True,
            "answer": True,
            "evidence": "Led HIPAA-regulated engineering teams.",
            "model": "gemini-test",
            "message": "",
        }

        response = self.client.post(
            reverse("explorer:classify_candidate"),
            data=json.dumps(
                {
                    "candidate_id": "elena-martinez",
                    "question_key": "healthcare_hipaa",
                    "chunk_size": 100,
                    "overlap": 20,
                    "top_k": 4,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["classification"]["answer"])
        self.assertIsNotNone(data["stored"])

        record = ResumeClassification.objects.get(
            candidate_id="elena-martinez", question_key="healthcare_hipaa"
        )
        self.assertTrue(record.answer)
        self.assertEqual(record.candidate_name, "Dr. Elena Martinez")

    @patch("explorer.views.gemini_classifier.classify_chunks")
    @patch("explorer.views.search_chunks")
    def test_run_stores_token_usage(self, mocked_search, mocked_classify):
        mocked_search.return_value = [
            {
                "id": 0,
                "text": "Led HIPAA-regulated engineering teams.",
                "start_word": 1,
                "end_word": 6,
                "word_count": 6,
                "overlap_count": 0,
                "rank": 1,
                "score": 0.87,
            }
        ]
        mocked_classify.return_value = {
            "available": True,
            "answer": True,
            "evidence": "Led HIPAA-regulated engineering teams.",
            "model": "gemini-test",
            "message": "",
            "usage": {
                "prompt_tokens": 200,
                "output_tokens": 30,
                "thinking_tokens": 50,
                "total_tokens": 280,
            },
            "latency_ms": 842,
        }

        response = self.client.post(
            reverse("explorer:classify_candidate"),
            data=json.dumps(
                {
                    "candidate_id": "elena-martinez",
                    "question_key": "healthcare_hipaa",
                    "chunk_size": 100,
                    "overlap": 20,
                    "top_k": 4,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["classification"]["usage"]["total_tokens"], 280)
        self.assertEqual(response.json()["classification"]["latency_ms"], 842)

        record = ResumeClassification.objects.get(
            candidate_id="elena-martinez", question_key="healthcare_hipaa"
        )
        self.assertEqual(record.prompt_tokens, 200)
        self.assertEqual(record.output_tokens, 30)
        self.assertEqual(record.thinking_tokens, 50)
        self.assertEqual(record.total_tokens, 280)
        self.assertEqual(record.latency_ms, 842)

    @patch("explorer.views.gemini_classifier.classify_chunks")
    @patch("explorer.views.search_chunks")
    def test_run_does_not_store_when_gemini_unavailable(self, mocked_search, mocked_classify):
        mocked_search.return_value = []
        mocked_classify.return_value = {
            "available": False,
            "answer": None,
            "evidence": "",
            "model": "gemini-test",
            "message": "Gemini is not available.",
        }

        response = self.client.post(
            reverse("explorer:classify_candidate"),
            data=json.dumps(
                {
                    "candidate_id": "marcus-reed",
                    "question_key": "cloud_infra",
                    "chunk_size": 100,
                    "overlap": 20,
                    "top_k": 4,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["stored"])
        self.assertFalse(
            ResumeClassification.objects.filter(
                candidate_id="marcus-reed", question_key="cloud_infra"
            ).exists()
        )

    def test_query_rejects_unknown_question(self):
        response = self.client.post(
            reverse("explorer:query_classifications"),
            data=json.dumps({"question_key": "not-a-real-question"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_query_returns_stored_matches_ordered_by_answer(self):
        ResumeClassification.objects.create(
            candidate_id="elena-martinez",
            candidate_name="Dr. Elena Martinez",
            question_key="healthcare_hipaa",
            question_text=CLASSIFICATION_QUESTIONS["healthcare_hipaa"]["question"],
            answer=True,
            evidence="Led HIPAA-regulated systems.",
            chunk_size=100,
            overlap=20,
            top_k=4,
            model_name="gemini-test",
        )
        ResumeClassification.objects.create(
            candidate_id="olivia-grant",
            candidate_name="Olivia Grant",
            question_key="healthcare_hipaa",
            question_text=CLASSIFICATION_QUESTIONS["healthcare_hipaa"]["question"],
            answer=False,
            evidence="No healthcare experience found.",
            chunk_size=100,
            overlap=20,
            top_k=4,
            model_name="gemini-test",
        )

        response = self.client.post(
            reverse("explorer:query_classifications"),
            data=json.dumps({"question_key": "healthcare_hipaa"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_classified"], 2)
        self.assertEqual(data["matched_count"], 1)
        self.assertEqual(data["results"][0]["candidate_id"], "elena-martinez")
        self.assertTrue(data["results"][0]["answer"])


class GroundTruthDataTests(SimpleTestCase):
    def test_every_candidate_and_question_has_a_label(self):
        self.assertEqual(set(GROUND_TRUTH.keys()), set(CANDIDATE_DOCUMENTS.keys()))
        for candidate_id, labels in GROUND_TRUTH.items():
            self.assertEqual(
                set(labels.keys()),
                set(CLASSIFICATION_QUESTIONS.keys()),
                f"{candidate_id} is missing or has extra rubric question labels",
            )
            for question_key, answer in labels.items():
                self.assertIsInstance(
                    answer,
                    bool,
                    f"{candidate_id}.{question_key} ground truth must be a bool",
                )


class ExperimentViewTests(TestCase):
    def test_experiment_page_renders(self):
        response = self.client.get(reverse("explorer:experiment"))

        self.assertContains(response, "Configuration A")
        self.assertContains(response, "Configuration B")
        self.assertContains(response, "Dr. Elena Martinez")

    def test_run_cell_rejects_unknown_candidate(self):
        response = self.client.post(
            reverse("explorer:experiment_run_cell"),
            data=json.dumps(
                {
                    "candidate_id": "not-a-real-candidate",
                    "question_key": "healthcare_hipaa",
                    "chunk_size": 100,
                    "overlap": 20,
                    "top_k": 4,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_run_cell_rejects_custom_question(self):
        response = self.client.post(
            reverse("explorer:experiment_run_cell"),
            data=json.dumps(
                {
                    "candidate_id": "elena-martinez",
                    "question_key": "custom",
                    "chunk_size": 100,
                    "overlap": 20,
                    "top_k": 4,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    @patch("explorer.views.gemini_classifier.classify_chunks")
    @patch("explorer.views.search_chunks")
    def test_run_cell_marks_correct_answer(self, mocked_search, mocked_classify):
        mocked_search.return_value = [
            {
                "id": 0,
                "text": "Healthcare analytics SaaS, HIPAA-regulated systems.",
                "start_word": 1,
                "end_word": 6,
                "word_count": 6,
                "overlap_count": 0,
                "rank": 1,
                "score": 0.9,
            }
        ]
        mocked_classify.return_value = {
            "available": True,
            "answer": True,
            "evidence": "Healthcare analytics SaaS, HIPAA-regulated systems.",
            "model": "gemini-test",
            "message": "",
            "usage": {
                "prompt_tokens": 100,
                "output_tokens": 10,
                "thinking_tokens": 20,
                "total_tokens": 130,
            },
            "latency_ms": 500,
        }

        response = self.client.post(
            reverse("explorer:experiment_run_cell"),
            data=json.dumps(
                {
                    "candidate_id": "elena-martinez",
                    "question_key": "healthcare_hipaa",
                    "chunk_size": 100,
                    "overlap": 20,
                    "top_k": 4,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["expected"])
        self.assertTrue(data["correct"])
        self.assertEqual(data["classification"]["usage"]["total_tokens"], 130)

    @patch("explorer.views.gemini_classifier.classify_chunks")
    @patch("explorer.views.search_chunks")
    def test_run_cell_marks_incorrect_answer(self, mocked_search, mocked_classify):
        mocked_search.return_value = []
        mocked_classify.return_value = {
            "available": True,
            "answer": True,
            "evidence": "Mentions a scheduling tool.",
            "model": "gemini-test",
            "message": "",
            "usage": {
                "prompt_tokens": 50,
                "output_tokens": 5,
                "thinking_tokens": 5,
                "total_tokens": 60,
            },
            "latency_ms": 400,
        }

        # Ground truth says Marcus Reed has NOT held 10+ years of tech
        # leadership, so a "yes" prediction here should be scored incorrect.
        response = self.client.post(
            reverse("explorer:experiment_run_cell"),
            data=json.dumps(
                {
                    "candidate_id": "marcus-reed",
                    "question_key": "leadership_10yr",
                    "chunk_size": 100,
                    "overlap": 20,
                    "top_k": 4,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["expected"])
        self.assertFalse(data["correct"])

    @patch("explorer.views.gemini_classifier.classify_chunks")
    @patch("explorer.views.search_chunks")
    def test_run_cell_never_writes_to_resume_classification(
        self, mocked_search, mocked_classify
    ):
        mocked_search.return_value = []
        mocked_classify.return_value = {
            "available": True,
            "answer": True,
            "evidence": "",
            "model": "gemini-test",
            "message": "",
            "usage": {
                "prompt_tokens": 1,
                "output_tokens": 1,
                "thinking_tokens": 1,
                "total_tokens": 3,
            },
            "latency_ms": 1,
        }

        self.client.post(
            reverse("explorer:experiment_run_cell"),
            data=json.dumps(
                {
                    "candidate_id": "elena-martinez",
                    "question_key": "healthcare_hipaa",
                    "chunk_size": 100,
                    "overlap": 20,
                    "top_k": 4,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(ResumeClassification.objects.count(), 0)

    @patch("explorer.views.gemini_classifier.classify_chunks")
    @patch("explorer.views.search_chunks")
    def test_run_cell_reports_none_correct_when_unavailable(
        self, mocked_search, mocked_classify
    ):
        mocked_search.return_value = []
        mocked_classify.return_value = {
            "available": False,
            "answer": None,
            "evidence": "",
            "model": "gemini-test",
            "message": "Gemini is not available.",
            "usage": None,
            "latency_ms": 0,
        }

        response = self.client.post(
            reverse("explorer:experiment_run_cell"),
            data=json.dumps(
                {
                    "candidate_id": "olivia-grant",
                    "question_key": "cloud_infra",
                    "chunk_size": 100,
                    "overlap": 20,
                    "top_k": 4,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["correct"])
        self.assertFalse(data["expected"])
