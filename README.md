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
