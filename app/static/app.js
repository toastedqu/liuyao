const form = document.querySelector("#divination-form");
const linesContainer = document.querySelector("#lines");
const submitButton = document.querySelector("#submit");
const errorBox = document.querySelector("#error");
const result = document.querySelector("#result");

const lineNames = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"];
const lineValues = [
  [6, "老阴 6（动，变阳）"],
  [7, "少阳 7（静）"],
  [8, "少阴 8（静）"],
  [9, "老阳 9（动，变阴）"],
];
const usefulGodOptions = [
  ["", "请选择用神"],
  ["世爻", "世爻（问自身或以自己为主）"],
  ["应爻", "应爻（问对方或外人）"],
  ["父母", "父母（父母、长辈、文书、宅舍等）"],
  ["兄弟", "兄弟（兄弟姐妹、同辈等）"],
  ["官鬼", "官鬼（丈夫、功名、官府等）"],
  ["妻财", "妻财（妻子、财物等）"],
  ["子孙", "子孙（子女、晚辈、医药等）"],
];

function ensureUsefulGodSelector() {
  const existing = document.querySelector("#useful-god");
  if (existing) return existing;

  const question = document.querySelector("#question");
  if (!question) {
    throw new Error("页面加载不完整，请刷新后重试。");
  }

  const label = document.createElement("label");
  label.htmlFor = "useful-god";
  label.textContent = "用神";

  const select = document.createElement("select");
  select.id = "useful-god";
  select.name = "useful_god";
  select.required = true;
  usefulGodOptions.forEach(([value, text], index) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = text;
    if (index === 0) {
      option.disabled = true;
      option.selected = true;
    }
    select.append(option);
  });

  const help = document.createElement("small");
  help.textContent =
    "只选择用神类别；具体用神爻位由系统依据《增删卜易》确定。婚恋通常男问女取妻财，女问男取官鬼。";
  question.after(label, select, help);
  return select;
}

function buildLines() {
  lineNames.forEach((name, index) => {
    const row = document.createElement("div");
    row.className = "line-row";
    const label = document.createElement("strong");
    label.textContent = name;
    row.append(label);

    const options = document.createElement("div");
    options.className = "line-options";
    lineValues.forEach(([value, text]) => {
      const option = document.createElement("label");
      option.className = "inline";
      const input = document.createElement("input");
      input.type = "radio";
      input.name = `line-${index}`;
      input.value = String(value);
      input.required = true;
      option.append(input, document.createTextNode(text));
      options.append(option);
    });
    row.append(options);
    linesContainer.append(row);
  });
}

function setDefaultDate() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    hourCycle: "h23",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  ["year", "month", "day", "hour"].forEach((key) => {
    document.querySelector(`#${key}`).value = values[key];
  });
}

function requestPayload() {
  return {
    question: document.querySelector("#question").value.trim(),
    useful_god: ensureUsefulGodSelector().value,
    calendar: {
      year: Number(document.querySelector("#year").value),
      month: Number(document.querySelector("#month").value),
      day: Number(document.querySelector("#day").value),
      hour: Number(document.querySelector("#hour").value),
      timezone: "Asia/Shanghai",
    },
    lines: lineNames.map((name, index) => {
      const selected = document.querySelector(
        `input[name='line-${index}']:checked`
      );
      if (!selected) throw new Error(`请选择${name}。`);
      return Number(selected.value);
    }),
  };
}

function messageFromError(payload, status) {
  if (Array.isArray(payload?.detail)) {
    return payload.detail
      .map((item) => `${item.loc.slice(1).join(".")}：${item.msg}`)
      .join("\n");
  }
  if (typeof payload?.detail === "string") {
    return payload.detail;
  }
  if (payload?.detail?.message) {
    const rationale = Array.isArray(payload.detail.rationale)
      ? `\n依据：${payload.detail.rationale.join("；")}`
      : "";
    const issues = Array.isArray(payload.detail.issues)
      ? `\n校验问题：${payload.detail.issues
          .map((item) => item.message || item.code)
          .join("；")}`
      : "";
    return `${payload.detail.message}${rationale}${issues}`;
  }
  return `请求失败（HTTP ${status}）`;
}

function display(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) return value.length ? value.join("、") : "—";
  return String(value);
}

function appendHeading(container, text) {
  const heading = document.createElement("h3");
  heading.textContent = text;
  container.append(heading);
}

function appendDefinitions(container, entries) {
  const list = document.createElement("dl");
  entries.forEach(([term, value]) => {
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = display(value);
    list.append(dt, dd);
  });
  container.append(list);
}

