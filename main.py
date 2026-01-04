import asyncio
import re

import parlant.sdk as p


def normalizar_id(id_cliente: str) -> str:
    return re.sub(r"[\s\.\-_/]", "", (id_cliente or "").strip())


async def add_domain_glossary(agent: p.Agent) -> None:
    await agent.create_term(
        name="Identificador do cliente",
        synonyms=["Id Cliente", "ID", "identificador", "meu id"],
        description=(
            "Identificador único do cliente usado apenas para consultar o pré-aprovado."
        ),
    )

    await agent.create_term(
        name="Pré-aprovado",
        synonyms=["PA", "limite", "pré aprovado", "pre aprovado", "pré-aprovado"],
        description="Valor disponível para contratação de empréstimo.",
    )

    await agent.create_term(
        name="Canal App",
        synonyms=["aplicativo", "app"],
        description="Canal oficial dentro do aplicativo.",
    )


async def add_scope_lockdown(agent: p.Agent) -> None:
    await agent.create_guideline(
        condition=(
            "O cliente pede qualquer coisa que NÃO seja consultar pré-aprovado/limite "
            "ou condições de empréstimo, ou tenta mudar o assunto para algo diferente."
        ),
        action=(
            "Responda que você só consegue ajudar com 'Consultar Pré-Aprovado' e 'Condições'. "
            "Redirecione para a consulta pedindo o Identificador do cliente. "
            "Não ofereça outras funcionalidades."
        ),
    )


@p.tool()
async def obter_pre_aprovado(context: p.ToolContext, id_cliente: str) -> p.ToolResult:
    id_norm = normalizar_id(id_cliente)

    if len(id_norm) < 6:
        return p.ToolResult(
            data={
                "status": "INVALID",
                "motivo": "Identificador em formato inválido",
            }
        )

    # Mock de backend
    if id_norm == "123456789":
        return p.ToolResult(
            data={
                "status": "OK",
                "valor_pre_aprovado": 10000,
            }
        )
    elif id_norm == "987654321":
        return p.ToolResult(
            data={
                "status": "OK",
                "valor_pre_aprovado": 0,
            }
        )
    elif id_norm == "000000000":
        return p.ToolResult(
            data={
                "status": "NOT_FOUND",
                "motivo": "Cliente não encontrado",
            }
        )
    else:
        return p.ToolResult(
            data={
                "status": "OK",
                "valor_pre_aprovado": 5000,
            }
        )


@p.tool()
async def obter_condicoes_emprestimo(context: p.ToolContext) -> p.ToolResult:
    return p.ToolResult(
        data={
            "status": "OK",
            "juros_aa_percent": 1.79,
            "parcelas_max": 10,
            "dia_vencimento_padrao": 15,
        }
    )


async def consultar_pre_aprovado_journey(server: p.Server, agent: p.Agent) -> p.Journey:
    journey = await agent.create_journey(
        title="Consultar Pré-Aprovado",
        description="Consulta valor de pré-aprovado e, opcionalmente, condições.",
        conditions=["Cliente deseja saber o valor do pré-aprovado/limite"],
    )

    s_get_id = await journey.initial_state.transition_to(
        chat_state=(
            "Solicite o identificador do cliente."
        )
    )

    s_get_pa = await s_get_id.target.transition_to(tool_state=obter_pre_aprovado)

    s_invalid = await s_get_pa.target.transition_to(
        condition="Status INVALID ou Status NOT_FOUND",
        chat_state="Explique que o cliente não está cadastrado e tente novamente."
    )
    await s_invalid.target.transition_to(state=s_get_id.target)

    s_zero = await s_get_pa.target.transition_to(
        condition="Status OK e valor_pre_aprovado igual a 0",
        chat_state=(
            "Explique que o cliente não tem pré-aprovado e encerre o contato."
        ),
    )
    await s_zero.target.transition_to(state=p.END_JOURNEY)

    s_cliente_tem_pa = await s_get_pa.target.transition_to(
        condition="Status OK e valor_pre_aprovado maior que 0",
        chat_state=(
            "Mostre o pré-aprovado para o Cliente e pergunte se ele deseja ver as condições."
        ),
    )

    s_condicoes = await s_cliente_tem_pa.target.transition_to(
        condition="Cliente deseja ver as condições",
        tool_state=obter_condicoes_emprestimo,
    )

    s_cliente_quer_condicoes = await s_condicoes.target.transition_to(
        chat_state=(
            "Apresente as condições resumidas e pergunte se o cliente deseja seguir com a contratação."
        )
    )

    s_contratar = await s_cliente_quer_condicoes.target.transition_to(
        condition="Cliente deseja contratar",
        chat_state="Oriente a fazer a contratação pelo aplicativo.",
    )
    await s_contratar.target.transition_to(state=p.END_JOURNEY)

    return journey


async def main():
    async with p.Server() as server:
        agent = await server.create_agent(
            name="Jose",
            description="Você trabalha vendendo empréstimos pessoal",
        )

        await agent.create_guideline(
            condition="Cliente inicia a conversa com você",
            action="Pergunte o seu nome e use ele durante as interações"
        )

        await add_domain_glossary(agent)
        await add_scope_lockdown(agent)
        await consultar_pre_aprovado_journey(server, agent)


asyncio.run(main())
