import hashlib

from django.db import models


def question_key_for(question_key, question_text):
    """Preset rubric questions keep their key; custom questions hash to a stable key."""
    if question_key and question_key != "custom":
        return question_key
    digest = hashlib.sha1(question_text.strip().lower().encode("utf-8")).hexdigest()[:10]
    return f"custom:{digest}"


class ResumeClassification(models.Model):
    candidate_id = models.CharField(max_length=64)
    candidate_name = models.CharField(max_length=200)
    question_key = models.CharField(max_length=64)
    question_text = models.TextField()
    answer = models.BooleanField()
    evidence = models.TextField(blank=True)
    chunk_size = models.PositiveIntegerField()
    overlap = models.PositiveIntegerField()
    top_k = models.PositiveIntegerField()
    model_name = models.CharField(max_length=100)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["candidate_id", "question_key"],
                name="unique_candidate_question",
            )
        ]
        ordering = ["question_key", "candidate_name"]

    def __str__(self):
        return f"{self.candidate_id}:{self.question_key}={self.answer}"
