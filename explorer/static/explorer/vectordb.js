(() => {
  "use strict";

  const jobPosting = JSON.parse(document.getElementById("job-posting-data").textContent);
  const initialIndexStatus = JSON.parse(
    document.getElementById("index-status-data").textContent
  );

  const CANDIDATE_STYLE = {
    "elena-martinez": { className: "candidate-teal", tally: "tally-teal" },
    "marcus-reed": { className: "candidate-blue", tally: "tally-blue" },
    "olivia-grant": { className: "candidate-plum", tally: "tally-plum" }
  };

  const chunkSizeInput = document.getElementById("chunk-size");
  const overlapInput = document.getElementById("overlap");
  const chunkSizeOutput = document.getElementById("chunk-size-output");
  const overlapOutput = document.getElementById("overlap-output");
  const overlapMax = document.getElementById("overlap-max");
  const buildButton = document.getElementById("build-button");
  const buildStatus = document.getElementById("build-status");
  const dbStatusCard = document.getElementById("db-status-card");
  const dbChunkCount = document.getElementById("db-chunk-count");
  const dbDimensions = document.getElementById("db-dimensions");
  const dbFileSize = document.getElementById("db-file-size");
  const dbBuildSettings = document.getElementById("db-build-settings");
  const dbPerCandidate = document.getElementById("db-per-candidate");

  const queryForm = document.getElementById("query-form");
  const queryText = document.getElementById("query-text");
  const topKInput = document.getElementById("top-k");
  const topKOutput = document.getElementById("top-k-output");
  const searchButton = document.getElementById("search-button");
  const queryStatus = document.getElementById("query-status");
  const queryLockBadge = document.getElementById("query-lock-badge");
  const useJobPostingButton = document.getElementById("use-job-posting");

  const emptyState = document.getElementById("empty-state");
  const candidateTally = document.getElementById("candidate-tally");
  const resultsList = document.getElementById("results-list");

  let indexReady = false;

  function updateTrack(input) {
    const min = Number(input.min);
    const max = Number(input.max);
    const progress = ((Number(input.value) - min) / (max - min)) * 100;
    input.style.setProperty("--progress", `${progress}%`);
  }

  function updateBuildControls() {
    const chunkSize = Number(chunkSizeInput.value);
    const allowedOverlap = Math.min(70, chunkSize - 5);
    overlapInput.max = String(allowedOverlap);
    if (Number(overlapInput.value) > allowedOverlap) {
      overlapInput.value = String(Math.floor(allowedOverlap / 5) * 5);
    }

    chunkSizeOutput.textContent = `${chunkSize} words`;
    overlapOutput.textContent = `${overlapInput.value} words`;
    overlapMax.textContent = overlapInput.max;
    [chunkSizeInput, overlapInput].forEach(updateTrack);
  }

  function updateQueryControls() {
    topKOutput.textContent =
      `${topKInput.value} ${topKInput.value === "1" ? "chunk" : "chunks"}`;
    updateTrack(topKInput);
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  function setIndexReady(status) {
    indexReady = Boolean(status);
    searchButton.disabled = !indexReady;
    queryLockBadge.textContent = indexReady
      ? "Vector database ready"
      : "Build the database first";
    queryLockBadge.classList.toggle("ready", indexReady);

    if (!status) {
      dbStatusCard.hidden = true;
      return;
    }

    dbStatusCard.hidden = false;
    dbChunkCount.textContent = String(status.chunk_count);
    dbDimensions.textContent = String(status.dimensions);
    dbFileSize.textContent = formatBytes(status.file_size_bytes);
    dbBuildSettings.textContent =
      `${status.chunk_size}w chunks, ${status.overlap}w overlap`;

    if (status.chunks_per_document) {
      dbPerCandidate.replaceChildren(
        ...status.chunks_per_document.map((entry) => {
          const row = document.createElement("div");
          row.className = "db-per-candidate-row";
          const name = document.createElement("span");
          name.textContent = entry.candidate_name;
          const count = document.createElement("span");
          count.textContent = `${entry.chunk_count} chunks`;
          row.append(name, count);
          return row;
        })
      );
    }
  }

  async function buildIndex() {
    const buttonLabel = buildButton.querySelector("span");
    buildButton.disabled = true;
    buttonLabel.textContent = "Embedding & writing…";
    buildStatus.classList.remove("error");
    buildStatus.textContent =
      "Chunking all resumes, embedding every chunk, and writing candidates.sqlite3.";

    try {
      const response = await fetch(window.vectorDbLab.buildUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": queryForm.querySelector("[name='csrfmiddlewaretoken']").value
        },
        body: JSON.stringify({
          chunk_size: Number(chunkSizeInput.value),
          overlap: Number(overlapInput.value)
        })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "The vector database could not be built.");
      }

      setIndexReady(data);
      buildStatus.textContent =
        `Stored ${data.chunk_count} chunks (${data.dimensions} dims) in ` +
        `${formatBytes(data.file_size_bytes)}.`;
    } catch (error) {
      buildStatus.textContent = error.message;
      buildStatus.classList.add("error");
    } finally {
      buildButton.disabled = false;
      buttonLabel.textContent = "Build vector database";
    }
  }

  function candidateStyleFor(documentId) {
    return CANDIDATE_STYLE[documentId] || { className: "candidate-teal", tally: "tally-teal" };
  }

  function buildResultCard(result) {
    const style = candidateStyleFor(result.document_id);
    const card = document.createElement("article");
    card.className = `result-card ${style.className}`;

    const rank = document.createElement("span");
    rank.className = "result-rank";
    rank.textContent = String(result.rank).padStart(2, "0");

    const main = document.createElement("div");
    main.className = "result-main";

    const meta = document.createElement("div");
    meta.className = "result-meta";

    const badge = document.createElement("span");
    badge.className = "candidate-badge";
    badge.textContent = result.candidate_name;

    const position = document.createElement("span");
    position.className = "chunk-position";
    position.textContent =
      `words ${result.start_word}–${result.end_word} · ${result.word_count} words`;

    const headline = document.createElement("span");
    headline.className = "result-headline";
    headline.textContent = `${result.headline} · ${result.location}`;

    meta.append(badge, position, headline);

    const text = document.createElement("p");
    text.className = "result-text";
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

    main.append(meta, text, scoreRow);
    card.append(rank, main);
    return card;
  }

  function renderTally(results) {
    const counts = new Map();
    results.forEach((result) => {
      const key = result.document_id;
      const existing = counts.get(key) || { name: result.candidate_name, count: 0 };
      existing.count += 1;
      counts.set(key, existing);
    });

    candidateTally.hidden = counts.size === 0;
    candidateTally.replaceChildren(
      ...Array.from(counts.entries()).map(([documentId, entry]) => {
        const style = candidateStyleFor(documentId);
        const chip = document.createElement("span");
        chip.className = `tally-chip ${style.tally}`;
        const dot = document.createElement("i");
        const label = document.createElement("span");
        label.textContent = `${entry.name} · ${entry.count} of ${results.length}`;
        chip.append(dot, label);
        return chip;
      })
    );
  }

  async function runSearch() {
    const query = queryText.value.trim();
    if (!query) {
      queryStatus.textContent = "Enter a query or choose one of the examples.";
      queryStatus.classList.add("error");
      queryText.focus();
      return;
    }

    const buttonLabel = searchButton.querySelector("span");
    searchButton.disabled = true;
    buttonLabel.textContent = "Searching…";
    queryStatus.classList.remove("error");
    queryStatus.textContent = "Embedding the query and ranking every stored vector.";

    try {
      const response = await fetch(window.vectorDbLab.searchUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": queryForm.querySelector("[name='csrfmiddlewaretoken']").value
        },
        body: JSON.stringify({
          query,
          top_k: Number(topKInput.value)
        })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Search failed.");
      }

      emptyState.hidden = true;
      resultsList.replaceChildren(...data.results.map(buildResultCard));
      renderTally(data.results);
      queryStatus.textContent = `Found ${data.results.length} chunks across the vector database.`;
      if (data.index) setIndexReady(data.index);
    } catch (error) {
      queryStatus.textContent = error.message;
      queryStatus.classList.add("error");
    } finally {
      searchButton.disabled = !indexReady;
      buttonLabel.textContent = "Search vector database";
    }
  }

  [chunkSizeInput, overlapInput].forEach((input) => {
    input.addEventListener("input", updateBuildControls);
  });
  topKInput.addEventListener("input", updateQueryControls);

  buildButton.addEventListener("click", buildIndex);
  queryForm.addEventListener("submit", (event) => {
    event.preventDefault();
    runSearch();
  });

  document.querySelectorAll("[data-query]").forEach((button) => {
    button.addEventListener("click", () => {
      queryText.value = button.dataset.query;
      if (indexReady) runSearch();
    });
  });

  useJobPostingButton.addEventListener("click", () => {
    queryText.value = jobPosting;
    if (indexReady) runSearch();
  });

  updateBuildControls();
  updateQueryControls();
  setIndexReady(initialIndexStatus);
})();
