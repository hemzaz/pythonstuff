#!/usr/bin/env python3
import boto3
import time
import argparse
import uuid
import os
import glob
import yaml
from botocore.exceptions import ClientError


class R53Error(Exception):
    pass


class DNSValidatedACMCertClient:
    def __init__(self, region):
        self.session = boto3.Session(region_name=region)
        self.acm = self.session.client("acm")
        self.route53 = self.session.client("route53")
        self.contact_details = self.discover_and_parse_yaml()

    def discover_and_parse_yaml(self):
        yaml_files = glob.glob(os.path.join(os.getcwd(), "domain.yaml"))
        if not yaml_files:
            print("No domain.yaml file found in the current directory.")
            return None

        with open(yaml_files[0], "r") as file:
            return yaml.safe_load(file)

    def request_certificate(self, domain_name, san_names):
        options = {"DomainName": domain_name, "ValidationMethod": "DNS"}
        if san_names:
            options["SubjectAlternativeNames"] = san_names

        response = self.acm.request_certificate(**options)
        return response["CertificateArn"]

    def get_certificate_status(self, certificate_arn):
        certificate = self.acm.describe_certificate(CertificateArn=certificate_arn)
        return certificate["Certificate"]["Status"]

    def wait_for_certificate_validation(
        self, certificate_arn, timeout=300, interval=30
    ):
        elapsed = 0
        while elapsed < timeout:
            status = self.get_certificate_status(certificate_arn)
            if status == "ISSUED":
                return True
            time.sleep(interval)
            elapsed += interval
        return False

    def get_domain_validation_records(self, certificate_arn):
        certificate = self.acm.describe_certificate(CertificateArn=certificate_arn)
        options = certificate["Certificate"]["DomainValidationOptions"]
        return [
            (opt["DomainName"], opt["ResourceRecord"])
            for opt in options
            if "ResourceRecord" in opt
        ]

    def create_hosted_zone(self, domain_name, caller_reference):
        hosted_zone_config = {
            "Name": domain_name,
            "CallerReference": caller_reference,
            "HostedZoneConfig": {"Comment": "Created by script", "PrivateZone": False},
        }

        if self.contact_details:
            hosted_zone_config["ContactDetails"] = self.contact_details

        try:
            response = self.route53.create_hosted_zone(**hosted_zone_config)
            return response["HostedZone"]["Id"].split("/")[-1]
        except ClientError as e:
            raise R53Error(f"Error creating hosted zone for {domain_name}: {str(e)}")

    def get_hosted_zone_id(self, domain_name):
        # Ensure the domain name ends with a dot for Route 53
        if not domain_name.endswith("."):
            domain_name += "."

        paginator = self.route53.get_paginator("list_hosted_zones")
        for page in paginator.paginate():
            for zone in page["HostedZones"]:
                if zone["Name"] == domain_name:
                    return zone["Id"].split("/")[-1]
        raise R53Error(f"No hosted zone found for domain {domain_name}")

    def create_dns_records(self, domain_validation_records, hosted_zone_id):
        changes = []
        for domain_name, record in domain_validation_records:
            # Ensure the record is correctly formatted
            if record["Type"] != "CNAME" or not record["Name"].endswith(
                domain_name + "."
            ):
                print(f"Invalid record format for domain {domain_name}: {record}")
                continue

            changes.append(
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": record["Name"],
                        "Type": record["Type"],
                        "TTL": 300,
                        "ResourceRecords": [{"Value": record["Value"]}],
                    },
                }
            )

        if not changes:
            print("No valid DNS changes to apply.")
            return

        try:
            self.route53.change_resource_record_sets(
                HostedZoneId=hosted_zone_id, ChangeBatch={"Changes": changes}
            )
        except ClientError as e:
            raise R53Error(f"Error creating DNS records: {str(e)}")


def main():
    parser = argparse.ArgumentParser(
        description="Create and validate an ACM certificate with DNS validation in AWS."
    )
    parser.add_argument(
        "--domain", required=True, help="The domain name for the certificate."
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        help="The AWS region for the ACM and Route 53 services.",
    )
    parser.add_argument(
        "--san",
        nargs="*",
        default=[],
        help="Subject Alternative Names for the certificate.",
    )
    parser.add_argument(
        "--create-zone",
        action="store_true",
        help="Create a new hosted zone for the domain.",
    )
    args = parser.parse_args()

    # Include both the base domain and a wildcard for subdomains in SANs
    san_names = set(args.san)
    san_names.add(args.domain)
    san_names.add(f"*.{args.domain}")

    client = DNSValidatedACMCertClient(region=args.region)

    hosted_zone_id = None
    if args.create_zone:
        caller_reference = f"{args.domain}_{str(uuid.uuid4())}"
        hosted_zone_id = client.create_hosted_zone(
            domain_name=args.domain, caller_reference=caller_reference
        )
        print(f"Created a new hosted zone with ID: {hosted_zone_id}")
    else:
        hosted_zone_id = client.get_hosted_zone_id(domain_name=args.domain)
        if hosted_zone_id is None:
            print(
                f"No hosted zone found for domain {args.domain}, unable to create DNS records for validation."
            )
            return

    certificate_arn = client.request_certificate(
        domain_name=args.domain, san_names=list(san_names)
    )
    print(f"Requested certificate for {args.domain} with ARN: {certificate_arn}")

    # Add a delay or implement a retry mechanism here if necessary
    time.sleep(30)  # Example: 30-second delay

    domain_validation_records = client.get_domain_validation_records(certificate_arn)
    if not domain_validation_records:
        print("No domain validation records available yet. Please try again later.")
        return

    client.create_dns_records(domain_validation_records, hosted_zone_id)
    print(f"DNS validation records created for {args.domain}")

    if client.wait_for_certificate_validation(certificate_arn):
        print(f"Certificate {certificate_arn} is issued and validated.")
    else:
        print(
            f"Certificate {certificate_arn} did not validate within the expected time."
        )


if __name__ == "__main__":
    main()
