# Profile — Arnaud Thery

## Contact
- Email: St4r4x@gmail.com
- Phone: +33 6 61624819
- Location: Ajaccio, 20090 — disponible Paris dès fin 2026
- LinkedIn: [à compléter]
- GitHub: github.com/St4r4x

## Summary
AI/ML Engineer with hands-on production experience in Computer Vision, LLM/RAG, and edge inference. Background in team management (8 years) brings strong project ownership and communication. Currently completing a Master of Science in AI (2026).

## Experience

### AI/ML Engineer — NeuralVision (Work-study, January 2025 – Present)
- Real-time edge inference system on Jetson Orin NX (ARM64): action recognition, fall detection
- Benchmark pipeline evaluating YOLO detectors + RTMPose estimators across resolutions to maximize F1 on lying-person class
- VideoMAE fine-tuning pipeline on AWS SageMaker Spot (A10G, bf16) with S3 manifest-based data loading
- Multi-user annotation tool (FiftyOne + SQLite) for bounding-box labeling and review
- Video processing framework (ffprobe, Docker, GHCR, CI/CD via GitHub Actions)
- Cloud infrastructure on AWS (SageMaker, S3, Kinesis, Lambda, DynamoDB, ECS Fargate, Cognito) — Terraform/Terragrunt (notions)
- ElderWatch: privacy-by-design embedded activity detection for elderly people (no video leaves the device)

### AI Designer — NeuralVision (Work-study, September 2023 – January 2025)
- Computer vision pipelines using OpenMMLab framework and Vision Transformers
- Model fine-tuning and data analysis
- Framework: OpenMMLab, PyTorch

### AI Developer — GoodBarber (Internship, April 2023 – June 2023)
- LLM utilization in a Django/Python backend
- Unit testing, Docker

### Department Manager — Fnac Ajaccio (CDI, April 2015 – September 2023)
- Sales team management, inventory, reporting, staffing & scheduling
- 8 years of leadership: autonomy, prioritization, communication under pressure

## Education
- **Master of Science BIHAR** — Aflokkat / ESIA (2024–2026)
- **Web and AI Designer Certification** — Aflokkat / ESIA (2023–2024)
- **AI Developer Certification** — Aflokkat / ESIA (2022–2023)
- **BTS Management of Commercial Units (MUC)** — 2008

## Skills

### Machine Learning & Deep Learning
- PyTorch — training loops, custom datasets
- HuggingFace Transformers — fine-tuning, Trainer API, Model Cards, Hub upload
- DeBERTa / NLP / NLI (multilingual, 15 languages)
- VideoMAE — video understanding fine-tuning
- Mixed precision training (fp16, bf16), weighted training (class imbalance)
- MLflow — experiment tracking, artifact management
- AWS SageMaker Spot — distributed training on A10G

### Computer Vision
- YOLO v11 — object detection, benchmarking pipelines
- RTMPose / pose estimation
- OpenMMLab framework
- Vision Transformers
- Fall detection / action recognition (real-time)
- Overhead camera / edge camera pipelines

### Edge & Embedded
- Jetson Orin NX (ARM64) deployment
- Docker multi-architecture (AMD64/ARM64)
- Real-time edge inference (watchdog, crash recovery, healthcheck)
- AWS IoT Greengrass (notions)

### MLOps & Data Engineering
- CI/CD — GitHub Actions, automated pipelines
- Docker & Docker Compose (multi-service)
- GHCR (GitHub Container Registry)
- ffprobe / video processing pipelines
- Dataset creation & annotation (FiftyOne, YOLO format)
- S3 / manifests for large-scale datasets

### Cloud & Infrastructure
- AWS: SageMaker, S3, Kinesis, Lambda, DynamoDB, ECS Fargate, Cognito
- Terraform / Terragrunt (notions — applied in professional project)
- Railway (app deployment)

### Backend & APIs
- FastAPI — REST API, inference serving
- Django / Python
- Spring Boot / Java (MongoDB, PostgreSQL, Redis, Elasticsearch, JWT)
- Playwright — web scraping, browser automation
- SQLite

### LLM / RAG / Agentic
- LLM utilization in production (GoodBarber)
- RAG pipelines
- Agentic AI — active self-training on agent patterns and multi-agent workflows (Claude Code)

### Data & Analysis
- Data Science / EDA, Pandas, Numpy
- Stratified splits, ML metrics: mAP, F1, recall, precision

### Languages
- French (native)
- English (professional)

## Personal Projects
- **Kaggle Watson**: NLI multilingual competition — DeBERTa-v3-base fine-tuning, AdamW + warmup + cosine decay, fp16, 15 languages
- **Olives Detector**: YOLOv11n + MLflow + FastAPI + Streamlit — full Docker Compose stack
- **InferAPI**: FastAPI inference service for ResNet50, GPU/CPU Docker Compose
- **eSport Scrapper**: Playwright-based daily scraper for pro player settings (CS2, Valorant, LoL, Fortnite) + web UI
- **Restaurant Analytics**: Spring Boot + MongoDB + PostgreSQL + Redis + Elasticsearch + JWT — deployed on Railway
