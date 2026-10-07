SELECT
    a.question_id,
    q.category,
    q.type,
    q.difficulty,
    q.question,
    a.model_name,
    a.prompt_id,
    a.temperature,
    a.correct_letter,
    a.ai_answer,
    a.ai_correct,
    a.response_time
FROM {{ ref('stg_answers') }} a
JOIN {{ ref('stg_questions') }} q
  ON a.question_id = q.question_id
