#!/usr/bin/env python3
import boto3
from botocore.exceptions import ClientError
import psycopg2
from psycopg2 import sql
import secrets
import string
import logging
import json
import argparse

# Constants
DB_ADMIN_USER = "admin"

# Initialize logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Initialize the RDS and Secrets Manager clients
rds_client = boto3.client("rds")
secrets_manager_client = boto3.client("secretsmanager")

# Argument parser setup
parser = argparse.ArgumentParser(description="RDS Admin Check and User Creation Script")
parser.add_argument("-check", action="store_true", help="Run only the login check")
parser.add_argument(
    "-force", action="store_true", help="Forcefully update users and passwords"
)
args = parser.parse_args()


# Function to generate a random password
def generate_random_password(length=12):
    password_characters = string.ascii_letters + string.digits
    password = "".join(secrets.choice(password_characters) for i in range(length))
    return password


# Function to get the admin password from AWS Secrets Manager
def get_admin_password(secret_name):
    try:
        get_secret_value_response = secrets_manager_client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        logging.error(f"Unable to retrieve secret {secret_name}: {e}")
        return None
    else:
        return get_secret_value_response["SecretString"]


# Function to check if user exists
def user_exists(cur, username):
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (username,))
    return cur.fetchone() is not None


# Function to create or update user and grant privileges
def create_or_update_user(
    db_host, db_port, db_name, db_user, db_password, new_user, new_password
):
    user_created_or_updated = False
    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password,
        )
        conn.autocommit = True
        cur = conn.cursor()

        if user_exists(cur, new_user):
            if not args.force:
                logging.info(
                    f"User {new_user} already exists in database {db_name}. Skipping!."
                )
                return user_created_or_updated
            else:
                cur.execute(
                    sql.SQL("ALTER USER {} WITH ENCRYPTED PASSWORD %s").format(
                        sql.Identifier(new_user)
                    ),
                    [new_password],
                )
                logging.info(f"User {new_user} password updated in database {db_name}.")
                user_created_or_updated = True
        else:
            cur.execute(
                sql.SQL("CREATE USER {} WITH ENCRYPTED PASSWORD %s").format(
                    sql.Identifier(new_user)
                ),
                [new_password],
            )
            logging.info(f"User {new_user} created in database {db_name}.")
            user_created_or_updated = True

        cur.execute(
            sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                sql.Identifier(db_name), sql.Identifier(new_user)
            )
        )
        cur.close()
        conn.close()
    except psycopg2.Error as e:
        logging.error(f"Error creating/updating user {new_user}: {e}")

    return user_created_or_updated


# Function to store or update the new user's password in AWS Secrets Manager
def store_password_in_secrets_manager(secret_name, key, password):
    try:
        try:
            response = secrets_manager_client.get_secret_value(SecretId=secret_name)
            secret_dict = json.loads(response["SecretString"])
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                secret_dict = {}
            else:
                logging.error(f"Error retrieving secret {secret_name}: {e}")
                return

        secret_dict[key] = password
        secret_string = json.dumps(secret_dict)

        try:
            secrets_manager_client.update_secret(
                SecretId=secret_name, SecretString=secret_string
            )
            logging.info(f"Password updated in Secrets Manager under {secret_name}.")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                secrets_manager_client.create_secret(
                    Name=secret_name, SecretString=secret_string
                )
                logging.info(f"Password stored in Secrets Manager under {secret_name}.")
            else:
                logging.error(f"Error updating/creating secret {secret_name}: {e}")
    except ClientError as e:
        logging.error(f"Unable to store or update secret {secret_name}: {e}")


# Function to check RDS login
def check_rds_login(db_host, db_port, db_name, db_user, db_password):
    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password,
        )
        conn.close()
        logging.info(f"Successfully connected to {db_name} as {db_user}.")
        return True
    except psycopg2.Error as e:
        logging.error(f"Failed to connect to {db_name} as {db_user}: {e}")
        return False


# List all RDS instances
rds_instances = rds_client.describe_db_instances()

for instance in rds_instances["DBInstances"]:
    db_identifier = instance["DBInstanceIdentifier"]
    db_engine = instance["Engine"]
    db_name = instance["DBName"]  # Extract the actual database name

    # Check if the instance is a read replica
    if (
        "ReadReplicaSourceDBInstanceIdentifier" in instance
        and instance["ReadReplicaSourceDBInstanceIdentifier"]
    ):
        logging.info(f"Instance {db_identifier} is a read replica. Skipping!.")
        continue

    if db_engine in ["postgres", "aurora-postgresql"]:
        env_name, service_name = (
            db_identifier.split("-")[0],
            db_identifier.split("-")[1],
        )

        secret_name_suffix = (
            "" if service_name.lower().startswith("core") else "-service"
        )
        secret_name = f"{env_name}/{service_name}{secret_name_suffix}"

        admin_secret_name = f"{env_name}-{service_name}-db-admin-Password"
        admin_password = get_admin_password(admin_secret_name)

        if admin_password:
            if args.check:
                check_rds_login(
                    instance["Endpoint"]["Address"],
                    instance["Endpoint"]["Port"],
                    db_name,  # Use the actual database name
                    DB_ADMIN_USER,
                    admin_password,
                )
            else:
                if check_rds_login(
                    instance["Endpoint"]["Address"],
                    instance["Endpoint"]["Port"],
                    db_name,  # Use the actual database name
                    DB_ADMIN_USER,
                    admin_password,
                ):
                    new_user = f"service.{service_name}"
                    new_password = generate_random_password()

                    user_created_or_updated = create_or_update_user(
                        db_host=instance["Endpoint"]["Address"],
                        db_port=instance["Endpoint"]["Port"],
                        db_name=db_name,  # Use the actual database name
                        db_user=DB_ADMIN_USER,
                        db_password=admin_password,
                        new_user=new_user,
                        new_password=new_password,
                    )

                    if user_created_or_updated:
                        store_password_in_secrets_manager(
                            secret_name, "DB_PASSWORD", new_password
                        )
