# User Workflows

<cite>
**Referenced Files in This Document**   
- [handlers.py](file://src/handlers.py)
- [run_analysis.py](file://src/run_analysis.py)
- [menus.py](file://src/menus.py)
- [markups.py](file://src/markups.py)
- [audio_utils.py](file://src/audio_utils.py)
- [analysis.py](file://src/analysis.py)
- [datamodels.py](file://src/datamodels.py)
- [config.py](file://src/config.py)
</cite>

## Table of Contents
1. [Audio Analysis Workflow](#audio-analysis-workflow)
2. [Search Workflow](#search-workflow)
3. [State Management](#state-management)
4. [User Interface Components](#user-interface-components)
5. [Backend Integration](#backend-integration)
6. [Real-World Examples](#real-world-examples)

## Audio Analysis Workflow

The audio analysis workflow in VoxPersona begins when a user uploads a voice message via Telegram. The system processes the audio through a series of steps: transcription, speaker role assignment, metadata input, and report generation.

When a user sends a voice message, the `handle_audio_msg` function in `handlers.py` is triggered. This function first validates the user's authorization status and checks the audio file size against the maximum limit of 2GB. Upon passing validation, the audio file is downloaded to a temporary directory and uploaded to MinIO for persistent storage.

The transcription process is handled by `transcribe_audio_and_save` in `audio_utils.py`, which calls the Whisper API to convert speech to text. The raw transcription is stored in the `processed_texts` dictionary, indexed by the user's chat ID. This enables subsequent processing steps to access the transcribed content.

Following transcription, the system automatically assigns speaker roles using the `assign_roles` function from `analysis.py`. This function sends the raw transcript to an LLM with a prompt that instructs it to identify and label segments as either [Сотрудник:] (Employee) or [Клиент:] (Client). The role-assigned text replaces the raw transcription in `processed_texts`.

After audio processing, the system transitions to metadata collection. The user state is updated to "inputing_fields", prompting the user to enter the audio file number. Subsequent inputs collect additional metadata including date, employee name, establishment name, building type, zone, and city (for design scenarios). For interview scenarios, the client's name is also collected.

The metadata collection follows a sequential state machine pattern where each input advances the user to the next required field. The collected data is stored in the `user_states` dictionary under the "data" key for the corresponding chat ID.

Once all metadata is collected, the user can generate reports by selecting from available options in the interview or design menu. The report generation process retrieves the appropriate prompts based on the selected scenario, building type, and report type, then processes the role-assigned transcript through the analysis pipeline.

**Section sources**
- [handlers.py](file://src/handlers.py#L400-L799)
- [audio_utils.py](file://src/audio_utils.py#L30-L49)
- [analysis.py](file://src/analysis.py#L450-L490)
- [config.py](file://src/config.py#L70-L75)

## Search Workflow

The search workflow in VoxPersona provides users with two distinct modes for querying the knowledge base: fast (RAG-based) search and deep (parallel LLM) search. Users access this functionality through the "Режим диалога" (Dialog Mode) option in the main menu.

When a user selects dialog mode, the system sets their state to "dialog_mode" and presents a menu with a toggle for deep search. The `make_dialog_markup` function in `markups.py` generates this interface, displaying "🔍 Глубокое исследование" (Deep Research) when disabled and "✅ Глубокое исследование" when enabled.

In fast search mode, the system uses a Retrieval-Augmented Generation (RAG) approach. When the user submits a query, `run_dialog_mode` in `run_analysis.py` classifies the query to determine whether it pertains to "Интервью" (Interview) or "Дизайн" (Design) scenarios. The system then retrieves relevant documents from the vector database using similarity search and generates a response based on these retrieved documents.

The deep search mode employs a more comprehensive analysis using multiple LLM instances in parallel. When enabled, `run_deep_search` processes the query by distributing the workload across multiple Anthropic API keys. The system splits the knowledge base into chunks and processes them simultaneously, aggregating the results to provide a comprehensive answer.

The parallel processing in deep search is managed by `extract_from_chunk_parallel_async`, which implements rate limiting to prevent API throttling. Each API key has defined token and request rate limits that are respected during processing. The results from individual chunks are aggregated using a dedicated prompt to create a cohesive final response.

Both search modes provide real-time feedback through a loading animation while processing. The system uses a threading event and spinner animation to indicate ongoing processing, updating the message with the final result once complete. The response is split into chunks of 4096 characters to comply with Telegram's message length limits.

**Section sources**
- [handlers.py](file://src/handlers.py#L200-L250)
- [run_analysis.py](file://src/run_analysis.py#L100-L200)
- [markups.py](file://src/markups.py#L100-L120)
- [utils.py](file://src/utils.py#L70-L90)

## State Management

State management in VoxPersona is implemented through the `user_states` dictionary in `config.py`, which tracks the current workflow state for each user session. This state object contains several key properties that control the application flow.

The primary state variable is "step", which determines the current phase of interaction. Initial steps include "ask_audio_number", "ask_date", "ask_employee", and other data collection states. As users progress through the workflow, the step value updates accordingly, guiding the system's response to subsequent inputs.

For metadata editing, the system uses a temporary "previous_step" field to store the original state before entering edit mode. When a user selects "✏️ Изменить" (Edit) from the confirmation menu, the system sets the step to "edit_fieldname" and stores the prior step. After editing, it returns to the previous step, maintaining workflow continuity.

Dialog mode maintains its own state with the "deep_search" boolean flag. This persists the user's preference for deep search across multiple queries. The `handle_toggle_deep` function toggles this state and updates the interface to reflect the current mode.

The state also includes a "mode" field that distinguishes between "interview" and "design" scenarios. This affects the available report types and the required metadata fields. For example, design scenarios require city information, while interview scenarios require client name.

Critical state transitions occur during report generation. When a report requires building type information, the system may set a "pending_report" field to store the intended report while collecting the missing building type. After selection, it retrieves this pending report and proceeds with analysis.

The system ensures state consistency by validating required data before proceeding. The `check_valid_data` function verifies that essential fields are present before initiating analysis. If validation fails, the system prompts the user to restart the process.

**Section sources**
- [handlers.py](file://src/handlers.py#L100-L300)
- [config.py](file://src/config.py#L85-L90)
- [validators.py](file://src/validators.py#L1-L50)

## User Interface Components

The user interface in VoxPersona is constructed using Telegram inline keyboards generated by functions in `markups.py`. These dynamic menus guide users through workflows and provide access to system functionality.

The main menu, created by `main_menu_markup`, presents three primary options: "📁 Хранилище" (Storage), "Режим диалога" (Dialog Mode), and "❓ Помощь" (Help). This serves as the central navigation hub throughout the application.

The storage menu, generated by `storage_menu_markup`, allows users to view and manage audio files. It provides options to view files, upload new files, and navigate back to the main menu. The file listing interface includes action buttons for each file: an open button to process the file and a delete button (❌) for removal.

During metadata collection, the system uses `confirm_menu_markup` to display a summary of entered information before finalizing. This confirmation interface includes "✅ Подтвердить" (Confirm) and "✏️ Изменить" (Edit) buttons, allowing users to review and correct their inputs.

The edit menu, created by `edit_menu_markup`, presents a list of editable fields based on the current scenario. Each field has a corresponding button that initiates editing mode. The menu dynamically adjusts its content based on whether the current mode is interview or design, showing "ФИО Клиента" (Client Name) for interviews and "Город" (City) for design scenarios.

Report selection menus differ between scenarios. The `interview_menu_markup` provides five report options including methodology assessment, decision links, general factors, specific factors, and employee performance analysis. The `design_menu_markup` offers three options: audit methodology, compliance assessment, and structured audit reporting.

Building type selection is handled by `building_type_menu_markup`, which presents buttons for "Отель" (Hotel), "Ресторан" (Restaurant), and "Центр здоровья" (Health Center). Each button includes a callback data payload that identifies the selected building type.

All menus are managed through the `active_menus` dictionary in `config.py`, which tracks message IDs for dynamic cleanup. The `clear_active_menus` function removes previous menu messages to prevent interface clutter, ensuring users always interact with the current state.

**Section sources**
- [markups.py](file://src/markups.py#L1-L100)
- [menus.py](file://src/menus.py#L1-L50)
- [config.py](file://src/config.py#L85-L90)

## Backend Integration

Backend integration in VoxPersona connects the Telegram interface with analysis capabilities through the `run_analysis.py` module. This integration orchestrates the workflow from user input to final report generation.

The primary integration point is `run_analysis_with_spinner`, which coordinates the analysis process while providing visual feedback. This function first validates that processed text exists for the user, then determines the appropriate scenario (interview or design) based on the callback data.

Prompt retrieval is managed by `fetch_prompts_for_scenario_reporttype_building` in the database handler. This function queries the database for prompts matching the selected scenario, report type, and building type. Prompts are organized in the `prompts-by-scenario` directory structure, with JSON prompts separated from regular prompts.

For reports requiring multiple processing steps, such as "Общие факторы" (General Factors), the system executes sequential analysis passes. The first pass processes part 1 prompts, the second pass handles part 2 prompts, and a final JSON pass aggregates the results. Each pass runs with a loading spinner to indicate progress.

The analysis execution is handled by `run_analysis_pass`, which manages the LLM interaction. This function sends the source text and prompts to the LLM, handles API errors, and ensures proper cleanup of the loading message. Successful analyses are saved to the database via `save_user_input_to_db`.

Database integration includes both prompt retrieval and result storage. The system uses a structured database schema to organize prompts by scenario, report type, and building type. Generated reports are stored with metadata including transcript, scenario, user data, label, and audit text.

External service integration includes MinIO for audio storage, OpenAI for transcription, and Anthropic for analysis. The configuration in `config.py` centralizes API keys and connection parameters, with separate settings for test and production environments.

The RAG system initialization in `init_rags` builds vector databases from grouped reports, creating searchable knowledge bases for both interview and design scenarios. These RAGs are updated when new reports are generated, maintaining an up-to-date knowledge base for search functionality.

**Section sources**
- [run_analysis.py](file://src/run_analysis.py#L1-L100)
- [analysis.py](file://src/analysis.py#L1-L100)
- [db_handler/db.py](file://src/db_handler/db.py#L1-L50)
- [config.py](file://src/config.py#L50-L85)

## Real-World Examples

Real-world interactions with VoxPersona demonstrate the seamless integration of its workflows. A typical audio analysis session begins when a user uploads a voice message from a client interview at a hotel.

After automatic transcription and role assignment, the user enters metadata: audio number "12345", date "2025-01-15", employee name "Иван Петров", establishment "Grand Plaza Hotel", building type "Отель", zone "лобби", and client name "Анна Смирнова". The system confirms these details and presents the interview report menu.

Selecting "Общие факторы" triggers a multi-stage analysis. The system first processes part 1 prompts to identify general decision-making factors, then processes part 2 prompts to uncover unstudied factors. Finally, it runs a JSON analysis to quantify the findings, producing a structured report on common factors influencing customer decisions.

In a search workflow example, a user enters dialog mode and enables deep search before asking, "Какие факторы влияют на выбор отеля?" (What factors influence hotel selection?). The system classifies this as a design scenario and conducts a comprehensive analysis across multiple report chunks.

The deep search distributes the query across seven Anthropic API instances, processing different segments of the knowledge base in parallel. Each instance analyzes relevant audit reports, extracting insights about hotel selection factors. The results are aggregated into a cohesive response that identifies key factors such as location, room quality, service standards, and price-value ratio.

Another example involves a user who needs to correct metadata. After reviewing the confirmation screen, they select "✏️ Изменить" and then "Город" to change the location from "Москва" to "Санкт-Петербург". The system temporarily stores the previous state, collects the new city name, and returns to the confirmation screen with updated information.

These examples illustrate how VoxPersona's state management, interface design, and backend integration work together to support complex analysis workflows. The system maintains context throughout multi-step processes, provides clear feedback at each stage, and delivers comprehensive analytical results.

**Section sources**
- [handlers.py](file://src/handlers.py#L300-L400)
- [run_analysis.py](file://src/run_analysis.py#L200-L300)
- [menus.py](file://src/menus.py#L50-L90)
- [markups.py](file://src/markups.py#L100-L130)