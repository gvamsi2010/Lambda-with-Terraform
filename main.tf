resource "aws_cloudwatch_event_rule" "scheduler_rule" {
  name                = "MyProgramaticRuleName"
  schedule_expression = var.schedule_expression
}

resource "aws_lambda_permission" "event_bridge_invoke_lambda_permission" {
  statement_id  = "AllowEventBridgeInvokeLambda"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scheduler_rule.arn
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.scheduler_rule.name
  arn       = var.lambda_function_arn
  target_id = "LambdaBTarget"

  input = jsonencode({
    data = var.target_input
  })
}


resource "aws_lambda_function" "example_lambda" {
  function_name    = "example_lambda_function"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_a.lambda_a"
  runtime          = "python3.8"
  filename         = "example_lambda.zip"  # Path to your Python code ZIP file
}

resource "aws_iam_role" "lambda_role" {
  name = "example_lambda_role"

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}