function appendTable(container, columns, rows) {
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  columns.forEach(([label]) => {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = label;
    headRow.append(th);
  });
  head.append(headRow);
  const body = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    columns.forEach(([, read]) => {
      const td = document.createElement("td");
      td.textContent = display(read(row));
      tr.append(td);
    });
    body.append(tr);
  });
  table.append(head, body);
  container.append(table);
}

function renderInputSummary(payload) {
  appendHeading(result, "1. 输入摘要");
  const summary = payload.input_summary;
  appendDefinitions(result, [
    ["所占之事", summary.question],
    ["模型判定占类", summary.category],
    ["模型判定问占视角", summary.perspective],
    ["公历时间", summary.calendar],
    ["时区", summary.timezone],
    ["爻序", summary.line_order],
  ]);
}

function renderCalendar(payload) {
  appendHeading(result, "2. 历法信息");
  const calendar = payload.calendar;
  appendDefinitions(result, [
    ["月建", calendar.month_pillar.ganzhi.branch],
    ["月柱", `${calendar.month_pillar.ganzhi.stem}${calendar.month_pillar.ganzhi.branch}`],
    ["日柱", `${calendar.day_pillar.ganzhi.stem}${calendar.day_pillar.ganzhi.branch}`],
    [
      "旬空",
      `${calendar.day_pillar.void_branches.first}${calendar.day_pillar.void_branches.second}`,
    ],
    ["日干", calendar.day_pillar.ganzhi.stem],
    [
      "本月交节",
      `${calendar.month_pillar.starting_jie.name} ${calendar.month_pillar.starting_jie.moment}`,
    ],
    [
      "下次交节",
      `${calendar.month_pillar.next_jie.name} ${calendar.month_pillar.next_jie.moment}`,
    ],
    ["换算说明", calendar.near_boundary_note],
  ]);
}

function renderHexagrams(payload) {
  appendHeading(result, "3. 主卦和变卦");
  appendTable(
    result,
    [
      ["", (row) => row.label],
      ["卦名", (row) => row.hexagram.name],
      ["上下卦", (row) => `${row.hexagram.upper_trigram}上${row.hexagram.lower_trigram}下`],
      ["卦宫", (row) => `${row.hexagram.palace}宫`],
      ["宫五行", (row) => row.hexagram.palace_element],
      ["宫序", (row) => row.hexagram.palace_stage],
      [
        "卦象",
        (row) =>
          [
            row.hexagram.is_six_clash ? "六冲" : null,
            row.hexagram.is_six_harmony ? "六合" : null,
            row.hexagram.is_wandering_soul ? "游魂" : null,
            row.hexagram.is_returning_soul ? "归魂" : null,
          ].filter(Boolean),
      ],
    ],
    [
      {label: "主卦", hexagram: payload.primary_hexagram},
      {label: "变卦", hexagram: payload.changed_hexagram},
    ]
  );
}

function renderLines(payload) {
  appendHeading(result, "4. 六爻排盘");
  appendTable(
    result,
    [
      ["爻位", (line) => line.name],
      ["六神", (line) => line.spirit],
      [
        "伏神",
        (line) =>
          line.hidden_spirit
            ? `${line.hidden_spirit.relative} ${line.hidden_spirit.stem}${line.hidden_spirit.branch}${line.hidden_spirit.element}`
            : "—",
      ],
      ["六亲", (line) => line.relative],
      ["纳甲", (line) => `${line.stem}${line.branch}${line.element}`],
      ["阴阳", (line) => (line.is_yang ? "阳" : "阴")],
      [
        "世应",
        (line) => [line.is_world ? "世" : null, line.is_response ? "应" : null].filter(Boolean),
      ],
      ["动静", (line) => (line.is_moving ? "动" : "静")],
      [
        "变爻",
        (line) =>
          line.changed
            ? `${line.changed.relative} ${line.changed.stem}${line.changed.branch}${line.changed.element}（${line.changed.is_yang ? "阳" : "阴"}）`
            : "—",
      ],
    ],
    [...payload.lines].reverse()
  );
}

