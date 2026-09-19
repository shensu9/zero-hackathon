const scenarioGrid = document.querySelector("#scenario-grid");
const benchmarkGrid = document.querySelector("#benchmark-grid");
const detailSection = document.querySelector("#scenario-detail-section");
const detailContainer = document.querySelector("#scenario-detail");
const closeDetail = document.querySelector("#close-detail");

let scenariosById = new Map();

function statusClass(status) {
  return `status-${status.toLowerCase().replaceAll("_", "-")}`;
}

async function loadScenarios() {
  const response = await fetch("/api/scenarios");
  if (!response.ok) throw new Error("Scenario request failed");

  const data = await response.json();

  scenariosById = new Map(
    data.scenarios.map((scenario) => [scenario.id, scenario])
  );

  scenarioGrid.innerHTML = data.scenarios.map((scenario) => `
    <article class="card scenario-card" data-scenario-id="${scenario.id}" role="button" tabindex="0">
      <p class="card-kicker">${scenario.id}</p>
      <h3>${scenario.name}</h3>
      <p>${scenario.goal}</p>
      <p>${scenario.summary}</p>
      <span class="status ${statusClass(scenario.status)}">
        ${scenario.status}
      </span>
      <div class="scenario-action">
        View decision trace →
      </div>
    </article>
  `).join("");
}

async function loadBenchmarks() {
  const response = await fetch("/api/benchmarks");
  if (!response.ok) throw new Error("Benchmark request failed");

  const data = await response.json();
  const repeated = data.repeated;

  benchmarkGrid.innerHTML = `
    <article class="card metric">
      <p class="card-kicker">Repeated benchmark</p>
      <div class="metric-value">${repeated.reduction_percent.toFixed(1)}%</div>
      <div class="metric-label">fewer medium/high evaluator findings</div>
    </article>

    <article class="card metric">
      <p class="card-kicker">Paired runs</p>
      <div class="metric-value">${repeated.paired_case_runs}</div>
      <div class="metric-label">
        ZERO wins ${repeated.zero_wins} · ties ${repeated.ties} · baseline wins ${repeated.baseline_wins}
      </div>
    </article>

    <article class="card metric">
      <p class="card-kicker">Neutral evaluator</p>
      <div class="metric-value">${data.evaluator.holdout_matched}/${data.evaluator.holdout_total}</div>
      <div class="metric-label">holdout cases matched</div>
    </article>

    <article class="card metric">
      <p class="card-kicker">Unseen suite</p>
      <div class="metric-value">${data.unseen.completed_cases}/${data.unseen.total_cases}</div>
      <div class="metric-label">completed · preserved failure included</div>
    </article>
  `;
}

function openScenarioDetail(id) {
  const scenario = scenariosById.get(id);

  if (!scenario) return;

  const traceItems = scenario.decision_trace
    .map((item) => `<li>${item}</li>`)
    .join("");

  const requirementText =
    scenario.requirements !== undefined
      ? `<p><strong>Requirements:</strong> ${scenario.requirements}</p>`
      : "";

  detailContainer.innerHTML = `
    <div class="detail-heading-row">
      <div>
        <p class="card-kicker">${scenario.id} / ${scenario.name}</p>
        <span class="status ${statusClass(scenario.status)}">
          ${scenario.status}
        </span>
      </div>
    </div>

    <p class="detail-goal">${scenario.goal}</p>
    <p>${scenario.summary}</p>
    ${requirementText}

    <h3>Why ZERO returned this outcome</h3>
    <ol class="decision-trace">
      ${traceItems}
    </ol>
  `;

  detailSection.hidden = false;

  detailSection.scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
}

scenarioGrid.addEventListener("click", (event) => {
  const card = event.target.closest(".scenario-card");

  if (!card) return;

  openScenarioDetail(card.dataset.scenarioId);
});

scenarioGrid.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;

  const card = event.target.closest(".scenario-card");

  if (!card) return;

  event.preventDefault();
  openScenarioDetail(card.dataset.scenarioId);
});

closeDetail.addEventListener("click", () => {
  detailSection.hidden = true;
});

async function main() {
  try {
    await Promise.all([
      loadScenarios(),
      loadBenchmarks(),
    ]);
  } catch (error) {
    console.error(error);
    scenarioGrid.textContent = "Unable to load preserved evidence.";
    benchmarkGrid.textContent = "Unable to load benchmark evidence.";
  }
}

main();
