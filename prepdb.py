#!/usr/bin/env python3
import boto3
from botocore.exceptions import ClientError
import psycopg2
from psycopg2 import sql
import secrets
import string
import logging
import json
from contextlib import contextmanager
import argparse

# Configuration and constants
DB_ADMIN_USER = "admin"
DEFAULT_PASSWORD_LENGTH = 12

# Initialize the RDS and Secrets Manager clients
rds_client = boto3.client("rds")
secrets_manager_client = boto3.client("secretsmanager")

@contextmanager
def db_connection(db_params):
    conn = psycopg2.connect(**db_params)
    try:
        yield conn
    finally:
        conn.close()

def generate_random_password(length=DEFAULT_PASSWORD_LENGTH):
    password_characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(password_characters) for i in range(length))

def get_admin_password(secret_name):
    try:
        get_secret_value_response = secrets_manager_client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        logging.error(f"Unable to retrieve secret {secret_name}: {e}")
        return None
    else:
        return get_secret_value_response["SecretString"]

def user_exists(cur, username):
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (username,))
    return cur.fetchone() is not None

def create_or_update_user(db_params, new_user, new_password, force_update=False):
    with db_connection(db_params) as conn:
        cur = conn.cursor()
        if user_exists(cur, new_user):
            if not force_update:
                logging.info(f"User {new_user} already exists. Skipping!")
                return False
            cur.execute(
                sql.SQL("ALTER USER {} WITH ENCRYPTED PASSWORD %s").format(
                    sql.Identifier(new_user)
                ),
                [new_password],
            )
            logging.info(f"User {new_user} password updated.")
        else:
            cur.execute(
                sql.SQL("CREATE USER {} WITH ENCRYPTED PASSWORD %s").format(
                    sql.Identifier(new_user)
                ),
                [new_password],
            )
            logging.info(f"User {new_user} created.")
        cur.execute(
            sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                sql.Identifier(db_params['dbname']), sql.Identifier(new_user)
            )
        )
        return True

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

        secrets_manager_client.update_secret(
            SecretId=secret_name, SecretString=secret_string
        )
        logging.info(f"Password updated in Secrets Manager under {secret_name}.")
    except ClientError as e:
        logging.error(f"Unable to store or update secret {secret_name}: {e}")

def check_rds_login(db_params):
    try:
        with db_connection(db_params) as conn:
            logging.info(f"Successfully connected to {db_params['dbname']} as {db_params['user']}.")
            return True
    except psycopg2.Error as e:
        logging.error(f"Failed to connect to {db_params['dbname']} as {db_params['user']}: {e}")
        return False

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description="RDS Admin Check and User Creation Script")
    parser.add_argument("-c", "--check", action="store_true", help="Run only the login check")
    parser.add_argument("-f", "--force", action="store_true", help="Forcefully update users and passwords")
    args = parser.parse_args()

    rds_instances = rds_client.describe_db_instances()

    for instance in rds_instances["DBInstances"]:
        db_identifier = instance["DBInstanceIdentifier"]
        db_engine = instance["Engine"]
        db_name = instance["DBName"]

        if db_engine not in ["postgres", "aurora-postgresql"]:
            logging.info(f"Instance {db_identifier} is not a PostgreSQL instance. Skipping!")
            continue

        env_name, service_name = db_identifier.split("-")[0], db_identifier.split("-")[1]
        secret_name_suffix = "" if service_name.lower().startswith("core") else "-service"
        secret_name = f"{env_name}/{service_name}{secret_name_suffix}"
        admin_secret_name = f"{env_name}-{service_name}-db-admin-Password"
        admin_password = get_admin_password(admin_secret_name)

        if admin_password:
            db_params = {
                "host": instance["Endpoint"]["Address"],
                "port": instance["Endpoint"]["Port"],
                "dbname": db_name,
                "user": DB_ADMIN_USER,
                "password": admin_password,
            }
            if args.check:
                check_rds_login(db_params)
            else:
                if check_rds_login(db_params):
                    new_user = f"service.{service_name}"
                    new_password = generate_random_password()
                    if create_or_update_user(db_params, new_user, new_password, args.force):
                        store_password_in_secrets_manager(secret_name, "DB_PASSWORD", new_password)

if __name__ == "__main__":
    main()
