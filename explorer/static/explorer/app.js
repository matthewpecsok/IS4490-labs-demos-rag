(() => {
  "use strict";

  const resume = JSON.parse(document.getElementById("resume-data").textContent);
  const chunkSizeInput = document.getElementById("chunk-size");
  const overlapInput = document.getElementById("overlap");
  const topKInput = document.getElementById("top-k");
  const chunkSizeOutput = document.getElementById("chunk-size-output");
  const overlapOutput = document.getElementById("overlap-output");
  const topKOutput = document.getElementById("top-k-output");
  const overlapMaxLabel = document.getElementById("overlap-max-label");
  const chunksGrid = document.getElementById("chunks-grid");
  const summaryChunks = document.getElementById("summary-chunks");
  const summaryUnique = document.getElementById("summary-unique");
  const configurationNote = document.getElementById("configuration-note");
  const searchForm = document.getElementById("search-form");
  const searchInput = document.getElementById("search-query");
  const searchMessage = document.getElementById("search-message");
  const resultSummary = document.getElementById("result-summary");

  let currentChunks = [];
  let currentResults = new Map();

  function wordsFromText(text) {
    return text.trim().split(/\s+/);
  }

  function createChunks(text, chunkSize, overlap) {
    const words = wordsFromText(text);
    const chunks = [];
    const step = chunkSize - overlap;

    for (let start = 0; start < words.length; start += step) {
      const chunkWords = words.slice(start, start + chunkSize);
      if (!chunkWords.length) break;

      chunks.push({
        id: chunks.length,
        words: chunkWords,
        startWord: start + 1,
        endWord: start + chunkWords.length,
        overlapCount: chunks.length ? Math.min(overlap, chunkWords.length) : 0
      });

      if (start + chunkSize >= words.length) break;
    }
    return chunks;
  }

  function updateRangeTrack(input) {
    const min = Number(input.min);
    const max = Number(input.max);
    const value = Number(input.value);
    const progress = ((value - min) / (max - min)) * 100;
    input.style.setProperty("--range-progress", `${progress}%`);
  }

  function appendChunkWords(container, chunk) {
    chunk.words.forEach((word, index) => {
      const span = document.createElement("span");
      span.textContent = word;

      if (index < chunk.overlapCount) {
        span.classList.add("overlap-word");
      }

      container.appendChild(span);
      if (index < chunk.words.length - 1) {
        container.appendChild(document.createTextNode(" "));
      }
    });
  }

  function buildChunkCard(chunk) {
    const result = currentResults.get(chunk.id);
    const card = document.createElement("article");
    card.className = `chunk-card${result ? " search-result" : ""}`;
    card.dataset.chunkId = String(chunk.id);

    if (result) {
      const rank = document.createElement("span");
      rank.className = "rank-badge";
      rank.textContent = `#${result.rank} result`;
      card.appendChild(rank);
    }

    const top = document.createElement("div");
    top.className = "chunk-card-top";

    const id = document.createElement("span");
    id.className = "chunk-id";
    id.textContent = `CHUNK ${String(chunk.id + 1).padStart(2, "0")}`;

    const range = document.createElement("span");
    range.className = "chunk-range";
    range.textContent = `words ${chunk.startWord}–${chunk.endWord}`;
    top.append(id, range);

    const text = document.createElement("p");
    text.className = "chunk-text";
    appendChunkWords(text, chunk);

    const footer = document.createElement("div");
    footer.className = "chunk-footer";
    const count = document.createElement("span");
    count.textContent = `${chunk.words.length} words`;
    footer.appendChild(count);

    if (result) {
      const scoreWrap = document.createElement("div");
      scoreWrap.className = "score-wrap";

      const bar = document.createElement("span");
      bar.className = "score-bar";
      const fill = document.createElement("i");
      const normalizedWidth = Math.max(4, Math.min(100, result.score * 100));
      fill.style.width = `${normalizedWidth}%`;
      bar.appendChild(fill);

      const score = document.createElement("span");
      score.textContent = `${result.score.toFixed(3)} similarity`;
      scoreWrap.append(bar, score);
      footer.appendChild(scoreWrap);
    } else if (chunk.overlapCount) {
      const overlap = document.createElement("span");
      overlap.textContent = `${chunk.overlapCount} repeated`;
      footer.appendChild(overlap);
    }

    card.append(top, text, footer);
    return card;
  }

  function renderChunks() {
    chunksGrid.replaceChildren(...currentChunks.map(buildChunkCard));
  }

  function noteForSettings(chunkSize, overlap) {
    const ratio = overlap / chunkSize;
    if (chunkSize <= 40) {
      return "Smaller chunks are precise, but an idea may be split across boundaries.";
    }
    if (chunkSize >= 150) {
      return "Larger chunks preserve context, but may introduce unrelated details.";
    }
    if (ratio >= 0.5) {
      return "Heavy overlap protects boundary context, with more repeated content to embed.";
    }
    if (ratio === 0) {
      return "No overlap means efficient storage, but boundary-spanning ideas can be lost.";
    }
    return "A balanced starting point for paragraph-sized ideas.";
  }

  function clearSearchResults() {
    currentResults = new Map();
    resultSummary.hidden = true;
    resultSummary.textContent = "";
    searchMessage.textContent = "";
    searchMessage.classList.remove("error");
  }

  function updateConfiguration({ clearResults = true } = {}) {
    const chunkSize = Number(chunkSizeInput.value);
    const allowedOverlap = Math.max(0, chunkSize - 5);

    overlapInput.max = String(Math.min(70, allowedOverlap));
    if (Number(overlapInput.value) > allowedOverlap) {
      overlapInput.value = String(Math.floor(allowedOverlap / 5) * 5);
    }

    const overlap = Number(overlapInput.value);
    const topK = Number(topKInput.value);

    chunkSizeOutput.textContent = `${chunkSize} words`;
    overlapOutput.textContent = `${overlap} words`;
    topKOutput.textContent = `${topK} ${topK === 1 ? "chunk" : "chunks"}`;
    overlapMaxLabel.textContent = `${overlapInput.max} words`;

    [chunkSizeInput, overlapInput, topKInput].forEach(updateRangeTrack);

    currentChunks = createChunks(resume, chunkSize, overlap);
    summaryChunks.textContent = String(currentChunks.length);
    summaryUnique.textContent = `${Math.round(((chunkSize - overlap) / chunkSize) * 100)}%`;
    configurationNote.textContent = noteForSettings(chunkSize, overlap);

    if (clearResults) clearSearchResults();
    renderChunks();
  }

  async function runSearch() {
    const query = searchInput.value.trim();
    if (!query) {
      searchMessage.textContent = "Enter a search term or choose one of the examples.";
      searchMessage.classList.add("error");
      searchInput.focus();
      return;
    }

    const submitButton = searchForm.querySelector("button[type='submit']");
    const buttonLabel = submitButton.querySelector("span");
    submitButton.disabled = true;
    buttonLabel.textContent = "Embedding…";
    searchMessage.classList.remove("error");
    searchMessage.textContent = "Comparing your query with every chunk. The first search may download the model.";

    try {
      const response = await fetch(window.chunkLab.searchUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": searchForm.querySelector("[name='csrfmiddlewaretoken']").value
        },
        body: JSON.stringify({
          query,
          chunk_size: Number(chunkSizeInput.value),
          overlap: Number(overlapInput.value),
          top_k: Number(topKInput.value)
        })
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Search failed.");
      }

      currentResults = new Map(data.results.map((result) => [result.id, result]));
      renderChunks();

      resultSummary.hidden = false;
      resultSummary.textContent =
        `Showing the ${data.results.length} most similar chunks for “${query}”. ` +
        "Similarity is cosine similarity; higher values indicate closer meaning.";
      searchMessage.textContent = `Search complete using ${data.model}.`;

      const firstResult = document.querySelector(".chunk-card.search-result");
      if (firstResult) {
        firstResult.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    } catch (error) {
      searchMessage.textContent = error.message;
      searchMessage.classList.add("error");
    } finally {
      submitButton.disabled = false;
      buttonLabel.textContent = "Run search";
    }
  }

  chunkSizeInput.addEventListener("input", () => updateConfiguration());
  overlapInput.addEventListener("input", () => updateConfiguration());
  topKInput.addEventListener("input", () => {
    topKOutput.textContent = `${topKInput.value} ${topKInput.value === "1" ? "chunk" : "chunks"}`;
    updateRangeTrack(topKInput);
    clearSearchResults();
    renderChunks();
  });

  searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    runSearch();
  });

  document.querySelectorAll("[data-query]").forEach((button) => {
    button.addEventListener("click", () => {
      searchInput.value = button.dataset.query;
      runSearch();
    });
  });

  updateConfiguration({ clearResults: false });
})();
