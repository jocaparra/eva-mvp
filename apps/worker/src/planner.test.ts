import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { parsePlanJson } from "./planner";

const VALID_PLAN = {
  steps: [
    { ordem: 1, descricao: "Pesquisar dados da empresa", tipo_entregavel: null },
    { ordem: 2, descricao: "Montar o teaser em slides", tipo_entregavel: "pptx" },
  ],
};

describe("parsePlanJson", () => {
  it("aceita JSON puro válido", () => {
    const result = parsePlanJson(JSON.stringify(VALID_PLAN));
    assert.equal(result.ok, true);
    if (result.ok) {
      assert.equal(result.plan.steps.length, 2);
      assert.equal(result.plan.steps[1]?.tipo_entregavel, "pptx");
    }
  });

  it("aceita JSON dentro de cerca de markdown", () => {
    const raw = "```json\n" + JSON.stringify(VALID_PLAN) + "\n```";
    const result = parsePlanJson(raw);
    assert.equal(result.ok, true);
  });

  it("aceita JSON com texto acidental ao redor", () => {
    const raw = `Aqui está o plano:\n${JSON.stringify(VALID_PLAN)}\nEspero que ajude.`;
    const result = parsePlanJson(raw);
    assert.equal(result.ok, true);
  });

  it("rejeita resposta sem JSON", () => {
    const result = parsePlanJson("Não consigo planejar isso.");
    assert.equal(result.ok, false);
  });

  it("rejeita JSON malformado", () => {
    const result = parsePlanJson('{"steps": [{"ordem": 1,]');
    assert.equal(result.ok, false);
  });

  it("rejeita schema inválido (tipo_entregavel desconhecido)", () => {
    const invalid = {
      steps: [{ ordem: 1, descricao: "Gerar documento", tipo_entregavel: "txt" }],
    };
    const result = parsePlanJson(JSON.stringify(invalid));
    assert.equal(result.ok, false);
  });

  it("rejeita lista de steps vazia", () => {
    const result = parsePlanJson(JSON.stringify({ steps: [] }));
    assert.equal(result.ok, false);
  });

  it("rejeita ordem não sequencial", () => {
    const invalid = {
      steps: [
        { ordem: 1, descricao: "Pesquisar", tipo_entregavel: null },
        { ordem: 3, descricao: "Gerar documento", tipo_entregavel: "pdf" },
      ],
    };
    const result = parsePlanJson(JSON.stringify(invalid));
    assert.equal(result.ok, false);
  });
});
