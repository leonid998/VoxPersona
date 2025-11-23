import io
import threading
from asyncio import BoundedSemaphore
import asyncio
import aiohttp
import queue
import time
import logging
from openai import OpenAI
import anthropic
from pydub import AudioSegment
import json
import re
from anthropic import RateLimitError
from typing import Any
from langchain_community.vectorstores import FAISS

from config import OPENAI_API_KEY, OPENAI_BASE_URL, ANTHROPIC_API_KEY, TRANSCRIPTION_MODEL_NAME, REPORT_MODEL_NAME
from constants import CLAUDE_ERROR_MESSAGE
from db_handler.db import fetch_prompt_by_name
from utils import count_tokens

def analyze_methodology(text: str, prompt_list: list[tuple[str, int]]) -> str | None:
    """
    Последовательно отправляет промпты из списка в модель.
    Если в списке несколько элементов, то ответ от предыдущего промпта
    передается как вход для следующего.

    :param prompt_list: Список кортежей вида (prompt, order)
    :return: Финальный ответ модели после обработки всех промптов
    """
    current_response = None

    for prompt, _ in prompt_list:
        if current_response == CLAUDE_ERROR_MESSAGE:
            raise ValueError(f"{CLAUDE_ERROR_MESSAGE}")
        if current_response is None:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"{prompt}\n\nВот документ аудита, на основе которого нужно сделать заключение:\n{text}"
                        }
                    ]
                }
            ]
            current_response = send_msg_to_model(messages=messages)
        else:
            combined_prompt = f"{prompt}\n\nТекст:{current_response}"
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": combined_prompt
                        }
                    ]
                }
            ]
            current_response = send_msg_to_model(messages=messages)
    return current_response if current_response != CLAUDE_ERROR_MESSAGE else None

def transcribe_audio_raw(
    file_path: str,
    model_name: str | None = TRANSCRIPTION_MODEL_NAME,
    api_key: str | None = OPENAI_API_KEY,
    base_url: str | None = OPENAI_BASE_URL,
    chunk_length_ms: int =3 * 60_000,  # 3 минуты
) -> str:
    """
    Разбивает аудиофайл на чанки по chunk_length_ms, конвертирует каждый в MP3, отправляет в OpenAI Whisper,
    возвращает объединённый текст.
    """

    try:
        # Загружаем исходное аудио (любого поддерживаемого формата)
        sound = AudioSegment.from_file(file_path)
        duration_ms = len(sound)
        out_texts = []

        client = OpenAI(api_key=api_key or "", base_url=base_url)

        start_ms = 0
        end_ms = chunk_length_ms

        while start_ms < duration_ms:
            chunk = sound[start_ms:end_ms]
            start_ms = end_ms
            end_ms += chunk_length_ms

            # Конвертируем чанк в MP3
            chunk_io = io.BytesIO()
            chunk.export(chunk_io, format="mp3")
            chunk_io.seek(0)
            chunk_io.name = "chunk.mp3"

            try:
                # Отправляем MP3 на транскрипцию
                response = client.audio.transcriptions.create(
                    model=model_name or "whisper-1",
                    file=chunk_io
                )
                text_part = response.text
            except Exception as e:
                logging.error(f"Ошибка транскрибирования чанка: {e}")
                text_part = ""

            out_texts.append(text_part)

        return " ".join(out_texts).strip()

    except Exception as e:
        logging.error(f"Ошибка при обработке аудио: {e}")
        return ""

def transcribe_audio(path_: str) -> str:
    return transcribe_audio_raw(path_)

def aggregate_citations(text: str, citations: str, aggregation_prompt: str):
    try:
        citations_text = "\n\n".join(citations)
        aggregation_result = send_msg_to_model(system=aggregation_prompt, messages=[{"role": "user", "content": f"Вопрос пользователя: {text}\n\nЦитаты:\n{citations_text}"}])
        aggregation_result = aggregation_result.strip()
        return aggregation_result
    except Exception as e:
        logging.error(f"Ошибка при агрегации цитат: {str(e)}")
        return "Произошла ошибка при агрегации цитат."

def extract_from_chunk(text: str, chunk: str, extract_prompt: str) -> str:
    try:
        extract_result = send_msg_to_model(system=extract_prompt, messages=[{"role": "user", "content": f"Документ:\n{chunk}\n\n{text}"}])
        logging.info(f"Результат извлечения: {extract_result}")
        extract_result = extract_result.strip()
        return extract_result
    except Exception as e:
        logging.error(f"Ошибка при извлечении из чанка: {str(e)}")
        logging.error(f"Ошибка при извлечении из чанка: {str(e)}")
        return "##not_found##"

