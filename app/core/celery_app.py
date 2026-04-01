"""
Configuracao do Celery para processamento assincrono.

O Celery e essencial nesta arquitetura porque tarefas de IA (analise de
contradicoes, extracao de PDFs, scoring jurimetrico avancado) podem levar
segundos ou minutos. Sem ele, a API ficaria bloqueada esperando a resposta.

Fluxo:
    1. Rota FastAPI recebe requisicao e dispara task via .delay()
    2. Celery enfileira no Redis (broker)
    3. Worker consome a fila e executa a tarefa em background
    4. Resultado fica disponivel no Redis (backend) para consulta

Para iniciar o worker:
    celery -A app.core.celery_app worker --loglevel=info --pool=solo
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "juris_intelligence",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# ── Configuracao do Celery ───────────────────────
# Em modo DEBUG sem Redis, executa tasks sincronamente (ideal para dev local)
if settings.DEBUG and not settings.CELERY_BROKER_URL.startswith("redis"):
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )

celery_app.conf.update(
    # Serializacao segura — evita execucao arbitraria de codigo (pickle)
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone brasileiro (ajuste conforme necessidade)
    timezone="America/Sao_Paulo",
    enable_utc=True,

    # Retry automatico em caso de falha de conexao com broker
    broker_connection_retry_on_startup=True,

    # Resultados expiram em 24h para nao acumular no Redis
    result_expires=86400,

    # Prefetch de 1 tarefa por worker — ideal para tarefas pesadas de IA
    # que consomem muita memoria/CPU (evita que um worker pegue 10 de uma vez)
    worker_prefetch_multiplier=1,

    # Limite de tarefas antes do worker reiniciar (previne memory leaks de modelos de IA)
    worker_max_tasks_per_child=100,
)

# Autodiscovery: Celery encontra automaticamente as tasks em app/worker/
celery_app.autodiscover_tasks(["app.worker"])
