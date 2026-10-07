SELECT
    question_id,
    category,
    type,
    difficulty,
    question,
    correct_answer,
    incorrect_answers
FROM {{ source('silver', 'questions') }}
