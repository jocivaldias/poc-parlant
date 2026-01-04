import asyncio
import random
import re
from dataclasses import dataclass
from typing import Dict

import parlant.sdk as p


@dataclass
class ClienteConta:
    pa_disponivel: float


CLIENTES: Dict[str, ClienteConta] = {}

_RNG = random.Random()


def normalizar_id(id_cliente: str) -> str:
    return re.sub(r"[\s\.\-_/]", "", (id_cliente or "").strip())


def get_or_create_conta(id_cliente_norm: str) -> ClienteConta:
    conta = CLIENTES.get(id_cliente_norm)
    if conta is None:
        if _RNG.random() < 0.50:
            pa = 0.0
        else:
            pa = float(_RNG.randrange(1000, 20001, 500))
        conta = ClienteConta(pa_disponivel=pa)
        CLIENTES[id_cliente_norm] = conta
    return conta


async def add_domain_glossary(agent: p.Agent) -> None:
    await agent.create_term(
        name="Identificador do cliente",
        synonyms=["Id Cliente", "ID", "identificador", "meu id"],
        description="Identificador único do cliente.",
    )

    await agent.create_term(
        name="Pré-aprovado",
        synonyms=["PA", "limite", "pré aprovado", "pre aprovado", "pré-aprovado"],
        description="Valor disponível para contratação de empréstimo.",
    )

    await agent.create_term(
        name="Condições",
        synonyms=["juros", "parcelas", "vencimento", "condições"],
        description="Condições básicas de contratação: juros, parcelas, vencimento.",
    )


async def add_scope_lockdown(agent: p.Agent) -> None:
    await agent.create_guideline(
        condition=(
            "O cliente pede qualquer coisa que não seja consultar pré-aprovado/limite, "
            "ver condições de empréstimo, ou contratar um empréstimo."
        ),
        action=(
            "Peça desculpas e diga que você só consegue ajudar com 'Consultar Pré-Aprovado' "
            "e 'Contratar Empréstimo'."
        ),
    )


@p.tool()
async def obter_pre_aprovado(context: p.ToolContext, id_cliente: str) -> p.ToolResult:
    id_norm = normalizar_id(id_cliente)

    if len(id_norm) < 6:
        return p.ToolResult(
            data={"status": "INVALID", "motivo": "Identificador em formato inválido"}
        )

    conta = get_or_create_conta(id_norm)

    return p.ToolResult(
        data={
            "status": "OK",
            "id_cliente": id_norm,
            "valor_pre_aprovado": conta.pa_disponivel,
        }
    )


@p.tool()
async def obter_condicoes_emprestimo(context: p.ToolContext) -> p.ToolResult:
    return p.ToolResult(data={
        "status": "OK",
        "juros": 1.79,
        "parcelas_max": 10,
        "dia_vencimento_padrao": 15,
    })


async def consultar_pre_aprovado_journey(agent: p.Agent) -> p.Journey:
    journey = await agent.create_journey(
        title="Consultar Pré-Aprovado",
        description="Consulta o valor de pré-aprovado e pode mostrar condições.",
        conditions=["Cliente deseja consultar pré-aprovado/limite"],
    )

    # pedir id
    s_get_id = await journey.initial_state.transition_to(chat_state="Solicite o identificador do cliente.")

    # tool PA
    s_get_pa = await s_get_id.target.transition_to(tool_state=obter_pre_aprovado)

    # inválido
    s_invalid = await s_get_pa.target.transition_to(
        condition="Status INVALID",
        chat_state="Explique que o identificador é inválido e peça novamente.",
    )
    await s_invalid.target.transition_to(state=s_get_id.target)

    # ok com PA = 0
    s_zero = await s_get_pa.target.transition_to(
        condition="Status OK e valor_pre_aprovado igual a 0",
        chat_state="Explique que o cliente não tem pré-aprovado e encerre.",
    )
    await s_zero.target.transition_to(state=p.END_JOURNEY)

    # ok com PA > 0
    s_has_pa = await s_get_pa.target.transition_to(
        condition="Status OK e valor_pre_aprovado maior que 0",
        chat_state="Mostre o pré-aprovado e pergunte se deseja ver as condições.",
    )

    # condições (opcional)
    s_cond = await s_has_pa.target.transition_to(
        condition="Cliente deseja ver as condições",
        tool_state=obter_condicoes_emprestimo,
    )

    s_show_cond = await s_cond.target.transition_to(
        chat_state="Apresente as condições resumidas, agradeça o contato e encerre.",
    )
    await s_show_cond.target.transition_to(state=p.END_JOURNEY)

    # não quer condições
    s_no_cond = await s_has_pa.target.transition_to(
        condition="Cliente não deseja ver as condições",
        chat_state="Encerre e agradeça o contato.",
    )
    await s_no_cond.target.transition_to(state=p.END_JOURNEY)

    return journey


async def main():
    async with p.Server() as server:
        agent = await server.create_agent(
            name="Jose",
            description="Você trabalha informando o pré-aprovado dos clientes"
        )

        await agent.create_guideline(
            condition="Cliente inicia a conversa",
            action="Cumprimente-o e pergunte se ele deseja consultar o pré-aprovado"
        )

        await agent.create_guideline(
            condition="Cliente responde de forma vaga, sem indicar consultar pré-aprovado",
            action="Pergunte novamente se ele deseja consultar o seu pré-aprovado."
        )

        await add_domain_glossary(agent)
        await add_scope_lockdown(agent)
        await consultar_pre_aprovado_journey(agent)


asyncio.run(main())
