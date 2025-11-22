/**
 * Test CDK stack with security vulnerabilities for extraction verification.
 *
 * This TypeScript CDK stack contains the SAME vulnerabilities as vulnerable_stack.py
 * to verify parity between Python and TypeScript CDK extraction.
 *
 * Coverage for all CDK security rules:
 * - aws_cdk_encryption: RDS, EBS, DynamoDB
 * - aws_cdk_iam_wildcards: actions, resources, AdministratorAccess
 * - aws_cdk_s3_public: publicReadAccess, missing blockPublicAccess
 * - aws_cdk_security_groups: 0.0.0.0/0, ::/0, allowAllOutbound
 */

import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

/**
 * CDK stack with intentional security misconfigurations for testing.
 */
export class VulnerableStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // VULN 1: Public S3 bucket (CRITICAL - publicReadAccess)
    const publicBucket = new s3.Bucket(this, 'PublicBucket', {
      publicReadAccess: true,
      versioned: false
    });

    // VULN 2: S3 bucket missing blockPublicAccess (HIGH)
    const unprotectedBucket = new s3.Bucket(this, 'UnprotectedBucket', {
      versioned: true
      // blockPublicAccess is missing (should be BlockPublicAccess.BLOCK_ALL)
    });

    // VULN 3: Unencrypted RDS instance (HIGH)
    const unencryptedDb = new rds.DatabaseInstance(this, 'UnencryptedDB', {
      engine: rds.DatabaseInstanceEngine.POSTGRES,
      storageEncrypted: false,
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.BURSTABLE3,
        ec2.InstanceSize.MICRO
      ),
      vpc: undefined  // Placeholder - would fail at synth, but we're only testing extraction
    });

    // VULN 4: Unencrypted EBS volume (HIGH)
    const unencryptedVolume = new ec2.Volume(this, 'UnencryptedVolume', {
      availabilityZone: 'us-east-1a',
      size: cdk.Size.gibibytes(10),
      encrypted: false
    });

    // VULN 5: DynamoDB with default encryption (MEDIUM)
    const unprotectedTable = new dynamodb.Table(this, 'UnprotectedTable', {
      partitionKey: {
        name: 'id',
        type: dynamodb.AttributeType.STRING
      }
      // encryption is missing (defaults to DEFAULT, not CUSTOMER_MANAGED)
    });

    // VULN 6: IAM policy with wildcard actions (HIGH)
    const wildcardPolicy = new iam.PolicyStatement({
      actions: ['*'],  // Wildcard action
      resources: ['arn:aws:s3:::my-bucket/*']
    });

    // VULN 7: IAM policy with wildcard resources (HIGH)
    const wildcardResourcePolicy = new iam.PolicyStatement({
      actions: ['s3:GetObject', 's3:PutObject'],
      resources: ['*']  // Wildcard resource
    });

    // VULN 8: IAM role with AdministratorAccess (CRITICAL)
    const adminRole = new iam.Role(this, 'AdminRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('AdministratorAccess')
      ]
    });

    // VULN 9: Security group with 0.0.0.0/0 ingress (CRITICAL)
    const openSgIpv4 = new ec2.SecurityGroup(this, 'OpenSecurityGroupIPv4', {
      vpc: undefined,  // Placeholder
      allowAllOutbound: true  // VULN 10: Allow all outbound (LOW)
    });
    openSgIpv4.addIngressRule(
      ec2.Peer.anyIpv4(),  // 0.0.0.0/0
      ec2.Port.tcp(22),
      'SSH from anywhere'
    );

    // VULN 11: Security group with ::/0 ingress (CRITICAL)
    const openSgIpv6 = new ec2.SecurityGroup(this, 'OpenSecurityGroupIPv6', {
      vpc: undefined,  // Placeholder
      allowAllOutbound: false
    });
    openSgIpv6.addIngressRule(
      ec2.Peer.anyIpv6(),  // ::/0
      ec2.Port.tcp(443),
      'HTTPS from anywhere IPv6'
    );
  }
}
