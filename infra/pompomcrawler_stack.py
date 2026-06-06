from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import jsii
from aws_cdk import BundlingOptions, CfnOutput, Duration, ILocalBundling, RemovalPolicy, Stack
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_authorizers as authorizers
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_scheduler as scheduler
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_iam as iam
from constructs import Construct


ROOT = Path(__file__).resolve().parents[1]


@jsii.implements(ILocalBundling)
class LocalPythonBundling:
    def try_bundle(self, output_dir: str, options: BundlingOptions) -> bool:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "sgmllib3k==1.0.0", "-t", output_dir])
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--platform",
                "manylinux2014_x86_64",
                "--implementation",
                "cp",
                "--python-version",
                "3.12",
                "--only-binary=:all:",
                "--no-deps",
                "--target",
                output_dir,
                "-r",
                str(ROOT / "requirements-lambda.txt"),
            ]
        )
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-deps", str(ROOT), "-t", output_dir])
        shutil.copytree(ROOT / "config", Path(output_dir) / "config", dirs_exist_ok=True)
        return True


class PompomCrawlerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        schedule_items = dynamodb.Table(
            self,
            "ScheduleItems",
            partition_key=dynamodb.Attribute(name="item_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
        )
        deleted_keys = dynamodb.Table(
            self,
            "DeletedScheduleKeys",
            partition_key=dynamodb.Attribute(name="block_key", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
        )
        raw_documents = dynamodb.Table(
            self,
            "RawDocuments",
            partition_key=dynamodb.Attribute(name="url", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
        )

        openai_secret = secretsmanager.Secret.from_secret_name_v2(
            self,
            "OpenAISecret",
            "pompomcrawler/openai",
        )

        common_env = {
            "SCHEDULE_ITEMS_TABLE": schedule_items.table_name,
            "DELETED_KEYS_TABLE": deleted_keys.table_name,
            "RAW_DOCUMENTS_TABLE": raw_documents.table_name,
            "OPENAI_SECRET_ARN": openai_secret.secret_arn,
            "POMPOM_CONFIG_PATH": "config/sources.yml",
            "ADMIN_EMAILS": str(self.node.try_get_context("admin_emails") or ""),
        }
        code = lambda_.Code.from_asset(
            str(ROOT),
            bundling=BundlingOptions(
                image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                local=LocalPythonBundling(),
                command=[
                    "bash",
                    "-c",
                    "pip install . -t /asset-output && cp -R config /asset-output/config",
                ],
            ),
        )

        api_function = lambda_.Function(
            self,
            "ApiFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="pompomcrawler.aws_handlers.api_handler",
            code=code,
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={**common_env, "CORS_ALLOW_ORIGIN": "*"},
        )
        crawler_function = lambda_.Function(
            self,
            "CrawlerFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="pompomcrawler.aws_handlers.crawler_handler",
            code=code,
            timeout=Duration.minutes(15),
            memory_size=1024,
            environment=common_env,
        )

        for function in [api_function, crawler_function]:
            schedule_items.grant_read_write_data(function)
            deleted_keys.grant_read_write_data(function)
            raw_documents.grant_read_write_data(function)
            openai_secret.grant_read(function)

        user_pool = cognito.UserPool(
            self,
            "AdminUserPool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            removal_policy=RemovalPolicy.RETAIN,
        )
        domain_prefix = f"pompomcrawler-{self.account}-{self.region}"
        user_pool.add_domain(
            "AdminDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=domain_prefix
            ),
        )
        callback_urls = context_list(
            self.node.try_get_context("callback_urls"),
            ["http://localhost:8001/docs/index.html", "http://localhost:8001/"],
        )
        logout_urls = context_list(self.node.try_get_context("logout_urls"), callback_urls)
        user_pool_client = cognito.UserPoolClient(
            self,
            "AdminUserPoolClient",
            user_pool=user_pool,
            generate_secret=False,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
                callback_urls=callback_urls,
                logout_urls=logout_urls,
            ),
        )
        cognito.CfnUserPoolGroup(
            self,
            "CalendarAdminGroup",
            user_pool_id=user_pool.user_pool_id,
            group_name="calendar-admin",
        )

        api = apigwv2.HttpApi(
            self,
            "HttpApi",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_headers=["authorization", "content-type"],
                allow_methods=[
                    apigwv2.CorsHttpMethod.GET,
                    apigwv2.CorsHttpMethod.POST,
                    apigwv2.CorsHttpMethod.DELETE,
                    apigwv2.CorsHttpMethod.OPTIONS,
                ],
                allow_origins=["*"],
            ),
        )
        integration = integrations.HttpLambdaIntegration("ApiIntegration", api_function)
        jwt_authorizer = authorizers.HttpJwtAuthorizer(
            "CognitoJwtAuthorizer",
            f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}",
            jwt_audience=[user_pool_client.user_pool_client_id],
        )
        api.add_routes(path="/items", methods=[apigwv2.HttpMethod.GET], integration=integration)
        api.add_routes(
            path="/admin/items",
            methods=[apigwv2.HttpMethod.GET],
            integration=integration,
            authorizer=jwt_authorizer,
        )
        api.add_routes(
            path="/admin/items/{item_id}",
            methods=[apigwv2.HttpMethod.DELETE],
            integration=integration,
            authorizer=jwt_authorizer,
        )
        api.add_routes(
            path="/admin/items/{item_id}/restore",
            methods=[apigwv2.HttpMethod.POST],
            integration=integration,
            authorizer=jwt_authorizer,
        )

        scheduler_role = iam.Role(
            self,
            "SchedulerRole",
            assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com"),
        )
        crawler_function.grant_invoke(scheduler_role)
        scheduler.CfnSchedule(
            self,
            "DailyCrawlerSchedule",
            flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(mode="OFF"),
            schedule_expression="cron(0 7,18 * * ? *)",
            schedule_expression_timezone="Asia/Tokyo",
            target=scheduler.CfnSchedule.TargetProperty(
                arn=crawler_function.function_arn,
                role_arn=scheduler_role.role_arn,
            ),
        )

        amplify_app_id = str(self.node.try_get_context("amplify_app_id") or "d1tvp4oub2aan6")
        amplify_branch_name = str(self.node.try_get_context("amplify_branch_name") or "main")
        github_repo = str(self.node.try_get_context("github_repo") or "koalafes/pompomcrawler")
        github_branch = str(self.node.try_get_context("github_branch") or "main")
        github_oidc_provider = iam.OpenIdConnectProvider(
            self,
            "GitHubOidcProvider",
            url="https://token.actions.githubusercontent.com",
            client_ids=["sts.amazonaws.com"],
        )
        amplify_branch_arn = Stack.of(self).format_arn(
            service="amplify",
            resource="apps",
            resource_name=f"{amplify_app_id}/branches/{amplify_branch_name}",
        )
        amplify_deployment_arn = f"{amplify_branch_arn}/deployments/*"
        amplify_job_arn = f"{amplify_branch_arn}/jobs/*"
        github_amplify_deploy_role = iam.Role(
            self,
            "GitHubAmplifyDeployRole",
            role_name="pompomcrawler-github-amplify-deploy",
            assumed_by=iam.FederatedPrincipal(
                github_oidc_provider.open_id_connect_provider_arn,
                conditions={
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                        "token.actions.githubusercontent.com:sub": f"repo:{github_repo}:ref:refs/heads/{github_branch}",
                    }
                },
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
        )
        github_amplify_deploy_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "amplify:CreateDeployment",
                    "amplify:StartDeployment",
                    "amplify:GetJob",
                ],
                resources=[amplify_branch_arn, amplify_deployment_arn, amplify_job_arn],
            )
        )

        CfnOutput(self, "ApiBaseUrl", value=api.api_endpoint)
        CfnOutput(self, "CognitoUserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "CognitoUserPoolClientId", value=user_pool_client.user_pool_client_id)
        CfnOutput(self, "CognitoDomain", value=f"https://{domain_prefix}.auth.{self.region}.amazoncognito.com")
        CfnOutput(self, "GitHubAmplifyDeployRoleArn", value=github_amplify_deploy_role.role_arn)
        CfnOutput(self, "ScheduleItemsTable", value=schedule_items.table_name)
        CfnOutput(self, "DeletedScheduleKeysTable", value=deleted_keys.table_name)
        CfnOutput(self, "RawDocumentsTable", value=raw_documents.table_name)


def context_list(value: object, default: list[str]) -> list[str]:
    if value is None:
        return default
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]