function renderUsefulGod(payload) {
  appendHeading(result, "5. 用神");
  const useful = payload.useful_god;
  if (!useful) {
    result.append(document.createTextNode("占类尚未确认，未选择用神。"));
    return;
  }
  appendDefinitions(result, [
    ["状态", useful.status],
    ["占问对象", useful.target],
    [
      "判定方式",
      { world: "世爻", response: "应爻", relative: "六亲" }[
        useful.selection_mode
      ] || useful.selection_mode,
    ],
    ["采用六亲", useful.useful_relative],
    ["采用爻位", useful.selected_line ? `第${useful.selected_line}爻` : null],
    [
      "全部候选",
      useful.candidates?.map((candidate) =>
        `第${candidate.line}爻 ${candidate.relative} ${candidate.branch}${candidate.element}`
      ),
    ],
    ["用神五行", useful.useful_element],
    ["元神", useful.yuan_element],
    ["忌神", useful.taboo_element],
    ["仇神", useful.enemy_element],
    ["选择依据", useful.rationale],
    ["原文依据", useful.source_ids],
  ]);
}

function renderFacts(payload) {
  appendHeading(result, "6. 卦象事实");
  appendTable(
    result,
    [
      ["事实 ID", (fact) => fact.id],
      ["类型", (fact) => fact.type],
      ["爻位", (fact) => (fact.line ? `第${fact.line}爻` : "全卦")],
      ["结果", (fact) => typeof fact.value === "object" ? JSON.stringify(fact.value) : fact.value],
      ["规则出处", (fact) => fact.rule_source],
    ],
    payload.facts
  );
}

function renderOutcomeEvidence(payload) {
  appendHeading(result, "7. 吉凶裁决证据");
  const analysis = payload.outcome_analysis;
  if (!analysis) {
    result.append(document.createTextNode("尚未判定用神，不生成吉凶裁决证据。"));
    return;
  }
  appendDefinitions(result, [
    ["质量控制结论", analysis.guardrail],
    ["限制", analysis.limitations],
    ["说明", "卦例不计入吉凶权重；仅用神及有效元忌相关事实可进入裁决。"],
  ]);
  appendTable(
    result,
    [
      ["证据 ID", (item) => item.id],
      ["方向", (item) => item.direction],
      ["层级", (item) => item.weight],
      ["说明", (item) => item.description],
      ["事实", (item) => item.fact_ids],
      ["原文", (item) => item.source_ids],
    ],
    analysis.evidence
  );
}

function appendJudgement(container, judgement) {
  const item = document.createElement("li");
  const statement = document.createElement("p");
  statement.textContent = judgement.statement;
  item.append(statement);
  if (judgement.fact_ids.length) {
    const facts = document.createElement("small");
    facts.textContent = `事实：${judgement.fact_ids.join("、")}`;
    item.append(facts);
  }
  judgement.citations.forEach((citation) => {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = citation.source_id;
    const quote = document.createElement("blockquote");
    quote.textContent = citation.quote;
    details.append(summary, quote);
    item.append(details);
  });
  container.append(item);
}

function appendJudgements(container, judgements) {
  if (!judgements?.length) return;
  const list = document.createElement("ul");
  judgements.forEach((judgement) => appendJudgement(list, judgement));
  container.append(list);
}

function renderInterpretation(payload) {
  appendHeading(result, "8. 断卦结论");
  const interpretation = payload.interpretation;
  const lead = document.createElement("p");
  lead.textContent = `${interpretation.overall.outlook}：${interpretation.overall.summary}`;
  result.append(lead);
  appendJudgements(result, interpretation.overall.judgements);

  const applicationHeading = document.createElement("h4");
  applicationHeading.textContent = "与所占之事的对应";
  result.append(applicationHeading);
  appendDefinitions(result, [
    ["本次判断焦点", interpretation.question_application.focus],
  ]);
  [
    ["有利因素", interpretation.question_application.favorable],
    ["不利因素", interpretation.question_application.adverse],
    ["具体综合判断", [interpretation.question_application.synthesis]],
  ].forEach(([label, judgements]) => {
    const heading = document.createElement("h5");
    heading.textContent = label;
    result.append(heading);
    appendJudgements(result, judgements);
  });

  [
    ["用神分析", interpretation.useful_god.judgements],
    ["月建日辰", interpretation.month_day.judgements],
    ["动爻和元忌", interpretation.moving_lines.judgements],
  ].forEach(([label, judgements]) => {
    const heading = document.createElement("h4");
    heading.textContent = label;
    result.append(heading);
    appendJudgements(result, judgements);
  });
  interpretation.special_patterns.patterns.forEach((pattern) => {
    const heading = document.createElement("h4");
    heading.textContent = `特殊格局：${pattern.name}`;
    result.append(heading);
    appendJudgements(result, pattern.judgements);
  });
  interpretation.risks.items.forEach((risk) => {
    const heading = document.createElement("h4");
    heading.textContent = `条件与限制：${risk.description}`;
    result.append(heading);
    appendJudgements(result, risk.judgements);
  });
}

