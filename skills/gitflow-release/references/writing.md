# Writing standards

Applies to release notes, PR descriptions, and commit messages either
agent drafts. Run anything written through `lint` before presenting it:

```
bash "{{STEWARD_HOME}}/bin/steward" lint <path> --json
```

FAIL findings must be fixed before the draft is shown for review. WARN
findings are advisory.

## Forbidden (FAIL)

- Hype words: elevate, seamless, unleash, cutting-edge, leverage, robust,
  powerful.
- Chatbot residue: "i hope this helps", "feel free to ask", "as an ai
  language model", "let me know if you have any other questions".
- Opener filler: "great question!", "certainly!", "of course!", "i'd be
  happy to".
- Closer filler: "i hope this helps", "i hope this helps clarify", "hope
  that helps".
- No AI-authorship claims anywhere in the output.

## Advisory (WARN)

- AI-vocabulary density above 3 per 100 words (utilize, delve, boost,
  tapestry, landscape, foster, vibrant, navigate, unlock, harness,
  streamline, paradigm, holistic, synergy, innovative, transformative —
  prefer the plain verb).
- Paragraphs over 150 words.
- Vague attribution ("some say", "studies show", "experts agree") without
  a named source.
- Rule-of-three filler, negative parallelism ("not just X, but Y"),
  non-parallel lists, narrating comments.

## General

Concrete verbs and facts over adjectives. State what changed, not that it
is an improvement. No AI attribution in commits, PR bodies, or the notes
themselves.
