# trivia-ai-benchmark

Benchmark de modèles d'IA sur les questions de culture générale d'OpenTDB.

## Bronze

`src/scrape_opentdb.py` interroge l'API OpenTDB et écrit `bronze/questions_raw.csv`.

OpenTDB renvoie au plus 50 questions par appel, et n'accepte qu'un appel toutes les 5 secondes. Le script attend entre chaque appel. Un token de session évite de recevoir deux fois la même question. Quand l'API répond avec le code 4, tout le jeu disponible a été récupéré.

Le CSV garde le texte tel que l'API le renvoie (entités HTML comprises). Les mauvaises réponses sont stockées en JSON dans la colonne `incorrect_answers`.

La collecte s'est arrêtée au code 4, avec **5250 questions** écrites. L'API en annonçait **5299** vérifiées. L'écart de 49 vient des coupures réseau : un appel a pu être compté côté OpenTDB sans que la réponse soit écrite dans le CSV. Le jeton a ensuite indiqué qu'il ne restait plus de question nouvelle.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/scrape_opentdb.py
```

Si le script s'arrête, relance la même commande : il reprend grâce à `bronze/session.json`. Pour tout recommencer : `python src/scrape_opentdb.py --reset`.

## Silver questions

`src/build_silver_questions.py` lit le bronze et écrit `silver/questions.parquet`. Une ligne = une question. Le CSV bronze n'est pas modifié.

Le script décode les entités HTML (`&quot;` devient `"`, `&#039;` devient `'`), uniformise `type` et `difficulty` en minuscules, et ajoute `question_id`. Cet identifiant est un hash des champs bruts : relancer le script redonne le même id pour la même question. Il n'y a pas encore de réponse de modèle.

```bash
python src/build_silver_questions.py
```

## Pourquoi pas tout en CSV

Le sujet fixe trois formats. On ne choisit pas le Parquet à la place du CSV pour tout le projet.

- Le bronze est un CSV, `questions_raw.csv`. C'est le brut : du texte, une ligne par question. On peut l'ouvrir et vérifier le scrape. On ne le modifie plus.
- Le silver est en Parquet, parce que le sujet le demande pour les données nettoyées et les réponses des modèles. Le fichier porte déjà les noms de colonnes et leurs types. DuckDB l'ouvre comme une table, sans deviner si une colonne est du texte ou une liste. Ce sera la source de dbt. Pour 5250 lignes, un CSV aurait été lisible aussi. Le gain n'est pas la vitesse. C'est que dbt et DuckDB lisent le schéma tel qu'il est écrit.
- Le gold sera une base DuckDB, pas un Parquet. Ce ne sont plus les questions, ce sont les chiffres du rapport. dbt les construit.

`profiles.yml`, `dbt_project.yml` et les modèles SQL viennent après l'enrichissement, quand le silver contient aussi `ai_answer`, `ai_correct` et `response_time`. Les écrire maintenant obligerait à les refaire.

## Modèle

On a regardé les modèles gratuits d'OpenRouter (`:free`). Ils ne coûtent rien à l'appel, mais un compte sans crédit acheté est limité à 50 requêtes par jour. Le dataset a 5250 questions : ce quota ne suffit pas. Le sujet demande en plus un runtime local.

On utilise Ollama sur la machine, avec `llama3.2:3b`. Le Mac est un MacBook Air M4, 16 Go. Ce modèle pèse environ 2 Go et laisse de la marge au reste. Un modèle de 7 ou 8 milliards de paramètres répondrait un peu mieux, et ralentirait la machine pendant toute la collecte.

```bash
brew install ollama
brew services start ollama
ollama pull llama3.2:3b
```

`src/answer_questions.py` lit `silver/questions.parquet`. Pour chaque question, les réponses possibles sont mélangées et étiquetées A, B, C, D. Le modèle doit répondre par une seule lettre. `ai_correct` compare cette lettre à la lettre qui porte la bonne réponse, pas au texte d'origine. Le résultat est `silver/answers.parquet`, avec le prompt utilisé et `response_time`.

Le script reprend là où il s'est arrêté. Une fois le modèle chargé, une lettre prend une fraction de seconde. Les 5250 questions tiennent dans l'heure.

```bash
source .venv/bin/activate
python src/answer_questions.py
```

## Comparaison avec Qwen

`src/answer_questions_qwen.py` applique exactement le même protocole avec
`qwen2.5:3b`, un modèle gratuit exécuté localement par Ollama. Ses résultats
sont écrits séparément dans `silver/answers_qwen.parquet`, ce qui permet de
les comparer à `silver/answers.parquet` sans écraser ceux de Llama.

Un seul lancement teste les températures `0`, `0.5` et `1.0`. La colonne
`temperature` permet ensuite de comparer exactitude et temps de réponse par
réglage. Vous pouvez choisir votre propre série avec `--temperatures`.

```bash
ollama pull qwen2.5:3b
python src/answer_questions_qwen.py
```

Pour un essai rapide sur dix nouvelles questions :

```bash
python src/answer_questions_qwen.py --limit 10
```

Par exemple, pour ne tester que 0 et 0.5 :

```bash
python src/answer_questions_qwen.py --temperatures 0,0.5
```
