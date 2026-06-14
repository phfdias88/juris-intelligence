# ⚖️ Juris Intelligence

Plataforma de **inteligência jurídica** que automatiza a análise de processos, combinando uma API moderna em Python com enriquecimento por **IA (Google Gemini)**. O projeto aplica arquitetura orientada a domínios (DDD) e processamento assíncrono para lidar com grandes volumes de dados jurídicos.

## ✨ Funcionalidades

- 📑 Análise inteligente de processos jurídicos com apoio de IA (Google Gemini).
- 🧠 Sistema de agentes para investigação e enriquecimento automático de informações processuais.
- 📊 Módulo de **jurimetria** para métricas e estatísticas sobre litígios.
- 💰 Módulo de **litigation finance** para análise financeira de litígios.
- 🔐 Autenticação via JWT (tokens) com hashing seguro de senhas.
- ⚙️ Processamento assíncrono de tarefas pesadas com Celery + Redis.

## 🏗️ Arquitetura

O código é organizado por domínios de negócio, facilitando manutenção e evolução:

```
app/
├── core/                    # Configurações, segurança e infraestrutura
├── domains/
│   ├── agent_system/        # Agentes de investigação e enriquecimento
│   ├── jurimetrics/         # Métricas e estatísticas jurídicas
│   ├── legal_intelligence/  # Análise inteligente de processos
│   ├── litigation_finance/  # Análise financeira de litígios
│   └── shared/              # Componentes compartilhados
├── worker/                  # Tarefas assíncronas (Celery)
└── main.py                  # Ponto de entrada da API (FastAPI)
```

## 🛠️ Tecnologias

| Camada | Tecnologias |
|--------|-------------|
| API | FastAPI, Uvicorn |
| Banco de dados | PostgreSQL, SQLAlchemy, Alembic |
| Validação | Pydantic |
| Autenticação | JWT (python-jose), Passlib/bcrypt |
| Assíncrono | Celery, Redis |
| IA / LLM | Google Gemini (google-generativeai) |
| Documentos | PyPDF2 |
| Testes | Pytest, HTTPX |
| Infra | Docker, Docker Compose |

## 🚀 Como executar

Pré-requisitos: Docker e Docker Compose instalados.

```bash
# Clonar o repositório
git clone https://github.com/phfdias88/juris-intelligence.git
cd juris-intelligence

# Configurar variáveis de ambiente
cp .env.example .env   # edite com suas chaves (inclui GEMINI_API_KEY)

# Subir os serviços
docker-compose up --build
```

A API ficará disponível em `http://localhost:8000` e a documentação interativa (Swagger) em `http://localhost:8000/docs`.

## ✅ Testes

```bash
pytest
```

## 📌 Status

Projeto em desenvolvimento — MVP funcional com suíte de testes automatizados.

## 👤 Autor

**Paulo Henrique Ferreira Dias** — [LinkedIn](https://www.linkedin.com/in/phdias-ti)
