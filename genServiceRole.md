# AWS IAM Role and Policy Setup Script

This script automates the creation of an IAM role with an attached policy for a specific company and environment within AWS. The script sets up a role with a trust relationship to an OpenID Connect (OIDC) provider and attaches a policy that grants permissions to interact with AWS Secrets Manager, S3, and MSK.

## Prerequisites

Before running this script, ensure the following prerequisites are met:

- AWS CLI is installed and configured with the necessary access rights.
- Python and Boto3 library are installed.
- You have permissions to create and manage IAM roles and policies in AWS.

## Usage

To use this script, you must provide two arguments: `<company>` and `<env>`, which are placeholders for your company's name and the environment (e.g., 'dev', 'prod').

```bash
python script.py <company> <env>
```

Example:

```bash
python script.py acmecorp dev
```

## Script Actions

The script performs the following actions:

1. Lists the OpenID Connect providers for the AWS account and retrieves the ARN of the first one.
2. Creates an IAM role named `{company}-{env}-k8s-services-roles` with a trust relationship to the OIDC provider.
3. Creates an IAM policy named `{company}-{env}-k8s-services-policy` with permissions for AWS Secrets Manager, S3, and MSK.
4. Attaches the created policy to the created role.

## Policy Details

The IAM policy created by this script contains the following permissions:

- Secrets Manager: Allows managing secrets and retrieving secret values.
- S3: Allows listing buckets and performing all object-related actions.
- MSK: Allows all actions on MSK clusters.
- Additional S3 permissions for object and object-lambda actions.

## Important Notes

- The script checks for the existence of the role and policy before attempting to create them. If they already exist, it will skip creation.
- The script assumes that the AWS account has at least one OIDC provider configured.
- The script requires that AWS credentials are properly set up in your environment.

## Troubleshooting

If you encounter issues, check the following:

- Ensure your AWS CLI is correctly configured with the right permissions.
- Verify that your Python environment has Boto3 installed.
- Confirm that you have the necessary IAM permissions to execute the script's operations.
