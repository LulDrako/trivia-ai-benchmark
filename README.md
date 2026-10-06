# trivia-ai-benchmark

Benchmark de modèles locaux sur les questions de culture générale d'OpenTDB.

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
