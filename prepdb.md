# RDS User Management Script
## *WARNING: RUN ON NEW ENVIRONMENTS ONLY*
## Overview
This script is designed to manage PostgreSQL users on AWS RDS instances. It can create new users, update existing users' passwords, and store these passwords securely in AWS Secrets Manager. The script supports non-destructive operations by default and offers a forceful update mode.

## Features
- Connect to AWS RDS PostgreSQL instances.
- Create new database users with encrypted passwords.
- Update existing database users' passwords.
- Store and update passwords in AWS Secrets Manager.
- Non-destructive updates: Skips existing users unless forced.
- Ability to check login credentials.
- Skip operations on read replicas.

## Prerequisites
- Python 3
- Boto3
- Psycopg2
- AWS CLI (configured with appropriate permissions)

## Installation
1. Ensure Python 3 is installed on your system.
2. Install required Python packages:
   ```bash
   pip install boto3 psycopg2
   ```
3. Configure AWS CLI with the necessary credentials and permissions.

## Usage
Run the script using Python 3. The script accepts the following flags:
- `-check`: Run the script in check mode to only verify login credentials.
- `-force`: Forcefully update existing users and passwords.

Example:
```bash
python prepdb.py -check
python prepdb.py -force
```

## How It Works
The script lists all RDS instances and performs the following actions:
- Skips read replicas.
- For each instance, it checks if the specified user exists.
- If the user does not exist or if the `-force` flag is used, it creates/updates the user.
- Passwords are securely stored and managed in AWS Secrets Manager.

## Logging
The script logs its operations, providing insights into its execution process, including any errors encountered.
