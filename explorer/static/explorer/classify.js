(() => {
  "use strict";

  const csrfToken = document.querySelector("[name='csrfmiddlewaretoken']").value;

  const chunkSizeInput = document.getElementById("chunk-size");
  const overlapInput = document.getElementById("overlap");
  const topKInput = document.getElementById("top-k");
  const chunkSizeOutput = document.getElementById("chunk-size-output");
  const overlapOutput = document.getElementById("overlap-output");
  const topKOutput = document.getElementById("top-k-output");
  const overlapMax = document.getElementById("overlap-max");
  const customQuestionInput = document.getElementById("custom-question");

  const runButton = document.getElementById("run-button");
  const runStatus = document.getElementById("run-status");
  const candidateRows = document.querySelectorAll(".candidate-row");

  const queryQuestionSelect = document.getElementById("query-question");
  const queryButton = document.getElementById("query-button");
  const queryStatus = document.getElementById("query-status");
  const queryResults = document.getElementById("query-results");

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
    topKOutput.textContent = `${topKInput.value} ${topKInput.value === "1" ? "chunk" : "chunks"}`;
    overlapMax.textContent = overlapInput.max;
    [chunkSizeInput, overlapInput, topKInput].forEach(updateTrack);
  }

  function selectedQuestion() {
    const selected = document.querySelector("input[name='question_key']:checked");
    if (!selected) return null;
    if (selected.value === "custom") {
      const text = customQuestionInput.value.trim();
      return text ? { question_key: "custom", question_text: text } : null;
    }
    return { question_key: selected.value, question_text: "" };
  }

  function setRowState(row, state, label) {
    row.classList.remove("is-running", "is-true", "is-false", "is-error");
    if (state) row.classList.add(state);
    row.querySelector("[data-role='status']").textContent = label;
  }

  function renderRowChunks(row, chunks) {
    const container = row.querySelector("[data-role='chunks']");
    if (!chunks || !chunks.length) {
      container.hidden = true;
      container.replaceChildren();
      return;
    }
    container.hidden = false;
    container.replaceChildren(
      ...chunks.map((chunk) => {
        const div = document.createElement("div");
        div.className = "candidate-row-chunk";
        div.textContent =
          `#${chunk.rank} · ${chunk.score.toFixed(3)} similarity · words ` +
          `${chunk.start_word}–${chunk.end_word}`;
        return div;
      })
    );
  }

  async function classifyOne(row, candidateId, question) {
    setRowState(row, "is-running", "Retrieving + classifying…");
    row.querySelector("[data-role='evidence']").textContent = "";

    const response = await fetch(window.classifyLab.runUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify({
        candidate_id: candidateId,
        question_key: question.question_key,
        question_text: question.question_text,
        chunk_size: Number(chunkSizeInput.value),
        overlap: Number(overlapInput.value),
        top_k: Number(topKInput.value)
      })
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Classification failed.");
    }

    renderRowChunks(row, data.chunks);

    const classification = data.classification;
    if (!classification.available) {
      setRowState(row, "is-error", "Unavailable");
      row.querySelector("[data-role='evidence']").textContent = classification.message;
      return;
    }

    setRowState(row, classification.answer ? "is-true" : "is-false", classification.answer ? "Yes" : "No");
    row.querySelector("[data-role='evidence']").textContent =
      `${classification.evidence} ${data.stored ? "· stored in database" : ""}`.trim();
  }

  async function runPipeline() {
    const question = selectedQuestion();
    if (!question) {
      runStatus.textContent = "Choose a rubric question or enter a custom one.";
      runStatus.classList.add("error");
      return;
    }

    const buttonLabel = runButton.querySelector("span");
    runButton.disabled = true;
    buttonLabel.textContent = "Classifying…";
    runStatus.classList.remove("error");

    candidateRows.forEach((row) => {
      setRowState(row, null, "Waiting");
      row.querySelector("[data-role='evidence']").textContent = "";
      renderRowChunks(row, []);
    });

    let index = 0;
    for (const row of candidateRows) {
      index += 1;
      const candidateId = row.dataset.candidateId;
      runStatus.textContent = `Classifying resume ${index} of ${candidateRows.length}…`;
      try {
        await classifyOne(row, candidateId, question);
      } catch (error) {
        setRowState(row, "is-error", "Error");
        row.querySelector("[data-role='evidence']").textContent = error.message;
      }
    }

    runStatus.textContent = "Done. Each resume was classified independently, one request at a time.";
    runButton.disabled = false;
    buttonLabel.textContent = "Classify all candidates";
  }

  function renderQueryResults(data) {
    if (!data.results.length) {
      queryResults.replaceChildren();
      const empty = document.createElement("p");
      empty.className = "query-empty";
      empty.textContent =
        "No stored classifications for this question yet. Run the pipeline above first.";
      queryResults.appendChild(empty);
      return;
    }

    queryResults.replaceChildren(
      ...data.results.map((result) => {
        const row = document.createElement("div");
        row.className = `query-result-row ${result.answer ? "answer-true" : "answer-false"}`;

        const icon = document.createElement("span");
        icon.className = "query-result-icon";
        icon.textContent = result.answer ? "Y" : "N";

        const body = document.createElement("div");
        body.className = "query-result-body";
        const name = document.createElement("div");
        name.className = "query-result-name";
        name.textContent = result.candidate_name;
        const evidence = document.createElement("div");
        evidence.className = "query-result-evidence";
        evidence.textContent = result.evidence;
        body.append(name, evidence);

        row.append(icon, body);
        return row;
      })
    );
  }

  async function runQuery() {
    const buttonLabel = queryButton.querySelector("span");
    queryButton.disabled = true;
    buttonLabel.textContent = "Querying…";
    queryStatus.classList.remove("error");
    queryStatus.textContent = "";

    try {
      const response = await fetch(window.classifyLab.queryUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ question_key: queryQuestionSelect.value })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Query failed.");
      }

      renderQueryResults(data);
      queryStatus.textContent =
        `${data.matched_count} of ${data.total_classified} classified candidates match.`;
    } catch (error) {
      queryStatus.textContent = error.message;
      queryStatus.classList.add("error");
    } finally {
      queryButton.disabled = false;
      buttonLabel.textContent = "Query database";
    }
  }

  [chunkSizeInput, overlapInput, topKInput].forEach((input) => {
    input.addEventListener("input", updateControls);
  });
  runButton.addEventListener("click", runPipeline);
  queryButton.addEventListener("click", runQuery);

  updateControls();
})();
