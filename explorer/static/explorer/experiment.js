(() => {
  "use strict";

  const csrfToken = document.querySelector("[name='csrfmiddlewaretoken']").value;
  const candidates = JSON.parse(document.getElementById("candidates-data").textContent);
  const questions = JSON.parse(document.getElementById("questions-data").textContent);

  const runButton = document.getElementById("run-button");
  const runStatus = document.getElementById("run-status");
  const progressFill = document.getElementById("progress-fill");
  const resultsSection = document.getElementById("results-section");
  const resultsTableBody = document.getElementById("results-table-body");
  const resultsQuestion = document.getElementById("results-question");
  const deltaBanner = document.getElementById("delta-banner");

  const CONFIG_NAMES = ["a", "b"];

  function configControls(name) {
    return {
      chunkSize: document.getElementById(`chunk-size-${name}`),
      overlap: document.getElementById(`overlap-${name}`),
      topK: document.getElementById(`top-k-${name}`),
      chunkSizeOutput: document.getElementById(`chunk-size-${name}-output`),
      overlapOutput: document.getElementById(`overlap-${name}-output`),
      topKOutput: document.getElementById(`top-k-${name}-output`),
      overlapMax: document.getElementById(`overlap-${name}-max`),
    };
  }

  const controls = { a: configControls("a"), b: configControls("b") };

  function updateTrack(input) {
    const min = Number(input.min);
    const max = Number(input.max);
    const progress = ((Number(input.value) - min) / (max - min)) * 100;
    input.style.setProperty("--progress", `${progress}%`);
  }

  function updateConfigControls(name) {
    const c = controls[name];
    const chunkSize = Number(c.chunkSize.value);
    const allowedOverlap = Math.min(70, chunkSize - 5);
    c.overlap.max = String(allowedOverlap);
    if (Number(c.overlap.value) > allowedOverlap) {
      c.overlap.value = String(Math.floor(allowedOverlap / 5) * 5);
    }

    c.chunkSizeOutput.textContent = `${chunkSize} words`;
    c.overlapOutput.textContent = `${c.overlap.value} words`;
    c.topKOutput.textContent = `${c.topK.value} ${c.topK.value === "1" ? "chunk" : "chunks"}`;
    c.overlapMax.textContent = c.overlap.max;
    [c.chunkSize, c.overlap, c.topK].forEach(updateTrack);
  }

  function readConfig(name) {
    const c = controls[name];
    return {
      chunkSize: Number(c.chunkSize.value),
      overlap: Number(c.overlap.value),
      topK: Number(c.topK.value),
    };
  }

  CONFIG_NAMES.forEach((name) => {
    const c = controls[name];
    [c.chunkSize, c.overlap, c.topK].forEach((input) => {
      input.addEventListener("input", () => updateConfigControls(name));
    });
    updateConfigControls(name);
  });

  function formatTokens(n) {
    return n.toLocaleString();
  }

  function formatLatency(ms) {
    return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
  }

  function formatPercent(fraction) {
    return `${(fraction * 100).toFixed(1)}%`;
  }

  function selectedQuestionKey() {
    const selected = document.querySelector("input[name='question_key']:checked");
    return selected ? selected.value : null;
  }

  function buildCellsList(questionKey) {
    return Object.entries(candidates).map(([candidateId, candidate]) => ({
      candidateId,
      candidateName: candidate.name,
      questionKey,
      key: candidateId,
    }));
  }

  function freshMetrics() {
    return {
      tp: 0,
      fp: 0,
      tn: 0,
      fn: 0,
      unavailable: 0,
      promptTokens: 0,
      thinkingTokens: 0,
      outputTokens: 0,
      totalTokens: 0,
      latencyMs: 0,
      calls: 0,
    };
  }

  function scoresFor(m) {
    const scored = m.tp + m.fp + m.tn + m.fn;
    const accuracy = scored ? (m.tp + m.tn) / scored : 0;
    const precision = m.tp + m.fp ? m.tp / (m.tp + m.fp) : 0;
    const recall = m.tp + m.fn ? m.tp / (m.tp + m.fn) : 0;
    const f1 = precision + recall ? (2 * precision * recall) / (precision + recall) : 0;
    return { accuracy, precision, recall, f1, scored };
  }

  function buildScoreBox(label, value) {
    const box = document.createElement("div");
    box.className = "metrics-score";
    const valueEl = document.createElement("span");
    valueEl.className = "value";
    valueEl.textContent = value;
    const labelEl = document.createElement("span");
    labelEl.className = "label";
    labelEl.textContent = label;
    box.append(valueEl, labelEl);
    return box;
  }

  function renderMetricsCard(name, config) {
    const card = document.querySelector(`.metrics-card[data-config="${name}"]`);
    const m = metrics[name];
    const scores = scoresFor(m);

    card.querySelector("[data-role='config-line']").textContent =
      `${config.chunkSize}w chunks · ${config.overlap}w overlap · top ${config.topK}`;

    const scoreEntries = [
      ["Accuracy", formatPercent(scores.accuracy)],
      ["Precision", formatPercent(scores.precision)],
      ["Recall", formatPercent(scores.recall)],
      ["F1", formatPercent(scores.f1)],
    ];
    card.querySelector("[data-role='scores']").replaceChildren(
      ...scoreEntries.map(([label, value]) => buildScoreBox(label, value))
    );

    card.querySelector("[data-role='footer']").textContent =
      `${m.tp}/${m.fp}/${m.tn}/${m.fn} TP/FP/TN/FN` +
      (m.unavailable ? ` · ${m.unavailable} unavailable` : "");
  }

  function renderCostCard(name) {
    const card = document.querySelector(`.metrics-card-cost[data-cost-config="${name}"]`);
    const m = metrics[name];

    const costEntries = [
      ["Total tokens", formatTokens(m.totalTokens)],
      ["Prompt", formatTokens(m.promptTokens)],
      ["Thinking", formatTokens(m.thinkingTokens)],
      ["Output", formatTokens(m.outputTokens)],
      ["Total latency", formatLatency(m.latencyMs)],
      ["Avg latency", m.calls ? formatLatency(m.latencyMs / m.calls) : "0ms"],
    ];
    card.querySelector("[data-role='cost-scores']").replaceChildren(
      ...costEntries.map(([label, value]) => buildScoreBox(label, value))
    );
  }

  function renderDelta(configA, configB) {
    const scoresA = scoresFor(metrics.a);
    const scoresB = scoresFor(metrics.b);
    const accuracyDeltaPts = (scoresB.accuracy - scoresA.accuracy) * 100;
    const tokenDeltaPct = metrics.a.totalTokens
      ? ((metrics.b.totalTokens - metrics.a.totalTokens) / metrics.a.totalTokens) * 100
      : 0;
    const latencyDeltaPct = metrics.a.latencyMs
      ? ((metrics.b.latencyMs - metrics.a.latencyMs) / metrics.a.latencyMs) * 100
      : 0;

    deltaBanner.hidden = false;
    deltaBanner.textContent =
      `Config B vs. Config A: ${accuracyDeltaPts >= 0 ? "+" : ""}${accuracyDeltaPts.toFixed(1)} ` +
      `accuracy points, ${tokenDeltaPct >= 0 ? "+" : ""}${tokenDeltaPct.toFixed(0)}% tokens, ` +
      `${latencyDeltaPct >= 0 ? "+" : ""}${latencyDeltaPct.toFixed(0)}% latency.`;
  }

  function buildRow(cell) {
    const row = document.createElement("tr");
    row.dataset.cellKey = cell.key;

    const candidateCell = document.createElement("td");
    candidateCell.className = "candidate-cell";
    candidateCell.textContent = cell.candidateName;

    const expectedCell = document.createElement("td");
    expectedCell.dataset.role = "expected";
    expectedCell.textContent = "–";

    const answerACell = document.createElement("td");
    answerACell.dataset.role = "answer-a";
    answerACell.appendChild(buildAnswerBadge(null));

    const answerBCell = document.createElement("td");
    answerBCell.dataset.role = "answer-b";
    answerBCell.appendChild(buildAnswerBadge(null));

    row.append(candidateCell, expectedCell, answerACell, answerBCell);
    return row;
  }

  function buildAnswerBadge(state) {
    const span = document.createElement("span");
    if (!state) {
      span.className = "cell-answer pending";
      span.textContent = "…";
      return span;
    }
    if (!state.available) {
      span.className = "cell-answer is-unavailable";
      span.textContent = "unavailable";
      return span;
    }
    span.className = `cell-answer ${state.correct ? "is-correct" : "is-incorrect"}`;
    span.textContent = `${state.answer ? "Yes" : "No"} ${state.correct ? "✓" : "✗"}`;
    return span;
  }

  function renderCellResult(configName, cell, data) {
    const row = resultsTableBody.querySelector(`tr[data-cell-key="${cell.key}"]`);
    const expectedCell = row.querySelector("[data-role='expected']");
    if (expectedCell.textContent === "–") {
      expectedCell.textContent = data.expected ? "Yes" : "No";
    }

    const answerCell = row.querySelector(`[data-role='answer-${configName}']`);
    const classification = data.classification;
    answerCell.replaceChildren(
      buildAnswerBadge(
        classification.available
          ? { available: true, answer: classification.answer, correct: data.correct }
          : { available: false }
      )
    );
  }

  let metrics = { a: freshMetrics(), b: freshMetrics() };

  function recordResult(configName, config, classification) {
    const m = metrics[configName];
    m.calls += 1;
    m.latencyMs += classification.latency_ms || 0;

    if (!classification.available) {
      m.unavailable += 1;
      renderMetricsCard(configName, config);
      renderCostCard(configName);
      return;
    }

    const usage = classification.usage || {};
    m.promptTokens += usage.prompt_tokens || 0;
    m.thinkingTokens += usage.thinking_tokens || 0;
    m.outputTokens += usage.output_tokens || 0;
    m.totalTokens += usage.total_tokens || 0;
    renderMetricsCard(configName, config);
    renderCostCard(configName);
  }

  function recordConfusion(configName, expected, predicted) {
    const m = metrics[configName];
    if (expected && predicted) m.tp += 1;
    else if (!expected && !predicted) m.tn += 1;
    else if (!expected && predicted) m.fp += 1;
    else m.fn += 1;
  }

  async function runCell(config, cell) {
    const response = await fetch(window.experimentLab.runCellUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify({
        candidate_id: cell.candidateId,
        question_key: cell.questionKey,
        chunk_size: config.chunkSize,
        overlap: config.overlap,
        top_k: config.topK,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Experiment cell failed.");
    }
    return data;
  }

  async function runComparison() {
    const questionKey = selectedQuestionKey();
    if (!questionKey) {
      runStatus.textContent = "Choose a question to test.";
      runStatus.classList.add("error");
      return;
    }
    const question = questions[questionKey];

    const cells = buildCellsList(questionKey);
    const totalCalls = cells.length * CONFIG_NAMES.length;
    let completed = 0;

    const buttonLabel = runButton.querySelector("span");
    runButton.disabled = true;
    buttonLabel.textContent = "Running…";
    runStatus.classList.remove("error");
    progressFill.style.width = "0%";

    metrics = { a: freshMetrics(), b: freshMetrics() };
    deltaBanner.hidden = true;
    resultsSection.hidden = false;
    resultsQuestion.innerHTML = "";
    resultsQuestion.append("Testing: ");
    const questionStrong = document.createElement("strong");
    questionStrong.textContent = question.label;
    resultsQuestion.append(questionStrong, ` — “${question.question}”`);
    resultsTableBody.replaceChildren(...cells.map(buildRow));

    const configs = { a: readConfig("a"), b: readConfig("b") };
    CONFIG_NAMES.forEach((name) => {
      renderMetricsCard(name, configs[name]);
      renderCostCard(name);
    });

    for (const configName of CONFIG_NAMES) {
      const config = configs[configName];
      for (const cell of cells) {
        runStatus.textContent =
          `Config ${configName.toUpperCase()}: ${cell.candidateName} ` +
          `(${completed + 1} of ${totalCalls})`;
        try {
          const data = await runCell(config, cell);
          renderCellResult(configName, cell, data);
          recordResult(configName, config, data.classification);
          if (data.classification.available) {
            recordConfusion(configName, data.expected, data.classification.answer);
            renderMetricsCard(configName, config);
          }
        } catch (error) {
          runStatus.textContent = error.message;
          runStatus.classList.add("error");
        }
        completed += 1;
        progressFill.style.width = `${(completed / totalCalls) * 100}%`;
      }
    }

    renderDelta(configs.a, configs.b);
    runStatus.textContent = "Comparison complete.";
    runButton.disabled = false;
    buttonLabel.textContent = "Run comparison";
  }

  runButton.addEventListener("click", runComparison);
})();
