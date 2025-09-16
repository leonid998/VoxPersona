# Spa Audit Compliance

<cite>
**Referenced Files in This Document**   
- [src/run_analysis.py](file://src/run_analysis.py#L1-L344)
- [src/analysis.py](file://src/analysis.py#L1-L491)
- [prompts-by-scenario/design/Information-on-compliance-with-the-audit-program/spa/part1/промпт дизайн спа.txt](file://prompts-by-scenario/design/Information-on-compliance-with-the-audit-program/spa/part1/промпт дизайн спа.txt#L0-L81)
- [prompts-by-scenario/design/Information-on-compliance-with-the-audit-program/spa/json-prompt/Дизайн. Соответствие программе аудита. СПА. Json.txt](file://prompts-by-scenario/design/Information-on-compliance-with-the-audit-program/spa/json-prompt/Дизайн. Соответствие программе аудита. СПА. Json.txt#L0-L41)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Spa Audit Compliance Overview](#spa-audit-compliance-overview)
3. [Core Prompt Structure and Domain-Specific Compliance](#core-prompt-structure-and-domain-specific-compliance)
4. [JSON Schema for Standardized Output](#json-schema-for-standardized-output)
5. [RAG Pipeline Integration in Analysis](#rag-pipeline-integration-in-analysis)
6. [Process for Integrating New Compliance Requirements](#process-for-integrating-new-compliance-requirements)
7. [Common Issues and Resolution Strategies](#common-issues-and-resolution-strategies)
8. [Conclusion](#conclusion)

## Introduction
This document provides a comprehensive analysis of the Spa Audit Compliance sub-feature within the VoxPersona system. The feature is designed to evaluate adherence to wellness and safety standards in spa and health center facilities through structured audits. The analysis focuses on how the system captures domain-specific compliance factors, standardizes output via JSON schema, leverages retrieval-augmented generation (RAG) for regulatory knowledge enrichment, and supports adaptability to evolving industry standards.

## Spa Audit Compliance Overview
The Spa Audit Compliance functionality assesses design and operational aspects of wellness centers against a defined methodology. It ensures that spa environments meet criteria related to psychological comfort, ecological materials, sensory perception, and alignment with the facility’s health philosophy. The system does not evaluate medical equipment or HVAC systems but emphasizes design elements that contribute to a restorative atmosphere.

The audit process is guided by two primary files:
- A detailed evaluation prompt (`промпт дизайн спа.txt`) that defines the analytical framework.
- A JSON extraction prompt (`Дизайн. Соответствие программе аудита. СПА. Json.txt`) that standardizes quantitative output.

These components work in tandem to produce structured, actionable insights from unstructured audit reports.

**Section sources**
- [prompts-by-scenario/design/Information-on-compliance-with-the-audit-program/spa/part1/промпт дизайн спа.txt](file://prompts-by-scenario/design/Information-on-compliance-with-the-audit-program/spa/part1/промпт дизайн спа.txt#L0-L81)
- [prompts-by-scenario/design/Information-on-compliance-with-the-audit-program/spa/json-prompt/Дизайн. Соответствие программе аудита. СПА. Json.txt](file://prompts-by-scenario/design/Information-on-compliance-with-the-audit-program/spa/json-prompt/Дизайн. Соответствие программе аудита. СПА. Json.txt#L0-L41)

## Core Prompt Structure and Domain-Specific Compliance
The core prompt in `промпт дизайн спа.txt` establishes a rigorous methodology for evaluating spa design audits. It requires the AI to act as a specialized expert in health center design assessment, ensuring deep semantic analysis of audit documents.

Key compliance domains evaluated include:

### Preparation Phase Assessment
- **Concept and positioning analysis**: Evaluation of the spa’s philosophy, mission, target audience, and wellness programs.
- **Location and environment review**: Assessment of site location, views, and ecological factors.
- **Evaluation criteria definition**: Verification that clear, health-centered criteria (e.g., healing alignment, psychological comfort, eco-friendliness) are established.

### Exterior Audit
- **Outdoor space evaluation**: Inspection of landscaping, outdoor amenities, and parking organization.
- **Facade analysis**: Review of architectural style, materials, and entrance design.

### Interior Audit
- **Entry zone and reception**: First impressions, reception layout, and wayfinding.
- **Public areas**: Corridors, lounges, and restrooms.
- **Functional zones**: Treatment rooms, group exercise studios, meditation spaces.

### Design Solution Analysis
- **Layout planning**: Functional zoning, traffic flow, and ergonomics.
- **Stylistic coherence**: Overall style, color schemes, and material choices.
- **Lighting design**: Natural light utilization, accent lighting, and lighting scenarios.
- **Acoustic comfort**: Sound insulation, noise control, and background music.

### Atmosphere Evaluation
- **Sensory perception**: Visual comfort, tactile experiences, and aromatic design.
- **Psychological well-being**: Privacy levels, color psychology, and stress-reducing elements.

### Reporting Quality
- **Conceptual alignment**: Identification of strengths, problem areas, and development potential.
- **Actionable recommendations**: Concrete, implementable improvement suggestions.
- **Implementation roadmap**: Prioritized changes, phased rollout, and resource estimates.

Each domain is scored on a percentage scale (0–100%) based on completeness and depth of analysis, with final ratings aggregated into an overall audit quality score.

**Section sources**
- [prompts-by-scenario/design/Information-on-compliance-with-the-audit-program/spa/part1/промпт дизайн спа.txt](file://prompts-by-scenario/design/Information-on-compliance-with-the-audit-program/spa/part1/промпт дизайн спа.txt#L0-L81)

## JSON Schema for Standardized Output
The JSON schema defined in `Дизайн. Соответствие программе аудита. СПА. Json.txt` enables reliable data extraction and reporting by structuring quantitative outputs. This schema specifies the exact metrics to be extracted from qualitative audit evaluations.

The schema includes the following fields:
```json
{
  "оценка_соответствия_методологии_подготовительный_анализ": null,
  "оценка_соответствия_методологии_аудит_экстерьера": null,
  "оценка_соответствия_методологии_аудит_интерьера": null,
  "оценка_соответствия_методологии_анализ_дизайн_решений": null,
  "оценка_соответствия_методологии_оценка_атмосферы": null,
  "оценка_соответствия_методологии_формирование_отчета": null,
  "общая_оценка_соответствия_методологии": null,
  "итоговая_оценка_качества_аудита": null
}
```

These fields capture:
- **Preparatory analysis compliance**
- **Exterior audit compliance**
- **Interior audit compliance**
- **Design solution analysis compliance**
- **Atmosphere evaluation compliance**
- **Reporting structure compliance**
- **Overall methodology compliance**
- **Final audit quality score**

The system extracts only numeric values (without % symbols), returning `null` if a metric is missing. This ensures consistent, machine-readable output suitable for dashboards, trend analysis, and automated reporting.

**Section sources**
- [prompts-by-scenario/design/Information-on-compliance-with-the-audit-program/spa/json-prompt/Дизайн. Соответствие программе аудита. СПА. Json.txt](file://prompts-by-scenario/design/Information-on-compliance-with-the-audit-program/spa/json-prompt/Дизайн. Соответствие программе аудита. СПА. Json.txt#L0-L41)

## RAG Pipeline Integration in Analysis
The system leverages a Retrieval-Augmented Generation (RAG) pipeline implemented in `src/run_analysis.py` to enrich audit analysis with spa-specific regulatory and best practice knowledge.

### RAG Initialization
The `init_rags()` function initializes multiple knowledge bases:
```python
def init_rags(existing_rags: dict | None = None) -> dict:
    rags = existing_rags.copy() if existing_rags else {}
    rag_configs = [
        ("Интервью", None, None),
        ("Дизайн", None, None),
        ("Интервью", "Оценка методологии интервью", None),
        ("Интервью", "Отчет о связках", None),
        ("Интервью", "Общие факторы", None),
        ("Интервью", "Факторы в этом заведении", None),
        ("Дизайн", "Оценка методологии аудита", None),
        ("Дизайн", "Соответствие программе аудита", None),
        ("Дизайн", "Структурированный отчет аудита", None),
    ]
```

For spa audits, the `"Дизайн"` and `"Соответствие программе аудита"` configurations are particularly relevant, creating in-memory vector databases from grouped reports.

### Knowledge Retrieval
During analysis, the system uses `generate_db_answer()` to retrieve relevant context:
```python
def generate_db_answer(query: str, db_index, k: int=15):
    similar_documents = db_index.similarity_search(query, k=k)
    message_content = '\n '.join([f'Отчет № {i+1}:\n' + doc.page_content for i, doc in enumerate(similar_documents)])
    response = send_msg_to_model(messages=[{"role": "user", "content": f'Вопрос пользователя: {query}'}], system=f'{system_prompt} Вот наиболее релевантные отчеты из бд: \n{message_content}')
    return response
```

This allows the model to ground its evaluations in real-world examples and historical audit data, improving accuracy and consistency.

**Section sources**
- [src/run_analysis.py](file://src/run_analysis.py#L1-L344)
- [src/analysis.py](file://src/analysis.py#L1-L491)

## Process for Integrating New Compliance Requirements
The system supports adaptation to evolving industry standards through modular prompt management and dynamic RAG indexing.

### Prompt-Based Updates
New compliance criteria can be integrated by:
1. Updating the core evaluation prompt (`промпт дизайн спа.txt`) with additional assessment dimensions.
2. Adding corresponding fields to the JSON schema prompt if quantitative tracking is required.
3. Deploying updated prompts via the database (managed by `fetch_prompts_for_scenario_reporttype_building`).

### Dynamic Knowledge Base Updates
The RAG system automatically incorporates new audit reports into its knowledge base through:
- `build_reports_grouped()`: Aggregates reports by scenario and type.
- `create_db_in_memory()`: Constructs vector databases from textual content.
- Periodic reinitialization of RAG instances to reflect updated data.

This enables the system to learn from recent audits and apply current best practices without code changes.

### Workflow Example
When a new wellness regulation is introduced:
1. The prompt is updated to include the new requirement.
2. Historical audits are reprocessed or new audits are conducted.
3. The RAG index is rebuilt, incorporating the updated methodology.
4. Future analyses automatically reflect the new standard.

**Section sources**
- [src/run_analysis.py](file://src/run_analysis.py#L1-L344)
- [src/analysis.py](file://src/analysis.py#L1-L491)

## Common Issues and Resolution Strategies
Despite its robust design, the system may encounter challenges in audit consistency and evidence quality.

### Issue 1: Inconsistent Terminology in Responses
**Symptom**: Variability in how compliance domains are described across audits.  
**Root Cause**: Lack of standardized vocabulary in the prompt or model drift.  
**Solution**: 
- Refine the prompt with explicit definitions for key terms (e.g., "psychological comfort").
- Use the RAG system to anchor responses in consistent terminology from high-quality historical audits.

### Issue 2: Lack of Verifiable Evidence
**Symptom**: Audit conclusions lack specific citations or examples.  
**Root Cause**: Model generates plausible but unsupported assertions.  
**Solution**:
- Strengthen the prompt to require evidence-based reasoning (e.g., "cite specific observations").
- Implement multi-step analysis using `analyze_methodology()` with chained prompts to separate observation from evaluation.

### Issue 3: Superficial Analysis
**Symptom**: High-level summaries without deep domain insight.  
**Root Cause**: Insufficient context or overly broad prompts.  
**Solution**:
- Break down the audit into sequential phases (e.g., exterior, interior, atmosphere) using multi-part prompts.
- Use the `run_analysis_pass()` function to chain specialized evaluations.

### Issue 4: Prompt Iteration and Context Refinement
To continuously improve audit quality:
- Monitor output for recurring gaps using the JSON extraction schema.
- Conduct A/B testing with revised prompts.
- Update the RAG knowledge base with exemplar audits that demonstrate desired analysis depth.

**Section sources**
- [src/run_analysis.py](file://src/run_analysis.py#L1-L344)
- [src/analysis.py](file://src/analysis.py#L1-L491)

## Conclusion
The Spa Audit Compliance sub-feature provides a structured, scalable framework for evaluating wellness facility design against industry standards. By combining a detailed domain-specific prompt, standardized JSON output, and a RAG-enhanced analysis pipeline, the system ensures consistent, evidence-based, and actionable audit results.

Key strengths include:
- Comprehensive coverage of spa-specific compliance factors.
- Machine-readable output for reliable reporting.
- Adaptive knowledge base that evolves with industry standards.
- Modular architecture enabling continuous improvement.

Future enhancements could include automated anomaly detection in audit scores, integration with facility management systems, and multilingual support for global spa chains.