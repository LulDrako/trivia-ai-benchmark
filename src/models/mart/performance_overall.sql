SELECT
    model_name,
    temperature,
    COUNT(*) AS n_questions,
    SUM(CASE WHEN ai_correct THEN 1 ELSE 0 END) AS n_correct,
    ROUND(100.0 * AVG(CASE WHEN ai_correct THEN 1.0 ELSE 0.0 END), 1) AS accuracy_pct,
    ROUND(AVG(response_time), 3) AS avg_response_time_s
FROM {{ ref('int_benchmark_results') }}
GROUP BY model_name, temperature
ORDER BY model_name, temperature
