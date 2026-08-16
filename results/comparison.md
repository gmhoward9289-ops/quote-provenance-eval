# Quote-provenance eval — cross-run comparison

| provider | model | corpus | quote exact | quote coverage | +normalized | fabricated | anchor located | anchor coverage |
|---|---|---|---|---|---|---|---|---|
| ollama | gemma4:latest | clean | 97% | 97% <sub>91%–99%</sub> | 100% | 0% | 100% | 100% <sub>96%–100%</sub> |
| ollama | gemma4:latest | hard | 73% | 73% <sub>61%–82%</sub> | 96% | 0% | 100% | 100% <sub>94%–100%</sub> |
| ollama | mistral:7b | clean | 83% | 83% <sub>74%–90%</sub> | 93% | 3% | 100% | 97% <sub>91%–99%</sub> |
| ollama | mistral:7b | hard | 64% | 64% <sub>52%–74%</sub> | 86% | 0% | 100% | 100% <sub>94%–100%</sub> |
| ollama | qwen2.5-coder:7b | clean | 70% | 70% <sub>60%–78%</sub> | 90% | 0% | 100% | 100% <sub>96%–100%</sub> |
| ollama | qwen2.5-coder:7b | hard | 64% | 64% <sub>52%–74%</sub> | 91% | 0% | 100% | 100% <sub>94%–100%</sub> |
| ollama | qwen2.5:14b | clean | 90% | 90% <sub>82%–95%</sub> | 97% | 0% | 97% | 90% <sub>82%–95%</sub> |
| ollama | qwen2.5:14b | hard | 68% | 68% <sub>56%–78%</sub> | 96% | 0% | 100% | 91% <sub>82%–96%</sub> |

**How to read this:** *quote exact* is the share of model-produced 'verbatim' quotes that actually appear character-for-character in the source — the only kind a naive string-match verifier accepts. *quote coverage* additionally requires the exact quote to contain the expected value — the apples-to-apples comparator for *anchor coverage*. *+normalized* adds quotes recoverable with cheap unicode/whitespace normalization. *anchor coverage* is the share of questions where the anchored-extraction arm located the model's anchor AND the located source sentence contains the expected value — and every span it emits is a real substring of the source by construction.
