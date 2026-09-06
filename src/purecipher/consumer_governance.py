"""Report required security approvals before a consumer profile is activated."""

from fastmcp.server.security.consent.models import ConsentQuery
from fastmcp.server.security.middleware.contract_validation import (
    ContractValidationMiddleware,
)


def blockers(registry, profile):
    registered = getattr(registry, "_consumer_tool_products", {})
    names = {name for selected in profile["servers"] for name in selected["tools"]}
    if not names.intersection(registered):
        return []
    broker = registry._broker_or_none()
    graph = registry._consent_graph_or_none()
    context = registry._required_context()
    consent_config = context.config.consent
    problems = []
    for client_id in profile["client_ids"]:
        client = registry._client_store.get_client(client_id)
        if not client:
            continue
        if broker is not None:
            contracts = broker.get_active_contracts_for_agent(client.slug)
            if not contracts:
                problems.append(
                    f"Security approval: client {client.slug} needs an active SecureMCP contract for the selected tools"
                )
            else:
                check = ContractValidationMiddleware(broker)
                if any(
                    check._check_term_constraint(contracts[0], "call_tool", name)
                    for name in names
                ):
                    problems.append(
                        f"Security approval: client {client.slug}'s active contract does not permit all selected tools"
                    )
        if graph is not None and consent_config is not None:
            if not graph.evaluate(
                ConsentQuery(
                    source_id=consent_config.resource_owner,
                    target_id=client.slug,
                    scope="execute",
                )
            ).granted:
                problems.append(
                    f"Security approval: client {client.slug} needs execute consent from {consent_config.resource_owner}"
                )
    return problems
