# System Architecture Overview

## Data Flow Diagram

```mermaid
graph TD
    CLI[run_agent.py] --> Graph[LangGraph Orchestrator]
    
    subgraph Scrape_Phase
        Graph --> Scout[scout_node]
        Scout --> SM[ScraperManager]
        SM --> JS[JobBoardScraper]
        SM --> LPS[LinkedInPostScraper]
    end
    
    subgraph Process_Phase
        Graph --> Dedup[dedup_node]
        Dedup --> DB[(SQLite)]
        Graph --> Intake[intake_node]
        Intake --> DB
        Graph --> Analysis[analysis_node]
        Analysis --> Parser[JobParser]
        Parser --> Gemini[Gemini 1.5/2.0]
    end
    
    subgraph Intelligence_Phase
        Graph --> Research[research_node]
        Research --> Search[Tavily / Glassdoor]
        Graph --> Match[matching_node]
        Match --> Chroma[(ChromaDB)]
    end
    
    subgraph Generation_Phase
        Graph --> Generator[generator_node]
        Generator --> CV[CVTailor]
        Generator --> CL[CoverLetterGen]
        CV --> LaTeX[LaTeX Engine]
        CL --> LaTeX
    end
```

## Key Components

### 1. LangGraph Pipeline
The core "brain" of the system. It handles the 11-node state machine, retries, and routing.

### 2. JobParser (Phase 4)
The extraction engine. It takes raw text and produces valid JSON matching the `ParsedJob` schema.

### 3. ScraperManager (Phase 2 & 3)
Orchestrates multiple scraping sources, merges results, and applies deduplication via SHA-256 fingerprints.

### 4. VectorStore (Phase 5 & 6)
Indexes the user's GitHub repos and CV projects into ChromaDB for semantic matching against job descriptions.

### 5. LaTeXEngine
A Jinja2-powered template engine that produces professional PDF documents from AI-generated content.
