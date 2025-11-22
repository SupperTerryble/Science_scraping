# Synthesis Scraper LLM

Ce projet est un outil automatisé pour extraire des conditions de synthèse de matériaux (température, précurseurs, méthodes) à partir de publications scientifiques. Il utilise un **LLM Multimodal (LLaVA)** via **Ollama** pour analyser à la fois le texte et les images (tableaux, graphiques) des articles.

## Fonctionnalités Principales

*   **Scraping Automatique** : Recherche et téléchargement de papiers depuis Arxiv.
*   **Analyse Multimodale** : Conversion des PDF en images pour permettre au LLM de "voir" les figures et tableaux.
*   **Extraction Structurée** : Sortie au format JSON strict (Matériau cible, Méthode, Précurseurs, Conditions).
*   **Base de Données** : Stockage relationnel (SQLite) des données extraites.
*   **Gestion Automatique du LLM** : Démarrage et arrêt automatique du serveur Ollama.

## Structure du Projet

### `src/main.py`
Le point d'entrée principal. Il orchestre tout le pipeline :
1.  Lance la recherche Arxiv (si demandée).
2.  Télécharge les PDF.
3.  Convertit les PDF en images via `ingestor.py`.
4.  Envoie les images à `extractor.py` pour analyse.
5.  Sauvegarde les résultats via `db_manager.py`.

**Usage :**
```bash
# Recherche automatique
python3 -m src.main --query "MOF synthesis" --max 5

# Fichier local
python3 -m src.main --input data/mon_papier.pdf
```

### `src/scraper.py`
Gère l'interaction avec l'API Arxiv.
- `search_papers(query, max_results)` : Récupère les métadonnées.
- `download_pdf(url)` : Télécharge le fichier localement.

### `src/ingestor.py`
Responsable de la lecture des fichiers.
- **Mode Multimodal** : Utilise `pdf2image` pour convertir chaque page du PDF en image (PIL).
- **Mode Texte** : (Legacy) Utilise `pypdf` pour extraire le texte brut.

### `src/extractor.py`
L'interface avec le LLM (Ollama).
- Prépare le prompt système (expert en science des matériaux).
- Encode les images en Base64.
- Envoie la requête à l'API Ollama (`/api/generate`).
- Nettoie et parse la réponse JSON.

### `src/db_manager.py`
Gère la base de données SQLite (`data/synthesis.db`).
- Crée les tables : `papers`, `syntheses`, `precursors`, `conditions`.
- Insère les données de manière relationnelle.

## Prérequis

*   **Python 3.10+**
*   **Ollama** installé et fonctionnel.
*   **Poppler-utils** (pour la conversion d'images) :
    ```bash
    sudo apt-get install -y poppler-utils
    ```
*   Dépendances Python :
    ```bash
    pip install -r requirements.txt
    ```

## Modèles LLM

Le projet est configuré pour utiliser **LLaVA** (Vision-Language Model).
Le script téléchargera automatiquement le modèle via Ollama si nécessaire (`ollama pull llava`).

## Logs

Les logs d'exécution sont enregistrés dans `scraper.log` à la racine du projet.