def generate_db_answer(query: str,
                       db_index: FAISS, # векторная база знаний
                       k: int=30,      # используемое к-во чанков
                       verbose: bool=True, # выводить ли на экран выбранные чанки
                       model: str | None=REPORT_MODEL_NAME
                       ):
    system_prompt = """Перед тобой отчеты из бд. Это малая часть отчетов, которые подобраны при помощи поиска по релевантности
    из большого набора отчетов. Пользователем задан вопрос. Тебе нужно как можно
    более четко и понятно ответить на данный вопрос. Если в данных тебе отчетах
    ты не видишь ответ на вопрос пользователя, именно так и скажи - не надо
    ничего придумывать от себя. В ответ не включай ссылки на отчеты и фразы клиентов."""

    similar_documents = db_index.similarity_search(query, k=k)
    message_content = re.sub(r'\n{2}', ' ', '\n '.join(
        [f'Отчет № {i+1}:\n' + doc.page_content
        for i, doc in enumerate(similar_documents)]))

    # Подсчитываем токены для системного промпта
    system_tokens = count_tokens(system_prompt)

    # Подсчитываем токены для найденных документов
    docs_tokens = count_tokens(message_content)

    # Подсчитываем токены для запроса пользователя
    query_tokens = count_tokens(query)

    # Общее количество токенов
    total_tokens = system_tokens + docs_tokens + query_tokens

    if verbose:
        logging.info("\nНайденные релевантные отчеты:")
        logging.info("-"*100)
        logging.info(message_content) # печатать на экран выбранные чанки
        logging.info("-"*100)
        logging.info(f"Токены системного промпта: {system_tokens}")
        logging.info(f"Токены найденных документов: {docs_tokens}")
        logging.info(f"Токены запроса пользователя: {query_tokens}")
        logging.info(f"Общее количество токенов, отправляемых в модель: {total_tokens}")
        logging.info("-"*100)

    messages = [{"role": "user", "content": f'Вопрос пользователя: {query}'}]

    # Используется актуальная модель Claude Sonnet 4.5 (fallback если model/REPORT_MODEL_NAME не заданы)
    response = send_msg_to_model(messages=messages, model=model or REPORT_MODEL_NAME or "claude-haiku-4-5-20251001", system=f'{system_prompt} Вот наиболее релевантные отчеты из бд: \n{message_content}')
    return response

async def send_msg_to_model_async(
    session: aiohttp.ClientSession,
    messages: list[dict[str, Any]],
    system: str,
    model: str,
    api_key: str,
    err: str = CLAUDE_ERROR_MESSAGE,
    max_tokens: int = 20000,
    max_retries: int = 5
):
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    data = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages
    }

    backoff = 1
    for _ in range(1, max_retries + 1):
        try:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["content"][0]["text"]
                elif response.status in [429, 529]:
                    logging.warning(f"[{err}] Получен статус {response.status}, ждём {backoff}s перед повтором...")
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    text = await response.text()
                    logging.error(f"[{err}] Ошибка {response.status}: {text}")
                    return f"[ERROR] {response.status}: {text}"
        except Exception as e:
            logging.exception(f"[{err}] Исключение при запросе: {e}")
            await asyncio.sleep(backoff)
            backoff *= 2

    return f"[ERROR] Превышено число попыток ({max_retries})"


def _calculate_rate_limits():
    """Вычисляет лимиты скорости для токенов и запросов."""
    token_limits_per_min = [80000, 20000, 20000, 20000, 20000, 20000, 20000]
    req_limits_per_min =   [2000,    50,    50,    50,    50,    50,    50]

    token_rates = [tl / 60.0 for tl in token_limits_per_min]
    req_rates = [rl / 60.0 for rl in req_limits_per_min]

    return token_rates, req_rates

def _calculate_delay(tokens: int, token_rate: float, req_rate: float) -> float:
    """Вычисляет задержку на основе токенов и лимитов скорости."""
    req_delay = 1.0 / req_rate if req_rate > 0 else float("inf")
    token_delay = tokens / token_rate if token_rate > 0 else float("inf")
    return max(token_delay, req_delay)

