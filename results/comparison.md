# Quote-provenance eval — cross-run comparison

| provider | model | quote exact | +normalized | fabricated | anchor located | anchor coverage |
|---|---|---|---|---|---|---|
| mock | chaotic | 37% | 60% | 13% | 97% | 93% |
| mock | faithful | 93% | 100% | 0% | 100% | 100% |
| mock | sloppy | 80% | 87% | 3% | 93% | 90% |

**How to read this:** *quote exact* is the share of model-produced 'verbatim' quotes that actually appear character-for-character in the source — the only kind a naive string-match verifier accepts. *+normalized* adds quotes recoverable with cheap unicode/whitespace normalization. *anchor coverage* is the share of questions where the anchored-extraction arm located the model's anchor AND the located source sentence contains the expected value — and every span it emits is a real substring of the source by construction.
