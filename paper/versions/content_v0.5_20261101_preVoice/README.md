# Central paper content

The single source of truth for Paper C's text. Every finding lives here; journal versions only change the wrapper.

- `meta.tex`: title, short title, keywords (macros).
- `abstract.tex`, `intro.tex`, `related.tex`, `methods.tex`, `results.tex`, `discussion.tex`, `conclusions.tex`: the body.
- `availability.tex`, `ai_use.tex`, `acks.tex`: back-matter text; each wrapper places it where its journal wants it.
- Figures: `../figures/`; references: `../refs.bib`.

Conventions so the text works in every template:
- Cite with natbib `\citep{}` (parenthetical) and `\citet{}` (textual); never bare `\cite{}`. This works for
  numbered and author-year styles alike.
- Content files never `\input` each other; only wrappers do.
- Journal-specific text goes in the wrapper, guarded by a flag, not into these files.
- Numbers trace to `../../FINDINGS.md`.

Builds (Tectonic, from the wrapper's folder):
- Central: `paper/main.tex` (neutral article class, numbered refs).
- Scientometrics: `paper/journals/scientometrics/main.tex` (Springer Nature `sn-jnl` v3.1, `sn-basic` author-year).
