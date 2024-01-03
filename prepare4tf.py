#!/usr/bin/env python3
import boto3
import os
import sys
from pathlib import Path

# Retrieve the environment name from the command line arguments or use the current directory name
if len(sys.argv) > 2:
    print("Usage: python create_terraform_backend.py [envname]")
    sys.exit(1)

envname = sys.argv[1] if len(sys.argv) == 2 else Path.cwd().name
account_name = "company"  # Replace with your actual company name
bucket_name = f"{account_name}-{envname}-tf-backend"
dynamodb_table_name = "terraform-state-lock-dynamo"

# Fetch the AWS default region from environment variable
region = os.environ.get("AWS_DEFAULT_REGION")
if not region:
    print("AWS_DEFAULT_REGION environment variable is not set.")
    sys.exit(1)

# Initialize the S3 and DynamoDB clients
s3_client = boto3.client("s3", region_name=region)
dynamodb_client = boto3.client("dynamodb", region_name=region)


# Create an S3 bucket for Terraform state storage
def create_s3_bucket(bucket_name):
    try:
        if region == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
            print(f"S3 bucket '{bucket_name}' created successfully.")
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        print(f"S3 bucket '{bucket_name}' created successfully.")
    except Exception as e:
        print(f"Failed to create S3 bucket: {e}")


# Enable versioning on the S3 bucket
def enable_bucket_versioning(bucket_name):
    try:
        s3_client.put_bucket_versioning(
            Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
        )
        print(f"Versioning enabled on S3 bucket '{bucket_name}'.")
    except Exception as e:
        print(f"Failed to enable versioning: {e}")


# Create a DynamoDB table for Terraform state locking
def create_dynamodb_table(table_name):
    try:
        dynamodb_client.create_table(
            TableName=table_name,
            AttributeDefinitions=[{"AttributeName": "LockID", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "LockID", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"DynamoDB table '{table_name}' created successfully.")
    except Exception as e:
        print(f"Failed to create DynamoDB table: {e}")


# Main function to create resources and output Terraform backend configuration
def main():
    create_s3_bucket(bucket_name)
    enable_bucket_versioning(bucket_name)
    create_dynamodb_table(dynamodb_table_name)

    # Output the Terraform backend configuration
    backend_config = f"""
terraform {{
  backend "s3" {{
    bucket         = "{bucket_name}"
    dynamodb_table = "{dynamodb_table_name}"
    key            = "{envname}.tfstate"
    region         = "{region}"
    encrypt        = true
  }}
}}
"""
    print("\nAdd the following configuration to your Terraform backend:\n")
    print(backend_config)


if __name__ == "__main__":
    main()
