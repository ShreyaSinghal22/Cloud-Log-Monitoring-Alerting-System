
import json
import boto3
import csv
import io
import urllib.parse
from datetime import datetime

# AWS clients
s3_client = boto3.client('s3')
cloudwatch = boto3.client('cloudwatch', region_name='ap-south-1')  # Change to your region

def lambda_handler(event, context):
    """
    Triggered when a new log file is uploaded to S3.
    Parses the log, extracts metrics, and pushes to CloudWatch.
    """
    
    # --- 1. Get the uploaded file details from the S3 event ---
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    object_key = urllib.parse.unquote_plus(
        event['Records'][0]['s3']['object']['key']
    )
    
    print(f"Processing file: s3://{bucket_name}/{object_key}")
    
    # --- 2. Read the file from S3 ---
    response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
    file_content = response['Body'].read().decode('utf-8')
    
    # --- 3. Parse the CSV log file ---
    reader = csv.DictReader(io.StringIO(file_content))
    
    total_requests = 0
    error_4xx_count = 0
    error_5xx_count = 0
    error_ips = []
    
    for row in reader:
        total_requests += 1
        
        # Get status code - handle different possible column names
        status = str(row.get('status', row.get('Status', row.get('status_code', '200')))).strip()
        ip = row.get('ip', row.get('IP', row.get('host', 'unknown'))).strip()
        
        if status.startswith('4'):
            error_4xx_count += 1
            error_ips.append(ip)
        elif status.startswith('5'):
            error_5xx_count += 1
            error_ips.append(ip)
    
    print(f"Total Requests: {total_requests}")
    print(f"4xx Errors: {error_4xx_count}")
    print(f"5xx Errors: {error_5xx_count}")
    
    # --- 4. Push Metrics to CloudWatch ---
    namespace = 'LogMonitoring/WebServer'
    
    cloudwatch.put_metric_data(
        Namespace=namespace,
        MetricData=[
            {
                'MetricName': 'TotalRequests',
                'Value': total_requests,
                'Unit': 'Count'
            },
            {
                'MetricName': 'Error4xx',
                'Value': error_4xx_count,
                'Unit': 'Count'
            },
            {
                'MetricName': 'Error5xx',
                'Value': error_5xx_count,
                'Unit': 'Count'
            },
            {
                'MetricName': 'ErrorRate',
                'Value': round((error_4xx_count + error_5xx_count) / max(total_requests, 1) * 100, 2),
                'Unit': 'Percent'
            }
        ]
    )
    
    print("✅ Metrics pushed to CloudWatch successfully!")
    
    # --- 5. Return summary ---
    return {
        'statusCode': 200,
        'body': json.dumps({
            'total_requests': total_requests,
            '4xx_errors': error_4xx_count,
            '5xx_errors': error_5xx_count,
            'error_rate_percent': round((error_4xx_count + error_5xx_count) / max(total_requests, 1) * 100, 2)
        })
    }
