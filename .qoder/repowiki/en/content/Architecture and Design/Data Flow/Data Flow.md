# Data Flow

<cite>
**Referenced Files in This Document**   
- [audio_utils.py](file://src/audio_utils.py)
- [parser.py](file://src/parser.py)
- [rag_persistence.py](file://src/rag_persistence.py)
- [storage.py](file://src/storage.py)
- [db_handler/db.py](file://src/db_handler/db.py)
- [analysis.py](file://src/analysis.py)
- [main.py](file://src/main.py)
- [handlers.py](file://src/handlers.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Data Flow: Happy Path](#data-flow-happy-path)
7. [Data Flow: Error Handling and Retry Mechanisms](#data-flow-error-handling-and-retry-mechanisms)
8. [Performance Considerations](#performance-considerations)
9. [Conclusion](#conclusion)

## Introduction
VoxPersona is an AI-powered voice analysis platform that enables automated transcription, content analysis, and report generation from audio inputs. This document provides a comprehensive end-to-end data flow analysis, tracing the journey of an audio file from Telegram upload to final report delivery. The system leverages OpenAI Whisper for transcription, a RAG-based retrieval system with FAISS and SentenceTransformers for contextual analysis, and PostgreSQL for structured data persistence. The flow includes preprocessing, parsing, storage, retrieval, and feedback loops, with robust error handling and performance optimization strategies.

## Project Structure
The project follows a modular structure with clear separation of concerns. Core application logic resides in the `src/` directory, while prompts are organized by scenario in dedicated folders. Configuration, database handling, and utility functions are encapsulated in individual modules.

```mermaid
graph TD
A[src/] --> B[audio_utils.py]
A --> C[parser.py]
A --> D[rag_persistence.py]
A --> E[storage.py]
A --> F[db_handler/db.py]
A --> G[analysis.py]
A --> H[handlers.py]
A --> I[main.py]
J[prompts-by-scenario/] --> K[design/]
J --> L[interview/]
J --> M[sql_prompts/]
N[.] --> A
N --> J
N --> O[README.md]
N --> P[DEPLOYMENT_GUIDE.md]
N --> Q[SETUP.md]
N --> R[Dockerfile]
N --> S[docker-compose.yml]
```

**Diagram sources**
- [src/audio_utils.py](file://src/audio_utils.py)
- [src/parser.py](file://src/parser.py)
- [src/rag_persistence.py](file://src/rag_persistence.py)
- [src/storage.py](file://src/storage.py)
- [src/db_handler/db.py](file://src/db_handler/db.py)

**Section sources**
- [src/audio_utils.py](file://src/audio_utils.py)
- [src/parser.py](file://src/parser.py)
- [src/rag_persistence.py](file://src/rag_persistence.py)
- [src/storage.py](file://src/storage.py)
- [src/db_handler/db.py](file://src/db_handler/db.py)

## Core Components
The core components of VoxPersona include audio preprocessing, transcription, text parsing, RAG-based context retrieval, vector and metadata storage, and structured database operations. Each component plays a critical role in transforming raw audio into actionable insights.

**Section sources**
- [audio_utils.py](file://src/audio_utils.py#L1-L50)
- [parser.py](file://src/parser.py#L1-L175)
- [rag_persistence.py](file://src/rag_persistence.py#L1-L37)
- [storage.py](file://src/storage.py#L1-L310)
- [db_handler/db.py](file://src/db_handler/db.py#L1-L399)

## Architecture Overview
The system architecture is event-driven, initiated by a Telegram message containing an audio file. The bot processes the file through a pipeline involving format validation, transcription, parsing, RAG retrieval, and report generation. Results are stored in both vector and relational databases for future retrieval and analysis.

```mermaid
graph LR
A[Telegram Upload] --> B[audio_utils.py]
B --> C[OpenAI Whisper API]
C --> D[parser.py]
D --> E[rag_persistence.py]
E --> F[FAISS + SentenceTransformers]
F --> G[storage.py]
G --> H[PostgreSQL]
H --> I[Report Generation]
I --> J[Telegram Response]
K[Error Handling] --> B
K --> C
K --> D
K --> E
K --> G
K --> H
```

**Diagram sources**
- [audio_utils.py](file://src/audio_utils.py#L1-L50)
- [analysis.py](file://src/analysis.py)
- [parser.py](file://src/parser.py#L1-L175)
- [rag_persistence.py](file://src/rag_persistence.py#L1-L37)
- [storage.py](file://src/storage.py#L1-L310)
- [db_handler/db.py](file://src/db_handler/db.py#L1-L399)

## Detailed Component Analysis

### Audio Processing and Transcription
The audio processing pipeline begins with `audio_utils.py`, which handles file validation, naming, and size extraction. It interfaces with `analysis.py` to perform transcription via the OpenAI Whisper API.

#### Audio Utility Functions
```mermaid
flowchart TD
Start([Extract Audio Filename]) --> ValidateType{"Message Type?"}
ValidateType --> |Voice| GenerateVoiceName["Generate timestamp-based name"]
ValidateType --> |Audio| UseAudioName["Use provided file name"]
ValidateType --> |Document| UseDocumentName["Use document file name"]
ValidateType --> |Unknown| GenerateDefaultName["Generate default name"]
GenerateVoiceName --> Output
UseAudioName --> Output
UseDocumentName --> Output
GenerateDefaultName --> Output
Output([Return filename])
SizeStart([Get File Size]) --> CheckType{"Message Type?"}
CheckType --> |Voice| GetVoiceSize["Return voice.file_size"]
CheckType --> |Audio| GetAudioSize["Return audio.file_size"]
CheckType --> |Document| GetDocSize["Return document.file_size"]
CheckType --> |None| ThrowError["Raise ValueError"]
GetVoiceSize --> SizeOutput
GetAudioSize --> SizeOutput
GetDocSize --> SizeOutput
ThrowError --> SizeOutput
SizeOutput([Return size in bytes])
```

**Diagram sources**
- [audio_utils.py](file://src/audio_utils.py#L1-L50)

**Section sources**
- [audio_utils.py](file://src/audio_utils.py#L1-L50)

### Text Parsing and Structuring
The `parser.py` module parses structured text input (e.g., metadata accompanying audio) into a standardized dictionary format. It normalizes building types, parses dates, and extracts key information based on the scenario (design or interview).

#### Parsing Logic Flow
```mermaid
flowchart TD
ParseStart([Parse Message Text]) --> DetermineMode{"Mode = 'design'?"}
DetermineMode --> |Yes| ParseDesign["parse_design(lines)"]
DetermineMode --> |No| ParseInterview["parse_interview(lines)"]
ParseDesign --> ExtractFields["Extract: audio_number, date, employee, place_name, building_type, zone_name, city"]
ParseDesign --> |6 lines| ExtractFieldsNoZone["Extract: audio_number, date, employee, place_name, building_type, city"]
ExtractFieldsNoZone --> SetZone["Set zone_name = '-'"]
ParseInterview --> ExtractInterviewFields["Extract: audio_number, date, employee, client, building_info, place_name"]
ExtractFields --> Normalize["Normalize data via parse_* functions"]
ExtractFieldsNoZone --> Normalize
ExtractInterviewFields --> Normalize
Normalize --> ParseNumber["parse_file_number()"]
Normalize --> ParseDate["parse_date()"]
Normalize --> ParseName["parse_name()"]
Normalize --> ParseBuilding["parse_building_type()"]
Normalize --> ParseZone["parse_zone()"]
Normalize --> ParseCity["parse_city()"]
ParseNumber --> Output
ParseDate --> Output
ParseName --> Output
ParseBuilding --> Output
ParseZone --> Output
ParseCity --> Output
Output([Return structured dict])
```

**Diagram sources**
- [parser.py](file://src/parser.py#L1-L175)

**Section sources**
- [parser.py](file://src/parser.py#L1-L175)

### RAG System and Context Retrieval
The RAG system, managed by `rag_persistence.py`, handles the loading and saving of FAISS vector indices. These indices are created using SentenceTransformers embeddings and are used for semantic retrieval during analysis.

#### RAG Persistence Workflow
```mermaid
sequenceDiagram
participant Main as main.py
participant RAG as rag_persistence.py
participant Storage as storage.py
participant Disk as File System
Main->>RAG : load_rag_indices()
RAG->>Disk : List RAG_INDEX_DIR
loop For each index
RAG->>Disk : Load FAISS index
RAG->>RAG : Initialize CustomSentenceTransformerEmbeddings
RAG->>RAG : FAISS.load_local(path, embeddings)
RAG-->>RAG : Store in dict
end
RAG-->>Main : Return rags dict
Main->>RAG : periodic_save_rags()
RAG->>RAG : Acquire rags_lock
loop For each rag
RAG->>Disk : Delete existing path
RAG->>Disk : Save FAISS index via save_local()
end
```

**Diagram sources**
- [rag_persistence.py](file://src/rag_persistence.py#L1-L37)
- [main.py](file://src/main.py#L1-L95)

**Section sources**
- [rag_persistence.py](file://src/rag_persistence.py#L1-L37)

### Vector and Metadata Storage
The `storage.py` module manages both in-memory vector databases and persistent storage operations. It creates FAISS indices from markdown text and handles safe filename generation for cross-platform compatibility.

#### Vector Database Creation
```mermaid
flowchart TD
CreateStart([create_db_in_memory]) --> SplitText["split_markdown_text(markdown_text)"]
SplitText --> CheckType{"Is Document list?"}
CheckType --> |Yes| UseChunks["Use as chunks_documents"]
CheckType --> |No| WrapChunks["Wrap in Document objects"]
UseChunks --> IndexCreation["FAISS.from_documents(documents, embedding)"]
WrapChunks --> IndexCreation
IndexCreation --> ReturnIndex["Return db_index"]
```

**Diagram sources**
- [storage.py](file://src/storage.py#L1-L310)

**Section sources**
- [storage.py](file://src/storage.py#L1-L310)

### Structured Data Storage
The `db_handler/db.py` module provides a transactional interface to PostgreSQL, handling CRUD operations for entities like employees, clients, places, and audits. It uses decorators for database transaction management.

#### Database Transaction Pattern
```mermaid
sequenceDiagram
participant Func as Function
participant Decorator as db_transaction
participant DB as PostgreSQL
Func->>Decorator : Call with @db_transaction
Decorator->>DB : Open connection
Decorator->>Func : Execute function with cursor
Func->>DB : Perform SQL operations
DB-->>Func : Return result
Func-->>Decorator : Return result
Decorator->>DB : Commit (if commit=True)
Decorator->>DB : Close connection
Decorator-->>Func : Return result
```

**Diagram sources**
- [db_handler/db.py](file://src/db_handler/db.py#L1-L399)

**Section sources**
- [db_handler/db.py](file://src/db_handler/db.py#L1-L399)

## Data Flow: Happy Path
This section traces the complete journey of an audio file through the system under ideal conditions.

```mermaid
sequenceDiagram
participant User as Telegram User
participant Bot as Telegram Bot
participant AudioUtils as audio_utils.py
participant Whisper as OpenAI Whisper API
participant Parser as parser.py
participant RAG as rag_persistence.py
participant Storage as storage.py
participant DB as PostgreSQL
User->>Bot : Upload audio file
Bot->>AudioUtils : extract_audio_filename(), define_audio_file_params()
AudioUtils-->>Bot : Return filename and size
Bot->>AudioUtils : transcribe_audio_and_save()
AudioUtils->>Whisper : transcribe_audio()
Whisper-->>AudioUtils : Return raw text
AudioUtils->>Bot : Store in processed_texts[chat_id]
Bot->>Parser : parse_message_text(text, mode)
Parser-->>Bot : Return structured data dict
Bot->>RAG : Use loaded RAG indices for context retrieval
RAG->>Storage : create_db_in_memory() with relevant prompts
Storage->>RAG : Return FAISS index
Bot->>Storage : save_user_input_to_db()
Storage->>DB : Execute INSERTs via db_handler/db.py
DB-->>Storage : Return IDs
Storage-->>Bot : Confirmation
Bot->>User : Send final report
```

**Diagram sources**
- [audio_utils.py](file://src/audio_utils.py#L1-L50)
- [parser.py](file://src/parser.py#L1-L175)
- [rag_persistence.py](file://src/rag_persistence.py#L1-L37)
- [storage.py](file://src/storage.py#L1-L310)
- [db_handler/db.py](file://src/db_handler/db.py#L1-L399)

## Data Flow: Error Handling and Retry Mechanisms
The system implements robust error handling at each stage, with logging and non-blocking failure recovery.

```mermaid
flowchart TD
A[Start Processing] --> B{Audio Validation}
B --> |Valid| C[Transcribe Audio]
B --> |Invalid| Z[Log Error, Notify User]
C --> |Success| D[Parse Text]
C --> |Failure| E[Retry Transcription]
E --> |Success| D
E --> |Max Retries| Z
D --> |Valid Format| F[Retrieve RAG Context]
D --> |Invalid Format| Z
F --> |Success| G[Store in DB]
F --> |Failure| H[Use Fallback Prompts]
H --> G
G --> |Success| I[Generate Report]
G --> |Failure| J[Rollback Transaction]
J --> Z
I --> K[Send to User]
K --> L[End]
Z --> L
```

**Diagram sources**
- [audio_utils.py](file://src/audio_utils.py#L1-L50)
- [parser.py](file://src/parser.py#L1-L175)
- [rag_persistence.py](file://src/rag_persistence.py#L1-L37)
- [storage.py](file://src/storage.py#L1-L310)
- [db_handler/db.py](file://src/db_handler/db.py#L1-L399)

**Section sources**
- [audio_utils.py](file://src/audio_utils.py#L1-L50)
- [parser.py](file://src/parser.py#L1-L175)
- [rag_persistence.py](file://src/rag_persistence.py#L1-L37)
- [storage.py](file://src/storage.py#L1-L310)
- [db_handler/db.py](file://src/db_handler/db.py#L1-L399)

## Performance Considerations
The system faces potential I/O bottlenecks in audio transcription, vector index loading, and database operations. Key optimization strategies include:

- **Caching**: RAG indices are loaded once and reused, with periodic persistence to disk.
- **Batching**: Database operations are wrapped in transactions to minimize round trips.
- **Asynchronous Processing**: RAG initialization runs in the background without blocking bot startup.
- **Efficient Text Splitting**: Markdown content is split intelligently to balance chunk size and semantic coherence.
- **Connection Pooling**: PostgreSQL connections are managed efficiently through context managers.

The use of `nest_asyncio` allows background tasks like RAG loading and periodic saving to coexist with the Telegram bot's event loop, improving responsiveness.

**Section sources**
- [main.py](file://src/main.py#L1-L95)
- [rag_persistence.py](file://src/rag_persistence.py#L1-L37)
- [storage.py](file://src/storage.py#L1-L310)
- [db_handler/db.py](file://src/db_handler/db.py#L1-L399)

## Conclusion
VoxPersona implements a robust, end-to-end pipeline for transforming audio inputs into structured analytical reports. The system effectively integrates multiple AI services, vector databases, and relational storage with careful attention to error handling and performance. By leveraging asynchronous processing, transactional integrity, and semantic retrieval, it provides a scalable solution for voice-based data analysis. Future improvements could include streaming transcription, enhanced retry logic with exponential backoff, and more sophisticated caching mechanisms for frequently accessed reports.