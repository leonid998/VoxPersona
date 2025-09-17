# File Management Workflow

<cite>
**Referenced Files in This Document**   
- [handlers.py](file://src/handlers.py)
- [menus.py](file://src/menus.py)
- [markups.py](file://src/markups.py)
- [db.py](file://src/db_handler/db.py)
- [storage.py](file://src/storage.py)
- [config.py](file://src/config.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [File Browser Interface](#file-browser-interface)
3. [File Retrieval Logic](#file-retrieval-logic)
4. [Delete Workflow](#delete-workflow)
5. [Upload Process](#upload-process)
6. [Synchronization and Caching](#synchronization-and-caching)
7. [Real-World Usage Patterns](#real-world-usage-patterns)
8. [Error Handling and Storage Management](#error-handling-and-storage-management)

## Introduction
VoxPersona provides comprehensive file management capabilities for audio recordings and processed transcripts. The system integrates a user-friendly file browser interface with robust backend operations for storing, retrieving, and processing audio files. This document details the complete file management workflow, covering viewing stored files, uploading new recordings, deleting existing files, and the underlying synchronization between database metadata and object storage. The implementation ensures efficient processing through caching mechanisms and handles various edge cases and error conditions to maintain system reliability.

## File Browser Interface

The file browser interface in VoxPersona allows users to view, select, and manage their stored audio files through an interactive menu system built with `menus.py` and `markups.py`. Users access the file management functionality from the main menu by selecting the "Storage" option, which presents categories of stored files.

The interface displays files in a structured format with options to view, select, or delete individual files. Each file entry includes a filename and a delete button (❌), while additional options allow users to upload new files or navigate back to the main menu. The file browser dynamically generates this interface by scanning the designated storage directories and creating callback buttons for each file operation.

```mermaid
flowchart TD
Start([User selects Storage]) --> DisplayCategories["Display file categories<br/>(audio, text_with_roles, etc.)"]
DisplayCategories --> SelectCategory["User selects category"]
SelectCategory --> ListFiles["List files in selected category"]
ListFiles --> ShowActions["Show actions for each file:<br/>- Select (view/analyze)<br/>- Delete (❌)"]
ShowActions --> UploadOption["Show Upload option"]
UploadOption --> BackOption["Show Back option"]
BackOption --> End([Return to main menu])
```

**Diagram sources**
- [menus.py](file://src/menus.py#L5-L45)
- [markups.py](file://src/markups.py#L45-L65)

**Section sources**
- [menus.py](file://src/menus.py#L5-L94)
- [markups.py](file://src/markups.py#L45-L133)

## File Retrieval Logic

The file retrieval process in VoxPersona involves querying both PostgreSQL for metadata and MinIO for file availability. When a user requests to view files in a specific category, the system first determines the appropriate storage directory from the configuration and lists all files in that directory.

For audio files, the retrieval logic includes additional processing steps. When a user selects an audio file for analysis, the system initiates a processing workflow that transcribes the audio and assigns speaker roles. The retrieval process validates file existence and handles potential errors such as missing files or processing failures.

The integration between the database and object storage ensures that metadata about files is consistently maintained. The system queries the PostgreSQL database to retrieve transcription records and related metadata, while simultaneously checking MinIO for the physical availability of the audio files.

```mermaid
sequenceDiagram
participant User as "User"
participant Interface as "File Browser Interface"
participant Storage as "MinIO Storage"
participant Database as "PostgreSQL"
User->>Interface : Request file list
Interface->>Interface : Determine storage category
Interface->>Interface : Scan storage directory
Interface->>User : Display file list with actions
User->>Interface : Select audio file
Interface->>Interface : Start processing animation
Interface->>Storage : Check file availability
alt File exists
Storage-->>Interface : Confirm availability
Interface->>Database : Query transcription metadata
Database-->>Interface : Return metadata
Interface->>Interface : Process audio (transcribe + assign roles)
Interface->>User : Display processed transcript
else File missing
Storage-->>Interface : File not found
Interface->>User : Display error message
end
```

**Diagram sources**
- [handlers.py](file://src/handlers.py#L150-L180)
- [storage.py](file://src/storage.py#L150-L200)
- [db.py](file://src/db_handler/db.py#L300-L350)

**Section sources**
- [handlers.py](file://src/handlers.py#L150-L200)
- [storage.py](file://src/storage.py#L150-L250)

## Delete Workflow

The delete workflow in VoxPersona implements a comprehensive cascading removal process that ensures data consistency across the system. When a user requests to delete a file, the system first validates the file's existence and then proceeds with removal operations.

The deletion process removes the physical file from the storage directory and triggers cascading removal of related records from the database. This includes deleting transcription records, associated audit reports, and any generated embeddings. The workflow includes confirmation prompts to prevent accidental deletions, ensuring users explicitly confirm their intent before permanent removal.

The system handles potential errors during deletion, such as file system permissions issues or database constraint violations, and provides appropriate feedback to the user. After successful deletion, the file browser interface is automatically refreshed to reflect the updated file list.

```mermaid
flowchart TD
A([User selects Delete]) --> B{File exists?}
B --> |Yes| C["Show confirmation prompt"]
C --> D{User confirms?}
D --> |Yes| E["Remove physical file"]
E --> F["Delete transcription record"]
F --> G["Remove related audit reports"]
G --> H["Delete embeddings"]
H --> I["Refresh file list"]
I --> J([Operation complete])
D --> |No| K([Cancel operation])
B --> |No| L["Show error: File not found"]
L --> M([Return to file list])
style E fill:#f9f,stroke:#333
style F fill:#f9f,stroke:#333
style G fill:#f9f,stroke:#333
style H fill:#f9f,stroke:#333
```

**Diagram sources**
- [handlers.py](file://src/handlers.py#L182-L195)
- [storage.py](file://src/storage.py#L130-L140)
- [db.py](file://src/db_handler/db.py#L200-L250)

**Section sources**
- [handlers.py](file://src/handlers.py#L182-L195)
- [storage.py](file://src/storage.py#L130-L140)

## Upload Process

The upload process for new audio files in VoxPersona includes comprehensive validation and automatic initiation of the analysis pipeline. When a user selects the upload option, the system prompts them to send an audio file, which is then subjected to format and size validation.

The validation process checks both the file format and size against predefined limits, rejecting files that exceed the maximum size of 2GB. For valid files, the system automatically saves them to the appropriate storage directory and immediately restarts the analysis pipeline, which includes transcription and speaker role assignment.

The upload workflow handles various file types, including voice messages, audio files, and document-attached audio, extracting appropriate metadata from each. After successful upload and validation, the system provides confirmation to the user and makes the file available in the file browser for immediate analysis.

```mermaid
sequenceDiagram
participant User as "User"
participant System as "VoxPersona System"
participant MinIO as "MinIO Storage"
participant Analysis as "Analysis Pipeline"
User->>System : Select upload option
System->>User : Prompt to send audio file
User->>System : Send audio file
System->>System : Validate format and size
alt Valid file
System->>System : Extract metadata
System->>MinIO : Save file to storage
MinIO-->>System : Confirmation
System->>Analysis : Start analysis pipeline
Analysis->>Analysis : Transcribe audio
Analysis->>Analysis : Assign speaker roles
Analysis-->>System : Processing complete
System->>User : Confirm successful upload and processing
else Invalid file
System->>User : Reject with error message
end
```

**Diagram sources**
- [handlers.py](file://src/handlers.py#L400-L450)
- [audio_utils.py](file://src/audio_utils.py#L30-L50)
- [config.py](file://src/config.py#L70-L80)

**Section sources**
- [handlers.py](file://src/handlers.py#L400-L450)
- [audio_utils.py](file://src/audio_utils.py#L30-L50)

## Synchronization and Caching

VoxPersona maintains strict synchronization between database entries and object storage to ensure data consistency. When files are uploaded, modified, or deleted, corresponding database records are updated to reflect the current state of the object storage. This bidirectional synchronization prevents data discrepancies and ensures that the file browser interface always displays accurate information.

The system implements a `processed_texts` cache to improve performance by storing recently processed transcripts in memory. This cache reduces the need for repeated processing of the same audio files, significantly improving response times for frequently accessed files. The cache is managed through a dictionary structure keyed by user chat ID, allowing personalized access to processed content.

The synchronization mechanism includes error handling for cases where database updates fail, ensuring that partial updates do not leave the system in an inconsistent state. Transactional operations are used where appropriate to maintain atomicity of related operations.

```mermaid
classDiagram
class StorageSynchronizer {
+synchronize_file_state()
+update_database_metadata()
+validate_storage_consistency()
+handle_sync_errors()
}
class ProcessedTextsCache {
-cache : dict[int, str]
+get(chat_id : int) str
+set(chat_id : int, text : str)
+clear(chat_id : int)
+clear_all()
}
class FileMetadata {
+file_name : str
+file_size : int
+upload_date : datetime
+transcription_id : int
+status : str
}
StorageSynchronizer --> FileMetadata : "manages"
StorageSynchronizer --> ProcessedTextsCache : "updates"
ProcessedTextsCache ..> StorageSynchronizer : "notifies"
FileMetadata ..> StorageSynchronizer : "provides"
```

**Diagram sources**
- [storage.py](file://src/storage.py#L50-L100)
- [config.py](file://src/config.py#L85-L90)
- [db.py](file://src/db_handler/db.py#L100-L150)

**Section sources**
- [storage.py](file://src/storage.py#L50-L150)
- [config.py](file://src/config.py#L85-L90)

## Real-World Usage Patterns

In real-world usage, VoxPersona's file management capabilities support several common patterns. Users frequently reprocess updated recordings when they need to refine analysis results or apply different processing parameters. The system's caching mechanism makes reprocessing efficient by avoiding redundant transcription operations.

Another common pattern involves cleaning up old files to manage storage quotas and maintain a focused dataset. Users typically review their file lists periodically and remove recordings that are no longer needed for analysis. The cascading delete functionality ensures that removing a file also removes all associated analysis results, maintaining data integrity.

Users also leverage the upload functionality to continuously add new recordings to their analysis pipeline. The automatic processing that follows upload allows for immediate analysis without additional user intervention, supporting a workflow of continuous data ingestion and analysis.

```mermaid
flowchart LR
A[Reprocess Recordings] --> B["Select existing audio file"]
B --> C["Modify processing parameters"]
C --> D["Initiate reprocessing"]
D --> E["Receive updated transcript"]
F[Clean Up Files] --> G["Review file list"]
G --> H["Identify obsolete files"]
H --> I["Confirm deletion"]
I --> J["System removes file and related data"]
K[Add New Recordings] --> L["Upload new audio file"]
L --> M["System validates and stores file"]
M --> N["Automatic analysis pipeline starts"]
N --> O["Results available for analysis"]
style A fill:#bbf,stroke:#333
style F fill:#bbf,stroke:#333
style K fill:#bbf,stroke:#333
```

**Diagram sources**
- [handlers.py](file://src/handlers.py#L150-L200)
- [storage.py](file://src/storage.py#L150-L200)
- [analysis.py](file://src/analysis.py#L1-L20)

**Section sources**
- [handlers.py](file://src/handlers.py#L150-L200)
- [storage.py](file://src/storage.py#L150-L200)

## Error Handling and Storage Management

The file management system in VoxPersona includes comprehensive error handling for various failure scenarios. For failed deletions, the system logs the error condition and provides user feedback while attempting to maintain system stability. Corrupted uploads are detected through validation checks and rejected before they can affect system integrity.

Storage quota management is implemented through size limits on uploaded files (2GB maximum) and monitoring of storage directory usage. When storage limits are approached, the system can trigger alerts or automated cleanup processes. The error handling framework includes specific handlers for common issues such as network connectivity problems with MinIO, database connection failures, and file system permission errors.

The system logs all error conditions for diagnostic purposes and provides meaningful error messages to users without exposing sensitive system information. Recovery procedures are designed to return the system to a stable state, allowing users to retry operations after addressing the underlying issue.

```mermaid
flowchart TD
A[Error Detection] --> B{Error Type}
B --> C["File System Errors"]
B --> D["Database Errors"]
B --> E["Network Errors"]
B --> F["Validation Errors"]
C --> G["Log error details"]
G --> H["Notify user"]
H --> I["Maintain system state"]
D --> J["Log error details"]
J --> K["Notify user"]
K --> L["Maintain system state"]
E --> M["Log error details"]
M --> N["Notify user"]
N --> O["Maintain system state"]
F --> P["Log error details"]
P --> Q["Notify user with guidance"]
Q --> R["Reject operation"]
style C fill:#f96,stroke:#333
style D fill:#f96,stroke:#333
style E fill:#f96,stroke:#333
style F fill:#f96,stroke:#333
```

**Diagram sources**
- [handlers.py](file://src/handlers.py#L50-L100)
- [storage.py](file://src/storage.py#L200-L250)
- [db.py](file://src/db_handler/db.py#L350-L400)

**Section sources**
- [handlers.py](file://src/handlers.py#L50-L100)
- [storage.py](file://src/storage.py#L200-L250)