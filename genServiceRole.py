#!/usr/bin/env python3
import boto3
import json
import sys

# Check if the correct number of arguments are provided
if len(sys.argv) != 3:
    print("Usage: python script.py <company> <env>")
    sys.exit(1)

# Assign arguments to variables
company = sys.argv[1]
env = sys.argv[2]

# Set up AWS clients
iam_client = boto3.client("iam")
sts_client = boto3.client("sts")

# Get the AWS account ID
account_id = sts_client.get_caller_identity().get("Account")

# 1. Fetch the OpenID Connect providers for the account
try:
    oidc_providers = iam_client.list_open_id_connect_providers()
    if not oidc_providers["OpenIDConnectProviderList"]:
        print("No OIDC providers found.")
        sys.exit(1)
    print("OIDC Providers:", oidc_providers)
except Exception as e:
    print(f"Error fetching OIDC providers: {e}")
    sys.exit(1)

# Assuming there is at least one OIDC provider, get the ARN of the first one
oidc_provider_arn = oidc_providers["OpenIDConnectProviderList"][0]["Arn"]

# Extract the OIDC provider URL from the ARN
oidc_provider_url = "/".join(oidc_provider_arn.split("/")[1:])

# 2. Set up a role named "<company>-<env>-k8s-services-roles"
role_name = f"{company}-{env}-k8s-services-roles"
assume_role_policy = json.dumps(
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Federated": oidc_provider_arn},
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {f"{oidc_provider_url}:aud": "sts.amazonaws.com"}
                },
            }
        ],
    }
)

# Create or update the role with the trust relationship
try:
    role = iam_client.create_role(
        RoleName=role_name, AssumeRolePolicyDocument=assume_role_policy
    )
    print("Role created:", role)
except iam_client.exceptions.EntityAlreadyExistsException:
    try:
        iam_client.update_assume_role_policy(
            RoleName=role_name, PolicyDocument=assume_role_policy
        )
        print(f"Role {role_name} already exists. Trust policy updated.")
    except Exception as e:
        print(f"Error updating trust policy for role {role_name}: {e}")

# 3. Set up a policy named "<company>-<env>-k8s-services-policy"
policy_name = f"{company}-{env}-k8s-services-policy"
policy_document = {
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
        {"Effect": "Allow", "Action": ["s3:*", "s3-object-lambda:*"], "Resource": "*"},
    ],
}

# Convert the policy document to JSON string format
policy_document_json = json.dumps(policy_document)

# Create the policy or fetch its ARN if it already exists
try:
    policy_response = iam_client.create_policy(
        PolicyName=policy_name, PolicyDocument=policy_document_json
    )
    policy_arn = policy_response["Policy"]["Arn"]
    print("Policy created:", policy_response)
except iam_client.exceptions.EntityAlreadyExistsException:
    policy_arn = iam_client.get_policy(
        PolicyArn=f"arn:aws:iam::{account_id}:policy/{policy_name}"
    )["Policy"]["Arn"]
    print(f"Policy {policy_name} already exists.")

# Attach the policy to the role
try:
    iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
    print(f"Policy {policy_name} attached to role {role_name}.")
except Exception as e:
    print(f"Error attaching policy: {e}")