async def _process_single_chunk_async(
    q: asyncio.Queue[tuple[int, str]],
    text: str,
    extract_prompt: str,
    model_idx: int,
    api_key: str,
    token_rate: float,
    req_rate: float,
    model_semaphore: BoundedSemaphore,
    session: aiohttp.ClientSession,
    results: list[str | None]
):
    """Обрабатывает один чанк асинхронно."""
    while True:
        try:
            idx, chunk = q.get_nowait()
        except asyncio.QueueEmpty:
            break

        user_content = f"Документ:\n{chunk}\n\n{text}"
        tokens = count_tokens(user_content)
        delay = _calculate_delay(tokens, token_rate, req_rate)

        logging.info(
            f"[Model#{model_idx}] Чанк #{idx}: {tokens} токенов → "
            f"delay={delay:.1f}s"
        )

        async with model_semaphore:
            await asyncio.sleep(delay)

        messages = [{"role": "user", "content": user_content}]
        response = await send_msg_to_model_async(
            session=session,
            messages=messages,
            system=extract_prompt,
            model=REPORT_MODEL_NAME or "claude-haiku-4-5-20251001",  # Исправлено: актуальная модель Claude Sonnet 4.5
            api_key=api_key,
            err=f"Ошибка при извлечении чанка #{idx}"
        )

        results[idx] = response
        q.task_done()

async def extract_from_chunk_parallel_async(
    text: str,
    chunks: list[str],
    extract_prompt: str,
    api_keys: list[str],
    session: aiohttp.ClientSession
) -> list[str | None]:
    """
    Асинхронная обработка чанков с контролем RPM и TPM.
    Чанки равномерно распределяются между моделями через очередь.
    """
    token_rates, req_rates = _calculate_rate_limits()

    q = asyncio.Queue()
    for idx, chunk in enumerate(chunks):
        await q.put((idx, chunk))

    results: list[str | None] = [None] * len(chunks)
    model_semaphores = [BoundedSemaphore(1) for _ in range(len(api_keys))]

    workers = [
        asyncio.create_task(_process_single_chunk_async(
            q, text, extract_prompt, model_idx, api_key,
            token_rates[model_idx], req_rates[model_idx],
            model_semaphores[model_idx], session, results
        ))
        for model_idx, api_key in enumerate(api_keys)
    ]

    await q.join()

    for task in workers:
        _ = task.cancel()

    return results

def _process_single_chunk_sync(
    q: queue.Queue[tuple[int, str]],
    text: str,
    extract_prompt: str,
    model_idx: int,
    api_key: str,
    token_rate: float,
    req_rate: float,
    results: list[str | None]
):
    """Обрабатывает один чанк синхронно."""
    req_delay = 1.0 / req_rate if req_rate > 0 else 0.0

    while True:
        try:
            idx, chunk = q.get_nowait()
        except queue.Empty:
            break

        user_content = f"Документ:\n{chunk}\n\n{text}"
        tokens = count_tokens(user_content)
        token_delay = tokens / token_rate if token_rate > 0 else 0.0
        delay = max(token_delay, req_delay)

        logging.info(
            f"[Model#{model_idx}] Чанк #{idx}: {tokens} токенов, "
            f"token_rate={token_rate:.1f} tok/s → delay_tok={token_delay:.1f}s, "
            f"req_rate={req_rate:.2f} req/s → delay_req={req_delay:.1f}s, "
            f"sleep={delay:.1f}s"
        )

        resp = send_msg_to_model(
            messages=[{"role": "user", "content": user_content}],
            system=extract_prompt,
            err=f"Ошибка при извлечении чанка #{idx}",
            model=REPORT_MODEL_NAME or "claude-haiku-4-5-20251001",  # Исправлено: актуальная модель Claude Sonnet 4.5
            api_key=api_key
        )
        results[idx] = resp

        if delay:
            time.sleep(delay)

        q.task_done()

def extract_from_chunk_parallel(
    text: str,
    chunks: list[str],
    extract_prompt: str,
    api_keys: list[str]
) -> list[str | None]:
    """
    Параллельно обрабатываем чанки тремя моделями, учитывая:
      - модель 0: 80k токенов/мин (≈1333 ток/сек), 2k запросов/мин (≈33,3 req/сек)
      - модель 1: 20k токенов/мин (≈333 ток/сек), 50 запросов/мин (≈0,83 req/сек)
      - модель 2: как модель 1

    Для каждого чанка вычисляем токен-задержку и запрос-задержку, берём max.
    """
    token_rates, req_rates = _calculate_rate_limits()

    q: queue.Queue[tuple[int, str]] = queue.Queue()
    for idx, chunk in enumerate(chunks):
        q.put((idx, chunk))

    results: list[str | None] = [None] * len(chunks)

    threads = []
    for m in range(len(api_keys)):
        if not q.empty():
            t = threading.Thread(
                target=_process_single_chunk_sync,
                args=(q, text, extract_prompt, m, api_keys[m],
                      token_rates[m], req_rates[m], results),
                daemon=True
            )
            threads.append(t)
            t.start()

    q.join()
    for t in threads:
        t.join()

    return results

