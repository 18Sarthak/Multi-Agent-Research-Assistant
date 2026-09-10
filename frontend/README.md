# Insight Weaver

Build a dark-themed web UI for a Multi-Agent AI Research Assistant.

## App Overview

Users type a research question and the app runs it through a 4-agent AI pipeline:

1. Planner → breaks the query into sub-questions

2. Researcher → searches the web and finds answers per sub-question

3. Writer → writes a structured markdown report

4. Reviewer → scores the report and requests revisions if needed

## Design Theme

- Dark mode only — background: #0a0a0f, card surfaces: #111118

- Accent color: electric indigo/violet (#7c3aed) with cyan highlights (#06b6d4)

- Glassmorphism cards with subtle border glow

- Smooth animations and transitions throughout

- Font: Inter or Geist

## Pages / Screens

### 1. Home / Search Page

- Large centered search bar with glowing border on focus

- Placeholder: "Ask anything — e.g. What is RLVR?"

- A "Research" button (gradient: indigo → cyan)

- Below the search bar: 3 example query chips (clickable)

- Subtle animated background (floating particles or gradient mesh)

### 2. Pipeline Progress Page (shown after submitting query)

- Shows the query at the top

- 4 agent cards in a vertical timeline with connecting lines:

  - 🗂 Planner

  - 🔍 Researcher  

  - ✍️ Writer

  - 🔎 Reviewer

- Each card has:

  - Agent icon + name

  - Status badge: Pending / Running (pulsing) / Done / Error

  - Output preview when done (collapsible)

- Animated progress — agents activate one by one as pipeline runs

### 3. Report Page (final output)

- Full markdown report rendered beautifully

  - ## headings styled large and bold

  - Inline citations styled as small badges [1], [2]

  - Code blocks with syntax highlighting if any

  - Key Takeaways section with bullet checkmarks (✓)

  - References section with clickable links

- Stats bar at top: "5 sub-questions · 5 findings · 1 review round · Score: 9/10"

- Two action buttons: "Copy Report" and "Download .md"

- "Research Again" button to go back to home

## Key UI Components

- QueryInput: glowing textarea, grows with content

- AgentCard: glass card, status indicator, collapsible output

- PipelineTimeline: vertical step tracker with animated connectors

- MarkdownViewer: renders markdown with dark-themed typography

- ScoreBadge: circular score display (e.g. 9/10 in green)

- StatsPill: small pill badges showing pipeline stats

## Interactions

- Typing in search: glow intensifies on focus

- Submit: page transitions to pipeline view with smooth slide-up

- Each agent activates with a fade-in + subtle pulse on the status dot

- Report loads with a fade-in from bottom

- Hover on citations: tooltip showing the source URL

- Copy button: flashes "Copied!" for 2 seconds

## Tech Stack

- React + TypeScript

- Tailwind CSS (dark theme)

- react-markdown + remark-gfm for rendering the report

- Framer Motion for animations

- Mock the API calls for now — simulate pipeline steps with realistic delays (1-2s per agent)

## Mock Data

Use this as the example report output when mocking:

- Query: "What is RLVR?"

- Sub-questions: 5 questions about definition, architecture, applications, comparisons, limitations

- Score: 9/10, approved in 1 review round

- Report has sections: Executive Summary, Background, 5 finding sections, Challenges, Key Takeaways, References


need colour theme and design  like above given picture

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/acda7cf8-307b-4b0e-b8d4-3790e7666737).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
