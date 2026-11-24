import boto3
import botocore.config
import json
import os
from datetime import datetime

# Initialize clients outside the handler so AWS Lambda reuses connections across warm invocations
bedrock = boto3.client(
    "bedrock-runtime",
    region_name="ap-southeast-2",
    config=botocore.config.Config(read_timeout=300, retries={"max_attempts": 3})
)
s3 = boto3.client("s3")


def blog_generate(blogtopic: str) -> str:
    prompt = f"Write a 200-word blog post on the topic: {blogtopic}"

    try:
        response = bedrock.converse(
            modelId="amazon.nova-pro-v1:0",  # Use "apac.amazon.nova-pro-v1:0" if cross-region profile is required in ap-southeast-2
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ],
            inferenceConfig={
                "maxTokens": 512,
                "temperature": 0.7,
                "topP": 0.9
            }
        )

        blog_details = response["output"]["message"]["content"][0]["text"]
        print(blog_details)
        return blog_details

    except Exception as e:
        print(f"Error generating the blog: {e}")
        return ""


def upload_to_s3(bucket_name: str, key: str, blog_content: str) -> bool:
    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=blog_content.encode("utf-8"),
            ContentType="text/plain"
        )
        print(f"Successfully uploaded to S3 bucket {bucket_name} with key {key}.")
        return True
    except Exception as e:
        print(f"Error uploading to S3: {e}")
        return False


def lambda_handler(event, context):
    # Handle both API Gateway proxy events (event["body"]) and direct Lambda console test events
    if "body" in event:
        event_body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
    else:
        event_body = event

    blogtopic = event_body.get("blogtopic", "").strip()
    if not blogtopic:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing 'blogtopic' in request payload."})
        }

    blog_content = blog_generate(blogtopic)

    if not blog_content:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to generate blog content from Amazon Bedrock."})
        }

    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    s3_key = f"blog-output/{current_time}.txt"
    s3_bucket_name = os.environ.get("S3_BUCKET_NAME", "aws-bedrock-blog")  # Replace with your actual bucket name

    uploaded = upload_to_s3(s3_bucket_name, s3_key, blog_content)
    if not uploaded:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Blog generated, but S3 upload failed."})
        }

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Blog generated and uploaded to S3 successfully!",
            "s3_key": s3_key
        })
    }