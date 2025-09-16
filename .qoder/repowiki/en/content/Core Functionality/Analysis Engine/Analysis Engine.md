# Analysis Engine

<cite>
**Referenced Files in This Document**   
- [run_analysis.py](file://src/run_analysis.py#L1-L344)
- [analysis.py](file://src/analysis.py#L1-L491)
- [parser.py](file://src/parser.py#L1-L175)
- [storage.py](file://src/storage.py#L1-L310)
- [rag_persistence.py](file://src/rag_persistence.py#L1-L37)
- [README.md](file://README.md#L1-L224)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Conclusion](#conclusion)

## Introduction
The Analysis Engine is the central processing component of the VoxPersona platform, responsible for orchestrating multi-stage AI-driven analysis of voice recordings. It leverages Anthropic's Claude 3.5 Sonnet model for deep language understanding, integrates Retrieval-Augmented Generation (RAG) via FAISS and SentenceTransformers for context-aware responses, and applies structured data extraction using JSON schema validation. The engine supports two primary analysis types: interview evaluation and design audit, each with scenario-specific prompts and evaluation logic. This document provides a comprehensive breakdown of the workflow, component interactions, data flow, error handling, and performance optimization strategies implemented in the system.

## Project Structure
The project follows a modular structure with clear separation of concerns. Core analysis logic resides in the `src/` directory, while prompts are organized by scenario in dedicated directories. The `prompts/` directory contains base prompt templates, whereas `prompts-by-scenario/` houses structured, scenario-specific prompts including JSON-formatted variants for structured output generation.

```mermaid
graph TB
subgraph "Configuration & Setup"
A[config.py] --> B[Dockerfile]
C[.env.template] --> D[docker-compose.yml]
end
subgraph "Core Application"
E[src/] --> F[main.py]
E --> G[bot.py]
E --> H[handlers.py]
E --> I[analysis.py]
E --> J[run_analysis.py]
E --> K[parser.py]
E --> L[storage.py]
E --> M[rag_persistence.py]
end
subgraph "Data & Prompts"
N[prompts/] --> O[design_audit_methodology.txt]
N --> P[interview_methodology.txt]
Q[prompts-by-scenario/] --> R[json-prompt/]
Q --> S[non-building/]
end
subgraph "Database & Utilities"
T[db_handler/] --> U[db.py]
V[sql_scripts/] --> W[create_tables.sql]
X[utils.py] --> Y[CustomSentenceTransformerEmbeddings]
end
F --> I
I --> J
J --> K
J --> L
L --> M
I --> Y
L --> U
N --> J
Q --> J
```

**Diagram sources**
- [README.md](file://README.md#L1-L224)
- [run_analysis.py](file://src/run_analysis.py#L1-L344)

**Section sources**
- [README.md](file://README.md#L1-L224)

## Core Components
The Analysis Engine comprises several interconnected components that work in concert to process audio inputs and generate structured analytical reports. Key components include `run_analysis.py` as the orchestration layer, `analysis.py` for LLM interaction and RAG operations, `parser.py` for structured data extraction, and `storage.py` for database persistence and vector index management. These components follow a pipeline architecture where raw audio is transcribed, analyzed through multiple prompt stages, enriched with external context via RAG, and finally persisted with metadata.

**Section sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L344)
- [analysis.py](file://src/analysis.py#L1-L491)
- [parser.py](file://src/parser.py#L1-L175)
- [storage.py](file://src/storage.py#L1-L310)

## Architecture Overview
The Analysis Engine follows a multi-stage processing pipeline that begins with user input and culminates in structured report generation. The architecture integrates LLM processing with vector-based retrieval systems and relational database storage. It supports both real-time interactive analysis and batch processing workflows.

```mermaid
graph TD
A[User Input] --> B{Input Type}
B --> |Audio| C[Transcribe Audio]
B --> |Text| D[Parse Message]
C --> E[Assign Roles]
D --> E
E --> F[Classify Query]
F --> G{Scenario}
G --> |Interview| H[Load Interview Prompts]
G --> |Design| I[Load Design Prompts]
H --> J[Run Analysis Pass]
I --> J
J --> K[Apply RAG Context]
K --> L[Generate Structured Output]
L --> M[Validate & Parse JSON]
M --> N[Persist to Database]
N --> O[Send Results to User]
```

**Diagram sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L344)
- [analysis.py](file://src/analysis.py#L1-L491)
- [parser.py](file://src/parser.py#L1-L175)

## Detailed Component Analysis

### run_analysis.py: Orchestration Layer
The `run_analysis.py` module serves as the primary orchestration component, managing the end-to-end analysis workflow. It handles user interaction through the Telegram bot interface, coordinates multiple analysis passes, and manages state throughout the processing pipeline.

#### Analysis Workflow
```mermaid
sequenceDiagram
participant User
participant Bot
participant RunAnalysis
participant Analysis
participant Storage
participant LLM
User->>Bot : Upload Audio / Send Text
Bot->>RunAnalysis : process_input()
RunAnalysis->>RunAnalysis : show_loading_spinner()
alt Audio Input
RunAnalysis->>Analysis : transcribe_audio()
RunAnalysis->>Analysis : assign_roles()
else Text Input
RunAnalysis->>parser.py : parse_message_text()
end
RunAnalysis->>Storage : fetch_prompts_for_scenario()
RunAnalysis->>Analysis : classify_query()
RunAnalysis->>RunAnalysis : run_analysis_pass()
RunAnalysis->>Analysis : analyze_methodology()
Analysis->>LLM : send_msg_to_model()
LLM-->>Analysis : response
Analysis-->>RunAnalysis : audit_text
RunAnalysis->>Storage : save_user_input_to_db()
RunAnalysis->>Bot : send_results()
Bot->>User : Display Report
```

**Diagram sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L344)

**Section sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L344)

### analysis.py: LLM Interaction and RAG Processing
The `analysis.py` module contains the core logic for interacting with the LLM and managing retrieval-augmented generation. It implements both synchronous and asynchronous processing patterns for efficient resource utilization.

#### Multi-Stage Analysis Pattern
```mermaid
flowchart TD
Start([Start Analysis]) --> ValidateInput["Validate Input Parameters"]
ValidateInput --> LoadPrompts["Load Prompts from DB"]
LoadPrompts --> CheckAnalysisType{"Analysis Type?"}
CheckAnalysisType --> |Interview - General Factors| SplitPrompts["Split into Part1 & Part2"]
SplitPrompts --> RunPart1["Run Analysis Pass (Part1)"]
RunPart1 --> RunPart2["Run Analysis Pass (Part2)"]
RunPart2 --> CombineResults["Combine Results"]
CombineResults --> RunJSON["Run JSON Analysis Pass"]
CheckAnalysisType --> |Other Analysis Types| RunSinglePass["Run Single Analysis Pass"]
RunSinglePass --> RunJSON
RunJSON --> ValidateOutput["Validate JSON Schema"]
ValidateOutput --> ReturnResult["Return Structured Result"]
```

**Diagram sources**
- [analysis.py](file://src/analysis.py#L1-L491)

**Section sources**
- [analysis.py](file://src/analysis.py#L1-L491)

### parser.py: Structured Data Extraction
The `parser.py` module is responsible for parsing user input and extracting structured data according to predefined schemas. It handles both interview and design scenarios with different data models.

#### Data Parsing Logic
```mermaid
classDiagram
class ParseResult {
+int audio_number
+str date
+str employee
+str client
+str place_name
+str building_type
+str zone_name
+str city
}
class Parser {
+parse_message_text(text, mode) ParseResult
+parse_design(lines) ParseResult
+parse_interview(lines) ParseResult
+parse_file_number(text) int
+parse_date(text) str
+parse_name(text) str
+parse_building_type(text) str
+parse_zone(text) str
}
class Normalizer {
+normalize_building_info(text) str
+del_pretext(text) str
+_normalize_first_word(words) str
+_lemmatize(word) str
}
Parser --> ParseResult : "creates"
Parser --> Normalizer : "uses"
```

**Diagram sources**
- [parser.py](file://src/parser.py#L1-L175)

**Section sources**
- [parser.py](file://src/parser.py#L1-L175)

## Dependency Analysis
The Analysis Engine components exhibit a layered dependency structure where higher-level modules depend on lower-level utilities while maintaining loose coupling through well-defined interfaces.

```mermaid
graph TD
A[run_analysis.py] --> B[analysis.py]
A --> C[parser.py]
A --> D[storage.py]
B --> E[utils.py]
B --> F[db_handler.db]
C --> F
D --> F
D --> G[langchain]
B --> H[anthropic]
B --> I[openai]
J[bot.py] --> A
K[handlers.py] --> A
```

**Diagram sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L344)
- [analysis.py](file://src/analysis.py#L1-L491)
- [parser.py](file://src/parser.py#L1-L175)
- [storage.py](file://src/storage.py#L1-L310)

**Section sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L344)
- [analysis.py](file://src/analysis.py#L1-L491)
- [parser.py](file://src/parser.py#L1-L175)
- [storage.py](file://src/storage.py#L1-L310)

## Performance Considerations
The Analysis Engine incorporates several performance optimization strategies to handle resource-intensive LLM operations efficiently.

### Token Usage Optimization
The system implements token-aware processing to minimize API costs and prevent model context overflow:
- Dynamic chunking of input text based on token count
- Selective prompt loading based on analysis type
- Efficient RAG retrieval with controlled k-value (default: 15)
- Token counting utility for pre-emptive validation

### Caching Strategies
The engine employs multiple caching mechanisms:
- In-memory FAISS vector databases for RAG operations
- Persistent RAG indices via `rag_persistence.py`
- Reuse of embedding models across requests
- Thread-safe semaphores for rate limiting control

### Parallel Execution
For high-throughput scenarios, the system supports parallel processing:
- Asynchronous RAG retrieval with `extract_from_chunk_parallel_async`
- Threaded execution of analysis passes
- Concurrent API key utilization to maximize throughput
- Rate limiting awareness with token-per-minute and request-per-minute tracking

**Section sources**
- [analysis.py](file://src/analysis.py#L1-L491)
- [rag_persistence.py](file://src/rag_persistence.py#L1-L37)
- [storage.py](file://src/storage.py#L1-L310)

## Troubleshooting Guide
The Analysis Engine includes comprehensive error handling and logging mechanisms to facilitate debugging and maintenance.

### Common Error Scenarios
**Section sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L344)
- [analysis.py](file://src/analysis.py#L1-L491)

#### LLM Response Errors
- **Malformed JSON**: When JSON parsing fails, the system logs the raw response and returns appropriate error messages
- **Rate Limiting**: The engine implements exponential backoff (1s, 2s, 4s, 8s, 16s) for rate limit recovery
- **API Key Issues**: Permission errors trigger specific user-facing messages about API key/region problems

#### Prompt Injection Failures
- Invalid prompt names result in fallback to default prompts
- Missing prompt parameters are handled with default values
- Database connection issues during prompt retrieval trigger exception logging

#### RAG Retrieval Inaccuracies
- Empty retrieval results return "nothing found" messages
- Corrupted vector indices are skipped with warning logs
- Embedding model loading failures trigger graceful degradation

### Error Handling Flow
```mermaid
flowchart TD
Start([Error Occurs]) --> IdentifyError{"Error Type?"}
IdentifyError --> |LLM Rate Limit| HandleRateLimit["Apply Exponential Backoff"]
HandleRateLimit --> Retry["Retry Request"]
IdentifyError --> |API Permission| HandlePermission["Log Security Issue"]
HandlePermission --> NotifyUser["Send User Error Message"]
IdentifyError --> |Database| HandleDB["Log Connection Error"]
HandleDB --> AttemptReconnect["Retry with Connection Pool"]
IdentifyError --> |Parsing| HandleParse["Log Invalid Format"]
HandleParse --> ReturnDefault["Return Default Value"]
IdentifyError --> |General Exception| HandleGeneral["Log Full Traceback"]
HandleGeneral --> CleanUp["Release Resources"]
CleanUp --> NotifyUser
NotifyUser --> End([Error Handled])
```

**Diagram sources**
- [analysis.py](file://src/analysis.py#L1-L491)
- [run_analysis.py](file://src/run_analysis.py#L1-L344)

## Conclusion
The Analysis Engine represents a sophisticated integration of LLM technology, retrieval-augmented generation, and structured data processing. By orchestrating multiple analysis stages through carefully designed prompts and validation mechanisms, it transforms raw audio inputs into actionable business insights. The modular architecture enables extensibility for new analysis types while maintaining robust error handling and performance optimization. The system's ability to handle both interview evaluations and design audits demonstrates its versatility in processing diverse qualitative data. Future enhancements could include adaptive prompt selection, enhanced schema validation, and real-time collaboration features.