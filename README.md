# Serverless Blog Generation API (AWS Bedrock + Lambda + S3)

![Python](https://img.shields.io/badge/Python-3.15-3776AB?style=flat&logo=python&logoColor=white)
![AWS Lambda](https://img.shields.io/badge/AWS-Lambda-FF9900?style=flat&logo=awslambda&logoColor=white)
![Amazon Bedrock](https://img.shields.io/badge/Amazon-Bedrock-232F3E?style=flat&logo=amazonaws&logoColor=white)
![Amazon S3](https://img.shields.io/badge/Amazon-S3-569A31?style=flat&logo=amazons3&logoColor=white)

A serverless Generative AI backend that generates structured 200-word blog posts on demand using **Amazon Bedrock (Amazon Nova Pro)** via the Converse API, orchestrated through **AWS Lambda**, exposed via **Amazon API Gateway**, and persisted automatically to **Amazon S3**.

---

## Architecture

```text
┌───────────────────┐       POST /dev/blog-generation       ┌─────────────────────────┐
│  Client           │ ────────────────────────────────────▶ │  Amazon API Gateway     │
│  (Postman / cURL) │                                       │  (HTTP API - dev stage) │
└───────────────────┘                                       └───────────┬─────────────┘
                                                                        │
                                                                        ▼
┌───────────────────┐       Converse API (Nova Pro)         ┌─────────────────────────┐
│  Amazon Bedrock   │ ◀──────────────────────────────────── │  AWS Lambda             │
│  (ap-southeast-2) │ ────────────────────────────────────▶ │  Python 3.15            │
└───────────────────┘       Generated Blog Content          │  + Boto3 1.44.10 Layer  │
                                                            └───────────┬─────────────┘
                                                                        │
                                                                        ▼
                                                            ┌─────────────────────────┐
                                                            │  Amazon S3              │
                                                            │  blog-output/*.txt      │
                                                            └─────────────────────────┘
```

---

## Tech Stack

| Component | Service / Technology | Details |
| :--- | :--- | :--- |
| **Foundation Model** | Amazon Bedrock (`Amazon Nova Pro`) | Invoked via `bedrock-runtime` `converse()` API (`apac.amazon.nova-pro-v1:0`) |
| **Compute** | AWS Lambda | Python 3.15 (`x86_64`) with custom `boto3==1.44.10` Lambda Layer |
| **API Layer** | Amazon API Gateway | HTTP API with `POST /blog-generation` route deployed to `dev` stage |
| **Storage** | Amazon S3 | Stores generated posts as UTF-8 `.txt` files under `blog-output/` |
| **Observability** | Amazon CloudWatch | Execution logs, latency metrics, and error diagnostics |
| **Region** | `ap-southeast-2` | Asia Pacific (Sydney) |

---

## Project Structure

```text
BlogGeneration/
├── lambda_function.py   # AWS Lambda handler, Bedrock Converse client, and S3 uploader
├── requirements.txt     # Python dependencies (boto3==1.44.10)
├── .gitignore           # Excludes venv, local layer builds, zip archives, and secrets
└── README.md            # Project documentation
```

---

## Prerequisites

* An active AWS account with **Amazon Bedrock** model invocation enabled in `ap-southeast-2`.
* **Python 3.15** and `pip` installed locally (for packaging the custom Lambda Layer).
* **Postman** or `curl` for testing the deployed endpoint.

---

## Setup & Deployment

### 1. Create the S3 Bucket
1. Open the **Amazon S3 Console** in `ap-southeast-2`.
2. Create a globally unique General Purpose bucket (e.g., `kashyap-aws-bedrock-blog-2026`).

### 2. Build & Upload the Custom Boto3 Lambda Layer
Package `boto3==1.44.10` for the Linux `x86_64` Lambda runtime:

```bash
mkdir lambda_layer\python
pip install boto3==1.44.10 --target lambda_layer\python --platform manylinux2014_x86_64 --implementation cp --python-version 3.15 --only-binary=:all:
tar -a -c -f boto3-1-44-10-layer.zip -C lambda_layer python
```

1. In the **AWS Lambda Console**, navigate to **Layers → Create layer**.
2. Upload `boto3-1-44-10-layer.zip` with architecture **`x86_64`** and compatible runtime **`Python 3.15`**.

### 3. Configure the AWS Lambda Function
1. Create a new Lambda function using runtime **`Python 3.15`** (`x86_64`).
2. Deploy `lambda_function.py` and attach the custom `boto3` layer created in Step 2.
3. Under **Configuration → General configuration**, increase **Timeout** to **`60 seconds`**.
4. Under **Configuration → Environment variables**, optionally add:
   * `S3_BUCKET_NAME`: Your S3 bucket name.
5. Under **Configuration → Permissions**, attach the following policies (or scoped least-privilege equivalents) to the function's IAM execution role:
   * `bedrock:InvokeModel` (or `AmazonBedrockFullAccess`)
   * `s3:PutObject` on your target bucket (or `AmazonS3FullAccess`)

### 4. Configure Amazon API Gateway
1. Create an **HTTP API** in API Gateway.
2. Add a **`POST /blog-generation`** route and integrate it with your Lambda function.
3. Deploy the API to the **`dev`** stage and copy the generated **Invoke URL**.

---

## API Reference

### Generate a Blog Post

```http
POST /dev/blog-generation
Content-Type: application/json
```

#### Request Body
```json
{
  "blogtopic": "Machine Learning and Generative AI"
}
```

#### Example (`cURL`)
```bash
curl -X POST https://<api-id>[.execute-api.ap-southeast-2.amazonaws.com/dev/blog-generation](https://.execute-api.ap-southeast-2.amazonaws.com/dev/blog-generation) \
  -H "Content-Type: application/json" \
  -d '{"blogtopic": "Machine Learning and Generative AI"}'
```

#### Expected Responses

> **Note on Live Execution:** The serverless infrastructure (API Gateway, AWS Lambda with custom `boto3` layer, CloudWatch, and S3) is fully deployed and verified end-to-end. Live Amazon Bedrock model inference (`Converse` API) is currently pending AWS account-level Bedrock access verification (`ValidationException: Operation not allowed`), so the `200 OK` response below reflects the expected output once model invocation is enabled on the account.

* **`200 OK`** *(Expected once Bedrock access is enabled)* — Blog generated and uploaded to S3:
  ```json
  {
    "message": "Blog generated and uploaded to S3 successfully!",
    "bucket": "<your-s3-bucket-name>",
    "s3_key": "blog-output/<timestamp>.txt"
  }
  ```

* **`400 Bad Request`** — Missing `blogtopic` field in payload:
  ```json
  {
    "error": "Missing 'blogtopic' in request payload."
  }
  ```

* **`500 Internal Server Error`** — Bedrock invocation or S3 upload error (check CloudWatch Logs for details):
  ```json
  {
    "error": "Failed to generate blog content from Amazon Bedrock."
  }
  ```

---

## Key Implementation Details

* **Connection Reuse:** `bedrock-runtime` and `s3` Boto3 clients are initialized outside `lambda_handler` so warm Lambda invocations reuse HTTP connections.
* **Dual Event Parsing:** `lambda_handler` gracefully handles both API Gateway proxy events (`event["body"]`) and direct AWS Lambda Console test payloads.
* **URL-Safe S3 Keys:** Output files are timestamped using `YYYY-MM-DD_HH-MM-SS.txt` to avoid URL-encoding issues with colons and spaces.

---

## Author

**Kashyap Sundaragiri**