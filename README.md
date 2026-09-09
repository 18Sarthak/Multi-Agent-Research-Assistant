# 🔬 Research Assistant

An autonomous multi-agent research pipeline built with **LangGraph** and **LangChain**.

Given any research question, it automatically:
1. **Plans** — breaks the query into focused sub-questions
2. **Researches** — searches the web (Tavily) and synthesizes answers per sub-question
3. **Writes** — produces a structured markdown report with citations
4. **Reviews** — scores the report and requests revisions if needed (capped at 2 rounds)

## Architecture

```
planner → researcher → writer → reviewer
                          ↑          |
                          └─"revise"─┘
                                     |
                                  "done" → final report
```

## Setup

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd research_assistant

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add API keys
cp .env.example .env
# Edit .env and add your keys
```

## Environment Variables

Create a `.env` file with:
```
NVIDIA_API_KEY=nvapi-...
TAVILY_API_KEY=tvly-...
```

- **NVIDIA_API_KEY** — get from [build.nvidia.com](https://build.nvidia.com) (free tier available)
- **TAVILY_API_KEY** — get from [tavily.com](https://tavily.com) (free tier available)

## Usage

```bash
# Run with a query
python main.py "What are the latest advances in protein folding?"

# No argument = uses default query
python main.py
```

## Project Structure

```
research_assistant/
├── main.py          # Entry point — CLI + run() function
├── graph.py         # LangGraph pipeline wiring
├── agents.py        # planner, researcher, writer, reviewer agents
├── state.py         # ResearchState TypedDict
├── config.py        # LLM model setup
├── requirements.txt
└── .env             # API keys (not committed)
```

## Models Used

- **LLM**: `meta/llama-3.2-11b-vision-instruct` via NVIDIA NIM (OpenAI-compatible endpoint)
- **Search**: Tavily Search API
