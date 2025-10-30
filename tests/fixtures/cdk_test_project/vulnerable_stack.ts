/**
 * Test CDK stack with security vulnerabilities for extraction verification.
 *
 * This TypeScript CDK stack contains the SAME vulnerabilities as vulnerable_stack.py
 * to verify parity between Python and TypeScript CDK extraction.
 */

import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

/**
 * CDK stack with intentional security misconfigurations for testing.
 */
export class VulnerableStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // VULN: Public S3 bucket
    const publicBucket = new s3.Bucket(this, 'PublicBucket', {
      publicReadAccess: true,
      versioned: false
    });

    // VULN: Unencrypted RDS instance
    const unencryptedDb = new rds.DatabaseInstance(this, 'UnencryptedDB', {
      engine: rds.DatabaseInstanceEngine.POSTGRES,
      storageEncrypted: false,
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.BURSTABLE3,
        ec2.InstanceSize.MICRO
      ),
      vpc: undefined  // Placeholder - would fail at synth, but we're only testing extraction
    });

    // VULN: Open security group
    const openSg = new ec2.SecurityGroup(this, 'OpenSecurityGroup', {
      vpc: undefined,  // Placeholder - would fail at synth, but we're only testing extraction
      allowAllOutbound: true
    });
  }
}
