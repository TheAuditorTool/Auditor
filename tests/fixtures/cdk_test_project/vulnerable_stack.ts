import * as cdk from "aws-cdk-lib";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as rds from "aws-cdk-lib/aws-rds";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as iam from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";

export class VulnerableStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const publicBucket = new s3.Bucket(this, "PublicBucket", {
      publicReadAccess: true,
      versioned: false,
    });

    const unprotectedBucket = new s3.Bucket(this, "UnprotectedBucket", {
      versioned: true,
    });

    const unencryptedDb = new rds.DatabaseInstance(this, "UnencryptedDB", {
      engine: rds.DatabaseInstanceEngine.POSTGRES,
      storageEncrypted: false,
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.BURSTABLE3,
        ec2.InstanceSize.MICRO,
      ),
      vpc: undefined,
    });

    const unencryptedVolume = new ec2.Volume(this, "UnencryptedVolume", {
      availabilityZone: "us-east-1a",
      size: cdk.Size.gibibytes(10),
      encrypted: false,
    });

    const unprotectedTable = new dynamodb.Table(this, "UnprotectedTable", {
      partitionKey: {
        name: "id",
        type: dynamodb.AttributeType.STRING,
      },
    });

    const wildcardPolicy = new iam.PolicyStatement({
      actions: ["*"],
      resources: ["arn:aws:s3:::my-bucket/*"],
    });

    const wildcardResourcePolicy = new iam.PolicyStatement({
      actions: ["s3:GetObject", "s3:PutObject"],
      resources: ["*"],
    });

    const adminRole = new iam.Role(this, "AdminRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName("AdministratorAccess"),
      ],
    });

    const openSgIpv4 = new ec2.SecurityGroup(this, "OpenSecurityGroupIPv4", {
      vpc: undefined,
      allowAllOutbound: true,
    });
    openSgIpv4.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(22),
      "SSH from anywhere",
    );

    const openSgIpv6 = new ec2.SecurityGroup(this, "OpenSecurityGroupIPv6", {
      vpc: undefined,
      allowAllOutbound: false,
    });
    openSgIpv6.addIngressRule(
      ec2.Peer.anyIpv6(),
      ec2.Port.tcp(443),
      "HTTPS from anywhere IPv6",
    );
  }
}
