# trivia-ai-benchmark

Benchmark de modèles locaux sur les questions de culture générale d'OpenTDB.

## Bronze

`src/scrape_opentdb.py` interroge l'API OpenTDB et écrit `bronze/questions_raw.csv`.

OpenTDB renvoie au plus 50 questions par appel, et n'accepte qu'un appel toutes les 5 secondes. Le script attend entre chaque appel. Un token de session évite de recevoir deux fois la même question. Quand l'API répond avec le code 4, tout le jeu disponible a été récupéré.

Le CSV garde le texte tel que l'API le renvoie (entités HTML comprises). Les mauvaises réponses sont stockées en JSON dans la colonne `incorrect_answers`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/scrape_opentdb.py
```

Si le script s'arrête, relance la même commande : il reprend grâce à `bronze/session.json`. Pour tout recommencer : `python src/scrape_opentdb.py --reset`.
