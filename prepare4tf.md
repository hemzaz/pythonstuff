# README for prepare4tf.py Script

## Overview
The `prepare4tf.py` script is designed to automate the setup of a Terraform backend using AWS services. It simplifies the process of creating an S3 bucket for Terraform state storage and a DynamoDB table for state locking. This script is particularly useful for setting up a robust and scalable Terraform backend infrastructure.

## Features
- **S3 Bucket Creation**: Automatically creates an S3 bucket for storing Terraform state files.
- **Versioning**: Enables versioning on the created S3 bucket to keep a history of state changes.
- **DynamoDB Table Creation**: Sets up a DynamoDB table for state locking, preventing concurrent state modifications.
- **Terraform Backend Configuration Output**: Generates the necessary Terraform backend configuration snippet.

## Prerequisites
- Python 3.x installed.
- AWS CLI installed and configured with appropriate permissions.
- `boto3` Python library installed (Install using `pip install boto3`).
- AWS account with permissions to create S3 buckets and DynamoDB tables.

## Installation
1. Ensure Python 3.x and AWS CLI are installed on your system.
2. Install the `boto3` library:
   ```bash
   pip install boto3
   ```
3. Download or copy the `prepare4tf.py` script to your desired directory.

## Usage
Run the script from the command line, optionally providing an environment name:

```bash
python prepare4tf.py [envname]
```

- If no environment name (`envname`) is provided, the script uses the name of the current directory.
- The script constructs the S3 bucket and DynamoDB table names using the provided or derived environment name.

### Example
```bash
python prepare4tf.py dev
```

This command sets up the Terraform backend for the "dev" environment.

## Output
Upon successful execution, the script outputs the Terraform backend configuration snippet, which can be directly used in your Terraform configuration files:

```hcl
terraform {
  backend "s3" {
    bucket         = "company-dev-tf-backend"
    dynamodb_table = "terraform-state-lock-dynamo"
    key            = "dev.tfstate"
    region         = "us-east-1"
    encrypt        = true
  }
}
```

## Troubleshooting
- Ensure that the AWS CLI is properly configured with the necessary permissions.
- Verify that the `boto3` library is correctly installed.
- Check for any error messages in the script output for clues on any issues encountered.

