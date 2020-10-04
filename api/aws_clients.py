import boto3

# AWS DynamoDB tables
ddb = boto3.resource('dynamodb', region_name='us-east-1')
MenuDatabase = ddb.Table("MenuDatabase")
OrderDatabase = ddb.Table("Orders")

# AWS S3 bucket 
restaurantS3Bucket = 'restaurant-api-menu-items'
s3Client = boto3.client('s3', region_name='us-east-1')
s3Resource = boto3.resource('s3', region_name='us-east-1')