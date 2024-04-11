provider "aws" {
  region = "us-east-1"
}

#lambda with python 

resource "aws_lambda_function" "test_lambda" {
  filename      = "lambda.zip"
  function_name = "lambda_function_name"
  role          = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
  handler       = "lambda_function.lambda_handler"

  source_code_hash = filebase64sha256("lambda.zip")

  runtime = "python3.8"
}
