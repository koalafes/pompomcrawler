#!/usr/bin/env python3
from aws_cdk import App, Environment

from pompomcrawler_stack import PompomCrawlerStack


app = App()
PompomCrawlerStack(
    app,
    "PompomCrawlerStack",
    env=Environment(region=app.node.try_get_context("region") or "ap-northeast-1"),
)
app.synth()