function appendCaseSource(container, label, source) {
  if (!source) return;
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = `${label} · ${source.source_id}`;
  const quote = document.createElement("blockquote");
  quote.textContent = source.text;
  details.append(summary, quote);
  container.append(details);
}

function renderCaseReasoning(payload) {
  appendHeading(result, "9. 卦例参考（不参与吉凶权重）");
  const comparisons = new Map(
    (payload.interpretation?.case_analysis?.comparisons || [])
      .map((comparison) => [comparison.example_id, comparison])
  );
  if (!payload.case_evidence?.length) {
    result.append(document.createTextNode("本次没有检索到可用的完整卦例。"));
    return;
  }

  payload.case_evidence.forEach((evidence) => {
    const article = document.createElement("article");
    article.className = "case-evidence";
    const heading = document.createElement("h4");
    heading.textContent = `${evidence.example_id} · ${evidence.chapter_title}`;
    article.append(heading);
    appendDefinitions(article, [
      ["参考检索分（非吉凶分）", evidence.match_score],
      ["检索原因", evidence.match_reasons],
      ["是否完成参考比照", comparisons.has(evidence.example_id) ? "是" : "否"],
    ]);

    const comparison = comparisons.get(evidence.example_id);
    if (comparison) {
      [
        ["相似点", comparison.similarities],
        ["关键差异", comparison.differences],
        ["方法参考边界", comparison.application],
      ].forEach(([label, judgement]) => {
        const subheading = document.createElement("h5");
        subheading.textContent = label;
        article.append(subheading);
        appendJudgements(article, [judgement]);
      });
    }

    appendCaseSource(article, "原占问", evidence.question);
    appendCaseSource(article, "原卦盘", evidence.chart);
    appendCaseSource(article, "原断语与应验", evidence.judgement);
    result.append(article);
  });
}

function renderTiming(payload) {
  appendHeading(result, "10. 应期候选");
  appendTable(
    result,
    [
      ["候选 ID", (candidate) => candidate.id],
      ["规则", (candidate) => candidate.trigger],
      ["候选地支", (candidate) => candidate.branches],
      ["时间范围", (candidate) => candidate.time_unit_hint],
      ["限制", (candidate) => candidate.confidence_limit],
      ["原文依据", (candidate) => candidate.source_ids],
    ],
    payload.timing_candidates
  );
  if (payload.interpretation) {
    appendDefinitions(result, [
      ["模型选择", payload.interpretation.timing.candidate_ids],
      [
        "证据不足",
        payload.interpretation.timing.insufficient_evidence ? "是，不输出确定日期" : "否",
      ],
    ]);
    appendJudgements(result, payload.interpretation.timing.judgements);
  }
}

function renderSources(payload) {
  appendHeading(result, "11. 原文依据");
  payload.sources.forEach((source) => {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = `${source.source_id} · ${source.chapter_title}`;
    const meta = document.createElement("p");
    meta.textContent = `类型：${source.content_type}；源文件：${source.source_path}`;
    const text = document.createElement("blockquote");
    text.textContent = source.text;
    details.append(summary, meta, text);
    result.append(details);
  });
}

function renderResponse(payload) {
  result.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = "排盘与断卦结果";
  result.append(title);
  renderInputSummary(payload);
  renderCalendar(payload);
  renderHexagrams(payload);
  renderLines(payload);
  renderUsefulGod(payload);
  renderFacts(payload);
  renderOutcomeEvidence(payload);
  if (payload.interpretation) {
    renderInterpretation(payload);
    renderCaseReasoning(payload);
  }
  renderTiming(payload);
  if (payload.sources) renderSources(payload);
  if (payload.limitations?.length) {
    appendHeading(result, "未实现或不作确定判断的规则");
    const list = document.createElement("ul");
    payload.limitations.forEach((limitation) => {
      const item = document.createElement("li");
      item.textContent = limitation;
      list.append(item);
    });
    result.append(list);
  }
  result.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.hidden = true;
  result.hidden = true;
  submitButton.disabled = true;
  submitButton.textContent = "正在判定占类并生成断语（需要两次模型调用，通常需数分钟）…";
  try {
    const response = await fetch("/api/v1/divinations", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(requestPayload()),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(messageFromError(payload, response.status));
    }
    renderResponse(payload);
  } catch (error) {
    errorBox.textContent =
      error instanceof Error ? error.message : "请求失败，请稍后再试";
    errorBox.hidden = false;
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "排盘并断卦";
  }
});

ensureUsefulGodSelector();
buildLines();
setDefaultDate();
