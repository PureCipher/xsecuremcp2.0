"""AWS calls with explicit per-connection credentials, never the host credential chain."""

import asyncio
import re

PRODUCTS = {"aws-core", "cloudwatch"}


async def execute(values, service, operation, params):
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError

    region = values.get("AWS_REGION", "")
    if not re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-\d", region):
        raise ValueError("Enter an AWS region such as us-east-1")
    if not values.get("AWS_ACCESS_KEY_ID") or not values.get("AWS_SECRET_ACCESS_KEY"):
        raise ValueError("Your AWS access key and secret key are required")

    def call():
        client = boto3.client(
            service,
            region_name=region,
            endpoint_url="https://"
            + {"sts": "sts", "cloudwatch": "monitoring", "logs": "logs"}[service]
            + "."
            + region
            + (".amazonaws.com.cn" if region.startswith("cn-") else ".amazonaws.com"),
            aws_access_key_id=values["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=values["AWS_SECRET_ACCESS_KEY"],
            aws_session_token=values.get("AWS_SESSION_TOKEN") or None,
            config=Config(
                connect_timeout=10,
                read_timeout=20,
                retries={"max_attempts": 1},
                proxies={},
            ),
        )
        try:
            result = getattr(client, operation)(**params)
            result.pop("ResponseMetadata", None)
            return result
        except (BotoCoreError, ClientError):
            raise ValueError(
                "AWS denied or could not complete the request; check permissions, region and credential expiry"
            ) from None
        finally:
            client.close()

    return await asyncio.to_thread(call)


async def verify(values):
    return await execute(values, "sts", "get_caller_identity", {})


def register(registry):
    from purecipher.consumer_runtime import _ACCESS, access

    registry._consumer_products = registry._consumer_products | PRODUCTS

    def tool(product):
        def decorate(fn):
            registry._consumer_tool_products[fn.__name__] = product
            registry.tool(
                annotations={
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "openWorldHint": True,
                }
            )(fn)
            return fn

        return decorate

    def values(product):
        access(product)
        context = _ACCESS.get()
        if context is None:
            raise ValueError("An assigned profile is required")
        return context["values"]

    @tool("aws-core")
    async def aws_caller_identity() -> dict:
        """Read your AWS account and caller identity using this connection's credentials."""
        return await verify(values("aws-core"))

    @tool("cloudwatch")
    async def cloudwatch_list_metrics(
        namespace: str = "", next_token: str = ""
    ) -> dict:
        """List metric definitions; requires cloudwatch:ListMetrics."""
        return await execute(
            values("cloudwatch"),
            "cloudwatch",
            "list_metrics",
            {
                **({"Namespace": namespace} if namespace else {}),
                **({"NextToken": next_token} if next_token else {}),
            },
        )

    @tool("cloudwatch")
    async def cloudwatch_list_log_groups(prefix: str = "", limit: int = 20) -> dict:
        """Read log-group metadata; requires logs:DescribeLogGroups."""
        if not 1 <= limit <= 50:
            raise ValueError("Limit must be between 1 and 50")
        return await execute(
            values("cloudwatch"),
            "logs",
            "describe_log_groups",
            {"limit": limit, **({"logGroupNamePrefix": prefix} if prefix else {})},
        )
