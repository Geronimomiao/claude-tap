# Eager Compare Rendering Delayed Deep Links

## What broke

Opening a comparison URL with a section hash such as `#diff-system` rendered every
comparison section before scrolling to the requested section. Collapsed parameter
and raw JSON sections were also fully serialized into the DOM.

## What was misleading

The session APIs returned in a few milliseconds, so the page initially looked like
a backend or SQLite performance problem. Headless profiling showed that the delay
was browser-side work: unrelated diff sections and large raw JSON blocks were built
before the requested System Prompt diff became usable.

## Fix

Deep-linked comparison pages now open only the requested section. Other sections
keep an empty details shell and render their content on the first expansion. Direct
comparison routes also load the requested pair before hydrating the hidden session
list and navigation metadata.

## Lesson

For dashboard deep links, prioritize the route's target content over global chrome
and below-the-fold panels. A collapsed `<details>` element is not cheap if its body
was already computed and inserted into the DOM.
