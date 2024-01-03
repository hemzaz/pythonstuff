#!/usr/bin/env python3
import boto3
import json
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="AWS IAM setup script")
    parser.add_argument("--company", default="default_company", help="Company name")
    parser.add_argument("--env", default="default_env", help="Environment")
    return parser.parse_args()


def get_aws_account_id(sts_client):
    return sts_client.get_caller_identity().get("Account")


def get_oidc_providers(iam_client):
    return iam_client.list_open_id_connect_providers()


def create_or_update_role(iam_client, role_name, oidc_provider_arn, oidc_provider_url):
    assume_role_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Federated": oidc_provider_arn},
                    "Action": "sts:AssumeRoleWithWebIdentity",
                    "Condition": {
                        "StringEquals": {
                            f"{oidc_provider_url}:aud": "sts.amazonaws.com"
                        }
                    },
                }
            ],
        }
    )
    try:
        role = iam_client.create_role(
            RoleName=role_name, AssumeRolePolicyDocument=assume_role_policy
        )
        print("Role created:", role)
    except iam_client.exceptions.EntityAlreadyExistsException:
        iam_client.update_assume_role_policy(
            RoleName=role_name, PolicyDocument=assume_role_policy
        )
        print(f"Role {role_name} already exists. Trust policy updated.")


def create_or_fetch_policy(iam_client, policy_name, policy_document_json, account_id):
    try:
        policy_response = iam_client.create_policy(
            PolicyName=policy_name, PolicyDocument=policy_document_json
        )
        return policy_response["Policy"]["Arn"]
    except iam_client.exceptions.EntityAlreadyExistsException:
        return iam_client.get_policy(
            PolicyArn=f"arn:aws:iam::{account_id}:policy/{policy_name}"
        )["Policy"]["Arn"]


def attach_policy_to_role(iam_client, role_name, policy_arn):
    iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)


def main():
    args = parse_args()
    iam_client = boto3.client("iam")
    sts_client = boto3.client("sts")
    account_id = get_aws_account_id(sts_client)
    oidc_providers = get_oidc_providers(iam_client)

    if not oidc_providers["OpenIDConnectProviderList"]:
        print("No OIDC providers found.")
        sys.exit(1)

    oidc_provider_arn = oidc_providers["OpenIDConnectProviderList"][0]["Arn"]
    oidc_provider_url = "/".join(oidc_provider_arn.split("/")[1:])
    role_name = f"{args.company}-{args.env}-k8s-services-roles"
    policy_name = f"{args.company}-{args.env}-k8s-services-policy"
    policy_document_json = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "SecretManager",
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetResourcePolicy",
                        "secretsmanager:GetSecretValue",
                        "secretsmanager:DescribeSecret",
                        "secretsmanager:ListSecretVersionIds",
                        "secretsmanager:GetRandomPassword",
                        "secretsmanager:ListSecrets",
                    ],
                    "Resource": f"arn:aws:secretsmanager:us-east-1:{account_id}:secret:*",
                },
                {
                    "Sid": "ListObjectsInBucket",
                    "Effect": "Allow",
                    "Action": "s3:ListBucket",
                    "Resource": "arn:aws:s3:::*",
                },
                {
                    "Sid": "AllObjectActions",
                    "Effect": "Allow",
                    "Action": "s3:*Object",
                    "Resource": "arn:aws:s3:::*/*",
                },
                {
                    "Sid": "AllowMSKAll",
                    "Effect": "Allow",
                    "Action": "kafka-cluster:*",
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": ["s3:*", "s3-object-lambda:*"],
                    "Resource": "*",
                },
            ],
        }
    )

    create_or_update_role(iam_client, role_name, oidc_provider_arn, oidc_provider_url)
    policy_arn = create_or_fetch_policy(
        iam_client, policy_name, policy_document_json, account_id
    )
    attach_policy_to_role(iam_client, role_name, policy_arn)
    print(f"Setup completed for {args.company} in {args.env} environment.")


if __name__ == "__main__":
    main()
