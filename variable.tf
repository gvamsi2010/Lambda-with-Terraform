variable "lambda_function_name" {
  description = "Name of the Lambda function to be scheduled"
}

variable "lambda_function_arn" {
  description = "ARN of the Lambda function to be scheduled"
}

variable "schedule_expression" {
  description = "Schedule expression for EventBridge rule"
}

variable "target_input" {
  description = "Input data for the target Lambda function"
}
