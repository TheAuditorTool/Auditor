"""Test CDK stack with security vulnerabilities for extraction verification."""

from aws_cdk import Stack
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_rds as rds
from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class VulnerableStack(Stack):
    """CDK stack with intentional security misconfigurations for testing."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # VULN: Public S3 bucket
        public_bucket = s3.Bucket(
            self,
            "PublicBucket",
            public_read_access=True,
            versioned=False
        )

        # VULN: Unencrypted RDS instance
        unencrypted_db = rds.DatabaseInstance(
            self,
            "UnencryptedDB",
            engine=rds.DatabaseInstanceEngine.POSTGRES,
            storage_encrypted=False,
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3,
                ec2.InstanceSize.MICRO
            ),
            vpc=None  # Placeholder
        )

        # VULN: Open security group
        open_sg = ec2.SecurityGroup(
            self,
            "OpenSecurityGroup",
            vpc=None,  # Placeholder
            allow_all_outbound=True
        )
