# Assessment of Interview Methodology

<cite>
**Referenced Files in This Document**   
- [bot.py](file://src/bot.py#L290-L319)
- [interview_methodology.txt](file://prompts/interview_methodology.txt#L53-L66)
- [промпт оценка методологии интервью.txt](file://prompts-by-scenario/interview/Assessment-of-the-interview-methodology/non-building/промпт оценка методологии интервью.txt#L77-L97)
- [Интервью. Оценка методологии интервью. Итоговая оценка качества интервью.txt](file://prompts-by-scenario/interview/Assessment-of-the-interview-methodology/json-prompt/Интервью. Оценка методологии интервью. Итоговая оценка качества интервью.txt#L0-L18)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Interview Methodology Assessment Overview](#interview-methodology-assessment-overview)
3. [Prompt Design and Output Formats](#prompt-design-and-output-formats)
4. [LLM Integration and Processing Pipeline](#llm-integration-and-processing-pipeline)
5. [Scoring Mechanism and Quality Calculation](#scoring-mechanism-and-quality-calculation)
6. [RAG System Integration](#rag-system-integration)
7. [Code Implementation and Error Handling](#code-implementation-and-error-handling)
8. [Common Issues and Tuning Guidance](#common-issues-and-tuning-guidance)
9. [Customization and Extension Points](#customization-and-extension-points)

## Introduction
The Interview Methodology Assessment module evaluates the quality and structure of employee-conducted interviews using AI-driven analysis. This system leverages Large Language Models (LLMs), specifically Anthropic Claude, to assess adherence to best practices in questioning techniques, interviewer behavior, and overall interview flow. The assessment is based on predefined methodological rules and scoring rubrics, with results structured for both human readability and automated processing. This document details the architecture, implementation, and operational mechanics of this sub-feature.

**Section sources**
- [bot.py](file://src/bot.py#L290-L319)
- [interview_methodology.txt](file://prompts/interview_methodology.txt#L53-L66)

## Interview Methodology Assessment Overview
The Interview Methodology Assessment evaluates how well an interview adheres to established qualitative research standards. It focuses on two primary dimensions: compliance with procedural rules and avoidance of methodological violations. The system analyzes transcripts where speaker roles are marked as [Employee:] and [Client:], assessing key aspects such as introduction clarity, empathetic engagement, question formulation, depth of inquiry, sequential logic, attention to transformational events, handling of causal linkages ("links"), and topic focus.

The assessment process generates a structured evaluation that includes percentage-based scores for each criterion, supported by direct quotes from the transcript. These scores are aggregated into two main components:
- **X%**: Average score for rule compliance
- **Y%**: Average score for absence of methodological violations

These values are used to compute the final quality metric.

**Section sources**
- [промпт оценка методологии интервью.txt](file://prompts-by-scenario/interview/Assessment-of-the-interview-methodology/non-building/промпт оценка методологии интервью.txt#L77-L97)

## Prompt Design and Output Formats
The system employs two distinct prompt variants to serve different analytical needs:

### JSON-Formatted Prompt
Located at `prompts-by-scenario/interview/Assessment-of-the-interview-methodology/json-prompt/Интервью. Оценка методологии интервью. Итоговая оценка качества интервью.txt`, this prompt instructs the LLM to extract the final interview quality score in JSON format. The expected output structure is:
```json
{
  "итоговая_оценка_качества_интервью": число
}
```
This format enables automated parsing and integration into downstream systems, ensuring structured data flow.

### Plain Text Analysis Prompt
The file `prompts-by-scenario/interview/Assessment-of-the-interview-methodology/non-building/промпт оценка методологии интервью.txt` contains the full analytical template. It defines a comprehensive evaluation framework with specific sections:
- Rule adherence (presentation, empathy, question format)
- Identification of methodological violations (depth, sequence, transformation events, link collection, topic drift)
- Final conclusion including the computed Z% score

Each section requires evidence-based scoring between 0–100%, with justification drawn directly from the interview transcript.

**Section sources**
- [Интервью. Оценка методологии интервью. Итоговая оценка качества интервью.txt](file://prompts-by-scenario/interview/Assessment-of-the-interview-methodology/json-prompt/Интервью. Оценка методологии интервью. Итоговая оценка качества интервью.txt#L0-L18)
- [промпт оценка методологии интервью.txt](file://prompts-by-scenario/interview/Assessment-of-the-interview-methodology/non-building/промпт оценка методологии интервью.txt#L0-L97)

## LLM Integration and Processing Pipeline
The system integrates with the LLM pipeline through the `vsegpt_complete()` function, which sends prompts to Anthropic Claude. The workflow begins in `src/bot.py` with the `analyze_interview_methodology()` function:

```python
def analyze_interview_methodology(text: str) -> str:
    base_ = load_prompt("interview_methodology.txt")
    if not base_:
        base_ = "Проанализируй методологию интервью."
    p = f"{base_}\n\nТекст:\n{text}"
    return vsegpt_complete(p, "Ошибка методологии интервью")
```

This function:
1. Loads the base prompt from `interview_methodology.txt`
2. Appends the interview transcript
3. Invokes the LLM via `vsegpt_complete()`
4. Returns the raw response

The context window is managed by truncating or summarizing long transcripts when necessary, though the current implementation assumes transcripts fit within the model’s token limits. Response parsing differs based on the prompt type:
- For JSON prompts, the output is parsed using standard JSON libraries
- For plain text, post-processing extracts scores and conclusions using pattern matching

**Section sources**
- [bot.py](file://src/bot.py#L290-L319)
- [interview_methodology.txt](file://prompts/interview_methodology.txt)

## Scoring Mechanism and Quality Calculation
The final interview quality score (Z%) is calculated using a precise formula defined in the prompt:
```
Z = (X + Y) / 2
```
Where:
- **X%** = Average of rule compliance scores (presentation, empathy, question format)
- **Y%** = Average of violation absence scores (depth, sequence, transformation focus, link quality, topic focus)

For example:
- If X = 85% and Y = 75%, then Z = (85 + 75) / 2 = 80%

The `Интервью. Оценка методологии интервью. Итоговая оценка качества интервью.txt` prompt is specifically designed to extract only the numerical value of Z% in JSON format, enabling seamless integration into scoring dashboards or databases.

**Section sources**
- [промпт оценка методологии интервью.txt](file://prompts-by-scenario/interview/Assessment-of-the-interview-methodology/non-building/промпт оценка методологии интервью.txt#L77-L97)
- [Интервью. Оценка методологии интервью. Итоговая оценка качества интервью.txt](file://prompts-by-scenario/interview/Assessment-of-the-interview-methodology/json-prompt/Интервью. Оценка методологии интервью. Итоговая оценка качества интервью.txt#L0-L18)

## RAG System Integration
The module interacts with a Retrieval-Augmented Generation (RAG) system to enhance evaluation consistency and benchmarking. Historical assessments are retrieved from a vector database using the `rag_persistence.py` module. When evaluating a new interview, the system:
1. Embeds the current transcript
2. Queries for similar past interviews
3. Retrieves previous assessments and scores
4. Presents them as context to the LLM

This allows the model to compare the current interview against prior evaluations, ensuring scoring consistency over time and providing richer feedback based on organizational benchmarks.

**Section sources**
- [rag_persistence.py](file://src/rag_persistence.py)

## Code Implementation and Error Handling
The core logic resides in `src/bot.py`, where the `analyze_interview_methodology()` function orchestrates the analysis. Key implementation details include:
- Prompt loading with fallback defaults
- Text concatenation and formatting
- LLM invocation with error labeling
- Logging for debugging

Error handling is minimal but effective:
- If the prompt file is missing, a default instruction is used
- Failed LLM calls return an error label ("Ошибка методологии интервью")
- No retry logic is implemented, assuming reliable LLM service

For malformed responses (e.g., invalid JSON), the system would require additional validation in the calling context, which is not shown in the current codebase.

**Section sources**
- [bot.py](file://src/bot.py#L290-L319)

## Common Issues and Tuning Guidance
Common challenges in this module include:
- **Inconsistent scoring**: Different LLM responses may apply rubrics unevenly
- **Ambiguous criteria**: Terms like "transformational event" require clear definitions
- **Context overflow**: Long transcripts may exceed token limits

To address these:
- Fine-tune prompts with annotated examples
- Include explicit definitions within the prompt (e.g., defining "transformational event")
- Implement transcript chunking and summarization for long inputs
- Use temperature=0 for deterministic outputs

Regular calibration with human-reviewed samples ensures scoring reliability.

**Section sources**
- [промпт оценка методологии интервью.txt](file://prompts-by-scenario/interview/Assessment-of-the-interview-methodology/non-building/промпт оценка методологии интервью.txt)

## Customization and Extension Points
The system supports several customization points:
- **Scoring rubrics**: Modify weightings or add new criteria in the prompt
- **Evaluation dimensions**: Extend the assessment to include new aspects (e.g., cultural sensitivity)
- **Output formats**: Add new JSON schemas for different consumers
- **Domain adaptation**: Adjust language and examples for specific industries (hotel, restaurant, spa)

Changes are made directly in the prompt files under `prompts-by-scenario/interview/Assessment-of-the-interview-methodology/`. The modular design allows updates without code changes, enabling non-technical users to refine the evaluation framework.

**Section sources**
- [промпт оценка методологии интервью.txt](file://prompts-by-scenario/interview/Assessment-of-the-interview-methodology/non-building/промпт оценка методологии интервью.txt)