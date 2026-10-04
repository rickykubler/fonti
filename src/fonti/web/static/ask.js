// Ask page: streams the answer, then shows it with its verified citations.
// Document text is untrusted: it is only ever inserted as text nodes, never as HTML.
"use strict";

const form = document.getElementById("ask-form");
const question = document.getElementById("question");
const statusLine = document.getElementById("status");
const draft = document.getElementById("draft");
const answerBox = document.getElementById("answer");
const citationList = document.getElementById("citations");

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function shorten(text, limit) {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length <= limit ? flat : flat.slice(0, limit - 1) + "…";
}

function isPdf(filename) {
  return filename.toLowerCase().endsWith(".pdf");
}

// Answer text with [n] markers turned into links to the citation cards.
function renderAnswerText(text) {
  const paragraph = element("p");
  const pattern = /\[(\d+(?:\s*[,;]\s*\d+)*)\]/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    paragraph.append(document.createTextNode(text.slice(last, match.index)));
    for (const number of match[1].split(/\s*[,;]\s*/)) {
      const link = element("a", "marker", number);
      link.href = "#fonte-" + number;
      paragraph.append(link);
    }
    last = match.index + match[0].length;
  }
  paragraph.append(document.createTextNode(text.slice(last)));
  return paragraph;
}

function pageLinks(docId, filename, page, start, end) {
  const links = element("div", "links");
  const open = element("a", null, isPdf(filename) ? "Apri il PDF a pagina " + page : "Apri il file");
  open.href = "/documents/" + docId + "/file" + (isPdf(filename) ? "#page=" + page : "");
  open.target = "_blank";
  open.rel = "noopener";
  links.append(open);
  if (isPdf(filename)) {
    const show = element("button", "link", "Mostra la pagina");
    show.type = "button";
    show.addEventListener("click", () => {
      const existing = links.nextElementSibling;
      if (existing && existing.tagName === "IMG") {
        existing.remove();
        show.textContent = "Mostra la pagina";
        return;
      }
      const image = element("img", "preview");
      image.alt = "Pagina " + page + " con il passaggio evidenziato";
      image.src = "/documents/" + docId + "/pages/" + page + ".png?start=" + start + "&end=" + end;
      links.after(image);
      show.textContent = "Nascondi la pagina";
    });
    links.append(show);
  }
  return links;
}

function renderCitations(citations) {
  const bySource = new Map();
  for (const citation of citations) {
    if (!bySource.has(citation.number)) bySource.set(citation.number, []);
    bySource.get(citation.number).push(citation);
  }
  for (const [number, items] of bySource) {
    const first = items[0];
    const card = element("li", "card");
    card.id = "fonte-" + number;
    const title = element("h3", null, "[" + number + "] " + (first.title || first.filename));
    card.append(title);
    if (first.section) card.append(element("p", "muted", first.section));
    for (const citation of items) {
      const quote = element("blockquote", null, "«" + citation.passage + "»");
      quote.cite = "/documents/" + citation.doc_id + "/file";
      card.append(element("p", "page", "pagina " + citation.page), quote);
      card.append(pageLinks(citation.doc_id, citation.filename, citation.page, citation.start, citation.end));
    }
    citationList.append(card);
  }
}

function renderNearest(sources) {
  if (!sources.length) return;
  const intro = element("p", "muted", "Passaggi più vicini trovati (non bastano per rispondere):");
  answerBox.append(intro);
  for (const hit of sources) {
    const card = element("li", "card nearest");
    card.append(element("h3", null, hit.title || hit.filename));
    card.append(element("p", "page", "pagina " + hit.page_start));
    card.append(element("blockquote", null, "«" + shorten(hit.text, 280) + "»"));
    card.append(pageLinks(hit.doc_id, hit.filename, hit.page_start, hit.start, hit.end));
    citationList.append(card);
  }
}

function renderAnswer(answer) {
  draft.textContent = "";
  statusLine.textContent = "";
  answerBox.replaceChildren();
  citationList.replaceChildren();
  if (answer.abstained) {
    answerBox.append(element("p", "abstained", answer.text));
    renderNearest(answer.sources);
    return;
  }
  answerBox.append(renderAnswerText(answer.text));
  renderCitations(answer.citations);
}

async function ask(text) {
  answerBox.replaceChildren();
  citationList.replaceChildren();
  draft.textContent = "";
  statusLine.textContent = "Cerco nei documenti…";
  const response = await fetch("/api/ask/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: text }),
  });
  if (!response.ok) {
    statusLine.textContent = "Errore " + response.status + ": la domanda non è valida.";
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newline;
    while ((newline = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      if (!line) continue;
      const event = JSON.parse(line);
      if (event.type === "token") {
        statusLine.textContent = "Scrivo la risposta (le citazioni vengono verificate alla fine)…";
        draft.textContent += event.text;
      } else if (event.type === "answer") {
        renderAnswer(event.answer);
      } else if (event.type === "error") {
        draft.textContent = "";
        statusLine.textContent = event.message;
      }
    }
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = question.value.trim();
  if (!text) return;
  const button = form.querySelector("button");
  button.disabled = true;
  ask(text)
    .catch(() => {
      statusLine.textContent = "Il server non risponde: è ancora in esecuzione?";
    })
    .finally(() => {
      button.disabled = false;
    });
});

question.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});
