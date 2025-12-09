# Préparation Entretien Technique - Synthesis Scraper

Ce document détaille l'architecture et les choix techniques du projet "synthesis-scraper" pour votre entretien chez Dassault Systèmes.

## 1. Vue d'ensemble du Pipeline

Le projet est un pipeline ETL (Extract, Transform, Load) automatisé conçu pour extraire des protocoles de synthèse de matériaux à partir de publications scientifiques.

**Flux de données :**
`Recherche Arxiv` -> `Téléchargement PDF` -> `Ingestion & Conversion Image` -> `Extraction LLM (Multimodal)` -> `Stockage Structuré (SQL)`

## 2. Étapes Détaillées du Pipeline

### Étape 1 : Acquisition de Données (Scraping)
- **Source** : Arxiv (via l'API `arxiv`).
- **Processus** : 
  - Recherche par mots-clés (ex: "MOF synthesis").
  - Filtrage par pertinence.
  - Téléchargement des PDF via `requests`.
  - Gestion des doublons et nettoyage des noms de fichiers.

### Étape 2 : Ingestion et Prétraitement
- **Conversion** : Les PDF sont convertis en images (JPEG) page par page.
- **Outil** : `pdf2image` (wrapper pour poppler) et `Pillow` (PIL).
- **Stratégie** : Conversion en images pour permettre à un modèle de vision (Vision-LLM) d'analyser non seulement le texte, mais aussi les **tableaux**, **graphiques** et **diagrammes** qui contiennent souvent les conditions critiques de synthèse.
- **Optimisation** : Limitation aux 3-5 premières pages pour économiser la mémoire et le temps de traitement, car la méthodologie est souvent au début.

### Étape 3 : Extraction d'Information (Le Cœur du Système)
- **Moteur IA** : **Ollama** (serveur d'inférence local).
- **Modèle** : **LLaVA** (Large Language-and-Vision Assistant). C'est un modèle multimodal capable de "voir" et de "lire".
- **Prompt Engineering** :
  - Utilisation d'un prompt système strict demandant une sortie **JSON uniquement**.
  - Définition d'un schéma JSON précis : `target_material`, `method_type`, `precursors` (liste), `conditions` (liste).
  - Instruction spécifique : "Pay special attention to TABLES and FIGURES".
- **Traitement** : Les images sont encodées en Base64 et envoyées au modèle via une requête HTTP POST.

### Étape 4 : Stockage des Données
- **Base de données** : **SQLite** (fichier `synthesis.db`).
- **Schéma Relationnel** :
  - `papers` : Métadonnées du papier (titre, DOI).
  - `syntheses` : Le protocole extrait (matériau cible, méthode).
  - `precursors` : Liste des réactifs liés à une synthèse (relation 1-N).
  - `conditions` : Paramètres comme la température, le temps (relation 1-N).

## 3. Stack Technique et Outils

| Catégorie | Outil / Librairie | Pourquoi ce choix ? |
|-----------|-------------------|---------------------|
| **Langage** | **Python 3.x** | Standard pour la Data Science et l'IA. |
| **LLM Serving** | **Ollama** | Permet de faire tourner des LLMs open-source (LLaVA) localement, sans frais d'API et avec confidentialité des données. |
| **Modèle** | **LLaVA** (Vision) | Capacité multimodale essentielle pour lire les tableaux et figures scientifiques. |
| **Scraping** | `arxiv`, `requests` | API officielle stable et requêtes HTTP simples. |
| **Traitement PDF** | `pdf2image`, `Pillow` | Robustesse pour la conversion PDF -> Image. |
| **Base de Données** | `sqlite3` | Léger, sans serveur, suffisant pour un prototype ou une application locale. |
| **Orchestration** | Scripts Python (`main.py`) | Logique séquentielle simple et facile à déboguer. |

## 4. Points Forts à Mettre en Avant (Pour l'entretien)

*   **Approche Multimodale** : Vous n'avez pas fait que du "RAG" (Retrieval Augmented Generation) sur du texte brut. Vous avez utilisé un modèle de vision pour capturer l'information visuelle (tableaux, structures chimiques), ce qui est crucial en science des matériaux.
*   **Inférence Locale** : Vous maîtrisez le déploiement de modèles locaux (Ollama), ce qui réduit les coûts et garantit la confidentialité (important pour la R&D industrielle).
*   **Sortie Structurée** : Vous forcez le LLM à sortir du JSON, rendant les données immédiatement exploitables pour une base de données, au lieu d'avoir du texte libre.
*   **Architecture Modulaire** : Séparation claire des responsabilités (`scraper`, `ingestor`, `extractor`, `db_manager`).

## 5. Améliorations Possibles (Si on vous demande)
- **Parallélisation** : Traiter plusieurs papiers en même temps (actuellement séquentiel).
- **RAG Avancé** : Indexer le texte dans une base vectorielle (ChromaDB, FAISS) pour poser des questions précises sur tout le document.
- **Validation** : Ajouter une étape de validation des données extraites (ex: vérifier que les unités sont cohérentes).
