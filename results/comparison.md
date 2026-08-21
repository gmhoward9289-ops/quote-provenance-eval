# Quote-provenance eval — cross-run comparison

| provider | model | corpus | n | unparseable | quote exact | quote coverage | +normalized | fabricated | anchor located | anchor coverage |
|---|---|---|---|---|---|---|---|---|---|---|
| ollama | granite3.3:8b | anchor2/anchor | 15 | 0 | — | — | — | — | 40% | 40% <sub>20%–64%</sub> |
| ollama | granite3.3:8b | anchor2/anchor | 45 | 0 | — | — | — | — | 93% | 93% <sub>82%–98%</sub> |
| ollama | granite3.3:8b | anchor2/anchor2 | 15 | 0 | — | — | — | — | 100% | 80% <sub>55%–93%</sub> |
| ollama | granite3.3:8b | anchor2/anchor2 | 45 | 0 | — | — | — | — | 100% | 100% <sub>92%–100%</sub> |
| ollama | granite3.3:8b | anchor2/anchor/fewshot | 45 | 0 | — | — | — | — | 100% | 100% <sub>92%–100%</sub> |
| ollama | granite3.3:8b | anchor2/anchor2/fewshot | 45 | 0 | — | — | — | — | 100% | 100% <sub>92%–100%</sub> |
| ollama | mistral:7b | anchor2/anchor | 15 | 0 | — | — | — | — | 100% | 100% <sub>80%–100%</sub> |
| ollama | mistral:7b | anchor2/anchor2 | 15 | 0 | — | — | — | — | 100% | 100% <sub>80%–100%</sub> |
| ollama | qwen2.5-coder:7b | anchor2/anchor | 15 | 0 | — | — | — | — | 100% | 100% <sub>80%–100%</sub> |
| ollama | qwen2.5-coder:7b | anchor2/anchor2 | 15 | 0 | — | — | — | — | 100% | 100% <sub>80%–100%</sub> |

**How to read this:** *quote exact* is the share of model-produced 'verbatim' quotes that actually appear character-for-character in the source — the only kind a naive string-match verifier accepts. *quote coverage* additionally requires the exact quote to contain the expected value — the apples-to-apples comparator for *anchor coverage*. *+normalized* adds quotes recoverable with cheap unicode/whitespace normalization. *anchor coverage* is the share of questions where the anchored-extraction arm located the model's anchor AND the located source sentence contains the expected value — and every span it emits is a real substring of the source by construction. All rates are intent-to-treat: responses that arrived but could not be parsed stay in the denominators (*unparseable* column); only provider/network errors are excluded.
