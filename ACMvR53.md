# README for ACMvR53 Script

## Overview
The `ACMvR53.py` script is designed to automate the creation and validation of an AWS ACM (Amazon Certificate Manager) certificate using DNS validation. It also supports the creation of a hosted zone in AWS Route 53 and utilizes contact details from a `domain.yaml` file for domain registration.

## Features
- Request an ACM certificate for a specified domain and its subdomains.
- Automatically include both the base domain and a wildcard for subdomains in the certificate SANs (Subject Alternative Names).
- Create a new hosted zone in Route 53 if required.
- Use contact details from a `domain.yaml` file for hosted zone creation.
- Validate the ACM certificate using DNS validation.

## Prerequisites
- Python 3.x
- AWS CLI configured with appropriate permissions.
- `boto3` and `pyyaml` Python libraries (Install using `pip install boto3 pyyaml`).
- A `domain.yaml` file in the script's directory for contact details (optional).

## Installation
1. Ensure Python 3.x is installed on your system.
2. Install required Python libraries:
   ```bash
   pip install boto3 pyyaml
   ```
3. Place the `ACMvR53.py` script in your desired directory.

## Usage
Run the script from the command line, providing the necessary arguments:

```bash
./ACMvR53.py --domain [domain_name] [--region [aws_region]] [--san [additional_SANs]] [--create-zone]
```

### Arguments
- `--domain`: (Required) The domain name for the certificate.
- `--region`: (Optional) The AWS region for the ACM and Route 53 services. Defaults to 'us-east-1'.
- `--san`: (Optional) Additional Subject Alternative Names for the certificate. The script automatically includes the base domain and a wildcard for subdomains.
- `--create-zone`: (Optional) Flag to create a new hosted zone for the domain.

### Example
```bash
./ACMvR53.py --domain "example.com"
```

This command requests a certificate for `example.com` and `*.example.com`.

## domain.yaml File Format
If you choose to use a `domain.yaml` file for contact details, it should be formatted as follows:

```yaml
RegistrantContact:
  FirstName: "John"
  LastName: "Doe"
  Email: "john.doe@example.com"
  # ... other fields ...

AdminContact:
  # ... similar structure ...

TechContact:
  # ... similar structure ...
```

## Troubleshooting
- Ensure AWS CLI is properly configured with the necessary permissions.
- Check the format of the `domain.yaml` file if used.
- Verify network connectivity and AWS service availability.