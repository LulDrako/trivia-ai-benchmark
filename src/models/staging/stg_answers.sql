-- Llama was run once at temperature 0. The Qwen file already stores temperature.
SELECT
    question_id,
    model_name,
    prompt_id,
    0.0 AS temperature,
    prompt_text,
    correct_letter,
    ai_answer,
    ai_correct,
    response_time
FROM {{ source('silver', 'answers_llama') }}

UNION ALL

SELECT
    question_id,
    model_name,
    prompt_id,
    temperature,
    prompt_text,
    correct_letter,
    ai_answer,
    ai_correct,
    response_time
FROM {{ source('silver', 'answers_qwen') }}
