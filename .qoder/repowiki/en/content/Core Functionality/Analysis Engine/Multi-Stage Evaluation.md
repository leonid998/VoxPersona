# Multi-Stage Evaluation

<cite>
**Referenced Files in This Document**   
- [run_analysis.py](file://src/run_analysis.py#L1-L344)
- [handlers.py](file://src/handlers.py#L1-L805)
- [analysis.py](file://src/analysis.py#L1-L491)
- [storage.py](file://src/storage.py#L1-L310)
- [datamodels.py](file://src/datamodels.py#L1-L72)
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
VoxPersona is an AI-powered voice analysis platform that automates transcription, contextual retrieval, and deep analysis of audio recordings using advanced language models. This document details the multi-stage evaluation workflow orchestrated by `run_analysis.py`, which manages a complex pipeline from audio input to structured reporting. The system supports two primary evaluation types—interview and design audit—each with specialized processing paths, prompt sets, and data handling logic. The workflow integrates RAG (Retrieval-Augmented Generation), asynchronous LLM processing, and robust error handling to deliver comprehensive analytical reports.

## Project Structure
The project follows a modular structure with clear separation of concerns. The core logic resides in the `src` directory, while prompts are organized by scenario and type. The system uses PostgreSQL for persistent storage and FAISS for in-memory vector databases to support semantic search.

```mermaid
graph TD
A[Root] --> B[prompts]
A --> C[prompts-by-scenario]
A --> D[src]
A --> E[DEPLOYMENT_GUIDE.md]
A --> F[Dockerfile]
A --> G[README.md]
A --> H[SETUP.md]
A --> I[docker-compose.yml]
A --> J[requirements.txt]
D --> K[db_handler]
D --> L[analysis.py]
D --> M[audio_utils.py]
D --> N[auth_utils.py]
D --> O[bot.py]
D --> P[config.py]
D --> Q[datamodels.py]
D --> R[handlers.py]
D --> S[main.py]
D --> T[markups.py]
D --> U[menus.py]
D --> V[parser.py]
D --> W[rag_persistence.py]
D --> X[run_analysis.py]
D --> Y[storage.py]
D --> Z[utils.py]
D --> AA[validators.py]
K --> AB[db.py]
K --> AC[fill_prompts_table.py]
```

**Diagram sources**
- [README.md](file://README.md#L1-L224)

## Core Components
The system's core functionality is distributed across several key components that handle audio processing, analysis orchestration, state management, and database interaction. The workflow begins with audio upload in `handlers.py`, transitions through analysis coordination in `run_analysis.py`, and concludes with LLM-driven processing in `analysis.py`. The `storage.py` module manages both persistent database operations and in-memory RAG indices, while `datamodels.py` defines critical mappings between user-facing labels and internal identifiers.

**Section sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L344)
- [handlers.py](file://src/handlers.py#L1-L805)
- [analysis.py](file://src/analysis.py#L1-L491)
- [storage.py](file://src/storage.py#L1-L310)
- [datamodels.py](file://src/datamodels.py#L1-L72)

## Architecture Overview
The system architecture follows a client-server model with Telegram as the primary user interface. Audio files are processed through a multi-stage pipeline that includes transcription, role assignment, contextual analysis, and report generation. The architecture leverages asynchronous processing for LLM interactions and maintains state through in-memory dictionaries and database persistence.

```mermaid
graph TD
A[Telegram User] --> B[Pyrogram Bot]
B --> C[handlers.py]
C --> D{Audio or Text?}
D --> |Audio| E[audio_utils.py]
D --> |Text| F[process_stored_file]
E --> G[transcribe_audio_and_save]
G --> H[assign_roles]
H --> I[processed_texts]
I --> J[run_analysis_with_spinner]
J --> K[run_analysis_pass]
K --> L[analyze_methodology]
L --> M[Claude 3.5 Sonnet]
M --> N[save_user_input_to_db]
N --> O[PostgreSQL]
P[RAG System] --> Q[FAISS Vector DB]
Q --> R[build_reports_grouped]
R --> S[generate_db_answer]
S --> M
T[State Management] --> U[user_states]
U --> C
U --> J
```

**Diagram sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L344)
- [handlers.py](file://src/handlers.py#L1-L805)
- [analysis.py](file://src/analysis.py#L1-L491)
- [storage.py](file://src/storage.py#L1-L310)

## Detailed Component Analysis

### run_analysis.py: Analysis Orchestration
The `run_analysis.py` module serves as the central orchestrator for the evaluation workflow, managing the end-to-end pipeline from user input to final report generation. It implements a multi-phase process that ensures systematic analysis while providing real-time feedback to users.

#### Analysis Pipeline Control Flow
```mermaid
graph TD
A[User Selects Report Type] --> B[run_analysis_with_spinner]
B --> C[Show Loading Animation]
C --> D[Fetch Prompts from DB]
D --> E{Multiple Parts?}
E --> |Yes| F[Process Part 1]
F --> G[Store Intermediate Result]
G --> H[Process Part 2]
H --> I[Combine Results]
E --> |No| J[Single Pass Analysis]
J --> K[JSON Processing]
K --> L[Save to Database]
L --> M[Send Results to User]
M --> N[Show Next Steps Menu]
N --> O[Main Menu]
style A fill:#f9f,stroke:#333
style O fill:#bbf,stroke:#333
```

**Diagram sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L344)

The `run_analysis_with_spinner` function initiates the analysis workflow when a user selects a report type from the menu. It first displays a loading animation to provide immediate feedback, then retrieves the appropriate prompts from the database based on the selected scenario (interview or design), report type, and building type. For complex analyses that require multiple processing stages (such as "Common Factors" in interviews), the function executes sequential passes, with each pass generating intermediate results that are combined for final JSON processing.

#### State Management and Progress Tracking
The system maintains user state through the `user_states` dictionary, which tracks the current step in the data collection process. When initiating analysis, `run_analysis_with_spinner` accesses the user's collected data (employee name, place name, date, etc.) and combines it with the transcribed audio text for processing. The function uses threading events and spinner threads to manage the loading animation, ensuring the user interface remains responsive during potentially lengthy LLM operations.

#### Specialized Execution Paths
The workflow diverges based on the evaluation type, with distinct processing logic for interview and design audit scenarios:

```mermaid
graph TD
A[Analysis Initiation] --> B{Scenario Type?}
B --> |Interview| C[Process Interview Prompts]
C --> D{Report Type?}
D --> |Methodology| E[Use interview_methodology.txt]
D --> |Common Factors| F[Process part1 and part2 separately]
D --> |Specific Factors| G[Use specific_factors template]
D --> |Links Report| H[Use quality_decision_links.txt]
B --> |Design| I[Process Design Prompts]
I --> J{Report Type?}
J --> |Audit Methodology| K[Use design_audit_methodology.txt]
J --> |Compliance| L[Use hotel/restaurant/spa_audit_compliance.txt]
J --> |Structured Report| M[Use structured_*_audit.txt]
style B fill:#f96,stroke:#333
style D fill:#f96,stroke:#333
style J fill:#f96,stroke:#333
```

**Diagram sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L344)
- [datamodels.py](file://src/datamodels.py#L1-L72)

For interview evaluations, the system first processes general factors (common decision-making elements across establishments) and then specific factors (unique to the particular venue). The results are combined and processed through a JSON-specific prompt to generate structured output. Design audits follow a similar pattern but focus on compliance with audit programs and structured reporting of design elements.

**Section sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L344)

### handlers.py: Workflow Initiation and State Management
The `handlers.py` module serves as the entry point for user interactions, managing the flow from audio upload to analysis initiation. It implements a state machine that guides users through data collection before triggering the analysis pipeline.

#### Audio Upload and Processing Flow
```mermaid
sequenceDiagram
participant User
participant handlers
participant audio_utils
participant analysis
participant storage
User->>handlers : Upload Audio
handlers->>handlers : Validate User
handlers->>handlers : Show Loading Message
handlers->>handlers : Start Spinner
handlers->>audio_utils : transcribe_audio_and_save
audio_utils->>OpenAI : Whisper API
OpenAI-->>audio_utils : Transcription
audio_utils-->>handlers : Return Text
handlers->>analysis : assign_roles
analysis->>Claude : Role Assignment Prompt
Claude-->>analysis : Text with Roles
analysis-->>handlers : Processed Text
handlers->>storage : save_user_input_to_db
storage->>PostgreSQL : Save Transcription
storage-->>handlers : Confirmation
handlers->>handlers : Stop Spinner
handlers->>User : "Audio Processed!"
```

**Diagram sources**
- [handlers.py](file://src/handlers.py#L1-L805)
- [audio_utils.py](file://src/audio_utils.py#L1-L50)
- [analysis.py](file://src/analysis.py#L1-L491)

When a user uploads an audio file, the `handle_audio_msg` function validates the user's authorization, checks file size limits, and initiates processing. It downloads the audio to a temporary location, uploads it to MinIO storage, and calls `transcribe_audio_and_save` to generate a text transcript using OpenAI's Whisper API. After transcription, it invokes `assign_roles` to identify speakers in the dialogue (e.g., interviewer vs. interviewee), enhancing the quality of subsequent analysis.

#### State Machine Implementation
The system implements a step-by-step data collection process using the `user_states` dictionary:

```mermaid
stateDiagram-v2
[*] --> Idle
Idle --> CollectingAudioNumber : User uploads audio
CollectingAudioNumber --> CollectingDate : Enter audio number
CollectingDate --> CollectingEmployee : Enter date
CollectingEmployee --> CollectingPlaceName : Enter employee name
CollectingPlaceName --> CollectingBuildingType : Enter place name
CollectingBuildingType --> CollectingZone : Enter building type
CollectingZone --> CollectingCityOrClient : Enter zone
CollectingCityOrClient --> ConfirmingData : Enter city (design) or client (interview)
ConfirmingData --> AnalysisReady : Confirm data
AnalysisReady --> Idle : Complete analysis
style CollectingAudioNumber fill : #f9f
style ConfirmingData fill : #9f9
style AnalysisReady fill : #9ff
```

**Diagram sources**
- [handlers.py](file://src/handlers.py#L1-L805)

The state machine guides users through collecting essential metadata (audio number, date, employee name, etc.) before analysis can proceed. Each step updates the user's state, and the system provides appropriate prompts for the next required input. Once all data is collected, users can confirm and proceed to select analysis reports.

#### Analysis Initiation
When a user selects a report type from the menu, the `handle_report` function determines whether building-specific prompts are required. For reports that depend on building type (hotel, restaurant, spa), it first prompts the user to select the appropriate type before proceeding with analysis. This ensures that the correct specialized prompts are used for contextually accurate results.

**Section sources**
- [handlers.py](file://src/handlers.py#L1-L805)

### analysis.py: Core Analysis Engine
The `analysis.py` module contains the core logic for LLM-driven analysis, implementing both sequential and parallel processing patterns for different types of analytical tasks.

#### Sequential Analysis Pipeline
```mermaid
flowchart TD
A[Input Text] --> B{Prompt List}
B --> C[First Prompt + Text]
C --> D[Claude API]
D --> E[Intermediate Result]
E --> F[Second Prompt + Result]
F --> G[Claude API]
G --> H[Final Result]
H --> I[Return Output]
style A fill:#f9f,stroke:#333
style I fill:#bbf,stroke:#333
```

**Diagram sources**
- [analysis.py](file://src/analysis.py#L1-L491)

The `analyze_methodology` function implements a sequential processing pipeline where multiple prompts are applied in order, with each subsequent prompt operating on the output of the previous step. This allows for complex analytical workflows, such as first extracting key information and then synthesizing it into a structured report. The function handles both single-pass analyses and multi-stage processes, maintaining state between prompt applications.

#### Parallel Processing for RAG
For retrieval-augmented generation tasks, the system implements parallel processing to improve performance and manage API rate limits:

```mermaid
flowchart TD
A[User Query] --> B[Vector Search]
B --> C[Retrieve Relevant Chunks]
C --> D{Multiple Chunks?}
D --> |Yes| E[Create Async Queue]
E --> F[Worker 1: API Key 1]
E --> G[Worker 2: API Key 2]
E --> H[Worker 3: API Key 3]
F --> I[Process Chunk]
G --> I
H --> I
I --> J[Aggregate Results]
J --> K[Generate Final Answer]
K --> L[Return Response]
style A fill:#f9f,stroke:#333
style L fill:#bbf,stroke:#333
```

**Diagram sources**
- [analysis.py](file://src/analysis.py#L1-L491)

The `extract_from_chunk_parallel_async` function distributes processing across multiple Anthropic API keys to overcome rate limits. It implements token and request rate limiting based on each API key's quota, calculating appropriate delays between requests to avoid exceeding limits. The system uses a priority queue to distribute work evenly across available API keys, maximizing throughput while maintaining compliance with usage quotas.

#### Error Handling and Resilience
The analysis engine implements comprehensive error handling to ensure reliability:

```mermaid
flowchart TD
A[Send Request] --> B{Success?}
B --> |Yes| C[Return Result]
B --> |No| D{Error Type?}
D --> |Rate Limit| E[Exponential Backoff]
E --> F[Retry with Delay]
F --> A
D --> |Permission| G[Log API Key Error]
G --> H[Return User-Friendly Message]
D --> |Other API Error| I[Log Error]
I --> J[Retry with Backoff]
J --> A
D --> |Processing Error| K[Return Default Response]
style A fill:#f9f,stroke:#333
style C fill:#9f9,stroke:#333
style H fill:#f99,stroke:#333
```

**Diagram sources**
- [analysis.py](file://src/analysis.py#L1-L491)

The `send_msg_to_model` function implements retry logic with exponential backoff for rate limit errors, automatically retrying failed requests with increasing delays. It also handles permission errors (such as invalid API keys) by logging the issue and returning user-friendly error messages. For other API errors, it implements a general retry mechanism with backoff to handle transient issues.

**Section sources**
- [analysis.py](file://src/analysis.py#L1-L491)

### storage.py: Data Management and RAG System
The `storage.py` module manages both persistent database operations and the in-memory RAG (Retrieval-Augmented Generation) system that enables contextual analysis across multiple reports.

#### RAG Index Creation
```mermaid
flowchart TD
A[Raw Markdown Text] --> B[split_markdown_text]
B --> C[Create Document Objects]
C --> D[CustomSentenceTransformerEmbeddings]
D --> E[FAISS.from_documents]
E --> F[Vector Database in Memory]
F --> G[Similarity Search]
G --> H[Retrieve Relevant Chunks]
H --> I[Generate Contextual Answer]
style A fill:#f9f,stroke:#333
style I fill:#bbf,stroke:#333
```

**Diagram sources**
- [storage.py](file://src/storage.py#L1-L310)

The `create_db_in_memory` function transforms markdown-formatted report text into a FAISS vector database using SentenceTransformer embeddings. It first splits the text into manageable chunks, then creates Document objects for each chunk, and finally generates embeddings to create the searchable index. This allows for semantic search across thousands of reports, retrieving the most relevant content for a given query.

#### Database Integration
The system integrates with PostgreSQL to store transcripts, audit results, and metadata:

```mermaid
erDiagram
USER_ROAD {
int audit_id PK
int scenario_id FK
int report_type_id FK
int building_id FK
}
AUDIT {
int audit_id PK
string audit_text
int employee_id FK
int place_id FK
date audit_date
int city_id FK
int transcription_id FK
int client_id FK
}
TRANSCRIPTION {
int transcription_id PK
string transcription_text
string audio_file_name
int number_audio
}
SCENARIO {
int scenario_id PK
string scenario_name
}
REPORT_TYPE {
int report_type_id PK
string report_type_desc
int scenario_id FK
}
BUILDING {
int building_id PK
string building_type
}
USER_ROAD ||--o{ AUDIT : contains
AUDIT ||--o{ TRANSCRIPTION : references
AUDIT ||--|| SCENARIO : has
AUDIT ||--|| REPORT_TYPE : has
AUDIT ||--|| BUILDING : has
```

**Diagram sources**
- [storage.py](file://src/storage.py#L1-L310)
- [db_handler/db.py](file://src/db_handler/db.py#L1-L100)

The database schema supports complex queries that join audit results with their contextual metadata. The `build_reports_grouped` function executes a comprehensive SQL query that joins multiple tables to retrieve complete report information, including transcription details, employee data, location information, and audit metadata. This grouped data is then used to populate the RAG system for contextual analysis.

**Section sources**
- [storage.py](file://src/storage.py#L1-L310)

## Dependency Analysis
The system components are interconnected through a well-defined dependency structure that enables modularity while maintaining cohesive functionality.

```mermaid
graph TD
A[handlers.py] --> B[run_analysis.py]
A --> C[audio_utils.py]
A --> D[storage.py]
A --> E[analysis.py]
B --> F[analysis.py]
B --> G[storage.py]
B --> H[datamodels.py]
C --> I[OpenAI Whisper]
D --> J[PostgreSQL]
D --> K[FAISS]
E --> L[Claude API]
E --> M[db_handler.db]
F --> N[config.py]
G --> O[utils.py]
style A fill:#f96,stroke:#333
style B fill:#69f,stroke:#333
style C fill:#69f,stroke:#333
style D fill:#69f,stroke:#333
style E fill:#69f,stroke:#333
```

**Diagram sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L344)
- [handlers.py](file://src/handlers.py#L1-L805)
- [analysis.py](file://src/analysis.py#L1-L491)
- [storage.py](file://src/storage.py#L1-L310)

The dependency graph shows that `handlers.py` serves as the primary integration point, depending on multiple core modules to implement the complete workflow. The `run_analysis.py` module depends on analysis and storage components to execute the evaluation pipeline, while the analysis engine itself relies on external LLM APIs and database access. Configuration data is centralized in `config.py`, which is imported by all components that require API keys or system settings.

**Section sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L344)
- [handlers.py](file://src/handlers.py#L1-L805)
- [analysis.py](file://src/analysis.py#L1-L491)
- [storage.py](file://src/storage.py#L1-L310)

## Performance Considerations
The system implements several performance optimizations to handle resource-intensive LLM operations efficiently while managing costs and rate limits.

### Asynchronous Execution
The system uses both threading and asyncio to maintain responsiveness during long-running operations. The loading animation runs in a separate thread from the main analysis, preventing UI blocking. For RAG operations, the system uses `aiohttp` with async/await patterns to process multiple chunks concurrently, significantly reducing total processing time compared to sequential execution.

### Parallel Analysis of Multiple Files
While the current implementation processes one file at a time per user, the architecture supports parallel analysis through its state management design. Each user's session is isolated through their chat ID, allowing the system to handle multiple concurrent analysis requests. The use of thread-safe data structures and proper synchronization primitives ensures data integrity across concurrent operations.

### Resource Throttling for LLM API Management
The system implements sophisticated resource throttling to manage LLM API costs and rate limits:

- **Token Rate Limiting**: The `extract_from_chunk_parallel_async` function calculates delays based on estimated token consumption, ensuring compliance with each API key's token-per-minute quota.
- **Request Rate Limiting**: The system also enforces requests-per-minute limits, using the maximum of token-based and request-based delays to prevent quota violations.
- **Multiple API Keys**: By supporting seven Anthropic API keys, the system can distribute load across multiple accounts, effectively multiplying the available rate limits.
- **Exponential Backoff**: For rate limit errors, the system implements exponential backoff with a maximum retry threshold to avoid infinite loops while handling temporary throttling.

These performance considerations ensure that the system can handle high-volume analysis tasks while remaining within API usage quotas and providing acceptable response times to users.

## Troubleshooting Guide
The system includes comprehensive error handling and logging to facilitate troubleshooting of common issues.

### Common Issues and Solutions
**Section sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L344)
- [handlers.py](file://src/handlers.py#L1-L805)
- [analysis.py](file://src/analysis.py#L1-L491)

#### API Key Errors
- **Symptoms**: "LLM unavailable (key/region)" messages, permission errors in logs
- **Causes**: Invalid API keys, region restrictions, expired keys
- **Solutions**: Verify keys in `.env` file, check Anthropic console for key status, ensure proper region access

#### Audio Processing Failures
- **Symptoms**: "Error processing audio" messages, incomplete transcripts
- **Causes**: Large file sizes, unsupported formats, Whisper API issues
- **Solutions**: Ensure audio is under size limits, convert to supported formats (MP3, WAV), verify OpenAI API connectivity

#### Rate Limit Exceeded
- **Symptoms**: Slow processing, "Rate limit hit" warnings in logs
- **Causes**: Excessive API requests, insufficient API keys
- **Solutions**: Add additional API keys to configuration, optimize prompt usage, implement caching

#### Database Connection Issues
- **Symptoms**: "Failed to create bucket" errors, inability to save results
- **Causes**: Incorrect database credentials, network issues, PostgreSQL service down
- **Solutions**: Verify database configuration in `.env`, check PostgreSQL service status, validate network connectivity

The system logs detailed information for each operation, including token counts, processing times, and API response codes, facilitating diagnosis of performance and functionality issues.

## Conclusion
The multi-stage evaluation workflow in VoxPersona represents a sophisticated integration of audio processing, natural language understanding, and structured reporting. The system orchestrates a complex pipeline from audio upload to final report generation, leveraging multiple AI models and data sources to deliver comprehensive analytical insights. Key strengths include its modular architecture, robust error handling, and efficient resource management through parallel processing and rate limit compliance. The clear separation of concerns between components enhances maintainability and allows for targeted improvements to specific stages of the workflow. Future enhancements could include caching of frequent queries, improved error recovery mechanisms, and expanded support for additional analysis types, further solidifying the system's capabilities as a comprehensive voice analysis platform.