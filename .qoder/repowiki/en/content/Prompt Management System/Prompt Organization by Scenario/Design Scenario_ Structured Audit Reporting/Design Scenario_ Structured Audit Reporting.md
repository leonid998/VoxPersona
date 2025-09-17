# Design Scenario: Structured Audit Reporting

<cite>
**Referenced Files in This Document**   
- [run_analysis.py](file://src/run_analysis.py)
- [analysis.py](file://src/analysis.py)
- [datamodels.py](file://src/datamodels.py)
- [Дизайн. Структ отчет отель. Подсчет пунктов информации. json.txt](file://prompts-by-scenario/design/Structured-information-on-the-audit-program/hotel/json-prompt/Дизайн. Структ отчет отель. Подсчет пунктов информации. json.txt)
- [аудит отель структ 1.txt](file://prompts-by-scenario/design/Structured-information-on-the-audit-program/hotel/part1/аудит отель структ 1.txt)
- [аудит отель структ ч2.txt](file://prompts-by-scenario/design/Structured-information-on-the-audit-program/hotel/part2/аудит отель структ ч2.txt)
- [аудит отель структ all.txt](file://prompts-by-scenario/design/Structured-information-on-the-audit-program/hotel/part3/аудит отель структ all.txt)
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
The Structured Audit Reporting feature enables comprehensive, multi-stage analysis of audit data for hotels, restaurants, and spas. This system leverages a chained prompt pipeline to generate itemized reports with precise information point counting. The architecture supports different processing structures: a three-part sequence for hotels and a two-part flow for restaurants and spas. Each stage processes raw transcription data into increasingly refined outputs, culminating in structured JSON reports suitable for downstream processing and RAG indexing. The orchestration is managed by `run_analysis.py`, which coordinates prompt execution, state management, and result aggregation while handling errors and maintaining consistency across report sections.

## Project Structure
The project organizes its components into distinct directories: `prompts` for base templates, `prompts-by-scenario` for scenario-specific prompt variations, and `src` for core application logic. The structured audit reporting functionality resides primarily in the `design/Structured-information-on-the-audit-program` subdirectory, with separate configurations for hotel, restaurant, and spa audits. Each building type has its own prompt sequence, with hotels using three sequential parts and restaurants/spas using two. The JSON schema prompts are stored in dedicated `json-prompt` subdirectories to standardize output formatting.

```mermaid
graph TD
Prompts[Prompts Directory] --> Design[Design Scenario]
Prompts --> Interview[Interview Scenario]
Design --> StructuredAudit[Structured-information-on-the-audit-program]
StructuredAudit --> Hotel[Hotel]
StructuredAudit --> Restaurant[Restaurant]
StructuredAudit --> Spa[Spa]
Hotel --> Part1[part1]
Hotel --> Part2[part2]
Hotel --> Part3[part3]
Hotel --> JsonPrompt[json-prompt]
Restaurant --> RPart1[RPart1]
Restaurant --> RPart2[RPart2]
Restaurant --> RJsonPrompt[RJsonPrompt]
Spa --> SPart1[SPart1]
Spa --> SPart2[Spart2]
Spa --> SJsonPrompt[SJsonPrompt]
Src[Source Code] --> RunAnalysis[run_analysis.py]
Src --> Analysis[analysis.py]
Src --> DataModels[datamodels.py]
RunAnalysis --> PromptExecution[Orchestrates Prompt Execution]
Analysis --> Methodology[analyze_methodology]
DataModels --> Mappings[Report Type Mappings]
```

**Diagram sources**
- [prompts-by-scenario/design/Structured-information-on-the-audit-program](file://prompts-by-scenario/design/Structured-information-on-the-audit-program)
- [src/run_analysis.py](file://src/run_analysis.py)

**Section sources**
- [prompts-by-scenario/design/Structured-information-on-the-audit-program](file://prompts-by-scenario/design/Structured-information-on-the-audit-program)
- [src/run_analysis.py](file://src/run_analysis.py)

## Core Components
The Structured Audit Reporting system consists of several key components that work together to transform raw transcription data into structured reports. The core functionality is implemented in `run_analysis.py`, which orchestrates the multi-stage analysis pipeline. The `analyze_methodology` function in `analysis.py` handles the sequential execution of prompts, chaining outputs from one stage to the next. The system uses a sophisticated state management approach to maintain context between prompt stages, ensuring consistency across the final report. The JSON schema defined in the json-prompt files enables standardized output formatting for downstream processing and RAG indexing.

**Section sources**
- [src/run_analysis.py](file://src/run_analysis.py#L1-L343)
- [src/analysis.py](file://src/analysis.py#L1-L490)
- [src/datamodels.py](file://src/datamodels.py#L1-L71)

## Architecture Overview
The Structured Audit Reporting architecture follows a multi-stage processing pipeline where each stage refines the output of the previous one. For hotels, the process involves three distinct prompt stages followed by a JSON formatting step. Restaurants and spas follow a similar but shorter two-stage process. The system uses a chaining mechanism where the output of one prompt becomes the input to the next, allowing for progressive refinement of the audit report. The final stage applies a JSON schema to structure the output for consistent downstream consumption.

```mermaid
graph TD
RawText[Raw Transcription Text] --> Part1["Part 1 Analysis<br/>(Initial Processing)"]
Part1 --> Part2["Part 2 Analysis<br/>(Secondary Processing)"]
Part2 --> Part3["Part 3 Analysis<br/>(Final Processing)<br/>Hotel Only"]
Part3 --> JsonStage["JSON Structuring<br/>(Information Point Counting)"]
Part2 --> JsonStageRest["JSON Structuring<br/>(Information Point Counting)<br/>Restaurant/Spa"]
style Part3 stroke:#0066cc,stroke-width:2px
style JsonStage stroke:#0066cc,stroke-width:2px
style JsonStageRest stroke:#0066cc,stroke-width:2px
subgraph "Hotel Processing"
Part1
Part2
Part3
end
subgraph "Restaurant/Spa Processing"
Part1
Part2
end
subgraph "Common Final Stage"
JsonStage
JsonStageRest
end
```

**Diagram sources**
- [src/run_analysis.py](file://src/run_analysis.py#L200-L300)
- [analysis.py](file://src/analysis.py#L1-L50)

## Detailed Component Analysis

### Structured Audit Pipeline
The structured audit reporting system implements a multi-part prompt chain that progressively transforms raw transcription data into comprehensive audit reports. For hotels, the process follows a three-part structure where each stage builds upon the previous output. Restaurants and spas use a two-part structure, reflecting differences in audit complexity and scope. The system maintains state between stages by passing the output of one prompt as input to the next, creating a coherent narrative throughout the report.

#### For Pipeline Components:
```mermaid
sequenceDiagram
participant User as "User"
participant RunAnalysis as "run_analysis_with_spinner"
participant Analyze as "analyze_methodology"
participant LLM as "LLM Service"
User->>RunAnalysis : Initiate Audit Analysis
RunAnalysis->>Analyze : Execute Part 1 Prompt
Analyze->>LLM : Send Prompt + Raw Text
LLM-->>Analyze : Return Part 1 Results
Analyze->>RunAnalysis : Pass Results
RunAnalysis->>Analyze : Execute Part 2 Prompt
Analyze->>LLM : Send Prompt + Part 1 Results
LLM-->>Analyze : Return Part 2 Results
Analyze->>RunAnalysis : Pass Results
alt Hotel Processing
RunAnalysis->>Analyze : Execute Part 3 Prompt
Analyze->>LLM : Send Prompt + Part 2 Results
LLM-->>Analyze : Return Part 3 Results
Analyze->>RunAnalysis : Pass Results
end
RunAnalysis->>Analyze : Execute JSON Prompt
Analyze->>LLM : Send JSON Prompt + Final Results
LLM-->>Analyze : Return Structured JSON
Analyze->>RunAnalysis : Pass JSON Output
RunAnalysis->>User : Deliver Final Report
```

**Diagram sources**
- [src/run_analysis.py](file://src/run_analysis.py#L200-L300)
- [src/analysis.py](file://src/analysis.py#L1-L50)

### JSON Schema and Structured Output
The system employs a standardized JSON schema to ensure consistent output formatting across all audit reports. This schema defines the structure for the final report, including the count of information points. The JSON formatting stage is critical for enabling downstream processing and RAG indexing, as it transforms free-form text into structured data that can be easily queried and analyzed. The schema is implemented in prompt files located in the `json-prompt` subdirectories for each building type.

#### For Structured Output Components:
```mermaid
classDiagram
class JsonSchema {
+int общее_количество_пунктов_информации
+validate_structure()
+count_information_points()
+generate_standardized_output()
}
class PromptProcessor {
-List[String] prompts
-String current_response
+analyze_methodology(text, prompt_list)
+chain_prompt_outputs()
+maintain_state_between_stages()
}
class ReportAggregator {
+aggregate_results()
+ensure_consistency_across_sections()
+handle_intermediate_failures()
+manage_token_budget()
}
PromptProcessor --> JsonSchema : "formats output"
ReportAggregator --> PromptProcessor : "orchestrates"
JsonSchema <|-- HotelJsonSchema : "extends"
JsonSchema <|-- RestaurantJsonSchema : "extends"
JsonSchema <|-- SpaJsonSchema : "extends"
```

**Diagram sources**
- [Дизайн. Структ отчет отель. Подсчет пунктов информации. json.txt](file://prompts-by-scenario/design/Structured-information-on-the-audit-program/hotel/json-prompt/Дизайн. Структ отчет отель. Подсчет пунктов информации. json.txt)
- [src/analysis.py](file://src/analysis.py#L1-L50)

**Section sources**
- [Дизайн. Структ отчет отель. Подсчет пунктов информации. json.txt](file://prompts-by-scenario/design/Structured-information-on-the-audit-program/hotel/json-prompt/Дизайн. Структ отчет отель. Подсчет пунктов информации. json.txt)
- [src/analysis.py](file://src/analysis.py#L1-L50)

## Dependency Analysis
The Structured Audit Reporting feature depends on several core modules that work together to process audit data. The `run_analysis.py` module orchestrates the entire process, calling functions from `analysis.py` to execute prompts and manage state. The `datamodels.py` file provides essential mappings that translate between internal codes and human-readable report types. The prompt files in the `prompts-by-scenario` directory contain the actual instructions sent to the LLM, organized by scenario, report type, and building category.

```mermaid
graph TD
RunAnalysis[src/run_analysis.py] --> Analysis[src/analysis.py]
RunAnalysis --> DataModels[src/datamodels.py]
RunAnalysis --> Db[src/db_handler/db.py]
Analysis --> OpenAI[OpenAI API]
Analysis --> Anthropic[Anthropic API]
Analysis --> Utils[src/utils.py]
DataModels --> Constants[Report Type Mappings]
DataModels --> BuildingTypes[Building Type Mappings]
RunAnalysis --> Prompts[prompts-by-scenario/]
Analysis --> Prompts[prompts-by-scenario/]
style RunAnalysis fill:#f9f,stroke:#333
style Analysis fill:#bbf,stroke:#333
style DataModels fill:#f96,stroke:#333
```

**Diagram sources**
- [src/run_analysis.py](file://src/run_analysis.py#L1-L343)
- [src/analysis.py](file://src/analysis.py#L1-L490)
- [src/datamodels.py](file://src/datamodels.py#L1-L71)

**Section sources**
- [src/run_analysis.py](file://src/run_analysis.py#L1-L343)
- [src/analysis.py](file://src/analysis.py#L1-L490)
- [src/datamodels.py](file://src/datamodels.py#L1-L71)

## Performance Considerations
The multi-stage LLM call architecture presents several performance considerations, particularly regarding token budget management and processing latency. Each prompt stage consumes tokens from the model's context window, requiring careful management to avoid exceeding limits. The system implements rate limiting and retry logic to handle API rate limits gracefully. For large transcriptions, the system may need to process content in chunks, which adds complexity to maintaining coherence across the final report. The asynchronous processing capabilities in `extract_from_chunk_parallel_async` help mitigate some performance bottlenecks by distributing work across multiple API keys.

**Section sources**
- [src/analysis.py](file://src/analysis.py#L300-L400)
- [src/run_analysis.py](file://src/run_analysis.py#L100-L150)

## Troubleshooting Guide
When intermediate steps fail in the structured audit reporting pipeline, the system implements several error handling strategies. The `run_analysis_pass` function includes comprehensive exception handling for API errors, including rate limit retries with exponential backoff. If a prompt stage fails, the system logs the error and attempts to continue with subsequent stages when possible. To maintain consistency across report sections, the system validates the output format at each stage and applies default values when necessary. Token budget management is critical, and the system monitors token usage to prevent exceeding model limits.

**Section sources**
- [src/run_analysis.py](file://src/run_analysis.py#L50-L100)
- [src/analysis.py](file://src/analysis.py#L400-L450)

## Conclusion
The Structured Audit Reporting feature provides a robust framework for generating comprehensive, itemized audit reports for hotels, restaurants, and spas. By implementing a multi-stage prompt pipeline with specialized processing flows for different building types, the system delivers detailed analysis while maintaining consistency and structure. The integration of JSON schema formatting enables downstream processing and RAG indexing, making the reports valuable for both human review and automated analysis. The architecture balances complexity with reliability through careful state management, error handling, and performance optimization.