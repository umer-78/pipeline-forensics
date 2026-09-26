## Where each version's GSM8K failures come from

| Version | Stop sequence | Accuracy | Failures | stopped before stating an answer | hit the token limit | extracted the wrong number | wrong answer (every check passed) |
|---|---|---|---|---|---|---|---|
| gpt-4o-2024-05-13 | none | 90.5% | 95 | 9% | 16% | 5% | 69% |
| gpt-4o-2024-08-06 | none | 90.9% | 91 | 11% | 5% | 14% | 69% |
| gemini-1.5-pro-001 | none | 83.6% | 164 | 5% | 0% | 32% | 63% |
| gemini-1.5-pro-002 | "\n\n" | 81.7% | 183 | 89% | 0% | 0% | 11% |
| gemini-1.5-flash-001 | none | 78.5% | 215 | 7% | 0% | 40% | 53% |
| gemini-1.5-flash-002 | "\n\n" | 32.8% | 672 | 97% | 0% | 3% | 0% |
| gemini-1.0-pro-001 | "\n\n" | 78.3% | 217 | 4% | 0% | 3% | 93% |
| gemini-1.0-pro-002 | none | 81.6% | 184 | 5% | 0% | 9% | 86% |
| mistral-large-2402 | "\n\n" | 69.4% | 306 | 75% | 0% | 3% | 22% |
| mistral-large-2407 | none | 91.2% | 88 | 11% | 18% | 11% | 59% |
| llama-3-70b | "\n\n" | 80.5% | 195 | 3% | 0% | 6% | 91% |
| llama-3.1-70b-instruct | none | 93.8% | 62 | 2% | 5% | 0% | 94% |

## The gemini-1.5-flash-001 → gemini-1.5-flash-002 regression

488 questions broke (right before, wrong after). Blamed on:

- stopped before stating an answer: 479 (98%)
- extracted the wrong number: 9 (2%)

Stop sequence: gemini-1.5-flash-001 none, gemini-1.5-flash-002 ['\n\n']. Broken answers, in full:

- "It took Finley 30 minutes to cook rice."
- "Amy starts with 2 palettes * 4 colors/palette = 8 colors from palettes."
- "Each horse eats 5 pounds of oats per meal * 2 meals/day = 10 pounds of oats per day."

## Injection test: one step broken on purpose (200 correct GPT-4o traces)

| Fault injected | Traces | Failed | Blamed on the right step and problem |
|---|---|---|---|
| prompt lost the question | 200 | 200 | 200 (100%) |
| stopped before stating an answer | 200 | 140 | 140 (100%) |
| hit the token limit | 200 | 196 | 196 (100%) |
| extracted the wrong number | 194 | 194 | 194 (100%) |
| wrong answer (every check passed) | 200 | 200 | 200 (100%) |
