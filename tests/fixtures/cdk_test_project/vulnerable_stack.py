"""Test CDK stack with security vulnerabilities for extraction verification."""

from aws_cdk import Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from constructs import Construct


class VulnerableStack(Stack):
    """CDK stack with intentional security misconfigurations for testing.

    Coverage for all CDK security rules:
    - aws_cdk_encryption: RDS, EBS, DynamoDB
    - aws_cdk_iam_wildcards: actions, resources, AdministratorAccess
    - aws_cdk_s3_public: public_read_access, missing block_public_access
    - aws_cdk_security_groups: 0.0.0.0/0, ::/0, allow_all_outbound
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # VULN 1: Public S3 bucket (CRITICAL - public_read_access)
        s3.Bucket(
            self,
            "PublicBucket",
            public_read_access=True,
            versioned=False
        )

        # VULN 2: S3 bucket missing block_public_access (HIGH)
        s3.Bucket(
            self,
            "UnprotectedBucket",
            versioned=True
            # block_public_access is missing (should be BLOCK_ALL)
        )

        # VULN 3: Unencrypted RDS instance (HIGH)
        rds.DatabaseInstance(
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

        # VULN 4: Unencrypted EBS volume (HIGH)
        ec2.Volume(
            self,
            "UnencryptedVolume",
            availability_zone="us-east-1a",
            size=10,
            encrypted=False
        )

        # VULN 5: DynamoDB with default encryption (MEDIUM)
        dynamodb.Table(
            self,
            "UnprotectedTable",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            )
            # encryption is missing (defaults to DEFAULT, not CUSTOMER_MANAGED)
        )

        # VULN 6: IAM policy with wildcard actions (HIGH)
        iam.PolicyStatement(
            actions=["*"],  # Wildcard action
            resources=["arn:aws:s3:::my-bucket/*"]
        )

        # VULN 7: IAM policy with wildcard resources (HIGH)
        iam.PolicyStatement(
            actions=["s3:GetObject", "s3:PutObject"],
            resources=["*"]  # Wildcard resource
        )

        # VULN 8: IAM role with AdministratorAccess (CRITICAL)
        iam.Role(
            self,
            "AdminRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
            ]
        )

        # VULN 9: Security group with 0.0.0.0/0 ingress (CRITICAL)
        open_sg_ipv4 = ec2.SecurityGroup(
            self,
            "OpenSecurityGroupIPv4",
            vpc=None,  # Placeholder
            allow_all_outbound=True  # VULN 10: Allow all outbound (LOW)
        )
        open_sg_ipv4.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),  # 0.0.0.0/0
            connection=ec2.Port.tcp(22),
            description="SSH from anywhere"
        )

        # VULN 11: Security group with ::/0 ingress (CRITICAL)
        open_sg_ipv6 = ec2.SecurityGroup(
            self,
            "OpenSecurityGroupIPv6",
            vpc=None,  # Placeholder
            allow_all_outbound=False
        )
        open_sg_ipv6.add_ingress_rule(
            peer=ec2.Peer.any_ipv6(),  # ::/0
            connection=ec2.Port.tcp(443),
            description="HTTPS from anywhere IPv6"
        )
