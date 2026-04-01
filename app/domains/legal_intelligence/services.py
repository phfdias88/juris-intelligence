"""
Servico do dominio de Inteligencia Legal.

Responsavel por:
- Registrar depoimentos de testemunhas
- Disparar analise assincrona de contradicoes via Celery
- Consultar status/resultado da analise
"""

from app.domains.shared.models import Depoimento, StatusDepoimento
from app.domains.shared.repository import ProcessoRepository
from app.worker.tasks import analisar_contradicao_testemunhas_task


class LegalIntelligenceService:
    """Servico de gestao de testemunhas e analise de contradicoes."""

    def __init__(self, repository: ProcessoRepository):
        self.repository = repository

    def registrar_depoimento(
        self, processo_id: int, testemunha_nome: str, texto_depoimento: str
    ) -> Depoimento:
        """Registra um depoimento e dispara analise assincrona via Celery.

        Fluxo:
        1. Persiste o depoimento com status PENDENTE
        2. Dispara a task Celery em background
        3. Salva o celery_task_id no depoimento para rastreamento
        4. Retorna o depoimento com o task_id (cliente pode consultar depois)
        """
        depoimento = Depoimento(
            processo_id=processo_id,
            testemunha_nome=testemunha_nome,
            texto_depoimento=texto_depoimento,
            status_analise=StatusDepoimento.PENDENTE,
        )
        depoimento = self.repository.criar_depoimento(depoimento)

        # Disparar analise assincrona — nao bloqueia a resposta HTTP
        task = analisar_contradicao_testemunhas_task.delay(depoimento.id)

        # Salvar o task_id para rastreamento posterior
        depoimento.celery_task_id = task.id
        self.repository.db.commit()
        self.repository.db.refresh(depoimento)

        return depoimento

    def buscar_depoimento(self, depoimento_id: int) -> Depoimento | None:
        """Retorna um depoimento pelo ID (inclui status da analise)."""
        return self.repository.buscar_depoimento_por_id(depoimento_id)

    def listar_depoimentos(self, processo_id: int) -> list[Depoimento]:
        """Lista todos os depoimentos de um processo."""
        return self.repository.listar_depoimentos(processo_id)
