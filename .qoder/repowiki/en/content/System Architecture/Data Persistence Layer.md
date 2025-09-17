# Data Persistence Layer

<cite>
**Referenced Files in This Document**   
- [db.py](file://src/db_handler/db.py)
- [storage.py](file://src/storage.py)
- [rag_persistence.py](file://src/rag_persistence.py)
- [fill_prompts_table.py](file://src/db_handler/fill_prompts_table.py)
- [datamodels.py](file://src/datamodels.py)
- [step_2_sql_request.txt](file://prompts-by-scenario/sql_prompts/part2/step_2_sql_request.txt)
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
This document provides comprehensive documentation for the data persistence architecture in VoxPersona, a system designed to analyze audio interviews and audit reports across different business types including hotels, restaurants, and health centers. The system employs a hybrid storage approach combining PostgreSQL for structured data and MinIO for binary audio files, with an additional RAG (Retrieval-Augmented Generation) index layer for fast semantic search. This documentation details the schema design, data flow, initialization processes, and performance characteristics of the persistence layer.

## Project Structure

```mermaid
graph TD
subgraph "Data Storage"
PostgreSQL[(PostgreSQL)]
MinIO[(MinIO Object Storage)]
end
subgraph "Application Layer"
DBHandler[db_handler]
Storage[storage]
RAG[rag_persistence]
Prompts[fill_prompts_table]
end
subgraph "Configuration & Models"
Config[config]
DataModels[datamodels]
end
DBHandler --> PostgreSQL
Storage --> MinIO
RAG --> MinIO
Prompts --> PostgreSQL
DataModels --> Prompts
DataModels --> Storage
```

**Diagram sources**
- [db.py](file://src/db_handler/db.py)
- [storage.py](file://src/storage.py)
- [rag_persistence.py](file://src/rag_persistence.py)
- [fill_prompts_table.py](file://src/db_handler/fill_prompts_table.py)

**Section sources**
- [db.py](file://src/db_handler/db.py)
- [storage.py](file://src/storage.py)
- [rag_persistence.py](file://src/rag_persistence.py)
- [fill_prompts_table.py](file://src/db_handler/fill_prompts_table.py)

## Core Components

The persistence architecture in VoxPersona consists of three main components: PostgreSQL for structured data storage, MinIO for binary object storage, and FAISS-based RAG indices for semantic search capabilities. The system uses a decorator-based transaction management pattern in `db.py` to ensure data consistency, with functions like `@db_transaction` handling connection lifecycle and commit operations. The storage layer in `storage.py` manages audio file processing and report generation, while `rag_persistence.py` handles the serialization and deserialization of vector indices. The initialization process in `fill_prompts_table.py` populates the prompts database from template files organized in a hierarchical directory structure.

**Section sources**
- [db.py](file://src/db_handler/db.py#L1-L399)
- [storage.py](file://src/storage.py#L1-L310)
- [rag_persistence.py](file://src/rag_persistence.py#L1-L37)
- [fill_prompts_table.py](file://src/db_handler/fill_prompts_table.py#L1-L228)

## Architecture Overview

```mermaid
graph TD
subgraph "PostgreSQL Database"
A[audit]
T[transcription]
S[scenario]
RT[report_type]
B[buildings]
P[place]
E[employee]
C[client]
CT[city]
Z[zone]
UR[user_road]
PB[prompts_buildings]
PR[prompts]
end
subgraph "MinIO Storage"
Audio[Audio Files]
RAGIndex[RAG Indices]
end
subgraph "Application"
DB[db.py]
ST[storage.py]
RP[rag_persistence.py]
FP[fill_prompts_table.py]
end
FP --> PR
FP --> RT
FP --> S
FP --> B
FP --> PB
DB --> A
DB --> T
DB --> UR
DB --> E
DB --> C
DB --> P
DB --> CT
DB --> Z
ST --> Audio
ST --> A
ST --> T
ST --> UR
RP --> RAGIndex
RP --> ST
A --> |transcription_id| T
A --> |employee_id| E
A --> |client_id| C
A --> |place_id| P
A --> |city_id| CT
A --> |audit_id| UR
UR --> |scenario_id| S
UR --> |report_type_id| RT
UR --> |building_id| B
PB --> |prompt_id| PR
PB --> |building_id| B
PB --> |report_type_id| RT
P --> |place_id| Z
```

**Diagram sources**
- [db.py](file://src/db_handler/db.py)
- [storage.py](file://src/storage.py)
- [rag_persistence.py](file://src/rag_persistence.py)
- [fill_prompts_table.py](file://src/db_handler/fill_prompts_table.py)

## Detailed Component Analysis

### PostgreSQL Schema Design

The PostgreSQL schema in VoxPersona follows a normalized design with referential integrity constraints to maintain data consistency. The core entity is the `audit` table which stores structured audit reports, linked to `transcription` records that contain the original text from audio processing. The system uses a flexible scenario-based architecture where `scenario` (either "Интервью" or "Дизайн") determines the type of analysis, with `report_type` specifying the specific report category within that scenario. The `user_road` table serves as a junction entity connecting audits to their corresponding scenario, report type, and building type, enabling complex queries across different dimensions of analysis.

```mermaid
erDiagram
audit {
integer audit_id PK
text audit
integer employee_id FK
integer client_id FK
integer place_id FK
integer city_id FK
integer transcription_id FK
date audit_date
}
transcription {
integer transcription_id PK
varchar transcription_text
varchar audio_file_name
timestamp transcription_date
integer number_audio
}
scenario {
integer scenario_id PK
varchar scenario_name
}
report_type {
integer report_type_id PK
varchar report_type_desc
integer scenario_id FK
}
buildings {
integer building_id PK
varchar building_type
}
place {
integer place_id PK
varchar place_name
varchar building_type
}
user_road {
integer user_road_id PK
integer audit_id FK
integer scenario_id FK
integer report_type_id FK
integer building_id FK
}
prompts {
integer prompt_id PK
text prompt
integer run_part
varchar prompt_name
boolean is_json_prompt
}
prompts_buildings {
integer prompt_id FK
integer building_id FK
integer report_type_id FK
}
employee {
integer employee_id PK
varchar employee_name
}
client {
integer client_id PK
varchar client_name
}
city {
integer city_id PK
varchar city_name
}
zone {
integer zone_id PK
varchar zone_name
}
place_zone {
integer place_id FK
integer zone_id FK
}
audit ||--o{ transcription : "1-to-1"
audit ||--o{ employee : "n-to-1"
audit ||--o{ client : "n-to-1"
audit ||--o{ place : "n-to-1"
audit ||--o{ city : "n-to-1"
audit ||--o{ user_road : "1-to-1"
user_road }o--|| scenario : "n-to-1"
user_road }o--|| report_type : "n-to-1"
user_road }o--|| buildings : "n-to-1"
prompts_buildings }o--|| prompts : "n-to-1"
prompts_buildings }o--|| buildings : "n-to-1"
prompts_buildings }o--|| report_type : "n-to-1"
place ||--o{ place_zone : "1-to-n"
zone ||--o{ place_zone : "1-to-n"
```

**Diagram sources**
- [db.py](file://src/db_handler/db.py)
- [step_2_sql_request.txt](file://prompts-by-scenario/sql_prompts/part2/step_2_sql_request.txt)

**Section sources**
- [db.py](file://src/db_handler/db.py#L1-L399)

### MinIO Binary Storage

The MinIO object storage system in VoxPersona handles binary audio files, providing scalable and durable storage for media assets. The `storage.py` module manages the interaction with MinIO, using the `process_stored_file` function to retrieve and process audio files for transcription. Audio files are stored with safe filenames generated by the `safe_filename` function, which transliterates Cyrillic characters and sanitizes special characters to ensure filesystem compatibility. The system supports various audio formats defined in `OPENAI_AUDIO_EXTS` in `datamodels.py`, including MP3, WAV, and M4A files. This separation of binary and structured data follows the principle of using the right storage system for each data type, with PostgreSQL handling metadata and text while MinIO manages large binary objects.

**Section sources**
- [storage.py](file://src/storage.py#L1-L310)
- [datamodels.py](file://src/datamodels.py#L1-L72)

### RAG Index Persistence

The RAG (Retrieval-Augmented Generation) persistence mechanism in `rag_persistence.py` enables fast semantic search capabilities by storing vector indices on disk. The system uses FAISS (Facebook AI Similarity Search) to create and manage these indices, which are serialized to and deserialized from the filesystem using the `save_rag_indices` and `load_rag_indices` functions. The indices are stored in the directory specified by `RAG_INDEX_DIR` in the configuration, with each index saved in a subdirectory named using the `safe_filename` function for filesystem compatibility. This persistence layer allows the system to maintain pre-computed embeddings for prompts and other textual data, significantly reducing the computational overhead during query time. The use of custom `CustomSentenceTransformerEmbeddings` ensures consistency in the embedding model across different sessions.

```mermaid
flowchart TD
A[Input Text] --> B[Split into Chunks]
B --> C[Generate Embeddings]
C --> D[Create FAISS Index]
D --> E[Save to Disk]
E --> F[MinIO/RAG Directory]
G[Query] --> H[Load FAISS Index]
H --> I[Search Similar Chunks]
I --> J[Return Results]
style F fill:#f9f,stroke:#333
subgraph "Persistence Operations"
E
H
end
subgraph "Memory Operations"
B
C
D
I
end
```

**Diagram sources**
- [rag_persistence.py](file://src/rag_persistence.py)
- [storage.py](file://src/storage.py)

**Section sources**
- [rag_persistence.py](file://src/rag_persistence.py#L1-L37)

### Prompts Database Initialization

The `fill_prompts_table.py` script initializes the prompts database by populating it from template files stored in the `prompts-by-scenario` directory hierarchy. The script recursively processes this directory structure, creating database records for scenarios, report types, buildings, and prompts based on the folder and file organization. It uses mapping dictionaries from `datamodels.py` to translate folder names into human-readable labels (e.g., "design" to "Дизайн"). The initialization process establishes the complex many-to-many relationships between prompts, buildings, and report types through the `prompts_buildings` junction table. This hierarchical approach to prompt management allows for easy updates and additions by simply modifying the template files without changing the application code, providing a flexible system for managing different types of audit and interview prompts across various business domains.

```mermaid
flowchart TD
A[Start] --> B[Connect to Database]
B --> C[Process Base Directory]
C --> D{Is Directory?}
D --> |Yes| E[Handle Special Cases]
D --> |No| F[Read Prompt File]
E --> G{Folder Type?}
G --> |hotel/restaurant/spa| H[Create Building Record]
G --> |part1/part2/part3| I[Set Run Part]
G --> |json-prompt| J[Set JSON Flag]
G --> |Other| K[Recurse]
F --> L[Create Prompt Record]
L --> M[Create Relationships]
M --> N[Commit Transaction]
style H fill:#bbf,stroke:#f66
style I fill:#bbf,stroke:#f66
style J fill:#bbf,stroke:#f66
style L fill:#bbf,stroke:#f66
style M fill:#bbf,stroke:#f66
```

**Diagram sources**
- [fill_prompts_table.py](file://src/db_handler/fill_prompts_table.py)
- [datamodels.py](file://src/datamodels.py)

**Section sources**
- [fill_prompts_table.py](file://src/db_handler/fill_prompts_table.py#L1-L228)
- [datamodels.py](file://src/datamodels.py#L1-L72)

## Dependency Analysis

```mermaid
graph TD
FP[fill_prompts_table.py] --> DB[db.py]
FP --> DM[datamodels.py]
ST[storage.py] --> DB[db.py]
ST --> DM[datamodels.py]
ST --> AN[analysis.py]
RP[rag_persistence.py] --> ST[storage.py]
RP --> UT[utils.py]
DB[db.py] --> CFG[config.py]
ST[storage.py] --> CFG[config.py]
RP[rag_persistence.py] --> CFG[config.py]
FP[fill_prompts_table.py] --> CFG[config.py]
DB -.->|Uses| PG[PostgreSQL]
ST -.->|Uses| MINIO[MinIO]
RP -.->|Uses| MINIO[MinIO]
class FP,DB,ST,RP,DM,CFG,AN,UT,Datamodels,Storage,RAG,Prompts,Config,Analysis,Utils class
class PG,MINIO external
```

**Diagram sources**
- [db.py](file://src/db_handler/db.py)
- [storage.py](file://src/storage.py)
- [rag_persistence.py](file://src/rag_persistence.py)
- [fill_prompts_table.py](file://src/db_handler/fill_prompts_table.py)

**Section sources**
- [db.py](file://src/db_handler/db.py)
- [storage.py](file://src/storage.py)
- [rag_persistence.py](file://src/rag_persistence.py)
- [fill_prompts_table.py](file://src/db_handler/fill_prompts_table.py)

## Performance Considerations

The data persistence architecture in VoxPersona makes several performance-oriented design decisions. Large text storage in PostgreSQL is optimized through the use of appropriate indexes on frequently queried fields such as `scenario_name`, `report_type_desc`, and `building_type`. The separation of binary audio files to MinIO reduces database bloat and improves query performance on the structured data. The RAG index persistence mechanism enables fast semantic search by pre-computing and storing vector embeddings, avoiding the computational cost of real-time embedding generation. The use of connection pooling and transaction decorators in `db.py` ensures efficient database resource utilization. For large-scale deployments, the architecture supports horizontal scaling of the MinIO storage layer and vertical scaling of the PostgreSQL database, with potential for read replicas to handle reporting workloads.

**Section sources**
- [db.py](file://src/db_handler/db.py)
- [storage.py](file://src/storage.py)
- [rag_persistence.py](file://src/rag_persistence.py)

## Troubleshooting Guide

Common issues in the persistence layer typically involve database connection problems, missing prompt templates, or corrupted RAG indices. Connection issues can be diagnosed by checking the `DB_CONFIG` in `config.py` and verifying network connectivity to the PostgreSQL server. Missing prompts can occur if the `fill_prompts_table.py` script fails to execute properly, which can be resolved by verifying the `prompts-by-scenario` directory structure and file permissions. Corrupted RAG indices may cause semantic search failures and can be addressed by deleting the contents of the `RAG_INDEX_DIR` and allowing the system to regenerate them. Audio processing issues are often related to unsupported file formats or corrupted audio files, which can be validated against the `OPENAI_AUDIO_EXTS` tuple in `datamodels.py`. All components include comprehensive logging to aid in troubleshooting, with error messages providing specific guidance for resolution.

**Section sources**
- [db.py](file://src/db_handler/db.py)
- [storage.py](file://src/storage.py)
- [rag_persistence.py](file://src/rag_persistence.py)
- [fill_prompts_table.py](file://src/db_handler/fill_prompts_table.py)
- [datamodels.py](file://src/datamodels.py)

## Conclusion

The data persistence architecture in VoxPersona effectively combines relational, object, and vector storage to support a comprehensive audit and interview analysis system. The PostgreSQL database provides a robust foundation for structured data with referential integrity and complex querying capabilities, while MinIO offers scalable storage for binary audio files. The RAG index persistence layer enables fast semantic search, enhancing the system's analytical capabilities. The initialization process in `fill_prompts_table.py` demonstrates a thoughtful approach to configuration management, allowing for easy updates through template files. This hybrid architecture balances performance, scalability, and maintainability, providing a solid foundation for the VoxPersona application's data management needs.