def classify_report_type(text: str, prompt_name: str) -> int | None:
    classification_prompt: str = fetch_prompt_by_name(prompt_name=prompt_name)
    classification_result = send_msg_to_model(system=classification_prompt, messages=[{"role": "user", "content": text}], max_tokens=1000)
    classification_result = classification_result.strip()
    try:
        for char in classification_result:
            if char.isdigit():
                subcategory = int(char)
                return subcategory
        logging.error(f"Не удалось найти номер подкатегории в ответе: {classification_result}")
        return None
    except ValueError as e:
        logging.error(f"Ошибка при преобразовании ответа в число: {e}. Ответ: {classification_result}")
        return None

def classify_query(text: str) -> str:
    classification_prompt: str = fetch_prompt_by_name(prompt_name="prompt_classify")
    classification_result = send_msg_to_model(system=classification_prompt, messages=[{"role": "user", "content": text}])
    classification_result = classification_result.strip()
    try:
        result_json = json.loads(classification_result)
        return result_json.get("category", "Не определено")
    except json.JSONDecodeError:
        logging.error(f"Ошибка парсинга JSON ответа классификатора: {classification_result}")
        return "Не определено"
    except Exception as e:
        logging.error(f"Ошибка при классификации запроса: {str(e)}")
        return "Не определено"

def send_msg_to_model(
        messages: list[dict[str, Any]],
        system: str | None = None,
        err: str=CLAUDE_ERROR_MESSAGE,
        max_tokens: int=20000,
        model: str | None=REPORT_MODEL_NAME,
        api_key: str | None=ANTHROPIC_API_KEY,
        return_usage: bool = False
        ) -> str | tuple[str, dict[str, int]]:
    """
    Отправляет сообщения в модель Claude API.

    Args:
        messages: Список сообщений для отправки
        system: Системный промпт (опционально)
        err: Сообщение об ошибке при неудаче
        max_tokens: Максимальное количество токенов в ответе
        model: Название модели Claude
        api_key: API ключ Anthropic
        return_usage: Если True, возвращает tuple (text, usage_dict)
                     где usage_dict = {"input_tokens": N, "output_tokens": N}

    Returns:
        str: Текст ответа модели (если return_usage=False)
        tuple[str, dict]: (текст, {"input_tokens": N, "output_tokens": N}) (если return_usage=True)
    """
    client = anthropic.Anthropic(api_key=api_key or "")

    # Fallback на актуальную модель Claude Sonnet 4.5 если model не задана
    # Исправлено: ранее использовалась несуществующая модель claude-sonnet-4-20250514
    if model is None:
        model = "claude-haiku-4-5-20251001"


    model_args = {
    "model": model,
    "max_tokens": max_tokens,
    "temperature": 0.1,
    "messages": messages
    }

    if system:
        model_args["system"] = system

    backoff = 1
    while True:
        try:
            response = client.messages.create(**model_args)
            text = response.content[0].text

            # Извлечение информации о использовании токенов
            if return_usage:
                usage = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                }
                return (text, usage)

            return text
        except RateLimitError as e:
            if backoff > 16:
                logging.exception(f"Rate limit persists after backoff: {e}")
                raise
            logging.warning(f"Rate limit hit, ожидаем {backoff}s перед повтором...")
            time.sleep(backoff)
            backoff *= 2
        except Exception as e:
            logging.exception(f"{err}: {e}")
            if return_usage:
                return (err, {"input_tokens": 0, "output_tokens": 0})
            return err

def auto_detect_category(text: str) -> str:
    """
    Пример простой эвристики для определения типа заведения.
    """
    lw = text.lower()
    if "ресторан" in lw or "restaurant" in lw:
        return "restaurant"
    elif "центр здоровья" in lw or "health" in lw:
        return "health_center"
    elif "отель" in lw or "hotel" in lw:
        return "hotel"
    return "hotel"

def assign_roles(text: str) -> str:
    logging.info(f"[assign_roles] Длина исходного текста: {len(text)} символов.")
    prompt_roles: str = fetch_prompt_by_name(prompt_name="assign_roles")
    messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"{prompt_roles}\n\nТекст:\n{text}"
                        }
                    ]
                }
            ]
    result = send_msg_to_model(messages=messages, err="Ошибка assign_roles")
    logging.info(f"[assign_roles] Длина результата: {len(result)} символов.")
    return result
