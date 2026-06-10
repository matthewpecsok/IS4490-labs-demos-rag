(() => {
  "use strict";

  const form = document.getElementById("experiment-form");
  const chunkSizeInput = document.getElementById("chunk-size");
  const overlapInput = document.getElementById("overlap");
  const topKInput = document.getElementById("top-k");
  const chunkSizeOutput = document.getElementById("chunk-size-output");
  const overlapOutput = document.getElementById("overlap-output");
  const topKOutput = document.getElementById("top-k-output");
  const overlapMax = document.getElementById("overlap-max");
  const evaluateButton = document.getElementById("evaluate-button");
  const formStatus = document.getElementById("form-status");
  const emptyState = document.getElementById("empty-state");
  const evaluationResults = document.getElementById("evaluation-results");
  const staleBadge = document.getElementById("stale-badge");
  const answerPanel = document.getElementById("answer-panel");
  const llmAnswer = document.getElementById("llm-answer");
  const llmModelBadge = document.getElementById("llm-model-badge");
  const retrievalPanel = document.getElementById("retrieval-panel");
  const retrievalList = document.getElementById("retrieval-list");
  const goldDocument = document.getElementById("gold-document");
  const precisionValue = document.getElementById("precision-value");
  const recallValue = document.getElementById("recall-value");
  const precisionDetail = document.getElementById("precision-detail");
  const recallDetail = document.getElementById("recall-detail");
  const totalChunksValue = document.getElementById("total-chunks-value");

  let hasEvaluation = false;

  function updateTrack(input) {
    const min = Number(input.min);
    const max = Number(input.max);
    const progress = ((Number(input.value) - min) / (max - min)) * 100;
    input.style.setProperty("--progress", `${progress}%`);
  }

  function updateControls() {
    const chunkSize = Number(chunkSizeInput.value);
    const allowedOverlap = Math.min(70, chunkSize - 5);
    overlapInput.max = String(allowedOverlap);
    if (Number(overlapInput.value) > allowedOverlap) {
      overlapInput.value = String(Math.floor(allowedOverlap / 5) * 5);
    }

    chunkSizeOutput.textContent = `${chunkSize} words`;
    overlapOutput.textContent = `${overlapInput.value} words`;
    topKOutput.textContent =
      `${topKInput.value} ${topKInput.value === "1" ? "chunk" : "chunks"}`;
    overlapMax.textContent = overlapInput.max;
    [chunkSizeInput, overlapInput, topKInput].forEach(updateTrack);

    if (hasEvaluation) staleBadge.hidden = false;
  }

  function percentage(value) {
    return `${Math.round(value * 100)}%`;
  }

  function buildRetrievalCard(result) {
    const card = document.createElement("article");
    card.className = `retrieval-card${result.is_relevant ? " relevant" : ""}`;

    const rank = document.createElement("span");
    rank.className = "retrieval-rank";
    rank.textContent = String(result.rank).padStart(2, "0");

    const main = document.createElement("div");
    main.className = "retrieval-main";

    const meta = document.createElement("div");
    meta.className = "retrieval-meta";

    const documentId = document.createElement("span");
    documentId.className = "document-id";
    documentId.textContent = result.document_id;

    const position = document.createElement("span");
    position.className = "chunk-position";
    position.textContent =
      `words ${result.start_word}–${result.end_word} · ${result.word_count} words`;

    const relevance = document.createElement("span");
    relevance.className = `relevance-badge ${result.is_relevant ? "yes" : "no"}`;
    relevance.textContent = result.is_relevant
      ? "Relevant · gold document"
      : "Not relevant";
    meta.append(documentId, position, relevance);

    const title = document.createElement("h3");
    title.className = "retrieval-title";
    title.textContent = result.document_title;

    const text = document.createElement("p");
    text.className = "retrieval-text";
    text.textContent = result.text;

    const scoreRow = document.createElement("div");
    scoreRow.className = "score-row";
    const scoreTrack = document.createElement("span");
    scoreTrack.className = "score-track";
    const scoreFill = document.createElement("i");
    scoreFill.style.width = `${Math.max(3, Math.min(100, result.score * 100))}%`;
    scoreTrack.appendChild(scoreFill);
    const score = document.createElement("span");
    score.textContent = `${result.score.toFixed(4)} cosine similarity`;
    scoreRow.append(scoreTrack, score);

    main.append(meta, title, text, scoreRow);
    card.append(rank, main);
    return card;
  }

  function renderMetrics(retrieval) {
    const metrics = retrieval.metrics;
    precisionValue.textContent = percentage(metrics.precision_at_k);
    recallValue.textContent = percentage(metrics.recall_at_k);
    totalChunksValue.textContent = String(retrieval.total_chunks);
    precisionDetail.textContent =
      `${metrics.relevant_chunks_retrieved} of ${retrieval.results.length} ` +
      "retrieved chunks were relevant.";
    recallDetail.textContent = metrics.gold_documents_retrieved
      ? "The gold document appeared in the retrieved context."
      : "The gold document was missing from the retrieved context.";
  }

  function renderAnswer(llm) {
    answerPanel.hidden = false;
    llmModelBadge.textContent = llm.model;
    llmAnswer.classList.toggle("unavailable", !llm.available);
    llmAnswer.textContent = llm.available ? llm.answer : llm.message;
  }

  function renderEvaluation(data) {
    hasEvaluation = true;
    staleBadge.hidden = true;
    emptyState.hidden = true;
    evaluationResults.hidden = false;
    retrievalPanel.hidden = false;

    renderMetrics(data.retrieval);
    renderAnswer(data.llm);
    goldDocument.textContent =
      `Gold document: ${data.retrieval.gold_document_ids.join(", ")}`;
    retrievalList.replaceChildren(
      ...data.retrieval.results.map(buildRetrievalCard)
    );
  }

  async function evaluate() {
    const selectedQuestion = form.querySelector(
      "input[name='question_key']:checked"
    );
    const buttonLabel = evaluateButton.querySelector("span");
    evaluateButton.disabled = true;
    buttonLabel.textContent = "Evaluating…";
    formStatus.classList.remove("error");
    formStatus.textContent =
      "Embedding all chunks, ranking evidence, then asking the local model.";

    try {
      const response = await fetch(window.assignmentLab.evaluateUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": form.querySelector(
            "[name='csrfmiddlewaretoken']"
          ).value
        },
        body: JSON.stringify({
          question_key: selectedQuestion.value,
          chunk_size: Number(chunkSizeInput.value),
          overlap: Number(overlapInput.value),
          top_k: Number(topKInput.value)
        })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "The evaluation could not be completed.");
      }

      renderEvaluation(data);
      formStatus.textContent = data.llm.available
        ? "Retrieval metrics and local answer are ready."
        : "Retrieval succeeded. The local LLM is currently unavailable.";
      document.querySelector(".metrics-panel").scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    } catch (error) {
      formStatus.textContent = error.message;
      formStatus.classList.add("error");
    } finally {
      evaluateButton.disabled = false;
      buttonLabel.textContent = "Run retrieval + answer";
    }
  }

  [chunkSizeInput, overlapInput, topKInput].forEach((input) => {
    input.addEventListener("input", updateControls);
  });
  form.querySelectorAll("input[name='question_key']").forEach((input) => {
    input.addEventListener("change", () => {
      if (hasEvaluation) staleBadge.hidden = false;
    });
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    evaluate();
  });

  updateControls();
})();
