SELECT
    model_name,
    temperature,
    ai_correct,
    COUNT(*) AS n_questions,
    ROUND(AVG(response_time), 3) AS avg_response_time_s,
    ROUND(MIN(response_time), 3) AS min_response_time_s,
    ROUND(MAX(response_time), 3) AS max_response_time_s
FROM {{ ref('int_benchmark_results') }}
GROUP BY model_name, temperature, ai_correct
ORDER BY model_name, temperature, ai_correct
