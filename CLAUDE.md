# CLAUDE.md — Python / Streamlit / Data App Rules

## Core Behavior
1. Think before acting.
2. Keep solutions simple, direct, and practical.
3. User instructions always override this file.
4. Do not add complexity unless it is clearly necessary.

## File & Context Handling
5. Read only the files relevant to the task.
6. Read before writing.
7. Do not re-read files unless they may have changed.
8. Ask for additional files only if they are truly necessary.
9. Work from the smallest relevant code block whenever possible.

## Editing Rules
10. Prefer editing existing code over rewriting full files.
11. Return only the necessary changes whenever possible.
12. Prefer targeted patches, diffs, or exact replacements over full rewrites.
13. Do not modify unrelated code, formatting, variable names, or structure.
14. Preserve the current app flow unless the user explicitly asks for redesign or refactor.

## Python Rules
15. Prefer standard library solutions first when reasonable.
16. Do not introduce new dependencies unless necessary.
17. Keep logic readable over clever.
18. Avoid overengineering.
19. Preserve compatibility with the existing code style and stack.
20. Do not add abstractions (classes, helpers, wrappers, config layers) unless they clearly reduce complexity.

## Streamlit Rules
21. Keep Streamlit code simple and idiomatic.
22. Do not redesign the UI unless requested.
23. Preserve the current layout, widgets, and user flow unless a change is required.
24. Avoid unnecessary reruns, duplicated computations, or state complexity.
25. Be careful with session_state, forms, caching, and widget keys.
26. Do not move chart or UI logic unless necessary to solve the problem.

## Data / Pandas Rules
27. Prefer clear pandas operations over overly compact one-liners.
28. Preserve column names, expected schemas, and existing transformations unless the user requests changes.
29. Do not silently change data types, formats, or grouping logic unless needed.
30. Be explicit when a fix could affect calculations, aggregations, joins, filters, or dates.

## Visualization Rules
31. Preserve existing chart intent unless asked to improve it.
32. Do not change labels, scales, sorting, aggregation, or axes unless required.
33. If a chart is broken, fix only the part causing the issue first.
34. Keep dashboard outputs easy to read at a glance.

## Debugging Rules
35. Identify the root cause before proposing broad changes.
36. Fix the smallest thing that solves the issue.
37. Do not rewrite working sections just to “clean them up”.
38. If there are multiple valid fixes, choose the least disruptive one first.
39. If the issue is caused by assumptions, point them out briefly.

## Output Rules
40. Keep visible output concise.
41. Do not explain obvious code unless asked.
42. Do not repeat the user’s code or context unnecessarily.
43. If useful, structure output as:
   - Problem
   - Cause
   - Fix
44. When editing code, prioritize showing only what changed.

## Validation Rules
45. Validate logic before declaring the task done.
46. If relevant, provide a short “how to verify” section.
47. Do not claim something works if it has not been reasonably checked.
48. If something remains uncertain, say exactly what is uncertain.

## Style
49. No fluff, no filler, no motivational language.
50. Optimize for usefulness per token.