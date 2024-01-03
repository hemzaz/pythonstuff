#!/usr/bin/env python3
import boto3
import argparse
from pathlib import Path
from botocore.exceptions import ClientError


class TerraformBackendCreator:
    def __init__(self, envname, region, account_name="company"):
        self.envname = envname
        self.region = region
        self.account_name = account_name
        self.bucket_name = f"{self.account_name}-{self.envname}-tf-backend"
        self.dynamodb_table_name = "terraform-state-lock-dynamo"
        self.s3_client = boto3.client("s3", region_name=self.region)
        self.dynamodb_client = boto3.client("dynamodb", region_name=self.region)

    def create_s3_bucket(self):
        try:
            if self.region == "us-east-1":
                self.s3_client.create_bucket(Bucket=self.bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=self.bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": self.region},
                )
            print(f"S3 bucket '{self.bucket_name}' created successfully.")
        except ClientError as e:
            print(f"Failed to create S3 bucket: {e}")

    def enable_bucket_versioning(self):
        try:
            self.s3_client.put_bucket_versioning(
                Bucket=self.bucket_name, VersioningConfiguration={"Status": "Enabled"}
            )
            print(f"Versioning enabled on S3 bucket '{self.bucket_name}'.")
        except ClientError as e:
            print(f"Failed to enable versioning: {e}")

    def create_dynamodb_table(self):
        try:
            self.dynamodb_client.create_table(
                TableName=self.dynamodb_table_name,
                AttributeDefinitions=[
                    {"AttributeName": "LockID", "AttributeType": "S"}
                ],
                KeySchema=[{"AttributeName": "LockID", "KeyType": "HASH"}],
                BillingMode="PAY_PER_REQUEST",
            )
            print(f"DynamoDB table '{self.dynamodb_table_name}' created successfully.")
        except ClientError as e:
            print(f"Failed to create DynamoDB table: {e}")

    def print_terraform_backend_config(self):
        backend_config = f"""
terraform {{
  backend "s3" {{
    bucket         = "{self.bucket_name}"
    dynamodb_table = "{self.dynamodb_table_name}"
    key            = "{self.envname}.tfstate"
    region         = "{self.region}"
    encrypt        = true
  }}
}}
"""
        print("\nAdd the following configuration to your Terraform backend:\n")
        print(backend_config)

    def create_resources(self):
        self.create_s3_bucket()
        self.enable_bucket_versioning()
        self.create_dynamodb_table()
        self.print_terraform_backend_config()


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Create resources for Terraform backend."
    )
    parser.add_argument(
        "-e", "--envname", type=str, help="Environment name", default=Path.cwd().name
    )
    parser.add_argument(
        "-r", "--region", type=str, help="AWS Region", default="us-west-2"
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    backend_creator = TerraformBackendCreator(args.envname, args.region)
    backend_creator.create_resources()


if __name__ == "__main__":
    main()
