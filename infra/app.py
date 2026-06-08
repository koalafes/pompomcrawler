#!/usr/bin/env python3
import os

from aws_cdk import App, Environment

from pompomcrawler_stack import PompomCrawlerStack


app = App()
PompomCrawlerStack(
    app,
    "PompomCrawlerStack",
    env=Environment(
        account=app.node.try_get_context("account") or os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=app.node.try_get_context("region") or os.getenv("CDK_DEFAULT_REGION") or "ap-northeast-1",
    ),
)
app.synth()
